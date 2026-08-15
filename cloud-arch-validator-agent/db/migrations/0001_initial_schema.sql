-- Knowledge graph schema.
--
-- Replaces the six YAML files under references/kg/. The shape below is not a
-- mechanical translation of those files; it splits them along the line that
-- actually matters at query time:
--
--   * Service facts are relational and typed, because they are what gets
--     filtered. "reachability = 'private_ip' AND category = 'database'" is the
--     query the product has always wanted to run and could never run against a
--     flat file.
--   * Rule predicates stay JSONB, because a `when` clause is an arbitrary
--     nested document and normalising it would mean inventing a predicate
--     table that only validate.py can interpret anyway. The rule engine still
--     evaluates them in Python; the database stores them, it does not judge.
--
-- Ordering is data, not presentation. Connectivity rules are FIRST MATCH WINS,
-- so `seq` is a real column with a unique constraint rather than an implicit
-- file order that a careless UPDATE could scramble.
--
-- The YAML comments carried most of the reasoning behind this model. They are
-- not dropped: every table that had them gets a `rationale` column, and the
-- seed script moves them across.

BEGIN;

CREATE SCHEMA IF NOT EXISTS kg;
SET search_path TO kg, public;

-- ---------------------------------------------------------------- nodes ----

CREATE TABLE IF NOT EXISTS service (
    id                 TEXT PRIMARY KEY,

    -- Authored order, and it is load-bearing. validate.py resolves a missing
    -- component with `by_role(role, provider)[0]` — the FIRST service holding
    -- the role. Ordering these rows by id instead would quietly swap which
    -- connector gets inserted into a client's architecture, with every test
    -- still green. New entries append (max + 1), exactly as appending to the
    -- YAML file used to.
    ord                INTEGER NOT NULL,

    name               TEXT NOT NULL,
    provider           TEXT NOT NULL,
    category           TEXT NOT NULL,
    tier               TEXT NOT NULL
        CHECK (tier IN ('managed', 'self_managed', 'serverless')),

    -- The three fields a catalogue lookup cannot answer. D6: a wrong value
    -- here fails silently across ~20 pairs, which is why they are constrained
    -- to a closed set here and gated by provenance below.
    network_placement  TEXT NOT NULL
        CHECK (network_placement IN ('serverless_offvpc', 'in_vpc',
                                     'managed_service', 'network_fabric',
                                     'connector', 'edge', 'policy')),
    reachability       TEXT NOT NULL
        CHECK (reachability IN ('api_endpoint', 'private_ip',
                                'public_or_private', 'n_a')),

    region_scope       TEXT NOT NULL
        CHECK (region_scope IN ('zonal', 'regional', 'multi_region', 'global')),

    -- Sparse per-service extras (engines, apis, features, attaches_to_roles).
    -- Four keys across 45 rows; a column each would be four mostly-NULL
    -- columns and a migration every time a fifth appears.
    extras             JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- D21 provenance. `generated` records who proposed the entry, `status`
    -- whether a human has vouched for the three judgement fields above.
    prov_generated     TEXT NOT NULL,
    prov_status        TEXT NOT NULL
        CHECK (prov_status IN ('manual', 'unverified', 'verified')),
    prov_verified      DATE,
    prov_sources       JSONB,
    prov_stale_after   DATE,

    rationale          TEXT,

    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- D21 used to be a check_kg.py pass that ran when someone remembered to
    -- run it. As a constraint it cannot be skipped: claiming a human verified
    -- an agent-proposed entry requires saying when.
    CONSTRAINT verified_needs_a_date
        CHECK (prov_status <> 'verified' OR prov_verified IS NOT NULL)
);

-- Roles are many-per-service and are matched by rules and by translation, so
-- they are rows, not an array column: `WHERE role = 'http_target'` beats
-- unnesting on every query. `ord` preserves the authored order so output that
-- lists roles reads the same as it did from YAML.
CREATE TABLE IF NOT EXISTS service_role (
    service_id  TEXT NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    ord         INTEGER NOT NULL,
    PRIMARY KEY (service_id, role)
);

CREATE INDEX IF NOT EXISTS service_role_role_idx ON service_role (role);
CREATE INDEX IF NOT EXISTS service_ord_idx ON service (ord);
CREATE INDEX IF NOT EXISTS service_provider_idx ON service (provider);
CREATE INDEX IF NOT EXISTS service_category_idx ON service (category);
CREATE INDEX IF NOT EXISTS service_reachability_idx ON service (reachability);
CREATE INDEX IF NOT EXISTS service_placement_idx ON service (network_placement);
CREATE INDEX IF NOT EXISTS service_extras_idx ON service USING GIN (extras);

-- ------------------------------------------------------ layer 1 rules ----

CREATE TABLE IF NOT EXISTS connectivity_rule (
    id            TEXT PRIMARY KEY,
    -- FIRST MATCH WINS. Specific rules must sort above the general rules that
    -- would also match them, so evaluation order is stored explicitly.
    seq           INTEGER NOT NULL UNIQUE,
    when_clause   JSONB NOT NULL,
    verdict       TEXT NOT NULL
        CHECK (verdict IN ('ALLOWED', 'ALLOWED_WITH_NOTE', 'NEEDS_COMPONENT',
                           'BLOCKED', 'UNCOVERED')),
    -- Nullable, and the YAML wrote `severity: null` explicitly for the rules
    -- that allow a connection outright. A NOT NULL here would have rejected six
    -- of the eighteen rules at seed time.
    severity      TEXT,
    message       TEXT NOT NULL,
    relationship  TEXT,
    -- Resolved to a concrete service of the TARGET provider at runtime, which
    -- is why intermediaries survive cross-provider translation.
    needs_role    TEXT,
    rationale     TEXT,

    CONSTRAINT needs_component_needs_a_role
        CHECK (verdict <> 'NEEDS_COMPONENT' OR needs_role IS NOT NULL)
);

