# Implementation Plan: Agent CLI Evaluation Metrics Conversion

**Branch**: `006-agents-cli-eval-metrics` | **Date**: 2026-08-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-agents-cli-eval-metrics/spec.md`

## Summary

Convert nine architecture-validator evaluation cases from `app/evals/evals.json` into Agent CLI EvaluationDataset records. Preserve IDs and Indonesian prompts, encode every source assertion as a case-specific rubric, cover tool and response behavior with configured metrics, and add migration validation so omissions, prompt drift, and unsupported multi-turn expectations fail visibly. Keep deterministic validation code outside evaluation-judge decision paths.

## Technical Context

**Language/Version**: Python 3.11–3.13, JSON, YAML

**Primary Dependencies**: `agents-cli` 1.1.x workflow, existing Google ADK project, PyYAML, pytest

**Storage**: Versioned JSON datasets, YAML evaluation config, generated trace/grade artifact directories

**Testing**: pytest for local conversion/schema checks; `agents-cli eval generate`, `grade`, `compare`, and `analyze` for end-to-end evaluation

**Target Platform**: Local Agent CLI execution with optional managed grading services

**Project Type**: Agent evaluation dataset/configuration and validation tooling

**Performance Goals**: Dataset validation completes locally in under 5 seconds; evaluation runtime remains governed by Agent CLI and judge service

**Constraints**: No production runtime changes; no credentials committed; no fabricated golden responses; missing traces and judge errors cannot pass; source prompts and IDs stay stable

**Scale/Scope**: 9 source cases, 34 source assertions, one consolidated target dataset, case-specific rubric coverage, existing agent project only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Verdict-Not-Guess**: PASS. Rubrics evaluate observed agent adherence to deterministic tool output; they do not decide architecture validity.
- **II. Evidence-Grounded History**: PASS. Rubrics require trace evidence and do not invent reference answers or historical facts.
- **III. Human Gate on Judgment Calls**: PASS. Evaluation reports behavior; it does not promote judge output into final organizational knowledge or judgment fields.
- **IV. Read-Only by Default, Explicit Write Path**: PASS. Generation/grading read agent behavior; E09 may verify existing Gap Report behavior but conversion adds no automatic knowledge write.
- **V. Layered Transparency**: PASS. Per-case rubric outcomes remain visible beside broad metrics; aggregate score is supplementary.

No gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/006-agents-cli-eval-metrics/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── evaluation-contract.md
└── tasks.md                    # /speckit-tasks output
```

### Source Code (repository root)

```text
cloud-arch-validator-agent/
├── app/evals/evals.json                    # source cases, migration reference
├── tests/eval/datasets/
│   ├── <converted-dataset>.json            # Agent CLI target dataset
│   └── README.md                           # workflow documentation
├── tests/eval/eval_config.yaml             # selected metrics
├── tests/eval/metrics/ or response_quality.py # case-rubric/custom metric support
├── tests/unit/                             # dataset conversion/schema tests
└── artifacts/
    ├── traces/                             # generated, ignored execution traces
    └── grades/                             # generated, ignored grade results
```

**Structure Decision**: Keep source cases under `app/evals`, target evaluation inputs under existing `tests/eval`, and generated outputs under existing `artifacts`. Add only migration-specific validation/metric support near existing evaluation tests; no production agent modules change.

## Phase 0: Research Complete

- Confirmed Agent CLI dataset supports `eval_cases`, exact prompt content, and per-case `rubric_groups`.
- Confirmed rubric metric can reference `source_assertions` group.
- Confirmed broad metrics supplement, not replace, case-specific criteria.
- Resolved E02 follow-up requirement by preserving it as explicit multi-turn/unverified condition.
- Documented decisions in [research.md](research.md).

## Phase 1: Design Complete

- Defined source, target, rubric, trace, and grade entities in [data-model.md](data-model.md).
- Defined dataset, metric, command, and compatibility contract in [contracts/evaluation-contract.md](contracts/evaluation-contract.md).
- Defined runnable validation workflow in [quickstart.md](quickstart.md).
- Agent context points to this plan.

## Phase 2: Implementation Outline

1. Build target dataset from source cases without changing IDs/prompts.
2. Encode all source assertions as stable rubric IDs and descriptions; identify E02 continuation condition.
3. Add local migration validation for count, uniqueness, exact prompts, assertion coverage, and rubric metric linkage.
4. Update eval configuration and README commands for selected metrics and artifact paths.
5. Run local validation and existing unit/integration tests.
6. Run Agent CLI generation and grading when credentials/services available; inspect every case and compare baseline.

