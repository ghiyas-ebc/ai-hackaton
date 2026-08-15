# CLAUDE.md

Orientation for any agent working in this repository. Read this before changing
anything under `cloud-arch-validator-agent/db/` or `cloud-arch-validator-agent/
app/kg_lib/`.

## What this is

A multi-agent ADK application over a knowledge graph of cloud services (GCP,
Azure) stored in Postgres. It validates architectures for structural, security,
reliability, cost, and data-residency problems, and translates them between
providers.

`cloud-arch-validator-agent/` is the product. A coordinator with no tools routes
to three specialists (D25):

- **`validator_agent`** — validates a described architecture and translates it
  between providers. Read-only. The common case.
- **`explorer_agent`** — questions about the graph itself: which services exist,
  filtering them by typed fields, graph health and rule coverage. Read-only.
- **`curator_agent`** — the only writer. Adds a service, records human
  verification. Gated on an engineer supplying `network_placement`,
  `reachability` and `roles` (D6, D26).

The four `cloud-architecture-validator-*` skill directories and the installed
copy under `.claude/skills/` are **deleted** by D27. They held their own copies
of the knowledge graph, one of which had gone two decisions stale while staying
invocable. Postgres is the only source of truth now.

`app/references/kg/*.yaml` still exists and is **generated output** — written by
`db/export_to_yaml.py`, never edited. See D27.

Its users are salespeople and presales engineers who do not design cloud
architecture for a living, producing material that goes in front of a
client's architect.

It is not a diagram generator. The value is in catching things that would
otherwise be caught in a client design review, or worse, after go-live.

## Commands

All paths below are relative to `cloud-arch-validator-agent/`.

```bash
docker compose up -d db                  # local Postgres, the graph's home
uv run python db/migrate.py              # apply pending schema migrations
uv run python db/migrate.py --status     # applied vs pending
uv run python db/seed_from_yaml.py       # rebuild a database from the export
uv run python db/export_to_yaml.py       # Postgres -> YAML, after any change
uv run python db/export_to_yaml.py --check     # diff the export against the DB

uv run pytest tests/unit tests/integration
uv run ruff check app tests db
```

The graph's own gate is `check_kg_health` (the `check_kg.py` engine): clean
integrity, **37/37 regression**, and L1 coverage **≥80%** before anything ships.
A coverage drop means a rule silently narrowed. It also reports per-layer
coverage for L2–L8 (see D23); a layer whose rules stop firing is the same
failure, hidden from the headline number. An entry flagged `provenance.status
unverified` is the D21 sign-off gate holding, not a defect — clear it by
reviewing the entry, not by clearing the flag.

Tests that need Postgres skip when `CAV_PG_DSN` does not answer, so the suite is
green on a machine with no database. The migration's parity proof runs without
one either: it chains the pure halves of the seed and the loader.

## Invariants — do not break these without an explicit decision

1. **No LLM in the decision path.** Verdicts come from `scripts/validate.py`.
   The model parses descriptions and communicates results; it never judges
   validity. This is the entire point of the skill.
2. **Validity is derived, not enumerated.** Connection validity comes from node
   properties via `connectivity-rules.yaml`. Do not add pair entries when a rule
   would cover the case. `overrides.yaml` is currently empty and should stay
   close to empty.
3. **No cloud SDK, no credentials for a specific cloud, at runtime.** *Amended
   by D24 — this used to read "no runtime dependency beyond PyYAML".* The graph
   now lives in Postgres, so `psycopg` is a runtime dependency. What has not
   changed is the reason the rule existed: no `google-cloud-*` client, no
   provider account needed to run the tool, and nothing that makes demoing an
   Azure architecture require a GCP login. A DSN is not a cloud SDK. `tools/` is
   exempt: it runs at authoring time and is excluded from the shipped zip.
