# Phase 0 Research: Add-Service Skill

No open NEEDS CLARIFICATION markers came out of Technical Context — the existing
`cloud-architecture-validator-add` SKILL.md design stub and root CLAUDE.md decisions (D6, D12,
D20, D21) already fixed the hard calls. The research below resolves implementation-shape
decisions the plan deferred, not unknowns about external technology.

## Human-confirmation UX shape

**Decision**: A single question batch per service — one prompt turn presenting all three
judgment fields (`network_placement`, `reachability`, `roles`) together with the agent's proposed
safe fields shown alongside for context, rather than one question at a time across multiple
turns.

**Rationale**: D20 says reuse `tools/review_queue.yaml`'s four-question-per-candidate shape from
the Terraform-schema sync path — that format already batches judgment questions per candidate
rather than drip-feeding them. Matches FR-004/FR-005 (nothing writes until *all* are answered) —
a single batch makes "all answered" a natural single confirmation step instead of tracking
partial state across turns.

**Alternatives considered**: One field at a time, conversational — rejected as unnecessary
overhead for three fixed fields with no branching logic between them; batching also makes the
FR-010 abandon-clears-everything behavior trivial (no batch confirmed = nothing written, no
partial state to reconcile).

## Duplicate detection

**Decision**: Match on `(name, provider)` case-insensitive against existing `services.yaml`
entries before proposing anything. A match short-circuits straight to reporting the existing
entry — no proposal, no judgment questions asked.

**Rationale**: FR-002 requires this before any proposal work happens, not as a post-write
dedup — asking judgment questions for a service that already exists wastes the human's time on
a question that's about to be discarded. `(name, provider)` is the same key a human skimming
`services.yaml` would use; `id` is a derived slug and can differ.

**Alternatives considered**: Matching on `id` alone — rejected, two independently-proposed
entries for the same real service could generate different slugs (e.g. `cloud-sql` vs.
`cloud-sql-postgres`) and still collide semantically; name+provider is the actual identity.

## Safe-field fetch failure handling

**Decision**: Each safe field (`category`, `description`, `references_url`, `icon`) fails
independently. A dead `references_url` or unresolvable icon does not block the other fields or
the judgment-question stage — it's surfaced as "could not verify, confirm or supply manually"
alongside the fields that did resolve.

**Rationale**: Matches spec Edge Cases directly. Blocking the whole add on one cosmetic/reference
field (icon, docs link) would make the tool less useful than a human just hand-editing the YAML,
which defeats the purpose of building it. `category`/`description` failing is treated the same
way — not fatal, just flagged.

**Alternatives considered**: Hard-fail the whole proposal if any safe field can't be fetched —
rejected, over-strict for fields whose only cost of being wrong is "annoying and visible" per the
SKILL.md's own framing (as opposed to the judgment fields, which fail silently and dangerously).

## Write mechanism

**Decision**: Read `services.yaml` with PyYAML preserving structure as much as round-tripping
allows, append the new entry as a new list item under `services:`, write back. No templating
engine, no manual string concatenation into the YAML file.

**Rationale**: Keeps a single, consistent parse/write path shared conceptually with
`check_kg.py`'s own YAML handling — avoids a second, subtly different YAML dialect entering the
KG's one file. D12 requires this to be indistinguishable in the file from a manual edit.

**Alternatives considered**: String-append a hand-formatted YAML block — rejected, brittle
against future schema/comment changes to the file and more likely to produce YAML that parses
but doesn't match the file's existing style (CLAUDE.md Style section: prefer YAML specifically
because of the comments it carries — a naive dump can flatten or reposition those).

## Staleness detection and AI-suggested judgment answers (update path)

**Decision**: On a duplicate match (US2), compare the requester's supplied reference against the
existing entry's last-checked date (per spec Assumption: `provenance.verified` date if present,
otherwise write time, otherwise treat as always-stale). Only a demonstrably newer reference
triggers the update path. When it does, the system reads the reference and drafts values for
every field — including `network_placement`/`reachability`/`roles` — each labeled with what in
the reference supports it, but every judgment-field draft still requires an explicit
per-field human confirmation before anything is written. An accepted-as-shown draft counts as a
confirmation; an unreviewed draft never does, regardless of how long the human waits or whether
they raised an objection.

**Rationale**: This is a direct amendment from an initial version of the idea that would have let
the AI "already answer the questions" from the reference and write without asking — rejected
during design discussion as a re-introduction of exactly the failure D6/Principle III exist to
prevent: an LLM inferring `reachability` from reading text is still an LLM inferring
`reachability`, whether the text is its own training data or a doc it just fetched. The corrected
version keeps the speed win (usually just confirming "yes, correct" instead of typing an answer
from scratch) without weakening the gate itself — this mirrors how FR-003's safe-field proposals
already work, just extended to fields that previously had no proposal at all.

**Alternatives considered**: Skip confirmation when the reference "clearly" states the answer
(e.g. doc literally says "publicly accessible") — rejected, "clearly" is exactly the judgment
call this tool must not make; a human still confirms even an apparently obvious reading, since
the cost of building an exception path for "obvious" cases is a second, weaker gate that
inevitably gets relied on for ambiguous cases too.

## Test strategy for "no write on abandon"

**Decision**: The regression suite drives `add_service.py`'s flow via its public functions
(propose → present-questions → confirm-or-abandon → write) rather than by simulating terminal
input, asserting `services.yaml`'s byte content is unchanged when confirm is never called.

**Rationale**: FR-010 is a negative assertion (nothing happens) — the cheapest reliable way to
prove it is a byte-for-byte file comparison before/after an abandoned flow, not just "no
exception was raised."

**Alternatives considered**: Only testing the happy path (write occurs on confirm) — rejected,
the do-nothing case is exactly the failure mode (silent partial write) the constitution's
Principle IV write-path discipline exists to prevent, and it's cheap to test directly.
