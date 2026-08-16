"""The best-practice-reference seed must lose nothing between the authored
YAML and what a read gets back from Postgres.

Same shape as `test_past_projects_seed.py`: `build_rows()` is a pure
transform, so most of this runs without a database. The round trip that does
need one compares those pure rows against what
`projects_pg.list_best_practice_tags()`/`best_practices()` actually read
back — the dev database is assumed seeded already (see `CLAUDE.md`'s
"Getting a database" section).
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
        "seed_best_practice_references",
        _AGENT_ROOT / "db" / "seed_best_practice_references.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed = _load_seed_module()

YAML_PATH = (
    _AGENT_ROOT / "app" / "references" / "projects" / "best_practice_references.yaml"
)


@pytest.fixture(scope="module")
def rows():
    return seed.build_rows(YAML_PATH)


# --------------------------------------------------------------- pure ----


def test_the_agentic_app_tag_is_authored(rows):
    assert {r["tag"] for r in rows["best_practice_tag"]} == {"agentic_app"}


def test_ord_is_assigned_from_authored_list_position(rows):
    refs = rows["best_practice_reference"]
    assert [r["ord"] for r in refs] == list(range(len(refs)))


def test_a_reference_names_its_tag_and_provider(rows):
    ref = next(r for r in rows["best_practice_reference"]
               if r["id"] == "gcp-agentic-app-reference-architecture")
    assert ref["tag"] == "agentic_app"
    assert ref["provider"] == "gcp"
    assert "Agent Runtime" in ref["title"]


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
    "`python3 db/seed_best_practice_references.py` to include the round-trip tests",
)


@needs_db
def test_seeded_database_matches_the_authored_yaml(rows):
    import pgconn

    with pgconn.connect() as conn:
        tags = projects_pg.list_best_practice_tags(conn)
        refs = projects_pg.best_practices(conn, ["agentic_app"])

    assert {t["tag"] for t in tags} >= {r["tag"] for r in rows["best_practice_tag"]}

    from_yaml = next(
        r for r in rows["best_practice_reference"]
        if r["id"] == "gcp-agentic-app-reference-architecture"
    )
    from_db = next(r for r in refs if r["id"] == from_yaml["id"])
    assert from_db["title"] == from_yaml["title"]
    assert from_db["provider"] == from_yaml["provider"]


@needs_db
def test_best_practices_with_no_matching_tag_is_an_empty_list():
    import pgconn

    with pgconn.connect() as conn:
        assert projects_pg.best_practices(conn, ["no-such-tag"]) == []
