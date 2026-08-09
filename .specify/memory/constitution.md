<!--
Sync Impact Report
Version change: 1.0.0 → 1.1.0
Modified principles:
  - I. Verdict-Not-Guess — added the three-tier evidence-gating classification
    (Proven / Theoretically Possible / Requires Deep Review) as the concrete mechanism the
    principle already implied.
  - IV. Read-Only by Default, Explicit Write Path — named the Gap Report as the specific
    artifact this write path produces for unfulfilled/uncovered requests.
Added sections:
  - "Non-Blocking Operation" bullet under Product Scope & Constraints (proceed on stated
    assumptions rather than stall the meeting waiting on missing input)
  - "Mismatch correction" clarified under Principle I rationale
Removed sections: none
Templates requiring updates:
  - .specify/templates/plan-template.md ⚠ pending (still generic/dynamic — no edit required,
    re-checked this pass)
  - .specify/templates/spec-template.md ⚠ pending (no conflict found, re-checked this pass)
  - .specify/templates/tasks-template.md ⚠ pending (no conflict found, re-checked this pass)
  - CLAUDE.md ✅ no change needed
Follow-up TODOs:
  - TODO(RATIFICATION_DATE): unchanged from v1.0.0 — original ratification date used as-is.
  - Source doc (Technical_Sales_Precision.pdf) names concrete internal metrics (18
    escalations/month, 6-day avg delay) as the business case; these are product-marketing
    claims, not constitutional obligations, and are deliberately not encoded as principles.
-->

# Technical Co-Pilot Constitution

## Core Principles

### I. Verdict-Not-Guess
Every difficulty score, technical-mismatch flag, or feasibility verdict the system presents MUST be
traceable to a deterministic rule, a KG lookup, or documented internal project history — never to an
LLM's unaided judgment. An LLM MAY parse a client's request, retrieve relevant history, and phrase the
verdict for a human reader, but it MUST NOT be the thing that decides difficulty or feasibility. When
no rule or historical evidence covers a request, the system MUST say so explicitly (e.g.
`NEEDS_ENGINEERING_REVIEW`, `NO_PRECEDENT`) rather than produce a plausible-sounding number.

Capability claims feeding a verdict MUST be classified into exactly one of three tiers, never blended
into a single confidence number: **Proven** (built and shipped before, cite the project), **Theoretically
Possible** (no internal precedent, but nothing in the KG/rules rules it out), or **Requires Deep Review**
(conflicts with a rule, or the request itself is ambiguous/unmatched). A verdict MUST also surface tech
mismatches — cases where the client's stated ask (e.g. "we need WebSockets") doesn't match what the
underlying requirement actually needs (e.g. a REST API) — as a correction, not a silent substitution.

Rationale: the entire value proposition is replacing a salesperson's gut feeling with a data-backed
assessment. An LLM-guessed verdict wearing the same "Verdict Card" UI as a rule-derived one is
indistinguishable to the user and destroys the tool's core trust claim the first time it's confidently
wrong in front of a client. The three-tier split exists because "Medium difficulty" alone can't tell a
rep whether that's because it's genuinely hard or because nobody has tried it — those require different
conversations with the client.

### II. Evidence-Grounded History
Every fact used to produce a verdict (past project outcome, technical mismatch, effort estimate) MUST
carry a pointer back to its source project/record. The system MUST NOT synthesize or interpolate a
"typical" outcome when no matching precedent exists in internal history. Coverage gaps MUST be visible
in the Verdict Card, not silently smoothed over.

Rationale: "internal project history and historical evidence" is the proposal's stated differentiator
over generic sales tools. Un-sourced evidence is just a fancier guess, and a Verdict Card a sales rep
can't defend when an engineer asks "where does that number come from?" fails on first contact with a
skeptical technical stakeholder.

### III. Human Gate on Judgment Calls
Fields that require subjective classification rather than lookup or computation — engineer-assigned
difficulty overrides, disputed technical-mismatch calls, "requires further engineering review" escalation
— MUST be reviewable and overridable by a human before they're presented as final, and any AI-proposed
value in these fields MUST be marked unverified until a human confirms it. The checklist generated for
engineers is an input to their judgment, not a substitute for it.

Rationale: mirrors the KG's own manual/unverified/verified provenance model — an unreviewed inference in
an under-verified field fails silently and confidently, which is worse for this product than for most,
since its whole pitch is that it does NOT make salespeople overcommit blind.

