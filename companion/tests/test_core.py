import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from companion.core import (
    list_ready_calls,
    load_active_call,
    prepare_call,
    start_call,
    stop_call,
)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "GptWebCall"
        self.sources = Path(self.temp.name) / "sources"
        self.sources.mkdir()
        self.now = datetime(
            2026, 7, 14, 15, 15, 0, tzinfo=timezone(timedelta(hours=-4))
        )
        self.request = self.write(
            "WEB_REVIEW_REQUEST.json", {"request_id": "request_fixture"}
        )
        self.schema = self.write(
            "WEB_RESPONSE_SCHEMA.json", {"type": "object"}
        )
        self.context = self.write("context.txt", "context\n")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        path = self.sources / name
        if isinstance(value, dict):
            path.write_text(json.dumps(value) + "\n", encoding="utf-8")
        else:
            path.write_text(value, encoding="utf-8")
        return path

    def spec(self, subject="Fixture call"):
        return {
            "subject": subject,
            "request_id": "request_fixture",
            "expected_main_json": "result.json",
            "prompt_text": "Follow this request and return files only.\n",
            "input_files": [
                {"path": str(self.request), "filename": self.request.name},
                {"path": str(self.schema), "filename": self.schema.name},
                {"path": str(self.context), "filename": self.context.name},
            ],
        }

    def test_prepare_call_uses_one_timestamp_for_folder_and_prompt(self):
        manifest = prepare_call(self.root, self.spec(), self.now)

        self.assertEqual(
            manifest["exchange_id"], "2026-07-14_151500_fixture_call"
        )
        self.assertEqual(manifest["state"], "PREPARED")
        self.assertEqual(manifest["request_id"], "request_fixture")
        names = [item["filename"] for item in manifest["request_files"]]
        self.assertEqual(
            names,
            [
                "PROMPT_2026-07-14_151500.txt",
                "WEB_REVIEW_REQUEST.json",
                "WEB_RESPONSE_SCHEMA.json",
                "context.txt",
            ],
        )
        exchange = self.root / "calls" / manifest["exchange_id"]
        for item in manifest["request_files"]:
            stored = exchange / "request" / item["filename"]
            self.assertTrue(stored.is_file())
            self.assertEqual(item["size"], stored.stat().st_size)
            self.assertEqual(
                item["sha256"], hashlib.sha256(stored.read_bytes()).hexdigest()
            )
        self.assertTrue((exchange / "response").is_dir())
        self.assertTrue((exchange / "validation").is_dir())

    def test_prepare_validates_request_identity(self):
        self.request.write_text('{"request_id":"wrong"}\n', encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "request_id"):
            prepare_call(self.root, self.spec(), self.now)

    def test_prepare_rejects_invalid_governing_json(self):
        self.request.write_text("{not-json}\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "WEB_REVIEW_REQUEST"):
            prepare_call(self.root, self.spec(), self.now)

    def test_prepare_rejects_invalid_response_schema_json(self):
        self.schema.write_text("{not-json}\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "WEB_RESPONSE_SCHEMA"):
            prepare_call(self.root, self.spec(), self.now)

    def test_prepare_rejects_missing_input(self):
        self.context.unlink()

        with self.assertRaisesRegex(FileNotFoundError, "context.txt"):
            prepare_call(self.root, self.spec(), self.now)

    def test_prepare_rejects_duplicate_packaged_names(self):
        spec = self.spec()
        spec["input_files"].append(
            {"path": str(self.context), "filename": "CONTEXT.txt"}
        )

        with self.assertRaisesRegex(ValueError, "duplicate"):
            prepare_call(self.root, spec, self.now)

    def test_prepare_rejects_caller_supplied_prompt(self):
        spec = self.spec()
        spec["input_files"].append(
            {
                "path": str(self.context),
                "filename": "PROMPT_2026-07-14_151500.txt",
            }
        )

        with self.assertRaisesRegex(ValueError, "PROMPT"):
            prepare_call(self.root, spec, self.now)

    def test_prepare_rejects_unsafe_subject_and_filename(self):
        with self.assertRaisesRegex(ValueError, "subject"):
            prepare_call(self.root, self.spec("../escape"), self.now)

        spec = self.spec()
        spec["input_files"][0]["filename"] = "../request.json"
        with self.assertRaisesRegex(ValueError, "filename"):
            prepare_call(self.root, spec, self.now)

    def test_list_ready_calls_and_single_active_call(self):
        first = prepare_call(self.root, self.spec("First"), self.now)
        second = prepare_call(
            self.root, self.spec("Second"), self.now + timedelta(seconds=1)
        )

        ready = list_ready_calls(self.root)
        self.assertEqual(
            [item["exchange_id"] for item in ready],
            [first["exchange_id"], second["exchange_id"]],
        )

        active = start_call(self.root, first["exchange_id"], 11, [2, 4])
        self.assertTrue(active["monitoring"])
        self.assertEqual(active["tab_id"], 11)
        self.assertEqual(active["download_baseline"], [2, 4])
        self.assertEqual(load_active_call(self.root), active)
        with self.assertRaisesRegex(RuntimeError, "already active"):
            start_call(self.root, second["exchange_id"], 12, [])

        remaining = list_ready_calls(self.root)
        self.assertEqual(
            [item["exchange_id"] for item in remaining], [second["exchange_id"]]
        )

    def test_stop_call_records_stop_before_clearing_active_state(self):
        call = prepare_call(self.root, self.spec(), self.now)
        start_call(self.root, call["exchange_id"], 11, [])

        stopped = stop_call(self.root)

        self.assertEqual(stopped["state"], "STOPPED")
        self.assertIsNone(load_active_call(self.root))
        manifest = json.loads(
            (self.root / "calls" / call["exchange_id"] / "EXCHANGE_MANIFEST.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["state"], "STOPPED")


if __name__ == "__main__":
    unittest.main()
