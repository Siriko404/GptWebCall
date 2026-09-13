#!/usr/bin/env python3
"""FinProdLine generic acceptance-check evaluator.

Contract: ../skill/webcall/references/finprodline/FINPRODLINE_PROTOCOL.md §2.6 and
../skill/webcall/references/finprodline/AUDIT_PROTOCOL.md.

This program is deliberately **artifact-agnostic**. It knows check *types*. It knows nothing about
any particular artifact, project or commission. A producer worker declares the checks its own output
must pass in a `acceptance_checks.json`; Terminal runs this evaluator over that declaration and
records the raw result. Terminal never authors artifact-specific checks (§2.6).

The declaration is DATA. This program never evaluates returned code, never imports it, never execs
it, and never touches the network. Adding a check type here is a change to Terminal's trusted code,
made once and reviewed — never a per-artifact extension.

Usage:
    fpl_validate.py --spec <acceptance_checks.json> --artifacts-dir <dir> [--json <out.json>]

Exit 0 = every check passed. Exit 1 = at least one check failed. Exit 2 = malformed input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SPEC_VERSION = 1
ZERO_HASH = "0" * 64


class Malformed(Exception):
    pass


# ------------------------------------------------------------------ primitives

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def resolve_pointer(doc, pointer: str):
    """RFC 6901 JSON pointer. Returns (found, value)."""
    if pointer in ("", "/"):
        return True, doc
    if not pointer.startswith("/"):
        raise Malformed(f"json pointer must start with '/': {pointer!r}")
    cur = doc
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict):
            if token not in cur:
                return False, None
            cur = cur[token]
        elif isinstance(cur, list):
            if not token.isdigit():
                return False, None
            idx = int(token)
            if idx >= len(cur):
                return False, None
            cur = cur[idx]
        else:
            return False, None
    return True, cur


def nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def is_acyclic(nodes: dict[str, list[str]]) -> bool:
    state: dict[str, int] = {}

    def walk(n: str) -> bool:
        if state.get(n) == 1:
            return False
        if state.get(n) == 2:
            return True
        state[n] = 1
        for m in nodes.get(n, []):
            if m in nodes and not walk(m):
                return False
        state[n] = 2
        return True

    return all(walk(n) for n in list(nodes))


# ------------------------------------------------------------------ check types

PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|XXX|LOREM IPSUM|FILL IN|<placeholder>)\b", re.I)


def chk_file_present(ctx, check) -> str | None:
    path = ctx.target(check)
    if not path.is_file():
        return f"file not present: {path.name}"
    return None


def chk_file_hash(ctx, check) -> str | None:
    path = ctx.target(check)
    if not path.is_file():
        return f"file not present: {path.name}"
    actual = sha256_bytes(path.read_bytes())
    want = str(check.get("sha256", "")).casefold()
    if actual != want:
        return f"{path.name} sha256 {actual[:16]}… != declared {want[:16]}…"
    return None


def chk_file_size(ctx, check) -> str | None:
    path = ctx.target(check)
    if not path.is_file():
        return f"file not present: {path.name}"
    actual = path.stat().st_size
    want = check.get("size")
    if actual != want:
        return f"{path.name} size {actual} != declared {want}"
    return None


def chk_text_matches(ctx, check) -> str | None:
    path = ctx.target(check)
    if not path.is_file():
        return f"file not present: {path.name}"
    pattern = check.get("pattern")
    if not pattern:
        raise Malformed("text_matches requires 'pattern'")
    n = len(re.findall(pattern, path.read_text(encoding="utf-8", errors="ignore"),
                       re.I if check.get("ignore_case") else 0))
    least = int(check.get("at_least", 1))
    if n < least:
        return f"{path.name}: pattern {pattern!r} matched {n} time(s), need >= {least}"
    return None


def chk_text_absent(ctx, check) -> str | None:
    path = ctx.target(check)
    if not path.is_file():
        return f"file not present: {path.name}"
    pattern = check.get("pattern")
    if not pattern:
        raise Malformed("text_absent requires 'pattern'")
    hits = re.findall(pattern, path.read_text(encoding="utf-8", errors="ignore"),
                      re.I if check.get("ignore_case") else 0)
    if hits:
        return f"{path.name}: forbidden pattern {pattern!r} present ({len(hits)} hit(s))"
    return None


def chk_text_placeholder_free(ctx, check) -> str | None:
    path = ctx.target(check)
    if not path.is_file():
        return f"file not present: {path.name}"
    hits = sorted({m.group(0).upper() for m in PLACEHOLDER.finditer(
        path.read_text(encoding="utf-8", errors="ignore"))})
    if hits:
        return f"{path.name}: placeholder markers present: {hits}"
    return None


def chk_json_pointer_present(ctx, check) -> str | None:
    found, _ = resolve_pointer(ctx.json_(check), check["pointer"])
    if not found:
        return f"json pointer {check['pointer']} not found"
    return None


def chk_json_equals(ctx, check) -> str | None:
    found, value = resolve_pointer(ctx.json_(check), check["pointer"])
    if not found:
        return f"json pointer {check['pointer']} not found"
    if value != check.get("value"):
        return f"{check['pointer']} is {value!r}, expected {check.get('value')!r}"
    return None


def chk_json_in(ctx, check) -> str | None:
    found, value = resolve_pointer(ctx.json_(check), check["pointer"])
    if not found:
        return f"json pointer {check['pointer']} not found"
    if value not in (check.get("values") or []):
        return f"{check['pointer']} is {value!r}, not in {check.get('values')!r}"
    return None


def chk_json_type(ctx, check) -> str | None:
    found, value = resolve_pointer(ctx.json_(check), check["pointer"])
    if not found:
        return f"json pointer {check['pointer']} not found"
    want = check.get("value")
    ok = {"string": str, "integer": int, "number": (int, float), "boolean": bool,
          "list": list, "object": dict, "null": type(None)}.get(str(want))
    if ok is None:
        raise Malformed(f"json_type: unknown value {want!r}")
    if want == "integer" and isinstance(value, bool):
        return f"{check['pointer']} is a boolean, expected integer"
    if want in ("integer", "number") and isinstance(value, bool):
        return f"{check['pointer']} is a boolean, expected {want}"
    if not isinstance(value, ok):
        return f"{check['pointer']} is {type(value).__name__}, expected {want}"
    return None


def chk_json_min_items(ctx, check) -> str | None:
    found, value = resolve_pointer(ctx.json_(check), check["pointer"])
    if not found:
        return f"json pointer {check['pointer']} not found"
    if not isinstance(value, list):
        return f"{check['pointer']} is not a list"
    least = int(check.get("count", 1))
    if len(value) < least:
        return f"{check['pointer']} has {len(value)} items, need >= {least}"
    return None


def chk_json_min_length(ctx, check) -> str | None:
    found, value = resolve_pointer(ctx.json_(check), check["pointer"])
    if not found:
        return f"json pointer {check['pointer']} not found"
    if not isinstance(value, (str, list, dict)):
        return f"{check['pointer']} has no length"
    least = int(check.get("count", 1))
    if len(value) < least:
        return f"{check['pointer']} length {len(value)} < {least}"
    return None


def chk_json_pointer_regex(ctx, check) -> str | None:
    found, value = resolve_pointer(ctx.json_(check), check["pointer"])
    if not found:
        return f"json pointer {check['pointer']} not found"
    if not isinstance(value, str):
        return f"{check['pointer']} is not a string"
    if not re.search(check["pattern"], value, re.I if check.get("ignore_case") else 0):
        return f"{check['pointer']} does not match {check['pattern']!r}"
    return None


def chk_json_all_items_have(ctx, check) -> str | None:
    found, value = resolve_pointer(ctx.json_(check), check["pointer"])
    if not found:
        return f"json pointer {check['pointer']} not found"
    if not isinstance(value, list):
        return f"{check['pointer']} is not a list"
    fields = check.get("fields") or []
    min_len = int(check.get("min_length", 1))
    # Per-field minimums, e.g. {"need": 40, "boundary": 40}. A field not named here falls back to
    # `min_length`. This is what lets a producer demand substantive reasoning in long-form fields
    # while only requiring an identifier to be non-empty.
    min_lengths = {str(k): int(v) for k, v in (check.get("min_lengths") or {}).items()}
    bad = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            bad.append(f"[{i}] not an object")
            continue
        for f in fields:
            v = item.get(f)
            floor = min_lengths.get(f, min_len)
            if not nonempty(v) or (isinstance(v, str) and len(v.strip()) < floor):
                bad.append(f"[{i}].{f} empty or shorter than {floor}")
    if bad:
        return f"{check['pointer']}: " + "; ".join(bad[:6]) + (f" (+{len(bad)-6} more)" if len(bad) > 6 else "")
    return None


def chk_json_unique_by(ctx, check) -> str | None:
    found, value = resolve_pointer(ctx.json_(check), check["pointer"])
    if not found:
        return f"json pointer {check['pointer']} not found"
    if not isinstance(value, list):
        return f"{check['pointer']} is not a list"
    key = check["key"]
    seen, dupes = set(), []
    for item in value:
        v = item.get(key) if isinstance(item, dict) else None
        if v in seen:
            dupes.append(v)
        seen.add(v)
    if dupes:
        return f"{check['pointer']}: duplicate {key} values {sorted(map(str, dupes))}"
    return None


def chk_json_array_covers(ctx, check) -> str | None:
    found, value = resolve_pointer(ctx.json_(check), check["pointer"])
    if not found:
        return f"json pointer {check['pointer']} not found"
    if not isinstance(value, list):
        return f"{check['pointer']} is not a list"
    key = check["key"]
    if check.get("explode"):
        present = set()
        for item in value:
            if isinstance(item, dict):
                for v in (item.get(key) or []):
                    present.add(str(v))
    else:
        present = {str(item.get(key)) for item in value if isinstance(item, dict)}
    missing = [r for r in (check.get("required") or []) if str(r) not in present]
    if missing:
        return f"{check['pointer']}: missing required {key} values {missing[:8]}"
    return None


def chk_json_dependencies_resolve(ctx, check) -> str | None:
    found, value = resolve_pointer(ctx.json_(check), check["pointer"])
    if not found:
        return f"json pointer {check['pointer']} not found"
    if not isinstance(value, list):
        return f"{check['pointer']} is not a list"
    id_key = check.get("id_key", "id")
    deps_key = check.get("dependencies_key", "depends_on")
    ids = {str(i.get(id_key)) for i in value if isinstance(i, dict)}
    bad = [f"{i.get(id_key)}->{d}" for i in value if isinstance(i, dict)
           for d in (i.get(deps_key) or []) if str(d) not in ids]
    if bad:
        return f"{check['pointer']}: unresolved dependencies {bad[:8]}"
    return None


def chk_json_graph_acyclic(ctx, check) -> str | None:
    found, value = resolve_pointer(ctx.json_(check), check["pointer"])
    if not found:
        return f"json pointer {check['pointer']} not found"
    if not isinstance(value, list):
        return f"{check['pointer']} is not a list"
    id_key = check.get("id_key", "id")
    deps_key = check.get("dependencies_key", "depends_on")
    nodes = {str(i.get(id_key)): [str(d) for d in (i.get(deps_key) or [])]
             for i in value if isinstance(i, dict)}
    if not is_acyclic(nodes):
        return f"{check['pointer']}: dependency graph is cyclic"
    return None


def chk_jsonl_hash_chain(ctx, check) -> str | None:
    path = ctx.target(check)
    if not path.is_file():
        return f"file not present: {path.name}"
    seq_f = check.get("seq_field", "seq")
    prev_f = check.get("prev_hash_field", "prev_event_hash")
    hash_f = check.get("hash_field", "event_hash")
    # STATE_PROTOCOL.md 2.2: event_hash is the sha256 of the event object with event_hash removed
    # AND with event_id removed — event_id is derived from event_hash and is computed last, so it is
    # not itself hashed. Omitting event_id here would fail every valid FinProdLine ledger.
    exclude = {hash_f, *check.get("exclude_fields", ["event_id"])}
    vocab = check.get("vocabulary")
    actor = check.get("actor_pattern")
    first = check.get("first_event")
    last = check.get("last_event")

    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return f"{path.name} is empty"
    prev = check.get("zero_hash", ZERO_HASH)
    problems = []
    for i, line in enumerate(lines, 1):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"line {i}: not JSON ({exc})")
            continue
        if ev.get(seq_f) != i:
            problems.append(f"line {i}: {seq_f} is {ev.get(seq_f)}")
        if ev.get(prev_f) != prev:
            problems.append(f"line {i}: {prev_f} chain broken")
        body = {k: v for k, v in ev.items() if k not in exclude}
        actual = sha256_bytes(canonical(body))
        if actual != ev.get(hash_f):
            problems.append(f"line {i}: {hash_f} does not recompute")
        prev = ev.get(hash_f, prev)
        if vocab is not None and ev.get("event_type") not in vocab:
            problems.append(f"line {i}: event_type {ev.get('event_type')!r} not in declared vocabulary")
        if actor and not re.match(actor, str(ev.get("actor", ""))):
            problems.append(f"line {i}: actor {ev.get('actor')!r} fails {actor!r}")
    if first and json.loads(lines[0]).get("event_type") != first:
        problems.append(f"first event is not {first!r}")
    if last and json.loads(lines[-1]).get("event_type") != last:
        problems.append(f"last event is not {last!r}")
    if problems:
        return f"{path.name}: " + "; ".join(problems[:6]) + (f" (+{len(problems)-6} more)" if len(problems) > 6 else "")
    return None


def chk_numeric_close(ctx, check) -> str | None:
    found, value = resolve_pointer(ctx.json_(check), check["pointer"])
    if not found:
        return f"json pointer {check['pointer']} not found"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"{check['pointer']} is not numeric"
    want = float(check["value"])
    tol = float(check.get("tolerance", 0.0))
    if abs(float(value) - want) > tol:
        return f"{check['pointer']} is {value}, expected {want} +/- {tol}"
    return None


CHECKS = {
    "file_present": chk_file_present,
    "file_hash": chk_file_hash,
    "file_size": chk_file_size,
    "text_matches": chk_text_matches,
    "text_absent": chk_text_absent,
    "text_placeholder_free": chk_text_placeholder_free,
    "json_pointer_present": chk_json_pointer_present,
    "json_equals": chk_json_equals,
    "json_in": chk_json_in,
    "json_type": chk_json_type,
    "json_min_items": chk_json_min_items,
    "json_min_length": chk_json_min_length,
    "json_pointer_regex": chk_json_pointer_regex,
    "json_all_items_have": chk_json_all_items_have,
    "json_unique_by": chk_json_unique_by,
    "json_array_covers": chk_json_array_covers,
    "json_dependencies_resolve": chk_json_dependencies_resolve,
    "json_graph_acyclic": chk_json_graph_acyclic,
    "jsonl_hash_chain": chk_jsonl_hash_chain,
    "numeric_close": chk_numeric_close,
}


class Context:
    """Resolves a check's `target` to a path inside the artifacts directory."""

    def __init__(self, artifacts: Path):
        self.artifacts = artifacts
        self._json: dict[str, object] = {}

    def target(self, check) -> Path:
        name = check.get("target")
        if not name:
            raise Malformed(f"check {check.get('check_id')!r} has no 'target'")
        if "/" in name or "\\" in name:
            raise Malformed(f"target must be a plain basename: {name!r}")
        return self.artifacts / name

    def json_(self, check):
        name = check.get("target")
        if not name:
            raise Malformed(f"check {check.get('check_id')!r} has no 'target'")
        if name not in self._json:
            path = self.target(check)
            if not path.is_file():
                raise Malformed(f"target file not present: {path}")
            try:
                self._json[name] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise Malformed(f"{name} is not valid JSON: {exc}") from exc
        return self._json[name]


