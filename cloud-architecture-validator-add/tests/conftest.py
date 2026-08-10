"""Shared test fixtures for add_service.py tests."""

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_services_yaml(tmp_path):
    """Copy small fixture KG (2-3 services) to tmp, return path."""
    # Minimal fixture: GCP LB, GCP Cloud Run, GCP Cloud SQL (one with verified provenance)
    fixture_kg = {
        "services": [
            {
                "id": "cloud-load-balancing",
                "name": "Cloud Load Balancing",
                "provider": "gcp",
                "category": "networking",
                "description": "Distribute traffic across resources",
                "references_url": "https://cloud.google.com/load-balancing/docs",
                "network_placement": ["public"],
                "reachability": "public_or_private",
                "roles": ["network-endpoint"],
                "icon": "https://example.com/icon.svg",
                "provenance": {
                    "generated": "manual",
                    "status": "manual"
                }
            },
            {
                "id": "cloud-run",
                "name": "Cloud Run",
                "provider": "gcp",
                "category": "compute",
                "description": "Serverless compute",
                "references_url": "https://cloud.google.com/run/docs",
                "network_placement": ["both"],
                "reachability": "public_or_private",
                "roles": ["compute-platform"],
                "icon": "https://example.com/icon.svg",
                "provenance": {
                    "generated": "manual",
                    "status": "verified",
                    "verified": "2026-08-01"
                }
            },
            {
                "id": "cloud-sql",
                "name": "Cloud SQL",
                "provider": "gcp",
                "category": "datastore",
                "description": "Managed relational database",
                "references_url": "https://cloud.google.com/sql/docs",
                "network_placement": ["private"],
                "reachability": "private_only",
                "roles": ["database"],
                "icon": "https://example.com/icon.svg",
                "provenance": {
                    "generated": "manual",
                    "status": "unverified"
                }
            }
        ]
    }

    yml_path = tmp_path / "services.yaml"
    import yaml
    with open(yml_path, "w") as f:
        yaml.dump(fixture_kg, f, default_flow_style=False, sort_keys=False)

    return yml_path
