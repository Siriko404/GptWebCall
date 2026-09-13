#!/usr/bin/env python3
"""FinProdLine package precheck — run BEFORE every `gptwebcall prepare`.

Contract: ../../skill/webcall/references/finprodline/FINPRODLINE_PROTOCOL.md §8 and
FINPRODLINE_SKILL.md §5.

Mechanical only: it compares what a package CLAIMS against what it SHIPS, plus the FinProdLine
naming and approval rules. It makes no judgement about content.

Usage:
    fpl_precheck.py --spec <prepare_spec.json> [--project <root>] [--webcall-root <root>]
                    [--turn <n>] [--approved <file-list.json>]

Exit 0 = PASS (safe to prepare). Exit 1 = FAIL (do not prepare).

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MAX_SUBJECT_SLUG = 80
RESERVED_BASENAMES = {"000_READ_ME_FIRST.md"}
GOVERNING = ("WEB_REVIEW_REQUEST.json", "WEB_RESPONSE_SCHEMA.json")
DESTINATION_PREFIX = re.compile(r"^(WORKER-NEW-TAB|COORD-THREAD)-")
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|bearer|private[_-]?key|access[_-]?token)\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def subject_slug(subject: str) -> str:
    """Mirror the installed companion's _subject_slug exactly."""
    return re.sub(r"[^a-z0-9]+", "_", subject.casefold()).strip("_")


