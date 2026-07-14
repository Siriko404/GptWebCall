from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from companion.core import (
    _active_path,
    _exchange_dir,
    _read_json_object,
    _safe_name,
    _sha256,
    _write_json_atomic,
    load_active_call,
)


def handle_completed_download(root: Path, download: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).resolve()
    active = load_active_call(root)
    if active is None:
        raise RuntimeError("no call is active")
    if not active.get("monitoring"):
        return {"status": "IGNORED", "reason": "monitoring is stopped"}

    download_id = download.get("id")
    if not isinstance(download_id, int) or download_id < 0:
        raise ValueError("download id must be a non-negative integer")
    if download.get("state", "complete") != "complete":
        raise ValueError("download is not complete")
    if download_id in active.get("download_baseline", []):
        return {"status": "IGNORED", "reason": "download predates Go"}
    if download_id in active.get("observed_download_ids", []):
        return {"status": "DUPLICATE", "download_id": download_id}

    filename = download.get("filename")
    if not isinstance(filename, str) or not filename:
        raise ValueError("completed download filename is required")
    source = Path(filename).resolve(strict=True)
    if not source.is_file():
        raise ValueError(f"completed download is not a regular file: {source.name}")

    exchange = Path(active["exchange_path"]).resolve()
    manifest = _read_json_object(
        exchange / "EXCHANGE_MANIFEST.json", "EXCHANGE_MANIFEST"
    )
    expected_main = _safe_name(
        str(manifest["expected_main_json"]), "expected main JSON filename"
    )
    active.setdefault("observed_download_ids", []).append(download_id)

    if _matches_expected_name(source.name, expected_main):
        try:
            main = _parse_main_response(source, manifest["request_id"], expected_main)
            _safe_move(source, exchange / "response" / expected_main)
        except FileExistsError as error:
            _save_active(root, active)
            return {"status": "CONFLICT", "error": str(error)}
        except (OSError, ValueError) as error:
            _save_active(root, active)
            return {"status": "INVALID", "error": str(error)}
        _record_collected(active, expected_main)
        released = _release_pending(root, active, exchange, main)
        _save_active(root, active)
        return {
            "status": "MOVED",
            "download_id": download_id,
            "stored_name": expected_main,
            "released_pending": released,
        }

    main_path = exchange / "response" / expected_main
    if not main_path.is_file():
        active.setdefault("pending_downloads", []).append(
            {"id": download_id, "filename": str(source)}
        )
        _save_active(root, active)
        return {"status": "PENDING", "download_id": download_id}

    main = _parse_main_response(main_path, manifest["request_id"], expected_main)
    artifact = _matching_artifact(main, source.name)
    if artifact is None:
        _save_active(root, active)
        return {"status": "IGNORED", "reason": "not listed by the main JSON"}
    result = _move_artifact(source, exchange, artifact)
    if result["status"] == "MOVED":
        _record_collected(active, artifact["filename"])
    _save_active(root, active)
    return result | {"download_id": download_id}


def finish_call(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    active = load_active_call(root)
    if active is None:
        raise RuntimeError("no call is active")

    active["monitoring"] = False
    _save_active(root, active)
    exchange = Path(active["exchange_path"]).resolve()
    manifest_path = exchange / "EXCHANGE_MANIFEST.json"
    manifest = _read_json_object(manifest_path, "EXCHANGE_MANIFEST")
    main_path = exchange / "response" / manifest["expected_main_json"]
    if main_path.is_file():
        try:
            main = _parse_main_response(
                main_path, manifest["request_id"], manifest["expected_main_json"]
            )
            _release_pending(root, active, exchange, main)
            _save_active(root, active)
        except ValueError:
            pass

    report = validate_response(exchange)
    _write_json_atomic(exchange / "validation" / "VALIDATION_REPORT.json", report)
    manifest["state"] = report["status"]
    _write_json_atomic(manifest_path, manifest)
    _write_json_atomic(
        root / "state" / "LAST_RESULT.json",
        {"exchange_id": manifest["exchange_id"], "report": report},
    )
    _active_path(root).unlink()
    return report


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
    return _validation_report(manifest, expected_main, missing, invalid, checked)


def finalize_exchange(root: Path, exchange_id: str) -> dict[str, Any]:
    root = Path(root).resolve()
    active = load_active_call(root)
    if active is not None:
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


def _release_pending(
    root: Path,
    active: dict[str, Any],
    exchange: Path,
    main: dict[str, Any],
) -> list[str]:
    remaining: list[dict[str, Any]] = []
    moved: list[str] = []
    for pending in active.get("pending_downloads", []):
        path = Path(pending["filename"])
        if not path.is_file():
            continue
        artifact = _matching_artifact(main, path.name)
        if artifact is None:
            remaining.append(pending)
            continue
        result = _move_artifact(path, exchange, artifact)
        if result["status"] == "MOVED":
            name = artifact["filename"]
            _record_collected(active, name)
            moved.append(name)
        else:
            remaining.append(pending)
    active["pending_downloads"] = remaining
    return moved


def _move_artifact(
    source: Path, exchange: Path, artifact: dict[str, Any]
) -> dict[str, Any]:
    digest, size = _sha256(source)
    if digest != artifact["sha256"] or size != artifact["size"]:
        return {
            "status": "INVALID",
            "error": f"artifact hash or size does not match: {artifact['filename']}",
        }
    try:
        _safe_move(source, exchange / "response" / artifact["filename"])
    except FileExistsError as error:
        return {"status": "CONFLICT", "error": str(error)}
    return {"status": "MOVED", "stored_name": artifact["filename"]}


def _safe_move(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_digest, source_size = _sha256(source)
    if destination.exists():
        destination_digest, destination_size = _sha256(destination)
        if source_digest == destination_digest and source_size == destination_size:
            source.unlink()
            return
        raise FileExistsError(
            f"response already contains different bytes: {destination.name}"
        )

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
    _write_json_atomic(_active_path(root), active)