-- --------------------------------------------------- layers 2-8 rules ----

CREATE TABLE IF NOT EXISTS architecture_layer (
    id           TEXT PRIMARY KEY,
    ord          INTEGER NOT NULL UNIQUE,
    title        TEXT NOT NULL,
    description  TEXT,
    -- L1 is the gate: an edge that cannot connect is withheld from L2-L8 so
    -- one broken connection does not spray derived findings across seven
    -- layers and bury the finding that matters.
    is_gate      BOOLEAN NOT NULL DEFAULT false,
    -- L7 ships `uncovered`: it has no rules because it needs node properties
    -- the graph does not carry, and reports that instead of inferring them.
    status       TEXT
);

CREATE TABLE IF NOT EXISTS architecture_rule (
    id            TEXT PRIMARY KEY,
    layer_id      TEXT NOT NULL REFERENCES architecture_layer(id),
    ord           INTEGER NOT NULL,
    enabled       BOOLEAN NOT NULL DEFAULT true,
    severity      TEXT NOT NULL,
    title         TEXT NOT NULL,
    message       TEXT NOT NULL,
    remediation   TEXT,
    -- Which context values switch the rule on (environment, data_residency,
    -- sla_tier). NULL means always active.
    applies_when  JSONB,
    threshold     JSONB,
    rationale     TEXT,

    UNIQUE (layer_id, ord)
);

-- ------------------------------------------------------- equivalences ----

CREATE TABLE IF NOT EXISTS equivalence (
    id                  SERIAL PRIMARY KEY,
    source_id           TEXT NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    -- REQUIRED when more than one target exists: 1:N equivalence without a
    -- selection question emits two nodes for one role.
    selection_criteria  TEXT,
    UNIQUE (source_id)
);

CREATE TABLE IF NOT EXISTS equivalence_target (
    equivalence_id  INTEGER NOT NULL REFERENCES equivalence(id) ON DELETE CASCADE,
    target_id       TEXT NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    ord             INTEGER NOT NULL,
    level           TEXT NOT NULL,
    when_clause     TEXT,
    caveats         TEXT,
    as_kind         TEXT,
    feature         TEXT,
    PRIMARY KEY (equivalence_id, target_id)
);

-- ----------------------------------------------- aliases and overrides ----

CREATE TABLE IF NOT EXISTS service_alias (
    alias        TEXT PRIMARY KEY,
    resolves_to  TEXT NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    as_kind      TEXT,
    feature      TEXT,
    note         TEXT
);

-- Deliberately near-empty. Validity is derived from node properties by
-- connectivity_rule; a row here is an admission that the rules could not
-- express something, so each one carries its reason.
CREATE TABLE IF NOT EXISTS connection_override (
    source_id  TEXT NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    target_id  TEXT NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    verdict    TEXT NOT NULL,
    severity   TEXT,
    message    TEXT,
    reason     TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id)
);

CREATE TABLE IF NOT EXISTS service_alternative (
    id        SERIAL PRIMARY KEY,
    a_id      TEXT NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    b_id      TEXT NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    decision  TEXT NOT NULL,
    UNIQUE (a_id, b_id)
);

-- -------------------------------------------------------------- icons ----

CREATE TABLE IF NOT EXISTS icon_category (
    provider  TEXT NOT NULL,
    category  TEXT NOT NULL,
    name      TEXT NOT NULL,
    file      TEXT NOT NULL,
    PRIMARY KEY (provider, category)
);

CREATE TABLE IF NOT EXISTS service_icon (
    service_id  TEXT PRIMARY KEY REFERENCES service(id) ON DELETE CASCADE,
    provider    TEXT NOT NULL,
    -- `generic` means the provider ships no icon for this service and the
    -- renderer should fall back to a plain shape. It is a real answer, not a
    -- missing mapping, and carries a note saying which shape to use.
    type        TEXT NOT NULL CHECK (type IN ('core', 'category', 'generic')),
    icon        TEXT,
    category    TEXT,
    note        TEXT,

    CONSTRAINT core_needs_a_file    CHECK (type <> 'core'     OR icon IS NOT NULL),
    CONSTRAINT category_needs_a_key CHECK (type <> 'category' OR category IS NOT NULL)
);

-- ----------------------------------------------------------- settings ----

-- Small singletons that are not worth a table each: the connectivity fallback
-- verdict and the roles equivalences regenerates at the target rather than
-- translating.
-- Also holds the `doc:*` rows carrying each source file's header commentary —
-- the field definitions and the reasoning behind them. Those are note-only, so
-- `value` is nullable: a row here is either a setting or a piece of
-- documentation, and documentation has no value to read.
CREATE TABLE IF NOT EXISTS kg_setting (
    key    TEXT PRIMARY KEY,
    value  JSONB,
    note   TEXT,

    CONSTRAINT setting_has_value_or_note
        CHECK (value IS NOT NULL OR note IS NOT NULL)
);

-- -------------------------------------------------------------- views ----

-- The query the product could not run against YAML. Kept as a view so the
-- explorer agent's search tool is one statement rather than a join it has to
-- reassemble every call.
CREATE OR REPLACE VIEW service_search AS
SELECT s.id,
       s.ord,
       s.name,
       s.provider,
       s.category,
       s.tier,
       s.network_placement,
       s.reachability,
       s.region_scope,
       s.prov_status,
       COALESCE(
           (SELECT array_agg(r.role ORDER BY r.ord)
            FROM service_role r WHERE r.service_id = s.id),
           ARRAY[]::text[]
       ) AS roles
FROM service s;

COMMIT;
