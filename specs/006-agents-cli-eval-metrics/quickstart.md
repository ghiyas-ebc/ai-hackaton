# Quickstart: Validate Evaluation Conversion

## Prerequisites

- Python environment installed with `uv`.
- Agent CLI installed and available as `agents-cli`.
- Agent credentials configured in `cloud-arch-validator-agent/.env`.
- Agent project dependencies installed.

## 1. Validate dataset structure

From repository root, inspect source and target counts, IDs, prompts, and assertion mappings with the migration validation test/check introduced by implementation.

Expected result: 14 source cases, 14 target cases, unique IDs, exact prompt preservation (or, for the one Shape-B case, exact prior-turn and follow-up preservation), zero unmapped assertions. See the 2026-08-15 addendum in `plan.md` — this count grew from the original 9 twice: once when `E02b-cross-cloud-choices` was added, again when `E10`-`E13` closed a curator/explorer coverage gap.

## 2. Generate traces

```bash
cd cloud-arch-validator-agent
set -a; . ./.env; set +a
agents-cli eval generate \
  --dataset tests/eval/datasets/<converted-dataset>.json \
  --output artifacts/traces/<run>/
```

Expected result: trace output identifies each source case ID. Missing credentials or agent failures exit visibly and do not count as passes.

## 3. Grade traces

```bash
agents-cli eval grade \
  --config tests/eval/eval_config.yaml \
  --traces artifacts/traces/<run>/ \
  --output artifacts/grades/<run>/
```

Expected result: configured broad metrics plus source-assertion rubric results. Inspect per-case criterion outcomes; aggregate score alone is insufficient.

## 4. Compare runs

```bash
agents-cli eval compare \
  artifacts/grades/<baseline>.json \
  artifacts/grades/<run>.json
```

Expected result: changes attributable to case IDs and metric names, with no silent missing-case improvement.

## 5. Analyze failures

```bash
agents-cli eval analyze artifacts/grades/<run>.json
```

Use when enough failures exist to cluster root causes. Do not use analysis output as production verdict logic.

## Acceptance Checks

- Indonesian prompts remain unchanged.
- E03 grades explicit unknown-service handling.
- E05 grades residency and production implications.
- E06 grades provider clarification instead of defaulting to GCP.
- E08 grades stated assumptions and uncertainty tier.
- E09 grades mismatch and automatic Gap Report behavior.
- E02 grades that the ambiguous Pub/Sub and Cloud Load Balancing choices are surfaced, not silently picked; E02b is a genuine Shape-B continuation of E02's own conversation, and its follow-up assertions (choices honoured, VNet Integration) are only evaluated with that continuation present — not on E02's initial response alone.
- E10 grades a curator happy-path add (`add_service_to_kg` written, provenance unverified).
- E11 grades the curator's `unknown_role` refusal on a typo'd role, including the `did_you_mean` correction.
- E12 grades the curator's `role_warning` path for a correctly-spelled but purely descriptive role.
- E13 grades explorer's typed `search_services`/`query_services` filtering and `check_kg_health` reporting.
- `kg_write_grounding` (E10-E13) and `verdict_grounding` (all cases) both fail a case whose response claims something the trace does not back, independent of judge opinion.
- Existing deterministic unit/integration tests remain unchanged and pass.
