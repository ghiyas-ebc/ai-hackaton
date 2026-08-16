"""Deterministic terminal renderer for architecture validation reports.

The diagram is a real flowchart now. What it produced before was a report that
looked like one: every service drawn as a full-width box stacked vertically,
with no edge drawn between any of them. The topology — the thing a reader is
looking at a diagram to see — existed only as a list of sentences underneath.

So the boxes carry the service name and nothing else, the arrows are drawn, and
everything that used to be crammed into a box (id, provider, category) or that
cannot be drawn at all (verdicts, findings) sits below the chart as text.

Layout comes from `retroflow`, which is Sugiyama rather than force-directed and
therefore deterministic — the same architecture renders identically on every
run and in every process. That property is not a nicety here: this output goes
into a document a presales engineer puts in front of a client's architect, and
a diagram that reshuffles between two runs of the same input is not something
anyone can review.

Nothing in this module decides anything. It formats what the rule engine
returned — no verdict, severity, equivalence, or missing element is inferred
here, and a service the graph does not know is drawn under its own id and
called out as UNKNOWN_SERVICE rather than quietly omitted.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping
from textwrap import wrap

from retroflow import FlowchartGenerator, ParseError

_MIN_WIDTH = 24

# Box width inside the chart. Distinct from `width`, which bounds the prose
# below it: the chart's total width is emergent from how the graph fans out and
# is not something the caller can clamp.
_MAX_BOX_TEXT = 24

_ARROW = {False: "→", True: ">"}
_BULLET = {False: "•", True: "*"}

# retroflow draws in Unicode box characters and has no 7-bit mode. The
# transliteration is one character for one character, which is what keeps
# columns aligned — anything that changed a glyph's width would shear every
# line below it.
_ASCII_GLYPHS = str.maketrans({
    "─": "-", "│": "|", "═": "=", "║": "|",
    "┌": "+", "┐": "+", "└": "+", "┘": "+",
    "├": "+", "┤": "+", "┬": "+", "┴": "+", "┼": "+",
    "╭": "+", "╮": "+", "╰": "+", "╯": "+",
    "╔": "+", "╗": "+", "╚": "+", "╝": "+",
    "►": ">", "◄": "<", "▼": "v", "▲": "^", "→": ">",
    "░": ":",
})


# Punctuation the knowledge graph's own prose uses. Without these the encode
# below turns each one into `?` and then into `_`, so a message reading
# "crosses the public internet — which almost always" came out as "internet _
# which", in the copy that goes to a client.
# ruff's RUF001 flags these as ambiguous characters, which is exactly what
# they are and why the table exists — it is the one place they belong.
_ASCII_PUNCTUATION = str.maketrans({
    "—": "-", "–": "-", "‑": "-", "…": "...",  # noqa: RUF001
    "‘": "'", "’": "'", "“": '"', "”": '"',  # noqa: RUF001
    " ": " ",  # noqa: RUF001
})


def _ascii_text(value: object) -> str:
    """Transliterate to 7-bit, marking only what genuinely cannot be carried.

    Encoding with `errors="replace"` and then rewriting `?` as `_` cannot tell
    an unencodable character from a question mark the author typed, so
    `selection_criteria` reading "Which database engine is in use?" arrived as
    "in use_". Accents are decomposed and their marks dropped, which is a
    faithful transliteration rather than a loss; anything still outside ASCII
    after that is genuinely unrepresentable and is marked.
    """
    text = str(value).translate(_ASCII_PUNCTUATION)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return "".join(c if c.isascii() else "_" for c in text)


def _clean(value: object, ascii_only: bool) -> str:
    text = " ".join(str(value or "").split())
    return _ascii_text(text) if ascii_only else text


def _wrap(value: object, width: int, ascii_only: bool) -> list[str]:
    text = _clean(value, ascii_only) or " "
    return wrap(text, width=max(1, width), break_long_words=True, break_on_hyphens=False) or [" "]


def _node_ids(report: Mapping[str, object]) -> list[str]:
    ids = set()
    for edge in report.get("connectivity", []):
        ids.update((str(edge.get("source", "")), str(edge.get("target", ""))))
    return sorted(i for i in ids if i)


def _labels(node_ids: Iterable[str], services: Mapping[str, Mapping[str, object]]) -> dict[str, str]:
    """Service id -> the name drawn in its box.

    Two ids sharing a display name would be merged into one box by the layout,
    silently collapsing two services into one — so a collision falls back to
    the id, which is unique by construction. `->` and newlines are stripped
    because they are the input format's own syntax.
    """
    names: dict[str, str] = {}
    for node_id in node_ids:
        node = services.get(node_id) or {}
        name = " ".join(str(node.get("name") or node_id).split())
        names[node_id] = name.replace("->", "-").replace(">", "-")

    seen: dict[str, list[str]] = {}
    for node_id, name in names.items():
        seen.setdefault(name, []).append(node_id)
    return {
        node_id: (name if len(seen[name]) == 1 else node_id)
        for node_id, name in names.items()
    }


def _flowchart(report: Mapping[str, object], labels: Mapping[str, str],
               ascii_only: bool) -> list[str]:
    """The chart itself, or an explanation of why there isn't one."""
    pairs = []
    for edge in report.get("connectivity", []):
        source, target = str(edge.get("source", "")), str(edge.get("target", ""))
        if not source or not target:
            continue
        pairs.append(f"{labels.get(source, source)} -> {labels.get(target, target)}")
    if not pairs:
        return ["[NO_CONNECTIONS] Nothing to draw."]

    generator = FlowchartGenerator(
        max_text_width=_MAX_BOX_TEXT,
        shadow=False,
        compact=True,
        direction="TB",
    )
    try:
        chart = generator.generate("\n".join(pairs))
    except ParseError as exc:
        # Reported rather than raised: a diagram is one part of the report, and
        # losing it should not take the verdicts and findings with it.
        return [f"[DIAGRAM_UNAVAILABLE] {_clean(exc, ascii_only)}"]
    if ascii_only:
        chart = chart.translate(_ASCII_GLYPHS)
    return [line.rstrip() for line in chart.splitlines()]


