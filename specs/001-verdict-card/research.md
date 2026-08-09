# Phase 0 Research: Verdict Card

No open NEEDS CLARIFICATION markers came out of Technical Context — this feature is additive over an
existing, well-understood rule engine. The research below resolves the design decisions the plan
deferred, not unknowns about external technology.

## Evidence tier mapping

**Decision**: Map each finding to a tier using two existing signals already returned by `validate()` and
`kg.py` — no new data is collected:

| Tier | Condition |
|---|---|
| **Proven** | Finding's layer status is `CLEAN`, or the specific connectivity/architecture rule fired with a definite verdict, AND every node involved has `provenance.status` of `manual` or `verified`. |
| **Theoretically Possible** | Layer status is `UNCOVERED` (no rule matched) but no involved node is itself `unverified`, and nothing else about the request conflicts with a known constraint. |
| **Requires Deep Review** | Layer status carries `ERROR`/`WARNING` severity, OR any involved node's `provenance.status` is `unverified`, OR the service/edge could not be resolved at all (`UNKNOWN_SERVICE`). |

**Rationale**: `validate()` already distinguishes CLEAN / UNCOVERED / severity-bearing findings per
layer (`_layer_report`), and `kg.py` node entries already carry `provenance.status`. Reusing both
signals means tier classification is a lookup, not a new judgment — satisfies Verdict-Not-Guess.

**Alternatives considered**: A fourth tier for "conflicting evidence" (rule says no, a KG entry implies
yes) was considered and rejected — the spec's edge case for this explicitly resolves it by rule
precedence, so it collapses into Requires Deep Review with the conflicting note preserved in supporting
detail, not a separate tier.

## Overall difficulty rollup

**Decision**: Reuse the existing `SEVERITY_ORDER` max-rollup already used for `summary.highest_severity`
in `validate.py`, extended one level: if the rolled-up severity is `ERROR` → High; `WARNING` → Medium;
`INFO` or clean-with-all-proven → Low; if any layer is `UNCOVERED` and nothing scored ERROR/WARNING →
Medium (can't confirm low difficulty when something wasn't checked, matches the edge case in spec).

**Rationale**: Deterministic, already-computed input (`SEVERITY_ORDER`); satisfies FR-003 (repeatable)
without inventing a new scoring formula.

**Alternatives considered**: A weighted numeric score (e.g. count of ERROR/WARNING findings) was
considered — rejected because a single WARNING and ten WARNINGs both mean "some risk, human should
look," and a numeric score implies a precision the KG data doesn't support (same reasoning as D14 in the
parent skill's decision log: don't present unmeasured precision as fact).

## Tech-mismatch detection

**Decision**: Detect mismatch when the sales rep's parsed request names a specific technology/service id
that resolves via `kg.lookup`/`search_services`, but the request's underlying requirement (inferred from
role/category the rep also states, e.g. "we need real-time updates") matches a *different* service's
role better than the named one's. Implemented as a small rule table (role → best-fit category/roles),
not a KG schema change.

**Rationale**: Spec explicitly scopes this to within-request (client's stated word vs. actual need), a
different concern from `translate.py`'s cross-provider equivalence mapping. Reusing `search_services`
means no new lookup infrastructure.

**Alternatives considered**: Doing mismatch detection via the LLM directly (let the model just notice the
client asked for the wrong thing) — rejected, violates Verdict-Not-Guess; the *determination* that X
doesn't fit Y must be table-driven so it's auditable, even though the LLM still does the job of noticing
which words in the client's request to check against the table.

## Gap Record storage

**Decision**: Append-only JSON Lines file, `app/references/gap_report.jsonl`, one line per gap
occurrence: `{timestamp, request_summary, unresolved_element, reason}`. No dedup, no schema beyond flat
fields (FR-009 requires every occurrence recorded, not merged).

**Rationale**: Matches root invariant #1 (D1 in parent skill) — file-scale data, no network/DB
dependency, consistent with the pattern used everywhere else in this KG. A structured log a Product-side
process can later batch-review; this feature does not build that review tooling, only the write path
(spec Assumption explicitly scopes notification/consumption out).

**Alternatives considered**: Writing to `services.yaml` or another KG file — rejected, Gap Records are
not knowledge-graph nodes and mixing them in would violate the "one file, one purpose" pattern the KG
already follows, and would put them under `check_kg.py`'s structural checks for no reason.

## Checklist generation

**Decision**: One checklist item per non-Proven finding, templated from the finding's tier and rule/gap
reason: e.g. "Confirm reachability path for `<edge>` — no prior verified instance" (Theoretically
Possible) or "Review `<rule_id>` violation on `<edge>` before committing" (Requires Deep Review).

**Rationale**: Direct 1:1 mapping keeps SC-004 mechanically verifiable and keeps checklist generation a
template substitution, not a generative step — no LLM judgment on *what* to check, only formatting.
