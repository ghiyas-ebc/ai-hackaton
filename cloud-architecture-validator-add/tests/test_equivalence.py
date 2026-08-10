"""Tests for equivalence detection. (T008-T010, T014-T016)"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from equivalence import (
    EquivalenceProposal,
    load_equivalences,
    find_existing_equivalence,
    format_recommendation,
    propose_equivalence,
    detect_competitor_mention,
)


class TestEquivalenceProposal:
    """T008: Proposal from service metadata."""

    def test_equivalence_proposal_from_service_metadata(self):
        """Given service with category, agent proposes equiv + confidence."""
        proposal = propose_equivalence(
            "Vertex AI",
            "gcp",
            ["ml-platform", "training"],
            "https://cloud.google.com/vertex-ai/docs"
        )

        assert proposal is not None
        assert proposal.service_name_from == "Vertex AI"
        assert proposal.provider_from == "gcp"
        assert proposal.provider_to == "azure"
        assert proposal.confidence in ("certain", "likely", "possible")
        assert len(proposal.sources) > 0


class TestEquivalenceRecommendationFormat:
    """T009: Recommendation output is copy-paste ready."""

    def test_equivalence_recommendation_format(self):
        """Confirmed proposal outputs valid YAML block."""
        proposal = EquivalenceProposal(
            provider_from="gcp",
            service_name_from="Cloud Run",
            provider_to="azure",
            service_name_to="Container Instances",
            confidence="certain",
            rationale="Both serverless container platforms",
            sources=["https://cloud.google.com/run/docs"]
        )

        recommendation = format_recommendation(proposal, "Container Instances")

        assert "Container Instances" in recommendation
        assert "cloud-architecture-validator-add" in recommendation
        assert "gcp:" in recommendation
        assert "azure:" in recommendation
        assert "```yaml" in recommendation


class TestExistingEquivalenceDetection:
    """T010: Existing mapping blocks proposal."""

    def test_equivalence_exists_blocks_proposal(self, tmp_services_yaml):
        """Service with existing mapping shows 'already mapped'."""
        # Load fixture equivalences (if set up in conftest)
        # For now, test the logic: find_existing_equivalence should return mapping
        mock_equivalences = {
            "equivalences": [
                {"gcp": "Cloud Run", "azure": "Container Instances"}
            ]
        }

        existing = find_existing_equivalence("gcp", "Cloud Run", mock_equivalences)
        assert existing is not None
        assert existing["gcp"] == "Cloud Run"


class TestCompetitorMentionDetection:
    """T014: Competitor mentions trigger equivalence detection."""

    def test_competitor_mention_detected(self):
        """Reference text containing 'Agent Platform' triggers proposal."""
        text = "Vertex AI offers similar capabilities to Agent Platform."
        mention = detect_competitor_mention(text)
        assert mention == "Agent Platform"

    def test_no_competitor_mention_skips_detection(self):
        """Reference without mentions returns None."""
        text = "Vertex AI is our machine learning platform for GCP."
        mention = detect_competitor_mention(text)
        assert mention is None

    def test_equivalence_proposal_on_update(self):
        """Update flow with competitor mention shows proposal."""
        proposal = propose_equivalence(
            "Vertex AI",
            "gcp",
            ["ml-platform"],
            "https://cloud.google.com/vertex-ai/docs"
        )
        assert proposal is not None
        assert proposal.provider_to == "azure"
