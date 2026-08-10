---

description: "Task list for Unicode Architecture Renderer"
---

# Tasks: Unicode Architecture Renderer

**Input**: Design documents from `/specs/005-unicode-architecture-renderer/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/agent-tools.md, quickstart.md

**Tests**: Included. Spec success criteria require deterministic fixture coverage, ASCII validation, width checks, edge-case safety, and agent tool inspection.

**Organization**: Tasks grouped by user story. User stories can be validated independently after shared setup.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other marked tasks after dependencies are satisfied.
- **[Story]**: User story mapping; setup/foundational/polish tasks have no story label.
- Every task includes exact repository file path.

## Phase 1: Setup

**Purpose**: Confirm existing agent and validator baseline before adding presentation code.

- [X] T001 Run existing agent unit and integration tests with `cloud-arch-validator-agent/.venv/bin/pytest` and record baseline in task notes.
- [X] T002 [P] Run `cloud-architecture-validator-create-architect/scripts/check_kg.py` and confirm clean integrity, 37/37 regression, and required coverage before renderer changes.
- [X] T003 [P] Inspect `cloud-arch-validator-agent/app/kg_lib/validate.py` report fields and document any contract mismatch in `specs/005-unicode-architecture-renderer/research.md`.

## Phase 2: Foundational

**Purpose**: Establish pure renderer boundaries and shared formatting policy before story-specific behavior.

- [X] T004 Create pure renderer module skeleton with public render entry point and no imports from Draw.io, SVG, icon, browser, or network code in `cloud-arch-validator-agent/app/renderer.py`.
- [X] T005 Define Unicode/ASCII glyph sets, minimum valid width, deterministic ordering policy, control-character sanitization, and ASCII transliteration/replacement helpers in `cloud-arch-validator-agent/app/renderer.py`.
- [X] T006 [P] Add renderer fixture helpers for synthetic reports, resolved nodes, unknown endpoints, findings, and edge cases in `cloud-arch-validator-agent/tests/unit/test_renderer.py`.

**Checkpoint**: Pure presentation boundary and formatting policy ready; no validator verdict logic duplicated.

---

## Phase 3: User Story 1 - Readable terminal architecture (Priority: P1) 🎯 MVP

**Goal**: Return deterministic terminal flowchart text with labeled service nodes, directed edges, metadata, and findings.

**Independent Test**: Call renderer/tool with known multi-service architecture; assert every node and edge identity, provider/category metadata, directional output, findings, terminal format, and deterministic repeatability.

### Tests for User Story 1

- [X] T007 [P] [US1] Add linear and branching graph fixtures asserting every resolved service renders as a labeled node in `cloud-arch-validator-agent/tests/unit/test_renderer.py`.
- [X] T008 [P] [US1] Add assertions for provider/category metadata, directional source-to-target edge rows, and stable node/edge ordering in `cloud-arch-validator-agent/tests/unit/test_renderer.py`.
- [X] T009 [P] [US1] Add findings fixture asserting rule id, severity, and message remain adjacent to affected edge/node without severity changes in `cloud-arch-validator-agent/tests/unit/test_renderer.py`.
- [X] T010 [P] [US1] Add repeated-render byte equality test for identical report/options in `cloud-arch-validator-agent/tests/unit/test_renderer.py`.

### Implementation for User Story 1

- [X] T011 [US1] Implement deterministic node normalization and metadata label generation in `cloud-arch-validator-agent/app/renderer.py`.
- [X] T012 [US1] Implement bounded node-box rendering with Unicode borders, wrapped labels, and stable component/layout ordering in `cloud-arch-validator-agent/app/renderer.py`.
- [X] T013 [US1] Implement directed edge rendering that preserves source/target identity and duplicate edge records in `cloud-arch-validator-agent/app/renderer.py`.
- [X] T014 [US1] Implement node, edge, and global finding annotation rendering that copies supplied verdict/severity/rule/message fields in `cloud-arch-validator-agent/app/renderer.py`.
- [X] T015 [US1] Add `render_ascii_diagram(edges, environment, ascii_only, width)` wrapper that calls existing `_parse_edges`, deterministic validator, KG resolution, and pure renderer in `cloud-arch-validator-agent/app/tools.py`.
- [X] T016 [US1] Return contract metadata (`format`, `ascii_only`, `width`, node/edge/finding counts, and `diagram`) from `render_ascii_diagram` in `cloud-arch-validator-agent/app/tools.py`.
- [X] T017 [US1] Add `render_ascii_diagram` to `ALL_TOOLS` and remove `render_drawio_diagram` from `ALL_TOOLS` in `cloud-arch-validator-agent/app/tools.py`.
- [X] T018 [US1] Replace Draw.io instructions with terminal-rendering guidance and preserve no-guessing instructions in `cloud-arch-validator-agent/app/agent.py`.
- [X] T019 [US1] Update agent tool wrapper tests for terminal contract and Draw.io absence in `cloud-arch-validator-agent/tests/unit/test_tools.py`.

**Checkpoint**: P1 terminal renderer independently usable for ordinary linear and branching architectures.

---

## Phase 4: User Story 2 - Strict ASCII fallback (Priority: P2)

**Goal**: Provide structurally equivalent output containing only ASCII characters and respecting configured width.

**Independent Test**: Render representative architecture with `ascii_only=True`; assert `diagram.isascii()`, matching node/edge identities and order, no replacement glyphs, and line-width compliance.

### Tests for User Story 2

- [X] T020 [P] [US2] Add strict ASCII output tests covering borders, arrows, metadata, findings, and non-ASCII labels/messages in `cloud-arch-validator-agent/tests/unit/test_renderer.py`.
- [X] T021 [P] [US2] Add long-label and multiline-finding fixtures asserting sanitized wrapping and maximum configured line width in `cloud-arch-validator-agent/tests/unit/test_renderer.py`.
- [X] T022 [P] [US2] Add invalid-small-width behavior test asserting documented clear error or minimum-width handling in `cloud-arch-validator-agent/tests/unit/test_renderer.py`.
- [X] T023 [US2] Add tool-level ASCII and width contract tests in `cloud-arch-validator-agent/tests/unit/test_tools.py`.

### Implementation for User Story 2

- [X] T024 [US2] Implement ASCII glyph selection and full-output ASCII sanitization for labels, findings, statuses, and arrows in `cloud-arch-validator-agent/app/renderer.py`.
- [X] T025 [US2] Implement word wrapping/truncation policy that preserves service identity and keeps every valid output line within configured width in `cloud-arch-validator-agent/app/renderer.py`.
- [X] T026 [US2] Expose and validate `ascii_only` and `width` options through `render_ascii_diagram` without changing validator results in `cloud-arch-validator-agent/app/tools.py`.

**Checkpoint**: P2 strict ASCII output independently usable in plain-text environments.

---

## Phase 5: User Story 3 - Honest unusual/incomplete graphs (Priority: P3)

**Goal**: Render unknown services, uncovered edges, cycles, disconnected components, duplicate edges, and empty input without guessing, omission, or exceptions.

**Independent Test**: Run dedicated fixtures for each graph shape and assert explicit statuses, complete node/edge identity, deterministic output, and no exception.

### Tests for User Story 3

- [X] T027 [P] [US3] Add unknown-service fixture asserting visible endpoint and literal `UNKNOWN_SERVICE` status in `cloud-arch-validator-agent/tests/unit/test_renderer.py`.
- [X] T028 [P] [US3] Add uncovered-edge fixture asserting visible directed edge and literal `UNCOVERED` status in `cloud-arch-validator-agent/tests/unit/test_renderer.py`.
- [X] T029 [P] [US3] Add cycle and disconnected-component fixtures asserting all nodes/edges render without recursion or omission in `cloud-arch-validator-agent/tests/unit/test_renderer.py`.
- [X] T030 [P] [US3] Add duplicate-edge and empty-input fixtures asserting explicit duplicate handling and clear empty-diagram message in `cloud-arch-validator-agent/tests/unit/test_renderer.py`.

### Implementation for User Story 3

- [X] T031 [US3] Normalize unresolved connectivity endpoints into visible rendered nodes/edge identities with explicit `UNKNOWN_SERVICE` status in `cloud-arch-validator-agent/app/renderer.py`.
- [X] T032 [US3] Preserve and annotate `UNCOVERED`/`UNKNOWN_SERVICE` connectivity statuses from validator output without inference in `cloud-arch-validator-agent/app/renderer.py`.
- [X] T033 [US3] Implement bounded non-recursive component handling for cycles and disconnected nodes in `cloud-arch-validator-agent/app/renderer.py`.
- [X] T034 [US3] Implement deterministic duplicate-edge representation and explicit empty-architecture output in `cloud-arch-validator-agent/app/renderer.py`.

**Checkpoint**: P3 incomplete and unusual graph shapes render honestly and safely.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate complete feature against spec, preserve legacy internals, and avoid unrelated scope expansion.

- [X] T035 [P] Run `cloud-arch-validator-agent/.venv/bin/pytest cloud-arch-validator-agent/tests/unit` and fix renderer/tool regressions only in feature-scoped files.
- [X] T036 [P] Run `cloud-arch-validator-agent/.venv/bin/pytest cloud-arch-validator-agent/tests/integration` with configured credentials and record result.
- [X] T037 [P] Verify Draw.io implementation remains unchanged and callable only through internal/deprecated code paths; inspect `cloud-arch-validator-agent/app/kg_lib/emit_drawio.py` and `diagram.py`.
- [X] T038 Run quickstart scenarios from `specs/005-unicode-architecture-renderer/quickstart.md` and record pass/fail outcomes.
- [X] T039 Run KG gate after implementation and confirm 37/37 regression and coverage remain unchanged using `cloud-architecture-validator-create-architect/scripts/check_kg.py`.
- [X] T040 Review diff for excluded work; confirm no live eval conversion, dataset replacement, author metadata, KG schema, SVG/icon, browser, or external rendering changes in `git diff --stat` and targeted file review.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; baseline first.
- **Foundational (Phase 2)**: Depends on Setup; blocks story work.
- **User Story 1 (Phase 3)**: Depends on Foundational; MVP and primary integration path.
- **User Story 2 (Phase 4)**: Depends on Foundational and renderer entry point; can proceed alongside US1 tests once shared renderer skeleton exists, but final tool tests depend on US1 wrapper.
- **User Story 3 (Phase 5)**: Depends on Foundational and renderer entry point; edge-case tests/implementation can proceed alongside US2 after shared helpers exist.
- **Polish (Phase 6)**: Depends on all selected stories.

### User Story Dependencies

- **US1 (P1)**: No dependency on another story after foundational phase.
- **US2 (P2)**: Reuses US1 renderer/tool contract; must not alter verdict logic.
- **US3 (P3)**: Reuses US1 normalization and US2 sanitization; behavior independently testable with synthetic reports.

### Within Each User Story

- Tests written before corresponding implementation.
- Pure renderer logic before tool wrapper changes.
- Tool registry/instruction updates after wrapper exists.
- Story checkpoint tests pass before polish.

### Parallel Opportunities

- T002 and T003 can run alongside T001.
- T006 can run alongside T004/T005 because it only creates test fixtures.
- T007–T010 can run in parallel within `test_renderer.py` before US1 implementation.
- T020–T022 can run in parallel; T023 follows wrapper contract availability.
- T027–T030 can run in parallel as independent fixtures.
- T035–T037 can run in parallel after implementation; T038/T039 follow code stabilization.

## Parallel Example: User Story 1

```text
Task: Add linear/branching node fixture tests in cloud-arch-validator-agent/tests/unit/test_renderer.py
Task: Add metadata/directed-edge tests in cloud-arch-validator-agent/tests/unit/test_renderer.py
Task: Add finding adjacency tests in cloud-arch-validator-agent/tests/unit/test_renderer.py
Task: Add deterministic repeatability test in cloud-arch-validator-agent/tests/unit/test_renderer.py
```

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Setup and Foundational phases.
2. Complete US1 tests and implementation.
3. Run unit tests and quickstart Scenario 1.
4. Stop for demo: terminal Unicode renderer available; Draw.io no longer agent-exposed.

### Incremental Delivery

1. Add US1 for ordinary terminal diagrams.
2. Add US2 for strict ASCII and width guarantees.
3. Add US3 for honest graph edge cases.
4. Run polish gates and full regression checks.

### Scope Guard

Do not convert live evals, replace generic dataset, fill author metadata, alter validation rules/KG schema, or remove internal Draw.io assets as part of this feature.

## Notes

- `[P]` means different files or independent test sections with no incomplete dependency.
- Renderer must remain presentation-only; validator remains sole verdict source.
- Existing Draw.io test may remain as internal compatibility coverage, but agent registry must exclude its function.
