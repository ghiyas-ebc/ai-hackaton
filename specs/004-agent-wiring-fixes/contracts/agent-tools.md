# Contract: Agent tool signatures

These are the two tool functions `tools.py` exposes to the ADK agent, replacing the stub and the
missing tool. Signatures, not implementations — implementation is Phase 2/tasks work.

## `add_service_to_kg`

```python
def add_service_to_kg(
    name: str,
    provider: str,                 # "gcp" | "azure"
    network_placement: str,        # human-supplied judgment field, e.g. "public private"
    reachability: str,             # human-supplied: "public_only" | "private_only" | "public_or_private"
    roles: list[str],              # human-supplied
    references_url: str = "",
) -> dict:
    """Add one service to the knowledge graph, or report an existing match.

    Preconditions: caller (the agent) MUST have already collected network_placement,
    reachability, and roles from the human in conversation — this function does not
    prompt for them and does not infer them.

    Returns one of:
      {"written": True, "entry": {...}}                    — new entry created, status=unverified
      {"written": False, "existing": {...}}                 — duplicate found, nothing written
      {"written": False, "error": "missing_field", "field": "..."} — precondition violated
    """
```

**Contract notes**:
- Never writes when any of `network_placement`, `reachability`, `roles` is empty/None — the caller
  (agent) is expected to have gathered these, but the function re-validates rather than trusting the
  caller, since a missing field silently defaulting is exactly the failure D6 exists to prevent.
- On success, echoes back the full written entry (FR-010) so the agent can show it to the engineer for
  visual confirmation.
- Idempotent against duplicates: existing (name, provider) short-circuits to a report, never a second
  write (FR-005).

## `propose_equivalence`

```python
def propose_equivalence(
    service_name: str,
    provider_from: str,            # "gcp" | "azure"
) -> dict:
    """Look up or propose a cross-cloud equivalent for a service. Read-only — does not write.

    Returns one of:
      {"status": "found", "equivalence": {...}}              — recorded in equivalences.yaml
      {"status": "not_applicable", "reason": "connector role has no equivalent by design"}
      {"status": "unknown", "message": "no known equivalent yet"}
    """
```

**Contract notes**:
- Checks `find_existing_equivalence()` against the loaded `equivalences.yaml` first (FR-006 scenario 1).
- If the service's role is in `regenerate_roles` (connectors excluded by design, per CLAUDE.md D23/L8),
  returns `not_applicable`, never `unknown` (FR-007) and never a fabricated name.
- Otherwise returns `unknown` — it MUST NOT surface `equivalence.propose_equivalence()`'s placeholder
  `service_name_to` value as if it were a real recommendation (see research.md).
