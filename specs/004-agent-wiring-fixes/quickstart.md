# Quickstart: Validating Agent Wiring Fixes

## Prerequisites

- Repo checked out on branch `004-agent-wiring-fixes`
- `cd cloud-arch-validator-agent && pip install -e .` (or equivalent existing env setup)
- KG at `cloud-architecture-validator-create-architect/references/kg/` present and passing
  `python3 scripts/check_kg.py` before you start (clean baseline to diff against)

## Scenario 1: Add a missing service end-to-end (Story 1)

1. Run the agent locally (existing ADK dev-server command for this project).
2. Ask it to validate an architecture containing a service not in `services.yaml`, e.g.
   `edges: "new-fake-service>cloud-sql"` — expect `UNKNOWN_SERVICE`.
3. Ask the agent to add that service, supplying provider and a references URL.
4. Confirm the agent asks for `network_placement`, `reachability`, `roles` before writing anything
   (FR-002) — answer them.
5. Confirm the agent reports back the exact entry it wrote (FR-010).
6. Inspect `services.yaml` directly: new entry present, `provenance.status: unverified`.
7. Run `python3 scripts/check_kg.py` — should still report clean integrity (coverage % may shift
   slightly with one more node; that's expected, not a regression).
8. Ask the agent to add the same service again — expect it to report the existing entry, not create a
   duplicate (FR-005).

## Scenario 2: Ask for a cross-cloud equivalent (Story 2)

1. Ask the agent for the Azure equivalent of a GCP service known to have a recorded mapping in
   `equivalences.yaml` — expect a `found` result with the recorded target and rationale.
2. Ask for the equivalent of a service with a `regenerate_roles` role (a connector) — expect
   `not_applicable`, not a guess and not `unknown`.
3. Ask for the equivalent of a service with no recorded mapping and no connector role — expect
   `unknown` ("no known equivalent yet"), not a fabricated name.

## Expected outcome

Both scenarios complete without the agent leaving the conversation to invoke an external CLI, and
without the model presenting an unverified guess as though it were a rule-derived or recorded fact.