def main() -> int:
    ap = argparse.ArgumentParser(prog="fpl_precheck.py")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--project")
    ap.add_argument("--webcall-root")
    ap.add_argument("--turn", type=int)
    ap.add_argument("--approved")
    args = ap.parse_args()

    problems: list[str] = []
    notes: list[str] = []

    spec_path = Path(args.spec).resolve()
    if not spec_path.is_file():
        print(f"FAIL:\n  - spec not found: {spec_path}")
        return 1
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    subject = spec.get("subject", "")
    request_id = spec.get("request_id", "")
    inputs = spec.get("input_files") or []
    names = [f.get("filename", "") for f in inputs]

    # ---- 1. FinProdLine naming rule (D1 ruling)
    if not DESTINATION_PREFIX.match(subject):
        problems.append(
            f"subject must begin WORKER-NEW-TAB- or COORD-THREAD- so the operator knows where the "
            f"package goes; got {subject!r}")
    if args.turn is not None:
        if not re.search(rf"-{args.turn:03d}$", subject):
            notes.append(f"subject does not end in the project-wide turn -{args.turn:03d}; "
                         f"confirm the turn number is correct")

    # ---- 2. the installed 80-character slug budget on the DERIVED archive name
    slug = subject_slug(subject)
    if not slug:
        problems.append(f"subject {subject!r} cannot form a safe exchange slug")
    elif len(slug) > MAX_SUBJECT_SLUG:
        problems.append(
            f"derived subject slug is {len(slug)} chars (> {MAX_SUBJECT_SLUG}); the companion will "
            f"refuse: {slug!r}")
    derived_uploads = f"{slug}_inputs.zip"

    # ---- 3. required fields and declared artifacts
    if not request_id:
        problems.append("request_id is empty")
    if not inputs:
        problems.append("input_files is empty")
    expected_main = spec.get("expected_main_json", "")
    if not expected_main.endswith(".json"):
        problems.append(f"expected_main_json must end .json; got {expected_main!r}")
    expected_artifacts = spec.get("expected_artifacts") or []
    if len(expected_artifacts) != 1:
        problems.append(f"expected_artifacts must be exactly one archive; got {expected_artifacts}")
    for a in expected_artifacts:
        if not a.endswith(".zip"):
            problems.append(f"expected_artifacts entry is not a .zip: {a!r}")

    # ---- 4. paths exist, basenames plain and unique
    missing = [f"{f.get('filename')} -> {f.get('path')}" for f in inputs
               if not Path(f.get("path", "")).is_file()]
    if missing:
        problems.append("declared input files do not exist on disk: " + ", ".join(missing))

    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        problems.append(f"duplicate basenames (the wrapper needs unique plain basenames): {dupes}")
    non_plain = [n for n in names if not n or "/" in n or "\\" in n]
    if non_plain:
        problems.append(f"non-plain basenames: {non_plain}")

    clash = sorted(RESERVED_BASENAMES & set(names))
    if clash:
        problems.append(f"wrapper-reserved basenames listed in input_files (the companion generates "
                        f"these itself -> 'duplicate input filename'): {clash}")

    for required in GOVERNING:
        if required not in names:
            problems.append(f"missing wrapper-required basename {required!r}")

    # ---- 5. request_id agreement across spec, request and schema const
    req_entry = next((f for f in inputs if f.get("filename") == "WEB_REVIEW_REQUEST.json"), None)
    req_json = None
    if req_entry and Path(req_entry["path"]).is_file():
        req_json = json.loads(Path(req_entry["path"]).read_text(encoding="utf-8"))
        if req_json.get("request_id") != request_id:
            problems.append(f"request_id mismatch: request JSON has {req_json.get('request_id')!r}, "
                            f"spec says {request_id!r}")
        sch_entry = next((f for f in inputs if f.get("filename") == "WEB_RESPONSE_SCHEMA.json"), None)
        if sch_entry and Path(sch_entry["path"]).is_file():
            sch = json.loads(Path(sch_entry["path"]).read_text(encoding="utf-8"))
            const = (sch.get("properties", {}).get("request_id", {}) or {}).get("const")
            if const != request_id:
                problems.append(f"schema request_id const is {const!r}, expected {request_id!r}")

    # ---- 6. claimed-but-unshipped: the recurring packaging defect
    if req_json:
        claimed = list((req_json.get("package_contents") or {}).keys())
        shipped = set(names)
        stems = {Path(n).stem for n in shipped}
        unshipped = [c for c in claimed
                     if c not in shipped and c not in stems and Path(c).stem not in stems]
        if unshipped:
            problems.append("CLAIMED IN package_contents BUT NOT SHIPPED: " + ", ".join(sorted(unshipped)))

    # ---- 6b. the prompt's own named deliverables must be the ones the wrapper expects
    #
    # Raised by TERM-FPL-006 manifestation 4. The prompt ships as 000_READ_ME_FIRST.md and is the
    # first thing the worker reads, so a name in it is an instruction. A prompt copied forward from
    # the previous turn and only partly find-and-replaced tells the worker to emit the PREVIOUS
    # turn's filenames — which are still routing names owned by a completed exchange, so the
    # download is filed against that exchange instead of reported as a mismatch.
    prompt = spec.get("prompt_text") or ""
    if prompt:
        if expected_main and expected_main not in prompt:
            problems.append(
                f"PROMPT NEVER NAMES THE EXPECTED MAIN JSON {expected_main!r}. The prompt is what "
                f"the worker obeys; it will name the main file something else and the delivery will "
                f"not be fileable.")
        for a in expected_artifacts:
            if a not in prompt:
                problems.append(
                    f"PROMPT NEVER NAMES THE EXPECTED ARCHIVE {a!r}. Downloads are routed by "
                    f"filename alone, so the archive will be attributed to whichever exchange "
                    f"still owns the name the prompt gave.")
        expected_names = {expected_main, *expected_artifacts}
        stale = {m.group(0) for m in
                 re.finditer(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*_(?:response\.json|outputs\.zip)", prompt)}
        stale -= expected_names
        if stale:
            problems.append(
                "PROMPT NAMES FOREIGN DELIVERABLES (stale turn token?): " + ", ".join(sorted(stale)) +
                ". A prompt must name exactly the archive and main JSON this call expects.")

    # ---- 7. project scope: nothing from Web Call calls/ or state/, nothing outside the project
    if args.project:
        proot = Path(args.project).resolve()
        for f in inputs:
            p = Path(f.get("path", "")).resolve()
            if not str(p).startswith(str(proot)):
                notes.append(f"{f.get('filename')} lives outside the project root: {p}")

    if args.webcall_root:
        wroot = Path(args.webcall_root).resolve()
        for f in inputs:
            p = Path(f.get("path", "")).resolve()
            for forbidden in ("calls", "state"):
                if str(p).startswith(str(wroot / forbidden)):
                    problems.append(
                        f"{f.get('filename')} is under Web Call {forbidden}/ — never transmitted")

    # ---- 8. credentials and tokens, by filename and by content sniff on small text files
    for f in inputs:
        p = Path(f.get("path", ""))
        if p.is_file() and p.stat().st_size < 2_000_000 and re.search(
                r"\.(json|md|txt|csv|ya?ml|py|toml|ini|env)$", p.name, re.I):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pat in SECRET_PATTERNS:
                m = pat.search(text)
                if m:
                    problems.append(f"{f.get('filename')} appears to contain a credential "
                                    f"(matched {m.group(0)!r})")
                    break

    # ---- 9. explicit operator upload approval
    if args.approved:
        approved = set(json.loads(Path(args.approved).read_text(encoding="utf-8")))
        unapproved = sorted(set(names) - approved - set(GOVERNING))
        if unapproved:
            problems.append("NO EXPLICIT OPERATOR UPLOAD APPROVAL for: " + ", ".join(unapproved))
    else:
        problems.append("no --approved list supplied: every project document needs explicit "
                        "operator upload approval before prepare")

    # ---- report
    print(f"spec            : {spec_path}")
    print(f"subject         : {subject!r}")
    print(f"derived upload  : {derived_uploads}")
    print(f"request_id      : {request_id}")
    print(f"expected json   : {expected_main}")
    print(f"expected archive: {expected_artifacts}")
    print(f"inputs          : {len(inputs)} declared, {len(missing)} missing on disk")
    if notes:
        print("\nnotes (not fatal):")
        for n in notes:
            print("  *", n)
    if problems:
        print("\nFAIL:")
        for p in problems:
            print("  -", p)
        print("\nDO NOT PREPARE until every item above is fixed.")
        return 1
    print(f"\nPASS - package matches its claims; safe to run:\n  gptwebcall prepare --spec {spec_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
