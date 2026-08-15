"""
Verdict Card — turns validate()'s L1-L8 rule-engine output into the
structured, tiered card a sales rep reads instead of prose.

Every field here is a deterministic function of validate()'s output plus KG
provenance lookups. No model call happens anywhere in this module — that is
the same root invariant #1 the rule engine itself is built on (see
CLAUDE.md's Principle I / Verdict-Not-Guess). This module never re-judges a
verdict validate() already produced; it classifies, rolls up, and formats.

Usage:
    from kg_lib.verdict_card import generate_verdict_card
    card = generate_verdict_card("cloud-run>cloud-sql", data_residency="eu")
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import validate as validate_module

GAP_REPORT_PATH = Path(__file__).resolve().parent.parent / "references" / "gap_report.jsonl"

# ------------------------------------------------------------- tier constants
TIER_PROVEN = "Proven"
TIER_THEORETICAL = "Theoretically Possible"
TIER_DEEP_REVIEW = "Requires Deep Review"

_UNCOVERED_VERDICTS = {"UNCOVERED"}
_UNKNOWN_VERDICTS = {"UNKNOWN_SERVICE"}
_ERROR_SEVERITIES = {"ERROR", "WARNING"}

_DIFFICULTY_ORDER = {"Low": 0, "Medium": 1, "High": 2, "Unassessed": -1}

# Stated-need keyword -> what it actually fits, per research.md's rule table.
# The WebSockets/REST example is the deck's own canonical case.
MISMATCH_RULES = [
    {
        "keywords": ("websocket", "websockets"),
        "fits_roles": {"stream_processing", "event_router", "messaging", "message_queue"},
        "actual_need_label": "a request/response API (REST-style http_target), not a persistent socket",
    },
    {
        "keywords": ("message queue", "pub/sub", "pub sub", "queue"),
        "fits_roles": {"message_queue", "messaging", "event_router", "event_source", "event_consumer"},
        "actual_need_label": "an asynchronous queue or pub/sub service, not a synchronous request/response API",
    },
]


# ------------------------------------------------------------------ provenance
def _provenance_status(kg, node_id):
    node = kg.services.get(node_id)
    if not node:
        return None
    return (node.get("provenance") or {}).get("status")


def _involved_node_ids(entry, kind):
    if kind == "connectivity":
        return [entry["source"], entry["target"]]
    detail = entry.get("detail")
    if isinstance(detail, list):
        return [d for d in detail if isinstance(d, str)]
    return []


# --------------------------------------------------------------- tier mapping
def _classify_tier(kg, verdict, severity, node_ids):
    """Proven / Theoretically Possible / Requires Deep Review — see research.md."""
    if verdict in _UNKNOWN_VERDICTS:
        return TIER_DEEP_REVIEW
    if severity in _ERROR_SEVERITIES:
        return TIER_DEEP_REVIEW
    if verdict in _UNCOVERED_VERDICTS:
        return TIER_THEORETICAL
    for nid in node_ids:
        status = _provenance_status(kg, nid)
        if status == "unverified":
            return TIER_DEEP_REVIEW
    return TIER_PROVEN


def _finding_from_connectivity(kg, entry):
    node_ids = _involved_node_ids(entry, "connectivity")
    tier = _classify_tier(kg, entry["verdict"], entry.get("severity"), node_ids)
    detail_bits = [f"rule={entry.get('rule_id')}", f"verdict={entry['verdict']}"]
    if entry.get("message"):
        detail_bits.append(entry["message"])
    return {
        "layer_id": "L1",
        "subject": f"{entry['source']} -> {entry['target']}",
        "tier": tier,
        "severity": entry.get("severity"),
        "verdict": entry["verdict"],
        "supporting_detail": "; ".join(detail_bits),
        "_node_ids": node_ids,
    }


def _finding_from_architecture(kg, entry):
    node_ids = _involved_node_ids(entry, "architecture")
    # Architecture findings only exist when a rule fired — there is no
    # "UNCOVERED" verdict at this level, only severity.
    tier = _classify_tier(kg, "MATCHED", entry.get("severity"), node_ids)
    detail_bits = [f"rule={entry.get('rule_id')}", entry.get("title", "")]
    if entry.get("message"):
        detail_bits.append(entry["message"])
    return {
        "layer_id": entry.get("layer"),
        "subject": entry.get("title") or entry.get("rule_id") or "architecture finding",
        "tier": tier,
        "severity": entry.get("severity"),
        "verdict": "MATCHED",
        "supporting_detail": "; ".join(b for b in detail_bits if b),
        "_node_ids": node_ids,
    }


def extract_findings(kg, report):
    """One Finding per connectivity + architecture entry from validate()'s report."""
    findings = [_finding_from_connectivity(kg, c) for c in report["connectivity"]]
    findings += [_finding_from_architecture(kg, a) for a in report["architecture"]]
    return findings


# --------------------------------------------------------------- difficulty
def compute_difficulty(findings):
    """Deterministic rollup — same findings always produce the same verdict (FR-003)."""
    if not findings:
        return "Low", "No findings — nothing to evaluate."

    error_findings = [f for f in findings if f["severity"] == "ERROR"]
    warning_findings = [f for f in findings if f["severity"] == "WARNING"]
    uncovered_findings = [f for f in findings if f["verdict"] in _UNCOVERED_VERDICTS
                           or f["verdict"] in _UNKNOWN_VERDICTS]

    if uncovered_findings and len(uncovered_findings) == len(findings):
        return "Unassessed", (
            "No rule or historical precedent covers any evaluated element "
            f"({', '.join(f['subject'] for f in uncovered_findings)}); "
            "feasibility could not be established."
        )

    if error_findings:
        subjects = ", ".join(f["subject"] for f in error_findings)
        return "High", f"Driven by blocking finding(s): {subjects}."

    if warning_findings:
        subjects = ", ".join(f["subject"] for f in warning_findings)
        return "Medium", f"Driven by warning finding(s): {subjects}."

    if uncovered_findings:
        subjects = ", ".join(f["subject"] for f in uncovered_findings)
        return "Medium", (
            f"No blocking or warning findings, but {subjects} could not be "
            "checked against any rule or history — cannot confirm low difficulty."
        )

    return "Low", "All findings proven clean against existing rules and history."


