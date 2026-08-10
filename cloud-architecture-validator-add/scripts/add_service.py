"""Add a service to the KG, with agent-proposed safe fields and human-gated judgment fields."""

import argparse
import sys


def propose_safe_fields(name, provider, references_url=None):
    """Fetch/propose category, description, references_url, icon. (T005)"""
    from propose import propose_safe_fields as _propose
    return _propose(name, provider, references_url)


def build_judgment_batch():
    """Create empty JudgmentQuestionBatch. (T007)"""
    from judgment import JudgmentQuestionBatch
    return JudgmentQuestionBatch()


def prompt_for_judgments(batch):
    """Interactive stdin prompt for judgment fields. (T012)"""
    # Integrated into main() flow directly
    pass


def build_provenance(sources):
    """Build provenance block with generated/status/sources. (T006)"""
    from provenance import build_provenance as _build
    return _build(sources)


def write_entry(kg_path, services, entry, mode="append"):
    """Write to services.yaml, append or replace. (T008)"""
    from kg_io import write_entry as _write
    return _write(kg_path, services, entry, mode)


def find_existing(services, name, provider):
    """Lookup (name, provider) case-insensitive. (T004)"""
    from kg_io import find_existing as _find
    return _find(services, name, provider)


def is_newer(reference_checked_at, existing_entry):
    """Staleness check: reference newer than entry's last-checked date? (T019)"""
    from kg_io import is_newer as _is_newer
    return _is_newer(reference_checked_at, existing_entry)


def build_update_proposal(existing_entry, reference_url):
    """Build UpdateProposal with drafts. (T020)"""
    from propose import build_update_proposal as _build
    return _build(existing_entry, reference_url)


def prompt_for_field_overrides(prompt_msg="Correct any field before confirming (leave blank to keep):"):
    """T024/T025: Ask user for field-by-field corrections.

    Returns dict with overrides (only non-empty values), else empty dict.
    """
    overrides = {}
    fields = ["category", "description", "references_url", "icon", "network_placement", "reachability", "roles"]

    print(f"\n{prompt_msg}")
    for field in fields:
        ans = input(f"  {field}: ").strip()
        if ans:
            if field == "roles":
                overrides[field] = [r.strip() for r in ans.split(",")]
            elif field == "network_placement":
                overrides[field] = ans.split()
            else:
                overrides[field] = ans

    return overrides


