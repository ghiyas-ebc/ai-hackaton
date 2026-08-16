"""The diagram has to be a diagram, and it has to be the same one every time.

What this rendered before was a report shaped like a diagram: every service in
a full-width box, stacked, with no edge drawn anywhere. The topology lived only
in a list of sentences underneath, which is the one thing a reader opens a
diagram to avoid reading.

Determinism is the other half, and it is why the layout library was chosen at
all. This output goes into material a presales engineer puts in front of a
client's architect. A chart that reshuffles between two runs of the same input
cannot be reviewed, diffed, or trusted.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from app import renderer, tools

_AGENT_ROOT = Path(__file__).resolve().parents[2]


def _section(diagram: str, name: str) -> str:
    """The block under a heading, up to the next blank-line-separated heading."""
    body = diagram.split(f"\n{name}\n", 1)[1]
    for other in ("SERVICES", "CONNECTIONS", "FINDINGS", "UNKNOWN_SERVICE"):
        body = body.split(f"\n\n{other}\n", 1)[0]
    return body


# ------------------------------------------------------------- the chart --


def test_the_chart_draws_edges_between_boxes():
    """The point of the rewrite. Boxes carry the name; arrows carry the shape."""
    diagram = tools.render_ascii_diagram(
        "cloud-load-balancing>cloud-run,cloud-run>cloud-sql", width=100
    )["diagram"]
    chart = diagram.split("\nSERVICES\n")[0]

    assert "│ Cloud Load Balancing │" in chart
    assert "│ Cloud Run │" in chart
    assert "▼" in chart, "no arrowhead drawn — this is a stacked list again"
    assert "─" in chart and "│" in chart

    # The box carries the name and nothing else. Ids and typed fields moved
    # below, where they do not have to fit inside a border.
    assert "provider:" not in chart
    assert "category:" not in chart


def test_a_fan_out_draws_one_arrow_per_branch():
    diagram = tools.render_ascii_diagram(
        "cloud-run>cloud-sql,cloud-run>secret-manager", width=100
    )["diagram"]
    chart = diagram.split("\nSERVICES\n")[0]
    assert chart.count("▼") == 2


def test_the_typed_fields_are_still_reported_just_not_in_the_box():
    diagram = tools.render_ascii_diagram("cloud-run>cloud-sql", width=100)["diagram"]
    services = _section(diagram, "SERVICES")
    assert "id: cloud-run" in services
    assert "provider: gcp" in services
    assert "category: compute" in services


def test_verdicts_and_findings_sit_under_the_chart():
    diagram = tools.render_ascii_diagram("cloud-run>cloud-sql", width=100)["diagram"]
    assert "→" in _section(diagram, "CONNECTIONS")
    assert "SEC-001" in _section(diagram, "FINDINGS")
    assert diagram.index("ARCHITECTURE") < diagram.index("FINDINGS")


# ------------------------------------------------------------ determinism --


def test_repeated_renders_are_identical():
    edges = "cloud-run>cloud-sql,cloud-sql>cloud-run,cloud-run>cloud-sql"
    first = tools.render_ascii_diagram(edges, ascii_only=True)["diagram"]
    second = tools.render_ascii_diagram(edges, ascii_only=True)["diagram"]
    assert first == second


def test_the_layout_is_stable_across_processes():
    """In-process repetition cannot see the failure this guards against.

    A layout that walks a set or a dict keyed by object identity is stable
    within one process and different in the next. The library's layout is
    Sugiyama rather than force-directed, which is the property being pinned
    here — with a randomised hash seed so an accidental dependency on
    iteration order shows up rather than hiding.
    """
    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(_AGENT_ROOT)!r})
        from app import tools
        print(tools.render_ascii_diagram(
            "cloud-load-balancing>cloud-run,cloud-run>cloud-sql,"
            "cloud-run>secret-manager,pubsub>cloud-run",
            ascii_only=True)["diagram"])
    """)

    outputs = set()
    for seed in ("0", "1", "12345"):
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, cwd=_AGENT_ROOT,
            env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": seed,
                 "CAV_KG_BACKEND": "local"},
        )
        assert proc.returncode == 0, proc.stderr[-2000:]
        outputs.add(proc.stdout)
    assert len(outputs) == 1, "layout differs between processes"


# ----------------------------------------------------------------- ascii --


