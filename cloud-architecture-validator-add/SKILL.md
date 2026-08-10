---
name: cloud-architecture-validator-add
description: Add a single cloud service to the KG with agent-proposed safe fields (category, description, references_url, icon) and human-confirmed judgment fields (network_placement, reachability, roles). Supports fresh add and staleness-detected updates.
---

# Cloud Architecture Validator — Add

Add or update a single service in `cloud-architecture-validator-create-architect`'s `references/kg/services.yaml`: agent-assisted for the fields an agent can verify, human-gated for the ones it can't.

## Usage

```bash
python3 scripts/add_service.py --name "Service Name" --provider gcp [--references-url https://...] [--dry-run]
```

**Arguments**:
- `--name` (required): Service display name
- `--provider` (required): `gcp` or `azure`
- `--references-url` (optional): URL to documentation for agent fetch + staleness check
- `--dry-run` (flag): Propose but don't write

**Exit codes**:
- `0`: Success (entry written or existing entry reported)
- `1`: Abandoned (user declined after proposal) or no update needed
- `2`: Error (missing KG, usage error)

## Flow

### Fresh Add (New Service)

1. User provides `--name` and `--provider`
2. Skill checks for duplicate `(name, provider)` pair
3. If duplicate found (no newer reference): reports existing entry, exits
4. If fresh: proposes safe fields (category, description, references_url, icon)
5. User answers three judgment questions: network_placement, reachability, roles
6. User can correct any field before confirming
7. Entry written to `services.yaml` with `provenance.status: unverified`

### Update (Newer Reference Found)

1. User provides `--name`, `--provider`, and `--references-url`
2. Skill checks for duplicate `(name, provider)` pair
3. If duplicate found + reference newer than entry's `provenance.verified` date:
   - Proposes update with draft answers for all three judgment fields
   - Shows differences from current entry
   - **Equivalence detection** (US2): Searches reference text for competitor mentions; if found, proposes equivalent service
4. User confirms each draft (or corrects before confirming)
5. If equivalence proposal shown, user accepts/corrects/declines (outputs recommendation for manual edit)
6. Entry updated in place with `provenance.status: unverified` (reset from prior)

### Duplicate Prevention

- Duplicate `(name, provider)` without newer reference: reports existing entry, no second entry

## The line this skill has to draw, and why

Split the fields in `services.yaml` into two kinds, because they fail differently when wrong:

**Verifiable by an agent (fetch + cross-check, safe to automate):**
`name`, `provider`, `category`, `description`, `references_url` — check the URL resolves, check the brand/category string matches what the provider actually calls the thing. Wrong here is annoying and visible; the user or a reviewer catches it on sight.

**Judgment calls, not automatable by data lookup — human confirms, always:**
`network_placement`, `reachability`, `roles`. These decide *validity*: they are exactly what `connectivity-rules.yaml` reads to produce a verdict. This is create-architect's CLAUDE.md decision D6, restated because it's the one constraint this skill cannot relax without breaking the parent skill's entire premise: *"a node with a wrong `reachability` value fails silently across roughly twenty pairs, producing confident wrong verdicts. Critically, `check_kg.py` would not catch it — it verifies structural consistency, not semantic truth."* An agent that "validates" a provider's marketing copy has no way to independently confirm whether a service's default posture is public or private-only — that isn't written down anywhere a lookup reaches, and guessing here is the specific failure mode create-architect's Layer 1 exists to prevent elsewhere.

So: agent pass proposes and checks the safe fields; the judgment fields are always presented to a human as an explicit question, never inferred, never defaulted. This mirrors create-architect's own `tools/sync_provider_inventory.py` pattern — automate the fetch, never automate the classification.

**Icon**: resolve via the same mechanism `references/kg/icons.yaml` + `kg.py`'s `icon_for()` already use (provider-official icon directories via `CAV_GCP_ICON_DIR`/`CAV_AZURE_ICON_DIR` env vars) — this part is genuinely mechanical and safe for the agent to do outright.

## Writes in place — decided, not a TODO

The confirmed entry lands directly in `cloud-architecture-validator-create-architect`'s `references/kg/services.yaml`, appended or replaced the same way a human edit would do it. No separate staging file, no outside store, no second copy of the data anywhere. This skill must not grow a second way to mutate `services.yaml` that `check_kg.py` doesn't already cover — one file, one write path, whether the edit came from a person or from this skill's agent-assisted flow.

## Provenance is not optional

Every entry this skill writes carries a `provenance` block (root CLAUDE.md D21). This skill writes `generated: cloud-architecture-validator-add` and `status: unverified`, plus `sources:` listing the URLs the agent checked the safe fields against. **`check_kg.py` fails while status is `unverified`** — that is the point, not a bug to route around. Only the human review step flips it to `status: verified` with a `verified:` date.

This skill must never write `status: verified` itself, and never write `status: manual` — `manual` means a person hand-wrote the entry with no agent in the loop, which is by definition not what happened here.

## Equivalence Detection (Fresh-Add & Update)

During fresh-add, after judgment fields confirmed: user is prompted whether service has a cross-provider equivalent. Agent proposes (e.g., "Cloud Run → Container Instances"). User can accept/correct/decline. If confirmed, system outputs recommendation block (YAML + metadata) for manual `equivalences.yaml` edit.

During update with newer reference: system checks reference text for competitor product mentions. If found (e.g., "Agent Platform"), triggers same equivalence proposal flow.

**Key guarantee**: Equivalence detection never auto-writes to `equivalences.yaml`. Recommendation-only — user manually edits file + engineer reviews before KG ingestion.

## Before using in production

1. Run `quickstart.md` scenarios 1-6 manually to confirm CLI behavior (fresh-add, update, equivalence prompts)
2. Run `check_kg.py` after a real add to verify:
   - 37/37 regression unaffected
   - L1 coverage unaffected elsewhere
   - New entry's `provenance.status: unverified` is the only reported provenance failure
3. Flip entry to `status: verified` after human review
4. If equivalence recommendation output, manually edit `references/kg/equivalences.yaml` + verify with `translate.py`
