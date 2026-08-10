---
description: "Task list for Equivalence Detection feature"
---

# Tasks: Equivalence Detection in Add-Service Skill

**Input**: Design documents from `/specs/003-equivalence-detection/`

**Prerequisites**: plan.md, spec.md

**Organization**: Tasks grouped by phase (Setup, Foundational, US1, US2, Polish) with parallel opportunities marked [P].

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story label (US1, US2)

---

## Phase 1: Setup

**Purpose**: Create module structure, test skeleton, base imports.

- [x] T001 Create `cloud-architecture-validator-add/scripts/equivalence.py` (empty module, docstrings only)
- [x] T002 Create `cloud-architecture-validator-add/tests/test_equivalence.py` with imports + fixture references
- [x] T003 Create test fixture in conftest.py for equivalences.yaml (load from sibling KG or mock)

---

## Phase 2: Foundational

**Purpose**: Shared helpers, existing-mapping detection, recommendation formatter.

- [x] T004 [P] Implement `load_equivalences(yaml_path)` in equivalence.py — read equivalences.yaml from sibling skill
- [x] T005 [P] Implement `find_existing_equivalence(provider_from, service_name_from, equivalences)` — case-insensitive (provider, name) lookup
- [x] T006 [P] Implement `format_recommendation(proposal, confirmed_name)` in equivalence.py — return copy-paste-ready YAML block + metadata
- [x] T007 Implement `EquivalenceProposal` dataclass in equivalence.py (fields: provider_from, service_name_from, provider_to, service_name_to, confidence, rationale, sources)

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Fresh-Add Equivalence Proposal (Priority: P1)

**Goal**: Fresh-add flow prompts for equivalence after judgment fields answered. Agent proposes equivalent service. User confirms/corrects/declines. Recommendation output if confirmed.

**Independent Test**: Fresh-add flow alone completes; equivalence prompt appears; proposal can be accepted/rejected; no equivalences.yaml written.

### Tests for User Story 1

- [x] T008 [P] [US1] Test `test_equivalence_proposal_from_service_metadata` — given service category + description, agent proposes equiv name + confidence
- [x] T009 [P] [US1] Test `test_equivalence_recommendation_format` — confirmed proposal outputs valid YAML block (copy-paste ready)
- [x] T010 [P] [US1] Test `test_equivalence_exists_blocks_proposal` — service with existing mapping shows "already mapped" instead of proposal

### Implementation for User Story 1

- [x] T011 [US1] Implement `propose_equivalence(service_name, provider_from, categories, references_url)` in equivalence.py — agent-based proposal (category + description → Azure equivalent)
- [x] T012 [US1] Wire equivalence prompt into `add_service.py` main() after judgment fields confirmed (before write): "Does [service] have an equivalent in [other provider]?"
- [x] T013 [US1] Wire user confirmation prompt (accept/correct/decline) + call `format_recommendation()` on confirmation

**Checkpoint**: User Story 1 fully functional — equivalence detection on fresh-add works end-to-end.

---

## Phase 4: User Story 2 - Update Equivalence Detection (Priority: P2)

**Goal**: Update flow (newer reference found) checks reference docs for competitor mentions. Agent proposes equivalence. User confirms/corrects/declines. Recommendation output if confirmed.

**Independent Test**: Update path fires; equivalence detection triggers when reference mentions competitors; proposal can be accepted/rejected; no auto-writes.

### Tests for User Story 2

- [x] T014 [P] [US2] Test `test_competitor_mention_detected` — reference text containing "Agent Platform" triggers proposal for Azure equiv
- [x] T015 [P] [US2] Test `test_no_competitor_mention_skips_detection` — reference without mentions skips equivalence prompt
- [x] T016 [P] [US2] Test `test_equivalence_proposal_on_update` — update flow shows equivalence prompt with draft confirmation gate

### Implementation for User Story 2

- [x] T017 [US2] Implement `detect_competitor_mention(reference_text)` in equivalence.py — search for known competitor product names (Agent Platform, etc.)
- [x] T018 [US2] Wire equivalence detection into `add_service.py` update path: after newer reference confirmed, check reference docs for competitor mentions
- [x] T019 [US2] Wire confirmation prompt into update flow (reuse T013 logic): user confirms/corrects/declines equivalence, calls `format_recommendation()`

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T020 Update `SKILL.md` in cloud-architecture-validator-add: document equivalence detection feature in fresh-add + update flows
- [x] T021 Run manual quickstart scenarios 1-3 from plan.md: fresh-add with equiv, fresh-add without equiv, update with competitor mention
- [x] T022 Verify no writes to equivalences.yaml (output-only); confirm recommendation blocks are copy-paste ready

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational only. This is the MVP.
- **US2 (Phase 4)**: Depends on Foundational + US1's wiring (update path already exists in main -add skill)
- **Polish (Phase 5)**: Depends on US1 + US2

### Parallel Opportunities

- T001, T002, T003 (Setup) can run in parallel (different files)
- T004, T005, T006 (Foundational) can run in parallel (different functions)
- T008, T009, T010 (US1 tests) can run in parallel
- T014, T015, T016 (US2 tests) can run in parallel

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run quickstart scenario 1 by hand
5. Demo: fresh-add Cloud Run, equivalence proposal accepted, recommendation output

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → validate (fresh-add equiv) → demo
3. US2 → validate (update equiv) → demo
4. Polish: SKILL.md rewrite, full quickstart pass

---

## Notes

- [P] tasks = different files or independent test functions, no ordering dependency.
- US1/US2 both wire into same main() flow (add_service.py); U1 at judgment confirmation, US2 at update confirmation.
- No writes to equivalences.yaml (recommendation-only, per plan.md Principle IV).
- All proposals require explicit user confirmation (per constitution Principle III).
- Existing -add tests unaffected (new tests in separate file).

---

## Format Validation

✓ All tasks follow `- [ ] [ID] [P?] [Story?] Description with file path` format
✓ IDs sequential (T001–T022)
✓ [P] markers on parallelizable tasks only
✓ [Story] labels on US1/US2 phase tasks only
✓ File paths explicit (equivalence.py, test_equivalence.py, add_service.py, SKILL.md)
✓ Phases in execution order with clear checkpoints
