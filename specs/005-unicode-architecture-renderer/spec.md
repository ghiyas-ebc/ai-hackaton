# Feature Specification: Unicode Architecture Renderer

**Feature Branch**: `005-unicode-architecture-renderer`

**Created**: 2026-08-10

**Status**: Draft

**Input**: User description: "Replace agent-facing Draw.io diagram output with a deterministic terminal architecture renderer using Unicode box-drawing by default and strict ASCII fallback. Render services as labeled nodes, directed connections as arrows, provider/category metadata, validation findings near affected nodes or edges, UNKNOWN_SERVICE and UNCOVERED explicitly, disconnected nodes and cycles safely, width-bounded wrapped labels, deterministic output for tests. Add `render_ascii_diagram` agent tool with `ascii_only` option. Remove or stop exposing `render_drawio_diagram` from the agent tool list; preserve existing Draw.io implementation only as deprecated internal code unless plan determines removal is safe. No SVG/icon embedding, browser, or external rendering dependency. Keep rule engine as sole verdict source. Scope excludes live eval conversion and unrelated evaluation gaps."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sales engineer gets a readable terminal architecture (Priority: P1)

A sales or presales engineer asks the agent to show an architecture while working in a terminal or
chat that cannot reliably display Draw.io files. The agent returns a compact flowchart with labeled
service boxes, directed arrows, provider/category context, and validation findings that can be read,
quoted, and pasted into a proposal without opening another application.

**Why this priority**: Terminal-readable output removes the broken icon/SVG and file-handling path
from the primary user experience while keeping architecture communication available everywhere the
agent runs.

**Independent Test**: Call the architecture-rendering tool with a known multi-service architecture
and verify that output contains every service, directed connection, provider/category metadata, and
stable box-and-arrow layout without any Draw.io XML or icon data.

**Acceptance Scenarios**:

1. **Given** a valid architecture with a linear or branching flow, **When** the engineer asks for a
   diagram, **Then** the agent returns a deterministic box-and-arrow flowchart with service labels and
   directed connections.
2. **Given** the same architecture rendered twice with the same options, **When** outputs are
   compared, **Then** they are byte-for-byte identical.
3. **Given** an architecture with a validation finding on a node or edge, **When** the diagram is
   rendered, **Then** the finding appears adjacent to the affected element without replacing or
   hiding the architecture.
4. **Given** a service with provider and category metadata, **When** rendered, **Then** the node
   label includes that metadata in a readable form.

---

### User Story 2 - Engineer uses plain ASCII fallback (Priority: P2)

An engineer works in a restricted terminal, plain-text ticket, or system that strips Unicode. They
request strict ASCII mode and receive a structurally equivalent diagram using only portable ASCII
characters.

**Why this priority**: Unicode improves readability, but ASCII compatibility makes the tool usable in
more terminals and preserves copy/paste fidelity across systems.

**Independent Test**: Render one architecture with the fallback option enabled and verify every output
character is ASCII, while node and edge information remains present and ordering matches Unicode mode.

**Acceptance Scenarios**:

1. **Given** a supported architecture, **When** `ascii_only` is enabled, **Then** output contains no
   non-ASCII characters and still shows all nodes, arrows, and findings.
2. **Given** a label longer than the configured display width, **When** rendered in either mode,
   **Then** the label wraps within the width bound without corrupting service identity.
3. **Given** an environment that cannot display Unicode, **When** the agent renders with fallback
   enabled, **Then** it does not error, emit replacement glyphs, or silently omit nodes.

---

### User Story 3 - Engineer sees incomplete or unusual graph shapes honestly (Priority: P3)

An engineer asks to render an architecture containing an unknown service, an uncovered connection,
a cycle, or disconnected components. The output makes those conditions explicit and still renders all
available information instead of guessing, crashing, or dropping graph elements.

**Why this priority**: Honest incomplete output supports the product's no-guessing principle and is
more useful than a polished but misleading diagram.

**Independent Test**: Render fixtures covering unknown services, uncovered edges, cycles, and isolated
nodes; verify each fixture returns output with explicit status labels and no exception.

**Acceptance Scenarios**:

1. **Given** an unknown service, **When** rendered, **Then** the node remains visible and is labeled
   `UNKNOWN_SERVICE`.
2. **Given** an uncovered connection, **When** rendered, **Then** the edge remains visible and is
   labeled `UNCOVERED` or equivalent explicit status.
