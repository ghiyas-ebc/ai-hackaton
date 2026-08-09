"""
Architecture validator — a layer ladder, L1 through L8.

L1 (connectivity): can A reach B, and what component is missing. Derived from
node properties via connectivity-rules.yaml rather than from a list of pairs.
Consequence: a pair nobody ever entered still gets a verdict, as long as both
nodes are known.

L2-L8 (architecture): will this design hold up, is it safe, is the cost
predictable, can it ever move. These are the questions a client's architect
asks in design review. Layer definitions live in architecture-rules.yaml.

L1 is a gate. An edge that cannot connect is dropped from the input to L2-L8,
because "your unreachable database is also publicly exposed" is cascade noise
that buries the finding that matters. What was suppressed is always reported,
never silently dropped.

No LLM sits in the decision path — the ladder is a decision tree in code, not
a thinking framework the model walks. The language model's job is to turn the
user's description into (source, target) pairs and to communicate the result in
language a salesperson can use — not to decide what is valid, at any layer.

Usage:
    python3 validate.py --edges "cloud-run>cloud-sql,cloud-load-balancing>cloud-run"
    python3 validate.py --edges "..." --environment production --residency id
"""

import argparse
import json
import sys

import kg as kg_module

SEVERITY_ORDER = {"ERROR": 3, "WARNING": 2, "INFO": 1, None: 0}


# --------------------------------------------------------------- layer 1 ---
def _match_side(node, cond):
    if not cond:
        return True
    roles = set(node.get("roles", []))
    if "any_role" in cond and not roles & set(cond["any_role"]):
        return False
    if "all_roles" in cond and not set(cond["all_roles"]) <= roles:
        return False
    if "none_role" in cond and roles & set(cond["none_role"]):
        return False
    if "placement_in" in cond and node["network_placement"] not in cond["placement_in"]:
        return False
    if "reachability_in" in cond and node.get("reachability") not in cond["reachability_in"]:
        return False
    if "provider_in" in cond and node["provider"] not in cond["provider_in"]:
        return False
    return True


def _match(rule, src, dst):
    w = rule["when"]
    if "same_node" in w and (src["id"] == dst["id"]) != w["same_node"]:
        return False
    if "same_provider" in w and (src["provider"] == dst["provider"]) != w["same_provider"]:
        return False
    return _match_side(src, w.get("source")) and _match_side(dst, w.get("target"))


def _should_reverse(src, dst):
    """Direction convention: an edge follows the direction of the request.

    The original draft had no convention — `memorystore -> compute-engine` and
    `cloud-load-balancing -> cloud-run` used opposite meanings of direction.
    Rather than rejecting the user's input, normalize it and say it was flipped.
    """
    s, d = set(src.get("roles", [])), set(dst.get("roles", []))
    is_passive_store = "datastore" in s and "event_source" not in s
    return is_passive_store and "compute" in d


def _resolve_component(kg, role, provider):
    cands = kg.by_role(role, provider=provider)
    return cands[0] if cands else None


