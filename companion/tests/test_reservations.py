"""Deliverable filenames must be reserved atomically, and re-reserved on repair.

Downloads are attributed by filename alone, so a name may belong to only one
call that can still receive files. Two paths broke that guarantee:

Preparation checked the names, then spent time copying and hashing inputs, then
published. Two preparations overlapping in that window both saw the names free.

Repair reopens a finished exchange. Finished exchanges have already released
their names, so another call may have taken them in the meantime; repair
transitioned the old one back to ACTIVE without looking.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from companion import core
from companion.core import prepare_call
from companion.downloads import finalize_exchange
from companion.repair import open_repair_round

WHEN = datetime(2026, 8, 8, 18, 0, 0, tzinfo=timezone(timedelta(hours=-4)))


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.root = base / "GptWebCall"
        self.sources = base / "sources"
        self.sources.mkdir()
        self.schema = self.sources / "WEB_RESPONSE_SCHEMA.json"
        self.schema.write_text('{"type":"object"}\n', encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def spec(self, subject, request_id, main):
        # One request file per call: the racing preparations overlap and must not
        # overwrite each other's governing document.
        request = self.sources / f"{request_id}.json"
        request.write_text(
            json.dumps({"request_id": request_id}) + "\n", encoding="utf-8"
        )
        return {
            "subject": subject,
            "request_id": request_id,
            "expected_main_json": main,
            "prompt_text": "Return files only.\n",
            "input_files": [
                {"path": str(request), "filename": "WEB_REVIEW_REQUEST.json"},
                {"path": str(self.schema), "filename": "WEB_RESPONSE_SCHEMA.json"},
            ],
        }

    def test_a_name_claimed_while_inputs_are_copied_still_blocks_publication(self):
        """The window between the check and the publish must not be exploitable.

        Copying and hashing inputs happens between them and is unbounded, so a
        second preparation can start, see the name free, and publish. The names
        are re-checked while holding the state lock, immediately before the
        exchange becomes visible.
        """
        original = core._copy_verified
        competitor = {"done": False}

        def copy_and_race(source, destination):
            # Stand in for a second preparation that wins the race: it claims the
            # same deliverable name while this one is still staging its inputs.
            if not competitor["done"]:
                competitor["done"] = True
                prepare_call(
                    self.root,
                    self.spec("rival", "request_rival", "contested.json"),
                    WHEN + timedelta(seconds=1),
                )
            return original(source, destination)

        core._copy_verified = copy_and_race
        try:
            with self.assertRaises(ValueError) as caught:
                prepare_call(
                    self.root,
                    self.spec("mine", "request_mine", "contested.json"),
                    WHEN,
                )
        finally:
            core._copy_verified = original

        self.assertIn("already claimed", str(caught.exception))
        published = sorted(path.name for path in (self.root / "calls").iterdir())
        self.assertEqual(published, ["2026-08-08_180001_rival"])
        # The refused preparation cleans up after itself: staging directories are
        # named ".<exchange_id>-<random>" and none may survive. The state lock is
        # a permanent fixture, not debris.
        leftovers = [
            path.name
            for path in (self.root / "state").iterdir()
            if path.is_dir() and path.name.startswith(".")
        ]
        self.assertEqual(leftovers, [])

    def test_repair_is_refused_when_another_call_took_the_names(self):
        first = prepare_call(
            self.root, self.spec("first", "request_first", "shared.json"), WHEN
        )
        exchange = self.root / "calls" / first["exchange_id"]
        (exchange / "response" / "shared.json").write_text(
            json.dumps(
                {
                    "request_id": "request_first",
                    "status": "PARTIAL",
                    "artifacts_manifest": [
                        {
                            "filename": "absent.md",
                            "status": "CREATED",
                            "media_type": "text/markdown",
                            "size": 3,
                            "sha256": "a" * 64,
                        }
                    ],
                    "delivery": ["shared.json"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        finalize_exchange(self.root, first["exchange_id"])

        # Finished, so the name was released and a second call legitimately took it.
        second = prepare_call(
            self.root,
            self.spec("second", "request_second", "shared.json"),
            WHEN + timedelta(minutes=1),
        )

        with self.assertRaises(RuntimeError) as caught:
            open_repair_round(self.root, first["exchange_id"], tab_id=7)

        self.assertIn(second["exchange_id"], str(caught.exception))
        self.assertIn("shared.json", str(caught.exception))
        # Refused cleanly: no round recorded, no orphan prompt, state untouched.
        stored = json.loads(
            (exchange / "EXCHANGE_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(stored["state"], "INCOMPLETE")
        self.assertNotIn("repair_round", stored)
        self.assertFalse((exchange / "repair").exists())

    def test_repair_still_works_when_no_other_call_wants_the_names(self):
        first = prepare_call(
            self.root, self.spec("solo", "request_solo", "solo.json"), WHEN
        )
        exchange = self.root / "calls" / first["exchange_id"]
        (exchange / "response" / "solo.json").write_text(
            json.dumps(
                {
                    "request_id": "request_solo",
                    "status": "COMPLETE",
                    "artifacts_manifest": [
                        {
                            "filename": "absent.md",
                            "status": "CREATED",
                            "media_type": "text/markdown",
                            "size": 3,
                            "sha256": "a" * 64,
                        }
                    ],
                    "delivery": ["solo.json"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        finalize_exchange(self.root, first["exchange_id"])

        opened = open_repair_round(self.root, first["exchange_id"], tab_id=7)

        self.assertEqual(opened["round"], 1)


if __name__ == "__main__":
    unittest.main()
