"""Roles are a closed vocabulary, and `kind` has to stay true.

Before the catalog, `roles` was free text with two silent failure modes.

A misspelled role inserted cleanly. `datstore` is structurally a perfectly good
string, so `check_integrity` walked past it, the node read as fully specified,
and it matched no rule for the rest of its life. That is D6's shape — a wrong
judgment field producing confident wrong answers with the health check reporting
clean — applied to the one judgment field that is a list.

And every role looked equally important. 19 of the 40 are matched by something;
the other 21 are labels. Asking an engineer to get all forty right, with nothing
saying which ones move a verdict, spends their attention where it is not needed
and leaves it thin where it is.

These tests defend the second half in particular, because it is the half that
rots: a rule that starts matching a descriptive role makes the catalog a lie,
and a lie here tells the curator a verdict-deciding field is optional.
"""

import copy
import sys
from pathlib import Path

import pytest

_AGENT_ROOT = Path(__file__).resolve().parents[2]
_KG_LIB = _AGENT_ROOT / "app" / "kg_lib"
if str(_KG_LIB) not in sys.path:
    sys.path.insert(0, str(_KG_LIB))

import check_kg  # noqa: E402
import kg as kg_module  # noqa: E402
import kg_write  # noqa: E402

sys.path.insert(0, str(_AGENT_ROOT))
from app import tools  # noqa: E402

KG_DIR = _AGENT_ROOT / "app" / "references" / "kg"


@pytest.fixture(scope="module")
def graph():
    """The committed export, read without a database."""
    return kg_module.load(backend="local")


# ------------------------------------------------------------- the catalog --


def test_the_committed_graph_has_a_clean_catalog(graph):
    problems, _ = check_kg.check_role_catalog(graph)
    assert problems == []


def test_every_role_a_service_holds_is_catalogued(graph):
    held = {r for s in graph.services.values() for r in s.get("roles", [])}
    assert held <= set(graph.role_catalog)


def test_every_role_a_rule_matches_is_load_bearing(graph):
    """The claim the split rests on, stated directly.

    `check_role_catalog` asserts it too, but only as one of several findings.
    Here it is the whole test, so a failure names the actual problem.
    """
    named = check_kg._roles_named_by_rules(graph) | set(graph.regenerate_roles)
    assert named <= graph.load_bearing_roles


def test_load_bearing_roles_say_where_they_are_read(graph):
    """The note is what makes `kind` checkable by a person.

    A role marked load-bearing with no statement of what reads it cannot be
    verified without grepping the engine, which is the work the catalog exists
    to have already done.
    """
    missing = [
        role for role in sorted(graph.load_bearing_roles)
        if not (graph.role_catalog[role].get("note") or "").strip()
    ]
    assert missing == []


def test_the_split_is_not_vacuous(graph):
    """Both kinds are populated.

    A catalog that called everything load-bearing would pass every other test
    here and change nothing about what the curator is asked for.
    """
    descriptive = set(graph.role_catalog) - graph.load_bearing_roles
    assert graph.load_bearing_roles
    assert descriptive


# ------------------------------------------------------ what the check sees --


def test_an_unknown_role_is_caught(graph):
    """The typo case. Nothing else in check_kg.py can see this."""
    broken = copy.deepcopy(graph)
    broken.services["cloud-run"]["roles"] = ["compute", "datstore"]

    problems, _ = check_kg.check_role_catalog(broken)
    assert any("datstore" in p and "cloud-run" in p for p in problems)


def test_a_descriptive_role_that_rules_match_is_caught(graph):
    """The rot case.

    A role can be demoted, or a rule can start matching one that was only ever
    a label. Either way the catalog now tells the curator that a field deciding
    verdicts is optional, which is worse than the catalog not existing.
    """
    broken = copy.deepcopy(graph)
    broken.role_catalog["datastore"] = {"kind": "descriptive"}
    broken.load_bearing_roles.discard("datastore")

    problems, _ = check_kg.check_role_catalog(broken)
    assert any("datastore" in p and "load_bearing" in p for p in problems)


def test_a_role_no_service_holds_is_a_warning_not_a_failure(graph):
    """Vocabulary ahead of the graph is untidy, not wrong."""
    ahead = copy.deepcopy(graph)
    ahead.role_catalog["queue_broker"] = {"kind": "descriptive"}

    problems, warnings = check_kg.check_role_catalog(ahead)
    assert problems == []
    assert any("queue_broker" in w for w in warnings)


def test_an_empty_catalog_reports_itself(graph):
    """Every check below it would otherwise pass vacuously.

    Reachable two ways: the local backend on a tree with no export, and a
    database migrated past 0004 but never seeded.
    """
    empty = copy.deepcopy(graph)
    empty.role_catalog = {}
    empty.load_bearing_roles = set()

    problems, _ = check_kg.check_role_catalog(empty)
    assert len(problems) == 1
    assert "empty" in problems[0]


