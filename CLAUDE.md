# CLAUDE.md

Orientation for any agent working in this repository. Read this before changing
anything under `cloud-architecture-validator-create-architect/references/kg/`
or any of the four skills' `scripts/`.

## What this is

Four Claude Skills, split from one, covering the lifecycle of a knowledge
graph of cloud services (GCP, Azure) and the architectures built from it:

- **`cloud-architecture-validator-create-architect`** — the core skill.
  Validates architectures for structural, security, reliability, cost, and
  data-residency problems, and translates them between providers. Owns
  `references/kg/` — the single source of truth the other three read.
- **`cloud-architecture-validator-show-kg`** — read-only, Neo4j-Bloom-style
  visual explorer of the KG itself (not a specific architecture). Has no KG
  of its own; imports create-architect's `kg.py`/`validate.py` directly so it
  can't drift.
- **`cloud-architecture-validator-add`** — design stub. Add one service to
  the KG, agent-verified where verification is possible (brand, category,
  description, references_url, icon), human-gated where it isn't
  (`network_placement`, `reachability`, `roles` — see D6).
- **`cloud-architecture-validator-init`** — design stub. Bulk (re)populate
  the KG from an external public catalog, versioned so a bad sync reverts
  cleanly. Source/schema/auth not yet specified.

Its users are salespeople and presales engineers who do not design cloud
architecture for a living, producing material that goes in front of a
client's architect.

It is not a diagram generator. The value is in catching things that would
otherwise be caught in a client design review, or worse, after go-live.

## Commands

All paths below are relative to `cloud-architecture-validator-create-architect/`
unless stated otherwise — that is the skill that owns the KG and the core
scripts.

```bash
python3 scripts/check_kg.py                      # integrity + regression + coverage
python3 scripts/validate.py --edges "a>b,b>c"    # two-layer validation
python3 scripts/translate.py --edges "..." --to azure
python3 tools/sync_provider_inventory.py --list tools/sample_resource_types.txt

# from cloud-architecture-validator-show-kg/scripts/ — reads the sibling KG above
python3 export_kg_graph.py --output ../visualizations/kg_graph.json
```

`check_kg.py` must report clean integrity, **37/37 regression**, and coverage
**≥80%** before anything ships. A coverage drop means a rule silently narrowed.

## Invariants — do not break these without an explicit decision

Unqualified `scripts/`, `references/`, and `tools/` paths below are all
inside `cloud-architecture-validator-create-architect/` — the skill that owns
them.

1. **No LLM in the decision path.** Verdicts come from `scripts/validate.py`.
   The model parses descriptions and communicates results; it never judges
   validity. This is the entire point of the skill.
2. **Validity is derived, not enumerated.** Connection validity comes from node
   properties via `connectivity-rules.yaml`. Do not add pair entries when a rule
   would cover the case. `overrides.yaml` is currently empty and should stay
   close to empty.
3. **No runtime dependency beyond PyYAML.** No cloud SDK, no credentials, no
   network at skill runtime. `tools/` is exempt: it runs at authoring time and
   is excluded from the shipped zip.
4. **Nothing writes `services.yaml` automatically.** See D6.
5. **`UNCOVERED` and `UNKNOWN_SERVICE` are valid answers.** Never make the
   system guess to avoid them.

## Decision log

Rationale for choices that look questionable without context. Several of these
are things a reasonable reader would otherwise propose reversing.

**D1 — Local YAML, not BigQuery.** The original draft stored the knowledge graph
in a BigQuery Property Graph. Total KG size is roughly 100 rows: file scale, not
warehouse scale. BigQuery made the skill unable to run without network and GCP
credentials — including when demoing Azure architectures to Azure clients. A
BigQuery backend stub remains in `scripts/kg.py` behind the same interface, for
when the KG outgrows files or needs multi-editor governance. *Reconsider only if
the KG passes roughly a thousand nodes or several people edit it concurrently.*

**D2 — Property model, not pair enumeration.** The draft stored validity as a
list of connection pairs: 20 edges covering 462 directed GCP pairs, about 4%.
Since the skill refuses to guess on unknown pairs, that meant nearly every real
architecture returned mostly "needs manual review" — alarm fatigue, and users
would learn to ignore the whole report. Properties plus ~18 rules brought
coverage to 80% with a similar volume of data. `evals/regression_draft_edges.json`
proves no knowledge was lost in the move.

**D3 — One skill, references per provider.** The draft had three skills (gcp,
azure, router) where the Azure skill referenced files inside the GCP skill's
folder — so installing it alone left it without its workflow. Split again only
when AWS/Huawei land and per-provider files exceed ~300 lines.