def render_flowchart(connectivity: list[dict], labels: Mapping[str, str], *,
                     ascii_only: bool = False) -> str:
    """Draw an arbitrary source/target edge list as a flowchart.

    A second entry point into the one retroflow call in `_flowchart`, for a
    caller that has service ids and edges but no rule-engine `report` — a
    past project's recorded topology, for instance. `render_report` and this
    both terminate in `_flowchart`, so there remains exactly one
    `FlowchartGenerator` construction in the codebase.
    """
    return "\n".join(_flowchart({"connectivity": connectivity}, labels, ascii_only))


def _detail_text(detail: object, ascii_only: bool) -> str:
    """Flatten a finding's detail.

    PORT-002 carries a list of dicts describing each ambiguous translation, and
    this used to reach the page as a `repr` — braces, quotes and all — in
    output written for a client. Each entry is rendered as the sentence it
    always was.
    """
    if not detail:
        return ""
    if isinstance(detail, Mapping):
        detail = [detail]
    if isinstance(detail, (str, bytes)):
        return _clean(detail, ascii_only)
    if not isinstance(detail, Iterable):
        return _clean(detail, ascii_only)

    parts = []
    for item in detail:
        if not isinstance(item, Mapping):
            parts.append(_clean(item, ascii_only))
            continue
        service = _clean(item.get("service", ""), ascii_only)
        options = item.get("options") or []
        text = f"{service} -> {_clean(item.get('to', ''), ascii_only)}"
        if options:
            text += f": {', '.join(_clean(o, ascii_only) for o in options)}"
        if item.get("question"):
            text += f" ({_clean(item['question'], ascii_only)})"
        parts.append(text.strip())
    return "; ".join(p for p in parts if p)


def _finding_lines(report: Mapping[str, object], ascii_only: bool) -> list[str]:
    out = []
    for finding in report.get("architecture", []):
        rule = _clean(finding.get("rule_id", "FINDING"), ascii_only)
        severity = _clean(finding.get("severity", "INFO"), ascii_only)
        message = _clean(finding.get("message", ""), ascii_only)
        detail = _detail_text(finding.get("detail"), ascii_only)
        suffix = f" [{detail}]" if detail else ""
        out.append(f"{rule} {severity}: {message}{suffix}".rstrip())
    return out


def render_report(report: Mapping[str, object], kg: object, *, width: int = 100,
                  ascii_only: bool = False) -> str:
    """Render report without recomputing any verdict or finding.

    `width` bounds the prose sections. The chart's width is decided by the
    layout — a wide fan-out needs the columns it needs, and wrapping a diagram
    would break it rather than fit it.
    """
    if not isinstance(width, int) or isinstance(width, bool) or width < _MIN_WIDTH:
        raise ValueError(f"width must be an integer >= {_MIN_WIDTH}")

    arrow, bullet = _ARROW[ascii_only], _BULLET[ascii_only]
    node_ids = _node_ids(report)
    services = getattr(kg, "services", {}) or {}
    lines: list[str] = ["ARCHITECTURE", ""]

    if not node_ids:
        lines.append("[EMPTY_ARCHITECTURE] No services or connections supplied.")
        return "\n".join(lines).rstrip()

    labels = _labels(node_ids, services)
    lines.extend(_flowchart(report, labels, ascii_only))

    unknown = [n for n in node_ids if n not in services]
    if unknown:
        lines.extend(("", "UNKNOWN_SERVICE"))
        for node_id in unknown:
            lines.extend(_wrap(
                f"{bullet} {node_id} is not in the knowledge graph. It is drawn "
                "under the id given, and nothing about it has been validated.",
                width, ascii_only))

    lines.extend(("", "SERVICES"))
    for node_id in node_ids:
        node = services.get(node_id)
        if node is None:
            text = f"{labels[node_id]} ({node_id}) — UNKNOWN_SERVICE"
        else:
            facts = [f"id: {node_id}"]
            for field in ("provider", "category"):
                if node.get(field):
                    facts.append(f"{field}: {node[field]}")
            text = f"{labels[node_id]} — {', '.join(facts)}"
        lines.extend(_wrap(f"{bullet} {text}", width, ascii_only))

    lines.extend(("", "CONNECTIONS"))
    connectivity = report.get("connectivity", [])
    if not connectivity:
        lines.append("[NONE] No directed connections.")
    for edge in connectivity:
        source = _clean(edge.get("source", ""), ascii_only)
        target = _clean(edge.get("target", ""), ascii_only)
        verdict = _clean(edge.get("verdict", ""), ascii_only)
        severity = _clean(edge.get("severity", ""), ascii_only)
        status = " ".join(x for x in (verdict, severity) if x)
        text = f"{source} {arrow} {target}"
        if status:
            text += f" [{status}]"
        if edge.get("message"):
            text += f" {_clean(edge['message'], ascii_only)}"
        lines.extend(_wrap(text, width, ascii_only))

    findings = _finding_lines(report, ascii_only)
    if findings:
        lines.extend(("", "FINDINGS"))
        for finding in findings:
            lines.extend(_wrap(f"{bullet} {finding}", width, ascii_only))
    return "\n".join(lines).rstrip()
