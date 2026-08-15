"""Agent-facing tools over the knowledge graph.

Every verdict returned here comes from the rule engine in `kg_lib/`, never from
the model. That is root invariant #1, and moving the graph into Postgres did not
touch it: the engine is the same Python it always was, it just receives its rows
from a database instead of from six files. These functions parse arguments,
query, and shape output. They do not judge validity.

The tools are grouped at the bottom of this file — `VALIDATION_TOOLS`,
`EXPLORER_TOOLS`, `CURATOR_TOOLS` — one group per sub-agent. The grouping is the
real access control in the system: the sub-agent that talks to a rep during a
client call is not handed a tool that writes to the graph, so no instruction it
is given can cause a write.
"""

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

# The engine modules import each other by bare name (`import kg`), so their
# directory has to be on sys.path before they are imported. This is a statement
# rather than `from . import kg_lib` on purpose: isort would hoist that import
# above the ones it enables, and the failure would only show at runtime.
_APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_APP_DIR / "kg_lib"))

import check_kg as check_kg_module
import export_kg_graph as export_module
import kg as kg_module
import kg_write as kg_write_module
import pgconn
import translate as translate_module
import validate as validate_module
import verdict_card as verdict_card_module

from app.renderer import render_report

# Loaded once per process. The graph is small and read on nearly every tool
# call, so a query per call would be all latency and no freshness — the only
# writer is the curator sub-agent in this same process, and it reloads
# explicitly (`_reload_kg`) after it writes.
_KG = kg_module.load()


def _reload_kg():
    """Re-read the graph after a write, so the new entry is usable immediately.

    Without this an engineer adds a service, validates an architecture using it
    in the next breath, and is told UNKNOWN_SERVICE by a process holding a
    snapshot from startup — which reads like the write silently failed.
    """
    global _KG
    _KG = kg_module.load()
    return _KG


def _parse_edges(edges: str):
    """'a>b,b>c' -> [('a','b'), ('b','c')]. Raises SystemExit on malformed input."""
    return validate_module._parse_edges(edges)


def validate_architecture(edges: str, environment: str = "poc",
                          data_residency: str = "none",
                          sla_tier: str = "standard") -> dict:
    """Validate a cloud architecture against the knowledge graph rule engine.

    Runs Layer 1 (connectivity: can these services actually talk?) and the
    L0-L8 Layer 2 ladder (security, reliability, data, cost, operations,
    performance, portability). Verdicts are computed by the rule engine, not
    inferred — report them as returned, and never override or soften them.

    Verdicts of UNCOVERED and UNKNOWN_SERVICE are valid, correct answers
    meaning the rules do not cover this case. Relay them as such; do not guess
    what the answer "probably" is.

    Args:
        edges: Connections as 'source>target' pairs, comma-separated, using
            service ids or known aliases. Example: 'cloud-run>cloud-sql,cloud-sql>gcs'.
        environment: Deployment environment — 'poc', 'staging', or 'production'.
            Some rules only fire in production.
        data_residency: Residency requirement, e.g. 'none', 'indonesia', 'eu'.
        sla_tier: Reliability expectation — 'standard' or 'high'.

    Returns:
        A dict with 'summary' (node/edge counts, highest severity), 'layers'
        (per-layer L0-L8 findings, including which edges L1 gated out),
        'connectivity' (per-edge verdicts), 'architecture' (rule findings),
        'exclusive_choices', and 'notes'.
    """
    context = {
        "environment": environment,
        "data_residency": data_residency,
        "sla_tier": sla_tier,
    }
    return validate_module.validate(_parse_edges(edges), context=context, kg=_KG)


