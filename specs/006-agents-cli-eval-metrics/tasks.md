# Tasks: Agent CLI Evaluation Metrics Conversion

**Input**: Design documents from `/specs/006-agents-cli-eval-metrics/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included because specification requires schema/coverage validation and measurable acceptance checks.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish target dataset and evaluation workspace without changing production agent behavior.

- [X] T001 [P] Create converted dataset file at `cloud-arch-validator-agent/tests/eval/datasets/architecture-validator-dataset.json` using Agent CLI `eval_cases` schema.
- [ ] T002 [P] Add ignored artifact run directories for generated traces and grades under `cloud-arch-validator-agent/artifacts/traces/` and `cloud-arch-validator-agent/artifacts/grades/` without committing generated outputs.
- [X] T003 [P] Document target dataset and migration workflow locations in `cloud-arch-validator-agent/tests/eval/datasets/README.md`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build shared source-to-target validation and rubric conventions before story-specific metric work.

- [X] T004 Add source/target dataset validator in `cloud-arch-validator-agent/tests/eval/validate_dataset.py` checking 9-case count, unique IDs, exact prompt preservation, and assertion coverage.
- [X] T005 [P] Define stable rubric ID and assertion-description conventions in `cloud-arch-validator-agent/tests/eval/rubrics.py`, including explicit handling for tool evidence, Indonesian language, uncertainty, assumptions, and follow-up conditions.
- [X] T006 [P] Add unit tests for dataset identity and assertion mapping in `cloud-arch-validator-agent/tests/unit/test_eval_dataset.py`.
- [X] T007 Configure common Agent CLI metric names and `source_assertions` rubric-group linkage in `cloud-arch-validator-agent/tests/eval/eval_config.yaml` without changing agent runtime configuration.
- [X] T008 [P] Add contract validation assertions for dataset and metric configuration in `cloud-arch-validator-agent/tests/unit/test_eval_contract.py` based on `specs/006-agents-cli-eval-metrics/contracts/evaluation-contract.md`.

**Checkpoint**: Source-to-target invariants and metric contract validated locally; user-story implementation can proceed.

---

## Phase 3: User Story 1 - Run Existing Evaluation Cases Through Agent CLI (Priority: P1) 🎯 MVP

**Goal**: Run all nine existing cases through Agent CLI while preserving IDs and prompts.

**Independent Test**: Load target dataset, compare it against `cloud-arch-validator-agent/app/evals/evals.json`, then generate traces and confirm every case ID appears or has an explicit execution error.

### Tests for User Story 1

- [X] T009 [P] [US1] Test exact source-to-target case count, IDs, and prompt equality in `cloud-arch-validator-agent/tests/unit/test_eval_dataset.py`.
- [X] T010 [P] [US1] Test malformed, duplicate-ID, missing-prompt, and missing-case failures in `cloud-arch-validator-agent/tests/unit/test_eval_dataset.py`.

### Implementation for User Story 1

- [X] T011 [US1] Convert all nine records from `cloud-arch-validator-agent/app/evals/evals.json` into `cloud-arch-validator-agent/tests/eval/datasets/architecture-validator-dataset.json` with unchanged prompt text.
- [X] T012 [US1] Add source assertion rubrics to each target case in `cloud-arch-validator-agent/tests/eval/datasets/architecture-validator-dataset.json` with one rubric per source assertion.
- [X] T013 [US1] Add a documented generation command and expected per-case trace behavior to `cloud-arch-validator-agent/tests/eval/datasets/README.md`.
- [X] T014 [US1] Run local dataset validation and Agent CLI generation; record failures as case-specific errors instead of treating missing traces as passes.

**Checkpoint**: MVP delivers reproducible Agent CLI input covering all source cases.

---

## Phase 4: User Story 2 - Grade Case-Specific Behavior (Priority: P1)

**Goal**: Grade every source assertion through explicit case rubrics plus broad response/tool metrics.

**Independent Test**: Grade generated traces and verify case-specific outcomes identify failed criteria, including injected failures for unknown-service handling and response language.

### Tests for User Story 2

- [X] T015 [P] [US2] Test rubric-group presence and one-to-one assertion mapping in `cloud-arch-validator-agent/tests/unit/test_eval_dataset.py`.
- [X] T016 [P] [US2] Test custom rubric metric output for passing, failing, missing-trace, and judge-error instances in `cloud-arch-validator-agent/tests/eval/test_metrics.py`.
- [ ] T017 [P] [US2] Add fixture traces with deliberate unknown-service, wrong-language, provider-default, and uncovered-finding failures in `cloud-arch-validator-agent/tests/eval/fixtures/`.

### Implementation for User Story 2

- [X] T018 [US2] Implement case-specific rubric metric support in `cloud-arch-validator-agent/tests/eval/metrics.py` or extend `response_quality.py` while preserving existing metric behavior.
- [X] T019 [US2] Configure `final_response_quality`, `instruction_following`, `tool_use_quality`, and applicable grounding/hallucination metrics in `cloud-arch-validator-agent/tests/eval/eval_config.yaml`.
- [X] T020 [US2] Configure rubric metric to reference `source_assertions` in `cloud-arch-validator-agent/tests/eval/eval_config.yaml` and ensure missing rubric groups are reported visibly.
- [X] T021 [US2] Encode E01–E09 assertions with evidence-specific descriptions covering required tools, deterministic outputs, caveats, Indonesian replies, assumptions, uncertainty tiers, mismatch detection, and Gap Report behavior in `cloud-arch-validator-agent/tests/eval/datasets/architecture-validator-dataset.json`.
- [X] T022 [US2] Represent E02 post-choice translation behavior as an explicit continued-interaction case or documented unverified condition in `cloud-arch-validator-agent/tests/eval/datasets/architecture-validator-dataset.json` and `cloud-arch-validator-agent/tests/eval/datasets/README.md`.
- [ ] T023 [US2] Run Agent CLI grading against generated traces and inspect per-case rubric results plus aggregate metrics under `cloud-arch-validator-agent/artifacts/grades/`.

**Checkpoint**: Assertion-level behavior visible; broad score cannot mask missing or failed criteria.

---

## Phase 5: User Story 3 - Preserve Evaluation Maintenance Workflow (Priority: P2)

**Goal**: Make generation, grading, comparison, and failure analysis repeatable from project documentation.

**Independent Test**: Follow README commands from `cloud-arch-validator-agent/`, produce trace/grade artifacts, compare two result files, and attribute differences to case IDs.

### Tests for User Story 3

- [X] T024 [P] [US3] Validate documented dataset/config paths and command examples in `cloud-arch-validator-agent/tests/unit/test_eval_workflow_docs.py`.
- [ ] T025 [P] [US3] Test result comparison fixture preserves case IDs and exposes missing-case regressions in `cloud-arch-validator-agent/tests/eval/fixtures/`.

### Implementation for User Story 3

- [X] T026 [US3] Update `cloud-arch-validator-agent/tests/eval/datasets/README.md` with prerequisites, generate, grade, compare, and analyze commands from `specs/006-agents-cli-eval-metrics/quickstart.md`.
- [X] T027 [US3] Update `cloud-arch-validator-agent/README.md` with the migrated evaluation entry point and artifact locations, without documenting credentials or committing secrets.
- [X] T028 [US3] Add explicit validation/error guidance for missing credentials, malformed datasets, unavailable judge services, missing traces, and unsupported follow-up cases in `cloud-arch-validator-agent/tests/eval/datasets/README.md`.
- [ ] T029 [US3] Run documented workflow against baseline and candidate grade results; verify compare output maps changes to case IDs and metrics.

**Checkpoint**: Contributors can repeat evaluation workflow without manual dataset/config edits.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Confirm migration quality, preserve deterministic behavior, and finish documentation.

- [ ] T030 [P] Run `uv run pytest tests/unit tests/integration` from `cloud-arch-validator-agent/` and confirm no production behavior regressions.
- [ ] T031 [P] Run `uv run ruff check app tests` from `cloud-arch-validator-agent/` and fix only migration-related lint issues.
- [X] T032 Run local dataset/contract checks and confirm all 9 cases and all 34 source assertions remain mapped.
- [ ] T033 Run final Agent CLI generate/grade workflow when credentials and services are available; save results outside source control and report unavailable dependencies explicitly.
- [X] T034 [P] Review `specs/006-agents-cli-eval-metrics/quickstart.md` against actual commands and update stale paths or flags.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T001–T003 can run in parallel.
- **Foundational (Phase 2)**: Depends on Setup; T005/T006/T008 can run in parallel after target path exists; T007 depends on rubric naming from T005.
- **User Story 1 (Phase 3)**: Depends on foundational validation conventions; T009/T010 can run in parallel, then T011–T014.
- **User Story 2 (Phase 4)**: Depends on US1 dataset and rubric records; T015–T017 can run in parallel, then T018–T023.
- **User Story 3 (Phase 5)**: Depends on stable dataset/config paths; T024/T025 can run in parallel, then T026–T029.
- **Polish (Phase 6)**: Depends on desired stories complete; T030/T031/T034 can run in parallel before final T032/T033.

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational only. MVP story.
- **US2 (P1)**: Depends on US1 target dataset and source rubric mapping.
- **US3 (P2)**: Depends on stable US1/US2 commands and configuration, but documentation tests can begin after paths are finalized.

### Parallel Opportunities

- Setup file/document tasks T001–T003.
- Foundational rubric, unit, and contract tasks T005, T006, T008 after T004 path conventions.
- US1 validation tests T009–T010.
- US2 fixture, mapping, and metric tests T015–T017.
- US3 documentation and comparison tests T024–T025.
- Final test, lint, and quickstart review T030–T031 and T034.

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and Foundational phases.
2. Convert all nine source cases and assertions.
3. Run local validation and Agent CLI generation.
4. Stop and verify every case ID produces trace or explicit error.

### Incremental Delivery

1. Add US1 dataset conversion and trace generation.
2. Add US2 case-specific rubrics and grading.
3. Add US3 repeatable documentation and compare workflow.
4. Run Polish checks and final evaluation.

### Notes

- `[P]` marks tasks safe to run in parallel on different files or independent fixtures.
- Every task includes concrete repository path.
- No task changes deterministic architecture verdict code or production agent decision logic.
