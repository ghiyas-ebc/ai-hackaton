# Data Model: Agent CLI Evaluation Metrics

## Source Evaluation Case

Existing record from `cloud-arch-validator-agent/app/evals/evals.json`.

| Field | Type | Rules |
|---|---|---|
| `id` | string | Required; unique; stable; copied to target `eval_case_id`. |
| `prompt` | string | Required; copied exactly into target user content. |
| `assertions` | list[string] | Required; non-empty; every item maps to one rubric or documented multi-turn condition. |

## Agent CLI Evaluation Case

Target record consumed by trace generation.

| Field | Type | Rules |
|---|---|---|
| `eval_case_id` | string | Required; equals source `id`; unique within dataset. |
| `prompt` | Content | Required user message; text equals source prompt. |
| `rubric_groups` | map[string, RubricGroup] | Required for assertion-bearing cases; group name matches configured rubric metric. |
| `agent_data` | AgentData | Optional; used when case needs prior turns or follow-up interaction. |

## Rubric Group

Named set of criteria attached to one evaluation case.

| Field | Type | Rules |
|---|---|---|
| group name | string | Stable, e.g. `source_assertions`. Must match metric `rubric_group_name`. |
| `rubrics` | list[Rubric] | One item per source assertion; no silent drops. |

## Rubric

| Field | Type | Rules |
|---|---|---|
| `rubric_id` | string | Stable, derived from case ID and assertion ordinal or safe slug. |
| `content.property.description` | string | Testable behavior; must identify expected evidence and failure condition. |

## Evaluation Trace

Generated execution record.

| Field | Type | Rules |
|---|---|---|
| case identifier | string | Links trace to target `eval_case_id`. |
| turns/events | structured list | Captures user, agent, and tool activity. Required evidence for tool-use and multi-turn rubrics. |
| final response | model content | Evidence for language, caveats, assumptions, and user-facing outcome. |

## Grade Result

Output record for one case and metric.

| Field | Type | Rules |
|---|---|---|
| case identifier | string | Must link to one source/target case. |
| metric name | string | Configured metric. |
| score | numeric or categorical | Must not convert missing/error result into pass. |
| explanation | string | Identifies evidence and failed criterion where possible. |

## Relationships

- One **Source Evaluation Case** maps to exactly one **Agent CLI Evaluation Case**.
- One source case maps to one rubric group containing exactly all source assertions.
- One target case produces zero or more **Evaluation Traces** across runs.
- One trace produces one result per configured metric.
- One **Grade Result** links back to case ID and rubric ID when assertion-level grading is supported.

## Validation Rules

1. Source and target case counts match: expected 9.
2. IDs are unique in both source and target.
3. Target prompts match source prompts byte-for-byte after JSON parsing.
4. Assertion count per case matches rubric/condition count.
5. Rubric metric group name matches every case's rubric group key.
6. Missing trace, malformed case, missing metric, or judge error is an explicit failure state, never pass.
7. Rubric descriptions assess observed agent behavior and tool evidence; they do not authorize runtime verdict decisions.