def validate_connectivity(kg, edges, notes):
    results = []
    for raw_src, raw_dst in edges:
        src, src_alias = kg.resolve(raw_src)
        dst, dst_alias = kg.resolve(raw_dst)

        missing = [r for r, n in ((raw_src, src), (raw_dst, dst)) if n is None]
        if missing:
            results.append({
                "source": raw_src, "target": raw_dst,
                "verdict": "UNKNOWN_SERVICE", "severity": "WARNING",
                "rule_id": None,
                "message": (
                    f"Service not present in the knowledge graph: {', '.join(missing)}. "
                    "Do not guess its behaviour — confirm the service name with the "
                    "user, or flag it to be added to the KG."
                ),
            })
            continue

        for raw, alias in ((raw_src, src_alias), (raw_dst, dst_alias)):
            if alias:
                notes.append({
                    "type": "alias", "input": raw,
                    "resolved_to": alias["resolves_to"],
                    "message": alias.get("note", ""),
                })

        # A feature-type alias pointing at the other endpoint is not a self-loop:
        # it is how a user describes "WAF in front of the gateway", which really
        # means the WAF is a SKU on that gateway.
        feature_alias = next(
            (a for a in (src_alias, dst_alias)
             if a and a.get("as") == "feature" and a["resolves_to"] in (raw_src, raw_dst, src["id"], dst["id"])),
            None,
        )
        if feature_alias and src["id"] == dst["id"]:
            results.append({
                "source": raw_src, "target": raw_dst,
                "verdict": "FEATURE_ON_NODE", "severity": "INFO",
                "rule_id": "ALIAS-FEATURE",
                "message": feature_alias.get("note", "").strip(),
                "render_as": {"node": src["id"], "badge": feature_alias.get("feature")},
            })
            continue

        reversed_edge = _should_reverse(src, dst)
        if reversed_edge:
            src, dst = dst, src

        ov = kg.overrides.get((src["id"], dst["id"]))
        if ov:
            entry = {**ov, "rule_id": f"OVERRIDE:{ov.get('reason', '')}"}
        else:
            entry = None
            for rule in kg.conn_rules:
                if _match(rule, src, dst):
                    entry = {**rule, "rule_id": rule["id"]}
                    break
            if entry is None:
                entry = {**kg.conn_fallback, "rule_id": "FALLBACK"}

        item = {
            "source": src["id"], "target": dst["id"],
            "verdict": entry["verdict"],
            "severity": entry.get("severity"),
            "rule_id": entry["rule_id"],
            "message": entry.get("message", "").strip(),
        }
        if entry.get("relationship"):
            item["relationship"] = entry["relationship"]
        if reversed_edge:
            item["direction_normalized"] = (
                f"Direction flipped to {src['id']} -> {dst['id']} to follow the "
                "request path. A datastore does not initiate connections to compute."
            )
        if entry["verdict"] == "NEEDS_COMPONENT":
            comp = _resolve_component(kg, entry["needs_role"], dst["provider"])
            if comp:
                item["insert_component"] = {"id": comp["id"], "name": comp["name"]}
            else:
                item["insert_component"] = None
                item["severity"] = "WARNING"
                item["message"] += (
                    f" (No component holding role '{entry['needs_role']}' exists "
                    f"for provider {dst['provider']} in the KG — needs review.)"
                )
        results.append(item)
    return results


# ------------------------------------------------------------- layers 2-8 ---
# Verdicts that mean "this edge does not work at all". The nodes on such an
# edge still exist in the design, so they stay in the node set — but the edge
# itself is withheld from rules that reason about traffic paths.
_DEAD_EDGE_VERDICTS = {"BLOCKED", "UNKNOWN_SERVICE"}


def _ctx_ok(rule, ctx):
    aw = rule.get("applies_when")
    if not aw:
        return True
    return all(ctx.get(k) in v for k, v in aw.items())


