"""Equivalence detection: propose, validate, format recommendations. (T004-T007, T011, T017)"""

from dataclasses import dataclass
from typing import Optional, Dict, List, Any
import yaml


@dataclass
class EquivalenceProposal:
    """T007: Equivalence proposal from agent.

    Fields:
      provider_from: "gcp" or "azure"
      service_name_from: Service name in source provider
      provider_to: Target provider
      service_name_to: Proposed equivalent in target provider
      confidence: "certain" | "likely" | "possible"
      rationale: Why this is equivalent (one-liner)
      sources: URLs checked during proposal
    """
    provider_from: str
    service_name_from: str
    provider_to: str
    service_name_to: str
    confidence: str
    rationale: str
    sources: List[str]


def load_equivalences(yaml_path):
    """T004: Load equivalences.yaml from sibling skill (create-architect/references/kg/).

    Returns:
      dict: {equivalences: [...]} or empty if file missing
    """
    try:
        with open(yaml_path) as f:
            return yaml.safe_load(f) or {"equivalences": []}
    except FileNotFoundError:
        return {"equivalences": []}


def find_existing_equivalence(provider_from, service_name_from, equivalences):
    """T005: Case-insensitive lookup for existing equivalence mapping.

    Returns:
      dict (existing mapping) or None
    """
    if not equivalences or "equivalences" not in equivalences:
        return None

    pf_lower = provider_from.lower()
    sn_lower = service_name_from.lower()

    for entry in equivalences.get("equivalences", []):
        entry_provider = str(entry.get(pf_lower, "")).lower()
        if entry_provider == sn_lower:
            return entry

    return None


def format_recommendation(proposal: EquivalenceProposal, confirmed_name: str) -> str:
    """T006: Format equivalence proposal as copy-paste-ready YAML + metadata.

    Args:
      proposal: EquivalenceProposal from agent
      confirmed_name: User-confirmed target service name (may differ from proposal)

    Returns:
      str: Formatted recommendation block
    """
    yaml_block = f"""- {proposal.provider_from}: {proposal.service_name_from}
  {proposal.provider_to}: {confirmed_name}
  notes: |
    Proposed by: cloud-architecture-validator-add
    Confidence: {proposal.confidence}
    Rationale: {proposal.rationale}"""

    metadata = f"""
Suggested equivalence entry for references/kg/equivalences.yaml:

```yaml
{yaml_block}
```

Proposed on: 2026-08-10
Requires human review before adding to the KG.
Next: Edit references/kg/equivalences.yaml in cloud-architecture-validator-create-architect, then run check_kg.py."""

    return metadata


def propose_equivalence(service_name: str, provider_from: str, categories: List[str], references_url: str = None) -> Optional[EquivalenceProposal]:
    """T011: Agent-based equivalence proposal.

    Stub: Real impl would fetch docs, infer target provider service.
    For now, returns placeholder proposal (to be filled by agent in actual impl).

    Args:
      service_name: Service to find equivalent for
      provider_from: Source provider (gcp, azure)
      categories: Service categories (["llm"], ["database"], etc.)
      references_url: Optional URL for agent to fetch

    Returns:
      EquivalenceProposal or None if no equiv found
    """
    # Stub: agent would query provider docs + infer equivalent
    # For MVP, return placeholder to be filled by agent call
    target_provider = "azure" if provider_from.lower() == "gcp" else "gcp"

    return EquivalenceProposal(
        provider_from=provider_from,
        service_name_from=service_name,
        provider_to=target_provider,
        service_name_to="[Agent will fill in equivalent name]",
        confidence="possible",
        rationale="[Agent will provide rationale after fetching docs]",
        sources=[references_url] if references_url else []
    )


def detect_competitor_mention(reference_text: str) -> Optional[str]:
    """T017: Search reference text for competitor product mentions.

    Known competitors: Agent Platform (Azure), SageMaker (AWS), etc.

    Args:
      reference_text: Text content of reference URL/docs

    Returns:
      str: Competitor name if found, else None
    """
    if not reference_text:
        return None

    competitors = [
        ("Agent Platform", "azure"),
        ("SageMaker", "aws"),
        ("Azure Machine Learning", "azure"),
        ("Azure SQL", "azure"),
        ("Container Instances", "azure"),
    ]

    text_lower = reference_text.lower()
    for competitor_name, provider in competitors:
        if competitor_name.lower() in text_lower:
            return competitor_name

    return None


def write_equivalence(yaml_path: str, proposal: EquivalenceProposal, confirmed_name: str) -> bool:
    """Write confirmed equivalence to equivalences.yaml with provenance.

    Option 2: Auto-write on user confirmation (no manual YAML edit needed).
    Principle III (Human Gate) still applies: user confirmed before this runs.

    Args:
      yaml_path: Path to equivalences.yaml in sibling skill
      proposal: EquivalenceProposal from agent
      confirmed_name: User-confirmed target service name

    Returns:
      bool: True if write succeeded
    """
    from datetime import datetime

    equivalences = load_equivalences(yaml_path)

    entry = {
        proposal.provider_from: proposal.service_name_from,
        proposal.provider_to: confirmed_name,
        "provenance": {
            "generated": "cloud-architecture-validator-add",
            "status": "unverified",
            "verified": None,
            "sources": proposal.sources,
            "proposed_on": datetime.now().isoformat(),
            "confidence": proposal.confidence,
            "rationale": proposal.rationale
        }
    }

    if "equivalences" not in equivalences:
        equivalences["equivalences"] = []

    equivalences["equivalences"].append(entry)

    try:
        with open(yaml_path, "w") as f:
            yaml.dump(equivalences, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception as e:
        print(f"Error writing equivalences.yaml: {e}")
        return False
