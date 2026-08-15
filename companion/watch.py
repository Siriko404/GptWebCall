"""Lifecycle observation for one exchange: a durable failure record, and a
wait that turns "the call ended" into a process exit.

The coding agent that prepared a call has no way to hear about it finishing.
Nothing can push into a running session; a session can, however, start a
process and be re-entered when that process exits. `wait_for_event` is that
process. It polls the filesystem database — the same one both entry points
already share — and returns when the watched exchange reaches an ending the
agent should see. The exit is the notification.

It never holds the state lock. Reads race writers by design: every state file
is written atomically via os.replace, so a read sees the old file or the new
one, never half of either. A manifest that is transiently unreadable is
retried before it is believed to be broken.

`record_download_failure` exists because of the one ending that used to leave
no trace on disk: Chrome finished writing a file and the extension could not
file it into its call. The extension's own record of that lives in session
storage, which a browser restart erases. This writes the same fact somewhere
durable, attributed to the call whose expected filename it matches, so both
the panel after a restart and a waiting agent can see it.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from companion.core import (
    _active_path_for,
    _exchange_dir,
    _read_json_object,
    _write_json_atomic,
    load_active_call,
    load_active_calls,
)
from companion.downloads import _matches_expected_name
from companion.lock import state_lock

POLL_MS_DEFAULT = 500
POLL_MS_MINIMUM = 50
# Enough retries to ride out an os.replace window or a transient read error,
# few enough that a genuinely corrupt manifest surfaces in under two seconds.
_UNREADABLE_POLL_LIMIT = 3
# Per-call and global caps. These are attention records, not logs: the newest
# few are what anyone acts on, and an unbounded list in the active record would
# grow inside a file that is rewritten on every download event.
FAILURES_KEPT_PER_CALL = 10
FAILURES_KEPT_GLOBAL = 20
_MESSAGE_LIMIT = 500

# A call has ended when its manifest carries a terminal state AND no active
# record remains. Both are needed: a correction round puts a terminal manifest
# back to ACTIVE, and `done` deletes the active record in the same locked step
# that writes the terminal state.
TERMINAL_STATES = {"COMPLETE", "INCOMPLETE", "STOPPED"}


class WaitInconsistency(RuntimeError):
    """The exchange is present but persistently unreadable.

    Deliberately not an ending: the caller is woken to inspect, not told the
    call finished. The CLI maps this to its own exit code so a session cannot
    mistake it for success or for an ordinary usage error.
    """


def record_download_failure(root: Path, failure: dict[str, Any]) -> dict[str, Any]:
    """Persist one download-filing failure where it can still be seen later.

    Attribution is by expected filename, the same and only key download routing
    itself uses. A failure that matches an active call's expected files goes
    into that call's active record, which is what `wait_for_event` watches and
    what the panel receives from `calls.active` after a restart. Anything else
    goes to a small global file, because inventing an owner would be worse than
    admitting there is none.
    """
    root = Path(root).resolve()
    message = failure.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("failure message is required")
    download_id = failure.get("download_id")
    if download_id is not None and (
        not isinstance(download_id, int)
        or isinstance(download_id, bool)
        or download_id < 0
    ):
        raise ValueError("download_id must be a non-negative integer when given")
    filename = failure.get("filename")
    if filename is not None and not isinstance(filename, str):
        raise ValueError("filename must be a string when given")

    record = {
        # The companion stamps the time. A caller-supplied timestamp would be
        # one more field to trust from the side that just failed.
        "at": datetime.now(timezone.utc).isoformat(),
        "download_id": download_id,
        "filename": Path(filename).name if filename else None,
        "message": message.strip()[:_MESSAGE_LIMIT],
    }

    with state_lock(root):
        attributed_to = _attribute_failure(root, record)
        if attributed_to is None:
            _append_global_failure(root, record)
    return {"attributed_to": attributed_to, "recorded": record}


def _attribute_failure(root: Path, record: dict[str, Any]) -> str | None:
    if not record["filename"]:
        return None
    for active in load_active_calls(root):
        exchange_id = str(active.get("exchange_id", ""))
        try:
            exchange = _exchange_dir(root, exchange_id)
            manifest = _read_json_object(
                exchange / "EXCHANGE_MANIFEST.json", "EXCHANGE_MANIFEST"
            )
        except (FileNotFoundError, ValueError):
            continue
        expected = [
            str(manifest.get("expected_main_json", "")),
            *[str(item) for item in manifest.get("expected_artifacts", [])],
        ]
        if not any(
            name and _matches_expected_name(record["filename"], name)
            for name in expected
        ):
            continue
        failures = list(active.get("download_failures", []))
        failures.append(record)
        active["download_failures"] = failures[-FAILURES_KEPT_PER_CALL:]
        _write_json_atomic(_active_path_for(root, exchange_id), active)
        return exchange_id
    return None


def _append_global_failure(root: Path, record: dict[str, Any]) -> None:
    path = root / "state" / "DOWNLOAD_FAILURES.json"
    failures: list[Any] = []
    if path.is_file():
        try:
            stored = _read_json_object(path, "DOWNLOAD_FAILURES")
            if isinstance(stored.get("failures"), list):
                failures = stored["failures"]
        except ValueError:
            failures = []
    failures.append(record)
    _write_json_atomic(
        path,
        {"schema_version": 1, "failures": failures[-FAILURES_KEPT_GLOBAL:]},
    )


def _snapshot(root: Path, exchange_id: str) -> dict[str, Any] | None:
    """One lockless read of everything an ending can be recognised from.

    None means the exchange directory itself is gone. An unreadable manifest
    raises ValueError, which the wait loop retries and this function does not
    hide — swallowing it here would turn a corrupt exchange into an eternal
    quiet wait.
    """
    try:
        exchange = _exchange_dir(root, exchange_id)
    except FileNotFoundError:
        return None
    manifest = _read_json_object(
        exchange / "EXCHANGE_MANIFEST.json", "EXCHANGE_MANIFEST"
    )
    active = load_active_call(root, exchange_id)
    report_path = exchange / "validation" / "VALIDATION_REPORT.json"
    main_path = exchange / "response" / str(manifest.get("expected_main_json", ""))
    return {
        "state": str(manifest.get("state", "")),
        "active": active is not None,
        "repair_round": int(manifest.get("repair_round", 0) or 0),
        "failures": len(active.get("download_failures", [])) if active else 0,
        "validation_report": str(report_path) if report_path.is_file() else None,
        "main_response": str(main_path) if main_path.is_file() else None,
        "active_record": (
            str(_active_path_for(root, exchange_id)) if active else None
        ),
    }


def _terminal(snap: dict[str, Any]) -> bool:
    return snap["state"] in TERMINAL_STATES and not snap["active"]


def wait_for_event(
    root: Path,
    exchange_id: str,
    *,
    poll_ms: int = POLL_MS_DEFAULT,
    timeout_seconds: float | None = None,
    after_current: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Block until the watched exchange produces an event, then report it once.

    Events, from the taxonomy of ways a call actually ends:

    - COMPLETE / INCOMPLETE / STOPPED — the manifest reached a terminal state
      and no active record remains. Done, the terminal rescue, and Stop all
      land here; the waiter does not care which hand moved the file.
    - DELETED — the exchange directory disappeared after the wait began.
    - REPAIR_OPENED — the repair round counter rose. Not an ending: the call is
      ACTIVE again, and a session that wants its true end waits again.
    - DOWNLOAD_FILING_FAILED — the call's durable failure list grew. The call
      is still running; a human needs to look before Done loses the file.
    - STILL_WAITING — the caller's own timeout expired. Absence of an event is
      reported as exactly that, never dressed up as an ending, because an
      abandoned call writes nothing and only the caller can decide how long
      nothing is worth waiting on.

    A wake-up is a fact about state, not permission to act on the response:
    whoever is woken still validates and reads before trusting anything.

    Without `after_current`, an already-terminal exchange returns immediately —
    asking about a finished call is answered, not queued. With it, the present
    situation becomes the baseline and only the next transition reports, which
    is how a session waits out a correction round on a call that is already
    INCOMPLETE.
    """
    root = Path(root).resolve()
    poll_ms = int(poll_ms)
    if poll_ms < POLL_MS_MINIMUM:
        raise ValueError(f"poll_ms must be at least {POLL_MS_MINIMUM}")
    if timeout_seconds is not None and float(timeout_seconds) < 0:
        raise ValueError("timeout_seconds must not be negative")

    baseline = _snapshot(root, exchange_id)
    if baseline is None:
        # Absent at first sight is a caller mistake, not a DELETED event: an
        # event needs a before, and there is none.
        raise FileNotFoundError(f"exchange does not exist: {exchange_id}")

    def report(event: str, snap: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "exchange_id": exchange_id,
            "event": event,
            "state": None if snap is None else snap["state"],
            "repair_round": 0 if snap is None else snap["repair_round"],
            "validation_report": None if snap is None else snap["validation_report"],
            "main_response": None if snap is None else snap["main_response"],
            "attention_record": (
                snap["active_record"]
                if snap is not None and event == "DOWNLOAD_FILING_FAILED"
                else None
            ),
        }

    if not after_current and _terminal(baseline):
        return report(baseline["state"], baseline)

    deadline = (
        None if timeout_seconds is None else monotonic() + float(timeout_seconds)
    )
    unreadable = 0
    current = baseline
    while True:
        if deadline is not None and monotonic() >= deadline:
            return report("STILL_WAITING", current)
        sleep(poll_ms / 1000)
        try:
            snap = _snapshot(root, exchange_id)
        except ValueError as error:
            unreadable += 1
            if unreadable >= _UNREADABLE_POLL_LIMIT:
                raise WaitInconsistency(
                    f"exchange {exchange_id} is present but unreadable: {error}"
                ) from error
            continue
        unreadable = 0
        if snap is None:
            return report("DELETED", None)
        if snap["repair_round"] > baseline["repair_round"]:
            return report("REPAIR_OPENED", snap)
        if snap["failures"] > baseline["failures"]:
            return report("DOWNLOAD_FILING_FAILED", snap)
        if _terminal(snap) and (
            not _terminal(baseline) or snap["state"] != baseline["state"]
        ):
            return report(snap["state"], snap)
        current = snap
