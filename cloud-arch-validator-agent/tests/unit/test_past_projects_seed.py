"""The past-projects seed must lose nothing between authored YAML and what a
read gets back from Postgres.

Same shape as `test_kg_postgres_parity.py`: `build_rows()` is a pure
transform (YAML -> table rows). Two fixtures, deliberately not one:

`synthetic_rows` exercises the pipeline's own properties (ord assignment,
members/tags surviving the transform, the [NO_CONNECTIONS] diagram fallback)
against a small inline fixture built just for this file. It used to reuse
`app/references/projects/past_projects.yaml` directly for this, coupling
pipeline correctness to whatever shapes happened to be in the real company
catalog — which broke the day two placeholder example projects were deleted
from it, taking the only zero-connection example with them. Pipeline
correctness should not depend on what a rep has or hasn't caught up on
authoring.

`rows` (the real file) is kept for the round trip that specifically claims
"the seeded database matches what's actually authored" — that one should
stay real, since a synthetic stand-in would prove nothing about the actual
catalog. The dev database is assumed seeded from it already (see CLAUDE.md's
"Getting a database" section).
"""

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

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

# Real kg.service ids (see app/references/kg/services.yaml) so this stays a
# realistic shape, even though build_rows() itself never touches the
# database and so never checks the foreign key.
_SYNTHETIC_PROJECTS = """
- id: test-fixture-with-connections
  name: "Test Fixture — With Connections"
  description: "Synthetic fixture for test_past_projects_seed.py. Not a real project."
  use_case: "Pipeline test coverage"
  started_at: 2024-01-01
  ended_at: 2024-06-01
  client_name: null
  tags: [fixture-a, fixture-b]
  members:
    - {name: "Test Author One", role_on_project: "Engineer"}
    - {name: "Test Author Two", role_on_project: "Analyst"}
  services:
    - cloud-load-balancing
    - cloud-run
    - serverless-vpc-access
    - cloud-sql
  connections:
    - {source: cloud-load-balancing, target: cloud-run, note: "ingress"}
    - {source: cloud-run, target: serverless-vpc-access, note: "private egress"}
    - {source: serverless-vpc-access, target: cloud-sql, note: "private IP"}

- id: test-fixture-without-connections
  name: "Test Fixture — Without Connections"
  description: "Synthetic fixture for test_past_projects_seed.py. Not a real project."
  use_case: "Pipeline test coverage"
  started_at: 2024-02-01
  ended_at:
  client_name: null
  tags: [fixture-c]
  members:
    - {name: "Test Author Three", role_on_project: "Architect"}
  services:
    - azure-cosmos-db
    - azure-synapse
    - azure-event-grid
  connections: []
"""


@pytest.fixture(scope="module")
def rows():
    return seed.build_rows(YAML_PATH)


@pytest.fixture(scope="module")
def synthetic_rows(tmp_path_factory):
    path = tmp_path_factory.mktemp("fixtures") / "synthetic_past_projects.yaml"
    path.write_text(_SYNTHETIC_PROJECTS, encoding="utf-8")
    return seed.build_rows(path)


# --------------------------------------------------------------- pure ----


def test_a_project_with_connections_and_one_without_are_both_authored(synthetic_rows):
    """The synthetic fixture needs one of each to exercise both diagram paths."""
    with_edges = list(synthetic_rows["project_connection"])
    assert with_edges, "no project_connection rows — author a project with connections"

    projects_with_edges = {r["project_id"] for r in synthetic_rows["project_connection"]}
    all_projects = {r["id"] for r in synthetic_rows["project"]}
    assert all_projects - projects_with_edges, (
        "every project has a connection — author one with services but none, "
        "to exercise the [NO_CONNECTIONS] fallback"
    )


def test_ord_is_assigned_from_authored_list_position(synthetic_rows):
    services = [r for r in synthetic_rows["project_service"]
                if r["project_id"] == "test-fixture-with-connections"]
    assert [r["ord"] for r in services] == list(range(len(services)))
    assert [r["service_id"] for r in services] == [
        "cloud-load-balancing", "cloud-run", "serverless-vpc-access", "cloud-sql",
    ]


def test_members_and_tags_survive_the_transform(synthetic_rows):
    members = [r for r in synthetic_rows["project_member"]
               if r["project_id"] == "test-fixture-with-connections"]
    assert {r["name"] for r in members} == {"Test Author One", "Test Author Two"}

    tags = {r["tag"] for r in synthetic_rows["project_tag"]
            if r["project_id"] == "test-fixture-without-connections"}
    assert tags == {"fixture-c"}


def test_a_project_without_connections_seeds_zero_connection_rows(synthetic_rows):
    connections = [r for r in synthetic_rows["project_connection"]
                   if r["project_id"] == "test-fixture-without-connections"]
    assert connections == []


def test_synthetic_fixture_yaml_parses_with_the_real_pyyaml_loader():
    """Guards against a hand-edited literal string drifting into invalid YAML."""
    docs = yaml.safe_load(_SYNTHETIC_PROJECTS)
    assert {d["id"] for d in docs} == {
        "test-fixture-with-connections", "test-fixture-without-connections",
    }


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
    """The real round trip: YAML -> SQL -> read back through `projects_pg`.

    Picks whichever real project in the authored file has at least one
    connection, rather than a hardcoded id — the specific project this
    proves the round trip against is not the point; that every field
    survives the trip is.
    """
    import pgconn

    projects_with_edges = {r["project_id"] for r in rows["project_connection"]}
    project_id = next(iter(projects_with_edges))

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
