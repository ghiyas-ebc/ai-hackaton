"""Whether the company has proven experience with a prospective ask.

A different question from architecture validity (`verdict_card.py`'s
`Proven`/`Theoretically Possible`/`Requires Deep Review` tiers, which judge
whether the rule engine covered a connection and whether a KG entry has been
human-verified). This module never touches `verdict_card.py` or
`project_catalog`'s own history from that angle — it asks whether *we* have
delivered something, derived from `project_catalog` and `kg.equivalence`,
never guessed.

Same fetch/pure split this repo uses everywhere for testability
(`kg_pg.py`'s `fetch_rows`/`kg_from_rows`, the seed scripts' `build_rows`/
`apply`): `candidate_ids` and `classify` are pure — `kg.equivalents()` is
already an in-memory lookup, no I/O — so only `assess()` needs a connection,
to read `project_catalog`.
"""

TIER_PROVEN = "Proven"
TIER_PARTIAL_PROVEN = "Partial Proven"
TIER_THEORETICAL = "Theoretical"
TIER_NOT_OWNED = "Not Owned"

_TIER_ORDER = {
    TIER_NOT_OWNED: 0,
    TIER_THEORETICAL: 1,
    TIER_PARTIAL_PROVEN: 2,
    TIER_PROVEN: 3,
}

# Equivalence "level" (EXACT/CLOSE/PARTIAL, kg.equivalence_target.level) is a
# different axis from the capability tier above that happens to share one of
# its words — level says how close a cross-provider technical match is; tier
# says how proven our delivery experience is. Only EXACT/CLOSE cross into
# Partial Proven; PARTIAL is too weak a technical match to claim delivery-
# experience transfer on.
_EQUIVALENCE_LEVELS_COUNTED = {"EXACT", "CLOSE"}


def candidate_ids(kg, service_ids: list[str]) -> dict:
    """Pure. No I/O. For each id: itself, plus cross-provider equivalents —
    everything worth checking against project_catalog.

    An id not in kg.services (e.g. a searched-but-not-found label like
    'agent-runtime') is not an error here — it lands in `unknown` and is
    classified Not Owned downstream, the same standing UNKNOWN_SERVICE has
    elsewhere in this codebase.
    """
    known = [i for i in service_ids if i in kg.services]
    unknown = [i for i in service_ids if i not in kg.services]
    equivalents = {}
    all_ids = set(known)
    for sid in known:
        other = "azure" if kg.services[sid]["provider"] == "gcp" else "gcp"
        targets, _criteria = kg.equivalents(sid, other)
        equivalents[sid] = [(t["id"], t.get("level")) for t in targets]
        all_ids.update(t["id"] for t in targets)
    return {
        "known": known,
        "unknown": unknown,
        "equivalents": equivalents,
        "all_ids": sorted(all_ids),
    }


def classify(service_ids: list[str], candidates: dict, usage: dict) -> dict:
    """Pure. `usage`: service_id -> [{project_id, name}, ...], already
    fetched. Dedupes `service_ids`, preserving first-seen order.
    """
    components, seen = [], set()
    for sid in service_ids:
        if not sid or sid in seen:
            continue
        seen.add(sid)

        if sid in candidates["unknown"]:
            components.append({"service_id": sid, "tier": TIER_NOT_OWNED, "evidence": []})
            continue

        direct = usage.get(sid, [])
        if direct:
            components.append({"service_id": sid, "tier": TIER_PROVEN, "evidence": direct})
            continue

        partial = [
            {**proj, "via_service_id": eq_id, "equivalence_level": level}
            for eq_id, level in candidates["equivalents"].get(sid, [])
            if level in _EQUIVALENCE_LEVELS_COUNTED
            for proj in usage.get(eq_id, [])
        ]
        if partial:
            components.append({"service_id": sid, "tier": TIER_PARTIAL_PROVEN, "evidence": partial})
            continue

        components.append({"service_id": sid, "tier": TIER_THEORETICAL, "evidence": []})

    if not components:
        return {"overall_tier": None, "components": []}
    overall = min(components, key=lambda c: _TIER_ORDER[c["tier"]])["tier"]
    return {"overall_tier": overall, "components": components}


def assess(kg, conn, service_ids: list[str], pattern_tags: list[str] | None = None) -> dict:
    """I/O entry point: candidate_ids (pure) -> project_catalog (DB) ->
    classify (pure), plus any matching best-practice references for the
    supplied tags.

    Tags are the caller's job to select from a closed set
    (`projects_pg.list_best_practice_tags`) — this does not invent or infer
    one. `best_practice_references` is returned whenever tags were supplied,
    regardless of tier; it is the agent's instruction, not this function,
    that says these matter most when the tier is Theoretical or Not Owned.
    """
    from app.project_lib import projects_pg

    candidates = candidate_ids(kg, service_ids)
    usage = (
        projects_pg.projects_using(conn, candidates["all_ids"])
        if candidates["all_ids"]
        else {}
    )
    result = classify(service_ids, candidates, usage)
    result["best_practice_references"] = projects_pg.best_practices(conn, pattern_tags or [])
    return result
