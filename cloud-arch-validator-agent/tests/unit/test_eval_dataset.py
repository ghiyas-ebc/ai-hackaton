from pathlib import Path

import pytest

from tests.eval.validate_dataset import load_source, load_target, validate


ROOT = Path(__file__).resolve().parents[2]


def test_converted_dataset_preserves_source_cases():
    validate()
    assert len(load_source()) == 9
    assert len(load_target()) == 9


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
