"""Convert source architecture eval cases to Agent CLI dataset format."""

from __future__ import annotations

import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "app" / "evals" / "evals.json"
TARGET = Path(__file__).resolve().parent / "datasets" / "architecture-validator-dataset.json"


def _rubric_id(case_id: str, index: int) -> str:
    return f"{case_id}-A{index:02d}"


def convert(source: Path = SOURCE) -> dict:
    payload = json.loads(source.read_text(encoding="utf-8"))
    cases = []
    for case in payload["evals"]:
        cases.append(
            {
                "eval_case_id": case["id"],
                "prompt": {
                    "role": "user",
                    "parts": [{"text": case["prompt"]}],
                },
                "rubric_groups": {
                    "source_assertions": {
                        "rubrics": [
                            {
                                "rubric_id": _rubric_id(case["id"], index),
                                "content": {
                                    "property": {
                                        "description": assertion,
                                    }
                                },
                            }
                            for index, assertion in enumerate(case["assertions"], 1)
                        ]
                    }
                },
            }
        )
    return {"eval_cases": cases}


def main() -> None:
    TARGET.write_text(json.dumps(convert(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
