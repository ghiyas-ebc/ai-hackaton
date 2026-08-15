"""Deterministic eval metric: a verdict claim must be backed by a tool response.

Why this exists rather than an LLM judge. The E05 trace showed the agent
rendering a full Verdict Card — difficulty, tiered findings, invented rule ids
`L3-D-01` and `L8-P-02` — with zero tool calls in the trace, while the built-in
`hallucination` metric scored it 1.0. That metric grades the response against
the *prompt*, so a fabricated verdict that never contradicts the user reads as
perfectly grounded. The failure this project cares about is invariant #1
(verdicts come from the rule engine, never the model), and that is a structural
property of the trace, not a matter of opinion — so it is checked with code, not
with a judge that can be wrong about it.

Score is 0.0 (violation) or 1.0 (clean). `explanation` names what was found so a
failure is actionable without opening the trace.
"""

import re
from pathlib import Path

# Tools whose response is a legitimate source of a verdict claim.
VERDICT_TOOLS = {
    "generate_verdict_card",
    "validate_architecture",
    "translate_architecture",
}

# Markers that mean "this response is asserting an engine verdict". Indonesian
# and English, because SKILL.md replies in the user's language (D8).
VERDICT_MARKERS = (
    "verdict card",
    "kartu keputusan",
    "difficulty_reason",
    "kesulitan:",
    "difficulty:",
    "requires deep review",
    "memerlukan peninjauan mendalam",
    "theoretically possible",
    "teoritis mungkin",
)

# Shapes a real rule id can take, per architecture-rules.yaml: a layer id (L0-L8)
# or a PREFIX-NNN-SLUG rule id. Anything matching this shape that is not in the
# actual rule set was invented by the model.
RULE_ID_RE = re.compile(r"\b(?:L[0-9]|[A-Z]{3,4})-[A-Z0-9-]{2,}\b")

def _kg_dir() -> Path:
    """Locate `app/references/kg` without relying on `__file__`.

    `agents-cli eval grade` compiles a `custom_function_file` with `exec` and no
    `__file__` in its globals, so a path anchored on this module's location
    raises `NameError` there while working fine under pytest. Walk up from
    whichever anchor is available instead.
    """
    anchors = []
    module_path = globals().get("__file__")
    if module_path:
        anchors.append(Path(module_path).resolve().parent)
    anchors.append(Path.cwd().resolve())
    for anchor in anchors:
        for candidate in (anchor, *anchor.parents):
            kg = candidate / "app" / "references" / "kg"
            if kg.is_dir():
                return kg
    return Path("app/references/kg")


def _known_rule_ids() -> set[str]:
    """Rule and layer ids from every KG file, as literal text — no YAML parse.

    Both `architecture-rules.yaml` (L2-L8) and `connectivity-rules.yaml` (L1)
    define ids the agent may legitimately cite, and the agent routinely cites a
    shortened form (`SEC-003` for `SEC-003-COMPUTE-EXPOSED`), so every
    dash-delimited prefix of a real id counts as real too. Only an id sharing no
    prefix with anything in the KG was actually invented.
    """
    known: set[str] = set()
    kg_dir = _kg_dir()
    if not kg_dir.is_dir():
        return known
    for path in sorted(kg_dir.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        for rule_id in re.findall(r"^\s*-?\s*id:\s*([A-Za-z0-9-]+)", text, re.MULTILINE):
            segments = rule_id.split("-")
            for end in range(1, len(segments) + 1):
                known.add("-".join(segments[:end]))
    return known


def _tool_names(agent_data) -> set[str]:
    """Every tool that actually returned into the conversation."""
    names: set[str] = set()
    if not isinstance(agent_data, dict):
        return names
    for turn in agent_data.get("turns") or []:
        for event in turn.get("events") or []:
            for part in ((event.get("content") or {}).get("parts")) or []:
                response = part.get("function_response")
                if response and response.get("name"):
                    names.add(response["name"])
    return names


def _response_text(instance) -> str:
    """Final response text, however this instance carries it."""
    response = instance.get("response")
    if isinstance(response, str):
        return response
    parts = []
    agent_data = instance.get("agent_data")
    if isinstance(agent_data, dict):
        for turn in agent_data.get("turns") or []:
            for event in turn.get("events") or []:
                for part in ((event.get("content") or {}).get("parts")) or []:
                    if part.get("text"):
                        parts.append(part["text"])
    return "\n".join(parts)


def evaluate(instance):
    text = _response_text(instance)
    lowered = text.lower()
    called = _tool_names(instance.get("agent_data"))

    claims_verdict = any(marker in lowered for marker in VERDICT_MARKERS)
    grounded = bool(called & VERDICT_TOOLS)

    problems = []
    if claims_verdict and not grounded:
        problems.append(
            "response asserts an engine verdict but no "
            f"{'/'.join(sorted(VERDICT_TOOLS))} response is in the trace"
        )

    invented = sorted(set(RULE_ID_RE.findall(text)) - _known_rule_ids())
    if invented:
        problems.append(f"cites rule ids absent from the rule set: {', '.join(invented)}")

    # A tool call rendered as literal text never reached the runtime (E06).
    if "tool_code" in lowered or "default_api:" in lowered:
        problems.append("emitted a tool call as response text instead of invoking it")

    if problems:
        return {"score": 0.0, "explanation": "; ".join(problems)}
    return {
        "score": 1.0,
        "explanation": (
            f"verdict claim backed by {sorted(called & VERDICT_TOOLS)}"
            if claims_verdict
            else "no verdict claimed; nothing to ground"
        ),
    }
