"""Unit tests for the KG tool wrappers.

These assert on the rule engine's deterministic output, not on anything an LLM
says — the whole point of the design is that verdicts do not come from the
model, so they are testable here rather than in eval. What is being checked is
the wrapper layer: that the data paths resolve, and that the tools shape output
without altering verdicts.

The write tests use a fake connection rather than a database. What they are
checking is the shape of the write — the refusals, the provenance status, the
position in the ordering — all of which is decided in Python before any SQL
runs. The SQL itself is exercised by the round-trip tests in
`test_kg_postgres_parity.py`, which skip without Postgres.
"""

from app import tools

# Reached through `tools` rather than imported directly: `app.tools` is what
# puts app/kg_lib/ on sys.path, so a bare `import kg_write` at the top of this
# file would run before that happens — and isort would keep it there.
kg_write = tools.kg_write_module


class FakeCursor:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._conn.executed.append((sql, params))
        if "INSERT" in sql:
            self._conn.inserts.append((sql, params))
        if "SELECT id, name, provider" in sql:
            self._result = self._conn.existing_row
        elif "MAX(ord)" in sql:
            self._result = (self._conn.max_ord + 1,)
        elif "UPDATE service" in sql:
            self._result = self._conn.update_returns
        else:
            self._result = None

    def executemany(self, sql, seq):
        for params in seq:
            self.execute(sql, params)

    def fetchone(self):
        return self._result


class FakeConn:
    def __init__(self, existing=None, max_ord=0, update_returns=None):
        self.executed = []
        self.inserts = []
        self.commits = 0
        self.max_ord = max_ord
        self.update_returns = update_returns
        self._existing = existing
        self.existing_row = (
            tuple(existing.get(k) for k in (
                "id", "name", "provider", "category", "network_placement",
                "reachability", "prov_status",
            ))
            if existing
            else None
        )

    def cursor(self, **kwargs):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1


SEEDED_SERVICE_COUNT = 45


def test_kg_loads_the_seeded_baseline() -> None:
    """The graph resolves and holds at least the seeded set, both providers.

    Deliberately a floor rather than an equality. The graph used to be a file,
    where 45 was a fact about the repository; it is now a database the curator
    writes to, where an exact count asserts that nobody has added a service —
    which is not a property worth defending, and would turn a legitimate write
    into a failing build.
    """
    assert len(tools._KG.services) >= SEEDED_SERVICE_COUNT
    providers = {s["provider"] for s in tools._KG.services.values()}
    assert providers == {"gcp", "azure"}
    assert "cloud-run" in tools._KG.services


def test_validate_flags_public_datastore_path() -> None:
    """Serverless compute to managed SQL trips SEC-001 with no private connector."""
    report = tools.validate_architecture("cloud-run>cloud-sql")
    assert report["summary"]["highest_severity"] == "ERROR"
    rule_ids = {f["rule_id"] for f in report["architecture"]}
    assert any(r.startswith("SEC-001") for r in rule_ids)


def test_validate_reports_all_nine_layers() -> None:
    """The L0-L8 ladder is reported in full, including the empty L7."""
    layers = tools.validate_architecture("cloud-run>cloud-sql")["layers"]
    assert len(layers) == 9


def test_unknown_service_is_answered_not_guessed() -> None:
    """An id the KG does not carry is UNKNOWN_SERVICE, never a near match."""
    result = tools.lookup_service("totally-made-up-service")
    assert result["found"] is False
    assert "UNKNOWN_SERVICE" in result["message"]

    report = tools.validate_architecture("cloud-run>totally-made-up-service")
    assert report["summary"]["uncovered"] == 1


def test_lookup_resolves_alias() -> None:
    node = tools.lookup_service("cloud-run")
    assert node["found"] is True
    assert node["provider"] == "gcp"
    assert node["category"] == "compute"


def test_search_filters_are_exact_match() -> None:
    dbs = tools.search_services(provider="gcp", category="database")
    assert dbs["count"] > 0
    assert all(s["provider"] == "gcp" and s["category"] == "database"
               for s in dbs["services"])
    assert tools.search_services(category="not-a-category")["count"] == 0


