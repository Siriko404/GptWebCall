import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from companion.cli import run


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
