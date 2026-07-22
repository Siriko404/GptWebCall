"""Wait for a web call to reach a terminal state and print one line saying which.

Written for an agent watching an exchange it cannot click through itself. Sina
drives Go, Attach, Send, the downloads and Done by hand; the agent has no way to
know when that finished short of asking him, which wastes a turn and makes him
the polling mechanism. This script is the alarm instead: arm it after `prepare`,
keep working, and one line arrives when the exchange settles.

It prints nothing at all until the exchange settles, then prints exactly one
line and exits. That makes it correct as the command of a background watch,
where every stdout line becomes a notification and a chatty poller becomes spam.

The one design rule worth stating: it fires on EVERY terminal state, not just
the happy one. A watcher that only recognises COMPLETE stays silent through a
failed validation, and silence is indistinguishable from still waiting. So
INCOMPLETE and STOPPED each get their own line, and INCOMPLETE says plainly that
repair is the next move rather than reading.

Usage:
    python scripts/watch_exchange.py [EXCHANGE_ID] [--interval SECONDS]

With no EXCHANGE_ID it watches the newest exchange sitting in PREPARED or
ACTIVE, which is the common case of having just prepared one. If several are in
flight it refuses to guess and says so, because picking the wrong one would
report a result that belongs to another call.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALLS = ROOT / "calls"

# downloads.py assigns manifest["state"] from the validation report status, and
# core.py assigns STOPPED. Nothing else is an end state.
TERMINAL = {"COMPLETE", "INCOMPLETE", "STOPPED"}
WAITING = {"PREPARED", "ACTIVE"}


def read_manifest(exchange_dir: Path) -> dict | None:
    """Return the manifest, or None if it is missing or mid-write.

    The companion rewrites this file while the agent is reading it. A partial
    read raises JSONDecodeError, which means "try again", not "the call failed".
    """
    path = exchange_dir / "EXCHANGE_MANIFEST.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_validation(exchange_dir: Path) -> dict:
    path = exchange_dir / "validation" / "VALIDATION_REPORT.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def pick_exchange() -> Path:
    candidates = []
    for directory in sorted(CALLS.iterdir()):
        if not directory.is_dir():
            continue
        manifest = read_manifest(directory)
        if manifest and manifest.get("state") in WAITING:
            candidates.append(directory)
    if not candidates:
        sys.exit("no exchange is PREPARED or ACTIVE; name one explicitly")
    if len(candidates) > 1:
        names = ", ".join(d.name for d in candidates)
        sys.exit(f"several exchanges are in flight, name one: {names}")
    return candidates[0]


def describe(exchange_dir: Path, manifest: dict) -> str:
    state = manifest["state"]
    subject = manifest.get("subject", "?")
    main = manifest.get("expected_main_json", "?")
    report = read_validation(exchange_dir)
    where = exchange_dir / "response"

    if state == "COMPLETE":
        checked = ", ".join(report.get("checked_files", [])) or main
        return f"READY  {subject}  validated: {checked}  in {where}"

    if state == "INCOMPLETE":
        missing = ", ".join(report.get("missing_files", [])) or "none listed"
        invalid = ", ".join(report.get("invalid_files", [])) or "none listed"
        return (
            f"FAILED VALIDATION  {subject}  missing: {missing}  invalid: {invalid}"
            f"  run repair, do not read this as a result"
        )

    return f"STOPPED  {subject}  the call was abandoned, nothing to read"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("exchange_id", nargs="?")
    parser.add_argument("--interval", type=float, default=15.0)
    args = parser.parse_args()

    if args.exchange_id:
        exchange_dir = CALLS / args.exchange_id
        if not exchange_dir.is_dir():
            sys.exit(f"no such exchange: {args.exchange_id}")
    else:
        exchange_dir = pick_exchange()

    while True:
        manifest = read_manifest(exchange_dir)
        if manifest and manifest.get("state") in TERMINAL:
            print(describe(exchange_dir, manifest), flush=True)
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
