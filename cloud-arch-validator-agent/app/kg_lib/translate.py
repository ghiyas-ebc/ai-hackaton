"""
Cross-provider architecture translation.

The order is deliberate:

  1. Drop connector components from the source architecture.
  2. Translate functional nodes only.
  3. If a node has several equivalents, STOP and ask for a decision — do not
     pick one.
  4. Re-validate the result against the target provider's rules, so any needed
     connectors emerge from those rules.

Steps 1 and 4 are linked and easy to miss. Translating source connectors
produces duplicated connectors, or connectors bridging something that needs no
bridge at the target — network patterns differ per provider, so connector
requirements cannot be inherited.

Usage:
    python3 translate.py --edges "cloud-load-balancing>cloud-run,cloud-run>cloud-sql" --to azure
    python3 translate.py --edges "..." --to azure --choose "cloud-load-balancing=azure-app-gateway"
"""

import argparse
import json
import sys

import kg as kg_module
from validate import validate, _parse_edges


def _is_regenerated(kg, node):
    return bool(set(node.get("roles", [])) & kg.regenerate_roles)


def translate(edges, target_provider, choices=None, context=None, kg=None):
    kg = kg or kg_module.load()
    choices = choices or {}

    # collect unique nodes from the edges, preserving order
    order, seen = [], set()
    for s, d in edges:
        for sid in (s, d):
            node, _ = kg.resolve(sid)
            key = node["id"] if node else sid
            if key not in seen:
                seen.add(key)
                order.append((sid, node))

    mapping, pending, dropped, unmapped = {}, [], [], []

    for raw, node in order:
        if node is None:
            unmapped.append({"source_service_id": raw, "reason": "not present in the knowledge graph"})
            continue
        if node["provider"] == target_provider:
            mapping[node["id"]] = node["id"]
            continue
        if _is_regenerated(kg, node):
            dropped.append({
                "source_service_id": node["id"],
                "reason": (
                    "Connector components are not translated. What is needed on "
                    f"{target_provider} is decided by that provider's own rules and "
                    "will appear during re-validation."
                ),
            })
            continue

        options, criteria = kg.equivalents(node["id"], target_provider)
        if not options:
            unmapped.append({
                "source_service_id": node["id"],
                "reason": (
                    f"No equivalent recorded for {target_provider}. Do not infer one "
                    "from general knowledge — flag it for review and KG addition."
                ),
            })
        elif node["id"] in choices:
            picked = choices[node["id"]]
            match = next((o for o in options if o["id"] == picked), None)
            if not match:
                unmapped.append({
                    "source_service_id": node["id"],
                    "reason": f"Choice '{picked}' is not a recorded equivalent.",
                })
            else:
                mapping[node["id"]] = match["id"]
        elif len(options) == 1:
            mapping[node["id"]] = options[0]["id"]
        else:
            pending.append({
                "source_service_id": node["id"],
                "source_name": node["name"],
                "question": (criteria or "").strip(),
                "options": [
                    {"id": o["id"], "name": o["name"], "level": o["level"],
                     "when": (o.get("when") or "").strip(),
                     "caveats": (o.get("caveats") or "").strip()}
                    for o in options
                ],
            })

    # caveats for equivalents that are already settled
    caveats = []
    for src_id, tgt_id in mapping.items():
        if src_id == tgt_id:
            continue
        opts, _ = kg.equivalents(src_id, target_provider)
        chosen = next((o for o in opts if o["id"] == tgt_id), None)
        if not chosen:
            continue
        entry = {
            "from": src_id, "to": tgt_id, "to_name": chosen["name"],
            "level": chosen["level"],
        }
        if chosen.get("caveats"):
            entry["caveats"] = chosen["caveats"].strip()
        if chosen.get("as") == "feature":
            entry["render_as"] = {"badge": chosen.get("feature"), "on": tgt_id}
        caveats.append(entry)

    result = {
        "schema_version": "1.0",
        "target_provider": target_provider,
        "mapping": mapping,
        "equivalence_notes": caveats,
        "needs_decision": pending,
        "regenerated_components": dropped,
        "unmapped": unmapped,
    }

    if pending:
        result["status"] = "AWAITING_DECISION"
        result["next_step"] = (
            "Some services have more than one equivalent. Put the questions in "
            "needs_decision to the user, then call translate again with their "
            "answers as choices (CLI: --choose 'src=tgt,...'). Choosing here on "
            "their behalf is the most common way to produce an architecture "
            "that looks convincing and is wrong."
        )
        return result

    dropped_ids = {d["source_service_id"] for d in dropped}
    unmapped_ids = {u["source_service_id"] for u in unmapped}

    # normalize source edges to canonical ids
    canon = []
    for s, d in edges:
        sn, _ = kg.resolve(s)
        dn, _ = kg.resolve(d)
        canon.append((sn["id"] if sn else s, dn["id"] if dn else d))

    # Connector contraction: A -> connector -> B becomes A -> B.
    # Without this, dropping the connector also drops the relationship it
    # represented, and whatever sat behind it (e.g. the database) disappears
    # from the translated architecture.
    contracted, bridged = [], []
    for s, d in canon:
        if s in dropped_ids and d in dropped_ids:
            continue
        if d in dropped_ids:
            for s2, d2 in canon:
                if s2 == d and d2 not in dropped_ids:
                    contracted.append((s, d2))
                    bridged.append([s, d, d2])
            continue
        if s in dropped_ids:
            continue
        contracted.append((s, d))

    new_edges, skipped = [], []
    for sid, did in contracted:
        if sid in unmapped_ids or did in unmapped_ids:
            skipped.append([sid, did])
            continue
        pair = (mapping.get(sid), mapping.get(did))
        if all(pair) and list(pair) not in new_edges:
            new_edges.append(list(pair))
    result_bridged = bridged

    result["status"] = "TRANSLATED"
    result["translated_edges"] = new_edges
    result["contracted_paths"] = result_bridged
    result["dropped_edges"] = skipped
    result["revalidation"] = validate([tuple(e) for e in new_edges], context=context, kg=kg)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--edges", required=True)
    p.add_argument("--to", required=True, help="target provider, e.g. azure")
    p.add_argument("--choose", default="", help="'src=tgt,src2=tgt2'")
    p.add_argument("--environment", default="poc")
    p.add_argument("--residency", default="none")
    a = p.parse_args()

    choices = {}
    for part in a.choose.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            choices[k.strip()] = v.strip()

    out = translate(
        _parse_edges(a.edges), a.to, choices,
        context={"environment": a.environment, "data_residency": a.residency},
    )
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
