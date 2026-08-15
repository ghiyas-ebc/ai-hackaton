"""Writes to the knowledge graph.

The only module that inserts. Reads happen from several places; writes happen
here, so the human-confirmation gate is in one file rather than repeated at
every call site that felt like adding a service.

What the database changed, and what it did not:

  changed  A wrong `network_placement` used to be accepted silently and then
           produce confident wrong verdicts across roughly twenty pairs, with
           the integrity check still reporting clean — it verifies structural
           consistency, not semantic truth. The CHECK constraints now reject a
           value outside the closed set at write time, at the storage layer,
           where no caller can route around them.

  not      A value that is inside the closed set and still wrong is still
           wrong, and no constraint can know that. `network_placement`,
           `reachability` and `roles` are not derivable from any catalogue
           lookup, so they still come from a human and land as `unverified`
           until one signs off. The gate is unchanged; it just has a floor
           under it now.
"""

REQUIRED_FIELDS = (
    "name",
    "provider",
    "category",
    "tier",
    "region_scope",
    # The three a lookup cannot answer. Never inferred, never defaulted.
    "network_placement",
    "reachability",
    "roles",
)

# Kept in step with the CHECK constraints in db/schema.sql. Duplicated on
# purpose: the constraint is the authority, but a tool that reports "reachability
# must be one of ..." is more use to the engineer being asked than a caught
# IntegrityError repeated back at them.
ALLOWED = {
    "tier": ("managed", "self_managed", "serverless"),
    "network_placement": (
        "serverless_offvpc",
        "in_vpc",
        "managed_service",
        "network_fabric",
        "connector",
        "edge",
        "policy",
    ),
    "reachability": ("api_endpoint", "private_ip", "public_or_private", "n_a"),
    "region_scope": ("zonal", "regional", "multi_region", "global"),
}


def service_id_for(name):
    return name.lower().replace(" ", "-")


def find_service(conn, name, provider):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, provider, category, network_placement, "
            "reachability, prov_status FROM service "
            "WHERE lower(name) = lower(%s) AND lower(provider) = lower(%s)",
            (name, provider),
        )
        row = cur.fetchone()
    if not row:
        return None
    keys = ("id", "name", "provider", "category", "network_placement",
            "reachability", "prov_status")
    return dict(zip(keys, row))


def validate_fields(fields):
    """Return a problem dict, or None when the entry is writable.

    Checked before touching the database so the engineer gets one clear
    statement of what is missing rather than a constraint violation.
    """
    for field in REQUIRED_FIELDS:
        if not fields.get(field):
            return {"error": "missing_field", "field": field}
    for field, allowed in ALLOWED.items():
        value = fields.get(field)
        if value not in allowed:
            return {
                "error": "invalid_value",
                "field": field,
                "value": value,
                "allowed": list(allowed),
            }
    if not isinstance(fields.get("roles"), (list, tuple)) or not fields["roles"]:
        return {"error": "missing_field", "field": "roles"}
    return None


