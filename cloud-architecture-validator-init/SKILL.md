---
name: cloud-architecture-validator-init
description: NOT YET IMPLEMENTED. Intended to (re)populate cloud-architecture-validator-create-architect's knowledge graph in bulk from an external public service catalog, with versioning so a bad sync can be rolled back. Currently a design stub — running it produces a clear "not implemented" error rather than touching any file. Do not use this to actually initialize a KG; hand-edit services.yaml via the create-architect skill's own instructions instead, or use cloud-architecture-validator-add for one service at a time.
---

# Cloud Architecture Validator — Init (stub)

Not built yet. This file exists to reserve the name, record the design intent
before anyone forgets it, and give the eventual implementer a starting
contract to argue with — not to be invoked as a working tool.

## Intended purpose

Bulk-populate or refresh `cloud-architecture-validator-create-architect`'s
`references/kg/services.yaml` from an external public catalog (source and
format TBD — the user who requested this skill has a specific public database
in mind that hasn't been specified yet: URL, schema, auth, and update cadence
all need to be pinned down before real code goes here). Versioned, so a bad
sync is a revert, not a forensic exercise.

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

## Versioning (intent, not yet designed)

"Rollback a bad sync" implies each init run is a labeled, revertible unit —
most likely a tagged commit or a snapshot of `services.yaml` alongside a
manifest of what changed and from which catalog version. Not designed in
detail yet; do not build the sync logic before this is.

## Before implementing this for real

1. Get the actual public database from the user: URL/access method, schema,
   auth requirements, rate limits, update frequency.
2. Decide the review-queue format and whether it reuses
   `tools/review_queue.yaml`'s shape from create-architect or needs its own.
3. Decide what "version" means concretely — commit-based, snapshot-based, or
   something else — before writing any code that produces one.
4. Write real tests before wiring this to `services.yaml`, mirroring
   `check_kg.py`'s regression suite — a bulk-write tool needs more
   verification than a single-entry one, not less.
