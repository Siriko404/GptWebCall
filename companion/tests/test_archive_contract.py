"""A responder may declare the files inside the outputs archive.

Under "two files up, two files down" every returned file except the main JSON
travels inside one archive. The protocol also tells the responder to list every
additional file in `artifacts_manifest`, so responders routinely enumerate the
archive's members there and declare a SHA-256 for each. That is the reading that
preserves integrity checking: a member's hash is the only way to detect a
truncated or corrupted file inside the archive.

The validator did not know it. A member is not a file in `response\\`, so every
declared member was reported missing, and the strict parser rejected the whole
response because `delivery` named the two files that actually came down rather
than all forty-odd declared ones. One real call produced forty-four defects
against a delivery whose two files were byte-exact.

These tests fix the contract in both directions: a declared member is satisfied
by its presence inside a delivered archive and verified against its declared
hash, while a member that is absent or corrupt is still reported.
"""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from companion.core import prepare_call
from companion.downloads import validate_response
from companion.repair import collect_defects

MEMBERS = {"finding_one.md": b"first finding\n", "finding_two.md": b"second finding\n"}


class ArchiveContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.root = base / "GptWebCall"
        sources = base / "sources"
        sources.mkdir()

        def source(name, value):
            path = sources / name
            path.write_text(json.dumps(value) + "\n", encoding="utf-8")
            return path

        spec = {
            "subject": "pack",
            "request_id": "request_pack",
            "expected_main_json": "pack_response.json",
            "expected_artifacts": ["pack_outputs.zip"],
            "prompt_text": "Return two files.\n",
            "input_files": [
                {
                    "path": str(source("WEB_REVIEW_REQUEST.json", {"request_id": "request_pack"})),
                    "filename": "WEB_REVIEW_REQUEST.json",
                },
                {
                    "path": str(source("WEB_RESPONSE_SCHEMA.json", {"type": "object"})),
                    "filename": "WEB_RESPONSE_SCHEMA.json",
                },
            ],
        }
        now = datetime(2026, 8, 8, 16, 40, 17, tzinfo=timezone(timedelta(hours=-4)))
        self.manifest = prepare_call(self.root, spec, now)
        self.exchange = self.root / "calls" / self.manifest["exchange_id"]

    def tearDown(self):
        self.temp.cleanup()

    def archive_bytes(self, members=MEMBERS):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, contents in members.items():
                archive.writestr(name, contents)
        return buffer.getvalue()

    def deliver(self, *, members=MEMBERS, declared=None, status="COMPLETE"):
        """Write the two downloadable files, declaring the archive and its members."""
        archive = self.archive_bytes(members)
        (self.exchange / "response" / "pack_outputs.zip").write_bytes(archive)
        entries = [
            {
                "filename": "pack_outputs.zip",
                "status": "CREATED",
                "media_type": "application/zip",
                "size": len(archive),
                "sha256": hashlib.sha256(archive).hexdigest(),
            }
        ]
        for name, contents in (declared if declared is not None else MEMBERS).items():
            entries.append(
                {
                    "filename": name,
                    "status": "CREATED",
                    "media_type": "text/markdown",
                    "size": len(contents),
                    "sha256": hashlib.sha256(contents).hexdigest(),
                }
            )
        main = {
            "request_id": "request_pack",
            "status": status,
            "artifacts_manifest": entries,
            "delivery": ["pack_response.json", "pack_outputs.zip"],
        }
        (self.exchange / "response" / "pack_response.json").write_text(
            json.dumps(main) + "\n", encoding="utf-8"
        )

    def test_declared_archive_members_validate_against_their_hashes(self):
        self.deliver()

        report = validate_response(self.exchange)

        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["missing_files"], [])
        self.assertEqual(report["invalid_files"], [])
        # The point of the fix: the declared hashes were usable, so they were
        # used. Falling back to a structural check here reported COMPLETE by
        # giving up rather than by verifying.
        self.assertTrue(report["manifest_verified"])
        for name in MEMBERS:
            self.assertIn(name, report["checked_files"])

    def test_declaring_members_produces_no_defects(self):
        self.deliver()

        self.assertEqual(collect_defects(self.exchange), [])

    def test_a_member_that_is_not_in_the_archive_is_still_missing(self):
        self.deliver(
            members={"finding_one.md": MEMBERS["finding_one.md"]},
            declared=MEMBERS,
        )

        report = validate_response(self.exchange)

        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertIn("finding_two.md", report["missing_files"])
        kinds = {defect["kind"] for defect in collect_defects(self.exchange)}
        self.assertIn("ARTIFACT_MISSING", kinds)

    def test_a_corrupt_member_is_invalid_even_though_the_archive_opens(self):
        self.deliver(
            members={**MEMBERS, "finding_two.md": b"tampered\n"},
            declared=MEMBERS,
        )

        report = validate_response(self.exchange)

        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertIn("finding_two.md", report["invalid_files"])
        kinds = {defect["kind"] for defect in collect_defects(self.exchange)}
        self.assertIn("ARTIFACT_HASH_MISMATCH", kinds)

    def test_an_intact_partial_delivery_that_declares_members_is_not_a_defect(self):
        """PARTIAL is the responder's account of its work, not a delivery fault.

        validate_response stopped conflating the two; collect_defects had not.
        """
        self.deliver(status="PARTIAL")

        report = validate_response(self.exchange)

        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["response_status"], "PARTIAL")
        self.assertFalse(report["work_complete"])
        self.assertEqual(collect_defects(self.exchange), [])


if __name__ == "__main__":
    unittest.main()