**D4 — Layer 2 exists and is the actual product.** Connectivity checks are table
stakes; those errors surface during development anyway. Security exposure, SPOF,
egress cost, and data residency are what sink a proposal. Do not treat
`architecture-rules.yaml` as secondary.

**D5 — Terraform is not the foundation.** Considered and rejected. `terraform
validate` checks syntax and schema consistency without contacting provider APIs
— it passes cleanly on a Cloud Run to Cloud SQL private-IP configuration, which
is exactly the class of error Layer 1 exists to catch. It also presumes HCL
exists, and this skill operates in the pre-code phase where it does not.
Terraform provider schemas *are* used, but only as a gap detector (see D6).
Accepted future uses: HCL as an **input adapter** for auditing existing
infrastructure (different persona, high value), and HCL skeleton as an **output
artifact**. Note the team does not currently use Terraform, which lowers the
priority of the input adapter.

**D6 — `sync_provider_inventory.py` never writes `services.yaml`.** Do not add
`--auto-merge`. The asymmetry: a missing node fails safely (`UNKNOWN_SERVICE`,
user is told to confirm), while a node with a wrong `reachability` value fails
silently across roughly twenty pairs, producing confident wrong verdicts.
Critically, **`check_kg.py` would not catch it** — it verifies structural
consistency, not semantic truth. Human classification is the only gate that
exists for this. Provider schemas carry names and attributes, never network
placement, reachability, or roles.

**D7 — Six verdicts deliberately differ from the original draft.** Documented
per-case in `evals/regression_draft_edges.json`. The substantive one: serverless
to managed-SQL was ERROR in the draft, now WARNING at Layer 1 because a public
endpoint exists and the connection does not fail. Layer 2 `SEC-001` still
escalates it to ERROR when no private connector exists anywhere in the
architecture. Same practical outcome, correct reasoning.

**D8 — Instructions in English, replies in the user's language.** `SKILL.md`
carries this rule explicitly, and `evals/evals.json` keeps its prompts in
Indonesian to test it. The performance premise behind English instructions is
plausible but unmeasured — see open questions.

**D9 — Four skills, split by workflow rather than by provider.** D3 said split
again only when AWS/Huawei land — that threshold hasn't been hit, and this
split doesn't contradict it: D3 was about per-provider file growth, this is a
different axis. What changed: validating an architecture, exploring the KG,
adding one service, and bulk-populating the KG are four different jobs with
four different risk profiles — the first is read-only and safe to run
constantly, the second is read-only and exploratory, the third and fourth
both write to `services.yaml` and need the human-confirmation gate D6
requires, but at very different scale (one entry vs. many). Bundling them
into one skill meant `-add`/`-init` requests would load the entire
validate/translate workflow into context even when the user just wanted to
browse the graph. `create-architect` still owns `references/kg/` alone; the
other three read it via relative sibling paths and fail loudly if it isn't
installed alongside them, rather than forking a copy. `-init` and `-add` are
currently design stubs — SKILL.md plus a script that refuses to run — not
working tools; see their own `SKILL.md` for what's actually missing.

## Open questions

Genuinely unresolved. Do not present any of these as settled.

- **Rendering is unimplemented.** Only `references/rendering.md` exists, and most
  of it is explicitly marked as unverified heuristic. Unknown whether draw.io's
  built-in shape libraries cover all 45 services.
- **Layer 2 rules are untuned.** Thresholds and severities are reasoned, not
  measured against real proposals. `REL-002` and `OPS-001` are the likeliest to
  prove too noisy.
- **Evals have never been run** against a Claude instance with the skill loaded.
  The highest-value cases are E02, E03, and E06 — all three test whether the
  model holds back rather than guessing.
- **English-vs-Indonesian instruction performance is unmeasured.** An Indonesian
  version of the skill exists in earlier history if a comparison is wanted.
- **Provider release lag is unmeasured**, so the right sync cadence is a guess
  (currently: quarterly).
- **The clustering heuristic in the sync tool is crude** — splits on the first
  two tokens. Fine for the sample; likely wrong somewhere on real provider data.
  Fix after seeing it fail, not before.
- **`cloud-architecture-validator-init`'s data source is unspecified.** Bulk
  sync "from a public database" was requested without saying which one, its
  schema, or its access method — none of that is decided, let alone built.
- **`cloud-architecture-validator-init`'s versioning scheme is unspecified.**
  "Rollback a bad sync" is the requirement; commit-based vs. snapshot-based
  vs. something else is not decided.
- **`cloud-architecture-validator-add`'s human-confirmation UX is unspecified.**
  Likely mirrors `tools/review_queue.yaml`'s per-candidate question format,
  but that's a guess, not a decision.

## Style

Explain why a constraint exists rather than asserting it. The KG comments carry
most of the reasoning behind the model; keep them when editing, and prefer
YAML over JSON for that reason.
