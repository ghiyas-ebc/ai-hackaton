#!/usr/bin/env python3
"""Load the hand-authored past-projects catalog into Postgres.

Unlike `seed_from_yaml.py`, this is not a one-time migration off a retiring
file — `app/references/projects/past_projects.yaml` stays the source of
truth and this script stays the way it gets into the database. See D27 (root
CLAUDE.md) for why the KG's YAML is generated and this one is not: this data
was never YAML-authored under the old pre-Postgres system, has no offline
consumer, and isn't checked by `verdict_grounding`.

Two halves, same split as `seed_from_yaml.py` and for the same reason —
testable without a database:

  build_rows()  pure transform, YAML documents -> table rows. No database.
  apply()       writes those rows. No transformation.

Usage:
    python3 db/seed_past_projects.py --dry-run     # counts only, no DB
    python3 db/seed_past_projects.py                # seed an empty catalog
    python3 db/seed_past_projects.py --replace       # wipe and reseed
"""

import argparse
import sys
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

DEFAULT_YAML_PATH = (
    _HERE.parent / "app" / "references" / "projects" / "past_projects.yaml"
)

# Insert order matters: everything else references project.
TABLE_ORDER = [
    "project",
    "project_member",
    "project_service",
    "project_connection",
    "project_tag",
]


def build_rows(yaml_path=DEFAULT_YAML_PATH):
    """YAML documents -> {table_name: [row, ...]}. Pure; touches no database."""
    projects = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8")) or []

    rows = {name: [] for name in TABLE_ORDER}
    for project in projects:
        pid = project["id"]
        rows["project"].append(
            {
                "id": pid,
                "name": project["name"],
                "description": project["description"],
                "use_case": project["use_case"],
                "started_at": project["started_at"],
                "ended_at": project.get("ended_at"),
                "client_name": project.get("client_name"),
            }
        )
        for ord_, member in enumerate(project.get("members") or []):
            rows["project_member"].append(
                {
                    "project_id": pid,
                    "name": member["name"],
                    "role_on_project": member["role_on_project"],
                    "ord": ord_,
                }
            )
        for ord_, service_id in enumerate(project.get("services") or []):
            rows["project_service"].append(
                {"project_id": pid, "service_id": service_id, "ord": ord_, "note": None}
            )
        for ord_, conn in enumerate(project.get("connections") or []):
            rows["project_connection"].append(
                {
                    "project_id": pid,
                    "source_service_id": conn["source"],
                    "target_service_id": conn["target"],
                    "note": conn.get("note"),
                    "ord": ord_,
                }
            )
        for tag in project.get("tags") or []:
            rows["project_tag"].append({"project_id": pid, "tag": tag})

    return rows


def apply(conn, rows, replace=False):
    """Write rows. Transformation already happened in build_rows()."""
    counts = {}
    with conn.cursor() as cur:
        cur.execute("SET search_path TO project_catalog, public")
        existing = _count(cur, "project")
        if existing and not replace:
            raise SystemExit(
                f"Refusing to seed: {existing} projects already present. "
                "Re-run with --replace to wipe and reload. This is not a "
                "merge tool."
            )
        if replace:
            cur.execute(
                "TRUNCATE project, project_member, project_service, "
                "project_connection, project_tag RESTART IDENTITY CASCADE"
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
                   help="wipe existing project-catalog tables before loading")
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
            # An empty database is just one with no migrations applied yet, so
            # seeding takes the same path production does rather than a
            # create-everything shortcut only this script knows about.
            import migrate as migrate_module

            migrate_module.apply(conn)
        counts = apply(conn, rows, replace=a.replace)
    for table in TABLE_ORDER:
        print(f"{table:24s} {counts[table]:4d}")
    print(f"\nSeeded {pgconn.dsn()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