def validate_architecture(kg, nodes, conn_results, ctx):
    roles = {r for n in nodes for r in n.get("roles", [])}
    findings = []

    def emit(rule, detail=None):
        layer = rule.get("layer")
        findings.append({
            "layer": layer,
            "layer_title": (kg.layers_by_id.get(layer) or {}).get("title"),
            "rule_id": rule["id"], "severity": rule["severity"],
            "title": rule["title"], "message": rule["message"].strip(),
            "remediation": rule.get("remediation", "").strip(),
            "detail": detail,
        })

    by_id = {r["id"]: r for r in kg.arch_rules if r.get("enabled", True)}
    node_ids = {n["id"] for n in nodes}

    def rule(rid):
        r = by_id.get(rid)
        return r if r and _ctx_ok(r, ctx) else None

    # SEC-001 — datastore still on a public path
    r = rule("SEC-001-PUBLIC-DATASTORE")
    if r:
        has_private = any("connector" in n.get("roles", []) for n in nodes)
        exposed = [
            c for c in conn_results
            if c["verdict"] == "NEEDS_COMPONENT" and c.get("severity") == "WARNING"
        ]
        if exposed and not has_private:
            emit(r, [f"{c['source']} -> {c['target']}" for c in exposed])

    # SEC-002 — no secret store
    r = rule("SEC-002-NO-SECRET-STORE")
    if r and "secret_store" not in roles:
        touches_data = any(
            "datastore" in (kg.services.get(c["target"], {}).get("roles") or [])
            for c in conn_results
        )
        if touches_data:
            emit(r)

    # SEC-003 — compute exposed with no managed entry point
    r = rule("SEC-003-COMPUTE-EXPOSED")
    if r and "edge_entry" not in roles and "http_target" in roles:
        emit(r, [n["id"] for n in nodes if "http_target" in n.get("roles", [])])

    # REL-001 — zonal components
    r = rule("REL-001-SINGLE-ZONE")
    if r:
        zonal = [n["id"] for n in nodes if n.get("region_scope") == "zonal"]
        if zonal:
            emit(r, zonal)

    # REL-002 — single region
    r = rule("REL-002-SINGLE-REGION")
    if r:
        emit(r)

    # REL-003 — no backup shown
    r = rule("REL-003-NO-DATA-DURABILITY")
    if r and "datastore" in roles:
        emit(r, [n["id"] for n in nodes if "datastore" in n.get("roles", [])])

    # COST-001 — regional and multi-region mixed
    r = rule("COST-001-CROSS-REGION-TRAFFIC")
    if r:
        scopes = {n.get("region_scope") for n in nodes}
        if "multi_region" in scopes and scopes & {"regional", "zonal"}:
            emit(r, sorted(s for s in scopes if s))

    # GOV-001 — data residency
    r = rule("GOV-001-DATA-RESIDENCY")
    if r:
        offenders = [
            n["id"] for n in nodes
            if "datastore" in n.get("roles", []) and n.get("region_scope") == "multi_region"
        ]
        if offenders:
            emit(r, offenders)

    # OPS-001 — observability
    r = rule("OPS-001-NO-OBSERVABILITY")
    if r and ctx.get("environment") == "production":
        emit(r)

    # PORT-001 / PORT-002 — L8 portability, read straight off equivalences.yaml.
    # "The other provider" is every provider in the KG that isn't this node's
    # own, so this keeps working unchanged when AWS or Huawei land.
    all_providers = {n["provider"] for n in kg.services.values()}
    no_equiv, ambiguous = [], []
    for n in nodes:
        # Connectors have no equivalents on purpose — equivalences.yaml drops
        # them and lets the target provider's own connectivity rules regenerate
        # what it needs. Reading that absence as lock-in would flag every
        # private-connectivity component in the KG as unportable, which is the
        # opposite of true.
        if set(n.get("roles", [])) & kg.regenerate_roles:
            continue
        for target_provider in sorted(all_providers - {n["provider"]}):
            equivs, criteria = kg.equivalents(n["id"], target_provider)
            if not equivs:
                no_equiv.append(f"{n['id']} -> {target_provider}")
            elif criteria or len(equivs) > 1 or any(e.get("level") == "PARTIAL" for e in equivs):
                ambiguous.append({
                    "service": n["id"], "to": target_provider,
                    "options": [e["id"] for e in equivs],
                    "question": criteria,
                })

    r = rule("PORT-001-NO-EQUIVALENT")
    if r and no_equiv:
        emit(r, sorted(no_equiv))

    r = rule("PORT-002-AMBIGUOUS-EQUIVALENT")
    if r and ambiguous:
        emit(r, ambiguous)

    # VIZ-001 — diagram density
    r = rule("VIZ-001-TOO-MANY-NODES")
    if r and len(node_ids) > r.get("threshold", 20):
        emit(r, {"node_count": len(node_ids), "threshold": r["threshold"]})

    return findings


