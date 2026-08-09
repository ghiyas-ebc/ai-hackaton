"""
Export the source knowledge graph (services.yaml + connectivity-rules.yaml) as
a node-link JSON graph, for exploration in visualizations/kg_explorer.html.

Distinct from emit_drawio.py: that renders one architecture the user described.
This renders the KG itself — every service as a node, every ALLOWED /
ALLOWED_WITH_NOTE / NEEDS_COMPONENT verdict the rule engine produces for same-
provider pairs as an edge. No new logic — every verdict comes from
validate_connectivity() in validate.py, the same function validate.py uses,
so the graph can't drift from what the skill actually decides.

BLOCKED and UNCOVERED pairs are left out on purpose: this is a map of what the
KG says CAN connect, not an exhaustive N^2 matrix. Cross-provider pairs are
always BLOCKED by CONN-CROSS-PROVIDER, so only same-provider pairs are checked.

This skill owns no KG data of its own — it reads cloud-architecture-validator-
create-architect's, which must be installed alongside it. kg.py resolves
references/kg/ relative to its own file location, so importing it from there
(rather than copying it here) keeps the KG single-sourced.

Usage:
    python3 export_kg_graph.py --output ../visualizations/kg_graph.json
"""

import argparse
import itertools
import json
import sys
from pathlib import Path

# Vendored into the agent: the create-architect scripts live alongside this
# file in kg_lib/ rather than in a sibling skill directory, so there is no
# cross-skill path to resolve or fail loudly on.
sys.path.append(str(Path(__file__).resolve().parent))

import kg as kg_module
from validate import validate_connectivity

KEPT_VERDICTS = {"ALLOWED", "ALLOWED_WITH_NOTE", "NEEDS_COMPONENT"}


def build_graph(kg):
    nodes = []
    for svc_id, svc in kg.services.items():
        nodes.append({
            "id": svc_id,
            "name": svc.get("name", svc_id),
            "provider": svc["provider"],
            "category": svc.get("category", "unknown"),
            "tier": svc.get("tier"),
            "roles": svc.get("roles", []),
            "network_placement": svc.get("network_placement"),
            "reachability": svc.get("reachability"),
            "region_scope": svc.get("region_scope"),
        })

    edges = []
    ids_by_provider = {}
    for svc_id, svc in kg.services.items():
        ids_by_provider.setdefault(svc["provider"], []).append(svc_id)

    for provider, ids in ids_by_provider.items():
        pairs = [(a, b) for a, b in itertools.permutations(ids, 2)]
        notes = []
        results = validate_connectivity(kg, pairs, notes)
        for r in results:
            if r["verdict"] not in KEPT_VERDICTS:
                continue
            edge = {
                "source": r["source"],
                "target": r["target"],
                "verdict": r["verdict"],
                "severity": r.get("severity"),
                "rule_id": r.get("rule_id"),
                "message": r.get("message", ""),
            }
            if r.get("insert_component"):
                edge["insert_component"] = r["insert_component"]
            edges.append(edge)

    return {"nodes": nodes, "edges": edges}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", "-o", default="kg_graph.json")
    args = parser.parse_args()

    kg = kg_module.load()
    graph = build_graph(kg)

    Path(args.output).write_text(json.dumps(graph, indent=2), encoding="utf-8")
    print(f"nodes: {len(graph['nodes'])}  edges: {len(graph['edges'])}  -> {args.output}")


if __name__ == "__main__":
    main()
