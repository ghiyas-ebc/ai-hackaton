# Feature Specification: Add-Service Skill

**Feature Branch**: `002-add-skill`

**Created**: 2026-08-10

**Status**: Draft

**Input**: User description: "build -add skills"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Guided single-service add (Priority: P1)

A presales engineer needs the KG to know about a cloud service it doesn't yet
cover (surfaced by a Gap Record, or just noticed missing). They name the
service; the system fetches and proposes the fields it can verify
(category, description, reference link, icon), then asks the engineer to
answer the fields no fetch can supply (network placement, reachability,
roles) before anything is written.

**Why this priority**: This is the entire feature — without it there is no
`-add` skill, only the existing stub.

**Independent Test**: Ask for one real, currently-missing service to be
added; confirm the judgment questions are asked, confirm the entry lands in
`services.yaml` only after they're answered, confirm `status: unverified` and
`provenance.sources` are present on the new entry.

**Acceptance Scenarios**:

1. **Given** a service name/provider not present in the KG, **When** the
   engineer requests it be added, **Then** the system proposes category,
   description, reference link, and icon, and separately asks for network
   placement, reachability, and roles before writing anything.
2. **Given** the engineer has answered all judgment questions, **When** they
   confirm, **Then** exactly one new entry is appended to `services.yaml`
   with `provenance.generated: cloud-architecture-validator-add` and
   `provenance.status: unverified`.
3. **Given** the engineer has not yet answered every judgment question,
   **When** they try to confirm early, **Then** the system does not write
   anything and re-asks the unanswered question(s).

---

### User Story 2 - Duplicate prevention (Priority: P2)

Before proposing a new entry, the system checks whether a service with the
same name/provider already exists, so the same service doesn't get added
twice under slightly different ids from repeated requests.

**Why this priority**: Cheap to add, and the failure mode it prevents
(duplicate nodes with diverging `reachability` values) is exactly the kind of
silent-wrong-verdict risk the parent skill's decision log already worries
about elsewhere (D6).

**Independent Test**: Request the same service twice; second request is
flagged as already-present instead of producing a second entry.

**Acceptance Scenarios**:

1. **Given** a service already exists in the KG, **When** it's requested
   again, **Then** the system reports the existing entry instead of
   proposing a new one.

---

### User Story 3 - Correct before write (Priority: P3)

The engineer can reject or edit any agent-proposed field (wrong category,
dead reference link, wrong icon) before confirming, since the agent's fetch
can be wrong and nothing should be written on a field the engineer knows is
incorrect.

**Why this priority**: Lower priority than P1/P2 because P1 already requires
an explicit confirm step; this story is about correcting the proposal within
that step rather than about a new mechanism.

**Independent Test**: Deliberately have the agent propose an incorrect
field, edit it during confirmation, verify the corrected value (not the
original proposal) is what gets written.

**Acceptance Scenarios**:

1. **Given** a proposed field the engineer knows is wrong, **When** they
   supply a correction during confirmation, **Then** the written entry
   reflects the correction, not the original proposal.

### User Story 4 - Staleness-detected update with AI-suggested answers (Priority: P2)

When the requested service already exists, the system doesn't just report it and stop — it checks
whether the reference the requester supplied is newer than what the existing entry was last
checked against. If so, it reads the reference and proposes updated values for every field,
*including* draft answers for `network_placement`/`reachability`/`roles`, each labeled with what
in the reference supports it. The human still must explicitly confirm every judgment field before
anything is written — the AI's read of the doc makes confirming faster (often just "yes,
correct"), it never replaces the confirmation itself.

**Why this priority**: Directly requested follow-up to US1/US2 once it became clear "duplicate
found" was a dead end for the common real case (Google ships an update to a service already in
the KG) rather than an update opportunity. Ranked P2, same tier as duplicate prevention, since
it's the other half of the same detection.

