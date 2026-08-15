#!/usr/bin/env python3
"""Write the knowledge graph out of Postgres and into YAML.

The inverse of `seed_from_yaml.py`, and the reason the YAML still exists.

Postgres is the source of truth: it is what the rule engine reads and the only
thing the curator can write to. But a database is a poor review surface. You
cannot see a proposed change to a connectivity rule in a pull request, you
cannot diff last month's graph against today's, and a `docker volume rm` takes
the whole thing with it. Those were all properties of the graph being a file,
and the migration to Postgres quietly gave them up.

So the YAML comes back, in the one role it can hold without becoming a second
source of truth: **generated output**. It is written by this script and by
nobody else. `tests/unit/test_kg_export_drift.py` fails when the committed
files disagree with the database, which is what stops the two from drifting
apart the way they silently did before.

That gives the YAML three honest jobs and no ambiguous ones:

  review     a diff in a pull request, showing what actually changed
  restore    seed a fresh database with `seed_from_yaml.py` and get this back
  offline    `CAV_KG_BACKEND=local` still runs with no database at all

What it is *not* is somewhere to edit. An edit here is overwritten by the next
export, and the drift test will fail before that in any case. Change the graph
through the curator agent or SQL, then run this.

Usage:
    python3 db/export_to_yaml.py             # write the files
    python3 db/export_to_yaml.py --check     # exit 1 if they are out of date
    python3 db/export_to_yaml.py --stdout services.yaml
"""

import argparse
import difflib
import sys
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "app" / "kg_lib"))

DEFAULT_OUT_DIR = _HERE.parent / "app" / "references" / "kg"

GENERATED_BANNER = (
    "# GENERATED FILE — do not edit.\n"
    "#\n"
    "# Written by db/export_to_yaml.py from the Postgres knowledge graph, which\n"
    "# is the source of truth. An edit here is overwritten by the next export,\n"
    "# and tests/unit/test_kg_export_drift.py fails before that anyway.\n"
    "#\n"
    "# To change the graph: use the curator agent, or SQL, then re-run the\n"
    "# export. To rebuild a database from this file: db/seed_from_yaml.py.\n"
)


def _dump(data):
    """Block-style YAML, keys in the order we build them rather than sorted."""
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=88,
    )


def _comment(text, indent=""):
    """Render stored rationale back into YAML comment lines."""
    if not text:
        return ""
    return "".join(f"{indent}# {line}\n" if line else f"{indent}#\n"
                   for line in text.splitlines())


def _header(settings, key):
    """The file's own preamble, kept in kg_setting as a `doc:*` row.

    These are the field definitions and the reasoning behind them. They were
    the first thing the migration nearly lost and are worth carrying back out.
    """
    note = settings.get(key)
    if not note:
        return GENERATED_BANNER + "\n"
    # Blank line, not a `#`, between the banner and the note. The banner is
    # metadata about how the file was produced; the note is the file's own
    # documentation. Run together into one comment block they are also one
    # block to whatever reads the file back, and the seed cannot tell where to
    # stop — which is how the banner ended up inside the `doc:` row and got
    # written twice by the export after that.
    return GENERATED_BANNER + "\n" + _comment(note) + "\n"


def _inject_entry_comments(body, notes, anchor_prefix="- id: "):
    """Put each entry's rationale above it, where a reader will find it.

    Directly above, with no blank line. The blank line that used to separate
    them cost more than the whitespace was worth: a comment block separated by
    one belongs to the section rather than to the entry, by the seed's own
    parsing rule, so on re-import the note detached from the entry it describes
    and was collected as trailing commentary on the entry *before* it. The WAF
    note on Application Gateway came back attached to Azure Load Balancer.
    """
    if not notes:
        return body
    out = []
    for line in body.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith(anchor_prefix):
            key = stripped[len(anchor_prefix):].strip().strip("'\"")
            note = notes.get(key)
            if note:
                indent = line[: len(line) - len(line.lstrip())]
                out.append(_comment(note, indent))
        out.append(line)
    return "".join(out)


def _compact(mapping):
    return {k: v for k, v in mapping.items() if v is not None}


# ---------------------------------------------------------------- documents --


