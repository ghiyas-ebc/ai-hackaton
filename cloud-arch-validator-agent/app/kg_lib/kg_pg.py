"""Postgres backend for the knowledge graph.

Returns the same `KnowledgeGraph` object `kg._load_local()` used to build from
YAML — same attributes, same nested shapes, same key-present/key-absent
distinctions. That is the whole design: `validate.py`, `translate.py`,
`verdict_card.py` and `check_kg.py` are untouched by the move to a database.
They still decide every verdict, in Python, from data they receive the same way
they always did. Root invariant #1 is not affected by where the rows are stored
— but it would have been affected by rewriting the evaluator, which is why the
evaluator was not rewritten.

Two entry points, split so the transform can be tested without a database:

    kg_from_rows(rows)   pure: table rows -> KnowledgeGraph
    load()               fetch rows from Postgres, then kg_from_rows

`db/seed_from_yaml.py:build_rows()` emits rows in exactly the shape
`fetch_rows()` returns. The parity test chains build_rows -> kg_from_rows and
compares against the YAML loader, so a lossy migration fails a unit test rather
than a client demo.

A note on absent keys. The YAML omitted optional fields rather than writing
`null`, and downstream code distinguishes the two in places (`"gate" in layer`,
`rule.get("needs_role")`). SQL has no "absent" — only NULL — so every builder
below drops None-valued optional keys on the way out. Removing that would not
break loudly; it would change a handful of verdicts quietly, which is worse.
"""

TABLES = {
    # ORDER BY ord, not by id: `by_role(...)[0]` picks the component that gets
    # inserted into a user's architecture, so row order is a verdict input.
    "service": """
        SELECT id, ord, name, provider, category, tier,
               network_placement, reachability, region_scope, extras,
               prov_generated, prov_status, prov_verified,
               prov_sources, prov_stale_after, rationale
        FROM service ORDER BY ord, id
    """,
    "service_role": """
        SELECT service_id, role, ord FROM service_role
        ORDER BY service_id, ord
    """,
    "connectivity_rule": """
        SELECT id, seq, when_clause, verdict, severity, message,
               relationship, needs_role, rationale
        FROM connectivity_rule ORDER BY seq
    """,
    "architecture_layer": """
        SELECT id, ord, title, description, is_gate, status
        FROM architecture_layer ORDER BY ord
    """,
    "architecture_rule": """
        SELECT id, layer_id, ord, enabled, severity, title, message,
               remediation, applies_when, threshold, rationale
        FROM architecture_rule ORDER BY ord
    """,
    "equivalence": """
        SELECT id, source_id, selection_criteria FROM equivalence ORDER BY id
    """,
    "equivalence_target": """
        SELECT equivalence_id, target_id, ord, level, when_clause,
               caveats, as_kind, feature
        FROM equivalence_target ORDER BY equivalence_id, ord
    """,
    "service_alias": """
        SELECT alias, resolves_to, as_kind, feature, note
        FROM service_alias ORDER BY alias
    """,
    "connection_override": """
        SELECT source_id, target_id, verdict, severity, message, reason
        FROM connection_override ORDER BY source_id, target_id
    """,
    "service_alternative": """
        SELECT id, a_id, b_id, decision FROM service_alternative ORDER BY id
    """,
    "icon_category": """
        SELECT provider, category, name, file FROM icon_category
        ORDER BY provider, category
    """,
    "service_icon": """
        SELECT service_id, provider, type, icon, category, note
        FROM service_icon ORDER BY service_id
    """,
    "kg_setting": "SELECT key, value, note FROM kg_setting ORDER BY key",
}


def _compact(mapping):
    """Drop None values, restoring the YAML's absent-vs-null distinction."""
    return {k: v for k, v in mapping.items() if v is not None}


# ------------------------------------------------------------ pure build ----