def add_service(conn, fields, sources=None, generated_by="agent:kg-curator"):
    """Insert one service. Returns the written entry, or a refusal.

    Appends at the end of the ordering, which is what appending to the YAML
    file did. Order is a verdict input — `by_role(...)[0]` picks the component
    inserted into a user's architecture — so a new entry must not displace an
    existing one's precedence.
    """
    problem = validate_fields(fields)
    if problem:
        return {"written": False, **problem}

    existing = find_service(conn, fields["name"], fields["provider"])
    if existing:
        return {"written": False, "error": "already_exists", "existing": existing}

    service_id = fields.get("id") or service_id_for(fields["name"])
    extras = {}
    if fields.get("references_url"):
        extras["references_url"] = fields["references_url"]
    if fields.get("description"):
        extras["description"] = fields["description"]

    import json

    with conn.cursor() as cur:
        cur.execute("SET search_path TO kg, public")
        cur.execute("SELECT COALESCE(MAX(ord), -1) + 1 FROM service")
        ord_ = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO service (
                id, ord, name, provider, category, tier,
                network_placement, reachability, region_scope, extras,
                prov_generated, prov_status, prov_sources
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'unverified', %s
            )
            """,
            (
                service_id,
                ord_,
                fields["name"],
                fields["provider"],
                fields["category"],
                fields["tier"],
                fields["network_placement"],
                fields["reachability"],
                fields["region_scope"],
                json.dumps(extras),
                generated_by,
                json.dumps(list(sources or [])),
            ),
        )
        cur.executemany(
            "INSERT INTO service_role (service_id, role, ord) VALUES (%s, %s, %s)",
            [(service_id, role, i) for i, role in enumerate(fields["roles"])],
        )
        # Every service needs an icon mapping or the integrity check reports the
        # whole graph unclean over one new entry. `generic` is the honest value:
        # nobody has looked up whether the provider ships an icon for this, and
        # the graph already uses `generic` for services where none exists. A
        # curator can promote it to `core` later; leaving the row out would make
        # the next `check_kg_health` call read as though the write broke
        # something.
        cur.execute(
            "INSERT INTO service_icon (service_id, provider, type, note) "
            "VALUES (%s, %s, 'generic', %s)",
            (
                service_id,
                fields["provider"],
                "Icon not yet mapped for this entry; drawn as a generic shape.",
            ),
        )
    conn.commit()

    return {
        "written": True,
        "entry": {
            "id": service_id,
            "name": fields["name"],
            "provider": fields["provider"],
            "category": fields["category"],
            "tier": fields["tier"],
            "network_placement": fields["network_placement"],
            "reachability": fields["reachability"],
            "region_scope": fields["region_scope"],
            "roles": list(fields["roles"]),
            "provenance": {"generated": generated_by, "status": "unverified"},
        },
        # Said plainly because it decides what happens next: an unverified entry
        # is in the graph and will be used, and nobody has confirmed the three
        # fields that a lookup could not answer.
        "note": (
            "Written as unverified. The entry is live in the graph, and its "
            "network_placement, reachability and roles have not been confirmed "
            "by a human. Have an engineer review it before this service appears "
            "in client material."
        ),
    }


def record_gaps(conn, records):
    """Persist Gap Report records.

    The gaps are the product's own feedback: what real users asked about that
    the graph could not answer. They used to append to a JSONL file inside the
    container, which made the one thing nobody can regenerate the one thing
    with no durability.

    `missing_services` is the triage split and the caller supplies it, because
    the caller is the only party that knows: it resolved every id against the
    graph while producing the verdict. Empty means every service named exists
    and the rules do not cover the pair — a rule to write. Non-empty means a
    node is missing. Those are different work, and an earlier version tried to
    infer the distinction in SQL and got it exactly backwards.
    """
    if not records:
        return 0
    with conn.cursor() as cur:
        cur.execute("SET search_path TO kg, public")
        cur.executemany(
            """
            INSERT INTO gap_record (
                logged_at, request_summary, unresolved_element, reason,
                missing_services
            ) VALUES (
                %(logged_at)s, %(request_summary)s, %(unresolved_element)s,
                %(reason)s, %(missing_services)s
            )
            """,
            [
                {
                    "logged_at": r["logged_at"],
                    "request_summary": r["request_summary"],
                    "unresolved_element": r["unresolved_element"],
                    "reason": r.get("reason"),
                    "missing_services": list(r.get("missing_services") or []),
                }
                for r in records
            ],
        )
    conn.commit()
    return len(records)


def mark_verified(conn, service_id, verified_on):
    """Flip an agent-proposed entry to verified. Requires a date by constraint."""
    with conn.cursor() as cur:
        cur.execute("SET search_path TO kg, public")
        cur.execute(
            "UPDATE service SET prov_status = 'verified', prov_verified = %s, "
            "updated_at = now() WHERE id = %s AND prov_status = 'unverified' "
            "RETURNING id",
            (verified_on, service_id),
        )
        row = cur.fetchone()
    conn.commit()
    if not row:
        return {"updated": False, "reason": "no unverified entry with that id"}
    return {"updated": True, "id": service_id, "verified": str(verified_on)}
