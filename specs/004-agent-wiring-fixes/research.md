# Research: Agent Wiring Fixes

## Decision: Gap 7 resolved as Option B (extract, don't shell out)

**Decision**: `add_service_to_kg` imports and calls `add_service.py`'s already-decomposed
non-interactive functions (`propose_safe_fields`, `find_existing`, `build_provenance`, `write_entry`,
`build_update_proposal`) directly, mirroring how `tools.py` already imports `kg_lib` modules via
`sys.path.insert`. It does **not** shell out to `add_service.py` as a subprocess.

**Rationale**: `add_service.py`'s `main()` is interactive (reads stdin via `input()`) — an ADK agent
cannot drive stdin prompts mid-conversation. But the functions `main()` calls were already extracted
as standalone, non-interactive functions (see `add_service.py:7-76`), so no new extraction work is
needed — only a new caller. Judgment fields (`network_placement`, `reachability`, `roles`) become
explicit keyword arguments the agent tool receives after the model has gathered them conversationally,
preserving CLAUDE.md D6/D21's human-gate: the *values* still come from a human, only the *transport*
changes from stdin to a function call.

**Alternatives considered**:
- *Option A (agent tells user to run the CLI)* — rejected. This is what the current stub effectively
  does today (worse: it claims the tool doesn't exist at all), and it's the exact gap the evaluation
  flagged: a completed capability the user can't reach without leaving the conversation.
- *Subprocess wrapping `add_service.py --name ... --provider ...`* — rejected. The CLI's fresh-add path
  still blocks on interactive judgment/equivalence/override prompts even with those two flags supplied;
  subprocess would need `--non-interactive` flags that don't exist today, which is just Option B with
  extra process-boundary complexity (stdout parsing, exit codes) for no benefit over a direct import.

## Decision: `propose_equivalence` tool exposes recommendation only, does not write

**Decision**: The new `propose_equivalence` agent tool calls `equivalence.propose_equivalence()` (and,
where useful, `find_existing_equivalence()` against the already-loaded `equivalences.yaml`) and returns
the recommendation for the agent to relay. It does not call `write_equivalence()`.

**Rationale**: Gap 2 in the evaluation explicitly frames this as "a recommendation, not a write path."
Keeping it read-only avoids introducing a second, less-reviewed way to mutate `equivalences.yaml`
alongside the CLI's existing `prompt_for_equivalence` flow, and keeps this feature's blast radius to
"expose what spec 003 already computes," matching the spec's Assumptions section.

**Known limitation to surface, not hide**: `equivalence.propose_equivalence()` (`equivalence.py:94`) is
itself currently a stub — it returns a placeholder `service_name_to="[Agent will fill in equivalent
name]"` rather than a real inference; the real target-service name was intended to come from the agent
doing its own doc lookup. Wiring the tool as specified (FR-006, FR-008: no LLM judgment) means the tool
must not let the model fill that placeholder in as if it were derived fact. Two sound options exist:
check `find_existing_equivalence()` first (real recorded equivalences answer most cases per FR-006's
first acceptance scenario) and only fall through to `propose_equivalence()`'s placeholder for the
explicit "no known equivalent yet" case (FR-006's second scenario) — surfaced as exactly that, not as a
name. This keeps the model from presenting a guess as a lookup result. Fixing `propose_equivalence()`
itself to do real inference is out of scope for this feature (spec 003 is marked done and out of this
feature's assumptions).

## Decision: No new locking/concurrency mechanism for simultaneous add-service writes

**Decision**: Rely on `find_existing()`'s pre-write check (FR-005) as the only duplicate guard; no file
locking is added.

**Rationale**: The existing `-add` skill (spec 002, complete) has no locking today, and the evaluation
does not flag this as a gap. The spec's edge case ("two engineers concurrently add the same service")
is handled adequately by re-checking `find_existing()` immediately before `write_entry()` — a narrow
race remains, consistent with D1's framing of the KG as file-scale/single- or few-editor scope, not
requiring warehouse-grade concurrency control.

**Alternatives considered**: File locking (`fcntl`/`portalocker`) — rejected as scope creep; it would
be new dependency surface (invariant #3) for a race window the project's own scale assumptions (D1)
don't consider load-bearing yet.