# ------------------------------------------------------------------ driver

def main() -> int:
    ap = argparse.ArgumentParser(prog="fpl_validate.py")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--artifacts-dir", required=True)
    ap.add_argument("--json")
    args = ap.parse_args()

    spec_path = Path(args.spec).resolve()
    if not spec_path.is_file():
        print(f"MALFORMED: spec not found: {spec_path}", file=sys.stderr)
        return 2
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"MALFORMED: spec is not valid JSON: {exc}", file=sys.stderr)
        return 2

    artifacts = Path(args.artifacts_dir).resolve()
    if not artifacts.is_dir():
        print(f"MALFORMED: artifacts dir not found: {artifacts}", file=sys.stderr)
        return 2

    try:
        if spec.get("spec_version") != SPEC_VERSION:
            raise Malformed(f"spec_version must be {SPEC_VERSION}")
        checks = spec.get("checks")
        if not isinstance(checks, list) or not checks:
            raise Malformed("spec must declare a non-empty 'checks' list")

        # ---- coverage model -------------------------------------------------
        # A criterion may be declared and deliberately NOT mechanically proved. The earlier
        # contract had only one relation (`proves`), which forced a producer to claim mechanical
        # proof of criteria that cannot have any — so an honest producer had to omit `criteria`
        # entirely, which disabled this guard. Disposition makes the honest answer expressible.
        criteria = [c for c in (spec.get("criteria") or []) if isinstance(c, dict)]
        cids = [c.get("criterion_id") for c in criteria]
        cset = set(cids)
        if len(cset) != len(cids):
            raise Malformed("duplicate criterion_id values in 'criteria'")

        proves_used = {p for c in checks for p in (c.get("proves") or [])}
        if proves_used and not criteria:
            raise Malformed(
                "checks use 'proves' but no 'criteria' are declared, so coverage cannot be "
                "verified. Declare every criterion, marking the ones no mechanical check can "
                "establish as disposition 'semantic_only' with a reason.")

        unknown = sorted(proves_used - cset)
        if unknown:
            raise Malformed(f"checks prove undeclared criteria: {unknown}")

        by_id = {}
        for c in criteria:
            cid = c.get("criterion_id")
            disp = c.get("disposition", "mechanical")
            if disp not in ("mechanical", "partial", "semantic_only"):
                raise Malformed(f"criterion {cid!r}: disposition must be mechanical, partial or "
                                f"semantic_only, got {disp!r}")
            by_id[cid] = c

        for cid, c in by_id.items():
            disp = c.get("disposition", "mechanical")
            proved = cid in proves_used
            if disp == "semantic_only":
                if proved:
                    raise Malformed(
                        f"criterion {cid!r} is disposition 'semantic_only' but a check claims to "
                        f"prove it. Either it is partially provable (use 'partial') or the check is "
                        f"overclaiming.")
                if not str(c.get("reason", "")).strip():
                    raise Malformed(f"criterion {cid!r} is 'semantic_only' and must state a reason")
            elif not proved:
                raise Malformed(
                    f"criterion {cid!r} has disposition {disp!r} but no check proves it. A "
                    f"criterion no mechanical check can establish must be declared "
                    f"'semantic_only' with a reason, not left silently uncovered.")
    except Malformed as exc:
        print(f"MALFORMED: {exc}", file=sys.stderr)
        return 2

    ctx = Context(artifacts)
    results = []
    malformed = None
    for check in checks:
        cid = check.get("check_id") or "<no check_id>"
        ctype = check.get("type")
        fn = CHECKS.get(str(ctype))
        if fn is None:
            malformed = f"check {cid}: unknown check type {ctype!r}"
            break
        try:
            failure = fn(ctx, check)
        except Malformed as exc:
            malformed = f"check {cid}: {exc}"
            break
        except (KeyError, TypeError) as exc:
            malformed = f"check {cid}: malformed ({exc!r})"
            break
        results.append({
            "check_id": cid,
            "type": ctype,
            "proves": check.get("proves") or [],
            "target": check.get("target"),
            "status": "FAIL" if failure else "PASS",
            "detail": failure or "ok",
        })

    if malformed:
        print(f"MALFORMED: {malformed}", file=sys.stderr)
        if args.json:
            Path(args.json).write_text(json.dumps(
                {"spec": str(spec_path), "malformed": malformed}, indent=2) + "\n", encoding="utf-8")
        return 2

    n_fail = sum(1 for x in results if x["status"] == "FAIL")
    summary = {
        "spec": str(spec_path),
        "request_id": spec.get("request_id"),
        "produced_by_worker": spec.get("produced_by_worker"),
        "artifacts_dir": str(artifacts),
        "checks_total": len(results),
        "checks_pass": len(results) - n_fail,
        "checks_fail": n_fail,
        "verdict": "PASS" if n_fail == 0 else "FAIL",
        "results": results,
    }

    print(f"acceptance checks — {spec.get('request_id')}")
    print(f"declared by: {spec.get('produced_by_worker')}")
    print(f"spec       : {spec_path}")
    print(f"artifacts  : {artifacts}")
    print()
    for x in results:
        print(f"  [{x['status']:<4}] {x['check_id']:<16} {x['type']:<26} {x['detail']}")
    print()
    print(f"checks: {len(results)} | pass: {len(results)-n_fail} | fail: {n_fail}")
    print(f"VERDICT: {summary['verdict']}")

    if args.json:
        Path(args.json).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