**Independent Test**: Point the tool at an existing entry with a reference URL demonstrably newer
than the entry's last-checked date; confirm the system proposes a diff instead of just reporting
"already exists," confirm every judgment field still requires an explicit human confirm (not just
an unattended accept), confirm declining leaves the existing entry untouched.

**Acceptance Scenarios**:

1. **Given** an existing entry whose reference is older than the one the requester now supplies,
   **When** the request is made, **Then** the system proposes updated field values (including
   draft judgment-field answers) instead of only reporting "already exists."
2. **Given** the system has proposed draft judgment-field answers from the reference, **When**
   the human has not yet explicitly confirmed each one, **Then** nothing is written — a
   plausible-looking draft is not treated as a confirmation.
3. **Given** the human confirms some fields as-shown and edits others, **When** they confirm the
   whole batch, **Then** the entry is updated to the confirmed values, not the raw AI draft, and
   `provenance` reflects a fresh `unverified` status pending re-review.
4. **Given** the human declines the proposed update entirely, **When** they exit the flow,
   **Then** the existing entry is left byte-for-byte unchanged.

### Edge Cases

- What happens when the reference URL doesn't resolve? Proposal proceeds
  without a verified link; the engineer is told the fetch failed and asked
  to supply or confirm the field manually rather than the system guessing.
- What happens when the engineer declines to answer a judgment question at
  all (walks away mid-flow)? No partial entry is written — the field set is
  all-or-nothing.
- What happens when no matching icon can be resolved? Entry is still
  written without an icon reference rather than blocking the whole add on a
  cosmetic field; this is reported, not silently dropped.
- What happens when the same service is proposed with conflicting judgment
  answers on a retry (e.g. `reachability` answered differently the second
  time)? The existing entry is not silently overwritten — the conflict is
  surfaced for a human to resolve which answer is correct.
