# Quickstart: Add-Service Skill

Validates the feature end-to-end once implemented. Assumes
`cloud-architecture-validator-create-architect` is installed as a sibling directory (this skill
writes into its `references/kg/services.yaml`).

## Prerequisites

```bash
cd cloud-architecture-validator-add
python3 -m pip install pyyaml  # only new-ish dependency, matches root invariant #3
```

## Scenario 1 — new service, full guided add (User Story 1)

```bash
python3 scripts/add_service.py --name "Memorystore for Redis" --provider gcp
```

Expected: proposed `category`/`description`/`references_url`/`icon` printed, then a single batch
of three judgment questions (`network_placement`, `reachability`, `roles`), then a confirm
prompt. Confirming appends one entry to
`../cloud-architecture-validator-create-architect/references/kg/services.yaml` with
`provenance: {generated: cloud-architecture-validator-add, status: unverified, sources: [...]}`
— confirms FR-001–FR-005, FR-007.

## Scenario 2 — duplicate request (User Story 2)

```bash
python3 scripts/add_service.py --name "Memorystore for Redis" --provider gcp
```

Run again after Scenario 1. Expected: reports the existing entry immediately, no judgment
questions asked, no second entry written — confirms FR-002, SC-003.

## Scenario 3 — abandon before confirming (FR-010)

```bash
python3 scripts/add_service.py --name "Some New Service" --provider azure
# answer judgment questions, then answer "no" at the final confirm prompt
```

Expected: exit code `1`, `services.yaml` unchanged (`git diff` shows nothing) — confirms FR-010.

## Scenario 4 — correction before write (User Story 3)

```bash
python3 scripts/add_service.py --name "Cloud CDN" --provider gcp
# when the proposed category/description is shown, supply a correction instead of accepting it
```

Expected: the written entry reflects the corrected value, not the original proposal — confirms
FR-006.

## Scenario 5 — dry run (no write)

```bash
python3 scripts/add_service.py --name "Anything" --provider gcp --dry-run
```

Expected: full flow runs to completion, prints what *would* be written, but
`services.yaml` is untouched — useful for demoing without mutating the KG.

## Scenario 6 — staleness-detected update (User Story 4)

```bash
python3 scripts/add_service.py --name "Vertex AI" --provider gcp \
  --references-url "https://cloud.google.com/vertex-ai/docs/whats-new"
```

Assumes `Vertex AI` already exists in the KG and the supplied reference is newer than the entry's
last-checked date. Expected: instead of "already exists," the tool prints a diff — changed
fields plus draft judgment-field answers (`network_placement`/`reachability`/`roles`), each with
a rationale citing the reference. Confirming each field (accept-as-shown or override) and then
confirming overall updates the entry in place, resets `provenance.status` to `unverified`, and
refreshes `provenance.sources` — confirms FR-011–FR-013.

```bash
python3 scripts/add_service.py --name "Vertex AI" --provider gcp \
  --references-url "https://cloud.google.com/vertex-ai/docs/whats-new"
# then answer "no" at the final confirm prompt
```

Expected: `services.yaml`'s `Vertex AI` entry is byte-for-byte unchanged — confirms the update
path's own abandon behavior (mirrors FR-010).

## Post-add integrity check

```bash
cd ../cloud-architecture-validator-create-architect
python3 scripts/check_kg.py
```

Expected: reports the new entry's `provenance.status: unverified` and fails the provenance gate
specifically on it — this is the intended behavior (D21), not a bug. Coverage/regression numbers
for everything else must be unchanged.

## Regression fixtures

Once `tests/test_add_service.py` exists, it should cover at least: one full happy-path write, one
duplicate short-circuit, one abandon-produces-no-write case, and one correction-before-write case
— mirroring the scenarios above.