def generate_verdict_card(edges: str, environment: str = "", data_residency: str = "",
                          sla_tier: str = "", stated_needs: str = "") -> dict:
    """Build a Verdict Card: one difficulty verdict, tiered findings, mismatch
    detection, an engineer checklist, and automatic Gap Report logging.

    This is the primary tool for a live sales conversation — prefer it over
    calling validate_architecture directly when the rep wants a card-style
    answer rather than a raw findings dump. Every field is derived from the
    rule engine and the knowledge graph, never from your own judgment.

    Each finding is tagged with exactly one evidence tier:
    - 'Proven': a rule matched definitively and every involved service's KG
      entry has been human-confirmed.
    - 'Theoretically Possible': no rule/history covers this — not ruled out,
      but not backed by anything either. Say so plainly, do not guess.
    - 'Requires Deep Review': conflicts with a known rule, or an involved
      service's KG entry is unverified, or the service could not be resolved.

    Leave environment/data_residency/sla_tier empty if the rep doesn't know —
    the tool proceeds on a stated default and reports it as an assumption on
    the card. Do not stop the conversation to ask for these.

    Any finding that is UNCOVERED or an unknown service is automatically
    logged to the Gap Report — this happens unconditionally, you do not need
    to do anything to trigger it and should not ask the user for permission.

    Args:
        edges: Connections as 'source>target' pairs, comma-separated.
        environment: 'poc', 'staging', or 'production'. Leave empty if unknown.
        data_residency: e.g. 'none', 'indonesia', 'eu'. Leave empty if unknown.
        sla_tier: 'standard' or 'high'. Leave empty if unknown.
        stated_needs: Comma-separated plain-language statement of what the
            client said they need (e.g. 'real-time updates,websockets'), used
            only to check for a mismatch between the client's stated ask and
            the actual requirement. Leave empty to skip mismatch checking.

    Returns:
        {'difficulty', 'difficulty_reason', 'findings' (each with 'tier'),
        'mismatches', 'checklist', 'checklist_empty_reason', 'assumptions',
        'context'}.
    """
    return verdict_card_module.generate_verdict_card(
        edges,
        environment=environment or None,
        data_residency=data_residency or None,
        sla_tier=sla_tier or None,
        stated_needs=stated_needs,
        kg=_KG,
        gap_sink=_persist_gaps,
    )


def _persist_gaps(records):
    """Store Gap Report records in Postgres, falling back to the JSONL file.

    A gap is logged while answering a user, so a database that is down must not
    turn a working verdict into an error. The file keeps its old behaviour as
    the fallback, and the failure is reported rather than swallowed silently —
    the point of the gap log is that somebody reads it later, and a log that
    quietly stopped recording is worse than one that never existed.
    """
    if not records:
        return
    # Which named services the graph does not have. Decided here, where the
    # loaded graph is in hand, rather than reconstructed later from a formatted
    # string — an uncovered pair reads "a -> b" and matching that text against
    # known ids finds the half that exists, which inverts the answer.
    for record in records:
        element = record.get("unresolved_element", "")
        named = [t.strip() for t in element.replace("->", " ").split() if t.strip()]
        record["missing_services"] = [
            t for t in named if _KG.resolve(t)[0] is None
        ]
    try:
        with pgconn.connect() as conn:
            kg_write_module.record_gaps(conn, records)
    # Broad on purpose: a gap is logged mid-answer, and no storage failure of
    # any kind should turn a good verdict into an error for the user waiting on
    # it.
    except Exception as exc:
        print(f"gap records fell back to file: {exc}", file=sys.stderr)
        verdict_card_module._append_gap_records(records)


def translate_architecture(edges: str, target_provider: str,
                           environment: str = "poc") -> dict:
    """Translate an architecture from one cloud provider to another.

    Maps each service to its equivalent on the target provider using
    equivalences.yaml, then re-validates the translated result. Some services
    have no equivalent and are reported as unmapped rather than substituted
    with a guess; connectors are dropped and regenerated at the target by
    design, so their absence is not a gap.

    Args:
        edges: Connections as 'source>target' pairs, comma-separated.
        target_provider: 'gcp' or 'azure'.
        environment: 'poc', 'staging', or 'production'.

    Returns:
        A dict with the service mapping, any dropped/unmapped/pending-choice
        services, and a validation report for the translated architecture.
    """
    return translate_module.translate(
        _parse_edges(edges),
        target_provider,
        context={"environment": environment},
        kg=_KG,
    )


def lookup_service(service_id: str) -> dict:
    """Look up one service's properties in the knowledge graph.

    Resolves aliases, so a component name that is not a standalone node
    reports what it actually resolves to.

    Args:
        service_id: Service id or alias, e.g. 'cloud-run' or 'cloud-sql'.

    Returns:
        The node's properties (provider, category, roles, network_placement,
        reachability, region_scope, provenance), plus 'alias_of' when the id
        given was an alias. Returns {'found': False} for an unknown id —
        which is a valid answer, not a failure to be worked around.
    """
    node, alias = _KG.resolve(service_id)
    if node is None:
        return {
            "found": False,
            "service_id": service_id,
            "message": (
                f"'{service_id}' is not in the knowledge graph. This is "
                "UNKNOWN_SERVICE, a legitimate answer — do not substitute a "
                "similar-sounding service."
            ),
        }
    out = {"found": True, **node}
    if alias:
        out["alias_of"] = alias.get("resolves_to")
        out["alias_note"] = alias.get("note")
    return out


