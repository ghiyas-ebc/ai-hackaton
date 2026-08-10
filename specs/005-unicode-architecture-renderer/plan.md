# Implementation Plan: Unicode Architecture Renderer

**Branch**: `005-unicode-architecture-renderer` | **Date**: 2026-08-10 | **Spec**: [spec.md](./spec.md)

## Summary

Add deterministic terminal rendering for architecture validation reports. A new renderer module will transform the existing rule-engine report into a stable, width-bounded flowchart using Unicode box drawing by default or strict ASCII glyphs when `ascii_only=True`. The agent wrapper will parse edges, call the unchanged deterministic validator, render its supplied nodes, connectivity results, and findings, and expose only `render_ascii_diagram`; Draw.io remains internal legacy code and is removed from `ALL_TOOLS`.

## Technical Context

**Language/Version**: Python 3.11+ (project supports Python >=3.11,<3.14)

**Primary Dependencies**: Python standard library; existing vendored `kg_lib.validate` and `kg_lib.kg`; PyYAML remains existing KG dependency. No renderer dependency added.

**Storage**: None. Renderer reads in-memory validation output and KG metadata; no files written.

**Testing**: pytest through `cloud-arch-validator-agent/.venv/bin/pytest`; deterministic unit fixtures plus existing integration and KG gate suites.

**Target Platform**: Terminal/chat output on local or deployed Python agent runtime.

**Project Type**: Python ADK agent with vendored deterministic validation library.

**Performance Goals**: Render typical sales architectures (up to 20 nodes and ordinary edge counts) in one synchronous tool call without network access or model calls. Linear work in nodes, edges, and findings is sufficient.

**Constraints**: No LLM in verdict path; no SVG, icons, Draw.io, browser, external rendering, or network dependency; all output lines respect configured width when width is valid; ASCII mode emits only characters in range U+0000–U+007F; repeated input/options produce byte-identical output; unknown and uncovered statuses remain explicit.

**Scale/Scope**: One agent tool and one renderer module. Supports resolved/unknown nodes, duplicate edges, cycles, disconnected components, empty input, findings, and width-bounded labels. Does not redesign validation, KG schema, Draw.io internals, eval conversion, dataset, or metadata.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I — Verdict-Not-Guess: PASS.** Renderer consumes `validate()` output and displays verdict, severity, and status verbatim. It never computes validity or severity.
- **Principle II — Evidence-Grounded History: PASS.** Renderer adds no evidence or claims; it only displays supplied KG metadata and findings.
- **Principle III — Human Gate: PASS.** Renderer performs no writes and does not alter provenance or judgment fields.
- **Principle IV — Read-Only by Default: PASS.** Tool is pure rendering over in-memory data; no KG or report writes.
- **Principle V — Layered Transparency: PASS.** Layer and finding labels remain visible; `UNCOVERED` and `UNKNOWN_SERVICE` are not hidden or normalized away.
- **Product constraints: PASS.** Terminal output is legible, deterministic, offline, and suitable for live conversation.

No constitution violations require complexity justification.

## Research Summary

Phase 0 decisions are recorded in [research.md](./research.md). Key choices:

1. Render the existing validation report rather than introduce a second graph/verdict model.
2. Use deterministic stable ordering and a rank-based layered layout; cycles and disconnected components render as components without recursive traversal.
3. Keep node boxes and edge annotations explicit, using a compact edge list below/alongside nodes where a fully routed graph would violate width bounds.
4. Treat width as a hard output contract for valid widths, sanitize control characters, and replace non-ASCII glyphs/text in ASCII mode.
5. Keep Draw.io code untouched except for removing its agent exposure.

## Project Structure

### Documentation (this feature)

```text
specs/005-unicode-architecture-renderer/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── agent-tools.md
└── tasks.md                         # created by /speckit-tasks
```

### Source Code

```text
cloud-arch-validator-agent/
├── app/
│   ├── renderer.py                  # pure terminal renderer
│   ├── tools.py                     # render_ascii_diagram wrapper; tool registry
│   └── agent.py                     # instructions no longer mention Draw.io
└── tests/
    └── unit/
        ├── test_renderer.py         # renderer fixtures and edge cases
        └── test_tools.py             # wrapper/tool-list assertions
```

Existing `app/kg_lib/emit_drawio.py`, `app/kg_lib/diagram.py`, and related assets remain unchanged legacy/internal code. Existing deterministic validation code remains unchanged.

**Structure Decision**: Put presentation-only logic in `app/renderer.py`, outside vendored `app/kg_lib/`, so vendored skill code does not fork. `tools.py` performs only parsing, validation, and delegation. Unit tests cover renderer behavior directly and tool exposure separately.

## Implementation Phases

### Phase 0 — Research

- Confirm validation report fields and KG resolution behavior.
- Define glyph sets, sanitization, width policy, stable ordering, and layout strategy.
- Record rejected alternatives and boundaries in `research.md`.

### Phase 1 — Design

- Define renderer input entities and output contract in `data-model.md` and `contracts/agent-tools.md`.
- Document fixture-driven quickstart in `quickstart.md`.
- Re-check constitution gates after design.

### Phase 2 — Implementation (via /speckit-tasks)

- Add renderer tests before implementation.
- Implement Unicode and strict ASCII rendering, including statuses/findings and edge cases.
- Add `render_ascii_diagram` wrapper with `ascii_only`, width, and environment options.
- Remove `render_drawio_diagram` from `ALL_TOOLS`; update agent instructions.
- Run full agent tests, KG gate, and integration tests with configured credentials.

## Complexity Tracking

None. Direct pure rendering is simpler than adapting Draw.io XML or introducing a graph-layout dependency.
