"""Unit tests for the Verdict Card transformation layer.

Mirrors test_tools.py's approach: asserts on deterministic output of pure
functions over validate()'s rule-engine report, never on anything an LLM
says. `edges` values below were probed directly against the real KG (see
specs/001-verdict-card/quickstart.md) — 'cloud-run>cloud-sql' trips SEC-001,
'cloud-load-balancing>cloud-run' is clean, 'cloud-run>cloud-armor' has no
connectivity rule match (UNCOVERED), and a made-up service id is UNKNOWN.
"""

import json

import pytest

from app import tools

# isort: split
# `tools` puts app/kg_lib/ on sys.path as a side effect of import (see
# tools.py's comment on why this can't be `from app.kg_lib import ...`) —
# importing the bare name here, after `tools`, resolves to the SAME module
# object tools.py itself calls into, so monkeypatching module globals here
# actually takes effect during generate_verdict_card().
import verdict_card as vc


@pytest.fixture(autouse=True)
def isolated_gap_report(tmp_path, monkeypatch):
    """Redirect the Gap Report log to a scratch file so tests never touch the
    real one, and so each test starts from a clean, empty log."""
    scratch = tmp_path / "gap_report.jsonl"
    monkeypatch.setattr(vc, "GAP_REPORT_PATH", scratch)
    return scratch


# --------------------------------------------------------- User Story 1 (P1)
def test_all_clean_architecture_is_low_and_every_finding_proven():
    card = tools.generate_verdict_card("cloud-load-balancing>cloud-run")
    assert card["difficulty"] == "Low"
    assert card["findings"], "clean architecture still reports its findings"
    for finding in card["findings"]:
        assert finding["tier"] == vc.TIER_PROVEN


def test_rule_violation_drives_the_overall_difficulty():
    card = tools.generate_verdict_card("cloud-run>cloud-sql")
    assert card["difficulty"] == "High"
    error_findings = [f for f in card["findings"] if f["severity"] == "ERROR"]
    assert error_findings, "SEC-001 should have fired as an ERROR finding"
    for f in error_findings:
        assert f["tier"] == vc.TIER_DEEP_REVIEW
        assert f["subject"] in card["difficulty_reason"] or f["subject"] in str(
            [ff["subject"] for ff in error_findings]
        )


def test_uncovered_connection_is_not_given_a_confident_pass():
    card = tools.generate_verdict_card("cloud-run>cloud-armor")
    uncovered = [f for f in card["findings"] if f["verdict"] == "UNCOVERED"]
    assert uncovered, "cloud-run>cloud-armor has no matching connectivity rule"
    for f in uncovered:
        assert f["tier"] in (vc.TIER_THEORETICAL, vc.TIER_DEEP_REVIEW)
    assert card["difficulty"] != "Low"


def test_all_findings_carry_exactly_one_tier():
    """SC-002: every finding on every card carries a tier label."""
    for edges in ("cloud-load-balancing>cloud-run", "cloud-run>cloud-sql", "cloud-run>cloud-armor"):
        card = tools.generate_verdict_card(edges)
        for f in card["findings"]:
            assert f["tier"] in (vc.TIER_PROVEN, vc.TIER_THEORETICAL, vc.TIER_DEEP_REVIEW)


def test_difficulty_is_repeatable_given_the_same_inputs():
    """SC-005: identical inputs always produce the identical difficulty."""
    first = tools.generate_verdict_card("cloud-run>cloud-sql")
    second = tools.generate_verdict_card("cloud-run>cloud-sql")
    assert first["difficulty"] == second["difficulty"]
    assert first["difficulty_reason"] == second["difficulty_reason"]


def test_missing_context_proceeds_with_a_stated_assumption():
    """FR-010 / SC-006: no context supplied should not block the card."""
    card = tools.generate_verdict_card("cloud-load-balancing>cloud-run")
    assert card["assumptions"], "defaults should be reported, not silently applied"
    assert any("environment" in a for a in card["assumptions"])


# --------------------------------------------------------- User Story 2 (P2)
def test_mismatch_detected_when_stated_need_does_not_fit():
    card = tools.generate_verdict_card(
        "cloud-load-balancing>cloud-run", stated_needs="we need websockets"
    )
    assert card["mismatches"], "cloud-run/load-balancer edge has no streaming role"
    m = card["mismatches"][0]
    assert m["stated_choice"] in ("websocket", "websockets")
    assert "actual_need" in m


def test_no_mismatch_when_stated_need_is_not_provided():
    card = tools.generate_verdict_card("cloud-load-balancing>cloud-run")
    assert card["mismatches"] == []


# --------------------------------------------------------- User Story 3 (P3)
def test_checklist_has_one_item_per_non_proven_finding():
    card = tools.generate_verdict_card("cloud-run>cloud-sql")
    non_proven = [f for f in card["findings"] if f["tier"] != vc.TIER_PROVEN]
    assert len(card["checklist"]) == len(non_proven)
    checklist_subjects = {item["source_finding"] for item in card["checklist"]}
    non_proven_subjects = {f["subject"] for f in non_proven}
    assert checklist_subjects == non_proven_subjects


def test_all_proven_card_has_an_explicit_empty_checklist():
    card = tools.generate_verdict_card("cloud-load-balancing>cloud-run")
    assert card["checklist"] == []
    assert card["checklist_empty_reason"]


# --------------------------------------------------------- User Story 4 (P3)
def test_uncovered_finding_appends_a_gap_record(isolated_gap_report):
    tools.generate_verdict_card("cloud-run>totally-made-up-service")
    lines = isolated_gap_report.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["unresolved_element"] == "cloud-run -> totally-made-up-service"
    assert "logged_at" in record and "reason" in record


def test_repeated_gap_is_logged_each_time_not_deduplicated(isolated_gap_report):
    tools.generate_verdict_card("cloud-run>totally-made-up-service")
    tools.generate_verdict_card("cloud-run>totally-made-up-service")
    lines = isolated_gap_report.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_clean_request_writes_no_gap_record(isolated_gap_report):
    tools.generate_verdict_card("cloud-load-balancing>cloud-run")
    assert not isolated_gap_report.exists()
