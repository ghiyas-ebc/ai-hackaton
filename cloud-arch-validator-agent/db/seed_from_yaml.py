#!/usr/bin/env python3
"""Load the retiring YAML knowledge graph into Postgres.

This runs once per environment. After it has run, `references/kg/*.yaml` is no
longer on the read path — the database is the source of truth and the YAML is
kept only as the record of what was migrated.

Two halves, deliberately separated:

  build_rows()  pure transform, YAML documents -> table rows. No database.
  apply()       writes those rows. No transformation.

The split is what makes the migration testable without a database: the parity
test feeds `build_rows()` straight into `kg_pg.kg_from_rows()` and asserts the
result is identical to what `kg.load()` builds from the YAML. If those two
disagree, the migration lost something, and it says so without anyone needing
Postgres running.

Usage:
    python3 db/seed_from_yaml.py --dry-run            # counts only, no DB
    python3 db/seed_from_yaml.py                      # seed an empty database
    python3 db/seed_from_yaml.py --replace            # wipe and reseed
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
_APP_KG_LIB = _HERE.parent / "app" / "kg_lib"
sys.path.insert(0, str(_APP_KG_LIB))
# migrate.py sits beside this file and is imported, not executed, so seeding a
# fresh database runs the same migrations production does.
sys.path.insert(0, str(_HERE))

# The agent's own vendored copy, not the sibling skill's. The skills are being
# retired by this migration; seeding from a tree that is on its way out would
# make the database's contents depend on which copy was more recently edited.
DEFAULT_KG_DIR = _HERE.parent / "app" / "references" / "kg"

# Insert order matters: everything references service, and service_role now
# references role_catalog.
TABLE_ORDER = [
    "role_catalog",
    "service",
    "service_role",
    "connectivity_rule",
    "architecture_layer",
    "architecture_rule",
    "equivalence",
    "equivalence_target",
    "service_alias",
    "connection_override",
    "service_alternative",
    "icon_category",
    "service_icon",
    "kg_setting",
]

# Columns holding JSON documents. Listed rather than sniffed, because a Python
# dict and a JSON string are both plausible values for these and guessing would
# make the failure mode "it silently stored the repr".
JSON_COLUMNS = {
    "service": {"extras", "prov_sources"},
    "connectivity_rule": {"when_clause"},
    "architecture_rule": {"applies_when", "threshold"},
    "kg_setting": {"value"},
}

# Two tables migration 0004 also seeds, because the schema needs them populated
# before there is a file to seed from: the role vocabulary, which
# `service_role.role` is a foreign key onto, and that file's own `doc:` row. On
# a database that has migrated but not been seeded, a plain INSERT collides
# with the migration's rows. Re-asserting instead of failing keeps the export
# authoritative for their contents without making the migration wrong.
UPSERT = {
    "role_catalog": ("role", ("kind", "note")),
    "kg_setting": ("key", ("value", "note")),
}


# --------------------------------------------------------------- comments ----
# PyYAML drops comments, and in this knowledge graph the comments are where the
# reasoning lives — the repo's own style rule says so. Dropping them during the
# migration would leave a future editor with `serverless_offvpc` and no idea
# what it means. So they are lifted out of the raw text and carried across.

_BANNER = re.compile(r"^[-=*\s]*$")

# First words of the export's own "do not edit" banner. That block is metadata
# about how the file was produced rather than documentation of what is in it,
# so it is not part of any `doc:` note. Carrying it in meant the next export
# printed it twice and the one after that three times.
# `tests/unit/test_kg_export_drift.py` pins this by asserting export -> seed ->
# export is byte-identical, so a reworded banner fails there rather than
# silently starting to accumulate again.
GENERATED_BANNER_PREFIX = "GENERATED FILE"


def _is_decoration(text):
    """Section banners (`# ---- GCP ----`) are layout, not reasoning."""
    if _BANNER.match(text):
        return True
    stripped = text.strip("-=* \t")
    return "----" in text and len(stripped.split()) <= 3


def _keep(text):
    """A comment line worth carrying: prose, or a paragraph break inside it."""
    return not (text and _is_decoration(text))


def _trim(block):
    """Drop blank lines at the ends of a block and keep the interior ones.

    A bare `#` inside a note is a paragraph break, and these notes are prose —
    the field definitions and the reasoning behind them. Treating those the
    same as a decorative banner ran every paragraph of every file header
    together into one wall of text on the first re-import.
    """
    while block and not block[0]:
        block.pop(0)
    while block and not block[-1]:
        block.pop()
    return block


def _comment_blocks(raw, anchor_re):
    """Map anchor value -> the commentary attached to that entry.

    Two places carry it, because the files use both:

      above  a contiguous comment block directly over the entry, no blank line
             in between (a comment separated by a blank line belongs to the
             section, not to the entry). This is how architecture-rules.yaml
             explains a rule, and it is what the export writes.
      inside comment lines within the entry's own body, before the next entry.
             This is how the hand-authored services.yaml annotated a single
             node, e.g. the note on Application Gateway explaining why WAF is
             a feature and not a separate box.

    The two overlap at one point and the overlap was a bug: a comment run that
    reaches the next entry is that entry's `above` block *and* sits inside this
    entry's line range, so every exported note was collected twice and the copy
    that stuck was the wrong one. `above` wins — a note written directly over
    an entry is about that entry.
    """
    lines = raw.splitlines()
    anchors = [(i, m.group(1)) for i, line in enumerate(lines)
               if (m := anchor_re.match(line))]
    out = {}
    for pos, (i, key) in enumerate(anchors):
        block = []
        j = i - 1
        while j >= 0:
            stripped = lines[j].strip()
            if not stripped.startswith("#"):
                break
            text = stripped.lstrip("#").strip()
            if _keep(text):
                block.append(text)
            j -= 1
        block.reverse()

        end = len(lines)
        if pos + 1 < len(anchors):
            end = anchors[pos + 1][0]
            # Give back the trailing comment run: it is the next entry's.
            while end > i + 1 and lines[end - 1].strip().startswith("#"):
                end -= 1
        for line in lines[i + 1:end]:
            stripped = line.strip()
            if stripped.startswith("#"):
                text = stripped.lstrip("#").strip()
                if _keep(text):
                    block.append(text)
        block = _trim(block)
        if block:
            out[key] = "\n".join(block)
    return out


def _preamble(raw):
    """The file's own header comment: what the fields mean and why.

    Reads the leading comment blocks and returns the first that is not the
    export's "do not edit" banner. A generated file carries both, in that
    order, separated by a blank line.
    """
    blocks, block = [], []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            if block:
                blocks.append(block)
                block = []
            continue
        if not stripped.startswith("#"):
            break
        text = stripped.lstrip("#").strip()
        if _keep(text):
            block.append(text)
    if block:
        blocks.append(block)

    for candidate in blocks:
        candidate = _trim(candidate)
        if candidate and not candidate[0].startswith(GENERATED_BANNER_PREFIX):
            return "\n".join(candidate)
    return None


# -------------------------------------------------------------- transform ----

_SERVICE_CORE = {
    "id",
    "name",
    "provider",
    "category",
    "tier",
    "roles",
    "network_placement",
    "reachability",
    "region_scope",
    "provenance",
}


def build_rows(kg_dir=DEFAULT_KG_DIR):
    """YAML documents -> {table_name: [row, ...]}. Pure; touches no database."""
    kg_dir = Path(kg_dir)

    def read(name):
        raw = (kg_dir / name).read_text(encoding="utf-8")
        return yaml.safe_load(raw), raw

    rows = {name: [] for name in TABLE_ORDER}

    # -- role vocabulary ------------------------------------------------
    # Read before services, because every role below has to exist here.
    roles_doc, roles_raw = read("role-catalog.yaml")
    for role, entry in (roles_doc.get("roles") or {}).items():
        rows["role_catalog"].append(
            {"role": role, "kind": entry["kind"], "note": entry.get("note")}
        )
    rows["kg_setting"].append(
        {"key": "doc:role-catalog", "value": None, "note": _preamble(roles_raw)}
    )

    # -- services -------------------------------------------------------
    services_doc, services_raw = read("services.yaml")
    svc_notes = _comment_blocks(services_raw, re.compile(r"^\s*-\s+id:\s*(\S+)"))
    for ord_, svc in enumerate(services_doc["services"]):
        prov = svc.get("provenance") or {}
        # Anything not in the core column set is a sparse per-service extra.
        extras = {k: v for k, v in svc.items() if k not in _SERVICE_CORE}
        rows["service"].append(
            {
                "id": svc["id"],
                "ord": ord_,
                "name": svc["name"],
                "provider": svc["provider"],
                "category": svc["category"],
                "tier": svc["tier"],
                "network_placement": svc["network_placement"],
                "reachability": svc["reachability"],
                "region_scope": svc["region_scope"],
                "extras": extras,
                "prov_generated": prov.get("generated", "manual"),
                "prov_status": prov.get("status", "manual"),
                "prov_verified": prov.get("verified"),
                "prov_sources": prov.get("sources"),
                "prov_stale_after": prov.get("stale_after"),
                "rationale": svc_notes.get(svc["id"]),
            }
        )
        for ord_, role in enumerate(svc.get("roles", [])):
            rows["service_role"].append(
                {"service_id": svc["id"], "role": role, "ord": ord_}
            )

    # -- connectivity rules (order is semantics: first match wins) -------
    conn_doc, conn_raw = read("connectivity-rules.yaml")
    conn_notes = _comment_blocks(conn_raw, re.compile(r"^\s*-\s+id:\s*(\S+)"))
    for seq, rule in enumerate(conn_doc["rules"]):
        rows["connectivity_rule"].append(
            {
                "id": rule["id"],
                "seq": seq,
                "when_clause": rule["when"],
                "verdict": rule["verdict"],
                "severity": rule["severity"],
                "message": rule["message"],
                "relationship": rule.get("relationship"),
                "needs_role": rule.get("needs_role"),
                "rationale": conn_notes.get(rule["id"]),
            }
        )
    rows["kg_setting"].append(
        {
            "key": "connectivity_fallback",
            "value": conn_doc["fallback"],
            "note": "Verdict when no connectivity rule matches. UNCOVERED is a "
            "correct answer, not a failure.",
        }
    )
    rows["kg_setting"].append(
        {"key": "doc:connectivity-rules", "value": None, "note": _preamble(conn_raw)}
    )

    # -- architecture layers and rules ----------------------------------
    arch_doc, arch_raw = read("architecture-rules.yaml")
    arch_notes = _comment_blocks(arch_raw, re.compile(r"^\s*-\s+id:\s*(\S+)"))
    for ord_, layer in enumerate(arch_doc.get("layers") or []):
        rows["architecture_layer"].append(
            {
                "id": layer["id"],
                "ord": ord_,
                "title": layer["title"],
                "description": layer.get("description"),
                "is_gate": bool(layer.get("gate", False)),
                "status": layer.get("status"),
            }
        )
    for ord_, rule in enumerate(arch_doc["rules"]):
        rows["architecture_rule"].append(
            {
                "id": rule["id"],
                "layer_id": rule["layer"],
                "ord": ord_,
                "enabled": bool(rule.get("enabled", True)),
                "severity": rule["severity"],
                "title": rule["title"],
                "message": rule["message"],
                "remediation": rule.get("remediation"),
                "applies_when": rule.get("applies_when"),
                "threshold": rule.get("threshold"),
                "rationale": arch_notes.get(rule["id"]),
            }
        )
    rows["kg_setting"].append(
        {"key": "doc:architecture-rules", "value": None, "note": _preamble(arch_raw)}
    )

    # -- equivalences ---------------------------------------------------
    eq_doc, eq_raw = read("equivalences.yaml")
    for eq_id, entry in enumerate(eq_doc["equivalences"], start=1):
        rows["equivalence"].append(
            {
                "id": eq_id,
                "source_id": entry["source"],
                "selection_criteria": entry.get("selection_criteria"),
            }
        )
        for ord_, tgt in enumerate(entry["targets"]):
            rows["equivalence_target"].append(
                {
                    "equivalence_id": eq_id,
                    "target_id": tgt["id"],
                    "ord": ord_,
                    "level": tgt["level"],
                    "when_clause": tgt.get("when"),
                    "caveats": tgt.get("caveats"),
                    "as_kind": tgt.get("as"),
                    "feature": tgt.get("feature"),
                }
            )
    rows["kg_setting"].append(
        {
            "key": "regenerate_roles",
            "value": eq_doc.get("regenerate_roles", []),
            "note": "Roles whose nodes are dropped and regenerated at the target "
            "provider instead of translated. Connectors have no equivalents by "
            "design; reading that absence as lock-in is a bug.",
        }
    )
    rows["kg_setting"].append(
        {"key": "doc:equivalences", "value": None, "note": _preamble(eq_raw)}
    )

    # -- aliases, overrides, alternatives -------------------------------
    ov_doc, ov_raw = read("overrides.yaml")
    for alias in ov_doc.get("aliases") or []:
        rows["service_alias"].append(
            {
                "alias": alias["alias"],
                "resolves_to": alias["resolves_to"],
                "as_kind": alias.get("as"),
                "feature": alias.get("feature"),
                "note": alias.get("note"),
            }
        )
    for ov in ov_doc.get("overrides") or []:
        rows["connection_override"].append(
            {
                "source_id": ov["source"],
                "target_id": ov["target"],
                "verdict": ov["verdict"],
                "severity": ov.get("severity"),
                "message": ov.get("message"),
                "reason": ov.get("reason") or ov.get("message") or "",
            }
        )
    for alt in ov_doc.get("alternatives") or []:
        a, b = alt["pair"]
        rows["service_alternative"].append(
            {"id": len(rows["service_alternative"]) + 1, "a_id": a, "b_id": b,
             "decision": alt["decision"]}
        )
    rows["kg_setting"].append(
        {"key": "doc:overrides", "value": None, "note": _preamble(ov_raw)}
    )

    # -- icons ----------------------------------------------------------
    icons_doc, icons_raw = read("icons.yaml")
    for provider, cats in (icons_doc.get("categories") or {}).items():
        for cat, definition in cats.items():
            rows["icon_category"].append(
                {
                    "provider": provider,
                    "category": cat,
                    "name": definition["name"],
                    "file": definition["file"],
                }
            )
    for sid, mapping in (icons_doc.get("services") or {}).items():
        rows["service_icon"].append(
            {
                "service_id": sid,
                "provider": mapping["provider"],
                "type": mapping["type"],
                "icon": mapping.get("icon"),
                "category": mapping.get("category"),
                "note": mapping.get("note"),
            }
        )
    rows["kg_setting"].append(
        {"key": "doc:services", "value": None, "note": _preamble(services_raw)}
    )
    rows["kg_setting"].append(
        {"key": "doc:icons", "value": None, "note": _preamble(icons_raw)}
    )

    return rows


# ------------------------------------------------------------------ write ----


def _adapt(table, row):
    json_cols = JSON_COLUMNS.get(table, set())
    return {
        k: (json.dumps(v) if k in json_cols and v is not None else v)
        for k, v in row.items()
    }


def apply(conn, rows, replace=False):
    """Write rows. Transformation already happened in build_rows()."""
    counts = {}
    with conn.cursor() as cur:
        cur.execute("SET search_path TO kg, public")
        existing = _count(cur, "service")
        if existing and not replace:
            raise SystemExit(
                f"Refusing to seed: {existing} services already present. "
                "Re-run with --replace to wipe and reload, or point CAV_PG_DSN "
                "at an empty database. This is not a merge tool."
            )
        if replace:
            cur.execute(
                "TRUNCATE service, role_catalog, connectivity_rule, "
                "architecture_layer, architecture_rule, equivalence, "
                "service_alias, connection_override, service_alternative, "
                "icon_category, kg_setting RESTART IDENTITY CASCADE"
            )
        for table in TABLE_ORDER:
            table_rows = rows[table]
            if not table_rows:
                counts[table] = 0
                continue
            cols = list(table_rows[0].keys())
            placeholders = ", ".join(f"%({c})s" for c in cols)
            on_conflict = ""
            if table in UPSERT:
                key, updated = UPSERT[table]
                on_conflict = (
                    f" ON CONFLICT ({key}) DO UPDATE SET "
                    + ", ".join(f"{c} = EXCLUDED.{c}" for c in updated)
                )
            sql = (
                f"INSERT INTO {table} ({', '.join(cols)}) "
                f"VALUES ({placeholders}){on_conflict}"
            )
            cur.executemany(sql, [_adapt(table, r) for r in table_rows])
            counts[table] = len(table_rows)
        # The equivalence ids were assigned by build_rows, not by the sequence.
        cur.execute(
            "SELECT setval(pg_get_serial_sequence('equivalence', 'id'), "
            "COALESCE((SELECT MAX(id) FROM equivalence), 1))"
        )
        cur.execute(
            "SELECT setval(pg_get_serial_sequence('service_alternative', 'id'), "
            "COALESCE((SELECT MAX(id) FROM service_alternative), 1))"
        )
    conn.commit()
    return counts


def _count(cur, table):
    cur.execute(f"SELECT count(*) FROM {table}")
    return cur.fetchone()[0]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kg-dir", default=str(DEFAULT_KG_DIR))
    p.add_argument("--replace", action="store_true",
                   help="wipe existing KG tables before loading")
    p.add_argument("--dry-run", action="store_true",
                   help="build the rows and report counts without connecting")
    p.add_argument("--no-migrate", action="store_true",
                   help="assume the schema is already current")
    a = p.parse_args(argv)

    rows = build_rows(a.kg_dir)
    if a.dry_run:
        for table in TABLE_ORDER:
            print(f"{table:24s} {len(rows[table]):4d}")
        return 0

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
