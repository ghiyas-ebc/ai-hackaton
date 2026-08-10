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


def test_metric_config_uses_built_in_adk_metrics_only():
    config = yaml.safe_load(CONFIG.read_text())
    assert config["metrics_to_run"] == [
        "final_response_quality",
        "instruction_following",
        "tool_use_quality",
        "hallucination",
    ]
    assert "custom_metrics" not in config
