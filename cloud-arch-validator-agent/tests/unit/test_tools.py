"""Unit tests for the KG tool wrappers.

These assert on the rule engine's deterministic output, not on anything an LLM
says — the whole point of the design is that verdicts do not come from the
model, so they are testable here rather than in eval. What is being checked is
the wrapper layer: that vendoring did not break the imports or the data paths,
and that the tools shape output without altering verdicts.
"""

from app import tools


def test_kg_loaded_from_vendored_references() -> None:
    """The vendored app/references/kg/ resolves — 45 services, both providers."""
    assert len(tools._KG.services) == 45
    providers = {s["provider"] for s in tools._KG.services.values()}
    assert providers == {"gcp", "azure"}


def test_validate_flags_public_datastore_path() -> None:
    """Serverless compute to managed SQL trips SEC-001 with no private connector."""
    report = tools.validate_architecture("cloud-run>cloud-sql")
    assert report["summary"]["highest_severity"] == "ERROR"
    rule_ids = {f["rule_id"] for f in report["architecture"]}
    assert any(r.startswith("SEC-001") for r in rule_ids)


def test_validate_reports_all_nine_layers() -> None:
    """The L0-L8 ladder is reported in full, including the empty L7."""
    layers = tools.validate_architecture("cloud-run>cloud-sql")["layers"]
    assert len(layers) == 9


def test_unknown_service_is_answered_not_guessed() -> None:
    """An id the KG does not carry is UNKNOWN_SERVICE, never a near match."""
    result = tools.lookup_service("totally-made-up-service")
    assert result["found"] is False
    assert "UNKNOWN_SERVICE" in result["message"]

    report = tools.validate_architecture("cloud-run>totally-made-up-service")
    assert report["summary"]["uncovered"] == 1


def test_lookup_resolves_alias() -> None:
    node = tools.lookup_service("cloud-run")
    assert node["found"] is True
    assert node["provider"] == "gcp"
    assert node["category"] == "compute"


def test_search_filters_are_exact_match() -> None:
    dbs = tools.search_services(provider="gcp", category="database")
    assert dbs["count"] > 0
    assert all(s["provider"] == "gcp" and s["category"] == "database"
               for s in dbs["services"])
    assert tools.search_services(category="not-a-category")["count"] == 0


def test_translate_to_azure_maps_services() -> None:
    result = tools.translate_architecture("cloud-run>cloud-sql", "azure")
    assert result["target_provider"] == "azure"
    assert result["mapping"]


def test_export_graph_can_be_filtered_by_provider() -> None:
    full = tools.export_kg_graph()
    gcp = tools.export_kg_graph(provider="gcp")
    assert full["counts"]["nodes"] == 45
    assert 0 < gcp["counts"]["nodes"] < full["counts"]["nodes"]
    assert all(n["provider"] == "gcp" for n in gcp["nodes"])


def test_terminal_renderer_contract_and_drawio_is_not_agent_exposed() -> None:
    result = tools.render_ascii_diagram("cloud-run>cloud-sql", ascii_only=True)
    assert result["format"] == "terminal"
    assert result["diagram"].isascii()
    assert tools.render_ascii_diagram in tools.ALL_TOOLS
    assert tools.render_drawio_diagram not in tools.ALL_TOOLS


def test_kg_health_gate_passes() -> None:
    """Integrity clean and 37/37 regression — the gate any KG change must clear."""
    report = tools.check_kg_health()["report"]
    assert "passed 37/37" in report
    assert "[!]" not in report


def test_add_service_rejects_missing_judgment_field(monkeypatch) -> None:
    def fail_write(*args, **kwargs):
        raise AssertionError("missing judgment fields must not write")

    monkeypatch.setattr(tools, "_KG", tools._KG)
    assert tools.add_service_to_kg("Foo", "gcp", "public", "", ["compute"])["error"] == "missing_field"


def test_add_service_reports_existing(monkeypatch) -> None:
    existing = {"name": "Foo", "provider": "gcp", "id": "foo"}
    monkeypatch.setattr("kg_io.load_services", lambda path: {"services": [existing]})
    result = tools.add_service_to_kg("Foo", "gcp", "public", "public_only", ["compute"])
    assert result == {"written": False, "existing": existing}


def test_add_service_writes_unverified_entry(monkeypatch) -> None:
    written = {}
    monkeypatch.setattr("kg_io.load_services", lambda path: {"services": []})
    monkeypatch.setattr("kg_io.write_entry", lambda path, services, entry, mode: written.update(entry))
    monkeypatch.setattr("propose.propose_safe_fields", lambda *args: {
        "category": "compute", "description": "desc", "icon": None,
        "references_url": args[2], "sources": [args[2]],
    })
    result = tools.add_service_to_kg("Foo", "gcp", "public", "public_only", ["compute"], "https://example.test")
    assert result["written"] is True
    assert result["entry"]["provenance"]["status"] == "unverified"
    assert written["name"] == "Foo"


def test_propose_equivalence_returns_recorded_mapping() -> None:
    result = tools.propose_equivalence("cloud-run", "gcp")
    assert result["status"] == "found"


def test_propose_equivalence_marks_connectors_not_applicable() -> None:
    result = tools.propose_equivalence("serverless-vpc-access", "gcp")
    assert result["status"] == "not_applicable"


def test_propose_equivalence_does_not_guess() -> None:
    result = tools.propose_equivalence("unknown-service", "gcp")
    assert result == {"status": "unknown", "message": "no known equivalent yet"}


def test_init_stub_remains_explicit() -> None:
    result = tools.init_kg_from_catalog()
    assert result["implemented"] is False
    assert "design stub" in result["message"]


def test_all_tools_exposes_new_functions() -> None:
    assert tools.add_service_to_kg in tools.ALL_TOOLS
    assert tools.propose_equivalence in tools.ALL_TOOLS
