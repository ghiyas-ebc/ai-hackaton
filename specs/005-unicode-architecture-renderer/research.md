# Research: Unicode Architecture Renderer

## Decision 1: Render validation output, not a second decision model

**Decision**: `render_ascii_diagram` parses the same edge input as existing tools, calls `validate_module.validate()`, and renders returned `connectivity`, resolved KG nodes, `architecture` findings, and layer statuses.

**Rationale**: Validation already resolves aliases, reports `UNKNOWN_SERVICE`, preserves `UNCOVERED`/fallback outcomes, gates dead edges, and computes findings. Reusing that report prevents presentation code from silently creating a second validity path and satisfies Principle I.

**Alternatives considered**:
- Reimplement graph validation in renderer: rejected; duplicates verdict logic and risks disagreement.
- Render raw user text only: rejected; loses resolved metadata and deterministic findings.
- Ask model to describe diagram: rejected; non-deterministic and violates no-LLM decision-path invariant.

## Decision 2: Stable rank-based layout with no recursive traversal

**Decision**: Build a stable node list from report connectivity order, then sort by resolved id; calculate a deterministic rank from incoming edges with bounded relaxation, and render components in stable node order. Use explicit edge annotations to preserve every directed edge, including cycles and duplicates.

**Rationale**: A fully optimized orthogonal graph layout is unnecessary for terminal output and introduces complexity around cycles, disconnected components, and width. Bounded rank calculation avoids infinite recursion. Explicit edge rows guarantee no edge disappears when visual routing is ambiguous.

**Alternatives considered**:
- Recursive DFS tree layout: rejected; cycles can recurse forever and disconnected nodes need separate handling.
- External graph layout library: rejected; adds runtime dependency and conflicts with small offline skill.
- Draw.io XML/SVG conversion: rejected; user explicitly wants terminal output and existing icon path is unreliable.

## Decision 3: Unicode default, strict ASCII glyph set

**Decision**: Unicode mode uses box-drawing borders and directional arrows. ASCII mode uses only portable characters such as `+`, `-`, `|`, `>`, `<`, and `^`/`v` where needed. ASCII mode also transliterates or replaces non-ASCII label characters so `str.isascii()` holds for complete output.

**Rationale**: Unicode improves readability in capable terminals. Strict ASCII must be enforceable for tickets and systems that strip Unicode; merely changing borders is insufficient if service names or findings contain non-ASCII text.

**Alternatives considered**:
- Always ASCII: portable but less readable, and fails requested default.
- Unicode with best-effort encoding: rejected; replacement glyphs violate explicit fallback behavior.
- Preserve arbitrary non-ASCII labels in ASCII mode: rejected; cannot guarantee ASCII-only output.

## Decision 4: Width is a hard contract for valid widths

**Decision**: Accept a documented positive width large enough for minimal node borders. Sanitize newlines and control characters, wrap labels/finding text to interior width, and ensure every emitted line is at most `width` characters. Invalidly small widths return a clear error or use a documented minimum rather than produce malformed borders.

**Rationale**: Terminal and copy/paste consumers need predictable line bounds. Sanitization prevents finding text from breaking the diagram. A minimum width is necessary because a box cannot be represented below its structural border width.

**Alternatives considered**:
- Let long labels overflow: rejected; violates FR-010.
- Truncate without wrapping: rejected; can corrupt service identity and hide status.
- ANSI terminal wrapping: rejected; output then depends on terminal and is not deterministic.

## Decision 5: Findings stay adjacent without changing severity

**Decision**: Node-related findings render in node annotations where practical; edge connectivity findings render in the edge row; global architecture findings render in a deterministic findings section immediately after graph content. Text includes original rule id, severity, verdict/status, and message as supplied.

**Rationale**: Adjacency supports quick diagnosis while a separate section handles findings with no single node/edge. Renderer only formats; it does not reclassify or infer.

**Alternatives considered**:
- Show only highest severity: rejected; hides required findings.
- Put all findings in prose before graph: rejected; weak association with affected elements.
- Alter severities for visual emphasis: rejected; violates FR-006 and Principle I.

## Decision 6: Draw.io stays internal legacy code

**Decision**: Do not delete `emit_drawio.py` or its CLI module in this feature. Remove `render_drawio_diagram` from the agent registry and remove its agent instruction. Keep existing Draw.io unit test only if it still tests internal compatibility; add assertions that new registry excludes it.

**Rationale**: User asks to stop agent-facing Draw.io output, not remove unrelated internal code. Narrow change reduces regression risk and preserves possible future non-agent use.

**Alternatives considered**:
- Delete all Draw.io code/assets: rejected; larger scope and no need for terminal renderer.
- Keep Draw.io exposed alongside terminal renderer: rejected; agent may choose unreliable path and violates FR-013.