# ------------------------------------------------------------- write gating --

CATALOG = {"compute": "load_bearing", "datastore": "load_bearing",
           "vm": "descriptive", "cache": "descriptive"}


def test_an_unknown_role_is_refused_with_the_available_set():
    """The foreign key would refuse this a moment later.

    Catching it here is about what comes back: a list of what was actually
    available is something the engineer being asked can act on, and an
    IntegrityError is not.
    """
    problem = kg_write.validate_roles(CATALOG, ["compute", "datstore"])
    assert problem["error"] == "unknown_role"
    assert problem["roles"] == ["datstore"]
    assert "datastore" in problem["allowed"]


def test_one_load_bearing_role_is_enough():
    assert kg_write.validate_roles(CATALOG, ["compute", "vm"]) is None


def test_roles_that_are_all_descriptive_warn_rather_than_refuse():
    """This was a refusal, and refusing was the wrong call.

    The entry is spelled right and describes the service accurately; what it
    lacks is a rule reading any of its roles. Blocking there puts a curator who
    wants the write to land one step from attaching `compute` to something that
    is not compute — and a wrong load-bearing role is D6's case, which is far
    worse than an entry matching nothing. An entry that matches nothing answers
    UNCOVERED, which invariant #5 calls a correct answer.
    """
    assert kg_write.validate_roles(CATALOG, ["vm", "cache"]) is None

    note = kg_write.roles_note(CATALOG, ["vm", "cache"])
    assert "UNCOVERED" in note
    assert kg_write.roles_note(CATALOG, ["compute", "vm"]) is None


# ---------------------------------------------------------- did you mean --


@pytest.mark.parametrize("typo,expected", [
    ("datstore", "datastore"),
    ("datasotre", "datastore"),
    ("http_taget", "http_target"),
    ("kubernets", "kubernetes"),
    ("serverless_vpc_conector", "serverless_vpc_connector"),
    ("event_sources", "event_source"),
])
def test_a_typo_gets_a_correction(graph, typo, expected):
    catalog = {r: e.get("kind") for r, e in graph.role_catalog.items()}
    assert kg_write.suggest_roles(catalog, [typo])[typo][0] == expected


@pytest.mark.parametrize("absent", ["monitoring", "blockchain", "queue"])
def test_a_word_the_graph_has_no_role_for_gets_no_correction(graph, absent):
    """The line between a typo and a missing concept.

    `monitoring` is not a misspelling of anything here — the graph has no role
    for it, and the honest answer is to say so. Offering the nearest string
    would be guessing, which is what this system refuses to do everywhere else.
    This is also the specific thing a vector search would get wrong: the
    nearest neighbours of a real concept are always *something*, and something
    plausible is worse than nothing.
    """
    catalog = {r: e.get("kind") for r, e in graph.role_catalog.items()}
    assert kg_write.suggest_roles(catalog, [absent]) == {}


def test_a_correction_is_offered_never_applied(graph):
    """Suggest, do not substitute.

    Silently reading `datstore` as `datastore` would be the same guess by
    another route, and it would be invisible. The refusal stands; the
    correction rides along with it.
    """
    catalog = {r: e.get("kind") for r, e in graph.role_catalog.items()}
    problem = kg_write.validate_roles(catalog, ["datstore"])
    assert problem["error"] == "unknown_role"
    assert problem["did_you_mean"] == {"datstore": ["datastore"]}


# ----------------------------------------------------------- the read path --
# Where a misspelled role does the most damage, and where there was no check at
# all. These tools tell the model an empty result is an answer, so a filter on
# `datstore` returned `count: 0` and became "no service in the graph has that
# role" — a confident wrong statement, on the path with no human in it.


@pytest.mark.parametrize("call", [
    lambda: tools.query_services(roles_any=["datstore"]),
    lambda: tools.query_services(roles_all=["datstore"]),
    lambda: tools.search_services(role="datstore"),
])
def test_a_typo_in_a_filter_is_an_error_not_an_empty_result(call):
    result = call()
    assert result["error"] == "unknown_role"
    assert result["did_you_mean"] == {"datstore": ["datastore"]}
    assert "count" not in result, "an error must not carry a count to report"


def test_a_real_role_that_matches_nothing_still_returns_zero():
    """The distinction the check exists to preserve.

    `cdn` is a real role held by one Azure service. Filtered to GCP it matches
    nothing, and that empty result is a true answer about the graph — exactly
    what the docstring tells the model to report. Only an unanswerable filter
    becomes an error.
    """
    result = tools.query_services(roles_any=["cdn"], provider="gcp")
    assert result["count"] == 0
    assert "error" not in result


def test_an_absent_role_filter_is_not_checked():
    """Empty means "no filter", not "a role called empty string"."""
    assert tools.search_services(provider="gcp")["count"] > 0
    assert tools.query_services(provider="gcp")["count"] > 0
