# Quickstart: Validate Evaluation Conversion

## Prerequisites

- Python environment installed with `uv`.
- Agent CLI installed and available as `agents-cli`.
- Agent credentials configured in `cloud-arch-validator-agent/.env`.
- Agent project dependencies installed.

## 1. Validate dataset structure

From repository root, inspect source and target counts, IDs, prompts, and assertion mappings with the migration validation test/check introduced by implementation.

Expected result: 9 source cases, 9 target cases, unique IDs, exact prompt preservation, zero unmapped assertions.

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
- E02 follow-up behavior remains marked unverified until user choice is supplied and subsequent trace is evaluated.
- Existing deterministic unit/integration tests remain unchanged and pass.