4. **Nothing adds a service without a human supplying the judgment fields.**
   *Amended by D26 — this used to read "nothing writes `services.yaml`
   automatically".* The file is no longer the store; the gate is unchanged and
   now has a CHECK constraint under it. See D6 and D26.
5. **`UNCOVERED` and `UNKNOWN_SERVICE` are valid answers.** Never make the
   system guess to avoid them.

## Decision log

Rationale for choices that look questionable without context. Several of these
are things a reasonable reader would otherwise propose reversing.

**D1 — Local YAML, not BigQuery.** *Superseded by D24: the graph is in Postgres.
The reasoning below is why BigQuery was wrong, and most of it is why Postgres is
the right replacement rather than a return to the warehouse.* The original draft
stored the knowledge graph
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

**D10 — KG checkpoints are pull-once snapshots, triggered by `check_kg.py`
passing, never a runtime dependency.** Answers the versioning half of
`cloud-architecture-validator-init`'s design (the data-source half is still
open — see below). A checkpoint is a zip of the entire `references/kg/`
directory (all six files — they interact, a partial snapshot isn't a real
rollback point) plus a manifest: version tag, git commit SHA, timestamp,
node count, regression result, coverage %, and a SHA-256 of the zip. Trigger
is `check_kg.py` reporting clean — a checkpoint means "this state passed the
gate," not "someone hit save." Storage is a GitHub Release, not GCS — decided
in favor of zero new infrastructure and no cloud SDK dependency, consistent
with `-init`'s own fetch side (see below): both directions of this skill stay
on plain HTTP/`gh` CLI, no `google-cloud-storage` client anywhere in the
dependency tree. **Same condition as D1 applies regardless of backend:** this
is authoring/distribution only. `-init` pulls a pinned checkpoint once and
writes local YAML; `create-architect`'s live validate path never reads from
GitHub at request time. This is also why GCS was ruled out and not just
deprioritized — it would reintroduce the exact failure D1 already rejected
BigQuery for, and worse: you can't demo an Azure architecture off a
GCP-credentialed backing store without a GCP account in hand.

