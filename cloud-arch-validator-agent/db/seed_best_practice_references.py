#!/usr/bin/env python3
"""Load the hand-authored best-practice-reference catalog into Postgres.

Same schema as `seed_past_projects.py` (`project_catalog`) but a separate
source file and a separate script: `past_projects.yaml` is our own delivery
history, `best_practice_references.yaml` is a principal's published
guidance, and the two shouldn't share a lifecycle just because they land in
the same schema.

Two halves, same split as `seed_past_projects.py`:

  build_rows()  pure transform, YAML documents -> table rows. No database.
  apply()       writes those rows. No transformation.

Usage:
    python3 db/seed_best_practice_references.py --dry-run     # counts only
    python3 db/seed_best_practice_references.py                # seed
    python3 db/seed_best_practice_references.py --replace       # wipe and reseed
"""

import argparse
import sys
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

DEFAULT_YAML_PATH = (
    _HERE.parent / "app" / "references" / "projects" / "best_practice_references.yaml"
)

# Insert order matters: best_practice_reference.tag references best_practice_tag.
TABLE_ORDER = ["best_practice_tag", "best_practice_reference"]


def build_rows(yaml_path=DEFAULT_YAML_PATH):
    """YAML document -> {table_name: [row, ...]}. Pure; touches no database."""
    doc = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8")) or {}

    rows = {name: [] for name in TABLE_ORDER}
    for tag in doc.get("tags") or []:
        rows["best_practice_tag"].append({"tag": tag["tag"], "note": tag["note"]})

    for ord_, ref in enumerate(doc.get("references") or []):
        rows["best_practice_reference"].append(
            {
                "id": ref["id"],
                "tag": ref["tag"],
                "provider": ref.get("provider"),
                "title": ref["title"],
                "note": ref["note"],
                "reference_url": ref.get("reference_url"),
                "ord": ord_,
            }
        )

    return rows


def apply(conn, rows, replace=False):
    """Write rows. Transformation already happened in build_rows()."""
    counts = {}
    with conn.cursor() as cur:
        cur.execute("SET search_path TO project_catalog, public")
        existing = _count(cur, "best_practice_reference")
        if existing and not replace:
            raise SystemExit(
                f"Refusing to seed: {existing} best-practice references already "
                "present. Re-run with --replace to wipe and reload. This is not "
                "a merge tool."
            )
        if replace:
            cur.execute(
                "TRUNCATE best_practice_reference, best_practice_tag "
                "RESTART IDENTITY CASCADE"
            )
        for table in TABLE_ORDER:
            table_rows = rows[table]
            if not table_rows:
                counts[table] = 0
                continue
            cols = list(table_rows[0].keys())
            placeholders = ", ".join(f"%({c})s" for c in cols)
            sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
            cur.executemany(sql, table_rows)
            counts[table] = len(table_rows)
    conn.commit()
    return counts


def _count(cur, table):
    cur.execute(f"SELECT count(*) FROM {table}")
    return cur.fetchone()[0]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--yaml-path", default=str(DEFAULT_YAML_PATH))
    p.add_argument("--replace", action="store_true",
                   help="wipe existing best-practice-reference tables before loading")
    p.add_argument("--dry-run", action="store_true",
                   help="build the rows and report counts without connecting")
    p.add_argument("--no-migrate", action="store_true",
                   help="assume the schema is already current")
    a = p.parse_args(argv)

    rows = build_rows(a.yaml_path)
    if a.dry_run:
        for table in TABLE_ORDER:
            print(f"{table:24s} {len(rows[table]):4d}")
        return 0

    sys.path.insert(0, str(_HERE.parent / "app" / "kg_lib"))
    import pgconn

    with pgconn.connect() as conn:
        if not a.no_migrate:
            import migrate as migrate_module

            migrate_module.apply(conn)
        counts = apply(conn, rows, replace=a.replace)
    for table in TABLE_ORDER:
        print(f"{table:24s} {counts[table]:4d}")
    print(f"\nSeeded {pgconn.dsn()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
