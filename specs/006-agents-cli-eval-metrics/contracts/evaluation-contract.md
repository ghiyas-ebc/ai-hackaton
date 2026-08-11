# Evaluation Contract

## Inputs

- Source reference: `cloud-arch-validator-agent/app/evals/evals.json`
- Target dataset: `cloud-arch-validator-agent/tests/eval/datasets/<name>.json`
- Eval config: `cloud-arch-validator-agent/tests/eval/eval_config.yaml`

## Dataset Contract

Target JSON MUST contain top-level `eval_cases`. Each case MUST include:

- unique `eval_case_id`
- `prompt.role: user`
- `prompt.parts[0].text`
- `rubric_groups.source_assertions.rubrics` for all assertion-bearing cases

Each rubric MUST include `rubric_id` and a testable property description.

## Metric Contract

Configured metrics MUST include a case-specific rubric metric referencing `source_assertions`. Broad metrics MAY supplement it, but cannot replace it. Metric errors MUST remain visible as errors.

## Commands

```bash
cd cloud-arch-validator-agent
agents-cli eval generate --dataset tests/eval/datasets/<name>.json --output artifacts/traces/<run>/
agents-cli eval grade --config tests/eval/eval_config.yaml --traces artifacts/traces/<run>/ --output artifacts/grades/<run>/
agents-cli eval compare artifacts/grades/<baseline>.json artifacts/grades/<run>.json
agents-cli eval analyze artifacts/grades/<run>.json
```

## Compatibility Contract

Conversion MUST preserve source IDs, prompts, and assertion coverage. Conversion MUST NOT alter agent runtime tools or deterministic validation code.