def build_documents(rows):
    """Table rows -> {filename: yaml text}. Pure; no database, no file I/O.

    Takes the same row shape `seed_from_yaml.build_rows()` produces and
    `kg_pg.fetch_rows()` returns, so export and import are provably inverse:
    the round-trip test feeds this straight back into build_rows.
    """
    settings = {r["key"]: r for r in rows["kg_setting"]}
    doc_notes = {k: v["note"] for k, v in settings.items()}

    roles_by_service = {}
    for r in rows["service_role"]:
        roles_by_service.setdefault(r["service_id"], []).append(r["role"])

    # -- services --------------------------------------------------------
    services = []
    for r in rows["service"]:
        entry = {
            "id": r["id"],
            "name": r["name"],
            "provider": r["provider"],
            "category": r["category"],
            "tier": r["tier"],
            "roles": roles_by_service.get(r["id"], []),
            "network_placement": r["network_placement"],
            "reachability": r["reachability"],
            "region_scope": r["region_scope"],
        }
        entry.update(r.get("extras") or {})
        entry["provenance"] = _compact({
            "generated": r["prov_generated"],
            "status": r["prov_status"],
            "verified": r["prov_verified"],
            "sources": r["prov_sources"],
            "stale_after": r["prov_stale_after"],
        })
        services.append(entry)

    services_body = _inject_entry_comments(
        _dump({"services": services}),
        {r["id"]: r["rationale"] for r in rows["service"] if r.get("rationale")},
    )

    # -- connectivity rules (order is first-match-wins) -------------------
    conn_rules = []
    for r in rows["connectivity_rule"]:
        rule = _compact({
            "id": r["id"],
            "when": r["when_clause"],
            "verdict": r["verdict"],
            "relationship": r["relationship"],
            "needs_role": r["needs_role"],
        })
        # Declared on every rule and explicitly null on the six that allow
        # outright, so it is written even when empty.
        rule["severity"] = r["severity"]
        rule["message"] = r["message"]
        conn_rules.append(rule)

    conn_body = _inject_entry_comments(
        _dump({
            "rules": conn_rules,
            "fallback": settings["connectivity_fallback"]["value"],
        }),
        {r["id"]: r["rationale"] for r in rows["connectivity_rule"] if r.get("rationale")},
    )

    # -- architecture layers and rules ------------------------------------
    layers = []
    for r in rows["architecture_layer"]:
        layer = {"id": r["id"], "title": r["title"]}
        if r["is_gate"]:
            layer["gate"] = True
        if r["status"]:
            layer["status"] = r["status"]
        if r["description"]:
            layer["description"] = r["description"]
        layers.append(layer)

    arch_rules = [
        _compact({
            "id": r["id"],
            "layer": r["layer_id"],
            "enabled": r["enabled"],
            "severity": r["severity"],
            "title": r["title"],
            "message": r["message"],
            "remediation": r["remediation"],
            "applies_when": r["applies_when"],
            "threshold": r["threshold"],
        })
        for r in rows["architecture_rule"]
    ]

    arch_body = _inject_entry_comments(
        _dump({"layers": layers, "rules": arch_rules}),
        {r["id"]: r["rationale"] for r in rows["architecture_rule"] if r.get("rationale")},
    )

    # -- equivalences ------------------------------------------------------
    targets_by_eq = {}
    for r in rows["equivalence_target"]:
        targets_by_eq.setdefault(r["equivalence_id"], []).append(_compact({
            "id": r["target_id"],
            "level": r["level"],
            "when": r["when_clause"],
            "caveats": r["caveats"],
            "as": r["as_kind"],
            "feature": r["feature"],
        }))
    equivalences = [
        _compact({
            "source": r["source_id"],
            "selection_criteria": r["selection_criteria"],
            "targets": targets_by_eq.get(r["id"], []),
        })
        for r in rows["equivalence"]
    ]

    # -- overrides ---------------------------------------------------------
    overrides_doc = {
        "aliases": [
            _compact({
                "alias": r["alias"],
                "resolves_to": r["resolves_to"],
                "as": r["as_kind"],
                "feature": r["feature"],
                "note": r["note"],
            })
            for r in rows["service_alias"]
        ],
        "overrides": [
            _compact({
                "source": r["source_id"],
                "target": r["target_id"],
                "verdict": r["verdict"],
                "severity": r["severity"],
                "message": r["message"],
                "reason": r["reason"],
            })
            for r in rows["connection_override"]
        ],
        "alternatives": [
            {"pair": [r["a_id"], r["b_id"]], "decision": r["decision"]}
            for r in rows["service_alternative"]
        ],
    }

    # -- role catalog ------------------------------------------------------
    role_catalog = {
        r["role"]: _compact({"kind": r["kind"], "note": r["note"]})
        for r in rows.get("role_catalog") or []
    }

    return {
        "services.yaml":
            _header(doc_notes, "doc:services") + services_body,
        "connectivity-rules.yaml":
            _header(doc_notes, "doc:connectivity-rules") + conn_body,
        "architecture-rules.yaml":
            _header(doc_notes, "doc:architecture-rules") + arch_body,
        "equivalences.yaml":
            _header(doc_notes, "doc:equivalences")
            + _dump({
                "regenerate_roles": settings["regenerate_roles"]["value"],
                "equivalences": equivalences,
            }),
        "overrides.yaml":
            _header(doc_notes, "doc:overrides") + _dump(overrides_doc),
        "role-catalog.yaml":
            _header(doc_notes, "doc:role-catalog")
            + _dump({"roles": role_catalog}),
    }


# -------------------------------------------------------------------- main --


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p.add_argument("--check", action="store_true",
                   help="report drift and exit 1 instead of writing")
    p.add_argument("--stdout", metavar="FILENAME",
                   help="print one generated file instead of writing any")
    a = p.parse_args(argv)

    import kg_pg

    documents = build_documents(kg_pg.fetch_rows())
    out_dir = Path(a.out_dir)

    if a.stdout:
        sys.stdout.write(documents[a.stdout])
        return 0

    if a.check:
        drifted = []
        for name, text in documents.items():
            path = out_dir / name
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != text:
                drifted.append((name, current, text))
        if not drifted:
            print(f"up to date — {len(documents)} files match the database")
            return 0
        for name, current, text in drifted:
            print(f"\n=== {name} ===")
            diff = difflib.unified_diff(
                current.splitlines(), text.splitlines(),
                fromfile=f"{name} (committed)", tofile=f"{name} (database)",
                lineterm="", n=1,
            )
            for line in list(diff)[:40]:
                print(line)
        print(f"\n{len(drifted)} file(s) out of date. Run: "
              "python3 db/export_to_yaml.py")
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in documents.items():
        (out_dir / name).write_text(text, encoding="utf-8")
        print(f"wrote {out_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
