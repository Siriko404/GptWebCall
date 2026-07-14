import json
import unittest
from pathlib import Path


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]

    def test_protocol_is_the_complete_global_entry_point(self):
        protocol = (self.root / "WEB_CALL_PROTOCOL.md").read_text(encoding="utf-8")

        for required in (
            "C:\\GptWebCall",
            "reasoning-heavy",
            "PROMPT_YYYY-MM-DD_HHMMSS.txt",
            "one active call",
            "Go",
            "Done",
            "WEB_REVIEW_REQUEST.json",
            "WEB_RESPONSE_SCHEMA.json",
            "artifacts_manifest",
            "manual fallback",
            "never presses Send",
            "never reads ChatGPT's response page",
        ):
            self.assertIn(required, protocol)

    def test_protocol_contains_every_fresh_session_operation(self):
        protocol = (self.root / "WEB_CALL_PROTOCOL.md").read_text(encoding="utf-8")

        for heading in (
            "## Fresh-session contract",
            "## Exact request construction",
            "## Call decomposition and continuation",
            "## Command reference",
            "## Semantic acceptance",
            "## Failure and correction rules",
            "## Compaction and handoff",
        ):
            self.assertIn(heading, protocol)
        for command in (
            ".\\gptwebcall.cmd prepare --spec",
            ".\\gptwebcall.cmd list",
            ".\\gptwebcall.cmd show --exchange",
            ".\\gptwebcall.cmd active",
            ".\\gptwebcall.cmd done",
            ".\\gptwebcall.cmd stop",
            ".\\gptwebcall.cmd validate --exchange",
        ):
            self.assertIn(command, protocol)
        for contract_term in (
            '"subject"',
            '"request_id"',
            '"expected_main_json"',
            '"prompt_text"',
            '"input_files"',
            '"artifacts_manifest"',
            '"delivery"',
            "Resume attachment",
            "Sina clicks",
            "advisory",
            "new correction call",
        ):
            self.assertIn(contract_term, protocol)

    def test_native_host_template_is_origin_pinned_and_scripts_are_safe(self):
        template = json.loads(
            (self.root / "native-host" / "com.sina.gptwebcall.template.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(template["name"], "com.sina.gptwebcall")
        self.assertEqual(template["type"], "stdio")
        self.assertTrue(template["description"])
        self.assertEqual(template["path"], "__HOST_PATH__")
        self.assertEqual(template["allowed_origins"], ["chrome-extension://__EXTENSION_ID__/"])

        installer = (self.root / "scripts" / "install.ps1").read_text(encoding="utf-8")
        uninstaller = (self.root / "scripts" / "uninstall.ps1").read_text(encoding="utf-8")
        self.assertIn("^[a-p]{32}$", installer)
        self.assertIn("[switch]$WhatIf", installer)
        self.assertIn("NativeMessagingHosts\\com.sina.gptwebcall", installer)
        self.assertIn("NativeMessagingHosts\\com.sina.gptwebcall", uninstaller)
        self.assertNotIn("Remove-Item -Recurse", uninstaller)


if __name__ == "__main__":
    unittest.main()
