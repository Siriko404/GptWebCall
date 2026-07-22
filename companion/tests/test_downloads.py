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
        self.assertEqual(report["response_status"], "COMPLETE")
        self.assertTrue(report["work_complete"])
        self.assertEqual(validate_response(self.exchange), report)

    def test_partial_response_delivered_intact_is_not_invalid(self):
        """A responder that declares its own gaps must not be told it is corrupt.

        This is the regression. Any status other than COMPLETE used to put the
        main JSON into invalid_files, the same bucket as a failed hash, so the
        exchange went INCOMPLETE and every reader was told to repair a response
        whose files were flawless. Prompts in this project explicitly ask for
        PARTIAL when something cannot be settled, so the system punished the one
        behaviour it had asked for, and it did so on every such call.

        Nothing covered this case, which is why it shipped. The delivery facts
        and the work facts are asserted separately here so they cannot be
        conflated again without a test going red.
        """
        main = self.download("result.json", self.main_json_bytes(status="PARTIAL"))
        artifact = self.download("report.md", self.report_bytes)
        handle_completed_download(self.root, self.completed(3, main))
        handle_completed_download(self.root, self.completed(4, artifact))

        report = finish_call(self.root)

        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["invalid_files"], [])
        self.assertEqual(report["missing_files"], [])
        self.assertEqual(report["response_status"], "PARTIAL")
        self.assertFalse(report["work_complete"])
        manifest = json.loads(
            (self.exchange / "EXCHANGE_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["state"], "COMPLETE")

    def test_blocked_response_delivered_intact_is_not_invalid(self):
        main = self.download("result.json", self.main_json_bytes(status="BLOCKED"))
        artifact = self.download("report.md", self.report_bytes)
        handle_completed_download(self.root, self.completed(3, main))
        handle_completed_download(self.root, self.completed(4, artifact))

        report = finish_call(self.root)

        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["invalid_files"], [])
        self.assertEqual(report["response_status"], "BLOCKED")
        self.assertFalse(report["work_complete"])

    def test_a_corrupt_artifact_is_still_invalid_whatever_the_status_says(self):
        """The fix must not soften the check it was carved out of.

        A hash mismatch is a real defect and has to keep reporting as one no
        matter how the responder describes its own work. Written against
        validate_response directly, because the download handler refuses a
        mismatching file on arrival and it would never reach the validator by
        the normal route.
        """
        response = self.exchange / "response"
        response.mkdir(parents=True, exist_ok=True)
        (response / "result.json").write_bytes(
            self.main_json_bytes(status="PARTIAL", artifact_digest="0" * 64)
        )
        (response / "report.md").write_bytes(self.report_bytes)

        report = validate_response(self.exchange)

        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertEqual(report["invalid_files"], ["report.md"])
        self.assertEqual(report["response_status"], "PARTIAL")

    def test_an_expected_artifact_declared_absent_is_not_reported_missing(self):
        """Declaring an artifact was not created is a report, not a silent drop.

        The expected-artifact backstop exists so a deliverable the main JSON
        forgot cannot vanish quietly. A response that names the file and marks
        it NOT_CREATED has not forgotten it, so calling it missing would punish
        the same honesty the status fix stopped punishing.
        """
        exchange, main_path = self._exchange_expecting_an_artifact()
        payload = {
            "request_id": "request_declared",
            "status": "BLOCKED",
            "artifacts_manifest": [
                {"filename": "declared_outputs.zip", "status": "NOT_CREATED"}
            ],
            "delivery": ["declared_result.json"],
        }
        main_path.write_text(json.dumps(payload), encoding="utf-8")

        report = validate_response(exchange)

        self.assertEqual(report["missing_files"], [])
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["response_status"], "BLOCKED")

    def test_an_expected_artifact_silently_dropped_is_still_missing(self):
        """The other half of that carve-out, so it cannot be widened by accident."""
        exchange, main_path = self._exchange_expecting_an_artifact()
        payload = {
            "request_id": "request_declared",
            "status": "COMPLETE",
            "artifacts_manifest": [],
            "delivery": ["declared_result.json"],
        }
        main_path.write_text(json.dumps(payload), encoding="utf-8")

        report = validate_response(exchange)

        self.assertEqual(report["missing_files"], ["declared_outputs.zip"])
        self.assertEqual(report["status"], "INCOMPLETE")

    def _exchange_expecting_an_artifact(self):
        """A prepared exchange that declares expected_artifacts.

        The shared fixture declares none, so the backstop it guards never runs
        there. A test of that backstop needs an exchange that actually expects
        something.
        """
        request = self.write_source(
            "declared_request.json", {"request_id": "request_declared"}
        )
        schema = self.write_source("declared_schema.json", {"type": "object"})
        spec = {
            "subject": "Declared artifact call",
            "request_id": "request_declared",
            "expected_main_json": "declared_result.json",
            "expected_artifacts": ["declared_outputs.zip"],
            "prompt_text": "Return files only.\n",
            "input_files": [
                {"path": str(request), "filename": "WEB_REVIEW_REQUEST.json"},
                {"path": str(schema), "filename": "WEB_RESPONSE_SCHEMA.json"},
            ],
        }
        manifest = prepare_call(
            self.root,
            spec,
            datetime(2026, 7, 14, 16, 0, 0, tzinfo=timezone(timedelta(hours=-4))),
        )
        exchange = self.root / "calls" / manifest["exchange_id"]
        (exchange / "response").mkdir(parents=True, exist_ok=True)
        # validate_response reads the expected main name from the manifest, so
        # the caller writes under whatever name was declared rather than
        # guessing one.
        return exchange, exchange / "response" / manifest["expected_main_json"]


if __name__ == "__main__":
    unittest.main()
