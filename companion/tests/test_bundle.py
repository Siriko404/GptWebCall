"""Everything except the prompt travels as one archive.

Two files go up and two come back. That is the whole rule, and these tests pin
the parts of it that could silently regress: what lands inside the archive, that
the archive is the only thing uploaded beside the prompt, that its digest is
stable, and that the return side is held to a single archive as well.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from companion.core import prepare_call, request_paths


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

    def test_the_archive_holds_every_input_and_never_the_prompt(self):
        manifest, exchange = self.prepared()
        archive = exchange / "request" / "bundle_fixture_inputs.zip"

        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            self.assertEqual(
                sorted(names),
                [
                    "WEB_RESPONSE_SCHEMA.json",
                    "WEB_REVIEW_REQUEST.json",
                    "context.md",
                    "deck.pdf",
                ],
            )
            self.assertEqual(bundle.read("context.md"), b"context body")
        self.assertFalse(any(name.startswith("PROMPT_") for name in names))

    def test_only_the_prompt_and_the_archive_are_uploaded(self):
        manifest, _ = self.prepared()

        uploaded = [Path(p).name for p in request_paths(self.root, manifest["exchange_id"])]
        self.assertEqual(
            uploaded, ["PROMPT_2026-07-21_200000.md", "bundle_fixture_inputs.zip"]
        )
        # The individual files are still on disk as the provenance record, so
        # the archive is a delivery mechanism and not the only copy.
        self.assertEqual(len(manifest["request_files"]), 6)

    def test_the_prompt_is_markdown(self):
        manifest, exchange = self.prepared()

        prompt = exchange / "request" / "PROMPT_2026-07-21_200000.md"
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
        self.assertEqual(len(manifest["attach_files"]), 2)

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

    def test_an_input_may_not_take_the_archive_name(self):
        spec = self.spec()
        spec["input_files"].append(
            {"path": str(self.sources / "context.md"), "filename": "bundle_fixture_inputs.zip"}
        )
        with self.assertRaisesRegex(ValueError, "duplicate input filename"):
            prepare_call(self.root, spec, self.now)


if __name__ == "__main__":
    unittest.main()
