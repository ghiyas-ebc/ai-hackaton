"""Agent-facing tools wrapping the cloud-architecture-validator skills.

Every verdict returned here comes from the vendored rule engine in `kg_lib/`,
never from the model — that is root invariant #1 of the skill this agent wraps.
These functions parse arguments and shape output; they do not judge validity.
"""

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

# The vendored scripts import each other by bare name (`import kg`), so their
# directory has to be on sys.path before they are imported. This is a statement
# rather than `from . import kg_lib` on purpose: isort would hoist that import
# above the ones it enables, and the failure would only show at runtime.
_APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_APP_DIR / "kg_lib"))
# Add-service helpers are kept in sibling skill scripts. Import them lazily below
# so agent startup stays independent of authoring-only dependencies.
_ADD_SCRIPTS_DIR = _APP_DIR.parent.parent / "cloud-architecture-validator-add" / "scripts"
sys.path.insert(0, str(_ADD_SCRIPTS_DIR))

import check_kg as check_kg_module
import emit_drawio as emit_drawio_module
import export_kg_graph as export_module
import kg as kg_module
import translate as translate_module
import validate as validate_module
import verdict_card as verdict_card_module

from app.renderer import render_report

# The KG is ~46 KB of YAML across six files and never changes at runtime
# (nothing in the validate path writes to it), so load it once per process.
_KG = kg_module.load()


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
    )


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
    out = {"found": True, **{k: v for k, v in node.items() if k != "icon_path"}}
    if alias:
        out["alias_of"] = alias.get("resolves_to")
        out["alias_note"] = alias.get("note")
    return out


def search_services(provider: str = "", category: str = "", role: str = "") -> dict:
    """List services in the knowledge graph, filtered by typed fields.

    These are structured fields, so filtering is exact-match on values, not
    fuzzy search. Leave a filter empty to skip it.

    Args:
        provider: 'gcp' or 'azure'. Empty for both.
        category: e.g. 'database', 'compute', 'storage', 'network'.
        role: e.g. 'connector', 'datastore', 'entrypoint'.

    Returns:
        {'count': N, 'services': [{id, name, provider, category, roles,
        network_placement, reachability, region_scope}, ...]}.
    """
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


def export_kg_graph(provider: str = "") -> dict:
    """Export the whole knowledge graph as nodes and edges, for exploring it.

    This describes the KG itself — every service and every connection the
    rules permit between them — not one specific architecture. Use
    validate_architecture for a specific design.

    Args:
        provider: Restrict to 'gcp' or 'azure'. Empty for the full graph.

    Returns:
        {'nodes': [...], 'edges': [...], 'counts': {...}}. Large — summarize
        rather than reciting it.
    """
    graph = export_module.build_graph(_KG)
    if provider:
        graph["nodes"] = [n for n in graph["nodes"] if n.get("provider") == provider]
        keep = {n["id"] for n in graph["nodes"]}
        graph["edges"] = [
            e for e in graph["edges"]
            if e.get("source") in keep and e.get("target") in keep
        ]
    graph["counts"] = {"nodes": len(graph["nodes"]), "edges": len(graph["edges"])}
    return graph


def render_drawio_diagram(edges: str, environment: str = "poc") -> dict:
    """Render an architecture as draw.io XML, annotated with validation findings.

    Icon embedding is deliberately off: `--embed-icons` is a known-broken code
    path in the underlying script and is not exposed here.

    Args:
        edges: Connections as 'source>target' pairs, comma-separated.
        environment: 'poc', 'staging', or 'production'.

    Returns:
        {'format': 'drawio-xml', 'xml': '<mxfile>...'} — the user opens this in
        draw.io. Do not paste the XML into the reply; hand it over as a file or
        tell the user it is ready.
    """
    parsed = _parse_edges(edges)
    report = validate_module.validate(parsed, context={"environment": environment}, kg=_KG)
    xml = emit_drawio_module.emit(
        report["connectivity"], report, kg=_KG, embed_icons=False
    )
    return {"format": "drawio-xml", "xml": xml}


def render_ascii_diagram(
    edges: str,
    environment: str = "poc",
    ascii_only: bool = False,
    width: int = 100,
) -> dict:
    """Render validated architecture as deterministic terminal text.

    Rendering formats rule-engine output only. It never infers validity, severity,
    service equivalence, or missing graph elements.
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
    network_placement: str = "",
    reachability: str = "",
    roles: list[str] | None = None,
    references_url: str = "",
) -> dict:
    """Add service after human supplies judgment fields.

    Safe fields are proposed by existing add-service helpers. Network placement,
    reachability, and roles are never inferred; caller must collect them from
    engineer before this tool writes. New entries remain unverified.
    """
    roles = roles or []
    required = {
        "network_placement": network_placement,
        "reachability": reachability,
        "roles": roles,
    }
    for field, value in required.items():
        if not value:
            return {"written": False, "error": "missing_field", "field": field}

    try:
        from kg_io import find_existing, load_services, write_entry
        from propose import propose_safe_fields
        from provenance import build_provenance
    except ModuleNotFoundError:
        # Deployed agent package does not include authoring-only sibling scripts.
        # Keep same non-interactive contract with PyYAML-only local helpers.
        import yaml

        def load_services(path):
            with open(path, encoding="utf-8") as handle:
                return yaml.safe_load(handle) or {"services": []}

        def find_existing(services, service_name, service_provider):
            return next(
                (
                    entry
                    for entry in services.get("services", [])
                    if entry.get("name", "").lower() == service_name.lower()
                    and entry.get("provider", "").lower() == service_provider.lower()
                ),
                None,
            )

        def write_entry(path, services, entry, mode="append"):
            services.setdefault("services", []).append(entry)
            with open(path, "w", encoding="utf-8") as handle:
                yaml.safe_dump(services, handle, sort_keys=False)

        def propose_safe_fields(service_name, service_provider, reference_url=None):
            return {
                "category": None,
                "description": None,
                "references_url": reference_url,
                "icon": None,
                "sources": [reference_url] if reference_url else [],
            }

        def build_provenance(sources):
            return {
                "generated": "cloud-architecture-validator-add",
                "status": "unverified",
                "sources": sources or [],
            }

    kg_path = _APP_DIR / "references" / "kg" / "services.yaml"
    services = load_services(kg_path)
    existing = find_existing(services, name, provider)
    if existing:
        return {"written": False, "existing": existing}

    proposal = propose_safe_fields(name, provider, references_url or None)
    entry = {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "provider": provider,
        "category": proposal.get("category"),
        "description": proposal.get("description"),
        "references_url": references_url or proposal.get("references_url"),
        "icon": proposal.get("icon"),
        "network_placement": network_placement.split(),
        "reachability": reachability,
        "roles": roles,
        "provenance": build_provenance(proposal.get("sources", [])),
    }
    write_entry(kg_path, services, entry, mode="append")
    return {"written": True, "entry": entry}


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


ALL_TOOLS = [
    validate_architecture,
    generate_verdict_card,
    translate_architecture,
    lookup_service,
    search_services,
    export_kg_graph,
    render_ascii_diagram,
    check_kg_health,
    add_service_to_kg,
    propose_equivalence,
    init_kg_from_catalog,
]
