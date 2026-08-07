---
name: cloud-architecture-validator-show-kg
description: Open an interactive, Neo4j-Bloom-style visual explorer of the cloud architecture validator's knowledge graph — every known GCP/Azure service as a node, every ALLOWED/ALLOWED_WITH_NOTE/NEEDS_COMPONENT connectivity verdict as an edge. Use this when someone wants to browse, audit, or sanity-check the KG itself (what services exist, how they're allowed to connect, why a rule fired) rather than validate one specific architecture. Not for validating a user's proposed architecture — that is cloud-architecture-validator-create-architect. Requires cloud-architecture-validator-create-architect installed alongside it; this skill has no KG of its own.
---

# Cloud Architecture Validator — Show KG

Renders the knowledge graph itself, not a user's architecture. Where
`cloud-architecture-validator-create-architect` answers "is *this* connection
valid," this answers "what does the KG as a whole look like, and why."

## Requires

`cloud-architecture-validator-create-architect` installed as a sibling
directory. This skill owns no `services.yaml` or `connectivity-rules.yaml` —
`scripts/export_kg_graph.py` imports create-architect's `kg.py` and
`validate.py` directly, so the graph can never drift from what that skill
actually decides at runtime. If create-architect isn't present, the export
script fails loudly rather than falling back to a stale or duplicated copy.

## Workflow

```bash
cd scripts
python3 export_kg_graph.py --output ../visualizations/kg_graph.json

cd ../visualizations
python3 -m http.server 8000
# open http://localhost:8000/kg_explorer.html
```

Must be served over HTTP — the page fetches `kg_graph.json`, which `file://`
blocks. Regenerate the JSON any time create-architect's `services.yaml` or
`connectivity-rules.yaml` changes; nothing does this automatically.

In the explorer: filter by provider/category/verdict, search by name, click a
node for its KG properties (roles, network_placement, reachability, ...),
click a relationship for the rule that produced it (`rule_id` + message).
Node and relationship labels toggle independently — relationship labels
default off since a fully-connected KG has hundreds of edges.

Full technical detail — including a documented NVL rendering bug and its
workaround, and how to rebuild the vendored bundle — is in
`visualizations/README.md`. Read that before touching `kg_explorer.html`.

## What this is not

Not a diagram of a specific proposed architecture — that output already
exists via create-architect's `emit_drawio.py`, driven by a real
`--edges` list a user described. This tool has no concept of "the user's
architecture"; it shows the entire KG at once, always.

Not a data-entry tool. It only reads; it never writes to `services.yaml` or
`connectivity-rules.yaml`. Adding or editing services is
`cloud-architecture-validator-add`.
