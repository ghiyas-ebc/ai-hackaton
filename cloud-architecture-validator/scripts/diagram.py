"""
Icon-resolution helper for diagram emitters.

Consumes the same --edges input as validate.py/translate.py and emits a JSON
document that lists every node in the architecture together with its resolved
icon metadata (type, path, category, generic fallback note).

This does NOT generate draw.io XML or SVG. It is the input to a future emitter.

Usage:
    python3 scripts/diagram.py --edges "cloud-load-balancing>cloud-run,cloud-run>cloud-sql"
    python3 scripts/diagram.py --edges "..." --to azure  # translated architecture

Environment variables for path resolution:
    CAV_GCP_ICON_DIR    -> root of GCP Icons 2026
    CAV_AZURE_ICON_DIR  -> root of Azure Icons 2026/Azure_Public_Service_Icons/Icons
"""

import argparse
import json
import sys

import kg as kg_module
from validate import _parse_edges


def _edge_pair(c):
    """Normalize a connectivity dict or a tuple into (source, target)."""
    if isinstance(c, tuple):
        return c
    return c["source"], c["target"]


def resolve_nodes(kg, edges, include_inserted=True):
    """Collect unique nodes from edges, optionally including insert_component."""
    seen, nodes = set(), []
    for c in edges:
        src, tgt = _edge_pair(c)
        for sid in (src, tgt):
            node, _ = kg.resolve(sid)
            if node and node["id"] not in seen:
                seen.add(node["id"])
                nodes.append(node)
        if include_inserted and isinstance(c, dict) and c.get("insert_component"):
            ic = c["insert_component"]
            if ic["id"] not in seen:
                seen.add(ic["id"])
                nodes.append(kg.services.get(ic["id"]) or {"id": ic["id"], "name": ic["name"]})
    return nodes


def emit(edges, to_provider=None, translated_mapping=None, kg=None):
    kg = kg or kg_module.load()
    nodes = resolve_nodes(kg, edges)

    out_nodes = []
    for n in nodes:
        sid = n["id"]
        icon_meta = kg.icon_for(sid)
        if icon_meta is None:
            icon_meta = {
                "service_id": sid,
                "name": n.get("name", sid),
                "provider": n.get("provider", "unknown"),
                "type": "generic",
                "icon_path": None,
                "note": "No icon mapping defined.",
            }
        entry = {
            "service_id": sid,
            "name": icon_meta["name"],
            "provider": icon_meta["provider"],
            "icon_type": icon_meta["type"],
        }
        if "category" in icon_meta:
            entry["category"] = icon_meta["category"]
            entry["category_name"] = icon_meta.get("category_name")
        if icon_meta.get("icon_path"):
            entry["icon_path"] = str(icon_meta["icon_path"])
            entry["icon_exists"] = icon_meta["icon_path"].exists()
        else:
            entry["icon_path"] = None
            entry["icon_exists"] = False
        if icon_meta.get("note"):
            entry["note"] = icon_meta["note"]
        if translated_mapping and sid in translated_mapping:
            entry["translated_from"] = sid
            entry["translated_to"] = translated_mapping[sid]
        out_nodes.append(entry)

    return {
        "schema_version": "1.0",
        "target_provider": to_provider,
        "node_count": len(out_nodes),
        "nodes": out_nodes,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--edges", required=True, help="'a>b,b>c'")
    p.add_argument("--to", default=None, help="target provider for translation")
    p.add_argument("--choose", default="", help="'src=tgt,src2=tgt2' (only with --to)")
    p.add_argument("--format", default="json", choices=["json", "drawio"], help="output format")
    p.add_argument("--output", default=None, help="output file (default: stdout)")
    p.add_argument("--embed-icons", action="store_true", help="embed SVG icons as base64 in drawio output")
    p.add_argument("--environment", default="poc", choices=["poc", "dev", "production"])
    p.add_argument("--residency", default="none", choices=["none", "id", "eu", "us"])
    p.add_argument("--sla", default="standard", choices=["best_effort", "standard", "critical"])
    a = p.parse_args()

    kg = kg_module.load()
    edges_raw = _parse_edges(a.edges)
    context = {"environment": a.environment, "data_residency": a.residency, "sla_tier": a.sla}

    if a.to:
        from translate import translate
        choices = {}
        if a.choose:
            for part in a.choose.split(","):
                if "=" in part:
                    s, t = part.split("=", 1)
                    choices[s.strip()] = t.strip()
        tresult = translate(edges_raw, a.to, choices=choices, context=context, kg=kg)
        if tresult["status"] == "AWAITING_DECISION":
            json.dump(tresult, sys.stdout, indent=2, ensure_ascii=False)
            print()
            sys.exit(0)
        edges = [tuple(e) for e in tresult.get("translated_edges", [])]
        mapping = tresult.get("mapping", {})
        if a.format == "drawio":
            import emit_drawio
            report = tresult.get("revalidation") or {"architecture": []}
            emit_drawio.emit(edges, report, kg=kg, embed_icons=a.embed_icons, output_path=a.output)
        else:
            report = emit(edges, to_provider=a.to, translated_mapping=mapping, kg=kg)
            json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
            print()
    else:
        from validate import validate
        vresult = validate(edges_raw, context=context, kg=kg)
        edges = vresult["connectivity"]
        if a.format == "drawio":
            import emit_drawio
            emit_drawio.emit(edges, vresult, kg=kg, embed_icons=a.embed_icons, output_path=a.output)
        else:
            report = emit(edges, kg=kg)
            json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
            print()


if __name__ == "__main__":
    main()
