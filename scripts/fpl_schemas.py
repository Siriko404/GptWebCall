#!/usr/bin/env python3
"""Emit the FinProdLine machine schemas.

Contract: ../../skill/webcall/references/finprodline/FINPRODLINE_PROTOCOL.md §"Required machine
contracts" (spec §23).

Design rule, stated once and applied to every schema here:

    pin identity, evidence, state and delivery; never pin the substantive answer.

A schema may fix a field name, an id format, a hash, a status, or an evidence reference, because
those are needed for deterministic validation. It must NOT enumerate the substantive finance
answers a competent worker could give — no candidate mechanisms, no design enums, no field named
after a preferred method. Where the expert's content goes, the schema says "object" and allows
anything.

Usage:
    fpl_schemas.py --emit <dir>     write the schema set
    fpl_schemas.py --check <dir>    verify on-disk schemas match this source of truth
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DRAFT = "https://json-schema.org/draft/2020-12/schema"
HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
ID = {"type": "string", "minLength": 1}
TEXT = {"type": "string", "minLength": 1}

# ---------------------------------------------------------------- shared envelope

def event_envelope(stream: str, event_types: list[str]) -> dict:
    return {
        "type": "object",
        "required": ["schema_version", "seq", "event_id", "timestamp", "actor", "event_type",
                     "subject_id", "payload", "evidence_refs", "supersedes", "prev_event_hash",
                     "event_hash"],
        "additionalProperties": True,
        "properties": {
            "schema_version": {"const": 1},
            "seq": {"type": "integer", "minimum": 1},
            "event_id": {"type": "string",
                         "pattern": f"^{stream}-[0-9]{{6}}-[0-9a-f]{{8}}$"},
            "timestamp": {"type": "string", "format": "date-time"},
            "actor": {"type": "string",
                      "pattern": "^(coordinator|terminal|operator|worker:[A-Za-z0-9._:-]+)$"},
            "event_type": {"enum": event_types},
            "subject_id": {"type": ["string", "null"]},
            "phase_id": {"type": ["string", "null"]},
            "gate": {"enum": ["METHOD", "DATA", "EXECUTION", None]},
            "payload": {"type": "object",
                        "description": "Free-form. The schema deliberately does not pin finance "
                                       "content here."},
            "evidence_refs": {"type": "array", "items": {"type": "string"}},
            "supersedes": {"type": "array", "items": ID},
            "prev_event_hash": HASH,
            "event_hash": HASH,
        },
    }


PROJECT_EVENTS = ["goal_set", "operator_ruling_recorded", "plan_proposed", "plan_accepted",
                  "plan_superseded", "phase_opened", "gate_state_changed", "finding_promoted",
                  "finding_closed", "conclusion_accepted", "open_item_raised", "open_item_settled",
                  "scope_changed", "earn_keep_cut_recorded", "final_decision"]
RUN_EVENTS = ["session_started", "project_initialized", "marker_verified",
              "coordinator_bootstrapped", "directive_received", "directive_rejected_malformed",
              "package_precheck_result", "upload_approval_recorded", "exchange_prepared",
              "exchange_armed", "exchange_event_received", "delivery_validated",
              "semantic_acceptance_recorded", "artifact_persisted", "reconciliation_result",
              "index_rebuilt", "supersession_linked", "anomaly_recorded", "recovery_event"]
WORKER_EVENTS = ["task_started", "input_pinned", "step_performed", "finding_recorded",
                 "output_produced", "issue_open", "issue_closed", "task_finished"]

# ---------------------------------------------------------------- the schema set

SCHEMAS: dict[str, dict] = {

    "project_config.schema.json": {
        "$schema": DRAFT, "title": "FinProdLine project configuration",
        "type": "object",
        "required": ["schema_version", "project_id", "root", "created_at", "goal", "canon_mode",
                     "audit_replicas", "handbook_learner", "release_artifacts"],
        "additionalProperties": True,
        "properties": {
            "schema_version": {"const": 1},
            "project_id": ID,
            "root": TEXT,
            "created_at": {"type": "string", "format": "date-time"},
            "goal": TEXT,
            "acceptance_outcome": {"type": ["string", "null"]},
            "canon_mode": {"enum": ["supplied", "researched", "hybrid"],
                           "description": "Sourcing mode, not a preferred canon."},
            "canon_pins": {"type": "array",
                           "items": {"type": "object", "required": ["path", "sha256"],
                                     "properties": {"path": TEXT, "sha256": HASH,
                                                    "note": {"type": "string"}}}},
            "audit_replicas": {"type": "integer", "minimum": 1,
                               "description": "Operator-chosen replica count N per audit chunk."},
            "handbook_learner": TEXT,
            "handbook_audience_testing": {"const": "not_required",
                                          "description": "Operator ruling: audience testing is not "
                                                         "required. Do not re-add it."},
            "release_artifacts": {"type": "object"},
            "restrictions": {"type": "array", "items": {"type": "string"}},
            "privacy_lock": {"type": ["string", "null"]},
            "event_vocabulary_extensions": {"type": "object",
                                            "additionalProperties": {"type": "string"}},
            "audit_budget_cap": {"const": None,
                                 "description": "Operator ruling: no cap on audit volume."},
        },
    },

    "project_ledger_event.schema.json": event_envelope("project", PROJECT_EVENTS),
    "run_ledger_event.schema.json": event_envelope("run", RUN_EVENTS),
    "worker_task_ledger_event.schema.json": event_envelope("worker", WORKER_EVENTS),

    "coordinator_directive.schema.json": {
        "$schema": DRAFT, "title": "Coordinator directive batch",
        "type": "object",
        "required": ["request_id", "status", "confirm", "prodline_status", "directives"],
        "additionalProperties": True,
        "properties": {
            "request_id": ID,
            "status": {"enum": ["COMPLETE", "PARTIAL", "BLOCKED"]},
            "confirm": {"enum": ["READY", None]},
            "prodline_status": {"enum": ["CONTINUE", "GREENLIGHT", "BLOCKED"]},
            "project_view": {"type": "object",
                             "description": "Generated state view, never a raw ledger."},
            "directives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "kind", "objective", "earn_keep", "dependencies",
                                 "parallel_group", "mode", "operator_interaction", "web_research",
                                 "context_scope", "authority", "scope_in", "scope_out",
                                 "requested_work", "deliverables", "acceptance", "stop_condition"],
                    "additionalProperties": True,
                    "properties": {
                        "id": ID,
                        "kind": {"enum": ["WORKER_CALL", "LOCAL_ACTION", "FINAL_QA", "AUDIT"]},
                        "objective": TEXT,
                        "earn_keep": {"type": "object",
                                      "required": ["need", "boundary", "fit", "proof"],
                                      "properties": {"need": TEXT, "boundary": TEXT,
                                                     "fit": TEXT, "proof": TEXT}},
                        "dependencies": {"type": "array", "items": ID},
                        "parallel_group": {"type": ["string", "null"]},
                        "persona": {"type": ["string", "null"]},
                        "mode": {"enum": ["bounded", "conductor"]},
                        "operator_interaction": {"enum": ["none", "allowed", "required"]},
                        "web_research": {"enum": ["allowed", "forbidden"]},
                        "context_scope": {"type": "array", "items": {"type": "string"}},
                        "mp_skills": {"type": "array",
                                      "items": {"type": "object", "required": ["name", "why"],
                                                "properties": {"name": TEXT, "why": TEXT}}},
                        "authority": {"type": "array", "items": {"type": "string"}},
                        "scope_in": {"type": "array", "items": {"type": "string"}},
                        "scope_out": {"type": "array", "items": {"type": "string"}},
                        "requested_work": {"type": "array", "items": {"type": "string"}},
                        "deliverables": {"type": "array", "items": {"type": "string"}},
                        "acceptance": {"type": "array", "items": {"type": "string"}},
                        "stop_condition": TEXT,
                        "phase_id": {"type": ["string", "null"]},
                        "gate": {"enum": ["METHOD", "DATA", "EXECUTION", None]},
                        "ledger_event_templates": {
                            "type": "array",
                            "description": "Deterministic outcome->event mappings. Terminal may "
                                           "append a semantic event immediately only when the "
                                           "observed outcome maps exactly to one of these.",
                            "items": {"type": "object",
                                      "required": ["when", "event_type"],
                                      "additionalProperties": True,
                                      "properties": {"when": {"type": "object"},
                                                     "event_type": {"type": "string"},
                                                     "payload_template": {"type": "object"}}}},
                    },
                },
            },
        },
    },

    "plan_layer1.schema.json": {
        "$schema": DRAFT, "title": "Layer 1 — tentative project overview plan",
        "type": "object",
        "required": ["schema_version", "plan_id", "layer", "version", "produced_by",
                     "tentative", "audit_state"],
        "additionalProperties": True,
        "properties": {
            "schema_version": {"const": 1},
            "plan_id": ID, "layer": {"const": 1},
            "version": {"type": "integer", "minimum": 1},
            "content_hash": HASH,
            "produced_by": {"type": "object", "required": ["worker_id", "exchange_id"],
                            "properties": {"worker_id": ID, "exchange_id": ID}},
            "tentative": {"const": True,
                          "description": "Layer 1 is explicitly tentative by definition."},
            "audit_state": {"enum": ["proposed", "in_audit", "accepted", "superseded"]},
            "phases": {"type": "array",
                       "description": "The proposed semantic phases. Content is the planner's own; "
                                      "the schema pins identity and evidence, not the phase design.",
                       "items": {"type": "object",
                                 "required": ["phase_id", "title"],
                                 "additionalProperties": True,
                                 "properties": {"phase_id": ID, "title": TEXT,
                                                "depends_on": {"type": "array", "items": ID},
                                                "evidence_refs": {"type": "array",
                                                                  "items": {"type": "string"}}}}},
            "authority": {"type": "array", "items": {"type": "string"}},
            "evidence_refs": {"type": "array", "items": {"type": "string"}},
        },
    },

    "plan_layer23.schema.json": {
        "$schema": DRAFT, "title": "Layer 2/3 — phase blueprint and execution instructions",
        "type": "object",
        "required": ["schema_version", "plan_id", "phase_id", "version", "produced_by",
                     "layer2", "layer3", "audit_state"],
        "additionalProperties": True,
        "properties": {
            "schema_version": {"const": 1},
            "plan_id": ID,
            "phase_id": ID,
            "version": {"type": "integer", "minimum": 1},
            "content_hash": HASH,
            "produced_by": {"type": "object", "required": ["worker_id", "exchange_id"],
                            "properties": {"worker_id": ID, "exchange_id": ID}},
            "audit_state": {"enum": ["proposed", "in_audit", "accepted", "superseded"]},
            "supersedes_plan_id": {"type": ["string", "null"]},
            "layer2": {
                "type": "object",
                "required": ["method_gate", "data_gate", "execution_gate", "acceptance_tests"],
                "additionalProperties": True,
                "properties": {
                    "method_gate": {"type": "object", "additionalProperties": True},
                    "data_gate": {"type": "object", "additionalProperties": True},
                    "execution_gate": {"type": "object", "additionalProperties": True},
                    "acceptance_tests": {"type": "array", "items": {"type": "object",
                                                                    "additionalProperties": True}},
                    "provenance_requirements": {"type": "array", "items": {"type": "string"}},
                    "output_impacts": {"type": "array", "items": {"type": "string"}},
                },
            },
            "layer3": {
                "type": "object",
                "required": ["steps"],
                "additionalProperties": True,
                "properties": {
                    "steps": {"type": "array",
                              "items": {"type": "object", "required": ["step_id", "actor"],
                                        "additionalProperties": True,
                                        "properties": {
                                            "step_id": ID,
                                            "actor": {"type": "string",
                                                      "description": "worker, terminal or "
                                                                     "operator-bridge."},
                                            "artifacts": {"type": "array",
                                                          "items": {"type": "string"}},
                                            "stop_condition": {"type": ["string", "null"]}}}},
                },
            },
        },
    },

    "audit_plan.schema.json": {
        "$schema": DRAFT, "title": "Audit plan",
        "type": "object",
        "required": ["schema_version", "audit_id", "audit_type", "target_scope", "produced_by",
                     "replica_count", "chunks", "criteria_coverage", "review_state"],
        "additionalProperties": True,
        "properties": {
            "schema_version": {"const": 1},
            "audit_id": ID,
            "audit_type": {"enum": ["plan", "method", "data", "execution", "ledger", "handbook",
                                    "final_project"],
                           "description": "Audit disciplines are distinct; one never substitutes "
                                          "for another."},
            "target_scope": {"type": "object", "additionalProperties": True},
            "produced_by": {"type": "object", "required": ["worker_id", "exchange_id"],
                            "properties": {"worker_id": ID, "exchange_id": ID}},
            "replica_count": {"type": "integer", "minimum": 1},
            "chunks": {"type": "array",
                       "items": {"type": "object", "required": ["chunk_id", "checks",
                                                                "evidence_required"],
                                 "additionalProperties": True,
                                 "properties": {"chunk_id": ID,
                                                "checks": {"type": "array",
                                                           "items": {"type": "object",
                                                                     "additionalProperties": True}},
                                                "evidence_required": {"type": "array",
                                                                      "items": {"type": "string"}},
                                                "cross_chunk_dependencies": {
                                                    "type": "array", "items": ID}}}},
            "criteria_coverage": {
                "type": "array",
                "description": "Every acceptance criterion must map to at least one check. An "
                               "unmapped criterion makes the plan malformed.",
                "items": {"type": "object", "required": ["criterion", "chunk_ids"],
                          "properties": {"criterion": TEXT,
                                         "chunk_ids": {"type": "array", "items": ID}}},
            },
            "failure_rules": {"type": "object", "additionalProperties": True},
            "materiality_rules": {"type": "object", "additionalProperties": True},
            "ledger_checks": {"type": "array", "items": {"type": "string"}},
            "review_state": {"enum": ["proposed", "plan_review_in_progress", "passed",
                                      "returned_for_revision"]},
            "reviewed_by": {"type": ["object", "null"]},
        },
    },

    "audit_replica_report.schema.json": {
        "$schema": DRAFT, "title": "One auditor replica's report",
        "type": "object",
        "required": ["schema_version", "audit_id", "chunk_id", "replica_index", "produced_by",
                     "findings", "verdict"],
        "additionalProperties": True,
        "properties": {
            "schema_version": {"const": 1},
            "audit_id": ID, "chunk_id": ID,
            "replica_index": {"type": "integer", "minimum": 1},
            "produced_by": {"type": "object", "required": ["worker_id", "exchange_id"],
                            "properties": {"worker_id": ID, "exchange_id": ID}},
            "independent_of": {"type": "array", "items": ID,
                               "description": "Replica ids this report did not see."},
            "context_completeness_manifest": {"type": "object", "additionalProperties": True},
            "findings": {"type": "array",
                         "items": {"$ref": "audit_finding.schema.json"}},
            "verdict": {"enum": ["pass", "fail", "blocked", "pass_with_notes"]},
            "notes": {"type": "array", "items": {"type": "string"}},
        },
    },

    "audit_finding.schema.json": {
        "$schema": DRAFT, "title": "Audit finding",
        "type": "object",
        "required": ["schema_version", "finding_id", "target", "severity", "what_is_wrong",
                     "why_it_is_wrong", "evidence", "violated", "impact", "remediation",
                     "remediation_reasoning", "closure_test", "status"],
        "additionalProperties": True,
        "properties": {
            "schema_version": {"const": 1},
            "finding_id": ID,
            "target": TEXT,
            "severity": {"enum": ["material", "minor", "observation"],
                         "description": "Materiality is a classification, not a finance answer."},
            "what_is_wrong": TEXT,
            "why_it_is_wrong": TEXT,
            "evidence": {"type": "array", "minItems": 1,
                         "items": {"type": "object", "required": ["ref"],
                                   "additionalProperties": True,
                                   "properties": {"ref": TEXT, "line": {"type": ["integer", "null"]},
                                                  "cell": {"type": ["string", "null"]},
                                                  "sha256": {"type": ["string", "null"]}}}},
            "violated": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "impact": {"type": "object", "additionalProperties": True,
                       "description": "The downstream dependency cone."},
            "remediation": TEXT,
            "remediation_reasoning": TEXT,
            "closure_test": TEXT,
            "status": {"enum": ["open", "closed", "rejected", "unresolved_minority"]},
            "disposition_reason": {"type": ["string", "null"]},
        },
        "description": "A finding that states no evidence, no remediation or no closure test is "
                       "malformed and is returned to the auditor.",
    },

    "audit_integration.schema.json": {
        "$schema": DRAFT, "title": "Integrated audit verdict",
        "type": "object",
        "required": ["schema_version", "audit_id", "produced_by", "replica_reports",
                     "findings_register", "conflicts", "verdict"],
        "additionalProperties": True,
        "properties": {
            "schema_version": {"const": 1},
            "audit_id": ID,
            "produced_by": {"type": "object", "required": ["worker_id", "exchange_id"],
                            "properties": {"worker_id": ID, "exchange_id": ID}},
            "replica_reports": {"type": "array", "items": ID},
            "findings_register": {"type": "array",
                                  "items": {"type": "object", "required": ["finding_id", "status"],
                                            "additionalProperties": True,
                                            "properties": {"finding_id": ID,
                                                           "status": {"enum": ["open", "closed",
                                                                               "rejected",
                                                                               "unresolved_minority"]},
                                                           "merged_from": {"type": "array",
                                                                           "items": ID},
                                                           "disposition_reason": {"type": "string"}}}},
            "conflicts": {"type": "array",
                          "items": {"type": "object", "required": ["between", "issue", "resolution"],
                                    "additionalProperties": True,
                                    "properties": {"between": {"type": "array", "items": ID},
                                                   "issue": TEXT,
                                                   "resolution": {"type": "string",
                                                                  "description": "Resolution "
                                                                                 "against authority, "
                                                                                 "or explicitly "
                                                                                 "unresolved."}}}},
            "verdict": {"enum": ["pass", "fail", "blocked"],
                        "description": "Pass requires every acceptance criterion mapped by the "
                                       "audit plan to be satisfied, every finding closed, no "
                                       "unadjudicated conflict, and reconciliation passed."},
            "repairs_performed": {"const": False,
                                  "description": "An integrator never repairs what it adjudicated."},
        },
    },

    "gate_status.schema.json": {
        "$schema": DRAFT, "title": "Phase gate status",
        "type": "object",
        "required": ["schema_version", "phase_id", "gate", "state", "passed"],
        "additionalProperties": True,
        "properties": {
            "schema_version": {"const": 1},
            "phase_id": ID,
            "gate": {"enum": ["METHOD", "DATA", "EXECUTION"]},
            "state": {"enum": ["not_started", "work_in_progress", "audit_in_progress", "repair",
                               "passed", "blocked"]},
            "passed": {"type": "boolean"},
            "accepted_plan_id": {"type": ["string", "null"]},
            "audit_id": {"type": ["string", "null"]},
            "finding_register": {"type": "array", "items": {"type": "object",
                                                            "additionalProperties": True}},
            "reconciliation": {"type": ["object", "null"],
                               "description": "Required for the EXECUTION gate; see the release "
                                              "artifact line."},
            "ledger_integrity": {"type": ["object", "null"]},
            "passed_at": {"type": ["string", "null"], "format": "date-time"},
            "evidence_refs": {"type": "array", "items": {"type": "string"}},
        },
    },

    "artifact_lineage.schema.json": {
        "$schema": DRAFT, "title": "Artifact and number-lineage record",
        "type": "object",
        "required": ["schema_version", "artifact_id", "path", "sha256", "media_type", "produced_by"],
        "additionalProperties": True,
        "properties": {
            "schema_version": {"const": 1},
            "artifact_id": ID,
            "path": TEXT,
            "sha256": HASH,
            "size": {"type": "integer", "minimum": 0},
            "media_type": {"type": "string"},
            "phase_id": {"type": ["string", "null"]},
            "accepted": {"type": "boolean"},
            "produced_by": {"type": "object", "required": ["worker_id", "exchange_id"],
                            "properties": {"worker_id": ID, "exchange_id": ID}},
            "lineage": {
                "type": "object",
                "required": ["from"],
                "additionalProperties": True,
                "properties": {
                    "from": {"type": "array", "items": ID,
                             "description": "Upstream artifact or source ids."},
                    "source": {"type": ["string", "null"]},
                    "raw_value_ref": {"type": ["string", "null"]},
                    "transformation": {"type": ["string", "null"],
                                       "description": "Mandatory and non-empty wherever the raw "
                                                      "value and the final value differ."},
                    "final_use": {"type": ["string", "null"]},
                },
            },
            "supersedes": {"type": "array", "items": ID},
        },
    },

    "handbook_plan.schema.json": {
        "$schema": DRAFT, "title": "Handbook plan for one eligible phase",
        "type": "object",
        "required": ["schema_version", "handbook_plan_id", "phase_id", "eligibility",
                     "learner_contract", "lesson_architecture", "produced_by", "audit_state"],
        "additionalProperties": True,
        "properties": {
            "schema_version": {"const": 1},
            "handbook_plan_id": ID,
            "phase_id": ID,
            "eligibility": {"type": "object",
                            "required": ["method_passed", "data_passed", "execution_passed"],
                            "properties": {"method_passed": {"const": True},
                                           "data_passed": {"const": True},
                                           "execution_passed": {"const": True}},
                            "description": "All three must be true. Handbook production cannot "
                                           "begin for an unpassed phase."},
            "learner_contract": {
                "type": "object",
                "required": ["assumed_knowledge", "excluded_assumptions",
                             "observable_outcomes"],
                "additionalProperties": True,
                "properties": {"assumed_knowledge": {"type": "array", "items": {"type": "string"}},
                               "excluded_assumptions": {"type": "array",
                                                        "items": {"type": "string"}},
                               "observable_outcomes": {"type": "array", "minItems": 1,
                                                       "items": {"type": "string"}}},
            },
            "lesson_architecture": {"type": "array",
                                    "items": {"type": "object", "required": ["lesson_id",
                                                                             "teaching_purpose",
                                                                             "outcomes"],
                                              "additionalProperties": True,
                                              "properties": {"lesson_id": ID,
                                                             "teaching_purpose": TEXT,
                                                             "outcomes": {"type": "array",
                                                                          "items": {"type": "string"}}}}},
            "produced_by": {"type": "object", "required": ["worker_id", "exchange_id"],
                            "properties": {"worker_id": ID, "exchange_id": ID}},
            "audit_state": {"enum": ["proposed", "in_audit", "accepted", "superseded"]},
        },
    },

    "handbook_qa.schema.json": {
        "$schema": DRAFT, "title": "Handbook QA verdicts",
        "type": "object",
        "required": ["schema_version", "phase_id", "finance_correctness", "teachability",
                     "control_fidelity"],
        "additionalProperties": True,
        "properties": {
            "schema_version": {"const": 1},
            "phase_id": ID,
            "finance_correctness": {"$ref": "#/$defs/dimension"},
            "teachability": {"$ref": "#/$defs/dimension"},
            "control_fidelity": {"$ref": "#/$defs/dimension"},
            "audience_testing": {"const": "not_required",
                                 "description": "Operator ruling: no external audience test. "
                                                "Teachability is an audited judgment against the "
                                                "learner contract."},
            "findings": {"type": "array", "items": {"$ref": "audit_finding.schema.json"}},
        },
        "$defs": {
            "dimension": {
                "type": "object",
                "required": ["verdict", "audited_by"],
                "additionalProperties": True,
                "properties": {
                    "verdict": {"enum": ["pass", "fail", "blocked"]},
                    "audited_by": {"type": "object", "required": ["worker_id", "exchange_id"],
                                   "properties": {"worker_id": ID, "exchange_id": ID}},
                    "tests_applied": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}

# ---------------------------------------------------------------- emit / check

def emit(target: Path) -> int:
    target.mkdir(parents=True, exist_ok=True)
    for name, body in SCHEMAS.items():
        (target / name).write_text(json.dumps(body, indent=2, sort_keys=False) + "\n",
                                   encoding="utf-8")
    print(f"wrote {len(SCHEMAS)} schemas to {target}")
    return 0


def check(target: Path) -> int:
    bad = []
    for name, body in SCHEMAS.items():
        path = target / name
        if not path.is_file():
            bad.append(f"{name}: missing")
        elif json.loads(path.read_text(encoding="utf-8")) != body:
            bad.append(f"{name}: differs from the generator's source of truth")
    if bad:
        print("SCHEMA DRIFT:")
        for b in bad:
            print("  -", b)
        return 1
    print(f"OK - {len(SCHEMAS)} schemas match the generator")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="fpl_schemas.py")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--emit", metavar="DIR")
    g.add_argument("--check", metavar="DIR")
    args = ap.parse_args()
    return emit(Path(args.emit).resolve()) if args.emit else check(Path(args.check).resolve())


if __name__ == "__main__":
    sys.exit(main())