def prompt_for_equivalence(service_name, provider, kg_path=None):
    """T012: Prompt user for equivalence detection (fresh-add).

    Option 2: If user confirms, offer to auto-write to equivalences.yaml.
    Still human-gated (user must click "Apply to KG").

    Returns: (EquivalenceProposal, was_written) or (None, False) if declined
    """
    from equivalence import propose_equivalence, format_recommendation, write_equivalence
    from pathlib import Path

    print(f"\nDoes {service_name} have an equivalent in other cloud providers?")
    ans = input("Check for equivalence? (y/n): ").strip().lower()
    if ans != "y":
        return None, False

    # Agent proposes (stub for now)
    proposal = propose_equivalence(service_name, provider, [], None)
    if not proposal:
        return None, False

    print(f"\nProposed equivalent:")
    print(f"  {proposal.provider_from}: {proposal.service_name_from}")
    print(f"  {proposal.provider_to}: {proposal.service_name_to}")
    print(f"  Confidence: {proposal.confidence}")

    # User confirm/correct/decline
    choice = input("Accept proposal, correct, or decline? (accept/correct/decline): ").strip().lower()
    if choice == "decline":
        return None, False

    confirmed_name = proposal.service_name_to
    if choice == "correct":
        confirmed_name = input("Enter corrected target service name: ").strip()
        if not confirmed_name:
            return None, False

    # Option 2: Offer to auto-write to KG
    if kg_path:
        apply = input("\nApply this equivalence to the KG? (y/n): ").strip().lower()
        if apply == "y":
            equiv_path = Path(kg_path).parent.parent / "cloud-architecture-validator-create-architect" / "references" / "kg" / "equivalences.yaml"
            if write_equivalence(str(equiv_path), proposal, confirmed_name):
                print(f"\n✓ Equivalence written to KG (status: unverified).")
                print(f"Run check_kg.py to verify, then update provenance.status to 'verified' after review.")
                return proposal, True
            else:
                print(f"\n✗ Failed to write equivalence. Check file permissions.")
                return proposal, False

    # Fallback: Output recommendation for manual edit
    recommendation = format_recommendation(proposal, confirmed_name)
    print(recommendation)

    return proposal, False


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
        from datetime import datetime
        ref_date = datetime.now()  # Placeholder: real impl would parse --references-url fetch date
        if args.references_url and is_newer(ref_date, existing):
            # T021: Update path (US4) — build proposal, ask for confirmation on drafts
            proposal = build_update_proposal(existing, args.references_url)

            print(f"\nNewer reference found for {args.name}.")
            print(f"Changed fields: {proposal['changed_fields']}")
            print(f"\nProposed updates:")
            for field in ("network_placement", "reachability", "roles"):
                draft = proposal["draft_fields"].get(field)
                rationale = proposal["draft_rationale"].get(field)
                print(f"  {field}: {draft}")
                print(f"    Reason: {rationale}")

            # T007/T012: Prompt for confirmation on each draft
            batch = JudgmentQuestionBatch()

            print("\nConfirm each field (or correct before confirming):")

            # network_placement draft
            default_np = proposal["draft_fields"].get("network_placement", "")
            ans = input(f"network_placement [{default_np}]: ").strip()
            if ans:
                batch.set_answer("network_placement", ans.split())
            else:
                batch.set_answer("network_placement", default_np)

            # reachability draft
            default_reach = proposal["draft_fields"].get("reachability", "")
            ans = input(f"reachability [{default_reach}]: ").strip()
            if ans:
                batch.set_answer("reachability", ans)
            else:
                batch.set_answer("reachability", default_reach)

            # roles draft
            default_roles = proposal["draft_fields"].get("roles", [])
            default_roles_str = ",".join(default_roles) if isinstance(default_roles, list) else str(default_roles)
            ans = input(f"roles [{default_roles_str}]: ").strip()
            if ans:
                batch.set_answer("roles", [r.strip() for r in ans.split(",")])
            else:
                batch.set_answer("roles", default_roles)

            # T006/T008: Build updated entry + write
            if not batch.all_answered():
                print("Not all fields confirmed. Aborting (FR-012).", file=sys.stderr)
                return 1

            # T018/T019/US2: Check for competitor mentions in reference + offer equivalence detection
            from equivalence import detect_competitor_mention, propose_equivalence, write_equivalence
            from pathlib import Path
            mention = detect_competitor_mention(proposal["reference_url"])  # T017: detect
            if mention:
                print(f"\nReference mentions competitor: {mention}")
                eq_proposal = propose_equivalence(args.name, args.provider, [], args.references_url)
                if eq_proposal:
                    print(f"Proposed equivalent: {eq_proposal.service_name_to}")
                    choice = input("Accept, correct, or decline equivalence? (accept/correct/decline): ").strip().lower()
                    if choice != "decline":
                        confirmed_name = eq_proposal.service_name_to
                        if choice == "correct":
                            confirmed_name = input("Enter corrected name: ").strip()
                        if confirmed_name:
                            # Option 2: Offer auto-write
                            apply = input("Apply equivalence to KG? (y/n): ").strip().lower()
                            if apply == "y":
                                equiv_path = Path(kg_path).parent.parent / "cloud-architecture-validator-create-architect" / "references" / "kg" / "equivalences.yaml"
                                if write_equivalence(str(equiv_path), eq_proposal, confirmed_name):
                                    print(f"✓ Equivalence written to KG (status: unverified).")
                                else:
                                    print(f"✗ Failed to write equivalence.")

            # T025: Prompt for field corrections before update write
            overrides = prompt_for_field_overrides()

            updated_entry = {
                "id": existing.get("id"),
                "name": existing.get("name"),
                "provider": existing.get("provider"),
                "category": overrides.get("category") or existing.get("category"),
                "description": overrides.get("description") or existing.get("description"),
                "references_url": overrides.get("references_url") or args.references_url,
                "icon": overrides.get("icon") or existing.get("icon"),
                "network_placement": overrides.get("network_placement") or batch.to_dict().get("network_placement"),
                "reachability": overrides.get("reachability") or batch.to_dict().get("reachability"),
                "roles": overrides.get("roles") or batch.to_dict().get("roles"),
                "provenance": build_provenance([args.references_url])
            }

            if args.dry_run:
                print("\n[DRY RUN] Would update:")
                import json
                print(json.dumps(updated_entry, indent=2))
                return 0

            write_entry(kg_path, services, updated_entry, mode="replace")
            print(f"\nUpdated {args.name} with newer reference. Status reset to unverified.")
            print("Run check_kg.py to verify, then update provenance.status to 'verified' after review.")
            return 0
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

    # T013/US1: Prompt for equivalence after judgment fields (fresh-add)
    prompt_for_equivalence(args.name, args.provider, str(kg_path))

    # T024: Prompt for field corrections before write
    overrides = prompt_for_field_overrides()

    entry = {
        "id": args.name.lower().replace(" ", "-"),
        "name": args.name,
        "provider": args.provider,
        "category": overrides.get("category") or proposal.get("category"),
        "description": overrides.get("description") or proposal.get("description"),
        "references_url": overrides.get("references_url") or args.references_url or proposal.get("references_url"),
        "icon": overrides.get("icon") or proposal.get("icon"),
        "network_placement": overrides.get("network_placement") or batch.to_dict().get("network_placement"),
        "reachability": overrides.get("reachability") or batch.to_dict().get("reachability"),
        "roles": overrides.get("roles") or batch.to_dict().get("roles"),
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
