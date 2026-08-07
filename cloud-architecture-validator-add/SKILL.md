---
name: cloud-architecture-validator-add
description: NOT YET IMPLEMENTED. Intended to add one cloud service to cloud-architecture-validator-create-architect's knowledge graph, with an AI agent validating brand, category, description, references_url, and icon before anything is written, and a human confirming the connectivity-relevant fields the agent cannot judge. Currently a design stub — running it produces a clear "not implemented" error rather than touching services.yaml. Do not use this to actually add a service; add it by hand following create-architect's own "Changing the knowledge graph" instructions, or wait for this skill to be built.
---

# Cloud Architecture Validator — Add (stub)

Not built yet. This file exists to reserve the name and record the design
intent — including where an "AI agent validates the fields" plan runs into
this repo's own stated principle that it must not.

## Intended purpose

Add a single service to `cloud-architecture-validator-create-architect`'s
`references/kg/services.yaml`: agent-assisted for the fields an agent can
actually verify, human-gated for the ones it can't.

## The line this skill has to draw, and why

Split the fields in `services.yaml` into two kinds, because they fail
differently when wrong:

**Verifiable by an agent (fetch + cross-check, safe to automate):**
`name`, `provider`, `category`, a `description`, `references_url` — check the
URL resolves, check the brand/category string matches what the provider
actually calls the thing. Wrong here is annoying and visible; the user or a
reviewer catches it on sight.

**Judgment calls, not automatable by data lookup — human confirms, always:**
`network_placement`, `reachability`, `roles`. These decide *validity*: they
are exactly what `connectivity-rules.yaml` reads to produce a verdict. This
is create-architect's CLAUDE.md decision D6, restated because it's the one
constraint this skill cannot relax without breaking the parent skill's entire
premise: *"a node with a wrong `reachability` value fails silently across
roughly twenty pairs, producing confident wrong verdicts. Critically,
`check_kg.py` would not catch it — it verifies structural consistency, not
semantic truth."* An agent that "validates" a provider's marketing copy has
no way to independently confirm whether a service's default posture is
public or private-only — that isn't written down anywhere a lookup reaches,
and guessing here is the specific failure mode create-architect's Layer 1
exists to prevent elsewhere.

So: agent pass proposes and checks the safe fields; the judgment fields are
always presented to a human as an explicit question, never inferred, never
defaulted. This mirrors create-architect's own `tools/sync_provider_inventory.py`
pattern — automate the fetch, never automate the classification.

**Icon**: resolve via the same mechanism `references/kg/icons.yaml` +
`kg.py`'s `icon_for()` already use (provider-official icon directories via
`CAV_GCP_ICON_DIR`/`CAV_AZURE_ICON_DIR` env vars) — this part is genuinely
mechanical and safe for the agent to do outright.

## Writes in place — decided, not a TODO

The confirmed entry lands directly in `cloud-architecture-validator-create-
architect`'s `references/kg/services.yaml`, appended the same way a human
edit would append it. No separate staging file, no outside store, no second
copy of the data anywhere. This skill must not grow a second way to mutate
`services.yaml` that `check_kg.py` doesn't already cover — one file, one
write path, whether the edit came from a person or from this skill's
agent-assisted flow.

## Before implementing this for real

1. Decide the exact human-confirmation UX — a single question batch per
   service, most likely, matching `tools/review_queue.yaml`'s
   four-classification-question shape from create-architect.
2. Decide how a rejected/edited proposal round-trips back to the agent for
   correction, versus how many free retries before it's a hard human edit.
3. Run `check_kg.py` after every add, same as a manual edit — coverage must
   not drop, and the new entries must show up in reachability output for at
   least one rule.
