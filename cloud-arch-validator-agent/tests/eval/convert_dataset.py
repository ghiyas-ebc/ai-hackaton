"""Convert source architecture eval cases to Agent CLI dataset format."""

from __future__ import annotations

import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "app" / "evals" / "evals.json"
TARGET = Path(__file__).resolve().parent / "datasets" / "architecture-validator-dataset.json"


def _rubric_id(case_id: str, index: int) -> str:
    return f"{case_id}-A{index:02d}"


def _rubric_groups(case: dict) -> dict:
    return {
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
    }


def _event(role: str, text: str) -> dict:
    author = "user" if role == "user" else "agent"
    message_role = "user" if role == "user" else "model"
    return {
        "author": author,
        "content": {"role": message_role, "parts": [{"text": text}]},
    }


def convert(source: Path = SOURCE) -> dict:
    payload = json.loads(source.read_text(encoding="utf-8"))
    cases = []
    for case in payload["evals"]:
        prior_turns = case.get("prior_turns")
        target: dict = {
            "eval_case_id": case["id"],
            "rubric_groups": _rubric_groups(case),
        }
        if prior_turns:
            # Shape B ("N+1"): a fixed conversation prefix plus the final user
            # turn, for a follow-up that cannot be exercised in one turn (see
            # tests/eval/datasets/README.md). `eval generate` appends the next
            # agent response after the last event below.
            events = [_event(turn["role"], turn["text"]) for turn in prior_turns]
            events.append(_event("user", case["prompt"]))
            target["agent_data"] = {"turns": [{"turn_index": 0, "events": events}]}
        else:
            target["prompt"] = {
                "role": "user",
                "parts": [{"text": case["prompt"]}],
            }
        cases.append(target)
    return {"eval_cases": cases}


def main() -> None:
    TARGET.write_text(json.dumps(convert(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
