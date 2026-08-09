---
description: "Task list for Verdict Card feature implementation"
---

# Tasks: Verdict Card

**Input**: Design documents from `/specs/001-verdict-card/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/generate_verdict_card.md, quickstart.md

**Tests**: Included — plan.md commits to a pytest regression-fixture discipline mirroring the parent
skill's `check_kg.py` 37/37 pattern, so each story ships fixtures alongside implementation.

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P2/P3/P3) so each is
independently implementable, testable, and demoable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files/functions, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 / US4, matching spec.md's four user stories
- All paths are relative to repo root

## Path Conventions

Single project, additive module inside the existing `cloud-arch-validator-agent/`:

- New module: `cloud-arch-validator-agent/app/kg_lib/verdict_card.py`
- New tests: `cloud-arch-validator-agent/tests/unit/test_verdict_card.py`
- Modified: `cloud-arch-validator-agent/app/tools.py`, `app/agent.py`
- New runtime artifact: `cloud-arch-validator-agent/app/references/gap_report.jsonl` (created at runtime,
  not committed)

---

## Phase 1: Setup

**Purpose**: Scaffold the new module and test file so implementation tasks have somewhere to land

- [X] T001 Create module skeleton (docstring, imports of `kg_lib.validate` and `kg_lib.kg`) in
      cloud-arch-validator-agent/app/kg_lib/verdict_card.py
- [X] T002 [P] Create test file skeleton with a shared fixture that loads the real KG via
      `kg_module.load()` in cloud-arch-validator-agent/tests/unit/test_verdict_card.py
- [X] T003 [P] Add `app/references/gap_report.jsonl` to cloud-arch-validator-agent/.gitignore (runtime
      data, not source)

**Checkpoint**: Module and test file exist and import cleanly.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared data shapes and extraction logic every user story's tasks build on

**⚠️ CRITICAL**: No user story task may start until this phase is complete

- [X] T004 Define `VerdictCard`, `Finding`, `MismatchEntry`, `ChecklistItem`, `GapRecord` dict-shape
      constructors per data-model.md in cloud-arch-validator-agent/app/kg_lib/verdict_card.py
- [X] T005 [P] Implement a node-provenance lookup helper (given a list of node ids, return each node's
      `provenance.status`) using the existing `kg.py` resolver in
      cloud-arch-validator-agent/app/kg_lib/verdict_card.py
- [X] T006 Implement extraction of one `Finding`-shaped record per connectivity/architecture entry from
      `validate()`'s output (walks `connectivity` and `architecture` lists, not yet tiered) in
      cloud-arch-validator-agent/app/kg_lib/verdict_card.py (depends on T004)
- [X] T007 Register a `generate_verdict_card` stub tool (accepts the contract's signature, returns a
      not-yet-implemented placeholder) in cloud-arch-validator-agent/app/tools.py, added to `ALL_TOOLS`
      (depends on T004)

**Checkpoint**: Shared shapes and raw finding extraction exist — user stories can now build tier logic,
mismatch logic, checklist logic, and gap logic independently on top of this.

---

## Phase 3: User Story 1 - Instant structured verdict during a live client conversation (Priority: P1) 🎯 MVP

**Goal**: Replace prose validation output with a card containing one overall difficulty verdict and
every finding tagged with an evidence tier.

**Independent Test**: Call `generate_verdict_card` with a mix of clean and untested/violating edges;
confirm a single card is returned with one difficulty label and every finding individually tiered.

### Tests for User Story 1

- [X] T008 [P] [US1] Regression fixture: architecture where every edge is KG-clean and provenance
      `manual`/`verified` → difficulty `Low`, every finding tier `Proven`, in
      cloud-arch-validator-agent/tests/unit/test_verdict_card.py
- [X] T009 [P] [US1] Regression fixture: architecture containing one rule-violating edge → difficulty
      reflects the worst finding, and that finding is distinguishable from the others, in
      cloud-arch-validator-agent/tests/unit/test_verdict_card.py
- [X] T010 [P] [US1] Regression fixture: architecture containing one uncovered edge (no rule, no
      precedent) → that finding tiers as `Requires Deep Review` or `Theoretically Possible` per
      research.md, and overall difficulty is never a confident `Low`, in
      cloud-arch-validator-agent/tests/unit/test_verdict_card.py

### Implementation for User Story 1

- [X] T011 [US1] Implement the evidence-tier classification function (Proven / Theoretically Possible /
      Requires Deep Review) per the research.md decision table in
      cloud-arch-validator-agent/app/kg_lib/verdict_card.py (depends on T006, T005)
- [X] T012 [US1] Implement the difficulty rollup function (extends `SEVERITY_ORDER`, handles the
      all-uncovered → `Unassessed` edge case from spec.md) in
      cloud-arch-validator-agent/app/kg_lib/verdict_card.py (depends on T011)
- [X] T013 [US1] Implement `difficulty_reason` generation naming the specific driving finding(s) (FR-004)
      in cloud-arch-validator-agent/app/kg_lib/verdict_card.py (depends on T012)
- [X] T014 [US1] Implement `generate_verdict_card()` core assembly — calls `validate()`, builds
      `findings`, `difficulty`, `difficulty_reason`, `assumptions` (from context defaults substituted per
      FR-010); `mismatches` and `checklist` left empty at this stage — in
      cloud-arch-validator-agent/app/kg_lib/verdict_card.py (depends on T011, T012, T013)
- [X] T015 [US1] Replace the stub tool with the real implementation in
      cloud-arch-validator-agent/app/tools.py (depends on T014, T007)
- [X] T016 [US1] Update the agent instruction to present card fields (difficulty, tiered findings,
      assumptions) instead of narrating raw tool output, in cloud-arch-validator-agent/app/agent.py
      (depends on T015)
- [X] T017 [US1] Run quickstart.md Scenarios 1 and 2 manually to confirm end-to-end behavior (depends on
      T015)

**Checkpoint**: User Story 1 fully functional and independently testable — this is the MVP.

---

## Phase 4: User Story 2 - Mismatch correction when the client's ask doesn't match the actual need (Priority: P2)

**Goal**: Detect and surface when the client's stated technology choice doesn't fit the underlying
requirement.

**Independent Test**: Call `generate_verdict_card` with `stated_needs` naming a technology that doesn't
fit the requirement; confirm a distinct mismatch entry appears naming both sides.

### Tests for User Story 2

- [X] T018 [P] [US2] Regression fixture: `stated_needs` naming a poor-fit technology → one mismatch entry
      naming both the stated choice and the actual need, in
      cloud-arch-validator-agent/tests/unit/test_verdict_card.py
- [X] T019 [P] [US2] Regression fixture: `stated_needs` matching the actual requirement → `mismatches` is
      empty, in cloud-arch-validator-agent/tests/unit/test_verdict_card.py

### Implementation for User Story 2

- [X] T020 [US2] Define the mismatch rule table (stated-need keyword → best-fit role/category) per
      research.md in cloud-arch-validator-agent/app/kg_lib/verdict_card.py
- [X] T021 [US2] Implement mismatch detection using `stated_needs` against the rule table and
      `search_services`/KG role lookups, producing `MismatchEntry` records, in
      cloud-arch-validator-agent/app/kg_lib/verdict_card.py (depends on T020)
- [X] T022 [US2] Wire the `stated_needs` parameter through `generate_verdict_card()` and the tool
      signature in cloud-arch-validator-agent/app/kg_lib/verdict_card.py and
      cloud-arch-validator-agent/app/tools.py (depends on T021, T014)
- [X] T023 [US2] Update the agent instruction to relay mismatch entries as a client-conversation
      correction, in cloud-arch-validator-agent/app/agent.py (depends on T022)
- [X] T024 [US2] Run quickstart.md Scenario 4 manually to confirm end-to-end behavior (depends on T022)

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Ready-made checklist for the engineer who picks this up next (Priority: P3)

**Goal**: Generate a concrete follow-up checklist item for every non-proven finding.

**Independent Test**: Generate a card with at least one non-proven finding; confirm one checklist item
exists per such finding, worded as a concrete action.

### Tests for User Story 3

- [X] T025 [P] [US3] Regression fixture: card with non-proven findings → checklist has exactly one item
      per such finding, in cloud-arch-validator-agent/tests/unit/test_verdict_card.py
- [X] T026 [P] [US3] Regression fixture: card where every finding is `Proven` → checklist is empty and
      `checklist_empty_reason` is set, in cloud-arch-validator-agent/tests/unit/test_verdict_card.py

### Implementation for User Story 3

- [X] T027 [US3] Implement per-tier checklist item templates (Theoretically Possible / Requires Deep
      Review wording) per research.md in cloud-arch-validator-agent/app/kg_lib/verdict_card.py
- [X] T028 [US3] Implement checklist generation building a 1:1 list from non-Proven findings and setting
      `checklist_empty_reason` when empty, in cloud-arch-validator-agent/app/kg_lib/verdict_card.py
      (depends on T027, T014)
- [X] T029 [US3] Wire checklist generation into `generate_verdict_card()`'s return value in
      cloud-arch-validator-agent/app/kg_lib/verdict_card.py (depends on T028)
- [X] T030 [US3] Update the agent instruction to present the checklist section (or its empty-reason) in
      cloud-arch-validator-agent/app/agent.py (depends on T029)
- [X] T031 [US3] Run quickstart.md Scenario 5 manually to confirm the 1:1 correspondence (depends on
      T029)

**Checkpoint**: User Stories 1, 2, and 3 all work independently.

---

## Phase 6: User Story 4 - Unanswered requests become visible market intelligence (Priority: P3)

**Goal**: Persist every uncovered/unknown finding as a standalone Gap Record, without human confirmation.

**Independent Test**: Submit a request with an uncovered/unknown element; confirm a corresponding line
is appended to the Gap Record log, retrievable independently of the conversation.

### Tests for User Story 4

- [X] T032 [P] [US4] Regression fixture: an `UNCOVERED`/`UNKNOWN_SERVICE` finding appends one matching
      line to the gap log, in cloud-arch-validator-agent/tests/unit/test_verdict_card.py
- [X] T033 [P] [US4] Regression fixture: the same gap occurring twice across two separate calls produces
      two separate log lines, not one deduplicated entry, in
      cloud-arch-validator-agent/tests/unit/test_verdict_card.py

### Implementation for User Story 4

- [X] T034 [US4] Implement the `GapRecord` builder (`logged_at`, `request_summary`, `unresolved_element`,
      `reason`) per data-model.md in cloud-arch-validator-agent/app/kg_lib/verdict_card.py
- [X] T035 [US4] Implement the append-only writer to
      cloud-arch-validator-agent/app/references/gap_report.jsonl (depends on T034)
- [X] T036 [US4] Wire a gap-record write into `generate_verdict_card()` for every
      `UNCOVERED`/`UNKNOWN_SERVICE` finding, unconditionally (no confirmation gate, per Constitution
      Principle IV) in cloud-arch-validator-agent/app/kg_lib/verdict_card.py (depends on T035, T014)
- [X] T037 [US4] Run quickstart.md Scenario 3 manually to confirm the log entry appears (depends on T036)

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, end-to-end validation, and the eval-credibility gap flagged in the prior
constitution discussion (D15-equivalent)

- [X] T038 [P] Document the `generate_verdict_card` tool and Verdict Card output shape in
      cloud-arch-validator-agent/README.md
- [X] T039 Confirm `FR-010`'s assumption-labeling covers every context field (`environment`,
      `data_residency`, `sla_tier`) not explicitly supplied by the caller, in
      cloud-arch-validator-agent/app/kg_lib/verdict_card.py (depends on T014)
- [X] T040 [P] Add an eval case to cloud-arch-validator-agent/app/evals/evals.json (or a new
      verdict-card-specific eval file) proving the agent reports a `Requires Deep Review`/uncovered tier
      rather than guessing a confident verdict, addressing the still-open D15 gap noted for this agent
- [X] T041 Run the full suite (`uv run pytest tests/unit/test_verdict_card.py`) and the complete
      quickstart.md scenario list end-to-end from cloud-arch-validator-agent/

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational only — this is the MVP
- **User Story 2 (Phase 4)**: Depends on Foundational; reuses US1's `generate_verdict_card()` core
  (T014) but adds its own parameter and function, so it can be built and tested independently once T014
  exists
- **User Story 3 (Phase 5)**: Depends on Foundational and T014 (reads `findings`), independent of US2
- **User Story 4 (Phase 6)**: Depends on Foundational and T014 (reads `findings`), independent of US2/US3
- **Polish (Phase 7)**: Depends on all four user stories being complete

### Within Each User Story

- Tests written before implementation tasks (fixtures should fail first)
- Tier/finding logic before assembly into the card
- Card assembly before tool wiring
- Tool wiring before agent-instruction updates
- Manual quickstart validation last

### Parallel Opportunities

- T002, T003 in Setup can run in parallel
- T005 in Foundational can run in parallel with T004 (different concerns, same file — coordinate on
  merge, not true file-parallelism, but no logical dependency)
- Once Foundational (T004-T007) completes, US2 (Phase 4), US3 (Phase 5), and US4 (Phase 6) can all start
  in parallel with each other — each depends only on T014 from US1, not on one another
- All fixture-writing tasks marked [P] within a story can run in parallel with each other

---

## Parallel Example: Post-Foundational Fan-Out

```bash
# Once T014 (generate_verdict_card core) lands, these three stories proceed independently:
Task: "US2 — mismatch rule table and detection (T020-T024)"
Task: "US3 — checklist templates and generation (T027-T031)"
Task: "US4 — Gap Record builder and writer (T034-T037)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run quickstart.md Scenarios 1-2, confirm SC-001/SC-002/SC-005
5. This alone replaces prose validation output with a structured, tiered card — demoable on its own

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. User Story 1 → validate → MVP demo
3. User Story 2 → validate → mismatch correction demo
4. User Story 3 → validate → engineer checklist demo
5. User Story 4 → validate → Gap Record demo
6. Polish → documentation, eval credibility, full regression pass

---

## Notes

- [P] tasks touch different functions/files or have no completed-task dependency
- [Story] label maps every user-story-phase task back to spec.md's US1-US4
- Commit after each task or logical group, per existing repo convention
- `validate.py` and `kg.py` are read-only inputs throughout — no task in this list modifies either
