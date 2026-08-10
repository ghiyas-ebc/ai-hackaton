# Feature Specification: Agent Wiring Fixes

**Feature Branch**: `004-agent-wiring-fixes`

**Created**: 2026-08-10

**Status**: Draft

**Input**: User description: "Agent Wiring Fixes: close gaps from project_evaluation.md prioritized list. Scope: (1) add_service_to_kg tool in cloud-arch-validator-agent/app/tools.py currently returns hardcoded stub error even though cloud-architecture-validator-add/scripts/add_service.py is a complete, tested implementation (spec 002 done) — need decision + fix for Gap 7 (Option A: agent tells user to run CLI externally, vs Option B: extract non-interactive function from add_service.py exposed as agent tool, preserving human-gate discipline per CLAUDE.md D6/D21) and update the stub message/behavior accordingly (P1). (2) Add propose_equivalence tool wrapping cloud-architecture-validator-add/scripts/equivalence.py's propose_equivalence() so cross-cloud equivalence suggestions (spec 003, already built/tested) are actually reachable from the agent (P3). Do not include eval-suite conversion (Gap 3/P2) or dataset/metadata cosmetic gaps (Gap 5/6) — those are separate follow-on work."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Presales engineer adds a missing service mid-conversation (Priority: P1)

A presales engineer is validating an architecture with the agent and hits `UNKNOWN_SERVICE` for a
service that isn't in the knowledge graph yet. Today the agent's add-service tool always replies
that it isn't implemented, even though the underlying add-service capability has been complete and
tested since spec 002. The engineer needs the agent to actually collect the required judgment
fields (network placement, reachability, roles) conversationally and write a properly-provenanced
entry to the knowledge graph — without breaking the human-confirmation gate that exists because a
wrong `reachability` value produces confident wrong verdicts silently.

**Why this priority**: This is the single most visible gap: a tool that lies about its own
implementation status, blocking the most common "the KG doesn't cover a service" recovery path
end-to-end inside the conversation the engineer is already having.

**Independent Test**: Ask the agent to validate an architecture containing a service not present in
`services.yaml`, then ask it to add that service by name/provider/URL. Can be fully tested by
completing one add-service round trip end-to-end and confirming the new entry appears in
`services.yaml` with `status: unverified` and full `provenance`, without the engineer leaving the
conversation to run a separate CLI.

**Acceptance Scenarios**:

1. **Given** an architecture references a service absent from the knowledge graph, **When** the
   engineer asks the agent to add it, **Then** the agent asks the engineer for the judgment fields
   it cannot verify itself (network placement, reachability, roles) before writing anything.
2. **Given** the engineer has supplied all required judgment fields, **When** the agent proceeds,
   **Then** a new entry is written to the knowledge graph with `status: unverified` and a
   `provenance` block, and the agent reports what was written for the engineer to confirm.
3. **Given** the engineer declines to provide a required judgment field, **When** the agent would
   otherwise write the entry, **Then** the agent does not write anything and explains what is
   missing.
4. **Given** a service name that already exists in the knowledge graph for that provider, **When**
   the engineer asks to add it again, **Then** the agent reports the existing entry instead of
   creating a duplicate.

---

### User Story 2 - Sales engineer asks for a cross-cloud equivalent (Priority: P3)

A sales engineer is discussing a GCP architecture with an Azure-only client and asks the agent
"what's the Azure equivalent of Cloud Run?" Today the underlying equivalence-detection logic exists
and is tested (spec 003) but no agent tool exposes it, so the agent has no sanctioned way to answer
without guessing — which the skill's design explicitly forbids (no LLM in the decision path).

**Why this priority**: Lower priority than Story 1 because it is a recommendation, not a write path,
and the conversation can proceed without it — but it is a completed, tested capability currently
unreachable from the one interface (the agent) engineers actually use.

**Independent Test**: Ask the agent for the cross-cloud equivalent of a known service and confirm it
returns a derived recommendation (or an explicit "no known equivalent yet" answer) rather than a
guessed answer.

**Acceptance Scenarios**:

1. **Given** a service that has a recorded equivalence, **When** the engineer asks for its
   cross-cloud equivalent, **Then** the agent returns the recommended equivalent and its source
   category/reference basis, not a freeform guess.
