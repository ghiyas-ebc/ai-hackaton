---
name: cloud-architecture-validator-create-architect
description: Validate cloud architectures (GCP and Azure) for structural, security, reliability, cost, and data-residency problems, and translate architectures between providers. Use this skill whenever someone describes a system made of cloud services and wants it reviewed, sketched, or diagrammed; whenever a non-technical user (sales, presales, account manager) needs an architecture for a client PoC or proposal; whenever someone asks for a cross-cloud equivalent ("what's the Azure equivalent of Cloud Run?", "what would this GCP architecture look like on Azure?"); and whenever an existing diagram needs a sanity check before it goes to a client. Do not answer connectivity or equivalence questions from general knowledge — run the validator scripts first, because plausible-sounding but wrong cloud architecture is exactly the failure mode this skill exists to prevent.
---

# Cloud Architecture Validator — Create Architecture

This is the core validate/translate/diagram skill — the one referred to
elsewhere as just "the validator." Sibling skills:
`cloud-architecture-validator-show-kg` browses the KG this skill owns;
`cloud-architecture-validator-add` and `cloud-architecture-validator-init`
add to and (re)populate it. This skill owns `references/kg/` — the others
read it, none of them fork or duplicate it.

This is not a diagram generator. Plenty of tools already turn text into boxes
and arrows. What this skill does: **check whether the proposed architecture will
actually work, hold up to a security review, and survive questions from the
client's architect** — and then, if asked, translate it to another provider.

The primary audience is sales and presales staff who don't design cloud
architectures for a living. They will not recognize technical jargon, and they
cannot act on findings phrased as jargon. Report findings in language they can
carry into a client conversation.

**Language:** these instructions are in English, but reply in whatever language
the user is writing in. Most findings will be delivered to an Indonesian-speaking
audience — translate the substance, don't hand over English strings verbatim.

## The principle that governs everything else

Valid/invalid decisions must **never** come from model reasoning. They come from
`scripts/validate.py`, which is deterministic. The model has three jobs here:
turn the user's description into a list of connections, run the validator, and
communicate the result in human language. The moment the model starts judging
connection validity on its own, the entire value of this skill disappears —
because that is precisely where confident-sounding hallucination lives.

## Workflow

### 1. Turn the description into a connection list

Map plain-language terms to `service_id`. The tables live in `references/gcp.md`
and `references/azure.md`. If the user names services without saying how they
connect, assume the most common pattern (entry point → compute → datastore) and
**state that assumption explicitly** before continuing.

Do not add connector components yourself at this stage. The validator decides
which connectors are needed — guessing first removes the chance for the validator
to catch that your guess was wrong.

If the provider is unclear, ask. Do not guess.

### 2. Run the validator

```bash
python3 scripts/validate.py \
  --edges "cloud-load-balancing>cloud-run,cloud-run>cloud-sql" \
  --environment production --residency id --sla critical
```

`--environment`, `--residency`, and `--sla` switch on the relevant rules in the
upper layers. Ask the user for these when the material is for a real client;
defaults are fine for an internal PoC.

The JSON output has three sections and all matter:

- `layers` — the L1–L8 ladder, one entry per layer, walked in order. Read this
  first: it tells you what was checked, what was clean, and what was
  `UNCOVERED`.
- `connectivity` — a verdict per connection (L1)
- `architecture` — findings from L2–L8, each tagged with its `layer`.
  **This is the section with the most value for the user.** Connectivity
  problems surface on their own during development; the upper layers are what
  sink a proposal in the meeting room.

The ladder:

| layer | checks | note |
|---|---|---|
| L1 | connectivity | **gate** — a dead edge is withheld from L2–L8 and listed in `gated_out` |
| L2 | security and exposure | |
| L3 | reliability | |
| L4 | data and residency | |
| L5 | cost | |
| L6 | operations | |
| L7 | performance and scale | **always `UNCOVERED`** — the KG has no properties to decide it |
| L8 | portability | derived from `equivalences.yaml` |

A layer with `status: UNCOVERED` was **not** checked. Say so plainly. Never
report it as passing, and never fill the gap with your own judgement — that
applies to L7 on every single run.

The ladder is `validate.py`'s decision tree, not yours. Do not reason through
the layers yourself to reach a verdict; read the ones the script produced and
explain them.

Verdict meanings:

| verdict | what to do |
|---|---|
| `ALLOWED` | draw as a direct line |
| `ALLOWED_WITH_NOTE` | draw directly, surface the note |
| `NEEDS_COMPONENT` | insert the node from `insert_component`; do not draw a direct line |
| `BLOCKED` | do not draw; report as a finding with its remediation |
| `FEATURE_ON_NODE` | not a separate node; draw as a badge on the node in `render_as` |
| `UNCOVERED` | unrecognized pattern — flag for architect review, do not guess |
| `UNKNOWN_SERVICE` | service absent from the KG — confirm the name with the user |

