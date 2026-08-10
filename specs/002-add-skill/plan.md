# Implementation Plan: Add-Service Skill

**Branch**: `002-add-skill` | **Date**: 2026-08-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-add-skill/spec.md`

## Summary

Turn the existing `cloud-architecture-validator-add` design stub into a working single-service
add flow: fetch/propose the fields a lookup can verify (category, description, references_url,
icon), always ask a human for the fields it can't (network_placement, reachability, roles), and
only then append one entry to `services.yaml` with `provenance.status: unverified`. Also covers
updating an existing entry when the requester's reference is demonstrably newer than what the
entry was last checked against — the update path reads the reference and drafts every field
(including the three judgment fields), but a draft is never itself a confirmation; the human
still confirms each judgment field explicitly before anything is written. No bulk population
(stays `-init`'s job, still unbuilt), no auto-verification (status flip to `verified` stays a
separate, later human step, for both fresh adds and updates).

## Technical Context

**Language/Version**: Python 3, stdlib + PyYAML only (matches `check_kg.py`/`kg.py` in the
parent skill).

**Primary Dependencies**: PyYAML only, per root invariant #3. Reuses
`cloud-architecture-validator-create-architect/scripts/kg.py` (`icon_for()`, node lookup) and
`check_kg.py`'s provenance schema (`VALID_PROVENANCE_STATUS`, required `provenance` fields) —
read as reference for schema shape, not imported across skill boundaries (each skill stays
independently installable per D9).

**Storage**: Writes directly to
`cloud-architecture-validator-create-architect/references/kg/services.yaml` — the single file
this entry belongs in (D12: no staging file, no second copy).

**Testing**: A CLI dry-run mode plus a fixture-driven unit test asserting: (a) no write happens
without every judgment field answered, (b) written entries always carry
`provenance.generated: cloud-architecture-validator-add` + `status: unverified`, (c)
`check_kg.py` still reports clean structural integrity (37/37 regression unaffected — this
feature never edits `connectivity-rules.yaml`/`architecture-rules.yaml`) after a fixture add,
with the single expected diff being `check_kg.py`'s provenance gate now failing on the new
`unverified` entry until a human flips it — that failure is correct behavior, not a bug.

**Target Platform**: Same as parent skill — runs at authoring time on a contributor's machine,
never part of the live validation path (root invariant #3's `tools/`-style exemption).

**Project Type**: Single project — this is `cloud-architecture-validator-add`'s own
`scripts/add_service.py`, replacing the stub in place, not a new skill or service.

**Performance Goals**: N/A — authoring-time, interactive, human-paced. No latency requirement
(unlike the live Verdict Card path).

**Constraints**: No LLM judgment on `network_placement`/`reachability`/`roles` (Principle III /
D6) — those three fields are always a literal human answer, never inferred from fetched data or
from an LLM's read of provider docs. Fetch of the safe fields (FR-003) may fail (dead link,
unresolvable icon) without blocking the add.

**Scale/Scope**: One service per invocation, matching spec Assumption — same scale discipline as
the rest of the KG (~45 services today).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Verdict-Not-Guess** — N/A to this feature directly (this skill doesn't produce a
  verdict), but the same discipline applies one level down: this skill MUST NOT let an LLM decide
  `network_placement`/`reachability`/`roles` by "reading" provider docs — those are exactly the
  properties `connectivity-rules.yaml` later uses to produce verdicts, so a guess here becomes a
  guessed verdict later, laundered through a KG entry that looks authoritative. FR-004 enforces
  this: PASS.
- **II. Evidence-Grounded History** — PASS. Every written entry's `provenance.sources` names what
  was actually checked (FR-007); nothing is written on inferred/typical values.
- **III. Human Gate on Judgment Calls** — PASS, this is the feature's central mechanism (FR-004,
  FR-005, FR-006). Matches the Dev Workflow requirement that "features that let an agent propose a
  write to organizational knowledge MUST ship with the human-confirmation gate in the same
  change" — there is no version of this feature without the gate. The update path (US4/FR-012)
  is the highest-risk part of this feature against this principle specifically — reading a
  reference doc and drafting judgment-field values is one step away from the LLM deciding them
  outright. FR-012 draws the line explicitly: a draft is a suggestion, never a confirmation, and
  is unconfirmed-by-default exactly like a from-scratch proposal. This was flagged and corrected
  during design (see research.md's "staleness + suggested answers" decision) precisely because
  the first version of the idea would have violated this principle.
- **IV. Read-Only by Default, Explicit Write Path** — PASS. The only write is the explicit,
  human-confirmed `services.yaml` append (FR-009); nothing is written on decline/abandon (FR-010).
- **V. Layered Transparency** — PASS by inheritance, not new work: the written entry's
  `provenance.status: unverified` is itself the transparency signal downstream (`check_kg.py`,
  and eventually the Verdict Card's tier mapping) already reads to distinguish proven from
  unverified.

No violations. Complexity Tracking section is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/002-add-skill/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
cloud-architecture-validator-add/
├── SKILL.md                      # UPDATED — stub language replaced once this ships
├── scripts/
│   └── add_service.py            # REPLACED — stub becomes the real fetch/confirm/write flow
└── tests/
    └── test_add_service.py       # NEW — fixture-driven regression tests

cloud-architecture-validator-create-architect/
├── scripts/
│   ├── kg.py                     # UNCHANGED — icon_for()/node lookup reused as-is
│   └── check_kg.py               # UNCHANGED — provenance gate already enforces status rules
└── references/kg/
    └── services.yaml             # WRITE TARGET — new entries appended here only
```

**Structure Decision**: Single project, in-place replacement of the existing design stub.
`add_service.py` stays inside `cloud-architecture-validator-add/scripts/` (its own skill,
per D9's split-by-workflow rationale) and writes into the sibling
`cloud-architecture-validator-create-architect/references/kg/services.yaml` the same way
`cloud-architecture-validator-show-kg` already reads it — via a relative sibling path, failing
loudly if the parent skill isn't installed alongside it, never forking a copy of the KG.

## Complexity Tracking

*No constitution violations — section not applicable.*
