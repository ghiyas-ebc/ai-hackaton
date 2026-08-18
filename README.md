# Cloud Architecture Validator

A multi-agent [ADK](https://adk.dev/) application that validates and translates cloud
architectures (GCP and Azure) for presales and sales engineers — people who do not design
cloud architecture for a living, producing material that goes in front of a client's
architect.

Verdicts come from a deterministic rule engine over a knowledge graph, never from an LLM
judging validity. The model's job is to parse a described architecture, call the right
tools, and communicate the result — not to decide whether a connection is safe.

## Repository layout

```
.
├── CLAUDE.md                        # Full orientation + decision log for this repo — read first
├── cloud-arch-validator-agent/      # The product: the ADK agent, its knowledge graph, and its tests
├── specs/                           # Spec Kit feature specs (001–006), one per shipped feature
├── project_evaluation.md            # Point-in-time gap analysis against the spec backlog
├── Technical_Sales_Precision.pdf    # Reference deck (Technical Co-Pilot source material)
├── .claude/                         # Claude Code skills/config installed for this repo
├── .agents/                         # agents-cli skill cache
└── .specify/                        # Spec Kit tooling (templates, scripts, workflows)
```

`cloud-arch-validator-agent/` is where the actual work happens. Its own
[README](cloud-arch-validator-agent/README.md) covers the `agents-cli` scaffold, local dev
server, deployment, and evaluation workflow in detail. `CLAUDE.md` at the repo root is the
canonical orientation doc — read it before touching anything under
`cloud-arch-validator-agent/db/` or `cloud-arch-validator-agent/app/kg_lib/`, since it
carries the reasoning (30 decisions and counting) behind choices that look questionable
without context.

## Architecture

A coordinator with no tools routes requests to three specialists, split by workflow and by
risk (D25):

- **`validator_agent`** — validates a described architecture and translates it between
  providers. Read-only. The common case.
- **`explorer_agent`** — answers questions about the graph itself: which services exist,
  filtering by typed fields, graph health and rule coverage. Read-only.
- **`curator_agent`** — the only writer. Adds a service or records human verification,
  gated on an engineer supplying the judgment fields a schema lookup can't answer
  (`network_placement`, `reachability`, `roles`).

The knowledge graph lives in Postgres (~100 services, GCP + Azure), reached over a plain
DSN — no cloud SDK and no provider credentials needed to run the tool, so demoing an Azure
architecture never requires a GCP login. Validity is *derived* from node properties at
query time via an L1–L8 rule ladder (`connectivity-rules.yaml` / `architecture-rules.yaml`),
not enumerated as a list of valid pairs — `UNCOVERED` and `UNKNOWN_SERVICE` are correct
answers the system is allowed to give rather than guess around.

## Quick start

All commands below run from `cloud-arch-validator-agent/`.

```bash
docker compose up -d db                  # local Postgres, the graph's home
uv run python db/migrate.py              # apply pending schema migrations
uv run python db/seed_from_yaml.py       # rebuild a database from the export

agents-cli playground                    # launch the agent locally with auto-reload
```

## Tests and gates

```bash
uv run pytest tests/unit tests/integration
uv run ruff check app tests db
```

The graph's own gate is `check_kg_health`: clean integrity, a clean role catalog, 37/37
regression, and L1 coverage ≥ 80% before anything ships. Tests that need Postgres skip
cleanly when `CAV_PG_DSN` isn't set, so the suite stays green with no database running.

## Further reading

- [`CLAUDE.md`](CLAUDE.md) — invariants, full decision log, open questions
- [`cloud-arch-validator-agent/README.md`](cloud-arch-validator-agent/README.md) — scaffold,
  deployment, and evaluation workflow
- [`specs/`](specs/) — per-feature specs, plans, and task breakdowns (Spec Kit)
- [`project_evaluation.md`](project_evaluation.md) — a point-in-time gap analysis; check it
  against `CLAUDE.md`'s decision log before trusting it, since the graph has moved since it
  was written
