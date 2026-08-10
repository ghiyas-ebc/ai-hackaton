# Feature Specification: Equivalence Detection in Add-Service Skill

**Feature Branch**: `003-equivalence-detection`

**Created**: 2026-08-10

**Status**: Draft

**Input**: User description: "build -add equivalence detection"

## User Scenarios & Testing

### User Story 1 - Fresh-Add Equivalence Proposal (Priority: P1)

When adding a new service (e.g., Gemini Enterprise to GCP), the engineer gets asked: "Does this service have an equivalent in [other provider] (Azure, AWS, etc.)?" Agent proposes the most likely equivalent based on the service's category, description, and provider docs. Engineer confirms, corrects, or declines the proposal. If confirmed, system outputs a recommendation to manually add the equivalence to `equivalences.yaml`.

**Why this priority**: Captures cross-provider knowledge at the moment of entry, before context is lost. Prevents manual post-add equivalence mapping work.

**Independent Test**: Fresh-add flow alone completes successfully; equivalence proposal appears and can be accepted/rejected independently of judgment field flow.

**Acceptance Scenarios**:

1. **Given** Cloud Run being added to GCP, **When** judgment fields confirmed, **Then** user prompted for equivalence + agent proposes "Container Instances" (Azure), user confirms, system outputs recommendation
2. **Given** new service with no obvious cross-provider equivalent, **When** equivalence prompt shown, **Then** user can explicitly decline (no recommendation output)
3. **Given** user corrects agent's proposed equivalent name, **When** confirmation given, **Then** recommendation reflects user's corrected name, not proposal

---

### User Story 2 - Update Equivalence Detection (Priority: P2)

When updating a service with a newer reference (e.g., Vertex AI with 2026-08-09 docs), system checks reference for competitor product mentions. If found (e.g., "compare Agent Platform"), agent proposes equivalence + fetches/validates the Azure service. Engineer confirms/corrects/declines. Outputs recommendation if accepted.

**Why this priority**: Staleness updates often include new competitive positioning language. Capturing cross-provider info at update time keeps `equivalences.yaml` current without manual review of every reference change.

**Independent Test**: Update flow completes with newer reference; equivalence detection fires independently of judgment field updates; proposal can be accepted/rejected.

**Acceptance Scenarios**:

1. **Given** Vertex AI updated with newer docs mentioning Agent Platform, **When** reference fetched, **Then** agent proposes "Agent Platform" (Azure), user confirms, recommendation outputs
2. **Given** reference has no competitor mentions, **When** equivalence check completes, **Then** no proposal shown, user skips to field confirmation
3. **Given** user rejects proposed equivalence, **When** update write completes, **Then** no equivalence recommendation generated (can be added manually later)

---

### Edge Cases

- Service with equivalents in multiple providers (e.g., Vertex AI → both Azure ML + AWS SageMaker): Agent proposes one most likely; user can note manual additions
- Proposed equivalent doesn't exist yet in target provider's KG: Recommendation includes note that target service must be added first via fresh-add
- Reference URL is malformed or unreachable: System skips equivalence detection, allows user to continue with judgment fields
- Equivalence already exists in `equivalences.yaml` for the service: System detects & suggests "already mapped" instead of re-proposing

## Requirements

### Functional Requirements

- **FR-E01**: During fresh-add confirmation (after judgment fields answered), system MUST prompt: "Does [service name] have an equivalent in [other provider]?"
- **FR-E02**: Agent MUST propose equivalent service name based on service category, description, references_url
- **FR-E03**: User MUST be able to confirm, correct, or decline the equivalence proposal
- **FR-E04**: If equivalence accepted/corrected, system MUST output a recommendation block showing suggested `equivalences.yaml` entry (gcp/azure, service names, optional notes)
- **FR-E05**: During update flow with newer reference, if reference text mentions competitor products, system MUST offer equivalence detection with agent proposal
- **FR-E06**: Equivalence detection MUST NOT write to `equivalences.yaml` automatically; recommendation is for manual human review
- **FR-E07**: If proposed equivalent service doesn't exist in target KG, recommendation MUST include note: "Target service must be added first via fresh-add"
- **FR-E08**: System MUST handle cases where equivalence already exists in `equivalences.yaml`; prompt shows "already mapped" instead of proposal

### Key Entities

- **Equivalence Entry**: `{gcp: service_name, azure: service_name, notes: optional_rationale}`
- **Equivalence Proposal**: Agent-generated suggestion with confidence indicator (certain/likely/possible)
- **Recommendation Block**: Formatted text output for manual `equivalences.yaml` edit (copy-paste ready)

## Success Criteria

### Measurable Outcomes

- **SC-E01**: Equivalence proposal appears within 2 seconds of judgment field completion (no slow agent calls)
- **SC-E02**: 90% of user confirmations result in correct `equivalences.yaml` entries (measured via manual review of outputs)
- **SC-E03**: Zero automatic writes to `equivalences.yaml` (human-gated only; verified via code review + commit logs)
- **SC-E04**: Recommendation output format matches existing `equivalences.yaml` structure (parseable, copy-paste ready)
- **SC-E05**: Feature reduces time-to-equivalence-documentation by 80% vs. manual discovery (user documents equivalence during add, not post-facto)

## Assumptions

- Agent has access to provider docs (same fetch mechanism as safe-field proposal in main -add skill)
- Equivalence file (`equivalences.yaml`) is in sibling `create-architect` skill, same location as `services.yaml`
- One-to-one equivalence is the common case; many-to-many (one service multiple equivalents) is noted but not auto-handled
- User performing add/update understands what equivalence means (architectural sematics, not just naming similarity)
- Equivalence detection only applies to GCP ↔ Azure (primary platform pair); AWS/others deferred
- Proposal uses agent inference, not a hard lookup table (more flexible, but requires human confirmation)