def _check_roles(roles):
    """Refuse a role filter the catalog does not know. None means it is fine.

    The read path is where a misspelled role does the most damage, and it had
    no check at all. A filter on `datstore` matched nothing and came back
    `count: 0` — which these tools explicitly tell the model to treat as an
    answer rather than a reason to relax the filter. One dropped letter became
    "no service in the graph has that role", stated confidently to a rep on a
    client call. That is D6's failure shape on a path with no human in it.

    Reads the catalog already in memory; no database call, and the same pure
    check the writer uses so the two cannot disagree about what a role is.
    """
    named = [r for r in roles if r]
    if not named:
        return None
    return kg_write_module.validate_roles(
        {r: e.get("kind") for r, e in _KG.role_catalog.items()}, named
    )


def search_services(provider: str = "", category: str = "", role: str = "") -> dict:
    """List services in the knowledge graph, filtered by typed fields.

    These are structured fields, so filtering is exact-match on values, not
    fuzzy search. Leave a filter empty to skip it.

    Args:
        provider: 'gcp' or 'azure'. Empty for both.
        category: e.g. 'database', 'compute', 'storage', 'network'.
        role: A role from the catalog, e.g. 'connector', 'datastore'. Call
            `list_roles` for the set.

    Returns:
        {'count': N, 'services': [{id, name, provider, category, roles,
        network_placement, reachability, region_scope}, ...]}, or
        {'error': 'unknown_role', ...} when the role is not in the catalog.
    """
    problem = _check_roles([role])
    if problem:
        return problem

    out = []
    for svc_id, svc in _KG.services.items():
        if provider and svc.get("provider") != provider:
            continue
        if category and svc.get("category") != category:
            continue
        if role and role not in svc.get("roles", []):
            continue
        out.append({
            "id": svc_id,
            "name": svc.get("name", svc_id),
            "provider": svc.get("provider"),
            "category": svc.get("category"),
            "roles": svc.get("roles", []),
            "network_placement": svc.get("network_placement"),
            "reachability": svc.get("reachability"),
            "region_scope": svc.get("region_scope"),
        })
    return {"count": len(out), "services": sorted(out, key=lambda s: s["id"])}


def export_kg_graph(provider: str = "", include_edges: bool = False) -> dict:
    """Describe the shape of the knowledge graph itself — the services in it and
    the connections the rules permit between them. Not one specific
    architecture; use validate_architecture for that.

    Edges are omitted by default, and that is usually what you want. There are
    ~691 of them because they are derived rather than stored: every same-provider
    pair the rule engine allows. Asking for them returns roughly 190 KB, which
    answers no question that the counts and per-node degree do not answer better.

    Request them only when the adjacency itself is the answer — "what can Cloud
    Run actually connect to". When the question is about services rather than
    connections, `query_services` and `lookup_service` are the right tools.

    Args:
        provider: Restrict to 'gcp' or 'azure'. Empty for the full graph.
        include_edges: Return every derived edge. Large; leave False unless the
            user needs the adjacency list itself.

    Returns:
        {'nodes': [...], 'counts': {...}, 'edges_omitted': bool}, plus 'edges'
        when include_edges is True. Each node carries 'out_degree', the number
        of services it may connect to.
    """
    graph = export_module.build_graph(_KG)
    if provider:
        graph["nodes"] = [n for n in graph["nodes"] if n.get("provider") == provider]
        keep = {n["id"] for n in graph["nodes"]}
        graph["edges"] = [
            e for e in graph["edges"]
            if e.get("source") in keep and e.get("target") in keep
        ]
    counts = {"nodes": len(graph["nodes"]), "edges": len(graph["edges"])}

    # Degree is computed before the edges are dropped, so the summary still
    # answers "which services are the most connected" without carrying the list
    # that answer was derived from.
    degree = {}
    for edge in graph["edges"]:
        degree[edge.get("source")] = degree.get(edge.get("source"), 0) + 1
    for node in graph["nodes"]:
        node["out_degree"] = degree.get(node["id"], 0)

    if not include_edges:
        graph.pop("edges", None)

    graph["counts"] = counts
    graph["edges_omitted"] = not include_edges
    return graph


