"""The past-projects seed must lose nothing between the authored YAML and
what a read gets back from Postgres.

Same shape as `test_kg_postgres_parity.py`: `build_rows()` is a pure
transform (YAML -> table rows), so most of this runs without a database. The
round trip that does need one compares those pure rows against what
`projects_pg.get_project()` actually reads back — no insert/cleanup dance,
since `app/references/projects/past_projects.yaml` is the fixture and the dev
database is assumed seeded from it already (see `CLAUDE.md`'s "Getting a
database" section).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_AGENT_ROOT = Path(__file__).resolve().parents[2]
_KG_LIB = _AGENT_ROOT / "app" / "kg_lib"
if str(_KG_LIB) not in sys.path:
    sys.path.insert(0, str(_KG_LIB))

from app.project_lib import projects_pg  # noqa: E402


def _load_seed_module():
    """db/ is not a package; load the seed script by path."""
    spec = importlib.util.spec_from_file_location(
        "seed_past_projects", _AGENT_ROOT / "db" / "seed_past_projects.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed = _load_seed_module()

YAML_PATH = _AGENT_ROOT / "app" / "references" / "projects" / "past_projects.yaml"


@pytest.fixture(scope="module")
def rows():
    return seed.build_rows(YAML_PATH)


# --------------------------------------------------------------- pure ----


def test_a_project_with_connections_and_one_without_are_both_authored(rows):
    """The fixture file needs one of each to exercise both diagram paths."""
    with_edges = list(rows["project_connection"])
    assert with_edges, "no project_connection rows — author a project with connections"

    projects_with_edges = {r["project_id"] for r in rows["project_connection"]}
    all_projects = {r["id"] for r in rows["project"]}
    assert all_projects - projects_with_edges, (
        "every project has a connection — author one with services but none, "
        "to exercise the [NO_CONNECTIONS] fallback"
    )


def test_ord_is_assigned_from_authored_list_position(rows):
    services = [r for r in rows["project_service"]
                if r["project_id"] == "retailco-cloud-platform-migration"]
    assert [r["ord"] for r in services] == list(range(len(services)))
    assert [r["service_id"] for r in services] == [
        "cloud-load-balancing", "cloud-run", "serverless-vpc-access", "cloud-sql",
    ]


def test_members_and_tags_survive_the_transform(rows):
    members = [r for r in rows["project_member"]
               if r["project_id"] == "retailco-cloud-platform-migration"]
    assert {r["name"] for r in members} == {"Jane Doe", "John Smith"}

    tags = {r["tag"] for r in rows["project_tag"]
            if r["project_id"] == "fintechco-azure-data-platform"}
    assert tags == {"fintech", "azure", "assessment"}


def test_a_project_without_connections_seeds_zero_connection_rows(rows):
    connections = [r for r in rows["project_connection"]
                   if r["project_id"] == "fintechco-azure-data-platform"]
    assert connections == []


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
    "`python3 db/seed_past_projects.py` to include the round-trip tests",
)


@needs_db
def test_seeded_database_matches_the_authored_yaml(rows):
    """The real round trip: YAML -> SQL -> read back through `projects_pg`."""
    import pgconn

    project_id = "retailco-cloud-platform-migration"
    with pgconn.connect() as conn:
        from_db = projects_pg.get_project(conn, project_id)
    assert from_db is not None, (
        f"{project_id} not found — run `python3 db/seed_past_projects.py` first"
    )

    from_yaml = next(r for r in rows["project"] if r["id"] == project_id)
    assert from_db["name"] == from_yaml["name"]
    assert from_db["description"] == from_yaml["description"]
    assert str(from_db["started_at"]) == str(from_yaml["started_at"])

    assert [s["service_id"] for s in from_db["services"]] == [
        r["service_id"] for r in rows["project_service"] if r["project_id"] == project_id
    ]
    assert [
        (c["source_service_id"], c["target_service_id"]) for c in from_db["connections"]
    ] == [
        (r["source_service_id"], r["target_service_id"])
        for r in rows["project_connection"] if r["project_id"] == project_id
    ]
    assert [m["name"] for m in from_db["members"]] == [
        r["name"] for r in rows["project_member"] if r["project_id"] == project_id
    ]


@needs_db
def test_a_project_with_no_connections_round_trips_to_an_empty_list():
    import pgconn

    with pgconn.connect() as conn:
        from_db = projects_pg.get_project(conn, "fintechco-azure-data-platform")
    assert from_db is not None
    assert from_db["connections"] == []