def test_ascii_mode_is_seven_bit_and_keeps_the_columns():
    result = tools.render_ascii_diagram(
        "cloud-load-balancing>cloud-run,cloud-run>cloud-sql",
        ascii_only=True, width=60,
    )
    diagram = result["diagram"]
    assert diagram.isascii()
    assert "→" not in diagram and "▼" not in diagram
    assert "v" in diagram and "+" in diagram

    # The transliteration is one character for one character. Anything that
    # changed a glyph's width would shear every line below it.
    unicode_chart = tools.render_ascii_diagram(
        "cloud-load-balancing>cloud-run,cloud-run>cloud-sql", width=60,
    )["diagram"].split("\nSERVICES\n")[0]
    ascii_chart = diagram.split("\nSERVICES\n")[0]
    assert [len(line) for line in ascii_chart.splitlines()] == \
           [len(line) for line in unicode_chart.splitlines()]


def test_a_real_question_mark_survives_the_transliteration():
    """`?` used to be rewritten as `_`, clobbering the author's own punctuation.

    Encoding with errors="replace" and then rewriting `?` cannot tell an
    unencodable character from one that was typed, so a selection question
    reading "Which database engine is in use?" reached the client as "in use_".
    """
    assert renderer._ascii_text("in use? café — naïve") == "in use? cafe - naive"


def test_prose_is_bounded_by_width_and_the_chart_is_not():
    """Width bounds the text. The chart's width is decided by the layout.

    Wrapping a diagram breaks it rather than fits it, so a wide fan-out gets
    the columns it needs and the caller is told so.
    """
    diagram = tools.render_ascii_diagram(
        "cloud-run>cloud-sql", ascii_only=True, width=60
    )["diagram"]
    prose = diagram.split("\nSERVICES\n", 1)[1]
    assert all(len(line) <= 60 for line in prose.splitlines())


# -------------------------------------------------------------- the edges --


def test_an_unknown_service_is_drawn_and_called_out():
    """Not omitted. A missing box would read as an architecture we validated."""
    diagram = tools.render_ascii_diagram("cloud-run>not-in-kg", ascii_only=True)["diagram"]
    chart = diagram.split("\nUNKNOWN_SERVICE\n")[0]
    assert "not-in-kg" in chart
    assert "UNKNOWN_SERVICE" in diagram


def test_empty_input_is_answered_not_crashed():
    diagram = tools.render_ascii_diagram("", ascii_only=True)["diagram"]
    assert "EMPTY_ARCHITECTURE" in diagram


def test_a_structured_finding_detail_is_a_sentence_not_a_repr():
    """PORT-002 carries a list of dicts and used to reach the page as `repr`.

    Braces, quotes and Python string escapes, in output written for a client.
    """
    diagram = tools.render_ascii_diagram(
        "cloud-load-balancing>cloud-run,cloud-run>cloud-sql", width=100
    )["diagram"]
    findings = _section(diagram, "FINDINGS")
    assert "PORT-002" in findings
    assert "{'service'" not in findings and "'options':" not in findings
    assert "azure-app-gateway" in findings


def test_two_services_sharing_a_display_name_do_not_merge_into_one_box():
    """The layout keys boxes by label, so a collision would silently fuse them."""
    services = {
        "a-svc": {"name": "Same Name", "provider": "gcp"},
        "b-svc": {"name": "Same Name", "provider": "gcp"},
    }
    labels = renderer._labels(["a-svc", "b-svc"], services)
    assert labels["a-svc"] != labels["b-svc"]


def test_renderer_rejects_invalid_width():
    with pytest.raises(ValueError, match="width"):
        renderer.render_report({}, tools._KG, width=10)


def test_render_flowchart_matches_render_report_chart_body():
    """Two entry points, one retroflow call — not two implementations that
    happen to agree today. `render_flowchart` exists for callers (a past
    project's stored topology) that have edges and labels but no rule-engine
    `report`.
    """
    edges = "cloud-load-balancing>cloud-run,cloud-run>cloud-sql"
    connectivity = [
        {"source": "cloud-load-balancing", "target": "cloud-run"},
        {"source": "cloud-run", "target": "cloud-sql"},
    ]
    labels = renderer._labels(
        renderer._node_ids({"connectivity": connectivity}), tools._KG.services
    )

    via_report = tools.render_ascii_diagram(edges, width=100)["diagram"]
    chart_from_report = (
        via_report.split("ARCHITECTURE\n\n", 1)[1]
        .split("\nSERVICES\n")[0]
        .rstrip("\n")
    )

    chart_from_flowchart = renderer.render_flowchart(connectivity, labels)

    assert chart_from_flowchart == chart_from_report
