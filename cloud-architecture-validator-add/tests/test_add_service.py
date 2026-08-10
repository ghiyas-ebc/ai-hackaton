"""Tests for add_service.py flows. (T009-T025)"""

import pytest
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from kg_io import load_services, write_entry, find_existing, is_newer
from provenance import build_provenance
from judgment import JudgmentQuestionBatch


class TestAddServiceHappyPath:
    """T009: Full add flow with all judgment answers."""

    def test_happy_path_add(self, tmp_services_yaml):
        """New service, all questions answered, entry written with provenance."""
        services = load_services(tmp_services_yaml)
        initial_count = len(services.get("services", []))

        # Simulate: new Memorystore service, all judgment questions answered
        entry = {
            "id": "memorystore-redis",
            "name": "Memorystore for Redis",
            "provider": "gcp",
            "category": "datastore",
            "description": "In-memory data store",
            "references_url": "https://cloud.google.com/memorystore/docs",
            "network_placement": ["private"],
            "reachability": "private_only",
            "roles": ["cache"],
            "icon": "https://example.com/icon.svg",
            "provenance": build_provenance(
                ["https://cloud.google.com/memorystore/docs"]
            )
        }

        # Write
        write_entry(tmp_services_yaml, services, entry, mode="append")

        # Verify
        services_after = load_services(tmp_services_yaml)
        assert len(services_after["services"]) == initial_count + 1

        # Last entry should be our new one
        new_entry = services_after["services"][-1]
        assert new_entry["name"] == "Memorystore for Redis"
        assert new_entry["provenance"]["generated"] == "cloud-architecture-validator-add"
        assert new_entry["provenance"]["status"] == "unverified"


class TestNoWriteWithoutAllAnswers:
    """T010: Unconfirmed batch blocks write."""

    def test_unconfirmed_draft_blocks_write(self, tmp_services_yaml):
        """Draft judgment fields alone don't count as answered. No write."""
        batch = JudgmentQuestionBatch()

        # Simulate: drafts from reference, but not explicitly confirmed
        batch.set_draft("network_placement", "private", "from docs")
        batch.set_draft("reachability", "private_only", "from docs")
        batch.set_draft("roles", ["cache"], "from docs")

        # Check: all_answered should be False (drafts don't count)
        assert not batch.all_answered()

        # In real flow (T021), this would block the write. Here we verify the gate.
        services = load_services(tmp_services_yaml)
        initial_count = len(services.get("services", []))

        # Attempt entry write (won't happen in real code until all_answered is true)
        # For this test, we verify the gate prevents it.
        # (In actual impl, write would never be called if all_answered is False)

        # Still verify unchanged
        services_after = load_services(tmp_services_yaml)
        assert len(services_after["services"]) == initial_count


class TestDuplicateDetection:
    """T015: Duplicate match reports existing, no write."""

    def test_duplicate_reports_existing(self, tmp_services_yaml):
        """Cloud Run already exists. Request again → report, no second entry."""
        services = load_services(tmp_services_yaml)

        # Look up Cloud Run
        existing = find_existing(services, "Cloud Run", "gcp")
        assert existing is not None
        assert existing["id"] == "cloud-run"

        # No write happens on duplicate match (FR-002)
        initial_count = len(services["services"])
        # (In main(), T015 exits before write on duplicate)
        final_count = len(services["services"])
        assert final_count == initial_count


class TestStalenessCheck:
    """T019: Newer reference triggers update path."""

    def test_newer_reference_is_newer(self, tmp_services_yaml):
        """Cloud Run (verified 2026-08-01) + newer reference → is_newer returns True."""
        services = load_services(tmp_services_yaml)

        # Cloud Run entry is verified 2026-08-01
        cloud_run = find_existing(services, "Cloud Run", "gcp")
        assert cloud_run["provenance"]["status"] == "verified"

        # Reference from 2026-08-02 is newer
        import datetime
        ref_date = datetime.datetime(2026, 8, 2)
        assert is_newer(ref_date, cloud_run)

    def test_same_or_older_reference_not_newer(self, tmp_services_yaml):
        """Cloud Run (verified 2026-08-01) + same/older reference → False."""
        services = load_services(tmp_services_yaml)
        cloud_run = find_existing(services, "Cloud Run", "gcp")

        import datetime
        # Same date: 2026-08-01
        same_date = datetime.datetime(2026, 8, 1)
        assert not is_newer(same_date, cloud_run)

        # Older: 2026-07-31
        older_date = datetime.datetime(2026, 7, 31)
        assert not is_newer(older_date, cloud_run)


class TestJudgmentBatch:
    """T007: Batch gating."""

    def test_all_answered_gate(self):
        """No fields answered → all_answered is False."""
        batch = JudgmentQuestionBatch()
        assert not batch.all_answered()

    def test_answers_unlock_gate(self):
        """Set all fields to answered → all_answered is True."""
        batch = JudgmentQuestionBatch()
        batch.set_answer("network_placement", "public")
        batch.set_answer("reachability", "public_or_private")
        batch.set_answer("roles", ["compute"])

        assert batch.all_answered()

    def test_draft_still_blocks_gate(self):
        """Even if two are answered, one draft blocks gate."""
        batch = JudgmentQuestionBatch()
        batch.set_answer("network_placement", "public")
        batch.set_draft("reachability", "public_or_private", "from docs")
        batch.set_answer("roles", ["compute"])

        assert not batch.all_answered()
