---
name: cloud-architecture-validator-init
description: NOT YET IMPLEMENTED. Intended to (re)populate cloud-architecture-validator-create-architect's knowledge graph in bulk from a public URL, with versioning so a bad sync can be rolled back. Currently a design stub — running it produces a clear "not implemented" error rather than touching any file. Do not use this to actually initialize a KG; hand-edit services.yaml via the create-architect skill's own instructions instead, or use cloud-architecture-validator-add for one service at a time.
---

# Cloud Architecture Validator — Init (stub)

Not built yet. This file exists to reserve the name, record the design intent
before anyone forgets it, and give the eventual implementer a starting
contract to argue with — not to be invoked as a working tool.

## Intended purpose

Bulk-populate or refresh `cloud-architecture-validator-create-architect`'s
`references/kg/services.yaml` from a public catalog. Versioned, so a bad
sync is a revert, not a forensic exercise.

## Source: plain HTTP GET against a public URL, nothing more

Decided: fetching is a plain `GET` against a public URL — standard library
(`urllib`/`requests`) only. **No cloud SDK dependency of any kind** —
specifically, no `google-cloud-storage`, no GCS client, no auth. This keeps
init as dependency-light as create-architect itself (PyYAML and nothing
else, per this repo's root invariant #3). If the eventual source turns out
to need auth or isn't reachable over plain HTTPS, that's a reason to
reconsider the source, not a reason to add an SDK here.

Per root CLAUDE.md D19: this is a public GCS object link or a GitHub Release
asset link, not a database — no auth either way, just a URL. Still open: the
actual URL, its schema/format, and update cadence — the *shape* of the
source is decided, the specific catalog is not.

## Hard constraints carried over from create-architect

These are not optional and are not this stub's invention — they're
`cloud-architecture-validator-create-architect`'s own CLAUDE.md decision D6,
and apply here with equal or greater force because init is bulk, not
one-record-at-a-time:

- **Never auto-write `services.yaml`.** A missing node fails safely
  (`UNKNOWN_SERVICE`, the validator says so). A node present with a wrong
  `reachability` or `network_placement` fails *silently* across roughly
  twenty connection pairs, and `check_kg.py` cannot catch it — it checks
  structural consistency, not semantic truth. At init's scale (many services
  per run instead of one) an unattended bad sync doesn't corrupt one entry,
  it corrupts a batch, all at once, all confidently.
- The real shape this points to: fetch → produce a reviewable diff/queue
  (see create-architect's existing `tools/sync_provider_inventory.py`
  pattern, which does exactly this against Terraform provider schemas — same
  problem, different source) → a human approves each entry → *then* it's
  written, in a commit a person can `git blame`.
- Provider/catalog data carries names, brands, and attributes. It does not
  carry network placement, reachability, or roles — those are architectural
  judgments a catalog listing cannot answer, classified by a human, every
  time, no exception carved out for "the source looked reliable."
- Writing itself goes through the same file `cloud-architecture-validator-add`
  and a manual edit both use — `services.yaml` in place. No separate staging
  file, no outside store. See D10 in the root CLAUDE.md: versioning is a
  *checkpoint* taken after a passing `check_kg.py` run, not a second copy of
  the data living somewhere else.

## Versioning

See root CLAUDE.md decision D10 — checkpoint shape and trigger are decided
(zip of `references/kg/` + manifest, taken when `check_kg.py` passes clean).
Storage backend for checkpoints is unrelated to the fetch source above and
still needs picking, but per the same no-cloud-SDK preference stated here,
GitHub Releases (via `gh`, already a CLI available in this environment) is
the natural fit over GCS.

## Before implementing this for real

1. Get the actual public URL from the user: what it serves, its
   schema/format, rate limits, update frequency.
2. Decide the review-queue format and whether it reuses
   `tools/review_queue.yaml`'s shape from create-architect or needs its own.
3. Write real tests before wiring this to `services.yaml`, mirroring
   `check_kg.py`'s regression suite — a bulk-write tool needs more
   verification than a single-entry one, not less.