- What happens when the requester's reference URL is the *same or older*
  than what the existing entry was last checked against? System reports
  "already exists, no newer reference supplied" (US2's original behavior) —
  it does not propose an update off a reference that proves nothing new.
- What happens when the AI misreads the reference and proposes a wrong
  judgment-field draft? No different from any other proposal error — the
  human is expected to catch it before confirming (US3's correction
  mechanism applies equally to update drafts), and an accepted-then-wrong
  answer is a human error, not a system one, exactly as it would be for a
  fresh add.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a request naming one target service
  (name + provider) to add to the KG.
- **FR-002**: System MUST check for an existing entry with the same
  name/provider before proposing anything new. If found and the requester
  supplied no newer reference than the entry's last-checked date, System
  MUST report the existing entry and propose nothing further (no duplicate
  created). If found and the requester's reference is newer, System MUST
  follow the update path (FR-011–FR-013) instead of silently doing nothing.
- **FR-003**: System MUST fetch/propose `category`, `description`,
  `references_url`, and `icon` for the named service without requiring
  human input for this subset.
- **FR-004**: System MUST always present `network_placement`,
  `reachability`, and `roles` as explicit questions to a human — never
  inferred, defaulted, or guessed from the fetched data.
- **FR-005**: System MUST NOT write anything to `services.yaml` until every
  judgment question (FR-004) has been explicitly answered by a human.
- **FR-006**: System MUST allow the human to reject or edit any
  agent-proposed field (FR-003) before the write happens.
- **FR-007**: Every entry this system writes MUST carry a `provenance`
  block with `generated: cloud-architecture-validator-add`,
  `status: unverified`, and `sources` listing what was checked to produce
  the proposed fields.
- **FR-008**: System MUST NOT ever write `provenance.status` as `verified`
  or `manual` — those states require a separate human review step this
  feature does not perform.
- **FR-009**: System MUST write the confirmed entry directly into
  `services.yaml` in place, the same file and file location a manual edit
  would use — no staging file, no second data store.
- **FR-010**: System MUST leave `services.yaml` unmodified if the human
  abandons the flow before confirming (no partial or draft entries).
- **FR-011**: System MUST compare the requester-supplied reference against
  the existing entry's last-checked date before deciding whether an update
  is proposed (FR-002) — a same-or-older reference MUST NOT trigger an
  update proposal.
- **FR-012**: When an update is proposed, System MUST include draft answers
  for `network_placement`, `reachability`, and `roles` derived from the
  supplied reference, each labeled with what in the reference supports it —
  but these drafts MUST still require an explicit human confirmation
  per-field, identically to FR-004/FR-005; an unconfirmed draft MUST NOT be
  written under any circumstance, including "the human didn't object."
- **FR-013**: When an update is written, System MUST reset the entry's
  `provenance.status` to `unverified` and refresh `provenance.sources`
  (FR-007's rule applies to updates the same as new entries) — an update
  MUST NOT preserve a stale `verified` status past the point the underlying
  facts changed.

### Key Entities

- **Service Proposal**: The draft record built before confirmation —
  proposed verifiable fields, the outstanding judgment questions, and which
  sources were checked. Exists only for the duration of one add session;
  never persisted on its own.
- **Judgment Answers**: The human-supplied values for `network_placement`,
  `reachability`, `roles` — always sourced from a person, never from a
  fetch.
- **Service Entry**: The final record appended to (or updated in)
  `services.yaml`, carrying the merged verifiable fields, judgment answers,
  and its `provenance` block.
- **Update Proposal**: Like a Service Proposal, but built against an
  existing entry rather than from scratch — carries the existing entry's
  current values, the reference-derived draft values (including draft
  judgment-field answers), and which fields actually differ. Exists only
  for the duration of one update session.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An engineer can take one missing service from "named" to
  "written into the KG" in a single guided session, without editing YAML by
  hand.
- **SC-002**: 100% of written entries have `network_placement`,
  `reachability`, and `roles` traceable to an explicit human answer, never
  to an inferred default — auditable from the entry's `provenance.sources`
  plus session record.
- **SC-003**: Repeating the same add request never results in more than one
  entry for that service in the KG.
- **SC-004**: The KG's structural integrity check continues to pass after
  every add (no broken references, no schema drift) — the only expected
  change to check output is the new entry counting toward coverage, and its
  `unverified` status blocking the checkpoint gate exactly as designed.
- **SC-005**: 100% of updates driven by AI-suggested judgment-field drafts
  are traceable to an explicit human confirmation per field — an accepted
  draft is auditable as "human confirmed," never indistinguishable from an
  unreviewed AI guess.
- **SC-006**: A reference no newer than the existing entry's last-checked
  date never produces a written change — updates only happen when the
  requester brings something newer.

## Assumptions

- Scope is one service per session — bulk/catalog population remains
  `-init`'s job and is explicitly out of scope here.
- Icon resolution reuses the existing `icons.yaml`/`kg.py` `icon_for()`
  mechanism already used elsewhere in the KG; this feature does not invent a
  new icon pipeline.
- Fetch/verification of the safe fields (FR-003) happens at authoring time,
  consistent with the parent skill's "no runtime dependency beyond PyYAML"
  rule — this tool is not part of the live validation path.
- Flipping `provenance.status` from `unverified` to `verified` is a
  separate, later human review step and out of scope for this feature —
  this feature's job ends at producing a correctly-flagged `unverified`
  entry.
- The human-confirmation exchange (judgment questions, proposal review) is
  conversational within the agent session; no separate ticketing/queue UI is
  assumed to exist yet.
- "Last-checked date" for staleness comparison (FR-011) is the entry's
  `provenance.verified` date when `status: verified`, or its write time when
  `status: unverified`/`manual` lacks one — an entry with no comparable date
  at all is treated as always-stale (any supplied reference triggers the
  update path) rather than blocking on a missing field.
- AI-suggested judgment-field drafts (FR-012) are a convenience layer over
  the same human-confirmation gate US1 already requires — this story does
  not weaken Principle III/FR-004, it only pre-fills what the human is
  confirming.
