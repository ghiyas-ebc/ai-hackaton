# Agent Tool Contract: `render_ascii_diagram`

## Signature

```python
render_ascii_diagram(
    edges: str,
    environment: str = "poc",
    ascii_only: bool = False,
    width: int = 100,
) -> dict
```

## Input

- `edges`: comma-separated directed pairs in existing tool syntax, for example `cloud-run>cloud-sql,cloud-sql>gcs`.
- `environment`: existing validator context (`poc`, `staging`, or `production` as accepted by wrapper conventions).
- `ascii_only`: strict portable output switch.
- `width`: positive maximum line width; renderer documents/rejects values below minimum structural width.

## Output

```json
{
  "format": "terminal",
  "ascii_only": false,
  "width": 100,
  "diagram": "...terminal text...",
  "node_count": 2,
  "edge_count": 1,
  "finding_count": 3
}
```

`diagram` is deterministic terminal text. It contains node boxes, directed edge rows, status labels, and findings. Errors use existing malformed-edge behavior or a structured tool error; renderer must not silently drop graph elements.

## Rendering rules

- Default uses Unicode box borders and directional arrows.
- `ascii_only=True` uses ASCII borders/arrows and sanitizes all labels/findings until `diagram.isascii()` is true.
- Every resolved node shows id/name, provider, and category where available.
- Unknown endpoint remains visible and includes `UNKNOWN_SERVICE`.
- Uncovered connectivity remains visible and includes `UNCOVERED`.
- Every edge retains source and target direction; duplicate edges retain separate rows or explicit count plus identities.
- Findings show original `rule_id`, severity, verdict/status, and sanitized message. No severity conversion.
- Cycles and disconnected components render without recursion or omission.
- Empty edge input returns explicit empty architecture message.
- Output lines stay within `width` for valid widths.

## Agent exposure

`render_ascii_diagram` appears in `app.tools.ALL_TOOLS`. `render_drawio_diagram` does not appear in `ALL_TOOLS` and must not be recommended by agent instructions. Existing Draw.io modules may remain callable through internal code.