2. **Given** a service with no recorded equivalence yet, **When** the engineer asks for its
   cross-cloud equivalent, **Then** the agent reports that no equivalence is known rather than
   inventing one.

---

### Edge Cases

- Engineer asks to add a service that has a connector-style role excluded from equivalence
  generation by design (`regenerate_roles`) — the equivalence tool must not report this as
  "unportable" or invent a suggestion for it.
- Engineer supplies a judgment field value that is inconsistent with an existing KG entry for the
  same service under a different provider — the agent should surface the discrepancy rather than
  silently overwrite.
- Two engineers in concurrent conversations both propose adding the same new service before either
  is confirmed — the second attempt must detect the first's (already-written) entry rather than
  producing a duplicate or a corrupt file.
- Engineer abandons the add-service conversation partway through (never supplies required judgment
  fields) — no partial or malformed entry is left behind in the knowledge graph.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an add-service capability reachable from within an agent
  conversation that does not require the engineer to leave the conversation to run a separate
  command-line tool.
- **FR-002**: The system MUST collect, from the engineer, every field that cannot be verified
  automatically (at minimum: network placement, reachability, roles) before writing any new
  knowledge-graph entry.
- **FR-003**: The system MUST NOT write a knowledge-graph entry until all required judgment fields
  have been explicitly supplied by the engineer for that entry.
- **FR-004**: Every entry written via this capability MUST record `status: unverified` and a
  provenance record (source, generation context) distinguishing it from hand-authored entries, per
  the existing knowledge-graph provenance model.
- **FR-005**: The system MUST detect and report when a requested service already exists for the
  given provider instead of creating a duplicate entry.
- **FR-006**: The system MUST provide a cross-cloud equivalence lookup reachable from within an
  agent conversation, returning either a recommended equivalent with its basis or an explicit
  no-equivalence-known result.
- **FR-007**: The equivalence lookup MUST NOT produce a recommendation for services whose role is
  excluded from equivalence generation by design; it MUST report these as not applicable rather than
  "no equivalence found" or a guess.
- **FR-008**: Neither capability MUST allow the underlying language model to determine validity,
  equivalence, or correctness on its own — both remain derived from the existing rule engine and
  knowledge graph, matching the no-guessing principle already governing the rest of the system.
- **FR-009**: If the engineer stops responding or declines to provide required fields, the system
  MUST leave the knowledge graph unchanged (no partial writes).
- **FR-010**: The system MUST report to the engineer, after any write, exactly what was written so
  they can visually confirm it before relying on it in a client-facing conversation.

### Key Entities

- **Service entry**: A single knowledge-graph record for one service under one provider — carries
  identity fields (name, provider, category, references URL), judgment fields supplied by a human
  (network placement, reachability, roles), and a provenance/status block recording how and when it
  was added.
- **Equivalence recommendation**: A proposed cross-cloud counterpart for a given service, carrying
  the candidate name, the category basis for the match, and enough reference information for a human
  to sanity-check it before repeating it to a client.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An engineer can go from encountering an `UNKNOWN_SERVICE` verdict to a confirmed new
  knowledge-graph entry within the same conversation, with no external tool invocation.
- **SC-002**: 100% of knowledge-graph entries created through this capability carry `status:
  unverified` and a complete provenance block — zero silently-trusted writes.
- **SC-003**: 0% of add-service attempts missing a required judgment field result in a written
  entry.
- **SC-004**: An engineer asking for a cross-cloud equivalent receives a derived answer (recommendation
  or explicit "unknown") in a single request, with no case answered by an unverifiable freeform guess.

## Assumptions

- The existing human-confirmation gate and provenance model (`status: manual` / `unverified` /
  `verified`, per CLAUDE.md D21) is the correct model to extend to conversational add-service — this
  spec does not introduce a new review mechanism.
- Judgment-field collection happens through ordinary conversational turns (the agent asks, the
  engineer answers) rather than through the original CLI's interactive stdin prompts, since those
  cannot be driven mid-conversation.
- Cross-cloud equivalence data already recorded (`equivalences.yaml`) is the sole source of truth for
  Story 2; this feature does not add new equivalence-detection logic beyond exposing what spec 003
  already computes.
- Eval-suite conversion, placeholder dataset replacement, and cosmetic metadata fixes (evaluation
  report gaps 3, 5, 6) are explicitly out of scope for this feature.
