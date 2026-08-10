# Contract: `add_service.py`

CLI entry point replacing the stub in `cloud-architecture-validator-add/scripts/add_service.py`.
This is the skill's sole interface — no separate API/tool wrapper exists (unlike the ADK agent's
`generate_verdict_card` tool wrapping `verdict_card.py`, this skill is invoked directly, matching
the existing stub's CLI shape).

## Invocation

```bash
python3 add_service.py --name "<display name>" --provider gcp|azure [--references-url <url>] [--dry-run]
```

| Flag | Required | Notes |
|---|---|---|
| `--name` | yes | Service display name to propose. |
| `--provider` | yes | `gcp` or `azure` (matches existing `services.yaml` provider values). |
| `--references-url` | no | Seed URL for the agent to check/verify; if omitted, the tool attempts to find one. |
| `--dry-run` | no | Runs the full propose → question → confirm flow but never writes to `services.yaml`, for testing/demo. |

## Flow (interactive, stdout/stdin)

1. **Duplicate check** — if `(name, provider)` already exists in `services.yaml`:
   - If `--references-url` is absent, or no newer than the existing entry's last-checked date
     (FR-011), print the existing entry and exit 0 without proposing anything (US2, FR-002).
   - If newer, branch to the **update flow** below instead (US4).
2. **Propose safe fields** — print `category`, `description`, `references_url`, `icon`,
   flagging any that came back unresolved (FR-003, Edge Cases).
3. **Ask judgment questions** — print all three (`network_placement`, `reachability`, `roles`)
   as one batch, read answers from stdin. Re-prompt on any left blank; never proceed with a
   default (FR-004).
4. **Offer correction** — before final confirm, allow the human to override any proposed safe
   field (FR-006, US3).
5. **Confirm or abandon** — explicit yes/no. On abandon (or EOF/interrupt), exit without writing
   anything (FR-010). On confirm, append the merged entry to `services.yaml` with
   `provenance.generated: cloud-architecture-validator-add`, `provenance.status: unverified`
   (FR-007, FR-008, FR-009).

## Update flow (US4, triggered from step 1 above)

1. Print the existing entry's current values alongside reference-derived drafts for every
   changed field, including `network_placement`/`reachability`/`roles`, each with a one-line
   rationale citing the reference (FR-012).
2. Present all three judgment fields as a batch, pre-filled with their draft value + rationale,
   but marked unconfirmed — identical confirm-required semantics to a fresh add's step 3; the
   human must explicitly accept-as-shown or override each one (FR-004/FR-005/FR-012 apply
   unchanged).
3. Offer correction on any field, same as step 4 of the add flow (US3 applies equally to
   updates).
4. Confirm or abandon — on confirm, the existing entry is replaced in place with the confirmed
   values, `provenance.status` reset to `unverified`, `provenance.sources` refreshed to the new
   reference (FR-013). On abandon, `services.yaml` is untouched, identical to FR-010.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success — either a new entry was written, or an existing duplicate was reported. |
| `1` | Abandoned by the human before confirmation — no write occurred. |
| `2` | Usage error (missing required flag, invalid `--provider` value). |

## Postconditions

- On exit `0` with a new write: `services.yaml` has exactly one additional entry, matching
  data-model.md's `ServiceEntry` shape.
- On any other exit code: `services.yaml` is byte-identical to its pre-invocation state.
- `check_kg.py` run afterward reports the new entry's `provenance.status` as `unverified` and
  fails the provenance gate on it — this is expected and correct until a human separately edits
  the file to flip it to `verified` with a `verified:` date.
