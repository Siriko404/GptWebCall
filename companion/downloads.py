from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from companion.core import (
    _active_path_for,
    _exchange_dir,
    _read_json_object,
    _safe_name,
    _sha256,
    _write_json_atomic,
    load_active_call,
    load_active_calls,
)
from companion.lock import state_lock


def handle_completed_download(root: Path, download: dict[str, Any]) -> dict[str, Any]:
    """Route one completed download to whichever active call named it.

    Attribution is by filename, not by tab, because Chrome does not tell an
    extension which tab produced a download. `start_call` therefore refuses to
    run two calls that expect the same main JSON name.
    """
    root = Path(root).resolve()
    download_id = download.get("id")
    if not isinstance(download_id, int) or download_id < 0:
        raise ValueError("download id must be a non-negative integer")
    if download.get("state", "complete") != "complete":
        raise ValueError("download is not complete")
    filename = download.get("filename")
    if not isinstance(filename, str) or not filename:
        raise ValueError("completed download filename is required")
    source = Path(filename).resolve(strict=True)
    if not source.is_file():
        raise ValueError(f"completed download is not a regular file: {source.name}")

    with state_lock(root):
        every = load_active_calls(root)
        if not every:
            raise RuntimeError("no call is active")
        watching = [record for record in every if record.get("monitoring")]
        if not watching:
            return {"status": "IGNORED", "reason": "monitoring is stopped"}
        if any(
            download_id in record.get("observed_download_ids", [])
            for record in watching
        ):
            return {"status": "DUPLICATE", "download_id": download_id}
        candidates = [
            record
            for record in watching
            if download_id not in record.get("download_baseline", [])
        ]
        if not candidates:
            return {"status": "IGNORED", "reason": "download predates Go"}

        named_main = [
            record
            for record in candidates
            if _matches_expected_name(source.name, _expected_main(record))
        ]
        if len(named_main) > 1:
            return {
                "status": "AMBIGUOUS",
                "download_id": download_id,
                "error": "several active calls expect "
                f"{source.name}: "
                + ", ".join(str(record["exchange_id"]) for record in named_main),
            }
        if named_main:
            return _accept_main_json(root, named_main[0], source, download_id)

        claims = []
        for record in candidates:
            main = _stored_main(record)
            if main is None:
                continue
            artifact = _matching_artifact(main, source.name)
            if artifact is not None:
                claims.append((record, artifact))
        if len(claims) > 1:
            return {
                "status": "AMBIGUOUS",
                "download_id": download_id,
                "error": f"several active calls list {source.name}: "
                + ", ".join(str(record["exchange_id"]) for record, _ in claims),
            }
        if claims:
            record, artifact = claims[0]
            exchange = Path(record["exchange_path"]).resolve()
            result = _move_artifact(
                source, exchange, artifact, _supersede_round(record)
            )
            record.setdefault("observed_download_ids", []).append(download_id)
            if result["status"] == "MOVED":
                _record_collected(record, artifact["filename"])
            _save_active(root, record)
            return result | {
                "download_id": download_id,
                "exchange_id": record["exchange_id"],
            }

        if any(_stored_main(record) is None for record in candidates):
            _hold_pending(root, download_id, source)
            return {"status": "PENDING", "download_id": download_id}
        return {"status": "IGNORED", "reason": "not listed by the main JSON"}


