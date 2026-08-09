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

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from companion import core
from companion.core import prepare_call
from companion import downloads
from companion.downloads import finalize_exchange, handle_completed_download
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

    def artifact_spec(self, subject, request_id, main, artifacts):
        spec = self.spec(subject, request_id, main)
        spec["expected_artifacts"] = artifacts
        return spec

    def deliver_main(self, exchange_id, request_id, main_name, entries):
        exchange = self.root / "calls" / exchange_id
        (exchange / "response" / main_name).write_text(
            json.dumps(
                {
                    "request_id": request_id,
                    "status": "COMPLETE",
                    "artifacts_manifest": entries,
                    "delivery": [main_name],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_a_reserved_call_ignores_an_artifact_it_never_reserved(self):
        """The response names its own artifacts, so without a reservation the
        model decides what the exchange will accept. Where the call reserved its
        artifact filenames, only those are filed; anything else is left in the
        downloads folder for the operator to deal with."""
        prepared = prepare_call(
            self.root,
            self.artifact_spec("guarded", "request_guarded", "guard.json", ["guard_outputs.zip"]),
            WHEN,
        )
        core.start_call(self.root, prepared["exchange_id"], 3, [])
        body = b"rogue\n"
        self.deliver_main(
            prepared["exchange_id"],
            "request_guarded",
            "guard.json",
            [
                {
                    "filename": "rogue.md",
                    "status": "CREATED",
                    "media_type": "text/markdown",
                    "size": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
            ],
        )
        stray = Path(self.temp.name) / "rogue.md"
        stray.write_bytes(body)

        result = handle_completed_download(
            self.root, {"id": 5, "filename": str(stray), "state": "complete"}
        )

        self.assertEqual(result["status"], "IGNORED")
        self.assertTrue(stray.is_file(), "an unreserved download stays where Chrome put it")
        self.assertFalse(
            (self.root / "calls" / prepared["exchange_id"] / "response" / "rogue.md").exists()
        )

    def test_a_call_that_reserved_nothing_still_accepts_what_it_declares(self):
        """expected_artifacts is optional, and calls prepared without it must keep
        working: with no reservation the main JSON remains the only authority."""
        prepared = prepare_call(
            self.root, self.spec("open", "request_open", "open.json"), WHEN
        )
        core.start_call(self.root, prepared["exchange_id"], 4, [])
        body = b"declared\n"
        self.deliver_main(
            prepared["exchange_id"],
            "request_open",
            "open.json",
            [
                {
                    "filename": "extra.md",
                    "status": "CREATED",
                    "media_type": "text/markdown",
                    "size": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
            ],
        )
        stray = Path(self.temp.name) / "extra.md"
        stray.write_bytes(body)

        result = handle_completed_download(
            self.root, {"id": 6, "filename": str(stray), "state": "complete"}
        )

        self.assertEqual(result["status"], "MOVED")

    def test_the_pending_pool_drops_what_it_can_never_release(self):
        """Unclaimed downloads accumulated for the life of the installation.

        An artifact downloaded before any main JSON waits in a shared pool until
        some call names it. Nothing removed an entry that was never named, so one
        real installation held 71, the oldest eighteen days old.
        """
        prepared = prepare_call(
            self.root, self.spec("pool", "request_pool", "pool.json"), WHEN
        )
        core.start_call(self.root, prepared["exchange_id"], 8, [])
        alive = Path(self.temp.name) / "recent.md"
        alive.write_bytes(b"recent\n")
        stale = Path(self.temp.name) / "stale.md"
        stale.write_bytes(b"stale\n")
        now = datetime.now(timezone.utc)
        (self.root / "state" / "PENDING_DOWNLOADS.json").write_text(
            json.dumps(
                {
                    "downloads": [
                        {"id": 1, "filename": str(alive), "held_at": now.isoformat()},
                        {
                            "id": 2,
                            "filename": str(stale),
                            "held_at": (now - timedelta(days=30)).isoformat(),
                        },
                        {"id": 3, "filename": str(Path(self.temp.name) / "gone.md")},
                        {"id": 4, "filename": str(alive)},
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )
        fresh = Path(self.temp.name) / "fresh.md"
        fresh.write_bytes(b"fresh\n")

        downloads._hold_pending(self.root, 9, fresh)

        held = json.loads(
            (self.root / "state" / "PENDING_DOWNLOADS.json").read_text(encoding="utf-8")
        )["downloads"]
        self.assertEqual(
            sorted(item["id"] for item in held),
            [1, 9],
            "kept: the recent entry and the new one. Dropped: expired, vanished, "
            "and the untimestamped entry that predates the field.",
        )

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
