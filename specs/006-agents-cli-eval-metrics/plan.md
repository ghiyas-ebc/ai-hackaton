# Implementation Plan: Agent CLI Evaluation Metrics Conversion

**Branch**: `006-agents-cli-eval-metrics` | **Date**: 2026-08-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-agents-cli-eval-metrics/spec.md`

## Summary

Convert nine architecture-validator evaluation cases from `app/evals/evals.json` into Agent CLI EvaluationDataset records. Preserve IDs and Indonesian prompts, encode every source assertion as a case-specific rubric, cover tool and response behavior with configured metrics, and add migration validation so omissions, prompt drift, and unsupported multi-turn expectations fail visibly. Keep deterministic validation code outside evaluation-judge decision paths.

## Technical Context

**Language/Version**: Python 3.11–3.13, JSON, YAML

**Primary Dependencies**: `agents-cli` 1.1.x workflow, existing Google ADK project, PyYAML, pytest

**Storage**: Versioned JSON datasets, YAML evaluation config, generated trace/grade artifact directories

**Testing**: pytest for local conversion/schema checks; `agents-cli eval generate`, `grade`, `compare`, and `analyze` for end-to-end evaluation

**Target Platform**: Local Agent CLI execution with optional managed grading services

**Project Type**: Agent evaluation dataset/configuration and validation tooling

**Performance Goals**: Dataset validation completes locally in under 5 seconds; evaluation runtime remains governed by Agent CLI and judge service

**Constraints**: No production runtime changes; no credentials committed; no fabricated golden responses; missing traces and judge errors cannot pass; source prompts and IDs stay stable

**Scale/Scope**: 9 source cases, 34 source assertions, one consolidated target dataset, case-specific rubric coverage, existing agent project only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Verdict-Not-Guess**: PASS. Rubrics evaluate observed agent adherence to deterministic tool output; they do not decide architecture validity.
- **II. Evidence-Grounded History**: PASS. Rubrics require trace evidence and do not invent reference answers or historical facts.
- **III. Human Gate on Judgment Calls**: PASS. Evaluation reports behavior; it does not promote judge output into final organizational knowledge or judgment fields.
- **IV. Read-Only by Default, Explicit Write Path**: PASS. Generation/grading read agent behavior; E09 may verify existing Gap Report behavior but conversion adds no automatic knowledge write.
- **V. Layered Transparency**: PASS. Per-case rubric outcomes remain visible beside broad metrics; aggregate score is supplementary.

No gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/006-agents-cli-eval-metrics/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── evaluation-contract.md
└── tasks.md                    # /speckit-tasks output
```

### Source Code (repository root)

```text
cloud-arch-validator-agent/
├── app/evals/evals.json                    # source cases, migration reference
├── tests/eval/datasets/
│   ├── <converted-dataset>.json            # Agent CLI target dataset
│   └── README.md                           # workflow documentation
├── tests/eval/eval_config.yaml             # selected metrics
├── tests/eval/metrics/ or response_quality.py # case-rubric/custom metric support
├── tests/unit/                             # dataset conversion/schema tests
└── artifacts/
    ├── traces/                             # generated, ignored execution traces
    └── grades/                             # generated, ignored grade results
```

**Structure Decision**: Keep source cases under `app/evals`, target evaluation inputs under existing `tests/eval`, and generated outputs under existing `artifacts`. Add only migration-specific validation/metric support near existing evaluation tests; no production agent modules change.

## Phase 0: Research Complete

- Confirmed Agent CLI dataset supports `eval_cases`, exact prompt content, and per-case `rubric_groups`.
- Confirmed rubric metric can reference `source_assertions` group.
- Confirmed broad metrics supplement, not replace, case-specific criteria.
- Resolved E02 follow-up requirement by preserving it as explicit multi-turn/unverified condition.
- Documented decisions in [research.md](research.md).

## Phase 1: Design Complete

- Defined source, target, rubric, trace, and grade entities in [data-model.md](data-model.md).
- Defined dataset, metric, command, and compatibility contract in [contracts/evaluation-contract.md](contracts/evaluation-contract.md).
- Defined runnable validation workflow in [quickstart.md](quickstart.md).
- Agent context points to this plan.

## Phase 2: Implementation Outline

1. Build target dataset from source cases without changing IDs/prompts.
2. Encode all source assertions as stable rubric IDs and descriptions; identify E02 continuation condition.
3. Add local migration validation for count, uniqueness, exact prompts, assertion coverage, and rubric metric linkage.
4. Update eval configuration and README commands for selected metrics and artifact paths.
5. Run local validation and existing unit/integration tests.
6. Run Agent CLI generation and grading when credentials/services available; inspect every case and compare baseline.

## Post-Design Constitution Re-check

All five principles remain PASS. Design keeps verdict authority in deterministic tools, requires trace-backed evidence, exposes uncertainty and failures per case, introduces no implicit knowledge-base write, and separates detailed rubric outcomes from aggregate scores.

## Complexity Tracking

No constitution violations or complexity exceptions.
