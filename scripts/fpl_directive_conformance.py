#!/usr/bin/env python3
"""FinProdLine directive-conformance check — run BEFORE `fpl_precheck` on every package.

Raised by Terminal defect TERM-FPL-006. Three packaging failures in one call had one root cause:
Terminal assembled the package from habit instead of from the directive. It dropped a required
envelope instruction, omitted a context item the directive named, and invented a deliverable name
that contradicted the directive's own. The delivery arrived INCOMPLETE, and an independent reviewer
had to return BLOCKED because an authority file it was told to use was not in the archive.

This program is the mechanical answer. It checks three things:

  RULE 1  every filename the directive's INPUT context names is actually packaged.
  RULE 2  every sibling directive the context REFERENCES (a bare `D003`, `D006`, ...) is packaged.
          This is the rule that catches the failure above: the directive said "plus D006
          directive/rulings from this round" and named no filename, so a filename-only check
          missed it.
  RULE 3  every deliverable the directive names appears in the prompt, so the prompt cannot tell the
          worker to return a differently-named artifact than the directive asked for.

It makes no judgement about content. It only asks: is what the directive asked for here?

Usage:
    fpl_directive_conformance.py --directive <d.json|response.json> --spec <spec.json> \
                                 [--prompt <prompt.md>] [--directive-id D007]

Exit 0 = conforms. Exit 1 = at least one named item is absent or contradicted. Exit 2 = malformed.

Stdlib only. No network.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

FILENAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*\.(?:json|jsonl|md|csv|xlsx|pdf|zip|txt)\b")
SHORTHAND = re.compile(r"([A-Za-z0-9_][A-Za-z0-9_.\-]*)\.(json|md|csv|jsonl)/\.(json|md|csv|jsonl)")
SIBLING = re.compile(r"\bD\d{3}\b")

# Fields whose filenames are things the PACKAGE must ship (inputs to the worker).
INPUT_FIELDS = ("context_scope", "authority", "scope_in")
# Fields whose filenames are things the WORKER returns (must be echoed in the prompt).
OUTPUT_FIELDS = ("deliverables",)

# Prose names a genuinely-renamed packaged file.
DEFAULT_ALIASES = {
    "worker_task_ledger.jsonl": [
        "worker_task_ledger_original.jsonl", "d006_worker_task_ledger.jsonl",
        "d003_worker_task_ledger.jsonl",
    ],
}


def load_directive(path: Path, directive_id: str | None) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, dict) and "directives" in doc:
        cands = doc["directives"]
        if directive_id:
            for d in cands:
                if str(d.get("id", "")).startswith(directive_id):
                    return d
            raise SystemExit(f"directive {directive_id!r} not found in {path}")
        if len(cands) != 1:
            raise SystemExit(f"{path} holds {len(cands)} directives; pass --directive-id")
        return cands[0]
    if isinstance(doc, dict) and "directive" in doc:
        return doc["directive"]
    return doc


def names_in(blob: str) -> set[str]:
    out: set[str] = set()
    for m in SHORTHAND.finditer(blob):
        out.add(f"{m.group(1)}.{m.group(2)}")
        out.add(f"{m.group(1)}.{m.group(3)}")
    for m in FILENAME.finditer(blob):
        out.add(m.group(0))
    return out


def field_blob(directive: dict, field: str) -> str:
    v = directive.get(field)
    if v is None:
        return ""
    return " ".join(str(x) for x in v) if isinstance(v, list) else str(v)


def main() -> int:
    ap = argparse.ArgumentParser(prog="fpl_directive_conformance.py")
    ap.add_argument("--directive",
                    help="The commission directive. Omit for a round that has none — a Coordinator "
                         "conductor round, for example. RULES 1-3 need a directive and are skipped "
                         "with a note; RULES 4-5 compare the package against the project's own "
                         "rulings and the installed system text, and run either way.")
    ap.add_argument("--directive-id")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--prompt")
    ap.add_argument("--rulings-dir",
                    help="A directory of operator rulings (governance/rulings). RULE 4 then requires "
                         "every ruling in it to be packaged. Raised by TERM-FPL-005, whose closure "
                         "test is 'every operator ruling by exact basename' — a package can satisfy "
                         "RULE 2 and still withhold a ruling the directive never named.")
    ap.add_argument("--system-refs",
                    help="A directory of current system documents (the installed finprodline "
                         "references). RULE 5 then requires every packaged file that also exists "
                         "there to be byte-identical to it. Raised by TERM-FPL-006 manifestation 5: "
                         "a package assembled by copying the previous package ships a superseded "
                         "protocol and tells the worker it is the contract.")
    ap.add_argument("--waive", action="append", default=[],
                    metavar="NAME=REASON",
                    help="Explicitly skip a named item. Repeatable. The reason is printed and is "
                         "part of the record. Use when the directive merely mentions a dependency "
                         "rather than requiring the file; never to silence a real omission.")
    args = ap.parse_args()

    waived: dict[str, str] = {}
    for w in args.waive:
        if "=" not in w:
            print(f"MALFORMED: --waive expects NAME=REASON, got {w!r}", file=sys.stderr)
            return 2
        k, v = w.split("=", 1)
        waived[k.strip()] = v.strip()

    dpath = Path(args.directive).resolve() if args.directive else None
    spath = Path(args.spec).resolve()
    if dpath and not dpath.is_file():
        print(f"MALFORMED: not found: {dpath}", file=sys.stderr)
        return 2
    if not spath.is_file():
        print(f"MALFORMED: not found: {spath}", file=sys.stderr)
        return 2
    try:
        directive = load_directive(dpath, args.directive_id) if dpath else {}
        spec = json.loads(spath.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"MALFORMED: {exc}", file=sys.stderr)
        return 2

    packaged = {f.get("filename", "") for f in (spec.get("input_files") or [])}
    packaged |= set(spec.get("expected_artifacts") or [])
    if spec.get("expected_main_json"):
        packaged.add(spec["expected_main_json"])
    low = {n.casefold() for n in packaged}
    low_stems = {Path(n).stem.casefold() for n in packaged}

    prompt = ""
    if args.prompt:
        pp = Path(args.prompt).resolve()
        if not pp.is_file():
            print(f"MALFORMED: prompt not found: {pp}", file=sys.stderr)
            return 2
        prompt = pp.read_text(encoding="utf-8")

    failures: list[str] = []
    notes: list[str] = []

    def resolve(name: str) -> str | None:
        """Return the packaged basename matching `name`, or None."""
        if name.casefold() in low:
            return name
        stem = Path(name).stem.casefold()
        if stem in low_stems:
            return next(n for n in packaged if Path(n).stem.casefold() == stem)
        for k, v in DEFAULT_ALIASES.items():
            if k.casefold() == name.casefold():
                hit = next((a for a in v if a.casefold() in low), None)
                if hit:
                    return hit
        for n in packaged:
            ns = Path(n).stem.casefold()
            if stem and (stem in ns or ns in stem):
                return n
        return None

    print(f"directive : {directive.get('id') or '(none — rules 1-3 skipped)'}")
    print(f"spec      : {spath}")
    print(f"packaged  : {len(packaged)} file(s)")
    print()
    if not dpath:
        notes.append("RULES 1-3 skipped: this round has no commission directive")

    # ---- RULE 1: input context must be packaged
    #
    # A name that the directive also lists as a DELIVERABLE is an output, not an input. Directives
    # routinely restate the artifact they are commissioning inside scope_in ("produce
    # rbc_fpl_layer1_audit_plan_v3.json ..."), and demanding the package ship the file it is asking
    # the worker to create is a false positive. Deliverables are RULE 3's business.
    output_names_all: set[str] = set()
    for field in OUTPUT_FIELDS:
        output_names_all |= names_in(field_blob(directive, field))

    input_names: dict[str, str] = {}
    for field in INPUT_FIELDS:
        for n in names_in(field_blob(directive, field)):
            if n in output_names_all:
                continue
            input_names.setdefault(n, field)
    print(f"RULE 1 — input context ({len(input_names)} named file(s))"
          + ("" if dpath else "  [skipped: no directive]"))
    for name, field in sorted(input_names.items()):
        hit = resolve(name)
        if hit is None:
            failures.append(f"RULE 1: {name} named by {field} is NOT packaged")
            print(f"  [MISSING] {name:<56} (named by {field})")
        elif hit.casefold() != name.casefold():
            notes.append(f"{name} shipped as {hit}")
            print(f"  [RENAMED] {name:<56} -> {hit}")
        else:
            print(f"  [ok]      {name}")

    # ---- RULE 2: referenced sibling directives must be packaged
    siblings: set[str] = set()
    for field in INPUT_FIELDS:
        siblings |= set(SIBLING.findall(field_blob(directive, field)))
    self_id = str(directive.get("id", ""))[:4]
    siblings.discard(self_id)
    print(f"\nRULE 2 — referenced sibling directives ({len(siblings)} named)"
          + ("" if dpath else "  [skipped: no directive]"))
    for sid in sorted(siblings):
        hit = next((n for n in packaged if sid in n), None)
        if hit is not None:
            print(f"  [ok]      {sid} -> {hit}")
        elif sid in waived or f"coordinator_directive_{sid}.json" in waived:
            reason = waived.get(sid) or waived[f"coordinator_directive_{sid}.json"]
            notes.append(f"WAIVED {sid}: {reason}")
            print(f"  [waived]  {sid} — {reason}")
        else:
            failures.append(f"RULE 2: sibling directive {sid} is referenced but NOT packaged. "
                            f"Ship coordinator_directive_{sid}.json, or waive it with a recorded "
                            f"reason if the directive only mentions it as a dependency.")
            print(f"  [MISSING] coordinator_directive_{sid}.json  (referenced in input context)")

    # ---- RULE 3: deliverables must be echoed by the prompt
    if not dpath:
        print("\nRULE 3 — skipped: no directive")
    elif prompt:
        out_names: dict[str, str] = {}
        for field in OUTPUT_FIELDS:
            for n in names_in(field_blob(directive, field)):
                out_names.setdefault(n, field)
        print(f"\nRULE 3 — deliverables echoed in the prompt ({len(out_names)} named)")
        for name, field in sorted(out_names.items()):
            if name in prompt:
                print(f"  [ok]      {name}")
            else:
                failures.append(f"RULE 3: deliverable {name} is named by the directive but the "
                                f"prompt never mentions it")
                print(f"  [ABSENT]  {name:<56} named by {field}, absent from the prompt")
    else:
        notes.append("RULE 3 skipped: no --prompt supplied")

    # ---- RULE 4: every operator ruling on disk must be packaged
    if args.rulings_dir:
        rdir = Path(args.rulings_dir).resolve()
        if not rdir.is_dir():
            print(f"MALFORMED: --rulings-dir not found: {rdir}", file=sys.stderr)
            return 2
        rulings = sorted(p.name for p in rdir.glob("*.json"))
        print(f"\nRULE 4 — operator rulings in {rdir.name}/ ({len(rulings)} on disk)")
        for rname in rulings:
            # The package convention renames R00N_<slug>.json to operator_ruling_R00N.json, so the
            # ruling ID, not the on-disk basename, is what must be found.
            rid = (re.match(r"(R\d{3})", rname) or [None])[0] if re.match(r"(R\d{3})", rname) else None
            hit = None
            if rid:
                hit = next((n for n in packaged if n.startswith(f"operator_ruling_{rid}")), None)
            if hit is None:
                hit = resolve(rname)
            if hit is not None:
                print(f"  [ok]      {rid or rname} -> {hit}")
            elif rname in waived or (rid and rid in waived):
                reason = waived.get(rname) or waived[rid]
                notes.append(f"WAIVED {rname}: {reason}")
                print(f"  [waived]  {rname} — {reason}")
            else:
                failures.append(f"RULE 4: operator ruling {rname} is on disk and NOT packaged. "
                                f"Relevance is never a withholding reason in audit context.")
                print(f"  [MISSING] {rname}")
    else:
        notes.append("RULE 4 skipped: no --rulings-dir supplied")

    # ---- RULE 5: packaged copies of system documents must be the CURRENT system text
    if args.system_refs:
        sdir = Path(args.system_refs).resolve()
        if not sdir.is_dir():
            print(f"MALFORMED: --system-refs not found: {sdir}", file=sys.stderr)
            return 2
        system = {}
        for p in sdir.rglob("*"):
            if p.is_file():
                system.setdefault(p.name, p)
        shared = sorted(n for n in packaged if n in system)
        print(f"\nRULE 5 — packaged system documents ({len(shared)} shared with {sdir.name}/)")
        for n in shared:
            shipped = next(f for f in (spec.get("input_files") or []) if f.get("filename") == n)
            spath = Path(shipped.get("path", ""))
            if not spath.is_file():
                continue
            a = hashlib.sha256(spath.read_bytes()).hexdigest()
            b = hashlib.sha256(system[n].read_bytes()).hexdigest()
            if a == b:
                print(f"  [ok]      {n}")
            elif n in waived:
                notes.append(f"WAIVED {n} (stale copy): {waived[n]}")
                print(f"  [waived]  {n} — {waived[n]}")
            else:
                failures.append(
                    f"RULE 5: packaged {n} is NOT the current system copy "
                    f"(packaged {a[:16]}…, system {b[:16]}…, "
                    f"{spath.stat().st_size} B vs {system[n].stat().st_size} B). The package is "
                    f"stale — rebuild it from {system[n]}.")
                print(f"  [STALE]   {n:<40} packaged {a[:12]}… != system {b[:12]}…")
    else:
        notes.append("RULE 5 skipped: no --system-refs supplied")

    print()
    for n in notes:
        print(f"  note: {n}")
    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        print("\nFix the package before running fpl_precheck. Do not rename the directive's own")
        print("deliverables to match what you happened to build.")
        return 1
    print("\nPASS — nothing the directive names is absent, and no deliverable is contradicted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