def render_ascii_diagram(
    edges: str,
    environment: str = "poc",
    ascii_only: bool = False,
    width: int = 100,
) -> dict:
    """Render a validated architecture as a deterministic ASCII flowchart.

    Boxes carry the service name; the arrows carry the shape. Ids, typed fields,
    connection verdicts and findings are listed underneath, where they do not
    have to fit inside a border.

    Rendering formats rule-engine output only. It never infers validity,
    severity, service equivalence, or missing graph elements. A service the
    graph does not know is drawn under the id given and called out as
    UNKNOWN_SERVICE rather than dropped from the picture.

    Args:
        edges: Connections as 'source>target' pairs, comma-separated.
        environment: 'poc', 'staging', or 'production'.
        ascii_only: Transliterate to 7-bit ASCII, one character per character,
            for places that mangle box-drawing glyphs.
        width: Bounds the text below the chart. The chart's own width comes
            from the layout — a wide fan-out needs the columns it needs, and
            wrapping a diagram breaks it rather than fits it.
    """
    parsed = _parse_edges(edges)
    report = validate_module.validate(parsed, context={"environment": environment}, kg=_KG)
    diagram = render_report(report, _KG, width=width, ascii_only=ascii_only)
    return {
        "format": "terminal",
        "ascii_only": ascii_only,
        "width": width,
        "diagram": diagram,
        "node_count": report["summary"]["nodes"],
        "edge_count": report["summary"]["edges"],
        "finding_count": len(report["architecture"]),
    }


def check_kg_health() -> dict:
    """Run the knowledge graph's own integrity, provenance, and regression gate.

    This is the gate that must pass before any KG change ships: clean
    integrity, 37/37 regression, L1 coverage >= 80%, and no node an agent
    proposed that a human has not signed off.

    Returns:
        {'report': '<full text output>'} — the same report the CLI prints.
    """
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            check_kg_module.main()
    except SystemExit:
        pass
    return {"report": buf.getvalue()}


_INIT_STUB = (
    "cloud-architecture-validator-init is a design stub, not a working tool. "
    "Nothing was fetched or written.\n\n"
    "What is missing: the source URL and its schema are still unpicked. The "
    "fetch method is settled — a plain HTTPS GET against a public URL, "
    "standard library only, no cloud SDK — but no specific catalog has been "
    "chosen to point it at."
)


def add_service_to_kg(
    name: str,
    provider: str,
    category: str = "",
    tier: str = "",
    region_scope: str = "",
    network_placement: str = "",
    reachability: str = "",
    roles: list[str] | None = None,
    references_url: str = "",
) -> dict:
    """Add one service to the knowledge graph. Writes to Postgres.

    `network_placement`, `reachability` and `roles` are never inferred and have
    no defaults — collect them from an engineer before calling. A wrong value in
    any of the three does not fail loudly; it produces confident wrong verdicts
    across every pair the service takes part in.

    `category`, `tier` and `region_scope` are also required. They are looked up
    rather than judged, but the graph cannot store an entry without them, and
    `region_scope` in particular drives the single-zone and single-region
    reliability findings.

    The entry lands as `unverified`: live in the graph, not yet signed off.

    Args:
        name: Product name as the provider writes it, e.g. 'Cloud Run'.
        provider: 'gcp' or 'azure'.
        category: e.g. 'compute', 'database', 'storage', 'network'.
        tier: 'managed', 'self_managed', or 'serverless'.
        region_scope: 'zonal', 'regional', 'multi_region', or 'global'.
        network_placement: One of 'serverless_offvpc', 'in_vpc',
            'managed_service', 'network_fabric', 'connector', 'edge', 'policy'.
        reachability: How it is reached as a target — 'api_endpoint',
            'private_ip', 'public_or_private', or 'n_a'.
        roles: Functional roles from the role catalog, e.g. ['datastore',
            'relational_db']. A role outside the catalog is refused. Call
            `list_roles` for the set.
        references_url: Provider documentation URL, recorded as the source.

    Returns:
        {'written': True, 'entry': {...}, 'note': ...} on success, plus
        'role_warning' when no role given is load-bearing — the entry is
        written and will answer UNCOVERED wherever it appears, which may be
        correct. Relay that warning; do not add a role to make it go away.

        {'written': False, 'error': ..., 'field'/'allowed'/'existing': ...} on
        refusal, with 'did_you_mean' when a role looks like a typo.
    """
    fields = {
        "name": name,
        "provider": provider,
        "category": category,
        "tier": tier,
        "region_scope": region_scope,
        "network_placement": network_placement,
        "reachability": reachability,
        "roles": roles or [],
        "references_url": references_url,
    }
    problem = kg_write_module.validate_fields(fields)
    if problem:
        return {"written": False, **problem}

    with pgconn.connect() as conn:
        result = kg_write_module.add_service(
            conn,
            fields,
            sources=[references_url] if references_url else [],
        )
    if result.get("written"):
        _reload_kg()
    return result


