"""Correction rounds for exchanges whose delivered files failed validation.

`collect_defects` diagnoses a response directory and `build_repair_prompt` turns
that diagnosis into an instruction the user can send in the same ChatGPT
conversation. `open_repair_round` records the round and re-arms monitoring so the
corrected downloads land in the same exchange.

The diagnosis here is deliberately separate from `downloads._parse_main_response`.
That function is a strict gate that decides whether a file may be moved and stops
at the first problem. This module reports every problem at once and never moves
anything.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from companion.core import (
    _active_path_for,
    claimed_deliverable_names,
    _exchange_dir,
    _read_json_object,
    _safe_name,
    _sha256,
    _write_json_atomic,
    load_active_call,
    load_active_calls,
)
from companion.downloads import archive_member_index
from companion.lock import state_lock

REPAIRABLE_STATES = {"ACTIVE", "INCOMPLETE", "COMPLETE"}


def collect_defects(exchange_dir: Path) -> list[dict[str, Any]]:
    """Return every reason the delivered response fails validation."""
    exchange = Path(exchange_dir).resolve()
    manifest = _read_json_object(
        exchange / "EXCHANGE_MANIFEST.json", "EXCHANGE_MANIFEST"
    )
    expected_main = _safe_name(
        str(manifest["expected_main_json"]), "expected main JSON filename"
    )
    request_id = str(manifest["request_id"])
    response_dir = exchange / "response"
    main_path = response_dir / expected_main
    defects: list[dict[str, Any]] = []

    if not main_path.is_file():
        return [
            _defect(
                "MAIN_MISSING",
                expected_main,
                f"a downloadable file named {expected_main}",
                "no such file was delivered",
            )
        ]

    try:
        raw = json.loads(main_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return [
            _defect(
                "MAIN_NOT_JSON",
                expected_main,
                "a single valid UTF-8 JSON object",
                f"the file could not be parsed: {error}",
            )
        ]
    if not isinstance(raw, dict):
        return [
            _defect(
                "MAIN_NOT_OBJECT",
                expected_main,
                "a JSON object at the top level",
                f"the top level is {type(raw).__name__}",
            )
        ]

    if raw.get("request_id") != request_id:
        defects.append(
            _defect(
                "REQUEST_ID_MISMATCH",
                expected_main,
                f'request_id "{request_id}"',
                f"request_id {json.dumps(raw.get('request_id'))}",
            )
        )

    status = raw.get("status")
    if status not in {"COMPLETE", "PARTIAL", "BLOCKED"}:
        defects.append(
            _defect(
                "STATUS_INVALID",
                expected_main,
                "status COMPLETE, PARTIAL, or BLOCKED",
                f"status {json.dumps(status)}",
            )
        )

    expected_downloads = tuple(
        str(name) for name in manifest.get("expected_artifacts", [])
    )
    defects.extend(_artifact_defects(raw, response_dir, expected_main))
    defects.extend(
        _delivery_defects(raw, expected_main, response_dir, expected_downloads)
    )
    defects.extend(_undeclared_expected_defects(raw, manifest, response_dir))
    return defects


def build_repair_prompt(
    exchange_dir: Path,
    defects: list[dict[str, Any]],
    round_number: int,
) -> str:
    """Render the correction instruction for the current round."""
    exchange = Path(exchange_dir).resolve()
    manifest = _read_json_object(
        exchange / "EXCHANGE_MANIFEST.json", "EXCHANGE_MANIFEST"
    )
    expected_main = str(manifest["expected_main_json"])
    request_id = str(manifest["request_id"])

    lines = [
        f"CORRECTION ROUND {round_number} for request_id {request_id}.",
        "",
        "Your previous delivery did not pass deterministic local validation.",
        "Do not apologize, summarize, or restate the assignment. Fix exactly the",
        "problems listed below and deliver corrected downloadable files.",
        "",
        "PROBLEMS FOUND",
    ]
    for index, defect in enumerate(defects, 1):
        lines.append(f"{index}. [{defect['kind']}] {defect['target']}")
        lines.append(f"   expected: {defect['expected']}")
        lines.append(f"   observed: {defect['observed']}")
    lines.extend(
        [
            "",
            "HOW TO FIX",
            "- Regenerate only the files named above. Every other delivered file must",
            "  stay byte-identical; do not rewrite work that already validated.",
            "- Write each file first, then compute its SHA-256 and byte size from the",
            "  bytes you actually wrote, then emit the main JSON last using those",
            "  measured values. Declaring a digest computed from an earlier draft is",
            "  the most common cause of this failure.",
            f'- Keep request_id exactly "{request_id}".',
            "- artifacts_manifest must list every created file once, with filename,",
            "  status CREATED, media_type, exact size in bytes, and exact sha256.",
            "  A file inside the outputs archive belongs in this list too, with its",
            "  own hash.",
            f"- delivery must list only what is downloadable: {expected_main} and the",
            "  outputs archive. Do not repeat the archive's members there.",
            "- If a file genuinely cannot be produced, set its status to NOT_CREATED,",
            "  leave it out of delivery, set the top-level status to PARTIAL, and give",
            "  the reason in limitations.",
            "",
            "DELIVERY",
            f"- Return no conversational text. Deliver only {expected_main} and the",
            "  corrected artifacts as downloadable files.",
        ]
    )
    return "\n".join(lines) + "\n"


def open_repair_round(
    root: Path,
    exchange_id: str,
    tab_id: int | None = None,
    download_baseline: list[int] | None = None,
) -> dict[str, Any]:
    """Record a correction round and re-arm monitoring for the same exchange."""
    root = Path(root).resolve()
    exchange = _exchange_dir(root, exchange_id)
    manifest_path = exchange / "EXCHANGE_MANIFEST.json"
    manifest = _read_json_object(manifest_path, "EXCHANGE_MANIFEST")
    state = manifest.get("state")
    if state not in REPAIRABLE_STATES:
        raise RuntimeError(f"exchange cannot be repaired from state {state}")

    active = load_active_call(root, exchange_id)
    if tab_id is not None:
        for other in load_active_calls(root):
            if other.get("exchange_id") != exchange_id and other.get("tab_id") == tab_id:
                raise RuntimeError(
                    f"tab {tab_id} is already bound to call {other['exchange_id']}"
                )

    # Reopening a finished exchange re-claims its deliverable names, and a
    # finished exchange has already released them. If another call took them in
    # the meantime, two calls able to receive files would expect the same
    # filename, which is the one thing download routing cannot survive. Checked
    # before anything is written, so a refusal leaves no orphan round behind.
    claimed = claimed_deliverable_names(root, exclude_exchange_id=exchange_id)
    for name in [
        str(manifest["expected_main_json"]),
        *[str(item) for item in manifest.get("expected_artifacts", [])],
    ]:
        owner = claimed.get(name.casefold())
        if owner:
            raise RuntimeError(
                f"call {owner} now expects the filename {name}, which this "
                "exchange released when it finished. Reopening it would leave two "
                "calls expecting the same download. Finish or delete that call "
                "first, or raise a new correction call with its own filenames."
            )

    defects = collect_defects(exchange)
    if not defects:
        raise RuntimeError("the delivered response has no validation defects")

    round_number = int(manifest.get("repair_round", 0)) + 1
    prompt = build_repair_prompt(exchange, defects, round_number)
    repair_dir = exchange / "repair"
    repair_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = repair_dir / f"ROUND_{round_number}_PROMPT.txt"
    defects_path = repair_dir / f"ROUND_{round_number}_DEFECTS.json"
    opened_at = datetime.now(timezone.utc).isoformat()
    prompt_path.write_text(prompt, encoding="utf-8", newline="\n")
    _write_json_atomic(
        defects_path,
        {
            "schema_version": 1,
            "exchange_id": exchange_id,
            "request_id": manifest["request_id"],
            "round": round_number,
            "opened_at": opened_at,
            "defects": defects,
        },
    )

    resolved_tab = tab_id if tab_id is not None else active.get("tab_id") if active else None
    if resolved_tab is None:
        raise ValueError("tab_id is required when no call is active")
    if not isinstance(resolved_tab, int) or isinstance(resolved_tab, bool) or resolved_tab < 0:
        raise ValueError("tab_id must be a non-negative integer")
    baseline = sorted(set(download_baseline or []))
    if any(not isinstance(item, int) or isinstance(item, bool) or item < 0 for item in baseline):
        raise ValueError("download_baseline must contain non-negative integers")

    reopened = {
        "exchange_id": exchange_id,
        "exchange_path": str(exchange),
        "request_id": manifest["request_id"],
        "expected_main_json": manifest["expected_main_json"],
        "tab_id": resolved_tab,
        "started_at": opened_at,
        "monitoring": True,
        "repair_round": round_number,
        "download_baseline": baseline,
        "observed_download_ids": [],
        "collected_files": list(active.get("collected_files", [])) if active else [],
    }
    manifest["state"] = "ACTIVE"
    manifest["repair_round"] = round_number
    manifest.setdefault("repairs", []).append(
        {
            "round": round_number,
            "opened_at": opened_at,
            "state_before": state,
            "defect_kinds": sorted({defect["kind"] for defect in defects}),
            "prompt_file": prompt_path.name,
            "defects_file": defects_path.name,
        }
    )
    active_path = _active_path_for(root, exchange_id)
    with state_lock(root):
        _write_json_atomic(active_path, reopened)
        try:
            _write_json_atomic(manifest_path, manifest)
        except BaseException:
            active_path.unlink(missing_ok=True)
            raise
    return {
        "exchange_id": exchange_id,
        "round": round_number,
        "defects": defects,
        "prompt": prompt,
        "prompt_path": str(prompt_path),
        "defects_path": str(defects_path),
        "active": reopened,
    }


def _artifact_defects(
    raw: dict[str, Any], response_dir: Path, expected_main: str
) -> list[dict[str, Any]]:
    artifacts = raw.get("artifacts_manifest")
    if not isinstance(artifacts, list):
        return [
            _defect(
                "ARTIFACTS_MANIFEST_INVALID",
                expected_main,
                "artifacts_manifest as a JSON array",
                f"artifacts_manifest is {type(artifacts).__name__}",
            )
        ]

    defects: list[dict[str, Any]] = []
    members: dict[str, tuple[str, int]] | None = None
    for position, artifact in enumerate(artifacts, 1):
        label = f"artifacts_manifest[{position}]"
        if not isinstance(artifact, dict):
            defects.append(
                _defect(
                    "ARTIFACT_ENTRY_INVALID",
                    label,
                    "a JSON object per artifact",
                    f"entry is {type(artifact).__name__}",
                )
            )
            continue
        name = artifact.get("filename")
        if not isinstance(name, str) or not name or Path(name).name != name:
            defects.append(
                _defect(
                    "ARTIFACT_ENTRY_INVALID",
                    label,
                    "filename as a plain file name with no path separators",
                    f"filename {json.dumps(name)}",
                )
            )
            continue
        if name.casefold() == expected_main.casefold():
            # Self-reference. The declared digest can never be right, because the
            # file would have to contain the hash of itself. Saying "recompute
            # the hash" here would ask for something impossible and the
            # correction round would never converge.
            defects.append(
                _defect(
                    "MAIN_JSON_LISTED_AS_ARTIFACT",
                    name,
                    "artifacts_manifest to list only the additional files, never "
                    "the main JSON itself",
                    f"artifacts_manifest contains an entry for {name}, which is "
                    "the main JSON. Remove that entry entirely. Keep the file "
                    "listed in delivery, which is correct.",
                )
            )
            continue
        status = artifact.get("status")
        if status not in {"CREATED", "MISSING", "NOT_CREATED"}:
            defects.append(
                _defect(
                    "ARTIFACT_ENTRY_INVALID",
                    name,
                    "status CREATED, MISSING, or NOT_CREATED",
                    f"status {json.dumps(status)}",
                )
            )
            continue
        if status != "CREATED":
            continue

        declared_size = artifact.get("size")
        declared_digest = artifact.get("sha256")
        media_type = artifact.get("media_type")
        if not isinstance(media_type, str) or not media_type:
            defects.append(
                _defect(
                    "ARTIFACT_ENTRY_INVALID",
                    name,
                    "media_type as a non-empty string",
                    f"media_type {json.dumps(media_type)}",
                )
            )
        if not isinstance(declared_size, int) or isinstance(declared_size, bool) or declared_size < 0:
            defects.append(
                _defect(
                    "ARTIFACT_ENTRY_INVALID",
                    name,
                    "size as a non-negative integer byte count",
                    f"size {json.dumps(declared_size)}",
                )
            )
            declared_size = None
        if not isinstance(declared_digest, str) or not re.fullmatch(
            r"[0-9a-fA-F]{64}", declared_digest
        ):
            defects.append(
                _defect(
                    "ARTIFACT_ENTRY_INVALID",
                    name,
                    "sha256 as 64 hexadecimal characters",
                    f"sha256 {json.dumps(declared_digest)}",
                )
            )
            declared_digest = None

        # A declared artifact is either a file beside the main JSON or a member of
        # the archive that came down with it. Looking only on disk made every
        # declared member of a byte-exact archive an ARTIFACT_MISSING defect, and
        # told the operator to spend a correction round repairing nothing.
        path = response_dir / name
        if path.is_file():
            resolved = _sha256(path)
        else:
            if members is None:
                members = archive_member_index(response_dir)
            resolved = members.get(name.casefold())
        if resolved is None:
            defects.append(
                _defect(
                    "ARTIFACT_MISSING",
                    name,
                    "the file to be delivered, beside the main JSON or inside the "
                    "outputs archive",
                    "it was declared CREATED but is neither a delivered file nor a "
                    "member of a delivered archive",
                )
            )
            continue
        actual_digest, actual_size = resolved
        if declared_size is not None and declared_size != actual_size:
            defects.append(
                _defect(
                    "ARTIFACT_SIZE_MISMATCH",
                    name,
                    f"size {declared_size} bytes, as your manifest declared",
                    f"the delivered file is {actual_size} bytes",
                )
            )
        if declared_digest is not None and declared_digest.casefold() != actual_digest:
            defects.append(
                _defect(
                    "ARTIFACT_HASH_MISMATCH",
                    name,
                    f"sha256 {declared_digest.casefold()}, as your manifest declared",
                    f"the delivered file hashes to {actual_digest}",
                )
            )
    return defects


def _undeclared_expected_defects(
    raw: dict[str, Any], manifest: dict[str, Any], response_dir: Path
) -> list[dict[str, Any]]:
    """Catch a promised artifact that the main JSON never mentions at all."""
    declared_in_main = set()
    artifacts = raw.get("artifacts_manifest")
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if isinstance(artifact, dict) and isinstance(artifact.get("filename"), str):
                declared_in_main.add(artifact["filename"].casefold())

    defects: list[dict[str, Any]] = []
    for item in manifest.get("expected_artifacts", []):
        name = _safe_name(str(item), "expected artifact filename")
        if name.casefold() in declared_in_main:
            continue
        if (response_dir / name).is_file():
            continue
        defects.append(
            _defect(
                "EXPECTED_ARTIFACT_ABSENT",
                name,
                "this artifact, which the call was prepared to expect",
                "it is neither listed in artifacts_manifest nor delivered",
            )
        )
    return defects


def _delivery_defects(
    raw: dict[str, Any],
    expected_main: str,
    response_dir: Path,
    expected_downloads: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    delivery = raw.get("delivery")
    if not isinstance(delivery, list) or any(
        not isinstance(item, str) for item in delivery
    ):
        return [
            _defect(
                "DELIVERY_INVALID",
                expected_main,
                "delivery as an array of file names",
                f"delivery is {json.dumps(delivery)[:120]}",
            )
        ]

    # `delivery` names what came down as downloads, which is one archive with
    # the main JSON inside it. A created artifact that lives inside that archive
    # was never separately downloadable, so requiring it here reported a correct
    # delivery as incomplete. Only files that arrived on their own belong in the
    # requirement, and the main JSON no longer does — naming it stays acceptable
    # because it is the response and older exchanges did download it.
    delivered = {item.casefold() for item in delivery}
    required: set[str] = set()
    if not delivered & ({expected_main.casefold()} | {name.casefold() for name in expected_downloads}):
        required.add(expected_main.casefold())
    artifacts = raw.get("artifacts_manifest")
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if (
                isinstance(artifact, dict)
                and artifact.get("status") == "CREATED"
                and isinstance(artifact.get("filename"), str)
                and (response_dir / artifact["filename"]).is_file()
            ):
                required.add(artifact["filename"].casefold())
    absent = sorted(required - delivered)
    if not absent:
        return []
    return [
        _defect(
            "DELIVERY_INCOMPLETE",
            expected_main,
            "delivery to name the outputs archive and every separately "
            "downloaded file",
            "delivery omits " + ", ".join(absent),
        )
    ]


def _defect(kind: str, target: str, expected: str, observed: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "target": target,
        "expected": expected,
        "observed": observed,
    }
