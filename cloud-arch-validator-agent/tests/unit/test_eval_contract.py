import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "tests/eval/datasets/architecture-validator-dataset.json"
CONFIG = ROOT / "tests/eval/eval_config.yaml"


def test_dataset_contract_has_source_assertions_for_every_case():
    cases = json.loads(DATASET.read_text())["eval_cases"]
    assert cases
    for case in cases:
        rubrics = case["rubric_groups"]["source_assertions"]["rubrics"]
        assert rubrics
        assert all(r["rubric_id"] and r["content"]["property"]["description"] for r in rubrics)


def test_metric_config_keeps_only_metrics_that_produced_usable_signal():
    # The two dropped built-ins errored on most cases in the baseline run; see
    # the rationale comment in eval_config.yaml.
    config = yaml.safe_load(CONFIG.read_text())
    assert config["metrics_to_run"] == [
        "instruction_following",
        "hallucination",
        "verdict_grounding",
        "kg_write_grounding",
    ]
    assert "final_response_quality" not in config["metrics_to_run"]
    assert "tool_use_quality" not in config["metrics_to_run"]


def test_verdict_grounding_is_a_local_deterministic_metric():
    # Invariant #1 must not be graded by a judge that can be wrong about it.
    config = yaml.safe_load(CONFIG.read_text())
    custom = {m["name"]: m for m in config["custom_metrics"]}
    assert custom["verdict_grounding"]["custom_function_file"] == "verdict_grounding.py"
    assert (CONFIG.parent / "verdict_grounding.py").exists()


def test_kg_write_grounding_is_a_local_deterministic_metric():
    # The curator's write boundary must not be graded by a judge that can only
    # see response text, not which tool response actually came back.
    config = yaml.safe_load(CONFIG.read_text())
    custom = {m["name"]: m for m in config["custom_metrics"]}
    assert custom["kg_write_grounding"]["custom_function_file"] == "kg_write_grounding.py"
    assert (CONFIG.parent / "kg_write_grounding.py").exists()