def mark_service_verified(service_id: str, verified_on: str) -> dict:
    """Record that a human has confirmed an agent-proposed entry.

    Only a person who actually checked the three judgment fields should call
    this, and the date is required rather than defaulted to today — a date the
    tool invented would assert a review that may not have happened.

    Args:
        service_id: The id returned by add_service_to_kg.
        verified_on: ISO date (YYYY-MM-DD) the review took place.

    Returns:
        {'updated': True, ...} or {'updated': False, 'reason': ...}.
    """
    with pgconn.connect() as conn:
        result = kg_write_module.mark_verified(conn, service_id, verified_on)
    if result.get("updated"):
        _reload_kg()
    return result


def propose_equivalence(service_name: str, provider_from: str) -> dict:
    """Return recorded cross-cloud mapping, or explicit unknown/not-applicable."""
    node, _ = _KG.resolve(service_name)
    if node is not None and set(node.get("roles", [])) & _KG.regenerate_roles:
        return {
            "status": "not_applicable",
            "reason": "connector role has no equivalent by design",
        }

    target_provider = "azure" if provider_from.lower() == "gcp" else "gcp"
    equivalents, criteria = _KG.equivalents(service_name, target_provider)
    if equivalents:
        return {
            "status": "found",
            "equivalence": {
                "provider_from": provider_from,
                "service_name_from": service_name,
                "provider_to": target_provider,
                "targets": equivalents,
                "selection_criteria": criteria,
            },
        }
    return {"status": "unknown", "message": "no known equivalent yet"}


def init_kg_from_catalog(source: str = "", version_tag: str = "") -> dict:
    """Bulk-populate the knowledge graph from a catalog. NOT IMPLEMENTED."""
    return {"implemented": False, "requested": {"source": source,
            "version_tag": version_tag}, "message": _INIT_STUB}


def query_services(
    provider: str = "",
    category: str = "",
    tier: str = "",
    region_scope: str = "",
    network_placement: str = "",
    reachability: str = "",
    roles_all: list[str] | None = None,
    roles_any: list[str] | None = None,
    unverified_only: bool = False,
) -> dict:
    """Find services by combining typed filters. All conditions must hold.

    This is the query the product wanted for a long time and could not run
    against a folder of files: "which Azure databases are reachable only over a
    private IP", "which regional services hold the connector role". These are
    typed fields, so this is exact matching over a closed set of values — not
    fuzzy search, and not similarity. Leave a filter empty to skip it.

    Prefer this over search_services when more than one condition matters.

    Args:
        provider: 'gcp' or 'azure'.
        category: e.g. 'database', 'compute', 'storage', 'network'.
        tier: 'managed', 'self_managed', or 'serverless'.
        region_scope: 'zonal', 'regional', 'multi_region', or 'global'.
        network_placement: e.g. 'in_vpc', 'serverless_offvpc', 'connector'.
        reachability: e.g. 'private_ip', 'api_endpoint', 'public_or_private'.
        roles_all: Every role listed must be held. Roles come from the
            catalog — call `list_roles` for the set.
        roles_any: At least one role listed must be held.
        unverified_only: Only entries no human has signed off on yet.

    Returns:
        {'count': N, 'services': [...], 'filters': {...}}. An empty result is
        an answer: no service in the graph matches. It is not a reason to relax
        a filter and report something adjacent.

        {'error': 'unknown_role', ...} when a role filter is not in the
        catalog, with `did_you_mean` where a correction is obvious. This is not
        an empty result and must not be reported as one — the filter was
        unanswerable, not unmatched.
    """
    roles_all = roles_all or []
    roles_any = roles_any or []
    problem = _check_roles(list(roles_all) + list(roles_any))
    if problem:
        return problem

    filters = {
        "provider": provider,
        "category": category,
        "tier": tier,
        "region_scope": region_scope,
        "network_placement": network_placement,
        "reachability": reachability,
        "roles_all": roles_all,
        "roles_any": roles_any,
        "unverified_only": unverified_only,
    }

    scalar = {
        "provider": provider,
        "category": category,
        "tier": tier,
        "region_scope": region_scope,
        "network_placement": network_placement,
        "reachability": reachability,
    }

    out = []
    # `ord` ordering, not alphabetical: it is the graph's own precedence, and
    # the first row of a role query is the one validate.py would insert.
    for svc_id, svc in _KG.services.items():
        if any(want and svc.get(field) != want for field, want in scalar.items()):
            continue
        held = set(svc.get("roles", []))
        if roles_all and not set(roles_all) <= held:
            continue
        if roles_any and not set(roles_any) & held:
            continue
        status = (svc.get("provenance") or {}).get("status")
        if unverified_only and status != "unverified":
            continue
        out.append({
            "id": svc_id,
            "name": svc.get("name", svc_id),
            "provider": svc.get("provider"),
            "category": svc.get("category"),
            "tier": svc.get("tier"),
            "roles": svc.get("roles", []),
            "network_placement": svc.get("network_placement"),
            "reachability": svc.get("reachability"),
            "region_scope": svc.get("region_scope"),
            "provenance_status": status,
        })
    return {"count": len(out), "services": out, "filters": filters}


