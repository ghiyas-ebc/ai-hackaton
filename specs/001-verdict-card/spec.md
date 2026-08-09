# Feature Specification: Verdict Card

**Feature Branch**: `001-verdict-card`

**Created**: 2026-08-09

**Status**: Draft

**Input**: User description: "Verdict Card: structured difficulty score, three-tier evidence, mismatch analysis, engineer checklist, and Gap Report logging on top of validate_architecture output"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Instant structured verdict during a live client conversation (Priority: P1)

A presales rep describes a proposed architecture to the assistant mid-meeting. Instead of a prose
explanation they must read line by line, they receive a single structured card: an overall difficulty
label, and every underlying finding tagged with how much confidence backs it — proven from a past
project, plausible but untested, or requiring engineering review before anyone commits to it.

**Why this priority**: This is the core promise of the tool — replacing "let me check with engineering
and get back to you" with an answer the rep can read and act on inside the meeting. Without this, the
rest of the feature has nothing to attach to.

**Independent Test**: Feed the assistant an architecture description covering a mix of well-established
and untested service combinations; confirm the response is a single card (not free-form prose) with one
overall difficulty label and every contributing finding individually labeled with its evidence tier.

**Acceptance Scenarios**:

1. **Given** an architecture description where every connection is backed by prior project history,
   **When** the rep asks for a validation, **Then** the card shows a low-difficulty verdict and every
   finding is labeled with the "proven" evidence tier, each citing what backs it.
2. **Given** an architecture description containing at least one connection that violates a known rule,
   **When** the rep asks for a validation, **Then** the card's overall difficulty reflects the worst
   individual finding, and that finding is visibly distinguished from the lower-severity ones.
3. **Given** an architecture description containing a connection with no matching rule or historical
   precedent, **When** the rep asks for a validation, **Then** the corresponding finding is labeled
   "requires deep review" rather than given a confident pass/fail, and the overall verdict communicates
   that not everything was fully checked.

---

### User Story 2 - Mismatch correction when the client's ask doesn't match the actual need (Priority: P2)

A client describes what they think they need in their own words (e.g., a specific technology or
pattern), but the requirement they're actually describing is better served by something else. The rep
sees this called out explicitly on the card rather than the system silently substituting a different
answer or missing the discrepancy entirely.

**Why this priority**: Sharpens the sales conversation itself — the deck's own framing is that these
tools should "correct client misdiagnoses on the fly." It depends on User Story 1's card existing, so it
sits at P2.

**Independent Test**: Submit a request where the client's stated technology choice doesn't match the
underlying requirement it's meant to solve; confirm the card surfaces the mismatch as a distinct,
labeled item rather than answering only the literal request.

**Acceptance Scenarios**:

1. **Given** a client request naming a specific technology that doesn't fit the stated requirement,
   **When** the card is generated, **Then** a mismatch entry names both what was asked for and what the
   requirement actually needs.
2. **Given** a client request where the named technology and the actual requirement agree, **When** the
   card is generated, **Then** no mismatch entry appears for that item.

---

### User Story 3 - Ready-made checklist for the engineer who picks this up next (Priority: P3)

When a finding is not fully "proven," the engineer who eventually reviews the deal receives a
pre-packaged list of exactly what needs to be checked — not a transcript they have to re-read and
distill themselves.

**Why this priority**: Saves the handoff step the deck identifies as a momentum killer (today: pause
the conversation, escalate, wait days for an answer). It builds directly on the tiered findings from
User Story 1, so it follows behind it.

**Independent Test**: Generate a card for an architecture with at least one non-proven finding; confirm
a checklist item exists for each such finding, stated as a concrete thing to verify (not a restatement
of the finding itself).

**Acceptance Scenarios**:

1. **Given** a card containing findings in the "theoretically possible" or "requires deep review" tiers,
   **When** the checklist is generated, **Then** each such finding produces one corresponding checklist
   item describing what an engineer needs to confirm.
2. **Given** a card where every finding is "proven," **When** the checklist is generated, **Then** the
   checklist is empty and says so explicitly, rather than listing already-settled items.

---

### User Story 4 - Unanswered requests become visible market intelligence (Priority: P3)

When a client's request touches something the system has no rule or historical precedent for, that gap
doesn't just get reported to the rep and forgotten — it becomes a record the product/knowledge-owning
team can review later to see what capability gaps keep coming up across deals.

**Why this priority**: This is the feature that turns individual "I don't know" answers into the
"strategic asset" the source material describes. Equal priority to User Story 3 — both are downstream
consumers of the same tiered findings, serving different audiences (engineer vs. product owner).

**Independent Test**: Submit a request with no matching rule or historical precedent; confirm a record
of that specific gap is retrievable afterward, independent of the conversation that produced it.

**Acceptance Scenarios**:

1. **Given** a request the system cannot classify against any rule or historical record, **When** the
   verdict is produced, **Then** a gap record is created describing what was asked and why it isn't
   covered, without requiring the rep to take any extra action.
2. **Given** the same uncovered gap occurs across multiple separate conversations, **When** the gap
   records are reviewed later, **Then** each occurrence is individually recorded rather than
   deduplicated away, so recurrence frequency is visible.

### Edge Cases

