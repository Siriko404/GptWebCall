#!/usr/bin/env python3
"""FinProdLine state surface.

Append-only JSONL streams, rebuildable indexes, deterministic commands.
Contract: ../../skill/webcall/references/finprodline/STATE_PROTOCOL.md

Every command emits exactly one JSON object on stdout (exit 0) or stderr (exit 2), matching the
installed Web Call CLI so one session reads both the same way.

Stdlib only. No network. Never writes outside the project root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MARKER = ".finprodline"
SCHEMA_VERSION = 1
ZERO_HASH = "0" * 64

STREAMS = {
    "project": [
        "goal_set", "operator_ruling_recorded", "plan_proposed", "plan_accepted",
        "plan_superseded", "phase_opened", "gate_state_changed", "finding_promoted",
        "finding_closed", "conclusion_accepted", "open_item_raised", "open_item_settled",
        "scope_changed", "earn_keep_cut_recorded", "final_decision",
    ],
    "run": [
        "session_started", "project_initialized", "marker_verified", "coordinator_bootstrapped",
        "directive_received", "directive_rejected_malformed", "package_precheck_result",
        "upload_approval_recorded", "exchange_prepared", "exchange_armed",
        "exchange_event_received", "delivery_validated", "semantic_acceptance_recorded",
        "artifact_persisted", "reconciliation_result", "plan_binding_recorded", "index_rebuilt",
        "supersession_linked", "anomaly_recorded", "recovery_event",
    ],
    "worker": [
        "task_started", "input_pinned", "step_performed", "finding_recorded", "output_produced",
        "issue_open", "issue_closed", "task_finished",
    ],
}

ENVELOPE = (
    "schema_version", "seq", "event_id", "timestamp", "actor", "event_type", "subject_id",
    "phase_id", "gate", "payload", "evidence_refs", "supersedes", "prev_event_hash", "event_hash",
)

GATES = ("METHOD", "DATA", "EXECUTION")
ACTORS = re.compile(r"^(coordinator|terminal|operator|worker:[A-Za-z0-9._:-]+)$")


class Failure(Exception):
    pass


# ------------------------------------------------------------------ primitives

def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def emit(command: str, result) -> int:
    print(json.dumps({"ok": True, "command": command, "result": result}, indent=2))
    return 0


def die(command: str, error: str) -> int:
    print(json.dumps({"ok": False, "command": command, "error": error}, indent=2), file=sys.stderr)
    return 2


# ------------------------------------------------------------------ project

def find_project(start: Path) -> Path | None:
    """Walk the directory and its parents for a valid marker. Never siblings, never whole disk."""
    cur = start.resolve()
    for candidate in [cur, *cur.parents]:
        marker = candidate / MARKER
        if (marker / "project.json").is_file():
            return candidate
    return None


def project_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).resolve()
        if not (root / MARKER / "project.json").is_file():
            raise Failure(f"no FinProdLine marker at {root}")
        return root
    found = find_project(Path.cwd())
    if found is None:
        raise Failure("no FinProdLine project marker in this directory or any parent")
    return found


def load_config(root: Path) -> dict:
    return json.loads((root / MARKER / "project.json").read_text(encoding="utf-8"))


def save_config(root: Path, cfg: dict) -> None:
    tmp = root / MARKER / "project.json.tmp"
    tmp.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, root / MARKER / "project.json")


def stream_path(root: Path, stream: str) -> Path:
    if stream == "project":
        return root / MARKER / "streams" / "project.jsonl"
    if stream == "run":
        return root / MARKER / "streams" / "run.jsonl"
    if stream.startswith("worker:"):
        wid = stream.split(":", 1)[1]
        if not re.fullmatch(r"[A-Za-z0-9._:-]+", wid):
            raise Failure(f"unsafe worker id: {wid!r}")
        return root / MARKER / "streams" / "workers" / f"{wid}.jsonl"
    raise Failure(f"unknown stream: {stream!r}")


def read_stream(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    events = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise Failure(f"{path}:{lineno}: not valid JSON: {exc}")
    return events


def stream_kind(stream: str) -> str:
    return "worker" if stream.startswith("worker:") else stream


# ------------------------------------------------------------------ append

def append_event(root: Path, stream: str, event: dict) -> dict:
    kind = stream_kind(stream)
    path = stream_path(root, stream)
    path.parent.mkdir(parents=True, exist_ok=True)

    cfg = load_config(root)
    vocab = set(STREAMS[kind]) | set(cfg.get("event_vocabulary_extensions", {}))

    etype = event.get("event_type")
    if etype not in vocab:
        raise Failure(f"event_type {etype!r} is not in the {kind} vocabulary")

    actor = event.get("actor", "")
    if not ACTORS.match(str(actor)):
        raise Failure(f"actor must be coordinator|terminal|operator|worker:<id>, got {actor!r}")
    if kind == "worker" and not str(actor).startswith("worker:"):
        raise Failure("a worker stream accepts only worker:<id> actors")

    gate = event.get("gate")
    if gate is not None and gate not in GATES:
        raise Failure(f"gate must be one of {GATES} or null, got {gate!r}")

    if "event_id" in event or "event_hash" in event or "seq" in event or "prev_event_hash" in event:
        raise Failure("seq, event_id, prev_event_hash and event_hash are computed, never supplied")

    prior = read_stream(path)
    seq = len(prior) + 1
    prev_hash = prior[-1]["event_hash"] if prior else ZERO_HASH

    body = {
        "schema_version": SCHEMA_VERSION,
        "seq": seq,
        "timestamp": event.get("timestamp") or now_rfc3339(),
        "actor": actor,
        "event_type": etype,
        "subject_id": event.get("subject_id", "project"),
        "phase_id": event.get("phase_id"),
        "gate": gate,
        "payload": event.get("payload", {}),
        "evidence_refs": event.get("evidence_refs", []),
        "supersedes": event.get("supersedes", []),
        "prev_event_hash": prev_hash,
    }
    event_hash = sha256_hex(canonical(body))
    body["event_hash"] = event_hash
    body["event_id"] = f"{kind}-{seq:06d}-{event_hash[:8]}"
    ordered = {k: body[k] for k in ENVELOPE}

    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ordered, ensure_ascii=False, sort_keys=True) + "\n")
    return ordered


# ------------------------------------------------------------------ verify

def integrity_path(root: Path) -> Path:
    return root / MARKER / "integrity.json"


def read_integrity(root: Path) -> dict:
    p = integrity_path(root)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("anchors", {})
    except json.JSONDecodeError:
        return {}


def verify_ledgers(root: Path, anchor: dict | None = None) -> dict:
    """Chain verification plus tail anchoring.

    A hash chain alone proves the events present are unmodified and internally consistent. It
    cannot see a removed tail: truncating a stream leaves a still-valid shorter chain. That is
    what the anchor in integrity.json is for — it records the event count and tail hash at the
    last recorded verification. A stream that is now shorter, or the same length with a different
    tail, was tampered with after that point.

    The honest limit: tampering *before* the last recorded verification is not detectable by this
    mechanism. Anchoring is therefore worth recording often, and `verify-ledgers --record` does so.
    """
    cfg = load_config(root)
    anchor = anchor or {}
    reports = []
    seen_ids: dict[str, str] = {}
    pending_supersedes: list[tuple[str, str, str]] = []

    paths = [("project", root / MARKER / "streams" / "project.jsonl"),
             ("run", root / MARKER / "streams" / "run.jsonl")]
    wdir = root / MARKER / "streams" / "workers"
    if wdir.is_dir():
        paths += [(f"worker:{p.stem}", p) for p in sorted(wdir.glob("*.jsonl"))]

    ok_all = True
    for kind, path in paths:
        kind_name = kind.split(":", 1)[0] if kind.startswith("worker:") else kind
        vocab = set(STREAMS[kind_name]) | set(cfg.get("event_vocabulary_extensions", {}))
        events = read_stream(path)
        problems = []
        prev = ZERO_HASH
        for i, ev in enumerate(events, 1):
            missing = [k for k in ENVELOPE if k not in ev]
            if missing:
                problems.append(f"seq {i}: missing envelope fields {missing}")
                ok_all = False
                continue
            if ev["seq"] != i:
                problems.append(f"line {i}: seq is {ev['seq']}, expected {i}")
                ok_all = False
            if ev["prev_event_hash"] != prev:
                problems.append(f"seq {i}: prev_event_hash does not chain")
                ok_all = False
            # event_id is derived from event_hash, so — like event_hash itself — it is not part of
            # the hashed content. Both are excluded when recomputing.
            body = {k: v for k, v in ev.items() if k not in ("event_hash", "event_id")}
            if sha256_hex(canonical(body)) != ev["event_hash"]:
                problems.append(f"seq {i}: event_hash does not match its content")
                ok_all = False
            if ev["event_type"] not in vocab:
                problems.append(f"seq {i}: unknown event_type {ev['event_type']!r}")
                ok_all = False
            if ev["event_id"] in seen_ids:
                problems.append(f"seq {i}: duplicate event_id {ev['event_id']}")
                ok_all = False
            seen_ids[ev["event_id"]] = kind
            for target in ev.get("supersedes", []):
                pending_supersedes.append((target, ev["event_id"], kind))
            prev = ev["event_hash"]
        notes = []
        recorded = anchor.get(kind)
        if recorded:
            if len(events) < recorded.get("events", 0):
                problems.append(
                    f"TRUNCATED: stream holds {len(events)} events but {recorded['events']} were "
                    f"recorded as verified — events were removed")
                ok_all = False
            elif len(events) == recorded.get("events", -1) and prev != recorded.get("tail_hash"):
                problems.append("REWRITTEN: same event count as the last recorded verification but "
                                "a different tail hash")
                ok_all = False
            elif len(events) > recorded.get("events", 0):
                notes.append(f"stream extended since the last recorded verification "
                             f"({recorded['events']} -> {len(events)})")
        else:
            notes.append("no recorded anchor: truncation before the first verification is not "
                         "detectable")

        reports.append({"stream": kind, "events": len(events), "tail_hash": prev,
                        "problems": problems, "notes": notes})

    unresolved = []
    for target, source, kind in pending_supersedes:
        if target not in seen_ids:
            unresolved.append(f"{source} supersedes unknown event {target}")
            ok_all = False

    return {"ok": ok_all, "streams": reports, "dangling_supersedes": unresolved}


# ------------------------------------------------------------------ views

def _latest(events, etype, key=None, value=None):
    hits = [e for e in events if e["event_type"] == etype]
    if key is not None:
        hits = [e for e in hits if e["payload"].get(key) == value]
    return hits[-1] if hits else None


def build_view(root: Path, name: str, selectors: dict) -> dict:
    project = read_stream(root / MARKER / "streams" / "project.jsonl")
    run = read_stream(root / MARKER / "streams" / "run.jsonl")
    cfg = load_config(root)

    if name == "project-current":
        goal = _latest(project, "goal_set")
        opened = {e["payload"].get("phase_id") for e in project if e["event_type"] == "phase_opened"}
        closed = {e["payload"].get("phase_id") for e in project
                  if e["event_type"] in ("gate_state_changed", "final_decision")
                  and e["payload"].get("phase_closed")}
        accepted = [e["payload"] for e in project if e["event_type"] == "plan_accepted"]
        superseded = {s for e in project if e["event_type"] == "plan_superseded"
                      for s in e["payload"].get("supersedes_plan_ids", [])}
        return {
            "goal": goal["payload"].get("goal") if goal else cfg.get("goal"),
            "active_phases": sorted(opened - closed),
            "gate": project[-1]["gate"] if project else None,
            "accepted_plans": [p for p in accepted if p.get("plan_id") not in superseded],
            "operator_locks": [e["payload"] for e in project
                               if e["event_type"] == "operator_ruling_recorded"],
        }

    if name == "open-items":
        # The item id may live in the payload OR in the envelope's subject_id. Keying on
        # payload["item_id"] alone silently collapsed every event to a None key, so an
        # open_item_raised followed by an unrelated open_item_settled produced an EMPTY view while
        # the append-only stream still showed the item open. That is exactly the index/stream
        # contradiction STATE_PROTOCOL 4 forbids, and an independent Layer-1 auditor found it as
        # UA3-C02-STATE-001 / UA3-C08-STATE-001 before anyone else did.
        def _key(e: dict, field: str):
            return e["payload"].get(field) or e.get("subject_id")

        raised = {_key(e, "item_id"): e["payload"] for e in project
                  if e["event_type"] == "open_item_raised"}
        settled = {_key(e, "item_id") for e in project
                   if e["event_type"] == "open_item_settled"}
        promoted = {_key(e, "finding_id"): e["payload"] for e in project
                    if e["event_type"] == "finding_promoted"}
        closed_f = {_key(e, "finding_id") for e in project
                    if e["event_type"] == "finding_closed"}
        return {
            "open_questions": [dict(v, item_id=k) for k, v in raised.items() if k not in settled],
            "open_findings": [dict(v, finding_id=k) for k, v in promoted.items()
                              if k not in closed_f],
        }

    if name == "plan-current":
        accepted = [e["payload"] for e in project if e["event_type"] == "plan_accepted"]
        superseded = {s for e in project if e["event_type"] == "plan_superseded"
                      for s in e["payload"].get("supersedes_plan_ids", [])}
        live = [p for p in accepted if p.get("plan_id") not in superseded]
        return {
            "layer1": [p for p in live if p.get("layer") == 1],
            "phase_plans": [p for p in live if p.get("layer") in (2, 3)],
        }

    if name == "artifact-index":
        arts = [e["payload"] for e in run if e["event_type"] == "artifact_persisted"]
        return {"artifacts": arts,
                "by_hash": {a.get("sha256"): a.get("artifact_id") for a in arts if a.get("sha256")}}

    if name == "lineage":
        arts = {e["payload"].get("artifact_id"): e["payload"] for e in run
                if e["event_type"] == "artifact_persisted"}
        edges = []
        for aid, a in arts.items():
            for parent in a.get("lineage", {}).get("from", []) or []:
                edges.append({"from": parent, "to": aid,
                              "transformation": a.get("lineage", {}).get("transformation")})
        return {"nodes": sorted(k for k in arts if k), "edges": edges}

    if name == "calls-current":
        # A prepared call that is later deleted must not keep presenting as current. The view used
        # to list every exchange ever prepared, so a deleted fleet still showed up as live and a
        # Layer-1 auditor raised it as UA1-CH01-F003 / UA1-CH08-F002.
        TERMINAL = {"COMPLETE", "INCOMPLETE", "STOPPED", "DELETED"}
        out = {}
        for e in run:
            if e["event_type"] in ("exchange_prepared", "exchange_armed", "delivery_validated",
                                   "exchange_event_received", "upload_approval_recorded",
                                   "semantic_acceptance_recorded"):
                xid = e["payload"].get("exchange_id")
                if not xid:
                    continue
                out.setdefault(xid, {"exchange_id": xid, "events": []})
                out[xid]["events"].append({"event_type": e["event_type"], "seq": e["seq"],
                                           "payload": e["payload"]})
        exchanges = []
        for xid, rec in out.items():
            kinds = {ev["event_type"] for ev in rec["events"]}
            state = None
            for ev in rec["events"]:
                if ev["event_type"] == "exchange_event_received":
                    state = ev["payload"].get("event") or ev["payload"].get("state") or state
            if state is None:
                # Older exchanges predate the exchange_event_received record. Fall back to the
                # strongest evidence they do carry, so a completed call is not shown as still live.
                if "delivery_validated" in kinds:
                    state = "COMPLETE"
                elif "semantic_acceptance_recorded" in kinds:
                    state = "COMPLETE"
                elif "exchange_armed" in kinds:
                    state = "PREPARED"
            rec["state"] = state or "PREPARED"
            rec["current"] = rec["state"] not in TERMINAL
            exchanges.append(rec)
        return {"exchanges": exchanges,
                "current_exchanges": [r for r in exchanges if r["current"]],
                "note": "An exchange whose latest recorded state is COMPLETE, INCOMPLETE, STOPPED or "
                        "DELETED is retained as history and marked current=false. Only current "
                        "exchanges are live routing obligations."}

    if name == "worker-history":
        wid = selectors.get("id")
        if not wid:
            raise Failure("worker-history requires --select id=<worker-id>")
        events = read_stream(stream_path(root, f"worker:{wid}"))
        return {"worker_id": wid, "task_ledger": events}

    if name == "audit-current":
        keep = ("package_precheck_result", "delivery_validated", "semantic_acceptance_recorded")
        audits = [e for e in project if e["event_type"] in ("finding_promoted", "finding_closed")]
        return {"audit_events": audits,
                "run_context": [e for e in run if e["event_type"] in keep]}

    if name == "handbook-current":
        covered = [e["payload"] for e in project
                   if e["event_type"] == "conclusion_accepted"
                   and e["payload"].get("kind") == "handbook_coverage"]
        return {"handbook_coverage": covered}

    if name == "audit-ledger-export":
        return {"streams": {"project": project, "run": run},
                "tails": {"project": project[-1]["event_hash"] if project else ZERO_HASH,
                          "run": run[-1]["event_hash"] if run else ZERO_HASH}}

    raise Failure(f"unknown view: {name!r}")


INDEX_NAMES = (
    "project-current", "open-items", "plan-current", "artifact-index", "lineage",
    "calls-current", "worker-history", "audit-current", "handbook-current", "audit-ledger-export",
)


def rebuild_index(root: Path, name: str, selectors: dict | None = None) -> dict:
    if name not in INDEX_NAMES:
        raise Failure(f"unknown index: {name!r}")
    view = build_view(root, name, selectors or {})
    project = read_stream(root / MARKER / "streams" / "project.jsonl")
    run = read_stream(root / MARKER / "streams" / "run.jsonl")
    idx_dir = root / MARKER / "indexes"
    idx_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "index": name,
        "built_at": now_rfc3339(),
        "source_tails": {
            "project": project[-1]["event_hash"] if project else ZERO_HASH,
            "run": run[-1]["event_hash"] if run else ZERO_HASH,
        },
        "view": view,
    }
    path = idx_dir / f"{name}.json"
    tmp = idx_dir / f"{name}.json.tmp"
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return {"index": name, "path": str(path), "source_tails": record["source_tails"]}


def verify_indexes(root: Path) -> dict:
    project = read_stream(root / MARKER / "streams" / "project.jsonl")
    run = read_stream(root / MARKER / "streams" / "run.jsonl")
    current = {"project": project[-1]["event_hash"] if project else ZERO_HASH,
               "run": run[-1]["event_hash"] if run else ZERO_HASH}
    idx_dir = root / MARKER / "indexes"
    stale, checked = [], 0
    if idx_dir.is_dir():
        for path in sorted(idx_dir.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            checked += 1
            if record.get("source_tails") != current:
                stale.append({"index": record.get("index"), "reason": "source tails moved"})
    return {"ok": not stale, "checked": checked, "stale": stale, "current_tails": current}


# ------------------------------------------------------------------ commands

def cmd_discover(args) -> int:
    start = Path(args.start or Path.cwd()).resolve()
    found = find_project(start)
    if found is None:
        return emit("discover", {"found": False, "start": str(start),
                                 "searched": [str(start), *[str(p) for p in start.parents]]})
    cfg = load_config(found)
    return emit("discover", {"found": True, "root": str(found), "config": cfg})


def cmd_init(args) -> int:
    root = Path(args.root).resolve()
    marker = root / MARKER
    if (marker / "project.json").is_file():
        raise Failure(f"a FinProdLine project already exists at {root}")
    if args.canon_mode not in ("supplied", "researched", "hybrid"):
        raise Failure("--canon-mode must be supplied, researched or hybrid")
    if args.audit_replicas < 1:
        raise Failure("--audit-replicas must be at least 1")

    root.mkdir(parents=True, exist_ok=True)
    (marker / "streams" / "workers").mkdir(parents=True, exist_ok=True)
    (marker / "indexes").mkdir(parents=True, exist_ok=True)
    for sub in ("governance", "plans", "evidence", "artifacts", "work/calls"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    cfg = {
        "schema_version": SCHEMA_VERSION,
        "project_id": re.sub(r"[^a-z0-9]+", "-", root.name.casefold()).strip("-") or "project",
        "root": str(root),
        "created_at": now_rfc3339(),
        "goal": args.goal,
        "canon_mode": args.canon_mode,
        "audit_replicas": args.audit_replicas,
        "handbook_learner": args.handbook_learner or "absolute beginner from zero",
        "handbook_audience_testing": "not_required",
        "release_artifacts": json.loads(args.release_override) if args.release_override
                             else {"data": "csv", "workbook": "xlsx", "engine": "python"},
        "restrictions": [],
        "privacy_lock": None,
        "event_vocabulary_extensions": {},
        "audit_budget_cap": None,
    }
    save_config(root, cfg)
    append_event(root, "project", {"actor": "operator", "event_type": "goal_set",
                                   "subject_id": "project",
                                   "payload": {"goal": args.goal}})
    append_event(root, "run", {"actor": "terminal", "event_type": "project_initialized",
                               "subject_id": "project",
                               "payload": {"root": str(root), "config": cfg}})
    return emit("init", {"root": str(root), "config": cfg})


def cmd_get(args) -> int:
    root = project_root(args.project)
    selectors = {}
    for item in args.select or []:
        if "=" not in item:
            raise Failure(f"--select expects key=value, got {item!r}")
        k, v = item.split("=", 1)
        selectors[k] = v
    view = build_view(root, args.view, selectors)
    rebuild_index(root, args.view, selectors)
    return emit("get", {"view": args.view, "selectors": selectors, "result": view})


def cmd_append(args) -> int:
    root = project_root(args.project)
    raw = sys.stdin.read() if args.event == "-" else Path(args.event).read_text(encoding="utf-8")
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Failure(f"event is not valid JSON: {exc}")
    written = append_event(root, args.stream, event)
    return emit("append", {"stream": args.stream, "event": written})


def cmd_worker(args) -> int:
    root = project_root(args.project)
    events = read_stream(stream_path(root, f"worker:{args.id}"))
    return emit("worker", {"worker_id": args.id, "events": len(events), "task_ledger": events})


SELECTOR_INDEXES = ("worker-history",)


def cmd_rebuild_index(args) -> int:
    root = project_root(args.project)
    if args.name == "all":
        names = [n for n in INDEX_NAMES if n not in SELECTOR_INDEXES]
        skipped = list(SELECTOR_INDEXES)
    else:
        names, skipped = (args.name,), []
    out = [rebuild_index(root, n) for n in names]
    return emit("rebuild-index", {"rebuilt": out, "skipped_needs_selector": skipped})


def cmd_verify_ledgers(args) -> int:
    """Read-only unless --record.

    Plain verification never writes: an integrity check that mutates state as a side effect of
    checking would move the stream tails and invalidate every index. `--record` is the deliberate
    act that appends the verification to the run stream and moves the anchor forward.
    """
    root = project_root(args.project)
    report = verify_ledgers(root, read_integrity(root))

    if getattr(args, "record", False):
        if not report["ok"]:
            return emit("verify-ledgers", {**report, "recorded": False,
                                           "reason": "not recorded: verification failed"})
        append_event(root, "run", {
            "actor": "terminal", "event_type": "marker_verified", "subject_id": "project",
            "payload": {"streams": {s["stream"]: {"events": s["events"], "tail_hash": s["tail_hash"]}
                                    for s in report["streams"]}},
        })
        # recompute after the append so the anchor includes the verification event itself
        report = verify_ledgers(root, read_integrity(root))
        anchors = {s["stream"]: {"events": s["events"], "tail_hash": s["tail_hash"]}
                   for s in report["streams"]}
        tmp = integrity_path(root).with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"anchors": anchors, "recorded_at": now_rfc3339()},
                                  indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, integrity_path(root))
        return emit("verify-ledgers", {**report, "recorded": True, "anchors": anchors})

    return emit("verify-ledgers", {**report, "recorded": False})


def cmd_verify_indexes(args) -> int:
    root = project_root(args.project)
    return emit("verify-indexes", verify_indexes(root))


def cmd_export_audit(args) -> int:
    """A complete, chunkable projection for ledger audits.

    AUDIT_PROTOCOL.md 9 requires the projection to carry more than the events and the tails: it needs
    the event sequence ranges, hash-chain proof, INDEX SOURCE TAIL IDENTITIES, referenced artifact
    identities, supersession links, and orphan and missing-reference checks. The first Layer-1
    auditor found the earlier, thinner projection and raised UA3-C08-PROJECTION-001 against it. This
    emits the full set.
    """
    root = project_root(args.project)
    export = build_view(root, "audit-ledger-export", {})
    chunks = max(1, args.chunk)
    all_events = [(s, e) for s, evs in export["streams"].items() for e in evs]
    size = max(1, (len(all_events) + chunks - 1) // chunks)
    packages = []
    for i in range(chunks):
        window = all_events[i * size:(i + 1) * size]
        by_stream: dict[str, list[int]] = {}
        for s, e in window:
            by_stream.setdefault(s, []).append(e.get("seq"))
        packages.append({
            "chunk": i + 1,
            "event_count": len(window),
            "sequence_ranges": {s: [min(q), max(q)] for s, q in by_stream.items() if q},
            "events": [{"stream": s, "event": e} for s, e in window],
        })

    # index source tail identities, so a reader can prove which stream state each index was built from
    idx_dir = root / ".finprodline/indexes"
    index_tails = {}
    if idx_dir.is_dir():
        for p in sorted(idx_dir.glob("*.json")):
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                index_tails[p.name] = {"unreadable": True}
                continue
            index_tails[p.name] = {"built_at": doc.get("built_at"),
                                   "source_tails": doc.get("source_tails")}

    # supersession links, with the existence of every target stated explicitly
    known = {e.get("event_id") for _, e in all_events}
    supersession_links, dangling = [], []
    for stream_name, evs in export["streams"].items():
        for e in evs:
            for target in e.get("supersedes") or []:
                exists = target in known
                supersession_links.append({"event_id": e.get("event_id"), "stream": stream_name,
                                           "supersedes": target, "target_exists": exists})
                if not exists:
                    dangling.append({"event_id": e.get("event_id"), "missing_target": target})

    # sequence contiguity and hash-chain proof, per stream
    chain = {}
    for stream_name, evs in export["streams"].items():
        seqs = [e.get("seq") for e in evs]
        gaps = [n for a, b in zip(seqs, seqs[1:]) if b != a + 1 for n in (a, b)]
        links_ok = all(evs[i].get("prev_event_hash") == evs[i - 1].get("event_hash")
                       for i in range(1, len(evs))) and bool(evs)
        chain[stream_name] = {"events": len(evs), "seq_contiguous": not gaps,
                              "seq_range": [min(seqs), max(seqs)] if seqs else None,
                              "prev_hash_links_ok": links_ok,
                              "tail_hash": evs[-1].get("event_hash") if evs else None}

    # referenced artifact identities, and evidence refs that name a project-relative path
    referenced, missing_refs = [], []
    for stream_name, evs in export["streams"].items():
        for e in evs:
            for r in e.get("evidence_refs") or []:
                looks_like_path = ("/" in r.rstrip("/")) and not r.startswith(("run-", "project-"))
                if looks_like_path:
                    exists = (root / r).exists()
                    referenced.append({"event_id": e.get("event_id"), "ref": r, "exists": exists})
                    if not exists:
                        missing_refs.append({"event_id": e.get("event_id"), "ref": r})

    return emit("export-audit", {
        "scope": args.scope, "chunks": len(packages),
        "total_events": len(all_events), "tails": export["tails"],
        "index_source_tails": index_tails,
        "stream_integrity": chain,
        "supersession_links": supersession_links,
        "referenced_identities": referenced,
        "orphan_and_missing_reference_checks": {
            "dangling_supersedes": dangling,
            "missing_evidence_refs": missing_refs,
            "streams_without_events": [s for s, v in chain.items() if v["events"] == 0],
        },
        "packages": packages,
    })


def cmd_lineage(args) -> int:
    root = project_root(args.project)
    view = build_view(root, "lineage", {})
    if args.frm:
        cone, frontier = set(), [args.frm]
        while frontier:
            node = frontier.pop()
            for edge in view["edges"]:
                if edge["from"] == node and edge["to"] not in cone:
                    cone.add(edge["to"])
                    frontier.append(edge["to"])
        return emit("lineage", {"from": args.frm, "downstream_cone": sorted(cone)})
    parents, frontier = set(), [args.to]
    while frontier:
        node = frontier.pop()
        for edge in view["edges"]:
            if edge["to"] == node and edge["from"] not in parents:
                parents.add(edge["from"])
                frontier.append(edge["from"])
    return emit("lineage", {"to": args.to, "upstream": sorted(parents)})


def cmd_recover_coordinator(args) -> int:
    root = project_root(args.project)
    cfg = load_config(root)
    package = {
        "root": str(root),
        "goal": build_view(root, "project-current", {}).get("goal") or cfg.get("goal"),
        "project_current": build_view(root, "project-current", {}),
        "plan_current": build_view(root, "plan-current", {}),
        "open_items": build_view(root, "open-items", {}),
        "handoff_notes": [
            "Declare takeover explicitly.",
            "Continue from this package and the accepted artifacts on disk.",
            "Never reconstruct state from conversation memory.",
        ],
    }
    append_event(root, "run", {"actor": "terminal", "event_type": "recovery_event",
                               "subject_id": "coordinator",
                               "payload": {"kind": "coordinator_bootstrap_package"}})
    return emit("recover-coordinator", package)


# ------------------------------------------------------------------ cli

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fpl_state", description="FinProdLine state surface")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("discover"); d.add_argument("--start"); d.set_defaults(func=cmd_discover)

    i = sub.add_parser("init")
    i.add_argument("--root", required=True)
    i.add_argument("--goal", required=True)
    i.add_argument("--canon-mode", default="supplied")
    i.add_argument("--audit-replicas", type=int, default=1)
    i.add_argument("--handbook-learner")
    i.add_argument("--release-override")
    i.set_defaults(func=cmd_init)

    g = sub.add_parser("get")
    g.add_argument("view", choices=INDEX_NAMES)
    g.add_argument("--select", action="append")
    g.add_argument("--project")
    g.set_defaults(func=cmd_get)

    a = sub.add_parser("append")
    a.add_argument("--stream", required=True)
    a.add_argument("--event", required=True)
    a.add_argument("--project")
    a.set_defaults(func=cmd_append)

    w = sub.add_parser("worker"); w.add_argument("--id", required=True)
    w.add_argument("--project"); w.set_defaults(func=cmd_worker)

    r = sub.add_parser("rebuild-index"); r.add_argument("name", nargs="?", default="all")
    r.add_argument("--project"); r.set_defaults(func=cmd_rebuild_index)

    v = sub.add_parser("verify-ledgers")
    v.add_argument("--record", action="store_true",
                   help="append the verification to the run stream and move the tail anchor")
    v.add_argument("--project")
    v.set_defaults(func=cmd_verify_ledgers)

    vi = sub.add_parser("verify-indexes"); vi.add_argument("--project")
    vi.set_defaults(func=cmd_verify_indexes)

    e = sub.add_parser("export-audit"); e.add_argument("--scope", required=True)
    e.add_argument("--chunk", type=int, default=1); e.add_argument("--project")
    e.set_defaults(func=cmd_export_audit)

    l = sub.add_parser("lineage")
    l.add_argument("--from", dest="frm"); l.add_argument("--to", dest="to")
    l.add_argument("--project"); l.set_defaults(func=cmd_lineage)

    c = sub.add_parser("recover-coordinator"); c.add_argument("--project")
    c.set_defaults(func=cmd_recover_coordinator)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Failure as exc:
        return die(args.command, str(exc))
    except Exception as exc:  # noqa: BLE001 - a CLI must not traceback at the operator
        return die(args.command, f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    sys.exit(main())
