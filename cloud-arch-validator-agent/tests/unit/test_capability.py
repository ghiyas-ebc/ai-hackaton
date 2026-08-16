"""Capability-tier derivation must be deterministic, and the tier vocabulary
must not silently collapse into `verdict_card.py`'s architecture-validity
tiers, which answer a different question.

`candidate_ids` and `classify` are pure — `kg.equivalents()` is an in-memory
lookup on the already-loaded `KnowledgeGraph`, so these run with no
database, using `usage` fixtures built by hand rather than read from
`project_catalog`. `app/tools.py::test_tools.py` covers the real seeded-DB
path end to end.
"""

from app import tools
from app.project_lib import capability

_KG = tools._KG


# --------------------------------------------------------- candidate_ids ----


def test_a_known_id_with_a_close_equivalent_is_a_candidate():
    """cloud-sql -> azure-sql-database is CLOSE (equivalences.yaml) — real
    data, not a fixture, so this also pins that the seeded graph still has
    it."""
    result = capability.candidate_ids(_KG, ["cloud-sql"])
    assert result["known"] == ["cloud-sql"]
    assert result["unknown"] == []
    eq_ids = {eq_id for eq_id, _level in result["equivalents"]["cloud-sql"]}
    assert "azure-sql-database" in eq_ids
    assert "azure-sql-database" in result["all_ids"]


def test_an_unknown_id_contributes_no_equivalents():
    result = capability.candidate_ids(_KG, ["not-a-real-service"])
    assert result["known"] == []
    assert result["unknown"] == ["not-a-real-service"]
    assert result["equivalents"] == {}
    assert result["all_ids"] == []


# -------------------------------------------------------------- classify ----


def test_exact_match_is_proven():
    candidates = capability.candidate_ids(_KG, ["cloud-sql"])
    usage = {"cloud-sql": [{"project_id": "p1", "name": "Project One"}]}
    result = capability.classify(["cloud-sql"], candidates, usage)
    assert result["overall_tier"] == capability.TIER_PROVEN
    assert result["components"][0]["tier"] == capability.TIER_PROVEN
    assert result["components"][0]["evidence"] == usage["cloud-sql"]


def test_close_equivalent_only_is_partial_proven():
    candidates = capability.candidate_ids(_KG, ["azure-sql-database"])
    usage = {"cloud-sql": [{"project_id": "p1", "name": "Project One"}]}
    result = capability.classify(["azure-sql-database"], candidates, usage)
    assert result["overall_tier"] == capability.TIER_PARTIAL_PROVEN
    evidence = result["components"][0]["evidence"]
    assert evidence[0]["via_service_id"] == "cloud-sql"
    assert evidence[0]["equivalence_level"] == "CLOSE"


def test_partial_level_equivalent_is_not_promoted():
    """spanner's only equivalent (azure-cosmos-db) is level PARTIAL — too
    weak a technical match to claim delivery-experience transfer on. Falls
    through to Theoretical even if the equivalent target was delivered.
    """
    candidates = capability.candidate_ids(_KG, ["spanner"])
    eq_ids = {eq_id for eq_id, level in candidates["equivalents"]["spanner"]
              if level == "PARTIAL"}
    assert "azure-cosmos-db" in eq_ids

    usage = {"azure-cosmos-db": [{"project_id": "p1", "name": "Project One"}]}
    result = capability.classify(["spanner"], candidates, usage)
    assert result["overall_tier"] == capability.TIER_THEORETICAL


def test_unknown_id_is_not_owned():
    candidates = capability.candidate_ids(_KG, ["not-a-real-service"])
    result = capability.classify(["not-a-real-service"], candidates, {})
    assert result["overall_tier"] == capability.TIER_NOT_OWNED
    assert result["components"][0]["evidence"] == []


def test_a_known_id_with_no_usage_and_no_equivalent_is_theoretical():
    candidates = capability.candidate_ids(_KG, ["bigtable"])
    result = capability.classify(["bigtable"], candidates, {})
    assert result["overall_tier"] == capability.TIER_THEORETICAL


def test_overall_tier_is_the_weakest_link_not_the_first_or_an_average():
    candidates = capability.candidate_ids(_KG, ["cloud-sql", "not-a-real-service"])
    usage = {"cloud-sql": [{"project_id": "p1", "name": "Project One"}]}
    result = capability.classify(["cloud-sql", "not-a-real-service"], candidates, usage)
    assert result["overall_tier"] == capability.TIER_NOT_OWNED
    tiers = {c["service_id"]: c["tier"] for c in result["components"]}
    assert tiers["cloud-sql"] == capability.TIER_PROVEN
    assert tiers["not-a-real-service"] == capability.TIER_NOT_OWNED


def test_classify_dedupes_preserving_first_seen_order():
    candidates = capability.candidate_ids(_KG, ["cloud-sql"])
    result = capability.classify(["cloud-sql", "cloud-sql"], candidates, {})
    assert len(result["components"]) == 1


def test_empty_service_ids_is_a_real_answer_not_an_error():
    result = capability.classify([], {"unknown": [], "equivalents": {}}, {})
    assert result == {"overall_tier": None, "components": []}
