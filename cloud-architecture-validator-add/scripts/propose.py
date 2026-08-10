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
    # Stub: real implementation would fetch the reference and draft all judgment fields.
    # For now, mark as unresolved.
    proposal = {
        "existing_entry": existing_entry,
        "reference_url": reference_url,
        "draft_fields": {},
        "draft_rationale": {},
        "changed_fields": []
    }

    return proposal
