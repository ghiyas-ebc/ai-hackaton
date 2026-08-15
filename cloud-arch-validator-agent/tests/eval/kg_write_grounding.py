"""Deterministic eval metric: a write/refusal claim must be backed by a tool
response, same reasoning as tests/eval/verdict_grounding.py applied to the
curator's write boundary instead of the validator's verdicts.

The curator is the system's only writer (D25/D26 in the parent repo). Whether
a service was actually written, refused for an unknown role, or written with a
role warning is a structural fact about the trace -- which `add_service_to_kg`
/ `query_services` / `search_services` response actually came back -- not a
matter a judge can settle by reading the final response text. Score is 0.0
(a claim with nothing backing it) or 1.0 (clean). `explanation` names what was
found so a failure is actionable without opening the trace.
"""

WRITE_TOOLS = {"add_service_to_kg"}
ROLE_LOOKUP_TOOLS = {"add_service_to_kg", "query_services", "search_services"}

# Indonesian and English, because SKILL.md replies in the user's language (D8).
SUCCESS_MARKERS = (
    "berhasil ditambahkan",
    "sudah ditambahkan",
    "telah ditambahkan",
    "successfully added",
    "was added",
    "has been added",
)

# A role/typo refusal or a role-warning caveat is only ever expressed as a
# sentence about a *role* -- but the specific wording is not a fixed phrase.
# A real response wrote "peran (`role`) yang diberikan, `datstore`, tidak
# dikenal" -- "peran" and "tidak dikenal" five words apart -- and another
# wrote "peringatan peran (*role warning*)", matching no contiguous phrase at
# all. Matching a single fixed phrase either false-positived (bare "tidak
# dikenal" is also how UNKNOWN_SERVICE is worded, with no role involved: it
# flagged E01/E03/E08, none of which ever mention a role) or silently missed
# the real thing (E12's actual warning phrasing matched no marker in the
# original list, so the check never ran at all -- a false negative that
# happened to still score 1.0 by having nothing to check).
#
# The fix: require a role-context word to co-occur with a looser refusal/
# warning word, rather than one long phrase to match exactly. The role-context
# gate is what actually protects against E01/E03/E08 -- their responses never
# mention "role"/"peran" anywhere, regardless of how loose the other word is.
ROLE_CONTEXT_WORDS = ("role", "peran")
REFUSAL_WORDS = ("tidak dikenal", "unknown_role", "tidak valid", "not valid")
WARNING_WORDS = ("warning", "peringatan", "load-bearing", "load bearing")


def _response_text(instance) -> str:
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


def _tool_responses(agent_data, names: set[str]) -> list[dict]:
    """Every response body from a tool in `names` that actually returned."""
    found = []
    if not isinstance(agent_data, dict):
        return found
    for turn in agent_data.get("turns") or []:
        for event in turn.get("events") or []:
            for part in ((event.get("content") or {}).get("parts")) or []:
                response = part.get("function_response")
                if response and response.get("name") in names:
                    body = response.get("response")
                    if isinstance(body, dict):
                        found.append(body)
    return found


def evaluate(instance):
    text = _response_text(instance)
    lowered = text.lower()
    agent_data = instance.get("agent_data")

    write_responses = _tool_responses(agent_data, WRITE_TOOLS)
    role_responses = _tool_responses(agent_data, ROLE_LOOKUP_TOOLS)

    wrote = any(r.get("written") is True for r in write_responses)
    already_existed = any(r.get("error") == "already_exists" for r in write_responses)
    refused_unknown_role = any(r.get("error") == "unknown_role" for r in role_responses)
    role_warned = any(r.get("role_warning") for r in write_responses)

    mentions_role = any(word in lowered for word in ROLE_CONTEXT_WORDS)
    claims_success = any(marker in lowered for marker in SUCCESS_MARKERS)
    claims_refusal = mentions_role and any(w in lowered for w in REFUSAL_WORDS)
    claims_warning = mentions_role and any(w in lowered for w in WARNING_WORDS)

    problems = []
    # "Already exists" is also a legitimate, truthful thing to report as a
    # non-failure -- a repeat eval run against the same Postgres will hit it
    # on every write case after the first, so it counts as grounded too.
    if claims_success and not (wrote or already_existed):
        problems.append(
            "response claims a service was added, but no add_service_to_kg "
            "response in the trace shows written: true or already_exists"
        )
    if claims_refusal and not refused_unknown_role:
        problems.append(
            "response claims a role/name was refused as unknown, but no trace "
            "response carries error: unknown_role"
        )
    if claims_warning and not role_warned:
        problems.append(
            "response surfaces a role-warning-style caveat, but no trace "
            "response carries a role_warning"
        )

    if problems:
        return {"score": 0.0, "explanation": "; ".join(problems)}
    return {
        "score": 1.0,
        "explanation": (
            f"write/refusal claim backed by trace (wrote={wrote}, "
            f"already_existed={already_existed}, "
            f"refused_unknown_role={refused_unknown_role}, "
            f"role_warned={role_warned})"
        ),
    }
