from pathlib import Path

import pytest

from tests.eval.validate_dataset import load_source, load_target, validate


ROOT = Path(__file__).resolve().parents[2]


def test_converted_dataset_preserves_source_cases():
    # 10 since E02b was added: E02 only proves the agent asks about the ambiguous
    # Pub/Sub and load-balancer choices, so translation itself went unexercised
    # until a case supplied those choices. 14 as of 2026-08-15: E02b became a
    # genuine Shape-B continuation of E02 (see test below), and E10-E13 close a
    # coverage gap -- curator_agent's write path (add/typo-refusal/role-warning)
    # and explorer_agent's typed query + health tools had zero eval cases.
    # 16 as of 2026-08-17: E14-E15 close a second coverage gap -- the
    # project_catalog capability-assessment tools (assess_capability,
    # search_past_projects, list_best_practice_tags) had zero eval cases, so
    # nothing exercised distinguishing a Proven delivered-project match from a
    # Theoretical pattern backed only by a principal reference architecture.
    validate()
    assert len(load_source()) == 16
    assert len(load_target()) == 16


def test_converted_dataset_has_unique_ids_and_all_assertions():
    source = {case["id"]: case for case in load_source()}
    target = {case["eval_case_id"]: case for case in load_target()}
    assert set(source) == set(target)
    for case_id, source_case in source.items():
        rubrics = target[case_id]["rubric_groups"]["source_assertions"]["rubrics"]
        assert len(rubrics) == len(source_case["assertions"])


def test_duplicate_target_id_fails(tmp_path):
    target = load_target()
    target[1]["eval_case_id"] = target[0]["eval_case_id"]
    path = tmp_path / "dataset.json"
    import json
    path.write_text(json.dumps({"eval_cases": target}), encoding="utf-8")
    with pytest.raises(AssertionError, match="unique"):
        validate(target_path=path)


def test_e02b_is_a_genuine_shape_b_continuation():
    # Not a restated Shape-A prompt: it carries E02's own prior turns as
    # agent_data.turns, and eval generate appends the next agent response.
    source = {case["id"]: case for case in load_source()}
    target = {case["eval_case_id"]: case for case in load_target()}
    e02b_source = source["E02b-cross-cloud-choices"]
    e02b_target = target["E02b-cross-cloud-choices"]
    assert e02b_source["prior_turns"]
    assert "prompt" not in e02b_target
    events = e02b_target["agent_data"]["turns"][0]["events"]
    assert len(events) == len(e02b_source["prior_turns"]) + 1
    assert events[0]["content"]["parts"][0]["text"] == source["E02-cross-cloud"]["prompt"]
    assert events[-1]["author"] == "user"
    assert events[-1]["content"]["parts"][0]["text"] == e02b_source["prompt"]


def test_shape_b_follow_up_prompt_drift_fails(tmp_path):
    import json

    target = load_target()
    for case in target:
        if case["eval_case_id"] == "E02b-cross-cloud-choices":
            case["agent_data"]["turns"][0]["events"][-1]["content"]["parts"][0]["text"] = "drifted"
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({"eval_cases": target}), encoding="utf-8")
    with pytest.raises(AssertionError, match="follow-up prompt changed"):
        validate(target_path=path)
