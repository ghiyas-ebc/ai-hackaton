from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_eval_docs_reference_migrated_dataset_and_commands():
    docs = (ROOT / "tests/eval/datasets/README.md").read_text()
    assert "architecture-validator-dataset.json" in docs
    for command in ("eval generate", "eval grade", "eval compare", "eval analyze"):
        assert command in docs
