# Data Model: Agent Wiring Fixes

No new persisted schema — this feature writes through the existing `services.yaml` entry shape
(unchanged, see `cloud-architecture-validator-create-architect/references/kg/services.yaml`) and reads
the existing `equivalences.yaml` shape. Documented here for reference, not as new design.

## Service entry (existing shape, write target of `add_service_to_kg`)

| Field | Source | Notes |
|---|---|---|
| `id` | derived | slug of `name` |
| `name`, `provider` | agent-collected | identity fields |
| `category`, `description`, `references_url`, `icon` | `propose_safe_fields()` | agent-verifiable, per CLAUDE.md's split of verifiable vs. judgment fields |
| `network_placement`, `reachability`, `roles` | **human-supplied**, passed as explicit tool parameters | judgment fields — never inferred (FR-002, FR-003) |
| `provenance` | `build_provenance()` | `status: unverified` always on this path (FR-004) |

## Equivalence proposal (existing shape, read-only for this feature)

| Field | Source | Notes |
|---|---|---|
| `provider_from`, `service_name_from` | tool input | the service the engineer asked about |
| `provider_to`, `service_name_to` | `find_existing_equivalence()` (recorded) or `propose_equivalence()` (placeholder) | see research.md — placeholder case must be reported as "no known equivalent yet," not as a name |
| `confidence`, `rationale`, `sources` | same | relayed as-is for the engineer to sanity-check (spec's Key Entities: "enough reference information for a human to sanity-check") |

## State transitions

None — both operations are single-step (collect → validate presence of required fields → write-or-report).
No entry moves through intermediate persisted states within this feature; `status: unverified → verified`
remains a separate, existing human action outside this feature's scope (CLAUDE.md D21).
