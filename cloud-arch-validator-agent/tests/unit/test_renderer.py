from app import renderer, tools


def test_unicode_render_contains_nodes_metadata_edges_and_findings():
    result = tools.render_ascii_diagram("cloud-run>cloud-sql", width=100)
    diagram = result["diagram"]
    assert "Cloud Run" in diagram
    assert "Cloud SQL" in diagram
    assert "provider: gcp" in diagram
    assert "category: compute" in diagram
    assert "cloud-run" in diagram and "cloud-sql" in diagram
    assert "→" in diagram
    assert "SEC-001" in diagram


def test_ascii_render_is_ascii_and_width_bounded():
    result = tools.render_ascii_diagram("cloud-run>cloud-sql", ascii_only=True, width=60)
    diagram = result["diagram"]
    assert diagram.isascii()
    assert all(len(line) <= 60 for line in diagram.splitlines())
    assert "→" not in diagram
    assert ">" in diagram
    assert "cloud-run" in diagram and "cloud-sql" in diagram


def test_unknown_service_is_explicit():
    result = tools.render_ascii_diagram("cloud-run>not-in-kg", ascii_only=True)
    assert "UNKNOWN_SERVICE" in result["diagram"]
    assert "not-in-kg" in result["diagram"]


def test_cycles_duplicates_and_empty_input_are_safe():
    edges = "cloud-run>cloud-sql,cloud-sql>cloud-run,cloud-run>cloud-sql"
    first = tools.render_ascii_diagram(edges, ascii_only=True)["diagram"]
    second = tools.render_ascii_diagram(edges, ascii_only=True)["diagram"]
    assert first == second
    assert first.count("cloud-run") >= 2
    empty = tools.render_ascii_diagram("", ascii_only=True)["diagram"]
    assert "EMPTY_ARCHITECTURE" in empty


def test_renderer_rejects_invalid_width():
    try:
        renderer.render_report({}, tools._KG, width=10)
    except ValueError as exc:
        assert "width" in str(exc)
    else:
        raise AssertionError("expected invalid width to fail")
