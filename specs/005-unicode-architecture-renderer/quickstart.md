# Quickstart: Unicode Architecture Renderer

## Prerequisites

Run from repository root. Agent dependencies must be installed and agent `.venv` available.

```bash
cd cloud-arch-validator-agent
.venv/bin/pytest tests/unit/test_renderer.py tests/unit/test_tools.py
```

Load `.env` only for integration tests that contact Gemini; renderer and unit tests are offline.

## Scenario 1: Unicode terminal diagram

Call tool function with a known architecture:

```python
from app.tools import render_ascii_diagram

result = render_ascii_diagram("cloud-run>cloud-sql", width=100)
print(result["diagram"])
```

Expected:

- `result["format"] == "terminal"`.
- Cloud Run and Cloud SQL appear with provider/category metadata.
- Directed connection appears from Cloud Run to Cloud SQL.
- Validation findings remain visible and retain original severity/rule id.
- Output contains Unicode box/arrows by default.

## Scenario 2: Strict ASCII fallback

```python
result = render_ascii_diagram(
    "cloud-run>cloud-sql",
    ascii_only=True,
    width=80,
)
assert result["diagram"].isascii()
assert all(len(line) <= 80 for line in result["diagram"].splitlines())
```

Expected: same node and edge identities as Unicode output, no non-ASCII characters, no replacement glyphs.

## Scenario 3: Honest incomplete graph

```python
result = render_ascii_diagram(
    "cloud-run>not-in-kg,cloud-sql>cloud-run",
    ascii_only=True,
)
```

Expected: unknown endpoint remains visible with `UNKNOWN_SERVICE`; known edge remains visible; no guessed service name appears.

## Scenario 4: Cycles, duplicates, and disconnected nodes

Use an input containing a cycle and repeated edge, then render twice:

```python
edges = "cloud-run>cloud-sql,cloud-sql>cloud-run,cloud-run>cloud-sql"
a = render_ascii_diagram(edges, ascii_only=True)
b = render_ascii_diagram(edges, ascii_only=True)
assert a["diagram"] == b["diagram"]
```

Expected: call returns without recursion error; all edge identities remain represented; duplicate handling is explicit; repeated output is byte-identical.

## Scenario 5: Agent exposure

```python
from app.tools import ALL_TOOLS, render_ascii_diagram

assert render_ascii_diagram in ALL_TOOLS
assert not any(tool.__name__ == "render_drawio_diagram" for tool in ALL_TOOLS)
```

Agent instructions must describe terminal rendering, not Draw.io file/XML handoff.

## Full validation

```bash
cloud-arch-validator-agent/.venv/bin/pytest cloud-arch-validator-agent/tests/unit cloud-arch-validator-agent/tests/integration
cloud-architecture-validator-create-architect/.venv/bin/python \
  cloud-architecture-validator-create-architect/scripts/check_kg.py
```

If integration credentials are unavailable, report that integration tests were skipped; renderer unit tests must remain offline and pass.
