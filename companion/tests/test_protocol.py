import json
import unittest
from pathlib import Path


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]

    def test_the_protocol_sends_an_agent_session_to_the_skills(self):
        """The skills are the operating surface; this file is the reference.

        A session that reads the protocol and drives `gptwebcall.cmd` itself has
        to hold five hundred lines to act safely, and the parts it does not hold
        are the ones that lose files. The protocol therefore has to say, in its
        own opening, that it is not the way in.
        """
        protocol = (self.root / "WEB_CALL_PROTOCOL.md").read_text(encoding="utf-8")

        self.assertIn("It is not the operating surface", protocol)
        for command in ("/webcall:init", "/webcall:prep", "/webcall:menu"):
            self.assertIn(command, protocol)
        # The human's path out stays, and stays named as the exception.
        self.assertIn("manual fallback below stays usable by hand", protocol)

        readme = (self.root / "README.md").read_text(encoding="utf-8")
        for command in ("/webcall:init", "/webcall:prep", "/webcall:menu"):
            self.assertIn(command, readme)
        # Teaching the CLI in the README puts a second front door beside the
        # skills, which is exactly what this replaced.
        self.assertNotIn(".\\gptwebcall.cmd prepare", readme)

    def test_the_skill_covers_every_command_the_cli_exposes(self):
        """A gap here is what pushes a session back to the raw CLI."""
        menu = (
            self.root / "skill" / "webcall" / "skills" / "menu" / "SKILL.md"
        ).read_text(encoding="utf-8")
        prep = (
            self.root / "skill" / "webcall" / "skills" / "prep" / "SKILL.md"
        ).read_text(encoding="utf-8")
        covered = menu + prep
        for command in (
            "prepare",
            "list",
            "show",
            "active",
            "done",
            "stop",
            "delete",
            "validate",
            "defects",
            "repair",
        ):
            self.assertIn(command, covered, command)

    def test_the_destination_control_is_documented_where_it_is_decided(self):
        """A control that changes what the call *is* cannot live only in the UI.

        Choosing the current conversation hands the request to a model that has
        already been argued with. That is the point of a conductor call and
        ruins a bounded one, so the reference has to name both settings and the
        refusals, and `prep` - where the mode is chosen - has to send the
        operator to the control before Go.
        """
        protocol = (self.root / "WEB_CALL_PROTOCOL.md").read_text(encoding="utf-8")

        self.assertIn("Send in a new conversation", protocol)
        self.assertIn("Send in the conversation I am in", protocol)
        # Resume once created a fresh tab unconditionally, which silently threw
        # away the thread a conductor call was bound to. It reads the control
        # now - but the control, not the call, is what carries the mode, and
        # saying otherwise would promise a memory the code does not have.
        self.assertIn("**Resume** reads the control too", protocol)
        self.assertIn("not the mode any particular call was sent with", protocol)

        prep = (
            self.root / "skill" / "webcall" / "skills" / "prep" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Send in the conversation I am in", prep)

    def test_protocol_is_the_complete_global_reference(self):
        protocol = (self.root / "WEB_CALL_PROTOCOL.md").read_text(encoding="utf-8")

        for required in (
            "System root: the directory containing this file",
            "reasoning-heavy",
            "000_READ_ME_FIRST.md",
            "## One zip up, at most two files down",
            "_inputs.zip",
            "either empty, when the call returns nothing but the main JSON, or a single `.zip`",
            "Several calls may be active at once",
            "## Parallel calls",
            "## Filenames are the routing key",
            "expected_artifacts",
            "AMBIGUOUS",
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
            "The operator clicks",
            "advisory",
            "new correction call",
        ):
            self.assertIn(contract_term, protocol)

    def test_shipped_documents_name_no_machine_but_the_reader_s_own(self):
        """The protocol is read by a session on a stranger's machine.

        An absolute path from the author's disk, or the author's name, reads to
        that session as the canonical location of a system that is in fact
        wherever the reader put it. This is a regression guard, not a style rule.
        """
        for name in ("README.md", "WEB_CALL_PROTOCOL.md", "docs/MANUAL_FALLBACK.md"):
            document = (self.root / name).read_text(encoding="utf-8")
            self.assertNotRegex(document, r"[A-Za-z]:\\Users\\[^\\\s]+", name)
            self.assertNotIn("Sina", document, name)

    def test_manual_fallback_uploads_the_two_attach_files(self):
        """Uploading every request file was the pre-bundle contract.

        Preparation now packs everything except the prompt into one archive and
        records the pair in attach_files. An instruction to upload all of
        request_files would have the operator attach the loose provenance copies
        alongside the archive that already contains them.
        """
        for name in ("WEB_CALL_PROTOCOL.md", "docs/MANUAL_FALLBACK.md"):
            document = (self.root / name).read_text(encoding="utf-8")
            self.assertIn("attach_files", document, name)
            self.assertNotIn("files listed in `request_files`", document, name)

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