## Post-Design Constitution Re-check

All five principles remain PASS. Design keeps verdict authority in deterministic tools, requires trace-backed evidence, exposes uncertainty and failures per case, introduces no implicit knowledge-base write, and separates detailed rubric outcomes from aggregate scores.

## Complexity Tracking

No constitution violations or complexity exceptions.

## Addendum — 2026-08-15 dataset enhancement

Not a new spec-kit cycle — content/config work, not an architectural decision
on the scale of the parent repo's `CLAUDE.md` D1-D30 log. Recorded here rather
than editing `spec.md`'s historical record of the original 9-case migration.

**Trigger.** A full `agents-cli eval generate`/`grade` run against a live agent
(run `20260815-221126`, the then-10 cases) surfaced two problems a rerun alone
would not fix:

1. Three cases (`E02`, `E02b`, `E07`) hard-errored on `instruction_following_v1`
   with a Vertex `400: Rubric results could not be reliably computed` —
   confirmed deterministic by regrading the same traces twice.
2. Two cases (`E01`, `E05`) returned `verdict: null` (not true/false) on some
   rubrics. Reading the judge's reasoning showed assertions asking about a
   *trace fact* (which tool ran, what args it got) that a judge grading only
   final response text structurally cannot answer.

Triage of the traces behind (2) found two real product defects in `app/`, not
dataset problems, both fixed in this pass — both discovered by reading traces,
neither by inspection of the code in the abstract:

- **`generate_verdict_card`/`validate_architecture`'s `data_residency`
  docstring** (`app/tools.py`) told the model to pass `'indonesia'` as an
  example value; the rule engine's actual gate
  (`GOV-001-DATA-RESIDENCY.applies_when.data_residency`) only matches `'id'`.
  The E05 trace showed the model following the docstring's own example
  verbatim, silently dropping a bank-client compliance finding. Fixed:
  docstrings on both tools now say `'id'`/`'eu'`/`'us'`/`'none'` and name the
  failure mode explicitly.