# ---------------------------------------------------------------- mismatches
def detect_mismatches(kg, node_ids, stated_needs):
    """Client's stated technology choice vs. what the request actually needs.

    Table-driven per research.md: the determination of fit is a lookup
    against MISMATCH_RULES, not an LLM judgment call — the model only
    supplies which words in the client's request to check.
    """
    if not stated_needs:
        return []
    stated_lower = stated_needs.lower()
    involved_roles = set()
    for nid in node_ids:
        node = kg.services.get(nid)
        if node:
            involved_roles |= set(node.get("roles", []))

    mismatches = []
    for rule in MISMATCH_RULES:
        matched_keyword = next((kw for kw in rule["keywords"] if kw in stated_lower), None)
        if not matched_keyword:
            continue
        if involved_roles & rule["fits_roles"]:
            continue
        mismatches.append({
            "stated_choice": matched_keyword,
            "actual_need": rule["actual_need_label"],
            "explanation": (
                f"Client asked for '{matched_keyword}', but the involved services "
                f"support {rule['actual_need_label']}."
            ),
        })
    return mismatches


# ---------------------------------------------------------------- checklist
def generate_checklist(findings):
    """One item per non-Proven finding — 1:1, never orphaned (SC-004)."""
    items = []
    for f in findings:
        if f["tier"] == TIER_PROVEN:
            continue
        if f["tier"] == TIER_THEORETICAL:
            action = (
                f"Confirm feasibility for {f['subject']} — no prior verified "
                "instance backs this; validate before committing to the client."
            )
        else:
            action = (
                f"Review {f['subject']} with engineering before committing to "
                f"the client ({f['supporting_detail']})."
            )
        items.append({"source_finding": f["subject"], "action": action})
    reason = None if items else "All findings proven — no follow-up required."
    return items, reason


# ---------------------------------------------------------------- gap records
def _gap_record(edges, finding, now=None):
    now = now or datetime.now(timezone.utc)
    return {
        "logged_at": now.isoformat(),
        "request_summary": edges,
        "unresolved_element": finding["subject"],
        "reason": finding["supporting_detail"],
    }


def _append_gap_records(records):
    if not records:
        return
    GAP_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GAP_REPORT_PATH, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def log_gap_records(edges, findings, sink=None):
    """Unconditional write — no confirmation gate (Constitution Principle IV).

    `sink` takes the record list and stores it. It defaults to appending the
    JSONL file, which is what keeps this module runnable with no database and
    no configuration — the engine is handed its data and does not go looking
    for it, and that stays true for what it writes as well. The caller passes a
    Postgres sink when there is a database to write to.
    """
    gaps = [
        f for f in findings
        if f["verdict"] in _UNCOVERED_VERDICTS or f["verdict"] in _UNKNOWN_VERDICTS
    ]
    records = [_gap_record(edges, f) for f in gaps]
    (sink or _append_gap_records)(records)
    return records


# --------------------------------------------------------------------- card
def generate_verdict_card(edges, environment=None, data_residency=None,
                           sla_tier=None, stated_needs="", kg=None,
                           gap_sink=None):
    """Build a Verdict Card from validate()'s output. See contracts/generate_verdict_card.md."""
    kg = kg or validate_module.kg_module.load()

    assumptions = []
    if environment is None:
        environment = "poc"
        assumptions.append("environment not specified by rep — assumed 'poc'.")
    if data_residency is None:
        data_residency = "none"
        assumptions.append("data residency not specified by rep — assumed 'none'.")
    if sla_tier is None:
        sla_tier = "standard"
        assumptions.append("SLA tier not specified by rep — assumed 'standard'.")

    parsed_edges = validate_module._parse_edges(edges)
    report = validate_module.validate(
        parsed_edges,
        context={"environment": environment, "data_residency": data_residency, "sla_tier": sla_tier},
        kg=kg,
    )

    findings = extract_findings(kg, report)
    difficulty, difficulty_reason = compute_difficulty(findings)

    all_node_ids = {nid for f in findings for nid in f["_node_ids"]}
    mismatches = detect_mismatches(kg, all_node_ids, stated_needs)

    checklist, checklist_empty_reason = generate_checklist(findings)

    log_gap_records(edges, findings, sink=gap_sink)

    public_findings = [
        {k: v for k, v in f.items() if not k.startswith("_")} for f in findings
    ]

    return {
        "schema_version": "1.1",
        "difficulty": difficulty,
        "difficulty_reason": difficulty_reason,
        "findings": public_findings,
        "mismatches": mismatches,
        # The engine reports when two named services are mutually exclusive
        # options rather than components used together (Cloud SQL vs Spanner,
        # Firestore vs Bigtable). The card used to drop it, so a rep who asked
        # for both was handed a Verdict Card for an architecture that cannot
        # exist, with nothing saying so. Added in 1.1; the omission was an
        # oversight rather than a decision -- nothing in the card's spec
        # mentions exclusive choices at all.
        "exclusive_choices": report.get("exclusive_choices") or [],
        "checklist": checklist,
        "checklist_empty_reason": checklist_empty_reason,
        "assumptions": assumptions,
        "context": report["context"],
    }