`UNCOVERED` and `UNKNOWN_SERVICE` are the only states where the answer is "I
don't know". Say so plainly. Guessing here is the exact behaviour that makes
people stop trusting AI output for technical work.

### 3. Cross-provider translation

```bash
python3 scripts/translate.py --edges "..." --to azure
```

If the status is `AWAITING_DECISION`, some service has more than one equivalent
(Pub/Sub maps to either Service Bus or Event Grid — not a trivial choice).
**Ask the questions in `needs_decision`; do not choose on the user's behalf.**
Then re-run with `--choose`.

The script already handles the two things that are easy to get wrong: source
connectors are dropped and regenerated according to target-provider rules, and
connections that ran through them are reconnected end to end. The result is
re-validated automatically — read the `revalidation` section like any other
validation result.

Surface every `caveats` entry in `equivalence_notes`, especially at level
`PARTIAL`. Presenting a PARTIAL equivalent as if it were 1:1 is the most
expensive mistake in this flow, because it looks clean right up until the client
asks about it.

More detail: `references/translation.md`.

### 4. Draw the diagram

Only after validation. Rules are in `references/rendering.md` — read it before
generating the first diagram in a session.

### 5. Report

Structure the report to the user like this:

```
[diagram]

Summary
  One sentence: ready to present, or needs fixes first.

Must fix (ERROR)
  What is wrong, what it means for the client, how to fix it.

Worth mentioning to the client (WARNING/INFO)
  Not errors, but things that will come up in review.

Not yet determinable
  UNCOVERED / UNKNOWN_SERVICE items, with a recommendation to review
  with the engineering team.
```

Never dump raw JSON. Never enumerate every valid connection — just state that
the rest checks out.

## Constraints to hold

- **Never draw an ERROR connection as a plain line with no annotation.** This is
  the core of the skill's value; break it and this is just another diagram
  generator.
- **Never guess on `UNCOVERED` or `UNKNOWN_SERVICE`,** however obvious the answer
  feels. If the combination really is valid and comes up often, propose adding
  it to the KG — that is a permanent fix, whereas a guess just moves the risk
  onto the user.
- **Never pick a cross-provider equivalent** when several options exist. The
  question is already written for you; ask it.
- **Never add components to the diagram that did not come from
  `insert_component`.** If you think something is missing, say so as a separate
  recommendation rather than quietly drawing it in.
- This skill validates structure, not capacity. It knows nothing about quotas,
  real pricing, or performance limits. Do not promise numbers.

## Changing the knowledge graph

Validity is not stored as a list of pairs; it is derived from node properties by
`references/kg/connectivity-rules.yaml`. Adding a service means adding one entry
to `references/kg/services.yaml` with the right properties — its connections are
covered immediately.

For adding a single service with brand/category/description/reference-URL/icon
validated by an agent before it's written, use `cloud-architecture-validator-
add` rather than editing `services.yaml` directly — same underlying file, but
with the human-confirmation gate D6 requires (see this repo's top-level
CLAUDE.md: a wrong `reachability` value fails silently across ~20 pairs, and
`check_kg.py` cannot catch it, so nothing writes this file unattended). For
bulk (re)population from an external catalog, that's
`cloud-architecture-validator-init`.

Every entry also carries a `provenance` block recording who wrote it and
whether a human confirmed the three properties a lookup cannot answer
(`network_placement`, `reachability`, `roles`). A hand-written entry is
`status: manual`; an agent-proposed one starts `unverified` and `check_kg.py`
fails until a human confirms it. Header comments in `services.yaml` give the
full field list.

After every change:

```bash
python3 scripts/check_kg.py
```

This checks integrity and runs the regression suite. Watch two coverage
figures: the L1 pair percentage, and the per-layer rule counts under
`Layer coverage`. Either dropping means a rule accidentally became too narrow —
the per-layer numbers exist because a single layer can go dead without moving
the headline percentage much.

## Supporting files

- `references/gcp.md` — plain language → GCP service_id, GCP-specific behaviour
- `references/azure.md` — plain language → Azure service_id, Azure-specific behaviour
- `references/translation.md` — cross-provider workflow and its traps
- `references/rendering.md` — layout, icon, and label rules
- `references/kg/` — the knowledge graph (nodes, rules, equivalences)
- `scripts/validate.py` — L1-L8 ladder validator
- `scripts/translate.py` — cross-provider translation
- `scripts/check_kg.py` — KG integrity + regression