3. **Given** a cyclic graph, **When** rendered, **Then** all cycle members and connections appear with
   a stable layout; renderer does not recurse indefinitely.
4. **Given** disconnected components, **When** rendered, **Then** every component appears in the same
   output and none is silently discarded.

---

### Edge Cases

- Empty architecture input returns a clear empty-diagram message, not a blank response or exception.
- A node or finding label contains punctuation, whitespace, or a very long value; output remains
  bounded and readable.
- Multiple edges connect the same pair; each edge remains distinguishable or is explicitly summarized.
- A graph contains both providers; provider labels prevent cross-provider identity confusion.
- A finding contains newline characters or non-ASCII text; renderer sanitizes/wraps it without
  breaking box borders or ASCII-only guarantees.
- Existing Draw.io rendering remains callable only through explicitly internal/deprecated code and is
  not offered to the agent as a tool.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose one agent-facing architecture renderer that returns terminal
  flowchart text rather than Draw.io XML.
- **FR-002**: The renderer MUST use Unicode box-drawing characters and directional arrows by default.
- **FR-003**: The renderer MUST support an `ascii_only` option that restricts output to ASCII
  characters while preserving graph information and node ordering.
- **FR-004**: Every resolved service in the input MUST appear as a labeled node containing service
  identity, provider, and category where available.
- **FR-005**: Every input connection MUST appear as a directed edge or an explicit summarized edge,
  retaining source and target identity.
- **FR-006**: Validation findings MUST be rendered adjacent to their affected node or edge and MUST
  not be converted into a different severity or verdict by the renderer.
- **FR-007**: Unknown services MUST remain visible and carry an explicit `UNKNOWN_SERVICE` label.
- **FR-008**: Uncovered connections MUST remain visible and carry an explicit `UNCOVERED` label.
- **FR-009**: Cycles, disconnected components, duplicate edges, and empty input MUST render safely with
  explicit, deterministic behavior.
- **FR-010**: Labels MUST be sanitized and wrapped to a documented maximum width; no output line may
  exceed the configured width bound except where the bound is itself invalid.
- **FR-011**: Rendering the same input and options repeatedly MUST produce identical output.
- **FR-012**: The renderer MUST have no runtime dependency on SVG files, icons, Draw.io, browser APIs,
  or external rendering services.
- **FR-013**: The agent MUST stop exposing `render_drawio_diagram` as an available tool. Existing
  Draw.io code MAY remain as deprecated internal code if removal would exceed this feature's scope.
- **FR-014**: The renderer MUST use validation and knowledge-graph results as supplied by the existing
  deterministic rule engine and MUST NOT infer validity, severity, or service equivalence.

### Key Entities

- **Architecture graph**: Service nodes and directed connections supplied for rendering, including
  resolved metadata and validation results.
- **Rendered node**: A bounded text box containing service identity, provider, category, and optional
  status/finding annotations.
- **Rendered edge**: A directional connector between node labels, optionally annotated with
  connectivity status or finding severity.
- **Render options**: Display width, ASCII-only mode, and stable ordering settings controlling output
  shape without changing architecture meaning.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of nodes and input connections in fixed renderer fixtures appear in returned output,
  including unknown and uncovered elements.
- **SC-002**: Repeated rendering of identical input produces identical output in 100% of deterministic
  test runs.
- **SC-003**: 100% of `ascii_only` outputs pass an ASCII-character validation check.
- **SC-004**: At least 95% of renderer output lines remain within the configured width in representative
  architecture fixtures, with intentional handling documented for invalidly small widths.
- **SC-005**: Cycle, disconnected-component, duplicate-edge, unknown-service, uncovered-edge, and empty
  input fixtures complete without renderer exceptions.
- **SC-006**: Agent tool inspection confirms Draw.io renderer is unavailable while terminal renderer is
  available.

## Assumptions

- Existing validation functions continue to provide connectivity and architecture findings; this
  feature changes presentation, not verdict computation.
- Unicode box drawing is acceptable as default terminal output; `ascii_only` exists for strict
  compatibility.
- Deterministic layout uses stable service/edge ordering rather than attempting optimal graph layout;
  predictable output matters more than minimizing every line.
- Existing Draw.io implementation and icon assets are not deleted unless implementation planning
  finds removal necessary and safe; they are simply removed from the agent-facing tool list.
- Live eval conversion, basic evaluation dataset replacement, author metadata, and unrelated
  knowledge-graph changes remain out of scope.
