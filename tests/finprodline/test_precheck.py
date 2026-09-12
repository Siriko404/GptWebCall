"""FinProdLine package-precheck tests.

Covers the precheck list in the governing specification §24: claimed-but-unshipped files, request-ID
drift, reserved basenames, duplicate and non-plain basenames, missing declared paths, the naming
rule, output-name shape, path escapes, unapproved uploads and credential detection.

Each test asserts both that a bad package FAILS and that the healthy package PASSES, so a check
that fails everything is not mistaken for a working check.
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ._load import load

pc = load("fpl_precheck")

REQUEST_ID = "demo-spec-d1-v1"
SUBJECT = "WORKER-NEW-TAB-demo-006"


class PrecheckTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fpl-pre-"))
        self.pkg = self.tmp / "pkg"
        self.pkg.mkdir()

        self.request = {
            "request_id": REQUEST_ID,
            "objective": "do the thing",
            "package_contents": {"context.md": "the context"},
        }
        (self.pkg / "WEB_REVIEW_REQUEST.json").write_text(json.dumps(self.request))
        (self.pkg / "WEB_RESPONSE_SCHEMA.json").write_text(json.dumps({
            "properties": {"request_id": {"const": REQUEST_ID}}}))
        (self.pkg / "context.md").write_text("# context\n")
        (self.pkg / "approved.json").write_text(json.dumps(["context.md"]))

        self.spec = {
            "subject": SUBJECT,
            "request_id": REQUEST_ID,
            "expected_main_json": "worker_new_tab_demo_006_response.json",
            "expected_artifacts": ["worker_new_tab_demo_006_outputs.zip"],
            "prompt_text": "do the thing",
            "input_files": [
                {"path": str(self.pkg / "WEB_REVIEW_REQUEST.json"),
                 "filename": "WEB_REVIEW_REQUEST.json"},
                {"path": str(self.pkg / "WEB_RESPONSE_SCHEMA.json"),
                 "filename": "WEB_RESPONSE_SCHEMA.json"},
                {"path": str(self.pkg / "context.md"), "filename": "context.md"},
            ],
        }

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_precheck(self, spec=None, **extra):
        spec_path = self.pkg / "spec.json"
        spec_path.write_text(json.dumps(spec or self.spec))
        argv = ["fpl_precheck.py", "--spec", str(spec_path),
                "--approved", str(self.pkg / "approved.json")]
        for k, v in extra.items():
            argv += [f"--{k.replace('_', '-')}", str(v)]
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(buf):
            rc = pc.main()
        return rc, buf.getvalue()

    # -- the healthy baseline --------------------------------------------------
    def test_healthy_package_passes(self):
        rc, out = self.run_precheck()
        self.assertEqual(rc, 0, out)
        self.assertIn("PASS", out)
        self.assertIn("worker_new_tab_demo_006_inputs.zip", out)

    # -- naming rule (operator ruling D1) --------------------------------------
    def test_subject_must_carry_the_destination_prefix(self):
        spec = dict(self.spec, subject="demo-worker-newtab-006")
        rc, out = self.run_precheck(spec)
        self.assertEqual(rc, 1)
        self.assertIn("WORKER-NEW-TAB-", out)

    def test_coord_thread_subject_is_accepted(self):
        rc, out = self.run_precheck(dict(self.spec, subject="COORD-THREAD-demo-007"))
        self.assertEqual(rc, 0, out)

    def test_over_long_derived_slug_is_caught(self):
        rc, out = self.run_precheck(dict(self.spec, subject="WORKER-NEW-TAB-" + "x" * 90))
        self.assertEqual(rc, 1)
        self.assertIn("derived subject slug is", out)
        self.assertIn("(> 80)", out)

    def test_turn_mismatch_is_a_note_not_a_failure(self):
        rc, out = self.run_precheck(turn=9)
        self.assertEqual(rc, 0, out)
        self.assertIn("notes (not fatal)", out)

    # -- artifact shape --------------------------------------------------------
    def test_expected_artifacts_must_be_exactly_one_zip(self):
        rc, out = self.run_precheck(dict(self.spec, expected_artifacts=["a.zip", "b.zip"]))
        self.assertEqual(rc, 1)
        self.assertIn("exactly one archive", out)

    def test_non_zip_artifact_is_refused(self):
        rc, out = self.run_precheck(dict(self.spec, expected_artifacts=["a.json"]))
        self.assertEqual(rc, 1)
        self.assertIn("not a .zip", out)

    def test_main_json_must_be_json(self):
        rc, out = self.run_precheck(dict(self.spec, expected_main_json="thing.txt"))
        self.assertEqual(rc, 1)
        self.assertIn("must end .json", out)

    # -- the recurring packaging defect ---------------------------------------
    def test_claimed_but_unshipped_is_caught(self):
        req = dict(self.request)
        req["package_contents"] = {"context.md": "the context", "phantom.md": "never shipped"}
        (self.pkg / "WEB_REVIEW_REQUEST.json").write_text(json.dumps(req))
        rc, out = self.run_precheck()
        self.assertEqual(rc, 1)
        self.assertIn("CLAIMED IN package_contents BUT NOT SHIPPED", out)
        self.assertIn("phantom.md", out)

    def test_missing_declared_path_is_caught(self):
        spec = json.loads(json.dumps(self.spec))
        spec["input_files"][2]["path"] = str(self.pkg / "gone.md")
        rc, out = self.run_precheck(spec)
        self.assertEqual(rc, 1)
        self.assertIn("do not exist on disk", out)

    def test_duplicate_basenames_are_caught(self):
        spec = json.loads(json.dumps(self.spec))
        spec["input_files"].append({"path": str(self.pkg / "context.md"),
                                    "filename": "context.md"})
        rc, out = self.run_precheck(spec)
        self.assertEqual(rc, 1)
        self.assertIn("duplicate basenames", out)

    def test_non_plain_basename_is_caught(self):
        spec = json.loads(json.dumps(self.spec))
        spec["input_files"][2]["filename"] = "sub/context.md"
        rc, out = self.run_precheck(spec)
        self.assertEqual(rc, 1)
        self.assertIn("non-plain basenames", out)

    def test_reserved_readme_basename_is_caught(self):
        (self.pkg / "000_READ_ME_FIRST.md").write_text("x")
        spec = json.loads(json.dumps(self.spec))
        spec["input_files"].append({"path": str(self.pkg / "000_READ_ME_FIRST.md"),
                                    "filename": "000_READ_ME_FIRST.md"})
        rc, out = self.run_precheck(spec)
        self.assertEqual(rc, 1)
        self.assertIn("wrapper-reserved", out)

    def test_governing_files_are_required(self):
        spec = json.loads(json.dumps(self.spec))
        spec["input_files"] = [f for f in spec["input_files"]
                               if f["filename"] != "WEB_RESPONSE_SCHEMA.json"]
        rc, out = self.run_precheck(spec)
        self.assertEqual(rc, 1)
        self.assertIn("WEB_RESPONSE_SCHEMA.json", out)

    # -- request id agreement --------------------------------------------------
    def test_request_id_drift_spec_vs_request(self):
        req = dict(self.request, request_id="different-v1")
        (self.pkg / "WEB_REVIEW_REQUEST.json").write_text(json.dumps(req))
        rc, out = self.run_precheck()
        self.assertEqual(rc, 1)
        self.assertIn("request_id mismatch", out)

    def test_request_id_drift_schema_const(self):
        (self.pkg / "WEB_RESPONSE_SCHEMA.json").write_text(json.dumps({
            "properties": {"request_id": {"const": "wrong-v1"}}}))
        rc, out = self.run_precheck()
        self.assertEqual(rc, 1)
        self.assertIn("schema request_id const", out)

    # -- upload approval -------------------------------------------------------
    def test_unapproved_files_are_refused(self):
        (self.pkg / "extra.md").write_text("x")
        spec = json.loads(json.dumps(self.spec))
        spec["input_files"].append({"path": str(self.pkg / "extra.md"), "filename": "extra.md"})
        rc, out = self.run_precheck(spec)
        self.assertEqual(rc, 1)
        self.assertIn("NO EXPLICIT OPERATOR UPLOAD APPROVAL", out)
        self.assertIn("extra.md", out)

    def test_missing_approved_list_is_refused(self):
        spec_path = self.pkg / "spec.json"
        spec_path.write_text(json.dumps(self.spec))
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["fpl_precheck.py", "--spec", str(spec_path)]), \
                contextlib.redirect_stdout(buf):
            rc = pc.main()
        self.assertEqual(rc, 1)
        self.assertIn("no --approved list supplied", buf.getvalue())

    # -- web call transmission prohibitions ------------------------------------
    def test_webcall_calls_and_state_paths_are_refused(self):
        wroot = self.tmp / "webcall"
        (wroot / "state").mkdir(parents=True)
        secret = wroot / "state" / "scratch.md"
        secret.write_text("private")
        spec = json.loads(json.dumps(self.spec))
        spec["input_files"].append({"path": str(secret), "filename": "scratch.md"})
        (self.pkg / "approved.json").write_text(json.dumps(["context.md", "scratch.md"]))
        rc, out = self.run_precheck(spec, webcall_root=wroot)
        self.assertEqual(rc, 1)
        self.assertIn("never transmitted", out)

    def test_outside_project_is_a_note_not_a_failure(self):
        rc, out = self.run_precheck(project=self.tmp / "elsewhere")
        self.assertEqual(rc, 0, out)
        self.assertIn("outside the project root", out)

    # -- credentials -----------------------------------------------------------
    def test_credential_in_content_is_caught(self):
        (self.pkg / "context.md").write_text("api_key: sk-abcdefghijklmnopqrstuvwxyz\n")
        rc, out = self.run_precheck()
        self.assertEqual(rc, 1)
        self.assertIn("appears to contain a credential", out)

    def test_private_key_block_is_caught(self):
        (self.pkg / "context.md").write_text("-----BEGIN RSA PRIVATE KEY-----\n")
        rc, out = self.run_precheck()
        self.assertEqual(rc, 1)
        self.assertIn("appears to contain a credential", out)

    def test_ordinary_security_prose_is_not_a_credential(self):
        (self.pkg / "context.md").write_text(
            "# Security review\n"
            "The schema pins the request_id; the token budget matters.\n"
        )
        rc, out = self.run_precheck()
        self.assertEqual(rc, 0, out)

    # -- robustness ------------------------------------------------------------
    def test_bad_select_is_reported_not_traced(self):
        spec = json.loads(json.dumps(self.spec))
        spec["input_files"] = []
        rc, out = self.run_precheck(spec)
        self.assertEqual(rc, 1)
        self.assertIn("input_files is empty", out)

    def test_missing_spec_file_fails_cleanly(self):
        buf = io.StringIO()
        with mock.patch.object(sys, "argv",
                               ["fpl_precheck.py", "--spec", str(self.pkg / "nope.json")]), \
                contextlib.redirect_stdout(buf):
            rc = pc.main()
        self.assertEqual(rc, 1)
        self.assertIn("spec not found", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
