"""Validate source-to-Agent CLI evaluation dataset coverage."""

from __future__ import annotations

import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent.parent / "app" / "evals" / "evals.json"
TARGET = Path(__file__).resolve().parent / "datasets" / "architecture-validator-dataset.json"


def load_source(path: Path = SOURCE) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["evals"]


def load_target(path: Path = TARGET) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["eval_cases"]


def validate(source_path: Path = SOURCE, target_path: Path = TARGET) -> None:
    source = load_source(source_path)
    target = load_target(target_path)
    if len(source) != len(target):
        raise AssertionError(f"case count differs: source={len(source)} target={len(target)}")

    source_by_id = {case["id"]: case for case in source}
    target_ids = [case.get("eval_case_id") for case in target]
    if len(set(target_ids)) != len(target_ids):
        raise AssertionError("target case IDs are not unique")
    if set(source_by_id) != set(target_ids):
        raise AssertionError("source and target IDs differ")

    for target_case in target:
        source_case = source_by_id[target_case["eval_case_id"]]
        prompt = target_case.get("prompt", {})
        text = (prompt.get("parts") or [{}])[0].get("text")
        if prompt.get("role") != "user" or text != source_case["prompt"]:
            raise AssertionError(f"prompt changed for {target_case['eval_case_id']}")
        rubrics = target_case.get("rubric_groups", {}).get("source_assertions", {}).get("rubrics", [])
        if len(rubrics) != len(source_case["assertions"]):
            raise AssertionError(f"assertion count differs for {target_case['eval_case_id']}")
        if any(not rubric.get("content", {}).get("property", {}).get("description") for rubric in rubrics):
            raise AssertionError(f"empty rubric for {target_case['eval_case_id']}")


if __name__ == "__main__":
    validate()
    print("dataset validation passed")