- **`translate_architecture` never exposed `translate.py`'s own `choices`
  parameter.** `translate.py`'s header comment documents its own design in
  four steps, the third of which is "if a node has several equivalents, STOP
  and ask for a decision — do not pick one," and the underlying `translate()`
  function has always accepted a `choices` dict to apply exactly such a
  decision on a follow-up call (the CLI exposes it as `--choose
  'src=tgt,...'`). The ADK-facing wrapper in `app/tools.py` never forwarded
  it — so once the model asked the user and the user answered, there was no
  parameter to hand the answer back through, and the tool would report the
  same pending decision forever regardless of what the user said. The `E02b`
  trace under the *original* (pre-fix) assertions showed exactly this: the
  user explicitly restated their choice, and the model re-asked. Fixed:
  `translate_architecture` now takes `choices: str = ""` (`'source_id=
  target_id,...'`, matching the CLI's own syntax), parses and forwards it.
  Verified live (see below): the model correctly maps the user's own words
  ("Service Bus", "global L7") to the right target ids on the first try,
  translation completes, and both choices are honoured in the response.
- **Service-name-to-id resolution**, found in the same E02 trace: the model
  invented plausible-looking ids (`cloud-pubsub`, `cloud-load-balancer`)
  instead of the graph's real ones (`pubsub`, `cloud-load-balancing`). Because
  `E02`'s original prompt gave no edges at all, the model also had to guess a
  topology in the same turn, compounding the failure mode being tested with
  an unrelated one. **Not fixed in `app/` this pass** — `E02`'s prompt now
  states edges explicitly (still using display names, not ids, so the
  resolution question stays live) and carries its own assertion for it,
  rather than working around it, so a future run either closes the gap or
  documents it failing honestly.

**Dataset changes** (`app/evals/evals.json`, 10 cases → 14):

- `E01`, `E02`, `E07` assertions reworded/split: text-verifiable claims instead
  of trace-only ones (mirrors why `verdict_grounding.py` exists), compound
  multi-clause assertions split into atomic ones.
- `E02b-cross-cloud-choices` converted from a restated Shape-A prompt to a
  genuine Shape-B continuation (`prior_turns` in the source →
  `agent_data.turns` in the target) of E02's own conversation, per the
  README's own documented Shape-A/B distinction, which the dataset had never
  actually used.
- `E10`-`E13` added to close a coverage gap: `curator_agent`'s entire write
  path (`add_service_to_kg` happy path, `unknown_role` typo refusal,
  `role_warning` on a descriptive-only role) and `explorer_agent`'s typed query
  tools (`search_services`, `query_services`, `check_kg_health`) had zero eval
  cases despite the curator being the system's one human-gated write boundary
  (D26/D29 in the parent `CLAUDE.md`).

**Structural changes:** `tests/eval/convert_dataset.py` and
`tests/eval/validate_dataset.py` now branch on a source case carrying
`prior_turns` to emit/validate Shape B; unaffected for the 13 Shape-A cases.
New deterministic custom metric `tests/eval/kg_write_grounding.py` (registered
in `eval_config.yaml`) applies `verdict_grounding.py`'s reasoning to the
curator's write boundary — a write/refusal/warning claim must be backed by the
matching `add_service_to_kg`/`query_services`/`search_services` trace
response, not graded by a text-only judge.

**Operational note:** `E10`-`E12` call `add_service_to_kg` for real against
whatever Postgres `CAV_PG_DSN` points at. The first run after a fresh seed
exercises the write path; every run after that hits `already_exists` instead.
Assertions and `kg_write_grounding` both treat that as a legitimate non-failure
outcome — see `tests/eval/datasets/README.md`. Each live verification run in
this pass wrote real rows (`Cloud Filestore`, `Persistent Disk`, `Cloud CDN`),
which drifted the database from the committed YAML export and broke
`test_kg_export_drift.py` and one `test_role_catalog.py` assertion that
assumed a clean seed — both false alarms about test correctness, not about the
change; `db/seed_from_yaml.py --replace` after each run restored a clean
database and a green suite.

**Both new/existing deterministic metrics had false-positive bugs, found only
by running them against real, varied model output — not by inspection:**

- `verdict_grounding.py`'s `RULE_ID_RE` (pre-existing, not new this pass)
  flagged `YYYY-MM-DD` (a date-format placeholder in an E11 response) and
  `L2-L8` (E13's own layer-range shorthand, the same idiom this document's
  D23 uses) as fabricated rule ids. Fixed: a candidate must contain a digit
  (excludes all-letter placeholders) and an explicit `L\d-L\d` exclusion
  (a layer range is prose, not a single id).
- `kg_write_grounding.py`'s first version matched fixed phrases
  (`"tidak dikenal"`, `"role_warning"`, ...). Real responses broke this both
  ways: E01/E03/E08 (plain validator cases, nothing to do with the curator)
  were flagged because `"tidak dikenal"` is also how `UNKNOWN_SERVICE` is
  worded generically; separately, E12's actual role-warning sentence matched
  *no* marker at all ("peringatan peran (*role warning*)"), so the check
  silently never ran — a false negative that happened to still score 1.0.
  Fixed: replaced fixed phrases with a co-occurrence gate — a role-context
  word (`"role"`/`"peran"`) must appear *and* a looser refusal/warning word
  must appear, rather than one exact phrase. The role-context word is what
  actually protects against the E01/E03/E08 class (their responses never say
  "role"/"peran" at all), which is why it can afford to be loose on the
  second half.

**A third-party tool limitation, not fixed (out of this repo):** the
installed `agents-cli` (v1.1.0) `eval generate`'s own `_inference_runner.py`
crashes (`AttributeError: 'str' object has no attribute 'get'`) specifically
on the one Shape-B case (`E02b`), in `_extract_new_events_from_partial`,
outside the script's own error handling — it aborts the whole run, not just
that case. Confirmed this is the CLI wrapper and not the dataset or the SDK:
driving `vertexai.Client(...).evals.run_inference` directly against the same
`E02b` case (bypassing the CLI's subprocess script) succeeds and returns a
well-formed multi-turn result — which is also how the `translate_architecture`
`choices` fix above was verified end-to-end. Live verification runs in this
pass therefore used a 13-case dataset excluding `E02b` for anything going
through the real CLI, plus one direct-SDK run for `E02b` itself.

**Final verification (2026-08-15):** three live `generate`+`grade` passes
against the fixed dataset/metrics. `verdict_grounding` and `kg_write_grounding`
scored a clean 1.0 across every case in the final pass — a real result against
fresh, varied model output, not a rerun of cached data. `instruction_following_v1`
still errors on a small, non-overlapping set of cases run to run (3 different
cases each time) with the same `400: Rubric results could not be reliably
computed` — confirmed non-deterministic (unlike the original `E02`/`E02b`/`E07`
trio, which reproduced identically twice against the same trace before the
rewrite), consistent with the same Vertex judge flakiness already documented
for the two dropped built-in metrics. Not chased further; a platform issue, not
a dataset defect.
