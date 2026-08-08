import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from companion.cli import run
from companion.core import start_call


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.root = base / "GptWebCall"
        sources = base / "sources"
        sources.mkdir()
        request = sources / "WEB_REVIEW_REQUEST.json"
        request.write_text('{"request_id":"request_cli"}\n', encoding="utf-8")
        schema = sources / "WEB_RESPONSE_SCHEMA.json"
        schema.write_text('{"type":"object"}\n', encoding="utf-8")
        self.spec_path = base / "spec.json"
        self.spec_path.write_text(
            json.dumps(
                {
                    "subject": "CLI fixture",
                    "request_id": "request_cli",
                    "expected_main_json": "cli_result.json",
                    "prompt_text": "Return files only.",
                    "created_at": "2026-07-14T15:45:00-04:00",
                    "input_files": [
                        {"path": str(request), "filename": request.name},
                        {"path": str(schema), "filename": schema.name},
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, *arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = run(
            ["--root", str(self.root), *arguments],
            stdout=stdout,
            stderr=stderr,
        )
        return code, stdout.getvalue(), stderr.getvalue()

    def test_prepare_list_and_show_emit_json(self):
        code, output, error = self.invoke("prepare", "--spec", str(self.spec_path))
        self.assertEqual((code, error), (0, ""))
        prepared = json.loads(output)
        exchange_id = prepared["result"]["exchange_id"]

        code, output, error = self.invoke("list")
        self.assertEqual((code, error), (0, ""))
        listed = json.loads(output)
        self.assertEqual(listed["result"][0]["exchange_id"], exchange_id)

        code, output, error = self.invoke("show", "--exchange", exchange_id)
        self.assertEqual((code, error), (0, ""))
        shown = json.loads(output)
        self.assertEqual(shown["result"]["request_id"], "request_cli")

    def test_show_rejects_path_traversal(self):
        code, output, error = self.invoke("show", "--exchange", "../escape")

        self.assertNotEqual(code, 0)
        self.assertEqual(output, "")
        failure = json.loads(error)
        self.assertFalse(failure["ok"])
        self.assertIn("unsafe", failure["error"])

    def test_validate_finishes_a_manually_collected_prepared_exchange(self):
        code, output, error = self.invoke("prepare", "--spec", str(self.spec_path))
        self.assertEqual((code, error), (0, ""))
        exchange_id = json.loads(output)["result"]["exchange_id"]
        response = self.root / "calls" / exchange_id / "response" / "cli_result.json"
        response.write_text(
            json.dumps(
                {
                    "request_id": "request_cli",
                    "status": "COMPLETE",
                    "artifacts_manifest": [],
                    "delivery": ["cli_result.json"],
                }
            )
            + "\n",
            encoding="utf-8",
        )

        code, output, error = self.invoke("validate", "--exchange", exchange_id)

        self.assertEqual((code, error), (0, ""))
        report = json.loads(output)["result"]
        self.assertEqual(report["status"], "COMPLETE")
        stored = json.loads(
            (self.root / "calls" / exchange_id / "EXCHANGE_MANIFEST.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(stored["state"], "COMPLETE")

    def test_active_done_and_stop_are_available_without_the_extension(self):
        code, output, error = self.invoke("prepare", "--spec", str(self.spec_path))
        self.assertEqual((code, error), (0, ""))
        exchange_id = json.loads(output)["result"]["exchange_id"]
        start_call(self.root, exchange_id, 0, [])

        code, output, error = self.invoke("active")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output)["result"]["exchange_id"], exchange_id)

        code, output, error = self.invoke("done")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output)["result"]["status"], "INCOMPLETE")

        second_spec = json.loads(self.spec_path.read_text(encoding="utf-8"))
        second_spec["subject"] = "Second CLI fixture"
        second_spec["created_at"] = "2026-07-14T15:45:01-04:00"
        self.spec_path.write_text(json.dumps(second_spec) + "\n", encoding="utf-8")
        code, output, error = self.invoke("prepare", "--spec", str(self.spec_path))
        self.assertEqual((code, error), (0, ""))
        second_id = json.loads(output)["result"]["exchange_id"]
        start_call(self.root, second_id, 0, [])

        code, output, error = self.invoke("stop")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output)["result"]["state"], "STOPPED")

    def test_delete_removes_a_prepared_call_and_frees_its_filenames(self):
        code, output, error = self.invoke("prepare", "--spec", str(self.spec_path))
        self.assertEqual((code, error), (0, ""))
        exchange_id = json.loads(output)["result"]["exchange_id"]

        # The name is spoken for, so an identical second call cannot be prepared.
        second_spec = json.loads(self.spec_path.read_text(encoding="utf-8"))
        second_spec["subject"] = "Second CLI fixture"
        second_spec["created_at"] = "2026-07-14T15:45:01-04:00"
        self.spec_path.write_text(json.dumps(second_spec) + "\n", encoding="utf-8")
        code, _, error = self.invoke("prepare", "--spec", str(self.spec_path))
        self.assertNotEqual(code, 0)
        self.assertIn("already claimed", json.loads(error)["error"])

        code, output, error = self.invoke("delete", "--exchange", exchange_id)

        self.assertEqual((code, error), (0, ""))
        deleted = json.loads(output)["result"]
        self.assertTrue(deleted["deleted"])
        self.assertEqual(deleted["state_before_delete"], "PREPARED")
        self.assertEqual(deleted["freed_deliverable_names"], ["cli_result.json"])
        self.assertFalse((self.root / "calls" / exchange_id).exists())

        # Freeing the name is the point: the same deliverable can now be claimed.
        code, _, error = self.invoke("prepare", "--spec", str(self.spec_path))
        self.assertEqual((code, error), (0, ""))

    def test_delete_refuses_a_running_call(self):
        code, output, error = self.invoke("prepare", "--spec", str(self.spec_path))
        self.assertEqual((code, error), (0, ""))
        exchange_id = json.loads(output)["result"]["exchange_id"]
        start_call(self.root, exchange_id, 0, [])

        code, output, error = self.invoke("delete", "--exchange", exchange_id)

        self.assertNotEqual(code, 0)
        self.assertIn("is running", json.loads(error)["error"])
        self.assertTrue((self.root / "calls" / exchange_id).is_dir())

    def test_delete_refuses_to_discard_a_received_response_unless_forced(self):
        code, output, error = self.invoke("prepare", "--spec", str(self.spec_path))
        self.assertEqual((code, error), (0, ""))
        exchange_id = json.loads(output)["result"]["exchange_id"]
        response = self.root / "calls" / exchange_id / "response" / "cli_result.json"
        response.write_text('{"request_id":"request_cli"}\n', encoding="utf-8")

        code, output, error = self.invoke("delete", "--exchange", exchange_id)
        self.assertNotEqual(code, 0)
        self.assertIn("cli_result.json", json.loads(error)["error"])
        self.assertTrue(response.is_file())

        code, output, error = self.invoke("delete", "--exchange", exchange_id, "--force")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(
            json.loads(output)["result"]["discarded_responses"], ["cli_result.json"]
        )
        self.assertFalse((self.root / "calls" / exchange_id).exists())

    def test_delete_rejects_path_traversal(self):
        code, output, error = self.invoke("delete", "--exchange", "../escape")

        self.assertNotEqual(code, 0)
        self.assertEqual(output, "")
        self.assertIn("unsafe", json.loads(error)["error"])

    @unittest.skipUnless(os.name == "nt", "Windows command wrapper test")
    def test_windows_wrapper_forwards_subcommand_after_root_path(self):
        repository_root = Path(__file__).resolve().parents[2]

        completed = subprocess.run(
            [str(repository_root / "gptwebcall.cmd"), "list"],
            cwd=repository_root,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        response = json.loads(completed.stdout)
        self.assertEqual(response["command"], "list")


if __name__ == "__main__":
    unittest.main()
