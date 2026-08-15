"""The migration from YAML to Postgres must lose nothing.

"Nothing" is a strong claim, so it is checked against the strongest available
reference: the YAML loader that has been the source of truth all along. If the
graph the database produces is not identical to the graph the files produce,
these tests fail, and the difference is named rather than discovered later in a
verdict.

Most of this runs with no database. `db/seed_from_yaml.py:build_rows()` is a
pure transform and `kg_pg.kg_from_rows()` is a pure builder, so chaining them
exercises the entire migration except the SQL round trip. The tests that do
need Postgres are marked and skip when the configured DSN does not answer —
a developer without a database running should see the migration verified, not
a wall of errors about a container they were never told to start.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_AGENT_ROOT = Path(__file__).resolve().parents[2]
_KG_LIB = _AGENT_ROOT / "app" / "kg_lib"
if str(_KG_LIB) not in sys.path:
    sys.path.insert(0, str(_KG_LIB))

import kg as kg_module  # noqa: E402
import kg_pg  # noqa: E402


def _load_seed_module():
    """db/ is not a package; load the seed script by path."""
    spec = importlib.util.spec_from_file_location(
        "seed_from_yaml", _AGENT_ROOT / "db" / "seed_from_yaml.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed = _load_seed_module()

# The YAML the agent actually vendors, not the sibling skill's copy.
KG_DIR = _AGENT_ROOT / "app" / "references" / "kg"


@pytest.fixture(scope="module")
def from_yaml():
    return kg_module.load(backend="local")


@pytest.fixture(scope="module")
def rows():
    return seed.build_rows(KG_DIR)


@pytest.fixture(scope="module")
def from_rows(rows):
    return kg_pg.kg_from_rows(rows)


# --------------------------------------------------------------- parity ----

ATTRIBUTES = [
    "services",
    "conn_rules",
    "conn_fallback",
    "arch_rules",
    "arch_layers",
    "aliases",
    "overrides",
    "alternatives",
    "regenerate_roles",
    "equivalences",
    "icons",
]


@pytest.mark.parametrize("attr", ATTRIBUTES)
def test_every_kg_attribute_survives_the_migration(from_yaml, from_rows, attr):
    """Compared attribute by attribute so a failure says which one drifted."""
    assert getattr(from_rows, attr) == getattr(from_yaml, attr)


def test_service_order_is_preserved(from_yaml, from_rows):
    """validate.py's `by_role(...)[0]` makes row order a verdict input.

    Sorting services by id instead of authored order changes which connector
    gets inserted into a user's architecture while every other assertion here
    still passes, so it is checked on its own.
    """
    assert list(from_rows.services) == list(from_yaml.services)


def test_connectivity_rules_keep_first_match_order(from_yaml, from_rows):
    """Layer 1 is first-match-wins; reordering it rewrites verdicts silently."""
    assert [r["id"] for r in from_rows.conn_rules] == [
        r["id"] for r in from_yaml.conn_rules
    ]


def test_optional_fields_stay_absent_rather_than_null(from_rows):
    """SQL has NULL where YAML had nothing, and downstream code reads presence.

    `gate` on a layer and `needs_role` on a rule are both checked by presence,
    so a column of NULLs faithfully rendered as `{"gate": None}` would be a
    different graph that no equality check on values alone would catch.
    """
    gated = [layer for layer in from_rows.arch_layers if "gate" in layer]
    assert [layer["id"] for layer in gated] == ["L1"]
    assert all("needs_role" not in r or r["needs_role"] for r in from_rows.conn_rules)


def test_yaml_comments_are_carried_across_not_dropped(rows):
    """The repo's style rule puts the reasoning in the comments.

    Migrating the data and dropping the commentary would leave a future editor
    with `serverless_offvpc` and no statement of what it means, so the seed
    lifts both the per-entry notes and each file's header out of the raw text.
    """
    docs = {r["key"]: r["note"] for r in rows["kg_setting"] if r["key"].startswith("doc:")}
    assert set(docs) == {
        "doc:services",
        "doc:connectivity-rules",
        "doc:architecture-rules",
        "doc:equivalences",
        "doc:overrides",
        "doc:icons",
    }
    assert "serverless_offvpc" in docs["doc:services"]
    assert "FIRST MATCH WINS" in docs["doc:connectivity-rules"].upper()

    # Per-entry commentary, from both places the files put it: above the entry
    # (architecture rules) and inside its body (services).
    assert [r for r in rows["architecture_rule"] if r["rationale"]]
    annotated = {r["id"]: r["rationale"] for r in rows["service"] if r["rationale"]}
    assert "WAF is a feature" in annotated.get("azure-app-gateway", "")


def test_provenance_gate_is_representable(rows):
    """D21's three-valued status survives as data the CHECK constraint reads."""
    statuses = {r["prov_status"] for r in rows["service"]}
    assert statuses <= {"manual", "unverified", "verified"}
    for row in rows["service"]:
        if row["prov_status"] == "verified":
            assert row["prov_verified"] is not None


# ------------------------------------------------- round trip (needs DB) ----


def _database_available():
    try:
        import pgconn

        return pgconn.reachable()
    except Exception:
        return False


needs_db = pytest.mark.skipif(
    not _database_available(),
    reason="no Postgres at CAV_PG_DSN; run `docker compose up -d db` and "
    "`python3 db/seed_from_yaml.py` to include the round-trip tests",
)


# `services` and `icons` are the two the curator writes to, so they are checked
# for containment below instead. The rest are rule tables that nothing writes at
# runtime, and equality is the right assertion for them.
WRITABLE = {"services", "icons"}


@needs_db
@pytest.mark.parametrize("attr", [a for a in ATTRIBUTES if a not in WRITABLE])
def test_seeded_database_matches_the_yaml(from_yaml, attr):
    """The real round trip: YAML -> SQL -> KnowledgeGraph."""
    from_db = kg_module.load(backend="postgres")
    assert getattr(from_db, attr) == getattr(from_yaml, attr)


@needs_db
def test_every_migrated_service_survived_the_round_trip(from_yaml):
    """Containment, not equality — the claim is that nothing was lost.

    Equality would additionally assert that nobody has added a service since
    the seed, which is not a property worth defending: the graph is a database
    the curator writes to, and a legitimate write is not a regression.
    """
    from_db = kg_module.load(backend="postgres")
    for service_id, entry in from_yaml.services.items():
        assert service_id in from_db.services, f"{service_id} did not survive"
        assert from_db.services[service_id] == entry

    for service_id, mapping in from_yaml.icons["services"].items():
        assert from_db.icons["services"][service_id] == mapping
    assert from_db.icons["categories"] == from_yaml.icons["categories"]

    # And the migrated entries still hold the front of the ordering, which is
    # what `by_role(...)[0]` reads.
    assert list(from_db.services)[: len(from_yaml.services)] == list(from_yaml.services)


@needs_db
def test_engine_gate_still_passes_against_postgres():
    """Clean integrity and 37/37 regression, reading from the database.

    The rule engine was not rewritten for this move, so this is the assertion
    that the claim holds: the same fixture, the same expected results, a
    different store underneath.
    """
    import check_kg

    kg = kg_module.load(backend="postgres")
    passed, failed, _deviations = check_kg.check_regression(kg)
    assert not failed, failed
    assert passed == 37
