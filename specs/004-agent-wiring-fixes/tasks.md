---

description: "Task list for Agent Wiring Fixes"
---

# Tasks: Agent Wiring Fixes

**Input**: Design documents from `/specs/004-agent-wiring-fixes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/agent-tools.md, quickstart.md

**Tests**: Included — `cloud-arch-validator-agent/tests/unit/test_tools.py` already exercises `tools.py`, and `cloud-architecture-validator-add/tests/` already tests the functions being reused; new tests extend both suites rather than introducing a new framework.

**Organization**: Tasks grouped by user story (US1 = P1 add-service wiring, US2 = P3 equivalence tool), per spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps task to US1 or US2 from spec.md

## Path Conventions

Single project. Agent tool code: `cloud-arch-validator-agent/app/tools.py`. Reused logic (unchanged):
`cloud-architecture-validator-add/scripts/*.py`. Tests: `cloud-arch-validator-agent/tests/unit/test_tools.py`
(agent-level) and `cloud-architecture-validator-add/tests/test_add_service.py` /
`test_equivalence.py` (already-existing suites, extended where the reused functions gain a new
caller-facing contract).

---

## Phase 1: Setup

**Purpose**: Confirm the baseline this feature builds on is intact before touching `tools.py`

- [X] T001 Run `python3 cloud-architecture-validator-create-architect/scripts/check_kg.py` and record baseline coverage/regression numbers (37/37, ≥80% L1) to diff against after T010
- [ ] T002 Run existing agent test suite (`pytest cloud-arch-validator-agent/tests/`) and existing `-add` suite (`pytest cloud-architecture-validator-add/tests/`) to confirm both are green before changes

---

## Phase 2: Foundational

**Purpose**: Nothing new is foundational here — `tools.py` already has the `sys.path.insert` pattern
this feature reuses (see `plan.md` Project Structure), and the functions being called already exist
and are tested in the `-add` skill. No blocking infrastructure work is required before either user
story.

**Checkpoint**: Proceed directly to Phase 3 — both stories can be implemented independently once Phase 1 confirms a clean baseline.

---

## Phase 3: User Story 1 - Presales engineer adds a missing service mid-conversation (Priority: P1) 🎯 MVP

**Goal**: Replace the hardcoded `add_service_to_kg` stub with a real tool that collects judgment
fields as parameters, writes a provenanced entry, and reports back what it wrote — matching FR-001
through FR-005, FR-008 through FR-010.

**Independent Test**: Per quickstart.md Scenario 1 — validate an architecture with an unknown
service, add it via the agent, confirm the written entry and its `status: unverified` provenance,
then attempt to add it again and confirm duplicate detection.

### Tests for User Story 1

- [X] T003 [P] [US1] Add test in `cloud-arch-validator-agent/tests/unit/test_tools.py` asserting `add_service_to_kg` returns `{"written": False, "error": "missing_field", ...}` and performs no write when `network_placement`, `reachability`, or `roles` is empty (FR-003)
- [X] T004 [P] [US1] Add test in `cloud-arch-validator-agent/tests/unit/test_tools.py` asserting `add_service_to_kg` returns `{"written": False, "existing": {...}}` and performs no write when `(name, provider)` already exists (FR-005), using `find_existing`
- [X] T005 [P] [US1] Add test in `cloud-arch-validator-agent/tests/unit/test_tools.py` asserting a successful call returns `{"written": True, "entry": {...}}` with `entry["provenance"]["status"] == "unverified"` (FR-004, FR-010)

### Implementation for User Story 1

- [X] T006 [US1] Add imports of `propose_safe_fields`, `find_existing`, `build_provenance`, `write_entry` from the `-add` skill's `scripts/` modules (`propose.py`, `kg_io.py`, `provenance.py`) to `cloud-arch-validator-agent/app/tools.py`, following the existing `sys.path.insert` pattern used for `kg_lib` (plan.md Project Structure)
- [X] T007 [US1] Replace the `add_service_to_kg` stub body in `cloud-arch-validator-agent/app/tools.py` with the real implementation per the contract in `contracts/agent-tools.md`: validate required judgment fields present, check `find_existing`, call `propose_safe_fields` for verifiable fields, build the entry dict, call `build_provenance` and `write_entry`, return the written entry or existing-match/error dict (depends on T006)
- [X] T008 [US1] Update `add_service_to_kg`'s docstring in `cloud-arch-validator-agent/app/tools.py` to describe the real contract (drop `_ADD_STUB` message and the "NOT IMPLEMENTED" framing) (depends on T007)
- [X] T009 [US1] Remove the now-unused `_ADD_STUB` constant from `cloud-arch-validator-agent/app/tools.py` if nothing else references it (depends on T007, T008)
- [X] T010 [US1] Run `python3 cloud-architecture-validator-create-architect/scripts/check_kg.py` after running T003-T005 tests (which write real entries to a scratch/test copy of `services.yaml`, not the live file) and confirm no unexpected regression drop versus the T001 baseline

**Checkpoint**: User Story 1 fully functional — an engineer can add a service through the agent without leaving the conversation, with the human-gate and provenance rules enforced by tests, not convention.

---

## Phase 4: User Story 2 - Sales engineer asks for a cross-cloud equivalent (Priority: P3)

**Goal**: Add a `propose_equivalence` tool that answers `found` / `not_applicable` / `unknown`
without ever presenting a guessed name as a fact, per FR-006, FR-007, FR-008.

**Independent Test**: Per quickstart.md Scenario 2 — ask for equivalents of a recorded service, a
`regenerate_roles` connector, and an unrecorded service; confirm the three distinct outcomes.

### Tests for User Story 2

- [X] T011 [P] [US2] Add test in `cloud-arch-validator-agent/tests/unit/test_tools.py` asserting `propose_equivalence` returns `{"status": "found", "equivalence": {...}}` for a service present in `equivalences.yaml`, using `find_existing_equivalence`
- [X] T012 [P] [US2] Add test in `cloud-arch-validator-agent/tests/unit/test_tools.py` asserting `propose_equivalence` returns `{"status": "not_applicable", ...}` for a service whose role is in `regenerate_roles`, and never calls `equivalence.propose_equivalence()`'s placeholder path for it (FR-007)
- [X] T013 [P] [US2] Add test in `cloud-arch-validator-agent/tests/unit/test_tools.py` asserting `propose_equivalence` returns `{"status": "unknown", ...}` (not a fabricated name) for a service with no recorded equivalence and no `regenerate_roles` role

### Implementation for User Story 2

- [X] T014 [US2] Use the vendored KG equivalence index and `regenerate_roles` source in `cloud-arch-validator-agent/app/tools.py`; avoid the authoring-only legacy equivalence helper because its schema differs from deployed `equivalences.yaml`
- [X] T015 [US2] Implement `propose_equivalence(service_name, provider_from)` in `cloud-arch-validator-agent/app/tools.py` per `contracts/agent-tools.md`: check the service's roles against `regenerate_roles` first (→ `not_applicable`), else check `find_existing_equivalence` (→ `found`), else return `unknown` — never call through to `equivalence.propose_equivalence()`'s placeholder-name path (depends on T014)
- [X] T016 [US2] Register `propose_equivalence` in the agent's tool list in `cloud-arch-validator-agent/app/tools.py` (alongside `add_service_to_kg`, `init_kg_from_catalog`) (depends on T015)

**Checkpoint**: Both user stories independently functional — Story 1 (write path) and Story 2 (read-only recommendation) do not share mutable state and can be delivered/demoed separately.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Confirm the two wired tools behave correctly together and match the evaluation report's original ask

- [X] T017 [P] Run `quickstart.md` Scenario 1 and Scenario 2 manually against tool functions: missing-field rejection, recorded equivalent, connector exception, and unknown result all match contract
- [X] T018 Update `cloud-arch-validator-agent/app/tools.py` module-level docstring / tool list docstrings if either tool's summary line still references "design stub" or similar stale language
- [X] T019 Re-run KG gate and full pytest suites (`cloud-arch-validator-agent/tests/`, `cloud-architecture-validator-add/tests/`) as final regression pass; live integration passes with configured credentials.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — run first
- **Foundational (Phase 2)**: Empty — no blocking work
- **User Story 1 (Phase 3)**: Depends on Phase 1 only
- **User Story 2 (Phase 4)**: Depends on Phase 1 only — independent of Phase 3 (different function, no shared mutable state; both only read the already-loaded `_KG`)
- **Polish (Phase 5)**: Depends on both user stories being complete

### Within Each User Story

- Tests (T003-T005, T011-T013) before implementation, and should fail (or not exist to call) before their corresponding implementation task lands
- T006 (imports) before T007 (implementation body) before T008/T009 (cleanup)
- T014 (imports) before T015 (implementation) before T016 (registration)

### Parallel Opportunities

- T003, T004, T005 in parallel (same file, but independent test functions — write them together, run together)
- T011, T012, T013 in parallel, same reasoning
- Phase 3 (US1) and Phase 4 (US2) can be implemented in parallel by different people once Phase 1 is done — both touch `tools.py` but in disjoint functions; coordinate on merge order to avoid edit conflicts in the same file

---

## Parallel Example: User Story 1

```bash
Task: "Add test for missing-judgment-field rejection in cloud-arch-validator-agent/tests/unit/test_tools.py"
Task: "Add test for duplicate-detection short-circuit in cloud-arch-validator-agent/tests/unit/test_tools.py"
Task: "Add test for successful write + provenance shape in cloud-arch-validator-agent/tests/unit/test_tools.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup
2. Phase 3: User Story 1 (add-service wiring)
3. **STOP and VALIDATE**: Run quickstart.md Scenario 1, confirm `check_kg.py` still clean
4. This alone closes the evaluation's P1 item and makes the stub message honest

### Incremental Delivery

1. Setup → baseline confirmed
2. User Story 1 → validate → this is the P1 fix from `project_evaluation.md`, deployable alone
3. User Story 2 → validate → closes the P3 item
4. Polish → final regression pass

## Notes

- [P] tasks share a file (`test_tools.py`) but are independent test functions — parallel-safe for
  authoring, not for literal simultaneous editing by two agents without coordination.
- Story 1 and Story 2 both edit `cloud-arch-validator-agent/app/tools.py` but touch disjoint
  functions (`add_service_to_kg` vs `propose_equivalence` plus the tool-list registration line) — if
  worked in parallel, merge the tool-list registration line last to avoid a conflict.
- Do not add file locking, `--auto-merge`, or any write path into `equivalences.yaml` from
  `propose_equivalence` — both are explicitly out of scope per research.md and CLAUDE.md D6.
