# Research: Agent CLI Evaluation Metrics Conversion

## Decision 1: Use Agent CLI EvaluationDataset records with per-case rubric groups

- **Decision**: Convert each source case into one dataset case under `cloud-arch-validator-agent/tests/eval/datasets/`, preserving `eval_case_id` and prompt. Store source assertions as named rubric entries in a per-case rubric group.
- **Rationale**: Agent CLI supports prompt-bearing cases and `rubric_groups` referenced by an LLM metric. This preserves case-specific behavior without fabricating golden responses for open-ended architecture conversations.
- **Alternatives considered**:
  - Bare prompts plus general quality only: rejected because it loses assertion-level coverage.
  - Golden final responses for every case: rejected because many cases intentionally require questions, assumptions, caveats, or later user choices rather than one canonical answer.
  - A separate dataset per source case: rejected because one consolidated dataset supports one generate/grade workflow and stable comparison.

## Decision 2: Select managed metrics by observable behavior

- **Decision**: Configure final response quality, instruction following, tool-use quality, and hallucination/grounding checks where supported; add one custom rubric metric bound to the per-case rubric group.
- **Rationale**: Built-in metrics cover broad response and trajectory behavior. Case rubrics encode project-specific requirements such as Indonesian replies, deterministic tool invocation, explicit uncertainty, and no provider guessing.
- **Alternatives considered**:
  - Keep only `custom_response_quality`: rejected because its broad 1–5 score cannot prove individual assertions.
  - Use exact response matching: rejected for non-deterministic, open-ended architecture advice.
  - Put every criterion into one global prompt: rejected because it would apply irrelevant criteria to unrelated cases.

## Decision 3: Represent multi-turn requirements as explicit test conditions

- **Decision**: Keep initial cases as single-turn where their expected behavior is observable in the first response. Mark cases requiring a later user choice as multi-turn scenarios or a documented follow-up validation case; never mark unobserved post-choice behavior as passed.
- **Rationale**: E02 explicitly expects behavior after user choices. Dataset schema supports `agent_data.turns`, while a single initial prompt cannot verify later translation output.
- **Alternatives considered**:
  - Invent a user choice during conversion: rejected because it changes source behavior and hides clarification quality.
  - Drop post-choice assertions: rejected because it silently loses source coverage.

## Decision 4: Keep source eval JSON as migration reference, not runtime dependency

- **Decision**: Add a validation test or conversion check that compares source IDs/prompts/assertion counts against target records. Target dataset and config become the Agent CLI execution inputs; source file remains reference until migration is accepted.
- **Rationale**: A stable comparison catches silent omissions and prompt changes without coupling runtime grading to two formats.
- **Alternatives considered**:
  - Dynamically transform source JSON at every eval run: rejected because it obscures the reviewed dataset and makes generated artifacts less reproducible.
  - Delete source file immediately: rejected because migration needs an auditable baseline.

## Decision 5: Preserve deterministic verdict boundary

- **Decision**: Metrics inspect generated traces and tool outputs only. They do not replace `validate.py`, `translate.py`, or verdict-card decision logic.
- **Rationale**: Constitution Principle I forbids LLM-decided verdicts. Evaluation may judge whether agent followed deterministic tool results, but production decisions stay in rule code.
- **Alternatives considered**:
  - Ask judge to decide whether architecture is valid: rejected as a direct violation of Verdict-Not-Guess.

## Decision 6: Validate locally before managed evaluation

- **Decision**: Add schema/coverage checks that require nine unique cases, exact prompts, and complete assertion mapping before invoking Agent CLI. Use documented generate, grade, compare, and analyze commands for end-to-end validation.
- **Rationale**: Local checks provide fast failure for migration defects; managed evaluation then measures agent behavior and requires credentials/services.
- **Alternatives considered**:
  - Depend only on remote grade errors: rejected because malformed or incomplete migration would be discovered late and ambiguously.
