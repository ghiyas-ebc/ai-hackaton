# Cloud Architecture Validator — Project Evaluation

## What this project is

A four-skill Claude agent system (GCP + Azure) that validates cloud architectures for
presales/sales engineers — without using an LLM to judge validity. Verdicts come from a local
YAML knowledge graph + rule engine. The deployed surface is an ADK agent
(`cloud-arch-validator-agent`) that wraps the skills as tools.

---

## Summary of completion status

| Feature / Spec | Tasks all ✅? | Actually wired into agent? | Notes |
|---|---|---|---|
| **001 – Verdict Card** | ✅ All 41 tasks done | ✅ `generate_verdict_card` in `tools.py` | MVP and all 4 user stories shipped |
| **002 – Add-Service Skill** | ✅ All 28 tasks done | ❌ Stub only in agent (`add_service_to_kg` returns error) | Scripts exist in `-add/scripts/` but not integrated |
| **003 – Equivalence Detection** | ✅ All 22 tasks done | ❌ Likewise — `equivalence.py` exists but not surfaced | Only recommendation output, never wired to agent |
| **`-init` skill** | N/A — design stub, intentionally unbuilt | ❌ Stub only | Source URL still unpicked (open question in CLAUDE.md) |

---

## Gap 1 — `add_service_to_kg` is still a stub (Critical)

