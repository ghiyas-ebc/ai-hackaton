"""Add a service to the KG, with agent-proposed safe fields and human-gated judgment fields."""

import argparse
import sys


def propose_safe_fields(name, provider, references_url=None):
    """Fetch/propose category, description, references_url, icon. (T005)"""
    raise NotImplementedError("T005: propose.py not yet built")


def build_judgment_batch():
    """Create empty JudgmentQuestionBatch. (T007)"""
    raise NotImplementedError("T007: judgment.py not yet built")


def prompt_for_judgments(batch):
    """Interactive stdin prompt for judgment fields. (T012)"""
    raise NotImplementedError("T012: main() confirmation UX not yet built")


def build_provenance(sources):
    """Build provenance block with generated/status/sources. (T006)"""
    raise NotImplementedError("T006: provenance.py not yet built")


def write_entry(services, entry, mode="append"):
    """Write to services.yaml, append or replace. (T008)"""
    raise NotImplementedError("T008: kg_io.py write_entry not yet built")


def find_existing(services, name, provider):
    """Lookup (name, provider) case-insensitive. (T004)"""
    raise NotImplementedError("T004: kg_io.py find_existing not yet built")


def is_newer(reference_checked_at, existing_entry):
    """Staleness check: reference newer than entry's last-checked date? (T019)"""
    raise NotImplementedError("T019: kg_io.py is_newer not yet built")


def build_update_proposal(existing_entry, reference_url):
    """Build UpdateProposal with drafts. (T020)"""
    raise NotImplementedError("T020: propose.py build_update_proposal not yet built")


def main():
    parser = argparse.ArgumentParser(
        description="Add or update a cloud service in the KG with human-gated judgment fields."
    )
    parser.add_argument("--name", required=True, help="Service display name")
    parser.add_argument("--provider", required=True, choices=["gcp", "azure"],
                        help="Cloud provider (gcp or azure)")
    parser.add_argument("--references-url", help="Reference URL for agent fetch (optional)")
    parser.add_argument("--dry-run", action="store_true", help="Propose but don't write")

    args = parser.parse_args()

    # T011: Wire fresh-add flow.
    from kg_io import load_services, find_existing, write_entry, is_newer
    from propose import propose_safe_fields, build_update_proposal
    from provenance import build_provenance
    from judgment import JudgmentQuestionBatch
    from pathlib import Path

    # Find services.yaml (sibling skill's references/kg/)
    kg_path = Path(__file__).resolve().parent.parent.parent / \
              "cloud-architecture-validator-create-architect" / \
              "references" / "kg" / "services.yaml"

    if not kg_path.exists():
        print(f"Error: KG not found at {kg_path}", file=sys.stderr)
        return 2

    services = load_services(kg_path)

    # Duplicate check (FR-002, T015 branch check)
    existing = find_existing(services, args.name, args.provider)

    if existing:
        # Check staleness (T019): is supplied reference newer?
        if args.references_url and is_newer(args.references_url, existing):
            # T021: Update path (US4) — Phase 5, not yet implemented
            # Would: build_update_proposal() → show drafts + diffs → confirm each judgment field
            # → write_entry(..., mode="replace") with fresh build_provenance()
            print("Note: newer reference supplied, but update path (Phase 5) not yet built.")
            print(f"To update, manually edit {kg_path} or re-run Phase 5.")
            return 1
        else:
            # T015: Report existing, exit
            print(f"Service already exists:")
            import json
            print(json.dumps(existing, indent=2))
            return 0

    # Fresh add (T011 main flow)
    # T005: Propose safe fields
    proposal = propose_safe_fields(args.name, args.provider, args.references_url)

    # T012: Print proposal
    print(f"\nProposed fields for {args.name} ({args.provider}):")
    for field in ("category", "description", "references_url", "icon"):
        val = proposal.get(field)
        status = " (unresolved)" if field in proposal.get("unresolved_fields", []) else ""
        print(f"  {field}: {val}{status}")

    # T007/T012: Prompt for judgment questions
    batch = JudgmentQuestionBatch()

    print("\nPlease answer the following (all required):")

    # network_placement
    while not batch.is_answered("network_placement"):
        ans = input("network_placement [public/private/both]: ").strip()
        if ans:
            batch.set_answer("network_placement", ans)

    # reachability
    while not batch.is_answered("reachability"):
        ans = input("reachability [public_only/private_only/public_or_private]: ").strip()
        if ans:
            batch.set_answer("reachability", ans)

    # roles
    while not batch.is_answered("roles"):
        ans = input("roles (comma-separated): ").strip()
        if ans:
            batch.set_answer("roles", [r.strip() for r in ans.split(",")])

    # T006/T007/T008: Build + write
    if not batch.all_answered():
        print("Not all fields answered. Aborting (FR-010).", file=sys.stderr)
        return 1

    entry = {
        "id": args.name.lower().replace(" ", "-"),
        "name": args.name,
        "provider": args.provider,
        "category": proposal.get("category"),
        "description": proposal.get("description"),
        "references_url": args.references_url or proposal.get("references_url"),
        "icon": proposal.get("icon"),
        **batch.to_dict(),
        "provenance": build_provenance(proposal.get("sources", []))
    }

    if args.dry_run:
        print("\n[DRY RUN] Would write:")
        import json
        print(json.dumps(entry, indent=2))
        return 0

    # T008: Write
    write_entry(kg_path, services, entry, mode="append")
    print(f"\nAdded {args.name} to services.yaml with status=unverified.")
    print("Run check_kg.py to verify, then update provenance.status to 'verified' after review.")
    return 0


if __name__ == "__main__":
    main()