def kg_from_rows(rows):
    """Table rows -> KnowledgeGraph. No database access, no I/O."""
    # Imported here rather than at module scope: kg.py dispatches into this
    # module, and a top-level import would close the cycle at import time.
    from kg import KnowledgeGraph

    roles_by_service = {}
    for row in rows["service_role"]:
        roles_by_service.setdefault(row["service_id"], []).append(row["role"])

    services = []
    for row in rows["service"]:
        entry = {
            "id": row["id"],
            "name": row["name"],
            "provider": row["provider"],
            "category": row["category"],
            "tier": row["tier"],
            "roles": roles_by_service.get(row["id"], []),
            "network_placement": row["network_placement"],
            "reachability": row["reachability"],
            "region_scope": row["region_scope"],
            "provenance": _compact(
                {
                    "generated": row["prov_generated"],
                    "status": row["prov_status"],
                    "verified": row["prov_verified"],
                    "sources": row["prov_sources"],
                    "stale_after": row["prov_stale_after"],
                }
            ),
        }
        entry.update(row.get("extras") or {})
        services.append(entry)

    conn_rules = []
    for r in rows["connectivity_rule"]:
        rule = _compact(
            {
                "id": r["id"],
                "when": r["when_clause"],
                "verdict": r["verdict"],
                "message": r["message"],
                "relationship": r["relationship"],
                "needs_role": r["needs_role"],
            }
        )
        # `severity` is exempt from compaction: the YAML declares it on every
        # rule and writes `severity: null` on the six that allow outright.
        # Dropping the key would be a different document.
        rule["severity"] = r["severity"]
        conn_rules.append(rule)

    arch_layers = []
    for r in rows["architecture_layer"]:
        layer = _compact(
            {
                "id": r["id"],
                "title": r["title"],
                "status": r["status"],
                "description": r["description"],
            }
        )
        # `gate` is present only where it is true; validate.py reads presence.
        if r["is_gate"]:
            layer["gate"] = True
        arch_layers.append(layer)

    arch_rules = [
        _compact(
            {
                "id": r["id"],
                "layer": r["layer_id"],
                "enabled": r["enabled"],
                "severity": r["severity"],
                "title": r["title"],
                "message": r["message"],
                "remediation": r["remediation"],
                "applies_when": r["applies_when"],
                "threshold": r["threshold"],
            }
        )
        for r in rows["architecture_rule"]
    ]

    targets_by_eq = {}
    for r in rows["equivalence_target"]:
        targets_by_eq.setdefault(r["equivalence_id"], []).append(
            _compact(
                {
                    "id": r["target_id"],
                    "level": r["level"],
                    "when": r["when_clause"],
                    "caveats": r["caveats"],
                    "as": r["as_kind"],
                    "feature": r["feature"],
                }
            )
        )
    equivalences = [
        _compact(
            {
                "source": r["source_id"],
                "selection_criteria": r["selection_criteria"],
                "targets": targets_by_eq.get(r["id"], []),
            }
        )
        for r in rows["equivalence"]
    ]

    aliases = [
        _compact(
            {
                "alias": r["alias"],
                "resolves_to": r["resolves_to"],
                "as": r["as_kind"],
                "feature": r["feature"],
                "note": r["note"],
            }
        )
        for r in rows["service_alias"]
    ]

    overrides = [
        _compact(
            {
                "source": r["source_id"],
                "target": r["target_id"],
                "verdict": r["verdict"],
                "severity": r["severity"],
                "message": r["message"],
                "reason": r["reason"],
            }
        )
        for r in rows["connection_override"]
    ]

    alternatives = [
        {"pair": [r["a_id"], r["b_id"]], "decision": r["decision"]}
        for r in rows["service_alternative"]
    ]

    icons = {"categories": {}, "services": {}}
    for r in rows["icon_category"]:
        icons["categories"].setdefault(r["provider"], {})[r["category"]] = {
            "name": r["name"],
            "file": r["file"],
        }
    for r in rows["service_icon"]:
        icons["services"][r["service_id"]] = _compact(
            {
                "provider": r["provider"],
                "type": r["type"],
                "icon": r["icon"],
                "category": r["category"],
                "note": r["note"],
            }
        )

    settings = {r["key"]: r["value"] for r in rows["kg_setting"]}

    return KnowledgeGraph(
        services=services,
        conn_rules=conn_rules,
        conn_fallback=settings.get("connectivity_fallback"),
        arch_rules=arch_rules,
        arch_layers=arch_layers,
        aliases=aliases,
        overrides=overrides,
        alternatives=alternatives,
        equivalences=equivalences,
        regenerate_roles=settings.get("regenerate_roles") or [],
        icons=icons,
    )


# ----------------------------------------------------------------- fetch ----


def fetch_rows(conn=None):
    """Read every KG table into the row shape `kg_from_rows` expects."""
    import pgconn

    owned = conn is None
    if owned:
        conn = pgconn.connect()
    try:
        from psycopg.rows import dict_row

        rows = {}
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SET search_path TO kg, public")
            for table, sql in TABLES.items():
                cur.execute(sql)
                rows[table] = cur.fetchall()
        return rows
    finally:
        if owned:
            conn.close()


def load(conn=None):
    rows = fetch_rows(conn)
    if not rows["service"]:
        raise RuntimeError(
            "The knowledge graph is empty. Run `python3 db/seed_from_yaml.py` "
            "against this database before starting the agent — an empty graph "
            "would answer UNKNOWN_SERVICE to every question, which reads like "
            "a working system with no knowledge rather than an unseeded one."
        )
    return kg_from_rows(rows)