- What happens when the rep can't supply a detail the verdict depends on (e.g., production vs. proof-of-
  concept, expected data residency)? The system MUST proceed using an explicitly stated assumption
  rather than stopping to demand the missing detail, and MUST label that assumption on the card.
- How does the system handle a request where every single finding is uncovered (nothing matches any
  rule or history)? The card MUST still render, with an overall verdict that plainly says feasibility
  could not be established, rather than defaulting to a specific difficulty label.
- How does the system handle conflicting evidence — e.g., a past project succeeded with a pairing that a
  rule now flags as invalid? The rule-based finding takes precedence and is reported at its stated
  severity; the prior project reference is preserved in the finding's supporting detail so a human can
  see both sides, but the system does not average or soften the two into a compromise verdict.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST present validation results as a single structured card containing one overall
  difficulty verdict, rather than free-form narrative text.
- **FR-002**: System MUST classify every individual finding contributing to a verdict into exactly one
  of three evidence tiers: proven (backed by a specific prior instance), theoretically possible (no
  historical precedent, but not ruled out by any known constraint), or requires deep review (conflicts
  with a known constraint, or could not be classified at all).
- **FR-003**: System MUST derive the overall difficulty verdict from the individual findings using a
  fixed, repeatable method, such that the same set of findings always produces the same overall verdict.
- **FR-004**: System MUST NOT let the overall difficulty verdict obscure or downgrade the severity of
  any individual finding — a viewer must be able to see which specific finding(s) drove the verdict.
- **FR-005**: System MUST detect when a client's explicitly named technology choice does not match what
  their underlying requirement actually needs, and surface this as a distinct, separately labeled item
  naming both the stated choice and the actual need.
- **FR-006**: System MUST generate a checklist of concrete follow-up items for engineering review,
  containing exactly one item per finding not classified as "proven."
- **FR-007**: System MUST state explicitly when no checklist items are needed, rather than omitting the
  checklist section silently.
- **FR-008**: System MUST record every request or finding that cannot be classified against any known
  rule or historical precedent as a standalone, retrievable gap record, without requiring a person to
  manually decide to save it.
- **FR-009**: Gap records MUST be recorded individually per occurrence, not merged or deduplicated
  against prior occurrences of the same gap.
- **FR-010**: System MUST proceed to produce a verdict when requested information is missing, by
  substituting an explicitly stated assumption, and MUST display that assumption as part of the card.
- **FR-011**: System MUST NOT require a human confirmation step before recording a gap record (this
  differs from other organizational-knowledge writes, which do require confirmation).
- **FR-012**: The full card (verdict, tiered findings, mismatches, checklist) MUST be producible without
  any step in its generation being decided by unverified model judgment — every displayed label MUST
  trace back to a rule evaluation, a knowledge lookup, or a historical record.

### Key Entities

- **Verdict Card**: The structured output shown to the sales rep for one architecture/request. Holds one
  overall difficulty verdict, a list of tiered findings, zero or more mismatch entries, and the
  generated checklist (which may be empty).
- **Finding**: One evaluated aspect of the request (e.g., one connection or one component's fitness for
  a requirement). Carries an evidence tier and the supporting detail behind that tier (rule id, cited
  project, or reason it's unclassifiable).
- **Mismatch Entry**: A record that the client's stated technology choice and the requirement's actual
  need diverge. Carries both the stated choice and the actual need.
- **Engineer Checklist Item**: One concrete follow-up task generated from a non-proven finding.
- **Gap Record**: A standalone entry describing one occurrence of a request that could not be classified
  against any rule or historical precedent, retrievable independently of the conversation that produced
  it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A sales rep can read and understand the full verdict — overall difficulty plus which
  findings drove it — in under 5 seconds of glancing at the card.
- **SC-002**: 100% of findings shown on any card carry exactly one of the three evidence tiers; none are
  shown without a tier label.
- **SC-003**: Every request containing at least one unclassifiable element produces a corresponding gap
  record, verifiable by comparing verdict outputs against the gap record log over a sample of requests.
- **SC-004**: For any card containing at least one non-proven finding, the generated checklist has a
  1:1 correspondence with those findings, with zero items referencing already-proven findings.
- **SC-005**: Given the same architecture description and the same underlying rules/history, the system
  produces the same overall difficulty verdict on repeated runs.
- **SC-006**: A rep can obtain a verdict even when they cannot supply every requested detail — no
  scenario in normal use requires the rep to abandon the request due to missing information.

## Assumptions

- This feature builds directly on the existing rule-engine and knowledge-graph validation output; it
  does not introduce a new data source or a separate historical-project-record system.
- "Historical precedent" for the proven/theoretical/deep-review split maps to the existing distinction
  between knowledge-graph entries with confirmed real-world provenance and those without — not a
  separate log of past sales deals (no such log exists yet).
- The audience for the Gap Record is an internal product/knowledge-owning function, not the client or
  the sales rep directly; how that audience is notified (dashboard, digest, direct query) is out of
  scope for this spec and left to planning.
- Mismatch detection operates within a single request (what the client asked for vs. what their stated
  need actually requires) — it is a distinct concern from translating an architecture to a different
  provider, which is an existing, separate capability.
- "Requested information is missing" refers to details the rep would normally supply about context
  (e.g., environment tier, compliance requirements) — not to the identity of the services/components
  themselves, which must still be resolvable for a card to be produced at all.
