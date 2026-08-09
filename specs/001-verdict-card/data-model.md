# Phase 1 Data Model: Verdict Card

All entities below are transient dicts produced by `verdict_card.py`, except Gap Record, which is
persisted. None require a new KG schema change — `services.yaml`, `connectivity-rules.yaml`, and
`architecture-rules.yaml` are read-only inputs to this feature.

## VerdictCard

Top-level object returned by the new `generate_verdict_card` tool.

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | Independent of `validate()`'s `schema_version`; starts at `"1.0"`. |
| `difficulty` | enum: `Low` \| `Medium` \| `High` \| `Unassessed` | `Unassessed` per spec edge case: every finding uncovered. |
| `difficulty_reason` | string | Names the specific finding(s)/layer(s) that drove the verdict (FR-004). |
| `findings` | list[Finding] | One per connectivity/architecture finding from `validate()`, always present even when tier is Proven. |
| `mismatches` | list[MismatchEntry] | May be empty. |
| `checklist` | list[ChecklistItem] | May be empty; `checklist_empty_reason` set when so (FR-007). |
| `checklist_empty_reason` | string \| null | e.g. `"All findings proven — no follow-up required."` |
| `assumptions` | list[string] | Explicitly stated substitutions made for missing rep-supplied context (FR-010). |
| `context` | dict | Passed through from `validate()`'s `context` (environment, residency, sla_tier). |

## Finding

| Field | Type | Notes |
|---|---|---|
| `layer_id` | string | `L1`-`L8`, from `validate()`'s layer report. |
| `subject` | string | Edge (`source -> target`) or node id the finding is about. |
| `tier` | enum: `Proven` \| `Theoretically Possible` \| `Requires Deep Review` | Per research.md mapping — exactly one, never absent (FR-002, SC-002). |
| `severity` | string \| null | Carried through from the underlying `validate()` verdict/status when present. |
| `supporting_detail` | string | What backs the tier: rule id + verified node provenance, or "no matching rule/history", or the conflict description. |

## MismatchEntry

| Field | Type | Notes |
|---|---|---|
| `stated_choice` | string | The technology/service the client named. |
| `actual_need` | string | The service/role the underlying requirement actually maps to. |
| `explanation` | string | One-line reason, from the mismatch rule table (research.md). |

## ChecklistItem

| Field | Type | Notes |
|---|---|---|
| `source_finding` | string | `subject` of the Finding this item was generated from — 1:1, never orphaned (SC-004). |
| `action` | string | Concrete task text, from the tier-specific template. |

## GapRecord (persisted)

One JSON object per line in `app/references/gap_report.jsonl`.

| Field | Type | Notes |
|---|---|---|
| `logged_at` | string (ISO 8601) | Wall-clock time of the request, not of card generation retries. |
| `request_summary` | string | Edges/services as parsed from the rep's input. |
| `unresolved_element` | string | The specific edge/service/layer that was uncovered or unknown. |
| `reason` | string | Why it's uncovered — layer's `why_uncovered` text, or "unknown service id". |

Validation rule: every occurrence is appended as a new line — no read-modify-write, no dedup key. This
is the mechanism, not just the intent, behind FR-009.

## State / lifecycle

VerdictCard, Finding, MismatchEntry, ChecklistItem have no persistence or state transitions — they are
computed fresh per request and returned to the calling agent turn. GapRecord is append-only; it is
never updated or deleted by this feature (out of scope per spec Assumptions — consumption/rotation is a
later concern).