**D11 — `-init` fetches over plain HTTP, no cloud SDK.** The external catalog
`-init` bulk-syncs from is read via a plain `GET` against a public URL —
standard library only, no auth, no `google-cloud-storage` or any other cloud
client dependency. Keeps `-init` as dependency-light as create-architect
itself (PyYAML and nothing else — root invariant #3). If the real source
later needs auth or isn't reachable over plain HTTPS, that's a reason to
reconsider the source, not a reason to add an SDK. The specific URL, its
schema, and update cadence are still unspecified — this decision fixes the
*method*, not the *source*.

**D12 — `-add` writes directly to `services.yaml`, no outside store.**
*Superseded by D24/D26 — the store is now a Postgres table. The principle it
was really asserting survives: one write path, no staging copy, whether the
edit came from a person or an agent.* The confirmed entry lands in place, the
same file and the same way a manual edit would land it. No staging file, no
second copy of the data living anywhere else — one file, one write path,
whether the edit came from a person or from `-add`'s agent-assisted flow.

**D13 — Verify rendering against a small real subset before trusting it
broadly.** `references/rendering.md`'s layout rules are marked unverified
heuristics, and nobody has opened `emit_drawio.py`'s output in real draw.io
to confirm icons/layout actually look right. Rather than verify all 45
services up front, verify the ~10 most likely to appear in an actual sales
demo first (load-balancer → compute → datastore patterns, the ones already
used as examples throughout this doc), fix what's ugly, expand coverage as
real usage surfaces more combinations. A broken diagram in front of a client
is worse than no diagram, but this doesn't need to block on covering
services nobody will draw yet.

**D14 — Untuned Layer 2 rules render as INFO, not their nominal severity,
until measured.** `REL-002` and `OPS-001` specifically — their severities
were reasoned, not measured against real proposals. Downgrading them to
INFO until they've seen real usage keeps the tool honest about what it
actually knows, consistent with the `UNCOVERED`-over-guessing principle
already governing Layer 1. Cheap and reversible: restore nominal severity
once a rule has been checked against real client material and holds up.

**D15 — Evals must run against a live Claude instance before real client
use, particularly E02/E03/E06.** Those three test whether the model holds
back rather than guesses — the entire premise invariant #1 rests on. Until
`evals/evals.json` has actually been run against a Claude instance with the
skill loaded, "the model never guesses" is an unverified claim, not a
verified invariant, regardless of how the rule engine itself tests out.

**D16 — English-vs-Indonesian instruction performance stays unmeasured for
now.** No evidence the current setup (English instructions, replies matched
to the user's language) is actually a problem — chasing an unmeasured
premise with no signal it's broken isn't worth the cycles. Revisit only if
reply quality issues actually surface in Indonesian sessions specifically.

**D17 — Sync cadence stays quarterly.** No data exists yet on actual
provider release lag either way, so tightening the guess now would just be
a different guess. Revisit once `-init` has real run history to look at.

**D18 — The sync tool's crude clustering heuristic (splits on first two
tokens) stays as-is.** `tools/` is authoring-time only, zero runtime risk —
per this doc's own stated plan, fix after seeing it misfire on real
provider data, not before.

**D19 — `-init`'s source is a plain public URL — a GCS public object link or
a GitHub Release asset link, not a database.** Consistent with D11: no auth,
no cloud SDK, just an HTTPS `GET` against a URL that happens to be hosted on
GCS-as-public-bucket or as a GitHub Release asset. The specific URL is still
unpicked (see Open questions), but the *shape* of the source is now settled.
Note this is deliberately the same mechanism D10 already chose for
checkpoint *output* (GitHub Releases) — input and output could plausibly
share infrastructure, though they remain conceptually separate: one is the
external catalog `-init` reads, the other is `-init`'s own versioned
snapshot of what it wrote.

**D20 — `-add`'s human-confirmation UX reuses `tools/review_queue.yaml`'s
existing four-question-per-candidate shape.** That format already solves
the same problem (present a human with the judgment-call fields a fetch
can't answer) for the Terraform-schema sync path. Don't invent a second
review format for a near-identical problem in the same repo — reuse until
it demonstrably doesn't fit `-add`'s case.

**D21 — Every `services.yaml` entry carries a `provenance` block, and
`check_kg.py` fails on any entry an agent proposed that no human has signed
off.** Adopted from OKF v0.2's trust/provenance fields (`sources`,
`generated`, `verified`, `status`, `stale_after`) — the one part of the
Graphify/OKF pattern worth taking. The rest of that pattern was rejected:
Graphify extracts a graph *from* unstructured code via Tree-sitter plus LLM
semantic extraction, which is a problem this repo does not have (the KG is
45 hand-curated nodes), and its store-nodes-and-edges model is a straight
D2 reversal — our edges are derived from node properties at query time, not
persisted. NetworkX would also breach invariant #3. OKF as the KG's own
on-disk format stays rejected for the reason already given: one-concept-per-
file markdown loses the YAML comments this doc's Style section calls the
primary carrier of the model's reasoning, and it shatters the six
interacting files D10 requires to snapshot together.

What provenance buys that nothing else does: D6 correctly says `check_kg.py`
cannot catch a wrong `reachability` because it checks structural
consistency, not semantic truth. That stays true. But it *can* catch
"nobody claims to have looked," which converts D6 from a discipline into a
gate — `-init` and `-add` write `status: unverified`, the check fails, a
human flips it to `verified` with a date. `status` is three-valued, not
boolean: `manual` (hand-written, no agent involved, judgment fields human by
construction), `unverified` (agent-proposed, fails the check), `verified`
(agent-proposed and human-confirmed, requires a `verified:` date). All 45
existing entries backfilled as `manual` rather than `verified` with an
invented date — they *are* hand-authored, but nobody re-reviewed them on
2026-08-08 and the field should not say otherwise. `stale_after` warns
rather than fails, and is what gives D17's quarterly cadence something
concrete to act on.

**D22 — No RAG, no embeddings, no vector store. The KG goes into context
whole.** All six files total 46 KB (~12k tokens); `services.yaml` alone is
17 KB for 45 nodes. Retrieval exists to select from a corpus that does not
fit in context — a retriever here would shrink 12k tokens to 8k while adding
a ranking layer that can be wrong. It can only subtract. The model is the
semantic layer: it already knows Cloud SQL is a database without being told,
which is precisely the "semantic search" a lexical scorer was being built to
fake. A concrete attempt made this vivid: a hand-built scorer for
`kg_explorer.html` ranked "Serverless VPC Access" second on the query
*serverless public database*, and fixing that took a 50-entry synonym map
plus a coverage-weighting term — machinery to approximate, badly, what the
model does for free.

Two further reasons this stays decided rather than deferred. First, vector
search is the wrong tool for *structured* data regardless of scale: these are
typed fields, and "reachability = public_or_private AND category = database"
is a `WHERE` clause, not a cosine distance. When the KG does outgrow context,
the answer is a query tool (D1's BigQuery stub), not embeddings. Second,
anything that retrieves must stay clear of the decision path — retrieval that
feeds `validate.py` a *subset* of the KG silently changes verdicts, which is
invariant #1 violated by omission rather than by opinion. The retrieval panel
in `kg_explorer.html` is therefore a **visualization** of what a question
touches, explicitly not a retrieval step, and nothing downstream reads it.

**D23 — Layer 2 is now a declared L1–L8 ladder, with L1 as a gate and L7
deliberately empty.** D4 established that Layer 2 is the actual product; this
gives it structure. The nine existing rules were regrouped, not rewritten
(rule ids are unchanged — the 37/37 regression fixture depends on them, and
`REL-003` sits under L4 despite its `REL-` prefix because backup is a data
concern). Layers are declared in `architecture-rules.yaml` and every rule
names one, so `check_kg.py` can report **per-layer** coverage: a single layer
can go dead without moving the headline L1 percentage, which one global number
would hide.

Three properties worth keeping:

*L1 gates.* An edge that cannot connect is withheld from L2–L8 (`gated_out`
records what was withheld). Without this, one broken connection sprays derived
findings across seven layers and buries the single finding that matters.
Node-scoped rules still see the node — a zonal service is zonal whether or not
one of its edges is broken.

*L7 ships empty and says so.* Performance needs node properties the KG does
not carry (scaling model, sync vs. async, throughput class). Inferring them
from `category` would be guessing, so L7 reports `UNCOVERED` on every run —
invariant #5 applied to a whole layer rather than a pair. Filling it means a
human classification pass over all 45 entries under D6/D21, which is the real
cost and the reason it is not done yet.

*L8 was free.* Portability is derived entirely from `equivalences.yaml`, so it
needed no schema change, and it cannot drift from what `translate.py` would
actually do. It is also the layer most specific to this product's audience: a
presales engineer asked "are we locked in?" gets a derived answer instead of a
reassurance. Both PORT rules ship at INFO per D14. Note `PORT-001` must skip
nodes whose roles are in `regenerate_roles` — connectors have no equivalents
*by design* (equivalences.yaml drops and regenerates them at the target), and
reading that absence as lock-in flagged all five connectors in the KG as
unportable on the first run.

**D24 — The knowledge graph lives in Postgres. D1 is superseded, but not
reversed.** D1 rejected BigQuery and it was right to: 100 rows is file scale,
and the real damage was that it made the tool unable to run without network and
GCP credentials — including when demoing Azure architectures to Azure clients.
Every word of that still holds, and it is why the replacement is a local
Postgres over a DSN rather than a return to the warehouse. `docker compose up -d
db` plus a seed is the whole setup: no project, no credentials, no cloud client
in the dependency tree. Cloud SQL swaps in by changing `CAV_PG_DSN` and nothing
else, because nothing else knows where the database is.

What changed was not size but *access*. D1 reasoned about row count; the
pressure that actually arrived was concurrency and shape. Three agents now read
the graph and one writes to it (D25), which a file cannot arbitrate — the write
path was a read-modify-rewrite of a whole YAML document, which is a lost update
waiting for a second editor. And the queries the product wanted were always
`WHERE` clauses over typed fields (D22 said exactly this: "when the KG does
outgrow context, the answer is a query tool, not embeddings"). "Which Azure
databases are reachable only over a private IP" is one statement against a view
and was a scripted scan over a parsed file.

The migration is deliberately not a rewrite. `validate.py`, `translate.py`,
`verdict_card.py` and `check_kg.py` are untouched: `kg_pg.py` returns the same
`KnowledgeGraph` object `_load_local()` did, so the rule engine never learns
where its rows came from. This is what keeps invariant #1 intact through the
move — the engine still decides every verdict, in the same Python, and the
37/37 regression fixture passes against Postgres unchanged. Storage was
swapped; judgement was not touched.

Three things the migration had to get right, each of which would have failed
silently:

*Row order is a verdict input.* `validate.py` resolves a missing component with
`by_role(role, provider)[0]` — the first service holding the role, in authored
order. `ORDER BY id` would have quietly changed which connector gets inserted
into client architectures with every test still green. Hence `service.ord`.

*Absent is not NULL.* The YAML omitted optional fields rather than writing
`null`, and downstream code reads presence (`"gate" in layer`). SQL has only
NULL, so the loader drops None-valued optional keys on the way out — except
`severity`, which the YAML declares on every connectivity rule and explicitly
sets to `null` on six of them.

*The comments were the documentation.* This doc's own Style section says the KG
comments carry most of the reasoning behind the model. Migrating the data and
dropping the commentary would have left a future editor with `serverless_offvpc`
and nothing saying what it means, so the seed lifts both per-entry notes and each
file's header out of the raw text into `rationale` columns and `doc:*` rows.

The YAML files survive as `CAV_KG_BACKEND=local`. They are no longer
authoritative — they are the reference the migration is tested against, and a
backend that needs no database. `tests/unit/test_kg_postgres_parity.py` chains
the pure halves of the seed and the loader to prove the two produce an identical
graph, and it runs without Postgres; the SQL round trip is a second set of tests
that skip when no DSN answers. *D10's checkpoint format needs revisiting: a zip
of `references/kg/` no longer captures the state that matters.*

**D25 — Multi-agent, split by workflow, and the tool grouping is the actual
boundary.** One agent with thirteen flat tools became a coordinator with no
tools and three specialists: `validator_agent` (validate, translate, diagram),
`explorer_agent` (query the graph, health), `curator_agent` (the only writer).
The axis is D9's, and for D9's reasons — these are different jobs with different
risk profiles, two read-only and one gated. Splitting by validation layer was
considered and rejected: L1–L8 is a decision tree inside `validate.py`, and
giving a layer its own agent would put a model between rungs of it, which is
invariant #1 lost by architecture rather than by opinion.

What makes the split real is which tools each agent holds, not what each is
told. Every boundary here is also a sentence in a prompt, and a prompt can be
argued with — a model holding a write tool can be talked into writing. So the
two agents a rep talks to during a client call hold no writer, and the curator
holds no verdict tool: an agent that could both validate and add has an obvious
way out of an inconvenient `UNKNOWN_SERVICE`, which is adding the service.
`tests/unit/test_agent_boundaries.py` asserts these, because a boundary nobody
tests is a comment.

The coordinator holds zero tools on purpose. One that could answer directly
would stop transferring under any pressure at all.

**D26 — The judgment-field gate is now a CHECK constraint, and D6's asymmetry
is unchanged.** D6 observed that `check_kg.py` cannot catch a wrong
`reachability` because it verifies structural consistency, not semantic truth.
That is still true, and the human gate is still the only thing standing between
a wrong value and roughly twenty confidently-wrong verdicts.

What the database adds is a floor. `network_placement`, `reachability`, `tier`
and `region_scope` are constrained to closed sets at the storage layer, which no
caller can route around. This caught a live bug in the old write path the moment
it was exercised: it took `network_placement` as free text and stored `.split()`
of it — a list where the schema wants a scalar — and never checked
`reachability` against the four legal values at all. Both produced a node that
read as present and valid. `check_kg.py` reported clean, exactly as D6 predicted.

D21's provenance gate is now a constraint too: `prov_status = 'verified'`
requires a `prov_verified` date, so an entry cannot claim a review without
saying when. The curator writes `unverified` and the health check holds open
until a human flips it — `mark_service_verified` requires the caller to supply
the date rather than defaulting to today, because a date the tool invented would
assert a review that did not happen.

**D27 — One graph, in Postgres. The YAML is generated output and the skill
directories are gone.** D24 moved the graph into Postgres and left four copies
of the YAML behind: the agent's vendored set, the retired
`create-architect/references/kg/`, and an installed copy under
`.claude/skills/`. That was supposed to be temporary and instead became the
system's main structural risk.

The `.claude/skills/` copy is why this is a decision and not a cleanup. It was
committed, it was invocable, and its graph predated two decisions: **0 of 45
services carried a provenance block** (D21) and **the L0–L8 ladder was absent
entirely**, along with both PORT rules (D23). Anything invoking that skill got
connectivity answers with no architecture layer behind them and no sign-off
gate, while the database three directories away had both. Two consumers, one
product, different answers, and nothing anywhere reporting the divergence —
`check_kg` cannot see a copy it does not read.

All five skill directories are deleted (56 files). Nothing in the agent
imported them.

What stays is one YAML set under `app/references/kg/`, and it is now generated
by `db/export_to_yaml.py` rather than authored. The direction of the arrow is
the whole change: Postgres is written, YAML is produced from it. Before, the
same files were simultaneously the seed input, the offline fallback, and the
list of valid rule ids `verdict_grounding` checks a response against — three
jobs, no owner, and a silent failure in each. Seed from a stale file and get an
old graph. Run `CAV_KG_BACKEND=local` and get different verdicts than
production. Add a rule in SQL and watch the metric score its id as fabricated.

Deleting the YAML outright was the other option and was rejected for what it
would have cost: a database is a poor review surface. You cannot see a proposed
change to a connectivity rule in a pull request, cannot diff last month's graph
against today's, and `docker volume rm` takes the whole thing. Those were
properties of the graph being a file, and D24 gave them up without noticing.
Generated-and-checked gets them back without reintroducing a second source.

`tests/unit/test_kg_export_drift.py` is what makes the arrow real rather than a
convention: it fails when the committed files disagree with the database, and
`--check` prints the offending lines. The round-trip half runs without Postgres
— export and re-import produce an identical graph, verified including the two
orderings that decide verdicts (`service.ord`, `connectivity_rule.seq`) — and
the 37/37 regression passes through the export unchanged.

*Rejected: Apache AGE.* A graph extension sounds like the natural fit for a
knowledge graph and is the wrong tool for this one. D2 is the reason: validity
here is **derived from node properties at query time**, not stored. The 691
edges `export_kg_graph` returns are computed by running the rule engine over
every pair — they are output, not data. Persisting them as AGE vertices and
edges is D2 reversed, and D21 already rejected the same store-nodes-and-edges
model when it came up as Graphify/OKF. The edges that genuinely are stored —
equivalences, aliases, alternatives — number about 30 against 45 nodes, are all
one hop, and are already single joins. There is no traversal question the
product asks that Cypher would answer better than the `WHERE` clause it is
today. The cost is not theoretical either: **Cloud SQL does not allow-list
AGE**, so adopting it would break D24's "Cloud SQL swaps in by changing
`CAV_PG_DSN` and nothing else" and put self-managed Postgres on the critical
path. *Reconsider if the graph ever stores multi-hop relationships it needs to
traverse — dependency chains, blast radius, migration paths — which would be a
real change in what the graph is for, not a change in how it is queried.*

**D28 — Numbered migrations, a capped graph export, and the Gap Report in the
database.** Three consequences of D24 that the migration itself did not carry,
found by assessing the data layer rather than by anything breaking.

*Schema changes have a path.* `schema.sql` was `CREATE TABLE IF NOT EXISTS`
throughout, which works exactly once — re-running it against a populated
database is a no-op, so the second change had nowhere to go but a hand-typed
`ALTER` against live data with nothing recording it. It is now
`db/migrations/0001_initial_schema.sql`, applied by `db/migrate.py` and recorded
in `kg.schema_migration`. Plain SQL and a small runner; Alembic is more
machinery than thirteen tables justify. Three properties earn their keep: each
migration runs in its own transaction (Postgres has transactional DDL, so a
failure leaves nothing behind — verified when 0003 failed on a bad `unnest` and
rolled back clean), applied files are checksummed so editing one that already
ran is refused rather than silently diverging, and a fresh database is not
special-cased — seeding runs the same migrations production does.

*`export_kg_graph` no longer returns 190 KB by default.* Its 691 edges are
derived, not stored — every same-provider pair the engine allows — so they are
output rather than data, and putting them in a context window answers no
question the counts and a per-node degree do not answer better. Default is now
a 12.6 KB summary; `include_edges=True` returns the full adjacency for the case
where the adjacency is the answer.

*The Gap Report is a table.* Every `UNCOVERED` verdict and unknown service logs
a record, and that list is the only data here that cannot be regenerated — it is
what real users actually asked. It was appending to a gitignored JSONL file
inside the container, which made it the least durable thing in the system. It
now writes to `kg.gap_record`, with `gap_summary` grouping repeats, because the
question it exists to answer ("what should the graph cover next") is a join
against the graph and was a hand-written script over a file.

The engine did not learn about the database to make that work. `log_gap_records`
takes a `sink`, defaulting to the file; `tools.py` injects a Postgres one and
falls back to the file when the database is unreachable, because a gap is logged
while a user waits on a verdict and storage being down is not their problem.

One bug worth recording, because the fix is the general rule: 0002 resolved
which service was missing by matching the element text against known ids in SQL.
On `cloud-run -> cloud-composer` that finds `cloud-run` — the half that exists —
and reported the gap as being about a known service, inverting the triage it
existed to support. 0003 replaced it with `missing_services`, supplied by the
caller, which resolved every id against the loaded graph while producing the
verdict. The database should not be asked to re-derive something the caller
already knew.

## Open questions

Genuinely unresolved. Do not present any of these as settled.

- **`emit_drawio.py --embed-icons` is broken** (backlog, not investigated).
  Plain output (no icon embedding) works as intended. `--embed-icons` base64s
  SVGs found via `kg.icon_for()` into the output — something in that path
  fails; not yet diagnosed which part (icon resolution, path lookup, or the
  base64/XML embedding itself).
- **`cloud-architecture-validator-init`'s literal source URL is still
  unpicked.** D19 fixed the shape (a public GCS object link or GitHub
  Release asset link, plain HTTPS `GET`, no SDK) — which specific URL,
  serving what schema, is not decided.

## Style

Explain why a constraint exists rather than asserting it. The KG comments carry
most of the reasoning behind the model; keep them when editing, and prefer
YAML over JSON for that reason.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/006-agents-cli-eval-metrics/plan.md
<!-- SPECKIT END -->
