# Tool Contract: `generate_verdict_card`

New ADK tool in `app/tools.py`, exposed to `root_agent` alongside the existing nine tools.

## Signature

```python
def generate_verdict_card(
    edges: str,
    environment: str = "poc",
    data_residency: str = "none",
    sla_tier: str = "standard",
    stated_needs: str = "",
) -> dict:
```

- `edges`, `environment`, `data_residency`, `sla_tier`: identical contract to the existing
  `validate_architecture` tool — this tool calls it internally, it does not replace it.
- `stated_needs` (new): free-text, comma-separated statements of what the client said they need
  (e.g. `"real-time updates,strict consistency"`), used only for mismatch detection (User Story 2).
  Optional — omitting it means the `mismatches` list is always empty, which is a valid, non-error
  result (mirrors the existing "UNCOVERED is a valid answer" pattern).

## Return shape

Returns a `VerdictCard` dict per `data-model.md`. This is the literal tool return value — the agent
relays its fields, it does not reformat or re-derive them (Constitution Principle I: the tool decides,
the model communicates).

## Preconditions

- Same as `validate_architecture`: `edges` must parse as `source>target` pairs; unresolvable service
  ids are not an error, they surface as `Requires Deep Review` findings with `UNKNOWN_SERVICE` detail.

## Postconditions

- `findings` has exactly one entry per finding `validate()` produced (connectivity + architecture),
  none dropped, none added.
- `checklist` has exactly one entry per finding whose `tier != "Proven"`.
- If any finding's underlying layer status is `UNCOVERED` or `UNKNOWN_SERVICE`, exactly one `GapRecord`
  is appended to `app/references/gap_report.jsonl` per such finding, before the tool returns — this is
  a side effect but is unconditional (not gated on a confirmation, per Principle IV).
- `difficulty` is a pure function of `findings`— calling this tool twice with identical `edges`/context
  produces an identical `difficulty` (SC-005). `assumptions` and Gap Record timestamps may legitimately
  differ across calls; `difficulty` and `findings[*].tier` must not.

## Failure modes

- Malformed `edges` string: raises the same `SystemExit`-style error `validate_architecture` already
  raises for this — not a new failure mode, not caught and reinterpreted here.
- No new network, filesystem-beyond-the-KG-and-log, or credential dependency introduced.
