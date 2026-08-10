"""Deterministic terminal renderer for architecture validation reports."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from textwrap import wrap

_MIN_WIDTH = 24

_UNICODE = {
    "top_left": "┌", "top_right": "┐", "bottom_left": "└", "bottom_right": "┘",
    "horizontal": "─", "vertical": "│", "arrow": "→", "bullet": "•",
}
_ASCII = {
    "top_left": "+", "top_right": "+", "bottom_left": "+", "bottom_right": "+",
    "horizontal": "-", "vertical": "|", "arrow": ">", "bullet": "*",
}


def _ascii_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "replace").decode("ascii")
    return text.replace("?", "_")


def _clean(value: object, ascii_only: bool) -> str:
    text = " ".join(str(value or "").split())
    return _ascii_text(text) if ascii_only else text


def _wrap(value: object, width: int, ascii_only: bool) -> list[str]:
    text = _clean(value, ascii_only) or " "
    return wrap(text, width=max(1, width), break_long_words=True, break_on_hyphens=False) or [" "]


def _line(text: str, width: int) -> str:
    return text[:width].ljust(width)


def _node_label(node: Mapping[str, object] | None, node_id: str, ascii_only: bool) -> list[str]:
    if node is None:
        return [node_id, "provider: unknown", "status: UNKNOWN_SERVICE"]
    lines = [str(node.get("name") or node_id), f"id: {node_id}"]
    if node.get("provider"):
        lines.append(f"provider: {node['provider']}")
    if node.get("category"):
        lines.append(f"category: {node['category']}")
    return [_clean(line, ascii_only) for line in lines]


def _node_ids(report: Mapping[str, object], kg: object) -> list[str]:
    ids = set()
    for edge in report.get("connectivity", []):
        ids.update((str(edge.get("source", "")), str(edge.get("target", ""))))
    return sorted(i for i in ids if i)


def _finding_lines(report: Mapping[str, object], node_ids: set[str], ascii_only: bool) -> list[str]:
    out = []
    for finding in report.get("architecture", []):
        rule = _clean(finding.get("rule_id", "FINDING"), ascii_only)
        severity = _clean(finding.get("severity", "INFO"), ascii_only)
        message = _clean(finding.get("message", ""), ascii_only)
        detail = finding.get("detail")
        if isinstance(detail, Iterable) and not isinstance(detail, (str, bytes, Mapping)):
            detail_text = ", ".join(_clean(x, ascii_only) for x in detail)
        elif detail:
            detail_text = _clean(detail, ascii_only)
        else:
            detail_text = ""
        suffix = f" [{detail_text}]" if detail_text else ""
        out.append(f"{rule} {severity}: {message}{suffix}".rstrip())
    return out


def render_report(report: Mapping[str, object], kg: object, *, width: int = 100,
                  ascii_only: bool = False) -> str:
    """Render report without recomputing any verdict or finding."""
    if not isinstance(width, int) or isinstance(width, bool) or width < _MIN_WIDTH:
        raise ValueError(f"width must be an integer >= {_MIN_WIDTH}")
    glyph = _ASCII if ascii_only else _UNICODE
    inner = width - 4
    node_ids = _node_ids(report, kg)
    services = getattr(kg, "services", {})
    lines: list[str] = [_line("ARCHITECTURE", width), ""]

    if not node_ids:
        lines.append(_line("[EMPTY_ARCHITECTURE] No services or connections supplied.", width))
        return "\n".join(lines).rstrip()

    node_blocks: list[list[str]] = []
    for node_id in node_ids:
        node = services.get(node_id)
        labels = _node_label(node, node_id, ascii_only)
        wrapped = [part for label in labels for part in _wrap(label, inner, ascii_only)]
        border_top = glyph["top_left"] + glyph["horizontal"] * (width - 2) + glyph["top_right"]
        border_bottom = glyph["bottom_left"] + glyph["horizontal"] * (width - 2) + glyph["bottom_right"]
        block = [border_top]
        block.extend(glyph["vertical"] + " " + _line(label, inner) + " " + glyph["vertical"] for label in wrapped)
        block.append(border_bottom)
        node_blocks.append(block)
    for index, block in enumerate(node_blocks):
        lines.extend(block)
        if index != len(node_blocks) - 1:
            lines.append("")

    lines.extend(("", _line("CONNECTIONS", width)))
    connectivity = report.get("connectivity", [])
    if not connectivity:
        lines.append(_line("[NONE] No directed connections.", width))
    for edge in connectivity:
        source = _clean(edge.get("source", ""), ascii_only)
        target = _clean(edge.get("target", ""), ascii_only)
        verdict = _clean(edge.get("verdict", ""), ascii_only)
        severity = _clean(edge.get("severity", ""), ascii_only)
        status = " ".join(x for x in (verdict, severity) if x)
        text = f"{source} {glyph['arrow']} {target}"
        if status:
            text += f" [{status}]"
        message = edge.get("message")
        if message:
            text += f" {_clean(message, ascii_only)}"
        for part in _wrap(text, width, ascii_only):
            lines.append(_line(part, width))

    findings = _finding_lines(report, set(node_ids), ascii_only)
    if findings:
        lines.extend(("", _line("FINDINGS", width)))
        for finding in findings:
            for part in _wrap(f"{glyph['bullet']} {finding}", width, ascii_only):
                lines.append(_line(part, width))
    return "\n".join(lines).rstrip()
