---

description: "Task list for the Add-Service Skill feature"
---

# Tasks: Add-Service Skill

**Input**: Design documents from `/specs/002-add-skill/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/add_service.md, quickstart.md

**Tests**: Included — plan.md's Testing section and quickstart.md's "Regression fixtures" section
both call for fixture-driven tests per scenario; tests are written before their implementation
task in each story phase.

**Organization**: Tasks are grouped by user story (spec.md priorities: US1=P1, US2=P2, US4=P2,
US3=P3) so each can be implemented and demoed independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)

## Path Conventions

Single project. All implementation lives in `cloud-architecture-validator-add/` (this skill's own
directory); the only file this skill touches outside it is the write target
`cloud-architecture-validator-create-architect/references/kg/services.yaml` (sibling skill,
untouched code-wise — only its data file is written to at runtime).

---

## Phase 1: Setup

**Purpose**: Replace the stub scaffold with a real CLI skeleton.

- [x] T001 Replace the stub in `cloud-architecture-validator-add/scripts/add_service.py` with a
      real argparse CLI skeleton: `--name` (required), `--provider` {gcp,azure} (required),
      `--references-url` (optional), `--dry-run` (flag) — per contracts/add_service.md. Remove
      the unconditional `sys.exit("...NOT IMPLEMENTED...")`; leave `main()` calling into
      not-yet-built functions from Phase 2 (fine to stub-raise `NotImplementedError` there only,
      not at the CLI level).
- [x] T002 [P] Create `cloud-architecture-validator-add/tests/` directory with an empty
      `__init__.py` and add `cloud-architecture-validator-add/tests/conftest.py` providing a
      `tmp_services_yaml` fixture that copies a small fixture KG (2-3 services, including one
      with `provenance.status: verified` and a `verified:` date) into a tmp path so tests never
      touch the real `references/kg/services.yaml`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared read/write/lookup/gating logic every user story's flow depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 [P] Implement YAML round-trip load/write for `services.yaml` in
      `cloud-architecture-validator-add/scripts/kg_io.py` — load preserving list order, append or
      replace one entry, write back without reformatting untouched entries or dropping comments
      elsewhere in the file (research.md: "Write mechanism" decision).
- [x] T004 [P] Implement `find_existing(services, name, provider)` case-insensitive
      `(name, provider)` lookup in `cloud-architecture-validator-add/scripts/kg_io.py`
      (research.md: "Duplicate detection" decision — match on name+provider, not `id`).
- [x] T005 [P] Implement safe-field fetch/propose functions (`category`, `description`,
      `references_url` link-check, `icon` via the sibling `kg.py`'s `icon_for()` mechanism) in
      `cloud-architecture-validator-add/scripts/propose.py` — each field fails independently and
      is reported as unresolved rather than blocking the others (research.md: "Safe-field fetch
      failure handling").
- [x] T006 [P] Implement `build_provenance(sources)` in
      `cloud-architecture-validator-add/scripts/provenance.py` — always returns
      `{generated: "cloud-architecture-validator-add", status: "unverified", sources: [...]}`,
      never any other `status` value (FR-007, FR-008).
- [x] T007 Implement the `JudgmentQuestionBatch` gate in
      `cloud-architecture-validator-add/scripts/judgment.py`: three fields
      (`network_placement`, `reachability`, `roles`), each in state `unanswered` | `draft` |
      `answered`; `all_answered()` returns `True` only when every field is `answered` — a `draft`
      never counts (data-model.md, FR-004/FR-005/FR-012). Depends on: none (pure data structure),
      but is consumed by T011/T021.
- [x] T008 Implement `write_entry(services, entry, mode="append"|"replace")` in
      `cloud-architecture-validator-add/scripts/kg_io.py` — appends for a fresh add, replaces the
      matched entry in place for an update, never a partial write. Depends on: T003, T006.

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Guided single-service add (Priority: P1) 🎯 MVP

**Goal**: Name a missing service, get proposed safe fields, answer judgment questions, get exactly
one new `services.yaml` entry with `provenance.status: unverified`.

**Independent Test**: Run against a service name not in the fixture KG; confirm judgment questions
are asked and the entry is written only after they're all answered.

### Tests for User Story 1

- [x] T009 [P] [US1] Fixture test in
      `cloud-architecture-validator-add/tests/test_add_service.py::test_happy_path_add` —
      full flow with all judgment answers supplied writes exactly one new entry with
      `provenance.generated: cloud-architecture-validator-add` and `status: unverified`.
- [x] T010 [P] [US1] Fixture test
      `test_add_service.py::test_no_write_without_all_judgment_answers` — confirming with one
      judgment field still `unanswered` results in zero changes to `services.yaml` (byte
      comparison, per research.md's "Test strategy for no write on abandon").

### Implementation for User Story 1

- [x] T011 [US1] Wire the fresh-add flow into `main()` in
      `cloud-architecture-validator-add/scripts/add_service.py`: propose safe fields (T005) →
      present `JudgmentQuestionBatch` (T007) starting fully `unanswered` → block confirm until
      `all_answered()` → build entry (safe fields + judgment answers + `build_provenance`, T006)
      → `write_entry(..., mode="append")` (T008). Depends on: T005, T006, T007, T008.
- [x] T012 [US1] Add stdout formatting for the proposal and judgment-question prompts, and stdin
      reading with re-prompt on blank answers, in `add_service.py` (contracts/add_service.md
      Flow steps 2-3).
- [x] T013 [US1] Implement exit codes 0 (write or reported-existing)/1 (abandoned)/2 (usage error)
      per contracts/add_service.md "Exit codes" table.

**Checkpoint**: User Story 1 fully functional and testable independently — this is the MVP.

---

## Phase 4: User Story 2 - Duplicate prevention (Priority: P2)

**Goal**: Requesting an already-present `(name, provider)` reports the existing entry instead of
creating a second one.

**Independent Test**: Run the same `--name`/`--provider` twice; second run reports existing entry,
no new entry appears.

### Tests for User Story 2

- [x] T014 [P] [US2] Fixture test
      `test_add_service.py::test_duplicate_reports_existing_no_proposal` — requesting a
      name/provider already in the fixture KG (with no `--references-url`, or one no newer than
      the entry's last-checked date) prints the existing entry, asks no judgment questions, and
      leaves `services.yaml` unchanged.

### Implementation for User Story 2

- [x] T015 [US2] Wire `find_existing` (T004) into `main()` before the propose step: if found and
      no newer reference supplied, print the existing entry and exit 0 without building a
      proposal (FR-002's non-update branch). Depends on: T004, T011 (runs before it in the flow).

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 4 - Staleness-detected update with AI-suggested answers (Priority: P2)

**Goal**: A duplicate match with a demonstrably newer reference proposes an update — including
draft judgment-field answers — instead of just reporting "already exists"; drafts still require
explicit human confirmation per field.

**Independent Test**: Run against an existing fixture entry with a reference newer than its
last-checked date; confirm a diff with draft judgment answers is proposed, confirm nothing writes
until each draft is explicitly confirmed, confirm declining leaves the entry untouched.

### Tests for User Story 4

- [x] T016 [P] [US4] Fixture test
      `test_add_service.py::test_newer_reference_triggers_update_proposal` — existing entry +
      newer `--references-url` produces an `UpdateProposal` with `changed_fields` and draft
      judgment answers, not a bare "already exists" report.
- [x] T017 [P] [US4] Fixture test
      `test_add_service.py::test_unconfirmed_draft_blocks_write` — draft judgment-field values
      alone (no explicit per-field confirmation) result in zero changes to `services.yaml`, even
      when none of the drafts are objected to (FR-012's "unconfirmed draft is never a
      confirmation").
- [x] T018 [P] [US4] Fixture test
      `test_add_service.py::test_same_or_older_reference_does_not_trigger_update` — a reference
      no newer than the entry's last-checked date falls back to US2's plain "already exists"
      report (FR-011, Edge Cases).

### Implementation for User Story 4

- [x] T019 [US4] Implement `is_newer(reference_checked_at, existing_entry)` staleness comparator
      in `cloud-architecture-validator-add/scripts/kg_io.py`, using
      `provenance.verified` date when `status: verified`, entry write time otherwise, and
      "always stale" when neither is present (spec Assumption on "last-checked date"). Depends
      on: T004.
- [x] T020 [US4] Implement `build_update_proposal(existing_entry, reference_url)` in
      `cloud-architecture-validator-add/scripts/propose.py` — extends T005's fetch mechanics to
      also draft `network_placement`/`reachability`/`roles` from the reference, each with a
      one-line rationale, and computes `changed_fields` against `existing_entry` (data-model.md
      `UpdateProposal`). Depends on: T005, T019.
- [x] T021 [US4] Wire the update flow into `main()`: on `is_newer`, build the proposal (T020),
      present `JudgmentQuestionBatch` (T007) pre-filled as `draft` (not `answered`), block confirm
      until each is explicitly confirmed via `all_answered()`, then `write_entry(...,
      mode="replace")` (T008) with a fresh `build_provenance` call (T006) resetting `status` to
      `unverified` regardless of the prior status (FR-013). Depends on: T007, T008, T015, T020.

**Checkpoint**: User Stories 1, 2, and 4 all work independently.

---

## Phase 6: User Story 3 - Correct before write (Priority: P3)

**Goal**: The human can override any agent-proposed field (safe field or judgment draft) before
confirming, for both the fresh-add and update flows.

**Independent Test**: Force a wrong proposed field, supply a correction during confirmation,
verify the corrected value (not the original proposal) is what's written.

### Tests for User Story 3

- [x] T022 [P] [US3] Fixture test
      `test_add_service.py::test_correction_overrides_proposed_field_on_add` — supplying an
      override for a proposed safe field during the fresh-add flow (T011) results in the override
      value in the written entry.
- [x] T023 [P] [US3] Fixture test
      `test_add_service.py::test_correction_overrides_draft_field_on_update` — supplying an
      override for a draft judgment field during the update flow (T021) results in the override
      value, not the draft, in the written entry.

### Implementation for User Story 3

- [x] T024 [US3] Add field-override handling to the fresh-add confirmation step in `main()`
      (`add_service.py`): before final confirm, accept per-field corrections and merge them over
      the proposal (data-model.md `Confirmation.field_overrides`) prior to calling `write_entry`.
      Depends on: T011.
- [x] T025 [US3] Add the same field-override handling to the update confirmation step in `main()`
      (`add_service.py`), reusing T024's merge logic against the update proposal instead of the
      fresh-add proposal. Depends on: T021, T024.

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T026 [P] Update `cloud-architecture-validator-add/SKILL.md` to remove stub language ("Not
      built yet", "NOT YET IMPLEMENTED" in its frontmatter description) and describe the real
      flow (fresh add + staleness-detected update), keeping the existing "line this skill has to
      draw" rationale section as-is since it still accurately describes the design.
- [x] T027 Run `quickstart.md` Scenarios 1-6 manually end-to-end against a real (non-fixture)
      clone of `references/kg/services.yaml` to confirm the documented CLI behavior matches
      implementation.
- [x] T028 [P] Run
      `cloud-architecture-validator-create-architect/scripts/check_kg.py` after a real Scenario 1
      add (T027) and confirm: 37/37 regression unaffected, L1 coverage unaffected elsewhere, and
      the new entry's `provenance.status: unverified` is the only reported provenance failure.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **US1 (Phase 3)**: Depends on Foundational only. This is the MVP.
- **US2 (Phase 4)**: Depends on Foundational; T015 depends on T011 existing (runs earlier in the
  same `main()` flow US1 built).
- **US4 (Phase 5)**: Depends on Foundational and on US2's `find_existing`/duplicate branch (T015)
  since staleness detection only fires from the duplicate-match path.
- **US3 (Phase 6)**: Depends on US1 (T011) and US4 (T021) — it adds correction handling to both
  existing confirmation steps rather than introducing a new flow.
- **Polish (Phase 7)**: Depends on all four stories being complete.

### User Story Dependencies

- **US1 (P1)**: No dependencies on other stories — true MVP.
- **US2 (P2)**: Builds on US1's flow (inserts a check before it) but is independently testable
  (its own fixture, its own assertion).
- **US4 (P2)**: Builds on US2's duplicate-match branch — cannot be tested without US2 present,
  but adds an independent, separately-testable outcome (update proposal vs. plain report).
- **US3 (P3)**: Cross-cutting over US1 and US4's confirmation steps — genuinely last, since there's
  nothing to "correct before write" until both write flows exist.

### Parallel Opportunities

- T003, T004, T005, T006 (Phase 2) touch different files — parallelizable.
- T009, T010 (US1 tests) — parallelizable, same file but independent test functions.
- T016, T017, T018 (US4 tests) — parallelizable.
- T022, T023 (US3 tests) — parallelizable.
- T026, T028 (Polish) — parallelizable with each other, not with T027 which they depend on.

---

## Parallel Example: Foundational Phase

```bash
Task: "Implement YAML round-trip load/write in cloud-architecture-validator-add/scripts/kg_io.py"
Task: "Implement duplicate lookup in cloud-architecture-validator-add/scripts/kg_io.py"
Task: "Implement safe-field fetch/propose functions in cloud-architecture-validator-add/scripts/propose.py"
Task: "Implement build_provenance in cloud-architecture-validator-add/scripts/provenance.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run quickstart.md Scenario 1 by hand
5. Demo: one real missing service added end-to-end

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → validate → demo (MVP)
3. US2 → validate (duplicate no longer silently re-adds) → demo
4. US4 → validate (staleness update path, the follow-up request that motivated this story) → demo
5. US3 → validate (corrections work on both flows) → demo
6. Polish: SKILL.md rewrite, full quickstart pass, `check_kg.py` sanity check

---

## Notes

- [P] tasks = different files or independent test functions, no ordering dependency.
- US2/US4/US3 are additive over the same `main()` flow US1 establishes — this is intentional
  (spec.md's stories build on "duplicate found" as a shared branch point), not a violation of
  story independence: each still has its own fixture test proving its own acceptance scenarios
  pass without needing the later stories implemented.
- Every write path (T011, T021, T024, T025) must go through `write_entry`/`build_provenance`
  (T006, T008) — no task should hand-construct a YAML write or a provenance block inline, since
  that would create a second write path FR-009 explicitly forbids.
- Commit after each checkpoint, not after every task.
