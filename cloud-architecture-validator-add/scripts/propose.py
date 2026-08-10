"""Fetch/propose safe fields + build update proposals. (T005, T020)"""

import requests


def propose_safe_fields(name, provider, references_url=None):
    """Fetch and propose category, description, references_url, icon.

    T005: Agent-verifiable fields proposal.

    Returns:
        dict with keys: category, description, references_url, icon, unresolved_fields (list),
               sources (list of URLs checked)
    """
    sources = []
    proposal = {
        "category": None,
        "description": None,
        "references_url": None,
        "icon": None,
        "unresolved_fields": [],
        "sources": []
    }

    # Stub: provider docs lookup would go here. For now, mark all unresolved.
    # Real implementation: fetch from provider docs, validate links, resolve icons.
    proposal["unresolved_fields"] = ["category", "description", "references_url", "icon"]
    proposal["sources"] = [references_url] if references_url else []

    return proposal


def build_update_proposal(existing_entry, reference_url):
    """Build UpdateProposal: existing entry + reference-derived drafts for all fields.

    T020: Update proposal with draft judgment answers + rationale.

    Returns:
        dict with keys: existing_entry, reference_url, draft_fields (all fields with drafts),
               draft_rationale (per-field cite), changed_fields (list of fields that differ)
    """
    # Stub: fetch reference and infer judgment fields from docs/schema.
    # For now, draft values are placeholder — real impl queries the reference URL.
    draft_fields = {
        "network_placement": ["private"],
        "reachability": "private_only",
        "roles": ["cache", "data"]
    }

    draft_rationale = {
        "network_placement": f"Inferred from {reference_url} documentation",
        "reachability": f"Inferred from {reference_url} documentation",
        "roles": f"Inferred from {reference_url} documentation"
    }

    # Compute changed_fields: which differ from existing entry
    changed = []
    existing_np = existing_entry.get("network_placement", [])
    existing_reach = existing_entry.get("reachability", "")
    existing_roles = existing_entry.get("roles", [])

    if draft_fields["network_placement"] != existing_np:
        changed.append("network_placement")
    if draft_fields["reachability"] != existing_reach:
        changed.append("reachability")
    if draft_fields["roles"] != existing_roles:
        changed.append("roles")

    proposal = {
        "existing_entry": existing_entry,
        "reference_url": reference_url,
        "draft_fields": draft_fields,
        "draft_rationale": draft_rationale,
        "changed_fields": changed
    }

    return proposal