> **File**: [`tools.py:288-325`](file:///Users/ghiyas/Projects/EBCO/ai-hackaton/cloud-arch-validator-agent/app/tools.py#L288-L325)

The agent's `add_service_to_kg` tool returns a hard-coded error message:
> *"cloud-architecture-validator-add is a design stub, not a working tool."*

But `cloud-architecture-validator-add/scripts/add_service.py` **is now a complete implementation**
(specs/002 is done). The gap is that `tools.py` was never updated to call the real script instead
of returning the stub string.

**To close**: Wire `tools.py::add_service_to_kg` to invoke or import `add_service.py`'s flow, or
expose a subprocess/function call path. Since `add_service.py` is interactive (reads stdin), a
more practical agent integration would be to expose the _non-interactive_ write path as a tool
function that accepts all required fields directly, bypassing the CLI prompts.

---

## Gap 2 — Equivalence detection not surfaced to the agent (Moderate)

> **File**: [`tools.py`](file:///Users/ghiyas/Projects/EBCO/ai-hackaton/cloud-arch-validator-agent/app/tools.py)

`cloud-architecture-validator-add/scripts/equivalence.py` is built and tested (spec 003 done),
but there is no tool in `tools.py` that exposes it. The agent cannot suggest cross-cloud
equivalences during a conversation.

**To close**: Add a `propose_equivalence(service_name, provider_from)` tool function wrapping
`equivalence.propose_equivalence()`. This is lower priority than Gap 1 (it's
a recommendation, not a write path), but it's a completed piece of work going unused.

---

## Gap 3 — Evals have not been run against a live Claude instance (High risk)

> **File**: [`evals.json`](file:///Users/ghiyas/Projects/EBCO/ai-hackaton/cloud-arch-validator-agent/app/evals/evals.json)

CLAUDE.md D15 explicitly flags this:
> *"Evals must run against a live Claude instance before real client use, particularly E02/E03/E06.
> Until `evals/evals.json` has actually been run against a Claude instance with the skill loaded,
> 'the model never guesses' is an unverified claim."*

The eval scaffolding exists (`eval_config.yaml`, `response_quality.py`, `verdict-card-dataset.json`)
but the 9-case eval suite in `evals.json` is in the _skill_ directory format (not the ADK eval
runner format), so it cannot be run with `agents-cli eval` as-is without conversion.

The two verdict-card cases in `tests/eval/datasets/verdict-card-dataset.json` (E08, E09) are the
only ones in the ADK runner format — but they have no `reference` expected answers, so the
LLM-as-judge can only give a generic quality score, not assert specific behavior.

**To close**:
1. Convert E01–E09 from `evals.json` into the ADK eval runner dataset format.
2. Add `reference` answers (or structured `assertion` fields) for the critical behavioral evals
   (E02 – holds back on Pub/Sub choice, E03 – doesn't infer unknown service, E06 – asks for provider).
3. Run `agents-cli eval generate --dataset verdict-card-dataset.json` to capture live agent traces,
   then `agents-cli eval grade` to score them.

---

## Gap 4 — `emit_drawio.py --embed-icons` is known broken (Low / Backlog)

> **File**: [`tools.py:250`](file:///Users/ghiyas/Projects/EBCO/ai-hackaton/cloud-arch-validator-agent/app/tools.py#L250)

The tool already documents this and disables icon embedding. The open question is just diagnosis —
is it the icon path lookup, or the base64/XML embedding step? Not blocking anything functional.

---

## Gap 5 — `basic-dataset.json` is a generic scaffold placeholder (Minor)

> **File**: [`basic-dataset.json`](file:///Users/ghiyas/Projects/EBCO/ai-hackaton/cloud-arch-validator-agent/tests/eval/datasets/basic-dataset.json)

Contains greeting/weather/Paris questions — scaffold defaults that were never replaced with
domain-specific cases. This doesn't break anything but it means `agents-cli eval` on this dataset
tells you nothing about architecture validation.

**To close**: Replace with 2–3 real validation scenarios (e.g., the same ones from `evals.json` E01, E05).

---

## Gap 6 — `pyproject.toml` metadata not filled in (Cosmetic)

> **File**: [`pyproject.toml:5-7`](file:///Users/ghiyas/Projects/EBCO/ai-hackaton/cloud-arch-validator-agent/pyproject.toml#L5-L7)

`authors` still says `"Your Name" / "your@email.com"`. Harmless for a hackathon; noticeable if
demoing or publishing.

---

## Gap 7 — `add_service.py` integration path is architectural (Needs design decision)

`add_service.py` is a terminal-interactive CLI (reads stdin for judgment questions). This works as
a standalone authoring tool but cannot be called directly from an ADK agent mid-conversation —
the agent can't inject stdin answers.

Two options:
- **Option A** — Agent orchestrates it externally: the agent tells the user *what to run* and the
  user runs the CLI themselves, then comes back to report the result. The current stub message
  already says this implicitly.
- **Option B** — Extract a non-interactive function from `add_service.py` that accepts all fields
  as parameters, and expose that as an agent tool. The human-gate discipline is preserved: the
  agent would need to collect all judgment fields from the user during conversation before calling
  the write function.

Option B would properly close Gap 1 and make `add_service_to_kg` a real tool. Option A is what
the agent currently does (minus the guidance being accurate — it still says the tool isn't built,
which is now wrong).

---

## Prioritized action list

| Priority | Gap | Effort |
|---|---|---|
| 🔴 **P1** | Update `add_service_to_kg` stub message to reflect that the CLI is built and instruct users how to run it directly (stop lying about it being unimplemented) | ~5 min |
| 🔴 **P1** | Decide and document Gap 7 (Option A vs B) and either update the tool message or start Option B wiring | 1–4 h |
| 🟠 **P2** | Convert `evals.json` E01–E09 to ADK runner format + add reference answers | 2–3 h |
| 🟠 **P2** | Run evals live against the agent and fix behavioral regressions | depends |
| 🟡 **P3** | Add `propose_equivalence` tool (Gap 2) | 1 h |
| 🟡 **P3** | Replace `basic-dataset.json` placeholder cases (Gap 5) | 30 min |
| ⚪ **Backlog** | Diagnose `--embed-icons` (Gap 4) | unknown |
| ⚪ **Backlog** | Fill `pyproject.toml` author metadata (Gap 6) | 2 min |

---

## What's genuinely solid

- **Rule engine and KG** — `validate.py`, `kg.py`, `connectivity-rules.yaml`, `architecture-rules.yaml`
  are complete, tested (37/37 regression), and coverage-gated (≥80% L1).
- **Verdict Card** (spec 001) — All 4 user stories done, tiered findings, mismatch detection,
  engineer checklist, and Gap Report logging all wired end-to-end.
- **Add-service CLI** (spec 002) — All 7 phases complete. Fetch/propose, human gate, judgment
  questions, YAML round-trip, provenance, update path, and equivalence detection (spec 003) all built
  and tested in isolation.
- **Agent instruction** — Well-disciplined: tool-first, no soft-pedalling of UNCOVERED, language
  matching the user.
- **ADK scaffolding** — Properly structured with `agents-cli`, has FastAPI backend, A2A support,
  observability hooks, and a functioning eval runner config.
