# Implementation Plan: Equivalence Detection in Add-Service Skill

**Feature**: Equivalence Detection in Add-Service Skill

**Created**: 2026-08-10

**Status**: Planning

## Technical Context

### Tech Stack

- **Language**: Python 3, PyYAML only (same invariant as -add skill: no new dependencies)
- **Integration point**: cloud-architecture-validator-add skill (existing scripts/)
- **Write target**: Sibling skill's references/kg/equivalences.yaml (read-only, recommendation output only)
- **Agent interaction**: Claude model (same as main -add skill fetch/propose pipeline)

### Architecture Overview

**Fresh-Add Flow** (US1):
Judgment fields confirmed → Prompt equivalence → Agent proposes + fetches docs → User confirms/corrects/declines → Output recommendation

**Update Flow** (US2):
Newer reference found → Search docs for competitor mentions → Agent proposes equivalence → User confirms/corrects/declines → Output recommendation

### File Structure

Existing -add skill unchanged; all new code in:
- `cloud-architecture-validator-add/scripts/equivalence.py` — propose + validate
- `cloud-architecture-validator-add/tests/test_equivalence.py` — tests
- `cloud-architecture-validator-add/scripts/add_service.py` — wire prompts (2 calls)

Sibling read:
- `cloud-architecture-validator-create-architect/references/kg/equivalences.yaml` — read to detect existing mappings

### Assumptions

- Agent has network access to fetch docs
- equivalences.yaml structure stable
- One-to-one equivalence common case
- GCP ↔ Azure only (AWS deferred)
- User understands equivalence semantics

## Constitution Check

**Principles Implicated**: I (Verdict-Not-Guess), III (Human Gate), IV (Read-Only Write)

**I — Verdict-Not-Guess**:
✓ Agent proposes based on category + description + docs.
✓ User confirms (can decline/correct).
✓ No auto-write to equivalences.yaml.

**III — Human Gate**:
✓ Proposal is suggestion, not decision.
✓ Every proposal requires explicit confirmation.
✓ User can correct agent's name.
✓ Output is recommendation, not auto-write.

**IV — Read-Only Write**:
✓ Only write path: recommendation output (guidance text).
✓ Actual equivalences.yaml edit remains human-performed.
✓ No cascade side effects.
✓ Engineer review before KG land.

**Overall**: PASS. Design satisfies all three principles.

## Phase 0: Research

**Unknowns**: None significant. All spec assumptions sufficient.

## Phase 1: Design & Contracts

### Data Model

**EquivalenceProposal** (internal):
```
{
  provider_from: "gcp",
  service_name_from: "Vertex AI",
  provider_to: "azure",
  service_name_to: "Azure Machine Learning",
  confidence: "certain" | "likely" | "possible",
  rationale: "string",
  sources: ["urls"]
}
```

**EquivalenceRecommendation** (output):
```
Suggested entry for equivalences.yaml:

- gcp: Vertex AI
  azure: Azure Machine Learning
  notes: |
    Both ML platforms.

Proposed by: cloud-architecture-validator-add
Requires human review.
```

### Contracts

**Prompt** (fresh-add after judgment fields):
Input: service_name, provider, references_url, categories
Output: Prompt text + Proposal (if found) OR skip
User: Confirm | Correct | Decline

**Recommendation Output**:
Format: YAML block (copy-paste ready) + metadata + next steps

### Quickstart

**Scenario 1**: Fresh-add Cloud Run
```bash
python3 scripts/add_service.py --name "Cloud Run" --provider gcp \
  --references-url "https://cloud.google.com/run/docs"
# Judgment Qs → Equivalence prompt → "Container Instances" proposed
# User confirms → Recommendation output
```

**Scenario 2**: No equivalent
```bash
# Same flow → "No obvious equivalent" → Skip
```

**Scenario 3**: Update with competitor mention
```bash
python3 scripts/add_service.py --name "Vertex AI" --provider gcp \
  --references-url "https://cloud.google.com/vertex-ai/docs/updated"
# Update flow → Docs fetched, competitor mention detected
# Proposes equivalence → User confirms → Recommendation output
```

## Implementation Strategy

**MVP (Phase 1-3)**:
- US1: Fresh-add equivalence (new equivalence.py + tests + wire main)
- Basic proposal from metadata (category + description)
- Recommendation output

**Phase 2**:
- US2: Update path + competitor mention detection
- Reference text search

**Quality gates**:
- Existing -add tests unchanged
- Equivalence tests pass independently
- Quickstart scenarios 1-3 work end-to-end

## Deliverables

1. **equivalence.py**: `propose_equivalence()`, `detect_competitor_mention()`, `format_recommendation()`
2. **test_equivalence.py**: Proposal, recommendation, existing-mapping detection tests
3. **Updated add_service.py**: Wire US1 + US2 prompts
4. **quickstart.md**: Scenarios 1-3
5. **Updated SKILL.md**: Equivalence feature docs

No writes to equivalences.yaml (output-only). No new dependencies.