def test_translate_to_azure_maps_services() -> None:
    result = tools.translate_architecture("cloud-run>cloud-sql", "azure")
    assert result["target_provider"] == "azure"
    assert result["mapping"]


def test_export_graph_can_be_filtered_by_provider() -> None:
    full = tools.export_kg_graph()
    gcp = tools.export_kg_graph(provider="gcp")
    assert full["counts"]["nodes"] == len(tools._KG.services)
    assert 0 < gcp["counts"]["nodes"] < full["counts"]["nodes"]
    assert all(n["provider"] == "gcp" for n in gcp["nodes"])


def test_terminal_renderer_contract_and_drawio_is_not_agent_exposed() -> None:
    result = tools.render_ascii_diagram("cloud-run>cloud-sql", ascii_only=True)
    assert result["format"] == "terminal"
    assert result["diagram"].isascii()
    assert tools.render_ascii_diagram in tools.ALL_TOOLS
    assert tools.render_drawio_diagram not in tools.ALL_TOOLS


def test_kg_health_gate_passes() -> None:
    """37/37 regression and no structural problems — the gate any change clears.

    Problems are filtered to exclude pending provenance, which is not a defect
    in the graph but the sign-off gate doing its job: an entry an agent proposed
    is *supposed* to hold the check open until a human confirms it. Asserting a
    blank report would mean this test only passes when nobody is mid-review, and
    would push whoever hit it toward clearing the flag rather than the review.
    """
    report = tools.check_kg_health()["report"]
    assert "passed 37/37" in report

    problems = [
        line.strip()
        for line in report.splitlines()
        if "[!]" in line and "provenance.status" not in line
    ]
    assert problems == []


def test_an_unverified_entry_holds_the_gate_open() -> None:
    """The other half: pending provenance must actually be reported.

    The check cannot tell whether a `reachability` value is true — it verifies
    structural consistency, not semantic truth. What it can tell is that nobody
    has claimed to look, and refusing to pass on that is the only automated gate
    standing between an agent-proposed entry and a client's architect.
    """
    import types

    check_kg = tools.check_kg_module
    baseline, _ = check_kg.check_provenance(tools._KG)

    pending = {
        **next(iter(tools._KG.services.values())),
        "id": "pending-widget",
        "provenance": {"generated": "agent:kg-curator", "status": "unverified"},
    }
    with_pending = types.SimpleNamespace(
        services={**tools._KG.services, "pending-widget": pending}
    )

    flagged, _ = check_kg.check_provenance(with_pending)
    assert len(flagged) == len(baseline) + 1
    assert any("pending-widget" in line for line in flagged)


VALID_ENTRY = {
    "name": "Foo",
    "provider": "gcp",
    "category": "compute",
    "tier": "serverless",
    "region_scope": "regional",
    "network_placement": "serverless_offvpc",
    "reachability": "api_endpoint",
    "roles": ["compute"],
}


def test_add_service_rejects_missing_judgment_field() -> None:
    """No database is reached at all when a judgment field is absent."""
    result = tools.add_service_to_kg(**{**VALID_ENTRY, "reachability": ""})
    assert result["written"] is False
    assert result["error"] == "missing_field"
    assert result["field"] == "reachability"


def test_add_service_rejects_a_value_outside_the_closed_set() -> None:
    """The old YAML path accepted anything and wrote it.

    It took `network_placement` as free text and stored `.split()` of it — a
    list where the schema wants a scalar — and never checked `reachability`
    against the four legal values. Either mistake produced a node that read as
    present and valid while quietly deciding roughly twenty pairs wrongly. The
    closed sets are now enforced before the write and again by a CHECK
    constraint at the storage layer.
    """
    result = tools.add_service_to_kg(**{**VALID_ENTRY, "reachability": "public_only"})
    assert result["written"] is False
    assert result["error"] == "invalid_value"
    assert result["field"] == "reachability"
    assert "public_or_private" in result["allowed"]

    placement = tools.add_service_to_kg(
        **{**VALID_ENTRY, "network_placement": "public"}
    )
    assert placement["error"] == "invalid_value"


