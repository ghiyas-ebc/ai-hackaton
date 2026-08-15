"""The schema has a version and a way forward.

`schema.sql` full of `CREATE TABLE IF NOT EXISTS` works exactly once. Re-running
it against a populated database is a no-op, so the second schema change had
nowhere to go except an `ALTER` typed at a prompt against live data, with
nothing recording that it happened and no way for the next developer to get the
same schema.

Most of what matters here is checkable without a database — filenames, ordering,
and the checksum guard are properties of the files and the runner. The tests
that need Postgres check that a real database ends up at the expected version.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_AGENT_ROOT = Path(__file__).resolve().parents[2]
_KG_LIB = _AGENT_ROOT / "app" / "kg_lib"
for p in (str(_KG_LIB), str(_AGENT_ROOT / "db")):
    if p not in sys.path:
        sys.path.insert(0, p)


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, _AGENT_ROOT / "db" / filename
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migrate = _load("migrate", "migrate.py")
MIGRATIONS = _AGENT_ROOT / "db" / "migrations"


# ------------------------------------------------------- files, no database --


def test_every_migration_is_discovered_in_order():
    found = migrate.discover(MIGRATIONS)
    assert found, "no migrations found"
    versions = [int(p.name[:4]) for p in found]
    assert versions == sorted(versions)
    assert versions[0] == 1, "numbering starts at 0001"


def test_filenames_follow_the_convention(tmp_path):
    """A stray .sql in the directory is a mistake, not something to skip.

    Silently ignoring it is how a migration gets written, committed, and never
    applied anywhere.
    """
    (tmp_path / "0001_fine.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "not-a-migration.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(SystemExit, match="not a migration filename"):
        migrate.discover(tmp_path)


def test_duplicate_version_numbers_are_refused(tmp_path):
    """Two files claiming 0002 would apply in filesystem order, which is not an
    order anyone chose."""
    (tmp_path / "0001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0002_b.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0002_c.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(SystemExit, match="claim version 0002"):
        migrate.discover(tmp_path)


def test_checksums_are_stable_and_content_addressed():
    a = migrate._checksum("CREATE TABLE x ();")
    assert a == migrate._checksum("CREATE TABLE x ();")
    assert a != migrate._checksum("CREATE TABLE y ();")


def test_the_initial_migration_still_creates_the_graph():
    """0001 is the original schema.sql. It is the file a fresh database runs."""
    text = (MIGRATIONS / "0001_initial_schema.sql").read_text(encoding="utf-8")
    for table in ("service", "service_role", "connectivity_rule",
                  "architecture_rule", "equivalence", "kg_setting"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text, table


# ------------------------------------------------------------ needs database --


def _database_available():
    try:
        import pgconn

        return pgconn.reachable()
    except Exception:
        return False


needs_db = pytest.mark.skipif(
    not _database_available(), reason="no Postgres at CAV_PG_DSN"
)


@needs_db
def test_the_database_is_at_the_latest_version():
    """Every migration on disk has been applied to the database under test.

    Failing here means someone added a migration and did not run it, so the
    tests below this line are checking a schema nobody else has.
    """
    import pgconn

    with pgconn.connect() as conn:
        pending, done = migrate.plan(conn, MIGRATIONS)
    assert not pending, (
        f"{len(pending)} migration(s) not applied: "
        f"{[p.name for _, p, _, _ in pending]}. Run `python3 db/migrate.py`."
    )
    assert len(done) == len(migrate.discover(MIGRATIONS))


@needs_db
def test_applying_twice_changes_nothing():
    import pgconn

    with pgconn.connect() as conn:
        assert migrate.apply(conn, MIGRATIONS) == []


@needs_db
def test_editing_an_applied_migration_is_refused(tmp_path):
    """The classic mistake: change a migration that already ran, watch it work
    on the machine where it was applied and exist nowhere else."""
    import pgconn

    applied = MIGRATIONS / "0001_initial_schema.sql"
    tampered = tmp_path / applied.name
    tampered.write_text(
        applied.read_text(encoding="utf-8") + "\n-- edited\n", encoding="utf-8"
    )

    with pgconn.connect() as conn:
        with pytest.raises(SystemExit, match="has changed since it was applied"):
            migrate.plan(conn, tmp_path)