def finish_call(root: Path, exchange_id: str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    with state_lock(root):
        active = load_active_call(root, exchange_id)
        if active is None:
            raise RuntimeError("no call is active")

        active["monitoring"] = False
        _save_active(root, active)
        exchange = Path(active["exchange_path"]).resolve()
        manifest_path = exchange / "EXCHANGE_MANIFEST.json"
        manifest = _read_json_object(manifest_path, "EXCHANGE_MANIFEST")
        main = _stored_main(active)
        if main is not None:
            _release_pending(root, active, exchange, main, _supersede_round(active))
            _save_active(root, active)

        report = validate_response(exchange)
        _write_json_atomic(exchange / "validation" / "VALIDATION_REPORT.json", report)
        manifest["state"] = report["status"]
        _write_json_atomic(manifest_path, manifest)
        _write_json_atomic(
            root / "state" / "LAST_RESULT.json",
            {"exchange_id": manifest["exchange_id"], "report": report},
        )
        _active_path_for(root, active["exchange_id"]).unlink(missing_ok=True)
    return report


def _accept_main_json(
    root: Path, record: dict[str, Any], source: Path, download_id: int
) -> dict[str, Any]:
    exchange = Path(record["exchange_path"]).resolve()
    expected_main = _expected_main(record)
    supersede_round = _supersede_round(record)
    record.setdefault("observed_download_ids", []).append(download_id)
    try:
        main = _parse_main_response(source, record["request_id"], expected_main)
        _safe_move(source, exchange / "response" / expected_main, supersede_round)
    except FileExistsError as error:
        _save_active(root, record)
        return {"status": "CONFLICT", "error": str(error)}
    except (OSError, ValueError) as error:
        _save_active(root, record)
        return {"status": "INVALID", "error": str(error)}
    _record_collected(record, expected_main)
    released = _release_pending(root, record, exchange, main, supersede_round)
    _save_active(root, record)
    return {
        "status": "MOVED",
        "download_id": download_id,
        "exchange_id": record["exchange_id"],
        "stored_name": expected_main,
        "released_pending": released,
    }


def _expected_main(record: dict[str, Any]) -> str:
    """The main JSON filename for an active call.

    Records written before parallel calls existed do not carry the name, so it
    is read back from the exchange manifest.
    """
    name = record.get("expected_main_json")
    if not name:
        manifest = _read_json_object(
            Path(record["exchange_path"]) / "EXCHANGE_MANIFEST.json",
            "EXCHANGE_MANIFEST",
        )
        name = manifest["expected_main_json"]
    return _safe_name(str(name), "expected main JSON filename")


def _stored_main(record: dict[str, Any]) -> dict[str, Any] | None:
    """The already-collected main JSON for a call, or None when it is absent."""
    expected_main = _expected_main(record)
    path = Path(record["exchange_path"]) / "response" / expected_main
    if not path.is_file():
        return None
    try:
        return _parse_main_response(path, record["request_id"], expected_main)
    except ValueError:
        return None


def validate_response(exchange_dir: Path) -> dict[str, Any]:
    exchange = Path(exchange_dir).resolve()
    manifest = _read_json_object(
        exchange / "EXCHANGE_MANIFEST.json", "EXCHANGE_MANIFEST"
    )
    expected_main = _safe_name(
        str(manifest["expected_main_json"]), "expected main JSON filename"
    )
    main_path = exchange / "response" / expected_main
    missing: list[str] = []
    invalid: list[str] = []
    checked: list[str] = []

    if not main_path.is_file():
        missing.append(expected_main)
        return _validation_report(manifest, expected_main, missing, invalid, checked)

    try:
        main = _parse_main_response(main_path, manifest["request_id"], expected_main)
    except ValueError:
        invalid.append(expected_main)
        return _validation_report(manifest, expected_main, missing, invalid, checked)

    checked.append(expected_main)
    if main["status"] != "COMPLETE":
        invalid.append(expected_main)
    for artifact in main["artifacts_manifest"]:
        if artifact["status"] != "CREATED":
            continue
        name = artifact["filename"]
        path = exchange / "response" / name
        if not path.is_file():
            missing.append(name)
            continue
        digest, size = _sha256(path)
        if digest != artifact["sha256"] or size != artifact["size"]:
            invalid.append(name)
            continue
        checked.append(name)

    # An artifact the call was prepared to expect must arrive even when the main
    # JSON forgets to declare it, otherwise a silently dropped deliverable
    # validates as complete.
    for declared in manifest.get("expected_artifacts", []):
        name = _safe_name(str(declared), "expected artifact filename")
        if not (exchange / "response" / name).is_file():
            missing.append(name)
    return _validation_report(manifest, expected_main, missing, invalid, checked)


def finalize_exchange(root: Path, exchange_id: str) -> dict[str, Any]:
    root = Path(root).resolve()
    if load_active_call(root, exchange_id) is not None:
        raise RuntimeError("an active call must be finished with done or stop")
    exchange = _exchange_dir(root, exchange_id)
    manifest_path = exchange / "EXCHANGE_MANIFEST.json"
    manifest = _read_json_object(manifest_path, "EXCHANGE_MANIFEST")
    if manifest.get("state") not in {"PREPARED", "INCOMPLETE", "COMPLETE"}:
        raise RuntimeError(f"exchange cannot be validated from state {manifest.get('state')}")
    report = validate_response(exchange)
    _write_json_atomic(exchange / "validation" / "VALIDATION_REPORT.json", report)
    manifest["state"] = report["status"]
    _write_json_atomic(manifest_path, manifest)
    _write_json_atomic(
        root / "state" / "LAST_RESULT.json",
        {"exchange_id": exchange_id, "report": report},
    )
    return report


def _validation_report(
    manifest: dict[str, Any],
    expected_main: str,
    missing: list[str],
    invalid: list[str],
    checked: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "exchange_id": manifest["exchange_id"],
        "request_id": manifest["request_id"],
        "status": "COMPLETE" if not missing and not invalid else "INCOMPLETE",
        "main_json": expected_main,
        "missing_files": sorted(set(missing)),
        "invalid_files": sorted(set(invalid)),
        "checked_files": sorted(set(checked)),
    }


def _parse_main_response(
    path: Path, request_id: str, expected_main: str
) -> dict[str, Any]:
    main = _read_json_object(path, "main response")
    if main.get("request_id") != request_id:
        raise ValueError("main response request_id does not match the active call")
    if main.get("status") not in {"COMPLETE", "PARTIAL", "BLOCKED"}:
        raise ValueError("main response status is invalid")
    artifacts = main.get("artifacts_manifest")
    if not isinstance(artifacts, list):
        raise ValueError("main response artifacts_manifest must be a list")
    delivery = main.get("delivery")
    if not isinstance(delivery, list) or any(
        not isinstance(item, str) for item in delivery
    ):
        raise ValueError("main response delivery must be a filename list")
    if len({item.casefold() for item in delivery}) != len(delivery):
        raise ValueError("main response delivery contains duplicate filenames")

    seen: set[str] = set()
    created_names: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("artifact manifest entries must be objects")
        name = _safe_name(str(artifact.get("filename", "")), "artifact filename")
        folded = name.casefold()
        if folded in seen or folded == expected_main.casefold():
            raise ValueError(f"artifact filename is duplicate or reserved: {name}")
        seen.add(folded)
        status = artifact.get("status")
        if status not in {"CREATED", "MISSING", "NOT_CREATED"}:
            raise ValueError(f"artifact status is invalid: {name}")
        artifact["filename"] = name
        if status == "CREATED":
            size = artifact.get("size")
            digest = artifact.get("sha256")
            media_type = artifact.get("media_type")
            if not isinstance(size, int) or size < 0:
                raise ValueError(f"artifact size is invalid: {name}")
            if not isinstance(digest, str) or not re.fullmatch(
                r"[0-9a-fA-F]{64}", digest
            ):
                raise ValueError(f"artifact hash is invalid: {name}")
            if not isinstance(media_type, str) or not media_type:
                raise ValueError(f"artifact media_type is invalid: {name}")
            artifact["sha256"] = digest.casefold()
            created_names.append(name)

    delivered = {item.casefold() for item in delivery}
    required_delivery = {expected_main.casefold(), *(name.casefold() for name in created_names)}
    if not required_delivery.issubset(delivered):
        raise ValueError("main response delivery does not account for all created files")
    return main


def _matching_artifact(
    main: dict[str, Any], actual_name: str
) -> dict[str, Any] | None:
    for artifact in main["artifacts_manifest"]:
        if artifact["status"] == "CREATED" and _matches_expected_name(
            actual_name, artifact["filename"]
        ):
            return artifact
    return None


def _supersede_round(active: dict[str, Any]) -> int | None:
    value = active.get("repair_round")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _pending_path(root: Path) -> Path:
    return root / "state" / "PENDING_DOWNLOADS.json"


def _load_pending(root: Path) -> list[dict[str, Any]]:
    path = _pending_path(root)
    if not path.is_file():
        return []
    value = _read_json_object(path, "PENDING_DOWNLOADS")
    items = value.get("downloads")
    return items if isinstance(items, list) else []


def _hold_pending(root: Path, download_id: int, source: Path) -> None:
    """Park a download that arrived before any call's main JSON could claim it.

    The pool is shared across active calls. An artifact downloaded before its
    main JSON cannot be attributed yet, so it waits until some call's main JSON
    names it.
    """
    pending = _load_pending(root)
    if any(item.get("id") == download_id for item in pending):
        return
    pending.append({"id": download_id, "filename": str(source)})
    _write_json_atomic(_pending_path(root), {"downloads": pending})


def _release_pending(
    root: Path,
    active: dict[str, Any],
    exchange: Path,
    main: dict[str, Any],
    supersede_round: int | None = None,
) -> list[str]:
    remaining: list[dict[str, Any]] = []
    moved: list[str] = []
    for pending in _load_pending(root):
        path = Path(pending["filename"])
        if not path.is_file():
            continue
        artifact = _matching_artifact(main, path.name)
        if artifact is None:
            remaining.append(pending)
            continue
        result = _move_artifact(path, exchange, artifact, supersede_round)
        if result["status"] == "MOVED":
            name = artifact["filename"]
            _record_collected(active, name)
            moved.append(name)
        else:
            remaining.append(pending)
    _write_json_atomic(_pending_path(root), {"downloads": remaining})
    return moved


def _move_artifact(
    source: Path,
    exchange: Path,
    artifact: dict[str, Any],
    supersede_round: int | None = None,
) -> dict[str, Any]:
    digest, size = _sha256(source)
    if digest != artifact["sha256"] or size != artifact["size"]:
        return {
            "status": "INVALID",
            "error": f"artifact hash or size does not match: {artifact['filename']}",
        }
    try:
        _safe_move(
            source, exchange / "response" / artifact["filename"], supersede_round
        )
    except FileExistsError as error:
        return {"status": "CONFLICT", "error": str(error)}
    return {"status": "MOVED", "stored_name": artifact["filename"]}


def _safe_move(
    source: Path, destination: Path, supersede_round: int | None = None
) -> None:
    source = source.resolve(strict=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_digest, source_size = _sha256(source)
    if destination.exists():
        destination_digest, destination_size = _sha256(destination)
        if source_digest == destination_digest and source_size == destination_size:
            source.unlink()
            return
        if supersede_round is None:
            raise FileExistsError(
                f"response already contains different bytes: {destination.name}"
            )
        _archive_superseded(destination, supersede_round)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".incoming-", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with source.open("rb") as incoming, temporary.open("wb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        copied_digest, copied_size = _sha256(temporary)
        if copied_digest != source_digest or copied_size != source_size:
            raise OSError(f"copied download changed: {source.name}")
        os.replace(temporary, destination)
        source.unlink()
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _archive_superseded(destination: Path, supersede_round: int) -> None:
    """Move a rejected earlier delivery aside so a correction round can replace it."""
    archive = destination.parent / "superseded" / f"round{supersede_round}"
    archive.mkdir(parents=True, exist_ok=True)
    target = archive / destination.name
    attempt = 1
    while target.exists():
        attempt += 1
        stem = Path(destination.name).stem
        suffix = Path(destination.name).suffix
        target = archive / f"{stem} ({attempt}){suffix}"
    os.replace(destination, target)


def _matches_expected_name(actual: str, expected: str) -> bool:
    if actual.casefold() == expected.casefold():
        return True
    actual_path = Path(actual)
    expected_path = Path(expected)
    if actual_path.suffix.casefold() != expected_path.suffix.casefold():
        return False
    pattern = re.compile(
        rf"^{re.escape(expected_path.stem)} \([0-9]+\)$", re.IGNORECASE
    )
    return pattern.fullmatch(actual_path.stem) is not None


def _record_collected(active: dict[str, Any], name: str) -> None:
    collected = active.setdefault("collected_files", [])
    if name not in collected:
        collected.append(name)


def _save_active(root: Path, active: dict[str, Any]) -> None:
    _write_json_atomic(_active_path_for(root, active["exchange_id"]), active)
