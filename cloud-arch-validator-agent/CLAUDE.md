# Coding Agent Guide

## What this project is

An ADK agent front-end for the four `cloud-architecture-validator-*` skills in
the parent repository. It exposes their scripts as ten tools and lets a
salesperson or presales engineer describe an architecture in prose instead of
assembling a `--edges "a>b,b>c"` string by hand.

`generate_verdict_card` (in `app/kg_lib/verdict_card.py`) is the primary tool
for a live sales conversation: it wraps `validate_architecture`'s output into
a Verdict Card — one difficulty label, every finding tagged with an evidence
tier (`Proven` / `Theoretically Possible` / `Requires Deep Review`), optional
tech-mismatch detection, an engineer checklist, and automatic Gap Report
logging to `app/references/gap_report.jsonl` for anything uncovered. See
`specs/001-verdict-card/` in the parent repo for the full design. Like
everything else here, it is a pure transformation over the rule engine's
output — no tier, score, or checklist item is decided by the model.

**The rule engine decides, the model does not.** That is the parent repo's root
invariant #1 and it survives intact here: `app/tools.py` calls `validate.py` and
returns what it returns. The model's job is parsing prose into service ids and
explaining findings. If you find yourself adding a code path where the model
decides whether a connection is valid, stop — that defeats the product.

`UNCOVERED` and `UNKNOWN_SERVICE` are correct answers, not bugs to route around.

### Vendored knowledge graph

| Path | Origin |
|------|--------|
| `app/kg_lib/` | `create-architect/scripts/` + the three sibling skills' scripts |
| `app/references/` | `create-architect/references/` |
| `app/evals/` | `create-architect/evals/` |

Copied verbatim so the agent is self-contained and deployable in a container.
One edit was needed: `export_kg_graph.py` no longer resolves a cross-skill
sibling path. **Do not reformat anything under `app/kg_lib/` or `app/evals/`** —
they are excluded from ruff precisely so a diff against the skills shows real
drift rather than style noise. Fix bugs in the skills first, then re-copy.

The vendored layout mirrors the skill's own, which is why `kg.py` (`KG_DIR =
../references/kg`) and `check_kg.py` (`../evals`) needed no changes.

Those scripts import each other by bare name (`import kg`). `app/tools.py` puts
`app/kg_lib/` on `sys.path` with a plain statement before importing them —
deliberately not `from . import kg_lib`, which isort would hoist above the
imports it enables, failing only at runtime.

### Two tools are not implemented

`add_service_to_kg` and `init_kg_from_catalog` return `{'implemented': False}`
with an explanation. The underlying skills are design stubs: `-add` still needs
the human gate over `network_placement` / `reachability` / `roles` (a wrong
`reachability` fails silently across ~20 pairs and `check_kg.py` reports clean),
and `-init` has no source URL chosen. Building either means resolving that in
the parent repo first.

### Checks

```bash
uv run pytest tests/unit tests/integration   # unit tests cover all 10 tools
uv run ruff check app tests
```

`tests/unit/test_tools.py` asserts on rule-engine output, which is deterministic
and therefore belongs in pytest rather than eval. It includes the KG's own gate:
clean integrity and 37/37 regression.

Load `.env` before running anything (`set -a; . ./.env; set +a`) — without it
the model client fails with "No API key was provided."

---

## Prerequisites

Install the CLI (one-time):
```bash
uv tool install google-agents-cli
```

---

## Development Phases

### Phase 1: Understand Requirements
Before writing any code, understand the project's requirements, constraints, and success criteria.

### Phase 2: Build and Implement
Implement agent logic in `app/`. Use `agents-cli playground` for interactive testing. Iterate based on user feedback.

### Phase 3: The Evaluation Loop (Main Iteration Phase)
Start with 1-2 eval cases, run `agents-cli eval generate`, then `agents-cli eval grade`, iterate by making changes and rerunning both commands until satisfied. Expect 5-10+ iterations. Once you have a baseline, reach for `agents-cli eval compare` (regression diffs), `agents-cli eval analyze` (cluster failure modes), and `agents-cli eval optimize` (auto-tune prompts). See the **Evaluation Guide** for metrics, dataset schema, LLM-as-judge config, and common gotchas.

### Phase 4: Pre-Deployment Tests
Run `uv run pytest tests/unit tests/integration`. Fix issues until all tests pass.

### Phase 5: Deploy to Dev
**Requires explicit human approval.** Run `agents-cli deploy` only after user confirms. See the **Deployment Guide** for details.

### Phase 6: Production Deployment
Ask the user: Option A (simple single-project) or Option B (full CI/CD pipeline with `agents-cli infra cicd`).

## Development Commands

| Command | Purpose |
|---------|---------|
| `agents-cli playground` | Interactive local testing |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests |
| `agents-cli eval dataset synthesize` | Synthesize multi-turn eval scenarios for your agent |
| `agents-cli eval generate` | Run agent on eval dataset, produce traces |
| `agents-cli eval grade` | Run agent evaluations on the traces |
| `agents-cli eval compare` | Compare two grade-results files (regression check) |
| `agents-cli eval analyze` | Cluster failure modes from grade results |
| `agents-cli eval metric list` | List built-in metrics available in the SDK |
| `agents-cli eval optimize` | Auto-tune agent prompts using eval data |
| `agents-cli lint` | Check code quality |
| `agents-cli infra single-project` | Set up project infrastructure (Terraform) |
| `agents-cli deploy` | Deploy to dev |
| `agents-cli scaffold enhance` | Add deployment target or CI/CD to project |
| `agents-cli scaffold upgrade` | Upgrade project to latest version |

---

## Operational Guidelines for Coding Agents

- **Code preservation**: Only modify code directly targeted by the user's request. Preserve all surrounding code, config values (e.g., `model`), comments, and formatting.
- **NEVER change the model** unless explicitly asked.
- **Model 404 errors**: Fix `GOOGLE_CLOUD_LOCATION` (e.g., `global` instead of `us-central1`), not the model name.
- **ADK tool imports**: Import the tool instance, not the module: `from google.adk.tools.load_web_page import load_web_page`
- **Run Python with `uv`**: `uv run python script.py`. Run `agents-cli install` first.
- **Stop on repeated errors**: If the same error appears 3+ times, fix the root cause instead of retrying.
- **Terraform conflicts** (Error 409): Use `terraform import` instead of retrying creation.
