"""Everything travels as one archive, the prompt included.

One zip goes up. These tests pin the parts of that rule that could silently
regress: what lands inside the archive and in what order, that the archive is
the only thing uploaded, that its digest is stable, that the two-file shape
cannot be asked for any more, that the launch line the panel types names both
the archive and the file that governs it, and that the return side is held to a
single archive as well.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from companion.core import launch_prompt, prepare_call, request_paths


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.sources = self.root / "sources"
        self.sources.mkdir()
        self.now = datetime(2026, 7, 21, 20, 0, 0, tzinfo=timezone.utc)

        (self.sources / "WEB_REVIEW_REQUEST.json").write_text(
            json.dumps({"request_id": "bundle_fixture"}), encoding="utf-8"
        )
        (self.sources / "WEB_RESPONSE_SCHEMA.json").write_text(
            json.dumps({"type": "object"}), encoding="utf-8"
        )
        (self.sources / "context.md").write_text("context body", encoding="utf-8")
        (self.sources / "deck.pdf").write_bytes(b"%PDF-1.7\nnot really a pdf\n")

    def spec(self, subject="Bundle Fixture", artifacts=("bundle_outputs.zip",)):
        value = {
            "subject": subject,
            "request_id": "bundle_fixture",
            "expected_main_json": "bundle_response.json",
            "prompt_text": "Read the archive.",
            "input_files": [
                {
                    "path": str(self.sources / name),
                    "filename": name,
                }
                for name in (
                    "WEB_REVIEW_REQUEST.json",
                    "WEB_RESPONSE_SCHEMA.json",
                    "context.md",
                    "deck.pdf",
                )
            ],
        }
        if artifacts is not None:
            value["expected_artifacts"] = list(artifacts)
        return value

    def prepared(self, **kwargs):
        manifest = prepare_call(self.root, self.spec(**kwargs), self.now)
        return manifest, self.root / "calls" / manifest["exchange_id"]

    def test_the_archive_holds_every_input_and_the_prompt_first(self):
        """ChatGPT refuses loose .md attachments, so the prompt cannot go up
        beside the archive. Inside it, the name is the only thing telling a
        model which file governs, and the bundle is written in casefolded name
        order, so the leading 000 puts it first in the archive and in any
        listing a model prints."""
        manifest, exchange = self.prepared()
        archive = exchange / "request" / "bundle_fixture_inputs.zip"

        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            self.assertEqual(names[0], "000_READ_ME_FIRST.md")
            self.assertEqual(
                sorted(names),
                [
                    "000_READ_ME_FIRST.md",
                    "WEB_RESPONSE_SCHEMA.json",
                    "WEB_REVIEW_REQUEST.json",
                    "context.md",
                    "deck.pdf",
                ],
            )
            self.assertEqual(bundle.read("context.md"), b"context body")
            self.assertEqual(bundle.read("000_READ_ME_FIRST.md"), b"Read the archive.")
        self.assertFalse(any(name.startswith("PROMPT_") for name in names))

    def test_exactly_one_file_is_uploaded(self):
        manifest, _ = self.prepared()

        self.assertEqual(manifest["attach_files"], ["bundle_fixture_inputs.zip"])
        uploaded = [Path(p).name for p in request_paths(self.root, manifest["exchange_id"])]
        self.assertEqual(uploaded, ["bundle_fixture_inputs.zip"])
        # The individual files are still on disk as the provenance record, so
        # the archive is a delivery mechanism and not the only copy.
        self.assertEqual(len(manifest["request_files"]), 6)

    def test_the_prompt_is_markdown_and_stays_on_disk_beside_the_archive(self):
        manifest, exchange = self.prepared()

        prompt = exchange / "request" / "000_READ_ME_FIRST.md"
        self.assertTrue(prompt.is_file())
        self.assertEqual(prompt.read_text(encoding="utf-8"), "Read the archive.")

    def test_the_same_inputs_always_produce_the_same_archive(self):
        """Zip entries carry a modification time, which would otherwise make the
        digest change on every run and defeat verifying it against its own
        manifest record."""
        one = self.spec(subject="One", artifacts=("one_outputs.zip",))
        one["expected_main_json"] = "one_response.json"
        two = self.spec(subject="Two", artifacts=("two_outputs.zip",))
        two["expected_main_json"] = "two_response.json"

        first = prepare_call(self.root, one, self.now)
        second = prepare_call(self.root, two, self.now + timedelta(minutes=1))
        first_dir = self.root / "calls" / first["exchange_id"]
        second_dir = self.root / "calls" / second["exchange_id"]

        first_bytes = (first_dir / "request" / "one_inputs.zip").read_bytes()
        second_bytes = (second_dir / "request" / "two_inputs.zip").read_bytes()
        self.assertEqual(first_bytes, second_bytes)

    def test_a_call_may_return_no_artifacts_at_all(self):
        manifest, _ = self.prepared(artifacts=None)

        self.assertEqual(manifest["expected_artifacts"], [])
        self.assertEqual(len(manifest["attach_files"]), 1)

    def test_two_returned_artifacts_are_refused(self):
        with self.assertRaisesRegex(ValueError, "single .zip"):
            prepare_call(
                self.root,
                self.spec(artifacts=("one.zip", "two.zip")),
                self.now,
            )

    def test_a_returned_artifact_that_is_not_an_archive_is_refused(self):
        with self.assertRaisesRegex(ValueError, "single .zip"):
            prepare_call(
                self.root,
                self.spec(artifacts=("findings.md",)),
                self.now,
            )

    def test_the_two_file_shape_cannot_be_asked_for(self):
        """It was an opt-in flag while loose .md uploads still worked. They do
        not, so a spec that turns it off is asking for a call ChatGPT will
        refuse to accept, and failing at prepare beats failing at the upload."""
        spec = self.spec()
        spec["prompt_in_bundle"] = False
        with self.assertRaisesRegex(ValueError, "exactly one zip goes up"):
            prepare_call(self.root, spec, self.now)

    def test_the_launch_line_names_the_archive_and_the_governing_file(self):
        """One zip goes up carrying no instructions of its own. Sent bare it
        gets a model asking what to do with it, so the panel types this."""
        manifest, _ = self.prepared()

        line = launch_prompt(self.root, manifest["exchange_id"])
        self.assertIn("bundle_fixture_inputs.zip", line)
        self.assertIn("000_READ_ME_FIRST.md", line)
        # It routes and says nothing about the work: anything describing that
        # belongs in the prompt inside the archive, where it is hashed.
        self.assertNotIn("Read the archive.", line)

    def test_an_input_may_not_take_the_archive_name(self):
        spec = self.spec()
        spec["input_files"].append(
            {"path": str(self.sources / "context.md"), "filename": "bundle_fixture_inputs.zip"}
        )
        with self.assertRaisesRegex(ValueError, "duplicate input filename"):
            prepare_call(self.root, spec, self.now)


if __name__ == "__main__":
    unittest.main()
