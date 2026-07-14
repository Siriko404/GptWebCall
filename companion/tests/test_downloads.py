import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from companion.core import load_active_call, prepare_call, start_call
from companion.downloads import (
    finish_call,
    handle_completed_download,
    validate_response,
)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.root = base / "GptWebCall"
        self.sources = base / "sources"
        self.downloads = base / "Downloads"
        self.sources.mkdir()
        self.downloads.mkdir()
        request = self.write_source(
            "WEB_REVIEW_REQUEST.json", {"request_id": "request_fixture"}
        )
        schema = self.write_source(
            "WEB_RESPONSE_SCHEMA.json", {"type": "object"}
        )
        context = self.write_source("context.txt", "context\n")
        spec = {
            "subject": "Fixture call",
            "request_id": "request_fixture",
            "expected_main_json": "result.json",
            "prompt_text": "Return files only.\n",
            "input_files": [
                {"path": str(request), "filename": request.name},
                {"path": str(schema), "filename": schema.name},
                {"path": str(context), "filename": context.name},
            ],
        }
        now = datetime(
            2026, 7, 14, 15, 15, 0, tzinfo=timezone(timedelta(hours=-4))
        )
        self.manifest = prepare_call(self.root, spec, now)
        start_call(self.root, self.manifest["exchange_id"], 11, [99])
        self.exchange = self.root / "calls" / self.manifest["exchange_id"]
        self.report_bytes = b"report"
        self.report_digest = hashlib.sha256(self.report_bytes).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def write_source(self, name, value):
        path = self.sources / name
        if isinstance(value, dict):
            path.write_text(json.dumps(value) + "\n", encoding="utf-8")
        else:
            path.write_text(value, encoding="utf-8")
        return path

    def download(self, name, contents):
        path = self.downloads / name
        path.write_bytes(contents)
        return path

    def main_json_bytes(
        self,
        *,
        request_id="request_fixture",
        status="COMPLETE",
        artifacts=True,
        artifact_digest=None,
    ):
        manifest = []
        delivery = ["result.json"]
        if artifacts:
            manifest.append(
                {
                    "filename": "report.md",
                    "status": "CREATED",
                    "media_type": "text/markdown",
                    "size": len(self.report_bytes),
                    "sha256": artifact_digest or self.report_digest,
                }
            )
            delivery.append("report.md")
        return (
            json.dumps(
                {
                    "request_id": request_id,
                    "status": status,
                    "artifacts_manifest": manifest,
                    "delivery": delivery,
                }
            )
            + "\n"
        ).encode("utf-8")

    def completed(self, download_id, path):
        return {"id": download_id, "filename": str(path), "state": "complete"}

    def test_baseline_download_is_ignored(self):
        source = self.download("old.json", b"old")

        result = handle_completed_download(self.root, self.completed(99, source))

        self.assertEqual(result["status"], "IGNORED")
        self.assertTrue(source.exists())

    def test_artifact_waits_until_main_json_names_it(self):
        artifact = self.download("report.md", self.report_bytes)

        pending = handle_completed_download(self.root, self.completed(2, artifact))

        self.assertEqual(pending["status"], "PENDING")
        self.assertTrue(artifact.exists())
        main = self.download("result.json", self.main_json_bytes())
        moved = handle_completed_download(self.root, self.completed(3, main))
        self.assertEqual(moved["status"], "MOVED")
        self.assertFalse(main.exists())
        self.assertFalse(artifact.exists())
        self.assertEqual(
            (self.exchange / "response" / "report.md").read_bytes(),
            self.report_bytes,
        )

    def test_browser_suffix_binds_to_expected_main_json(self):
        main = self.download("result (1).json", self.main_json_bytes(artifacts=False))

        moved = handle_completed_download(self.root, self.completed(3, main))

        self.assertEqual(moved["stored_name"], "result.json")
        self.assertFalse(main.exists())
        self.assertTrue((self.exchange / "response" / "result.json").is_file())

    def test_unmatched_download_after_main_stays_in_downloads(self):
        main = self.download("result.json", self.main_json_bytes(artifacts=False))
        handle_completed_download(self.root, self.completed(3, main))
        unrelated = self.download("unrelated.pdf", b"unrelated")

        result = handle_completed_download(
            self.root, self.completed(4, unrelated)
        )

        self.assertEqual(result["status"], "IGNORED")
        self.assertTrue(unrelated.exists())

    def test_wrong_request_id_is_rejected_without_moving(self):
        main = self.download(
            "result.json", self.main_json_bytes(request_id="another_request")
        )

        result = handle_completed_download(self.root, self.completed(3, main))

        self.assertEqual(result["status"], "INVALID")
        self.assertIn("request_id", result["error"])
        self.assertTrue(main.exists())

    def test_artifact_hash_mismatch_is_not_moved(self):
        main = self.download("result.json", self.main_json_bytes())
        handle_completed_download(self.root, self.completed(3, main))
        artifact = self.download("report.md", b"wrong")

        result = handle_completed_download(
            self.root, self.completed(4, artifact)
        )

        self.assertEqual(result["status"], "INVALID")
        self.assertIn("hash", result["error"])
        self.assertTrue(artifact.exists())

    def test_existing_different_response_is_never_overwritten(self):
        main = self.download("result.json", self.main_json_bytes())
        handle_completed_download(self.root, self.completed(3, main))
        destination = self.exchange / "response" / "report.md"
        destination.write_bytes(b"different")
        artifact = self.download("report.md", self.report_bytes)

        result = handle_completed_download(
            self.root, self.completed(4, artifact)
        )

        self.assertEqual(result["status"], "CONFLICT")
        self.assertEqual(destination.read_bytes(), b"different")
        self.assertTrue(artifact.exists())

    def test_nonexistent_completed_path_is_rejected(self):
        missing = self.downloads / "missing.json"

        with self.assertRaisesRegex(FileNotFoundError, "missing.json"):
            handle_completed_download(self.root, self.completed(3, missing))

    def test_finish_call_reports_missing_artifact_and_stops_monitoring(self):
        main = self.download("result.json", self.main_json_bytes())
        handle_completed_download(self.root, self.completed(3, main))

        report = finish_call(self.root)

        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertEqual(report["missing_files"], ["report.md"])
        self.assertIsNone(load_active_call(self.root))
        stored = json.loads(
            (self.exchange / "validation" / "VALIDATION_REPORT.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(stored, report)

    def test_finish_call_validates_complete_delivery(self):
        main = self.download("result.json", self.main_json_bytes())
        artifact = self.download("report.md", self.report_bytes)
        handle_completed_download(self.root, self.completed(3, main))
        handle_completed_download(self.root, self.completed(4, artifact))

        report = finish_call(self.root)

        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["missing_files"], [])
        self.assertEqual(report["invalid_files"], [])
        self.assertEqual(validate_response(self.exchange), report)


if __name__ == "__main__":
    unittest.main()
