#!/usr/bin/env python3
"""Apply pending schema migrations, in order, once each.

The graph moved into Postgres with a single `schema.sql` full of
`CREATE TABLE IF NOT EXISTS`. That is fine exactly once. The second schema
change has nowhere to go: re-running the file is a no-op against an existing
database, so the only way to add a column was a hand-written `ALTER` typed at a
prompt, against live data, with nothing recording that it happened. The next
developer to seed a fresh database would get a different schema from the one in
production and no way to notice.

So: numbered `.sql` files in `db/migrations/`, applied in filename order, each
recorded in `kg.schema_migration` when it succeeds. Plain SQL and a hundred
lines of runner. Alembic is a reasonable tool and more machinery than thirteen
tables justify — this needs to be readable by someone who has never seen it.

Three properties worth having, all cheap:

*Each migration runs in its own transaction.* Postgres does transactional DDL,
so a migration that fails halfway leaves nothing behind. Half-applied schema is
the thing that turns a bad afternoon into a restore.

*Applied migrations are checksummed.* Editing a file that already ran is the
classic mistake: it works on your machine, where the change was applied by hand
or by a rebuild, and silently does not exist anywhere else. The runner refuses
to continue and tells you to write a new migration instead.

*An empty database is not special-cased.* A fresh database is just one with no
migrations applied yet, so the path a developer takes on Monday morning is the
same path production takes, and it is exercised every time anyone runs the
tests.

Usage:
    python3 db/migrate.py                # apply everything pending
    python3 db/migrate.py --status       # what is applied, what is pending
    python3 db/migrate.py --dry-run      # name them without applying
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "app" / "kg_lib"))

MIGRATIONS_DIR = _HERE / "migrations"
FILENAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")

# Bootstrapped outside the migration sequence: the table that records the
# sequence cannot itself be migration 0001. Kept in the default schema so it is
# reachable before `kg` exists.
LEDGER_DDL = """
CREATE SCHEMA IF NOT EXISTS kg;
CREATE TABLE IF NOT EXISTS kg.schema_migration (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    checksum    TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _checksum(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def discover(directory=MIGRATIONS_DIR):
    """Every migration on disk, in application order.

    Filenames must be `NNNN_lower_snake_name.sql`. The number is the version and
    it must be unique — two migrations claiming 0003 would apply in whatever
    order the filesystem felt like, which is the kind of thing that works for a
    year and then does not.
    """
    found = {}
    for path in sorted(Path(directory).glob("*.sql")):
        match = FILENAME.match(path.name)
        if not match:
            raise SystemExit(
                f"{path.name} is not a migration filename. Expected "
                "NNNN_lower_snake_name.sql, e.g. 0002_add_gap_record.sql"
            )
        version = int(match.group(1))
        if version in found:
            raise SystemExit(
                f"two migrations claim version {version:04d}: "
                f"{found[version].name} and {path.name}"
            )
        found[version] = path
    return [found[v] for v in sorted(found)]


def applied(conn):
    """version -> (name, checksum) for everything already run."""
    with conn.cursor() as cur:
        cur.execute(LEDGER_DDL)
        conn.commit()
        cur.execute(
            "SELECT version, name, checksum FROM kg.schema_migration ORDER BY version"
        )
        return {row[0]: (row[1], row[2]) for row in cur.fetchall()}


def plan(conn, directory=MIGRATIONS_DIR):
    """(pending, already_applied). Raises if a recorded migration was edited."""
    done = applied(conn)
    pending = []
    for path in discover(directory):
        version = int(path.name[:4])
        text = path.read_text(encoding="utf-8")
        digest = _checksum(text)
        if version in done:
            _, recorded = done[version]
            if recorded != digest:
                raise SystemExit(
                    f"{path.name} has changed since it was applied "
                    f"({recorded} -> {digest}).\n"
                    "A migration is a record of what happened, not a file to "
                    "edit. Restore it and add a new migration for the change."
                )
            continue
        pending.append((version, path, text, digest))
    return pending, done


def apply(conn, directory=MIGRATIONS_DIR, dry_run=False):
    pending, _ = plan(conn, directory)
    for version, path, text, digest in pending:
        if dry_run:
            print(f"  would apply {path.name}")
            continue
        with conn.cursor() as cur:
            # One transaction per migration. Postgres has transactional DDL, so
            # a failure rolls the whole file back rather than leaving half a
            # schema behind.
            cur.execute(text)
            cur.execute(
                "INSERT INTO kg.schema_migration (version, name, checksum) "
                "VALUES (%s, %s, %s)",
                (version, path.name, digest),
            )
        conn.commit()
        print(f"  applied {path.name}")
    return pending


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--status", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--dir", default=str(MIGRATIONS_DIR))
    a = p.parse_args(argv)

    import pgconn

    with pgconn.connect() as conn:
        if a.status:
            pending, done = plan(conn, a.dir)
            print(f"database: {pgconn.dsn()}\n")
            for version in sorted(done):
                name, _ = done[version]
                print(f"  [applied] {name}")
            for _, path, _, _ in pending:
                print(f"  [pending] {path.name}")
            if not done and not pending:
                print("  no migrations found")
            print(f"\n{len(done)} applied, {len(pending)} pending")
            return 0

        pending = apply(conn, a.dir, dry_run=a.dry_run)
        if not pending:
            print("up to date — nothing to apply")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
