# Implementation Plan: Agent Wiring Fixes

**Branch**: `004-agent-wiring-fixes` | **Date**: 2026-08-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-agent-wiring-fixes/spec.md`

## Summary

Two agent tools in `cloud-arch-validator-agent/app/tools.py` currently sit unwired despite complete,
tested logic existing in `cloud-architecture-validator-add/scripts/`: `add_service_to_kg` always
returns a hardcoded stub, and no tool exposes equivalence detection at all. Gap 7 is resolved as
**Option B**: extract the non-interactive functions already factored out in `add_service.py`
(`propose_safe_fields`, `find_existing`, `build_provenance`, `write_entry`, `build_update_proposal`)
and call them directly from a new tool function that takes judgment fields as explicit parameters
instead of reading stdin. `propose_equivalence` is wired the same way, with its known limitation
(the underlying function is a stub that returns a placeholder name rather than a real inference)
surfaced rather than hidden.

## Technical Context

**Language/Version**: Python 3.11 (matches existing `cloud-arch-validator-agent` and skill scripts)

**Primary Dependencies**: PyYAML only (existing invariant #3 — no new runtime dependency)

**Storage**: Flat YAML files under `cloud-architecture-validator-create-architect/references/kg/`
(`services.yaml`, `equivalences.yaml`) — read/write via existing `kg_io.py` helpers

**Testing**: pytest, matching existing test layout for the `-add` and agent skills

**Target Platform**: Same process as the ADK agent (`cloud-arch-validator-agent`), Linux/macOS dev + Cloud Run deploy

**Project Type**: Single agent service importing sibling skill scripts (existing pattern — see `sys.path.insert` in `tools.py`)

**Performance Goals**: N/A — human-paced conversational tool calls, not a throughput path

**Constraints**: No LLM in the decision path (root invariant #1); no `subprocess`/stdin-driven CLI
invocation from the agent (add_service.py's interactive prompts cannot be scripted mid-conversation);
every write carries `status: unverified` + provenance (CLAUDE.md D21)

**Scale/Scope**: Two tool functions, ~45-node KG, single-writer-at-a-time expectation (no concurrent-write locking exists today and none is being added — see Edge Cases in spec)

## Constitution Check

*Gate: Technical Co-Pilot Constitution v1.1.0*

- **Principle I (Verdict-Not-Guess)**: Not applicable to validation verdicts here — this feature
  writes KG data and proposes equivalences, neither of which is a difficulty/feasibility verdict.
  PASS.
- **Principle III (Human Gate on Judgment Calls)**: Directly governs this feature. `network_placement`,
  `reachability`, `roles` remain human-supplied parameters, never inferred; `propose_equivalence`'s
  output is explicitly a recommendation requiring human confirmation before touching
  `equivalences.yaml`. PASS, enforced by FR-002/FR-003/FR-007 in the spec.
- **Principle IV (Read-Only by Default, Explicit Write Path)**: `add_service_to_kg` is the write path;
  it fires only after all judgment fields are explicitly supplied (FR-003), and every write is reported
  back to the caller (FR-010). PASS.
- **Principle V (Layered Transparency)**: The equivalence tool must distinguish "found equivalence,"
  "no equivalence known," and "not applicable (regenerate_role)" rather than collapsing them (FR-007).
  PASS, provided the stub limitation below is surfaced rather than papered over.

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/004-agent-wiring-fixes/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output (agent tool signatures)
└── tasks.md              # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
cloud-arch-validator-agent/
└── app/
    └── tools.py                      # add_service_to_kg, propose_equivalence rewritten here

cloud-architecture-validator-add/
└── scripts/
    ├── add_service.py                # source of extracted non-interactive functions (unchanged)
    ├── equivalence.py                # propose_equivalence(), find_existing_equivalence() (unchanged)
    ├── kg_io.py                      # write_entry, find_existing, load_services (unchanged)
    ├── propose.py                    # propose_safe_fields, build_update_proposal (unchanged)
    └── provenance.py                 # build_provenance (unchanged)

cloud-architecture-validator-create-architect/
└── references/kg/
    ├── services.yaml                 # written by add_service_to_kg
    └── equivalences.yaml             # written only via existing manual/CLI path; propose_equivalence does not auto-write (Gap 2 is read-only)
```

**Structure Decision**: No new files or directories beyond docs — this is a wiring fix inside the
existing `tools.py`, importing already-tested functions from the sibling `-add` skill's `scripts/`
directory the same way `tools.py` already imports `kg_lib` modules. `propose_equivalence` as an agent
tool stays read-only (recommendation only); it does not call `write_equivalence`, keeping Gap 2's
scope to "surface the recommendation," matching the spec's SC-004 and avoiding a second, less-reviewed
write path into `equivalences.yaml` alongside the CLI's existing one.

## Complexity Tracking

*No constitution violations — table not needed.*
