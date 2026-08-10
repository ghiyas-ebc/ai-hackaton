# Feature Specification: Convert Evaluation Cases to Agent CLI Metrics

**Feature Branch**: `006-agents-cli-eval-metrics`

**Created**: 2026-08-10

**Status**: Draft

**Input**: User description: "convert the eval.json to agents-cli eval metrics"

## User Scenarios & Testing

### User Story 1 - Run Existing Evaluation Cases Through Agent CLI (Priority: P1)

As an engineer maintaining the cloud architecture validator agent, I want the existing evaluation cases converted into the Agent CLI dataset format so I can run them with the standard generation and grading commands without rewriting scenarios by hand.

**Why this priority**: Existing behavioral coverage must remain available after the evaluation tooling changes.

**Independent Test**: Run Agent CLI evaluation generation against the converted dataset and confirm every source evaluation case produces a traceable result with its original identifier.

**Acceptance Scenarios**:

1. **Given** the source evaluation file contains nine cases, **When** the converted dataset is loaded, **Then** it contains nine uniquely identified evaluation cases with equivalent user prompts.
2. **Given** a valid converted dataset, **When** evaluation generation runs, **Then** each case completes or reports an explicit execution failure tied to its case identifier.

### User Story 2 - Grade Case-Specific Behavior (Priority: P1)

As an engineer, I want each source assertion represented as a measurable metric or rubric so grading checks required behavior rather than only general response quality.

**Why this priority**: General quality scores can hide failures in tool selection, language, safety, and uncertainty handling.

**Independent Test**: Grade generated traces and inspect results for case-level assertion outcomes, including failures that identify which expected behavior was not met.

**Acceptance Scenarios**:

1. **Given** a case with multiple source assertions, **When** grading runs, **Then** results expose pass/fail evidence for each assertion or an equivalent case-specific rubric outcome.
2. **Given** a trace where the agent guesses instead of reporting an unknown service, **When** the unknown-service case is graded, **Then** its uncertainty-handling assertion fails rather than being masked by an aggregate score.
3. **Given** a trace where the agent answers in a language different from the user's language, **When** the language assertion is graded, **Then** the relevant assertion fails visibly.

### User Story 3 - Preserve Evaluation Maintenance Workflow (Priority: P2)

As an engineer, I want evaluation configuration and datasets located in the project's existing evaluation directories so future contributors can generate, grade, compare, and analyze results using documented Agent CLI commands.

**Why this priority**: Consistent placement and commands reduce drift between source scenarios, generated traces, and graded results.

**Independent Test**: Follow the evaluation README from a clean checkout, run the documented commands with configured credentials, and locate generated traces and grade results in the expected artifact directories.

**Acceptance Scenarios**:

1. **Given** the evaluation configuration and dataset are present, **When** a contributor runs the documented generate and grade commands, **Then** commands resolve the dataset and configured metrics without manual file edits.
2. **Given** a baseline grade result and a later grade result, **When** the contributor runs comparison, **Then** metric changes are attributable to evaluation case identifiers.

### Edge Cases

- Source case identifiers must remain unique and stable across conversions and later edits.
- Prompts containing Indonesian text must remain unchanged; grading must not silently translate or normalize them.
- Assertions requiring a tool call must distinguish calling the required tool from merely mentioning its name in the final response.
- Assertions involving a follow-up user choice must support multi-turn traces or explicitly mark the case as requiring continued interaction rather than treating the initial response as complete.
- Agent execution failures, missing credentials, malformed traces, and unavailable judge services must produce actionable errors and must not be recorded as passing evaluations.
- Aggregate scores must not hide an assertion-level failure or a missing result.
- Reference answers must only be added where deterministic expected text exists; open-ended architecture guidance must use behavior rubrics instead of fabricated golden responses.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST provide an Agent CLI-compatible evaluation dataset derived from every case in the existing evaluation source file.
- **FR-002**: The converted dataset MUST preserve each source case identifier and user prompt exactly, unless the Agent CLI schema requires an equivalent structural representation.
- **FR-003**: The system MUST represent source assertions as explicit, testable grading criteria associated with their originating evaluation case.
- **FR-004**: The evaluation configuration MUST select metrics that cover final response quality, instruction following, tool-use behavior, grounding or hallucination where applicable, and case-specific assertion rubrics.
- **FR-005**: The system MUST support grading both single-turn cases and cases whose expected behavior requires a follow-up turn, without inventing user choices or declaring an unobserved outcome as passing.
- **FR-006**: The system MUST report per-case results and identify failed criteria; aggregate results MUST remain supplementary.
- **FR-007**: The system MUST preserve uncertainty expectations: `UNKNOWN_SERVICE`, `UNCOVERED`, explicit assumptions, and engineering-review escalation MUST be gradable as intentional outcomes rather than generic failures.
- **FR-008**: The system MUST support Indonesian prompts and MUST grade response-language expectations where the source assertion requires them.
- **FR-009**: The system MUST document commands for generating traces, grading traces, comparing result files, and analyzing failures using the project's Agent CLI workflow.
- **FR-010**: The system MUST keep generated traces and grade results separate from source datasets and configuration, with predictable artifact locations.
- **FR-011**: The system MUST fail evaluation setup or grading clearly when required dataset fields, metric configuration, or case identifiers are invalid.
- **FR-012**: The conversion MUST NOT change production verdict logic or move decision-making from deterministic validation tools into an LLM judge; metrics may assess observed behavior but MUST NOT become runtime decision logic.

### Key Entities

- **Source Evaluation Case**: Existing case identifier, user prompt, and behavioral assertions being migrated.
- **Agent CLI Evaluation Case**: Dataset record containing prompt, optional conversation data, and case-specific grading criteria.
- **Assertion Rubric**: Human-readable, testable condition describing expected agent behavior for one source case.
- **Evaluation Metric**: Named grading mechanism producing a score and explanation for a trace or rubric.
- **Evaluation Trace**: Agent execution record containing responses and tool interactions for one case.
- **Grade Result**: Per-case and aggregate metric outcomes generated from a trace.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of source evaluation cases appear exactly once in the converted Agent CLI dataset.
- **SC-002**: 100% of source assertions are represented by an explicit rubric, metric, or documented multi-turn test condition; zero assertions are silently dropped.
- **SC-003**: A clean evaluation run produces identifiable trace and grade-result records for at least 9 of 9 cases when agent and judge dependencies are available; any unavailable dependency is reported as an execution error.
- **SC-004**: A deliberately injected failure in each assertion category is detected in the corresponding case result, with no fewer than 90% of failures attributed to the correct case and criterion during validation testing.
- **SC-005**: Contributors can run documented generation and grading commands from the agent project directory without editing dataset or metric files first.
- **SC-006**: Evaluation migration causes zero changes to deterministic architecture-validation verdicts and existing unit/integration test behavior.

## Assumptions

- The current source evaluation file is `cloud-arch-validator-agent/app/evals/evals.json` and remains the migration source of truth until replacement is reviewed.
- The target Agent CLI dataset lives under `cloud-arch-validator-agent/tests/eval/datasets/` and uses the repository's existing evaluation configuration.
- Existing local custom metrics may remain where they provide useful quality scoring, but they do not replace assertion-specific coverage.
- Agent CLI credentials and judge-service availability are provided by the person running evaluations; this feature does not add credentials or deploy infrastructure.
- Open-ended assertions are best represented as rubrics evaluated against trace evidence, while deterministic exact-answer cases may use references.
- Production behavior, knowledge-graph data, and runtime tool contracts are out of scope.