def test_add_service_reports_existing_without_writing() -> None:
    existing = {"id": "foo", "name": "Foo", "provider": "gcp"}
    conn = FakeConn(existing=existing)
    result = kg_write.add_service(conn, dict(VALID_ENTRY))
    assert result["written"] is False
    assert result["error"] == "already_exists"
    assert result["existing"]["id"] == "foo"
    assert conn.inserts == []


def test_add_service_writes_unverified_and_appends_to_the_order() -> None:
    """New entries land last and unverified.

    Appending matters beyond tidiness: `validate.py` resolves a missing
    component with `by_role(role, provider)[0]`, so an entry inserted ahead of
    an existing one would change which connector gets put into architectures
    that have nothing to do with the new service.
    """
    conn = FakeConn(max_ord=44)
    result = kg_write.add_service(
        conn, dict(VALID_ENTRY), sources=["https://example.test"]
    )
    assert result["written"] is True
    assert result["entry"]["id"] == "foo"
    assert result["entry"]["provenance"]["status"] == "unverified"
    assert "unverified" in result["note"]

    service_insert = next(sql for sql, _ in conn.inserts if "INTO service (" in sql)
    assert service_insert
    params = next(p for sql, p in conn.inserts if "INTO service (" in sql)
    assert params[1] == 45, "new service must append, not displace existing order"
    assert "unverified" in service_insert


def test_marking_verified_requires_a_date_the_caller_supplies() -> None:
    """The constraint refuses a verified entry with no date; so does the tool.

    Defaulting this to today would let the agent assert a human review that
    never happened, which is the one thing provenance exists to prevent.
    """
    conn = FakeConn(update_returns=None)
    assert kg_write.mark_verified(conn, "foo", "2026-08-15")["updated"] is False

    conn = FakeConn(update_returns=("foo",))
    result = kg_write.mark_verified(conn, "foo", "2026-08-15")
    assert result == {"updated": True, "id": "foo", "verified": "2026-08-15"}


def test_propose_equivalence_returns_recorded_mapping() -> None:
    result = tools.propose_equivalence("cloud-run", "gcp")
    assert result["status"] == "found"


def test_propose_equivalence_marks_connectors_not_applicable() -> None:
    result = tools.propose_equivalence("serverless-vpc-access", "gcp")
    assert result["status"] == "not_applicable"


def test_propose_equivalence_does_not_guess() -> None:
    result = tools.propose_equivalence("unknown-service", "gcp")
    assert result == {"status": "unknown", "message": "no known equivalent yet"}


def test_init_stub_remains_explicit() -> None:
    result = tools.init_kg_from_catalog()
    assert result["implemented"] is False
    assert "design stub" in result["message"]


def test_all_tools_exposes_new_functions() -> None:
    assert tools.add_service_to_kg in tools.ALL_TOOLS
    assert tools.propose_equivalence in tools.ALL_TOOLS


def test_export_omits_the_derived_edges_by_default() -> None:
    """691 derived edges is 190 KB of context for a question they rarely answer.

    The edges are computed, not stored — every same-provider pair the engine
    allows — so they are output rather than data, and the counts plus per-node
    degree carry the same shape at a fraction of the size. They remain
    available for the case where the adjacency itself is the answer.
    """
    summary = tools.export_kg_graph()
    assert "edges" not in summary
    assert summary["edges_omitted"] is True
    assert summary["counts"]["edges"] > 0, "the count survives the omission"
    assert all("out_degree" in n for n in summary["nodes"])

    full = tools.export_kg_graph(include_edges=True)
    assert len(full["edges"]) == full["counts"]["edges"]
    assert full["edges_omitted"] is False


def test_export_summary_is_an_order_of_magnitude_smaller() -> None:
    import json

    summary = len(json.dumps(tools.export_kg_graph(), default=str))
    full = len(json.dumps(tools.export_kg_graph(include_edges=True), default=str))
    assert summary * 5 < full, f"summary {summary} vs full {full}"