def list_roles(kind: str = "") -> dict:
    """List the role vocabulary, split into load-bearing and descriptive.

    Roles are a closed set. `load_bearing` means something in the engine
    matches the role — a connectivity rule's `when` clause, a `needs_role`, one
    of the L2-L8 checks, or the tech-mismatch rules — so getting one wrong or
    leaving it off changes verdicts. `descriptive` roles are carried for a
    person reading the entry and are read by no rule.

    Use this before asking an engineer which roles a new service holds: the
    load-bearing list is the short one that has to be right, and every role
    carries a note saying where it is read.

    Args:
        kind: 'load_bearing', 'descriptive', or empty for both.

    Returns:
        {'count': N, 'roles': [{'role', 'kind', 'note', 'services'}, ...]}.
        `services` counts how many entries currently hold the role.
    """
    held = {}
    for svc in _KG.services.values():
        for role in svc.get("roles", []):
            held[role] = held.get(role, 0) + 1

    out = [
        {
            "role": role,
            "kind": entry.get("kind"),
            "note": entry.get("note"),
            "services": held.get(role, 0),
        }
        for role, entry in _KG.role_catalog.items()
        if not kind or entry.get("kind") == kind
    ]
    return {"count": len(out), "roles": out, "filters": {"kind": kind}}


# --------------------------------------------------------------- grouping ----
# One list per sub-agent. Which tools a sub-agent holds is the boundary that
# actually enforces the split — an agent cannot be talked into calling a tool it
# was never given, whereas it can always be talked out of following an
# instruction. So the read-only agents hold no writer, and the curator holds no
# verdict tool: a service is either being looked up or being added, and letting
# one agent do both invites adding a service to make an inconvenient
# UNKNOWN_SERVICE go away.

VALIDATION_TOOLS = [
    validate_architecture,
    generate_verdict_card,
    translate_architecture,
    render_ascii_diagram,
    lookup_service,
]

EXPLORER_TOOLS = [
    lookup_service,
    search_services,
    query_services,
    list_roles,
    export_kg_graph,
    check_kg_health,
]

CURATOR_TOOLS = [
    lookup_service,
    query_services,
    list_roles,
    add_service_to_kg,
    mark_service_verified,
    propose_equivalence,
    init_kg_from_catalog,
]

# Every tool any agent can reach, de-duplicated. Used by tests asserting on the
# exposure surface. There is one renderer now: the draw.io emitter was never
# reachable from any agent, carried a known-broken icon path, and needed an
# icon mapping the graph no longer stores.
ALL_TOOLS = list(
    dict.fromkeys(VALIDATION_TOOLS + EXPLORER_TOOLS + CURATOR_TOOLS)
)
