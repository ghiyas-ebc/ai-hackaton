# Data Model: Unicode Architecture Renderer

## Architecture graph input

Produced internally from `edges` plus the deterministic KG validator.

| Field | Shape | Rule |
|---|---|---|
| `nodes` | ordered list of rendered node records | Include every resolved node referenced by input connectivity; unknown endpoints remain represented by edge identity and status. |
| `edges` | ordered list of edge records | Preserve every input connection, including duplicate and cyclic edges. |
| `findings` | ordered list of node, edge, or global findings | Copy rule-engine findings without changing severity, verdict, rule id, or message. |
| `layers` | ordered list of layer status records | Preserve `CLEAN`, severity, and `UNCOVERED` status for context where shown. |

## Rendered node

| Field | Shape | Rule |
|---|---|---|
| `id` | string | Stable KG id, or raw unknown endpoint id. |
| `name` | string | Human-readable KG name when resolved; raw id otherwise. |
| `provider` | string or absent | Show when resolved; unknown nodes show `provider: unknown`. |
| `category` | string or absent | Show when resolved; omit only when unavailable. |
| `roles` | list of strings | Optional metadata; stable sorted order if displayed. |
| `status` | optional status string | `UNKNOWN_SERVICE` for unresolved node references; never guessed. |
| `findings` | list of annotations | Findings associated with this node, preserving source severity and rule id. |

## Rendered edge

| Field | Shape | Rule |
|---|---|---|
| `source` | string | Original/resolved source identity from validator output. |
| `target` | string | Original/resolved target identity from validator output. |
| `arrow` | glyph string | Directional glyph selected by mode. |
| `verdict` | string | Copy connectivity verdict, including `UNKNOWN_SERVICE`, `UNCOVERED`, `BLOCKED`, or `NEEDS_COMPONENT`. |
| `severity` | optional string | Copy supplied severity. |
| `rule_id` | optional string | Copy supplied rule id. |
| `message` | optional string | Sanitized and wrapped annotation. |
| `findings` | list | Edge-associated architecture findings, if any. |

## Render options

| Field | Default | Rule |
|---|---|---|
| `ascii_only` | `False` | Unicode mode when false; strict ASCII output when true. |
| `width` | `100` | Maximum output line width. Must be positive and above documented minimum. |
| `environment` | `poc` | Passed to existing validator only; does not affect formatting. |

## Output invariants

1. Output is a string inside a tool result with `format: "terminal"`, `ascii_only`, and `width` metadata.
2. Node and edge identity appears at least once, including unresolved identities.
3. Every input edge appears as a directed edge row or explicit duplicate-edge summary retaining source and target.
4. `UNKNOWN_SERVICE` and `UNCOVERED` appear literally when present.
5. No line exceeds valid configured width.
6. ASCII mode output satisfies `output.isascii()`.
7. Same report and options produce byte-identical output.
8. Empty input returns explicit empty-architecture text.
