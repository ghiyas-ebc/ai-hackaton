# Quickstart: Verdict Card

Validates the feature end-to-end once implemented. Assumes `cloud-arch-validator-agent`'s existing dev
setup (`uv sync`, `.env` with model credentials) already works — this only adds scenarios for the new
tool.

## Prerequisites

```bash
cd cloud-arch-validator-agent
uv sync
```

## Scenario 1 — clean architecture, all-proven verdict (User Story 1)

```bash
uv run python -c "
from app.kg_lib.verdict_card import generate_verdict_card
card = generate_verdict_card('cloud-load-balancing>cloud-run,cloud-run>cloud-sql')
print(card['difficulty'])          # expect: Low
print([f['tier'] for f in card['findings']])   # expect: all 'Proven', if these pairs are KG-clean and manual/verified
"
```

Expected: single difficulty label, every finding individually tiered — confirms FR-001/FR-002.

## Scenario 2 — rule violation drives the verdict (User Story 1)

```bash
uv run python -c "
from app.kg_lib.verdict_card import generate_verdict_card
card = generate_verdict_card('cloud-run>cloud-sql', data_residency='eu')
print(card['difficulty'], card['difficulty_reason'])
"
```

Expected: `difficulty` reflects the worst finding (High/Medium depending on the residency rule's
severity), and `difficulty_reason` names the specific edge/rule — confirms FR-004.

## Scenario 3 — uncovered edge produces a Gap Record (User Story 4)

```bash
uv run python -c "
from app.kg_lib.verdict_card import generate_verdict_card
import json, pathlib
generate_verdict_card('some-unmapped-pairing>cloud-sql')
lines = pathlib.Path('app/references/gap_report.jsonl').read_text().splitlines()
print(json.loads(lines[-1]))
"
```

Expected: last line of `gap_report.jsonl` describes the unresolved element — confirms FR-008/FR-009.

## Scenario 4 — mismatch detection (User Story 2)

```bash
uv run python -c "
from app.kg_lib.verdict_card import generate_verdict_card
card = generate_verdict_card('cloud-run>cloud-sql', stated_needs='real-time updates')
print(card['mismatches'])
"
```

Expected: a mismatch entry naming the stated need vs. the actual fit, if the rule table flags this
combination — confirms FR-005.

## Scenario 5 — checklist correspondence (User Story 3)

```bash
uv run python -c "
from app.kg_lib.verdict_card import generate_verdict_card
card = generate_verdict_card('cloud-run>cloud-sql', data_residency='eu')
non_proven = [f for f in card['findings'] if f['tier'] != 'Proven']
assert len(card['checklist']) == len(non_proven)
print('OK', len(card['checklist']))
"
```

Expected: checklist length equals count of non-Proven findings — confirms SC-004.

## Agent-level check (via ADK)

```bash
uv run agents-cli run . --message "We want cloud-run talking to cloud-sql, EU residency, client asked for real-time updates via WebSockets"
```

Expected: reply presents a card-shaped answer (difficulty, tiered findings, mismatch, checklist) rather
than a narrative paragraph — confirms the agent instruction update, not just the tool.

## Regression fixtures

Once `test_verdict_card.py` exists, `uv run pytest tests/unit/test_verdict_card.py` should cover at
least one case per tier, one mismatch case, one all-proven checklist-empty case, and one Gap Record
case — mirroring the parent skill's `check_kg.py` regression discipline referenced in plan.md.