# ---------------------------------------------------------------- orchestration
def _layer_report(kg, conn, arch, gated):
    """One entry per declared layer, walked in ladder order.

    Every layer reports its own status even when it found nothing, because
    "L4 checked and found nothing" and "L4 has no rules and checked nothing"
    are different answers and collapsing them into silence is exactly the
    guessing this skill refuses to do (root invariant #5).
    """
    enabled = [r for r in kg.arch_rules if r.get("enabled", True)]
    out = []
    for layer in kg.arch_layers:
        lid = layer["id"]
        if lid == "L1":
            findings = [c for c in conn if c.get("severity") in ("ERROR", "WARNING")]
            rules_here = kg.conn_rules
        else:
            findings = [f for f in arch if f.get("layer") == lid]
            rules_here = [r for r in enabled if r.get("layer") == lid]

        if layer.get("status") == "uncovered" or not rules_here:
            status = "UNCOVERED"
        elif findings:
            status = max(
                (f.get("severity") for f in findings),
                key=lambda s: SEVERITY_ORDER.get(s, 0),
            )
        else:
            status = "CLEAN"

        entry = {
            "id": lid, "title": layer["title"], "status": status,
            "rules_active": len(rules_here), "findings": len(findings),
        }
        if status == "UNCOVERED":
            entry["why_uncovered"] = layer.get("description", "").strip()
        if layer.get("gate") and gated:
            entry["gated_out"] = gated
        out.append(entry)
    return out


def validate(edges, context=None, kg=None):
    kg = kg or kg_module.load()
    ctx = {"environment": "poc", "data_residency": "none", "sla_tier": "standard"}
    ctx.update(context or {})

    notes = []
    conn = validate_connectivity(kg, edges, notes)

    node_ids, nodes = set(), []
    for c in conn:
        for sid in (c["source"], c["target"]):
            node, _ = kg.resolve(sid)
            if node and node["id"] not in node_ids:
                node_ids.add(node["id"])
                nodes.append(node)

    # L1 gate. Edges that cannot carry traffic are withheld from L2-L8 so a
    # single broken connection doesn't spray derived findings across every
    # layer. The nodes stay — a node-scoped rule (zonal, residency, lock-in)
    # is still true about a service whose one edge happens to be broken.
    live_conn = [c for c in conn if c["verdict"] not in _DEAD_EDGE_VERDICTS]
    gated = [
        {"edge": f"{c['source']} -> {c['target']}", "verdict": c["verdict"]}
        for c in conn if c["verdict"] in _DEAD_EDGE_VERDICTS
    ]

    arch = validate_architecture(kg, nodes, live_conn, ctx)

    alts = []
    for a in kg.alternatives:
        if set(a["pair"]) <= node_ids:
            alts.append({
                "pair": a["pair"], "severity": "WARNING",
                "message": (
                    "These two services are mutually exclusive options, not "
                    "components used together. " + a["decision"].strip()
                ),
            })

    worst = max(
        [SEVERITY_ORDER.get(c.get("severity"), 0) for c in conn]
        + [SEVERITY_ORDER.get(f["severity"], 0) for f in arch]
        + [0]
    )
    return {
        "schema_version": "1.1",
        "context": ctx,
        "layers": _layer_report(kg, conn, arch, gated),
        "summary": {
            "nodes": len(node_ids),
            "edges": len(conn),
            "blocking": sum(1 for c in conn if c["verdict"] in ("BLOCKED", "NEEDS_COMPONENT")
                            and c.get("severity") == "ERROR"),
            "uncovered": sum(1 for c in conn if c["verdict"] in ("UNCOVERED", "UNKNOWN_SERVICE")),
            "architecture_findings": len(arch),
            "highest_severity": {v: k for k, v in SEVERITY_ORDER.items()}[worst],
        },
        "connectivity": conn,
        "architecture": arch,
        "exclusive_choices": alts,
        "notes": notes,
    }


def _parse_edges(text):
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if ">" not in part:
            raise SystemExit(f"Malformed edge: {part!r} (expected 'source>target')")
        s, d = part.split(">", 1)
        out.append((s.strip(), d.strip()))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--edges", required=True, help="'a>b,b>c'")
    p.add_argument("--environment", default="poc", choices=["poc", "dev", "production"])
    p.add_argument("--residency", default="none", choices=["none", "id", "eu", "us"])
    p.add_argument("--sla", default="standard", choices=["best_effort", "standard", "critical"])
    a = p.parse_args()
    report = validate(
        _parse_edges(a.edges),
        {"environment": a.environment, "data_residency": a.residency, "sla_tier": a.sla},
    )
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
