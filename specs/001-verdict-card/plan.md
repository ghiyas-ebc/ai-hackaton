# Implementation Plan: Verdict Card

**Branch**: `001-verdict-card` | **Date**: 2026-08-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-verdict-card/spec.md`

## Summary

Turn the existing `validate_architecture` rule-engine output into a structured Verdict Card: one
overall difficulty verdict, every finding tagged with an evidence tier (proven / theoretically possible
/ requires deep review), same-request tech-mismatch entries, an engineer checklist derived from
non-proven findings, and a Gap Record automatically logged for anything uncovered. No new rule engine,
no new KG, no new LLM judgment — this is a deterministic transformation layer on top of `validate()`'s
existing L1-L8 output plus a small mismatch-detection pass and a Gap Record sink.

## Technical Context

**Language/Version**: Python 3.11 (matches `cloud-arch-validator-agent`)

**Primary Dependencies**: None new. Reuses `app/kg_lib/validate.py`, `app/kg_lib/kg.py` (node/provenance
lookup), and the existing ADK `Agent`/tool wiring in `app/agent.py` / `app/tools.py`. PyYAML only,
per root invariant #3 (no new runtime dependency).

**Storage**: Gap Records persist as an append-only local file (`app/references/gap_report.jsonl` or
equivalent), consistent with the "local YAML/JSON, not a database" pattern (D1) already governing this
project — Gap Record volume is request-scale, not warehouse-scale.

**Testing**: pytest, mirroring `cloud-arch-validator-agent/tests/unit/test_tools.py` and the
`check_kg.py` 37/37 regression discipline — a Verdict Card regression fixture set plays the same role.

**Target Platform**: Same as parent agent — runs wherever the ADK agent runs (local dev, Agent Runtime).

**Project Type**: Single project — this is an additional module inside `cloud-arch-validator-agent/app/`,
not a new service.

**Performance Goals**: Card generation must complete within the same call as `validate_architecture`
(sub-second) — SC-001 requires the *card* to be readable in 5 seconds, which is a design/formatting
target, not a latency target, but the transformation itself must not introduce a second network or LLM
round-trip (Verdict-Not-Guess: no LLM step scores anything).

**Constraints**: No LLM in the decision path (Principle I / root invariant #1) — tier classification,
severity rollup, mismatch detection, checklist generation, and Gap Record writes are all pure functions
over `validate()`'s output plus KG lookups, never a model call.

**Scale/Scope**: Same scale as the existing KG (~45 services, single-digit edges per request) — no
scale-driven design decisions needed here.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Verdict-Not-Guess** — PASS. Card fields are computed from `validate()`'s existing `verdict`/
  `severity`/`status` fields and KG `provenance`, via a fixed mapping (Phase 1 data-model). No new model
  call is introduced. Overall difficulty is a deterministic max/rollup over layer statuses, matching
  FR-003's repeatability requirement.
- **II. Evidence-Grounded History** — PASS, with a named limitation carried from spec Assumptions:
  "historical precedent" is backed by KG provenance (`manual`/`verified` vs `unverified`/absent), not a
  separate log of closed deals — no such log exists yet. The card must not imply a richer evidentiary
  base than this. Phase 1 documents the exact mapping so it stays honest about what "proven" means.
- **III. Human Gate on Judgment Calls** — PASS. The card surfaces tiers and mismatches for human
  (rep/engineer) judgment; it does not auto-resolve `Requires Deep Review` findings or silently upgrade
  a tier. No new judgment-field writes to `services.yaml` occur in this feature.
- **IV. Read-Only by Default, Explicit Write Path** — PASS. The only write this feature introduces is
  the Gap Record log, which the constitution explicitly exempts from per-instance human confirmation
  (v1.1.0 amendment). No other persistent write occurs.
- **V. Layered Transparency** — PASS. This principle is close to the feature's entire purpose — FR-004
  (overall verdict must not obscure individual findings) and the tier labels directly implement it.

No violations. Complexity Tracking section is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-verdict-card/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
cloud-arch-validator-agent/
├── app/
│   ├── agent.py                  # ADK agent — instruction updated to describe the card, not prose
│   ├── tools.py                  # new tool: generate_verdict_card (wraps validate_architecture)
│   ├── kg_lib/
│   │   ├── validate.py           # UNCHANGED — remains the rule engine, sole source of verdicts
│   │   ├── kg.py                 # UNCHANGED — provenance/node lookups reused as-is
│   │   └── verdict_card.py       # NEW — pure transformation: validate() output -> Verdict Card
│   └── references/
│       ├── kg/                   # UNCHANGED
│       └── gap_report.jsonl      # NEW — append-only Gap Record log (created on first write)
└── tests/
    └── unit/
        └── test_verdict_card.py  # NEW — regression fixtures for tier mapping, rollup, checklist, gaps
```

**Structure Decision**: Single project, additive module. `verdict_card.py` sits beside `validate.py` in
`kg_lib/` as a second pure-function layer (`validate()` output in, Verdict Card dict out) rather than
modifying `validate.py` itself — keeps the rule engine's existing 37/37 regression fixture untouched and
gives the new logic its own fixture set. `tools.py` gets one new tool function that calls both in
sequence; `agent.py`'s instruction is updated to present the card's fields instead of narrating findings.

## Complexity Tracking

*No constitution violations — section not applicable.*