### IV. Read-Only by Default, Explicit Write Path
Capturing "market intelligence" back into the organizational knowledge base is a deliberate, auditable
write, never an automatic side effect of running a validation. Any component that turns a sales
conversation into a persisted knowledge asset MUST go through an explicit confirmation step and MUST
record provenance (who/what proposed it, when, verified status).

An unfulfilled or `UNCOVERED` request is not a dead end: it MUST be logged as a **Gap Report** entry —
a Product-facing, not sales-facing, artifact — describing what the client asked for and why current
rules/history don't cover it. This is the one write path that fires without a per-instance human
confirmation, because a Gap Report is a record of "we didn't know," not a claim of new organizational
fact, and Principle III's judgment-field protections don't apply to it.

Rationale: same asymmetry the KG invariants already rely on — a missing data point fails safely (visible
gap, prompts a human), a bad data point silently entering shared organizational knowledge does not, and
nothing downstream can tell the difference between a curated fact and a hallucinated one without
provenance.

### V. Layered Transparency
The Verdict Card MUST separate what was measured (rule/evidence-backed) from what was inferred and from
what is simply unknown, using distinct, consistent labels across every layer of assessment (structural,
technical mismatch, cost/effort, timeline risk, etc.). A single blended "difficulty score" without a
breakdown of which layers contributed and which layers had no data is not acceptable.

Rationale: a single opaque number invites the exact over-commitment risk this tool exists to prevent —
sales teams will anchor on it whether or not it's backed by evidence, unless the system itself makes the
distinction impossible to miss.

## Product Scope & Constraints

This system is a pre-validation copilot used live or near-live in sales conversations, by users
(salespeople, presales engineers) who are not technical architects. Consequences:

- Latency matters: a verdict must return fast enough to be usable mid-meeting, not as an overnight
  batch report. Slow, thorough analysis belongs in the generated engineer checklist, not the live card.
- Output MUST be legible to a non-technical reader first, with technical detail available on demand
  (e.g. for the engineer checklist) rather than always inline.
- The system draws on two data sources: (a) structural/technical rules about what's feasible, and
  (b) internal historical project records. A verdict lacking support from either MUST be labeled
  low-confidence or escalated, never presented with the same confidence as a fully-supported one.
- No client data or sales-conversation content leaves the organization's own systems for verdict
  computation; historical-evidence lookups and any LLM calls operate on internally-controlled data only.
- The system MUST remain non-blocking: if the sales rep can't supply a detail mid-meeting, the system
  proceeds using an explicitly stated assumption (labeled as such on the Verdict Card) rather than
  halting to demand missing input. A stalled tool in a live meeting is a worse failure than a verdict
  that's transparently caveated.

## Development Workflow & Quality Gates

- Every change that affects how a verdict, score, or mismatch flag is computed MUST include or update a
  regression fixture demonstrating the old and new behavior, mirroring the existing
  cloud-architecture-validator's 37/37 regression discipline. A change that silently narrows coverage
  (fewer requests get a real verdict) is a regression even if all fixtures pass.
- Any new field sourced from historical project data MUST specify, at the point it's introduced, how
  provenance is captured and how staleness is detected (evidence ages — a two-year-old project outcome
  is a different confidence tier than last quarter's).
- Features that let an agent or LLM propose a write to organizational knowledge MUST ship with the
  human-confirmation gate from Principle III in the same change, not as a follow-up.

## Governance

This constitution supersedes ad-hoc practice for this project. Amendments require: (1) a written
rationale for the change referencing which principle or section is affected, (2) a version bump per the
policy below, (3) propagation of the change into any dependent template or skill instructions that
reference the amended principle by name.

Versioning policy (semantic):
- MAJOR: a principle is removed or redefined in a way that reverses its prior guarantee (e.g. permitting
  LLM-decided verdicts).
- MINOR: a new principle or section is added, or existing guidance is materially expanded.
- PATCH: wording, clarification, or typo fixes with no change in obligation.

Compliance review: any plan or spec produced under this constitution MUST include a Constitution Check
step that names which of the five principles are implicated and how the design satisfies them. A design
that cannot satisfy Principle I (Verdict-Not-Guess) or III (Human Gate) MUST be revised before
implementation proceeds, not shipped with a caveat.

**Version**: 1.1.0 | **Ratified**: 2026-08-09 | **Last Amended**: 2026-08-09
