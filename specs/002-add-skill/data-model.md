# Phase 1 Data Model: Add-Service Skill

Only one entity is persisted (Service Entry, into `services.yaml`); the rest are transient to a
single `add_service.py` run.

## ServiceProposal (transient)

Built after the duplicate check passes, before any human input.

| Field | Type | Notes |
|---|---|---|
| `name` | string | As requested by the caller. |
| `provider` | enum: `gcp` \| `azure` | As requested by the caller. |
| `category` | string \| null | Agent-fetched; null if unresolved (Edge Case). |
| `description` | string \| null | Agent-fetched; null if unresolved. |
| `references_url` | string \| null | Agent-fetched and link-checked; null if it didn't resolve. |
| `icon` | string \| null | Resolved via `kg.py`'s `icon_for()` mechanism; null if unresolved. |
| `sources` | list[string] | URLs actually consulted while fetching the above — feeds `provenance.sources` (FR-007) regardless of whether the fetch succeeded. |
| `unresolved_fields` | list[string] | Names of any of the four safe fields that came back null — surfaced to the human, never silently dropped. |

## JudgmentQuestionBatch (transient)

Presented to the human in one turn, per research.md's "single batch" decision.

| Field | Type | Notes |
|---|---|---|
| `network_placement` | string \| draft \| unanswered | Starts unanswered for a fresh add (FR-004); may start as an unconfirmed `draft` value with rationale for an update (FR-012) — a `draft` is not an `answer` until explicitly confirmed. |
| `reachability` | string \| draft \| unanswered | Same. |
| `roles` | list[string] \| draft \| unanswered | Same. |
| `all_answered` | bool (derived) | `true` only when none of the three fields are `unanswered` **or** `draft` — an unconfirmed draft blocks a write exactly like an unanswered field (FR-005, FR-012). |

## UpdateProposal (transient)

Built instead of ServiceProposal when FR-002/FR-011's staleness check finds a newer reference
against an existing entry.

| Field | Type | Notes |
|---|---|---|
| `existing_entry` | dict | Full current record from `services.yaml`, unmodified. |
| `reference_url` | string | The newer reference supplied by the requester. |
| `reference_checked_at` | date | Compared against the existing entry's last-checked date (FR-011). |
| `draft_fields` | dict[str, any] | Reference-derived draft values for all fields, including `network_placement`/`reachability`/`roles`. |
| `draft_rationale` | dict[str, string] | Per-field note on what in the reference supports that draft (FR-012's "labeled" requirement). |
| `changed_fields` | list[string] | Which fields actually differ from `existing_entry` — presented to the human as the diff. |

`UpdateProposal`'s three judgment-field drafts flow into the same `JudgmentQuestionBatch` shape as
a fresh add (pre-filled with the draft value + rationale instead of starting blank), so the
all-or-nothing confirm gate (FR-005/FR-012) applies identically either way.

## Confirmation (transient)

The human's final response to the full proposal (safe fields + judgment answers).

| Field | Type | Notes |
|---|---|---|
| `field_overrides` | dict[str, any] | Any correction to an agent-proposed safe field (FR-006/US3) — keyed by field name, only present for fields the human changed. |
| `judgment_answers` | JudgmentQuestionBatch | Must have `all_answered == true`. |
| `confirmed` | bool | `false`/absent means abandon — FR-010 requires this to result in zero writes. |

## ServiceEntry (persisted)

The record appended to `services.yaml`'s `services:` list. Shape matches existing entries in the
file (see `services.yaml`'s own header comments for the full schema); this feature only fixes the
`provenance` sub-block's values, not the rest of the node schema.

| Field | Type | Notes |
|---|---|---|
| `id` | string | Derived slug from `name`/`provider`, following the file's existing convention. |
| `name`, `provider`, `category`, `description`, `references_url`, `icon` | various | Merged from ServiceProposal, with any `field_overrides` applied. |
| `network_placement`, `reachability`, `roles` | various | From `Confirmation.judgment_answers` — always human-sourced, never from ServiceProposal. |
| `provenance.generated` | literal `"cloud-architecture-validator-add"` | Fixed by FR-007 — never any other value from this tool. |
| `provenance.status` | literal `"unverified"` | Fixed by FR-008 — this tool never writes `verified` or `manual`. On an update, this resets to `unverified` even if the entry was previously `verified` (FR-013) — the update invalidates the prior sign-off. |
| `provenance.sources` | list[string] | Copied from `ServiceProposal.sources`. |

## State / lifecycle

`ServiceProposal` → `JudgmentQuestionBatch` → `Confirmation` is a strict linear flow within one
invocation; there is no persistence of intermediate state between runs (spec Assumption: no
queue/ticketing UI exists yet). If the flow ends without `Confirmation.confirmed == true`,
nothing downstream of `ServiceProposal` is ever written — `services.yaml` is untouched. Once a
`ServiceEntry` is written, its only further lifecycle transition (status `unverified` →
`verified`) is out of scope for this feature (spec Assumption) and happens via a separate manual
edit, not this tool — this holds whether the entry arrived via a fresh add or an update; an
update always lands back at `unverified`, never inheriting the prior entry's `verified` status
(FR-013).

`UpdateProposal` follows the same linear flow as a fresh add, just seeded from `existing_entry`
instead of starting blank: `UpdateProposal` → `JudgmentQuestionBatch` (pre-filled as `draft`) →
`Confirmation`. If the flow ends without `Confirmation.confirmed == true`, `existing_entry`
remains byte-for-byte in `services.yaml`, identically to FR-010's abandon behavior for a fresh
add.
