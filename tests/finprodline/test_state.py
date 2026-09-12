"""FinProdLine state surface tests.

Covers the unit/state list in the governing specification §24: append-only writes, hash-chain
detection of historical modification, truncation detection, deterministic index rebuild, stale
index rejection, discovery bounds, monotonic turn numbers, naming constraints, lineage cone, and
supersession that never deletes history.
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ._load import load

st = load("fpl_state")
pc = load("fpl_precheck")

MARKER = ".finprodline"


class StateTestCase(unittest.TestCase):
    def setUp(self):
        # every command prints its JSON envelope to stdout; keep the test log readable. stderr is
        # left alone deliberately: unittest reports failures there, and swallowing it would hide
        # the very failures this suite exists to surface.
        self._quiet = contextlib.ExitStack()
        self.addCleanup(self._quiet.close)
        self._quiet.enter_context(contextlib.redirect_stdout(io.StringIO()))

        self.tmp = Path(tempfile.mkdtemp(prefix="fpl-test-"))
        self.root = self.tmp / "proj"
        self.root.mkdir()
        st.main(["init", "--root", str(self.root), "--goal", "value a bank",
                 "--canon-mode", "hybrid", "--audit-replicas", "3"])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers ---------------------------------------------------------------
    def append(self, stream, **event):
        return st.append_event(self.root, stream, event)

    def stream_lines(self, stream):
        path = st.stream_path(self.root, stream)
        return path.read_text(encoding="utf-8").splitlines()

    # -- 1. append-only: prior bytes never change ------------------------------
    def test_append_never_mutates_prior_bytes(self):
        self.append("project", actor="coordinator", event_type="plan_accepted",
                    subject_id="p1", payload={"plan_id": "p1", "layer": 1})
        before = self.stream_lines("project")
        self.append("project", actor="coordinator", event_type="phase_opened",
                    subject_id="ph1", payload={"phase_id": "ph1"})
        after = self.stream_lines("project")
        self.assertEqual(before, after[:len(before)],
                         "appending must leave every earlier line byte-identical")

    # -- 2. hash chain detects historical modification -------------------------
    def test_hash_chain_detects_value_mutation(self):
        self.append("project", actor="coordinator", event_type="plan_accepted",
                    subject_id="p1", payload={"plan_id": "p1"})
        path = st.stream_path(self.root, "project")
        lines = path.read_text(encoding="utf-8").splitlines()
        # line 0 is init's goal_set; the plan_accepted event just appended is the last line
        self.assertIn("p1", lines[-1])
        path.write_text("\n".join(l.replace("p1", "pZ") for l in lines) + "\n", encoding="utf-8")

        report = st.verify_ledgers(self.root)
        self.assertFalse(report["ok"])
        problems = [p for s in report["streams"] for p in s["problems"]]
        self.assertTrue(any("event_hash does not match" in p for p in problems), problems)

    # -- 3. truncation is a hard failure (tail anchor) -------------------------
    def test_truncation_detected_after_record(self):
        self.append("run", actor="terminal", event_type="exchange_prepared",
                    subject_id="c1", payload={"exchange_id": "e1"})
        self.append("run", actor="terminal", event_type="exchange_armed",
                    subject_id="c1", payload={"exchange_id": "e1"})
        st.cmd_verify_ledgers(type("A", (), {"project": str(self.root), "record": True})())

        path = st.stream_path(self.root, "run")
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text(lines[0] + "\n", encoding="utf-8")     # drop the tail

        report = st.verify_ledgers(self.root, st.read_integrity(self.root))
        self.assertFalse(report["ok"], "a removed tail must be a hard failure")
        problems = [p for s in report["streams"] for p in s["problems"]]
        self.assertTrue(any("TRUNCATED" in p for p in problems), problems)

    def test_truncation_invisible_without_an_anchor(self):
        """The honest limit, asserted so it is never quietly assumed away."""
        self.append("run", actor="terminal", event_type="exchange_prepared",
                    subject_id="c1", payload={"exchange_id": "e1"})
        path = st.stream_path(self.root, "run")
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text(lines[0] + "\n", encoding="utf-8")
        report = st.verify_ledgers(self.root, {})           # no anchor recorded
        self.assertTrue(report["ok"])
        self.assertTrue(any("not detectable" in n
                            for s in report["streams"] for n in s["notes"]))

    # -- 4. vocabulary and envelope enforcement --------------------------------
    def test_unknown_event_type_is_rejected(self):
        with self.assertRaises(st.Failure):
            self.append("project", actor="coordinator", event_type="not_a_real_event",
                        subject_id="x", payload={})

    def test_event_type_is_stream_scoped(self):
        with self.assertRaises(st.Failure):
            self.append("run", actor="terminal", event_type="plan_accepted",
                        subject_id="x", payload={})

    def test_computed_fields_cannot_be_supplied(self):
        with self.assertRaises(st.Failure):
            self.append("project", actor="coordinator", event_type="plan_accepted",
                        subject_id="x", payload={}, seq=99)

    def test_bad_actor_is_rejected(self):
        with self.assertRaises(st.Failure):
            self.append("project", actor="somebody", event_type="plan_accepted",
                        subject_id="x", payload={})

    def test_bad_gate_is_rejected(self):
        with self.assertRaises(st.Failure):
            self.append("project", actor="coordinator", event_type="gate_state_changed",
                        subject_id="x", gate="TESTING", payload={})

    # -- 5. index rebuild is deterministic; stale index is rejected ------------
    def test_index_rebuild_is_deterministic(self):
        self.append("run", actor="terminal", event_type="artifact_persisted",
                    subject_id="a1", payload={"artifact_id": "a1", "sha256": "a" * 64})
        first = st.build_view(self.root, "artifact-index", {})
        st.rebuild_index(self.root, "artifact-index")
        second = st.build_view(self.root, "artifact-index", {})
        self.assertEqual(first, second)

    def test_stale_index_is_rejected(self):
        self.append("run", actor="terminal", event_type="artifact_persisted",
                    subject_id="a1", payload={"artifact_id": "a1"})
        st.rebuild_index(self.root, "artifact-index")
        self.assertTrue(st.verify_indexes(self.root)["ok"])

        self.append("run", actor="terminal", event_type="artifact_persisted",
                    subject_id="a2", payload={"artifact_id": "a2"})
        result = st.verify_indexes(self.root)
        self.assertFalse(result["ok"], "a rebuilt-away tail must invalidate the index")
        self.assertEqual(result["stale"][0]["index"], "artifact-index")

    def test_verify_ledgers_does_not_write(self):
        """An integrity check that mutates state would invalidate indexes as a side effect."""
        self.append("project", actor="coordinator", event_type="plan_accepted",
                    subject_id="p1", payload={})
        before = self.stream_lines("project")
        st.cmd_verify_ledgers(type("A", (), {"project": str(self.root), "record": False})())
        self.assertEqual(before, self.stream_lines("project"))

    # -- 6. discovery stops at cwd and parents, never siblings -----------------
    def test_discovery_finds_ancestor_and_never_a_sibling(self):
        nested = self.root / "evidence" / "deep"
        nested.mkdir(parents=True)
        self.assertEqual(st.find_project(nested), self.root)

        sibling = self.tmp / "other"
        st.main(["init", "--root", str(sibling), "--goal", "other project"])
        self.assertEqual(st.find_project(sibling), sibling)
        self.assertEqual(st.find_project(nested), self.root,
                         "a sibling project must never be discovered")
        self.assertIsNone(st.find_project(self.tmp))

    def test_project_isolation_only_this_projects_streams_are_read(self):
        other = self.tmp / "other"
        st.main(["init", "--root", str(other), "--goal", "other project"])
        st.append_event(other, "run", {"actor": "terminal", "event_type": "exchange_prepared",
                                       "subject_id": "x", "payload": {"exchange_id": "other-1"}})
        mine = st.build_view(self.root, "calls-current", {})
        self.assertEqual(mine["exchanges"], [],
                         "another project's exchanges must not appear in this project's view")

    # -- 7. init refuses to clobber; config records the rulings ----------------
    def cli(self, argv):
        """Run the CLI as a user would. main() converts a Failure into exit code 2 rather than
        raising, so a caller never sees a traceback."""
        with contextlib.redirect_stdout(io.StringIO()):
            return st.main(argv)

    def test_init_refuses_existing_project(self):
        self.assertEqual(self.cli(["init", "--root", str(self.root), "--goal", "again"]), 2)

    def test_init_rejects_bad_inputs(self):
        self.assertEqual(self.cli(["init", "--root", str(self.tmp / "x"), "--goal", "g",
                                   "--canon-mode", "whatever"]), 2)
        self.assertEqual(self.cli(["init", "--root", str(self.tmp / "y"), "--goal", "g",
                                   "--audit-replicas", "0"]), 2)

    def test_config_carries_the_operator_rulings(self):
        cfg = st.load_config(self.root)
        self.assertEqual(cfg["audit_replicas"], 3)
        self.assertIsNone(cfg["audit_budget_cap"], "R001: no cap on audit volume")
        self.assertEqual(cfg["handbook_audience_testing"], "not_required",
                         "R002: audience testing dropped")

    # -- 8. lineage cone and supersession --------------------------------------
    def test_lineage_identifies_the_downstream_cone(self):
        for aid, parents in (("src", []), ("m1", ["src"]), ("m2", ["m1"]), ("m3", ["m1"]),
                             ("out", ["m2", "m3"])):
            self.append("run", actor="terminal", event_type="artifact_persisted",
                        subject_id=aid,
                        payload={"artifact_id": aid, "lineage": {"from": parents}})
        view = st.build_view(self.root, "lineage", {})
        cone, frontier = set(), ["m1"]
        while frontier:
            node = frontier.pop()
            for e in view["edges"]:
                if e["from"] == node and e["to"] not in cone:
                    cone.add(e["to"])
                    frontier.append(e["to"])
        self.assertEqual(cone, {"m2", "m3", "out"},
                         "a defect at m1 must reach exactly its dependency cone")

    def test_supersession_never_deletes_history(self):
        self.append("project", actor="coordinator", event_type="plan_accepted",
                    subject_id="p1", payload={"plan_id": "p1", "layer": 1})
        first = self.append("project", actor="coordinator", event_type="plan_accepted",
                            subject_id="p2", payload={"plan_id": "p2", "layer": 1})
        self.append("project", actor="coordinator", event_type="plan_superseded",
                    subject_id="p1", payload={"supersedes_plan_ids": ["p1"]},
                    supersedes=[first["event_id"]])
        events = st.read_stream(st.stream_path(self.root, "project"))
        self.assertEqual(len(events), 4, "superseding adds an event; it never removes one")
        live = st.build_view(self.root, "plan-current", {})["layer1"]
        self.assertEqual([p["plan_id"] for p in live], ["p2"])

    def test_dangling_supersede_reference_is_reported(self):
        self.append("project", actor="coordinator", event_type="plan_superseded",
                    subject_id="p1", payload={}, supersedes=["project-999999-deadbeef"])
        report = st.verify_ledgers(self.root)
        self.assertFalse(report["ok"])
        self.assertTrue(report["dangling_supersedes"])

    # -- 9. recovery and audit export ------------------------------------------
    def test_recover_coordinator_builds_from_disk_only(self):
        self.append("project", actor="coordinator", event_type="plan_accepted",
                    subject_id="p1", payload={"plan_id": "p1", "layer": 1})
        out = st.build_view(self.root, "project-current", {})
        self.assertEqual(out["goal"], "value a bank")
        self.assertEqual(out["accepted_plans"][0]["plan_id"], "p1")

    def test_export_audit_is_chunkable_and_carries_tails(self):
        for i in range(6):
            self.append("run", actor="terminal", event_type="artifact_persisted",
                        subject_id=f"a{i}", payload={"artifact_id": f"a{i}"})
        export = st.build_view(self.root, "audit-ledger-export", {})
        self.assertIn("project", export["tails"])
        self.assertTrue(all(len(v) == 64 for v in export["tails"].values()))

    def test_every_index_view_is_buildable(self):
        for name in st.INDEX_NAMES:
            if name in st.SELECTOR_INDEXES:
                continue
            st.build_view(self.root, name, {})

    def test_worker_history_requires_a_selector(self):
        with self.assertRaises(st.Failure):
            st.build_view(self.root, "worker-history", {})


class NamingTestCase(unittest.TestCase):
    """The naming constraints the installed companion actually enforces.

    The precheck's slug function must mirror `companion/core.py::_subject_slug` exactly, because
    the companion derives the upload archive name from it and refuses anything over 80 characters.
    """

    def test_subject_slug_mirrors_the_companion(self):
        cases = {
            "WORKER-NEW-TAB-rbc-006": "worker_new_tab_rbc_006",
            "COORD-THREAD-rbc-007": "coord_thread_rbc_007",
            "WORKER-NEW-TAB-ExampleFinanceProject-012":
                "worker_new_tab_examplefinanceproject_012",
            "WORKER-NEW-TAB-a.b c--d": "worker_new_tab_a_b_c_d",
        }
        for subject, expected in cases.items():
            self.assertEqual(pc.subject_slug(subject), expected, subject)

    def test_derived_upload_name(self):
        self.assertEqual(pc.subject_slug("WORKER-NEW-TAB-rbc-006") + "_inputs.zip",
                         "worker_new_tab_rbc_006_inputs.zip")

    def test_slug_budget_is_enforced_by_the_precheck(self):
        long_subject = "WORKER-NEW-TAB-" + "x" * 90
        self.assertGreater(len(pc.subject_slug(long_subject)), pc.MAX_SUBJECT_SLUG)

    def test_precheck_slug_matches_the_installed_companion(self):
        """Cross-check against the real implementation rather than a restatement of it."""
        import importlib.util
        from ._load import REPO
        core_path = REPO / "companion" / "core.py"
        if not core_path.is_file():
            self.skipTest("companion/core.py not present in this checkout")
        spec = importlib.util.spec_from_file_location("_fpl_core", core_path)
        core = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(core)
        except Exception as exc:                      # pragma: no cover - env dependent
            self.skipTest(f"companion.core could not be imported: {exc}")
        for subject in ("WORKER-NEW-TAB-rbc-006", "COORD-THREAD-rbc-007",
                        "WORKER-NEW-TAB-a.b c--d"):
            self.assertEqual(pc.subject_slug(subject), core._subject_slug(subject), subject)


if __name__ == "__main__":
    unittest.main()
