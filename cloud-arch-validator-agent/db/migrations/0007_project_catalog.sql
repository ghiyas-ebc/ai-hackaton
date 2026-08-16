-- The company's own delivered-project history, as a catalog separate from the
-- cloud-service knowledge graph.
--
-- `kg` answers "what does the graph say about a service" — provider-general
-- facts the rule engine reasons over. This schema answers a different
-- question: "has the company actually built something like this before."
-- That is not a fact about a service, it is a fact about one project, so it
-- gets its own schema in the same database rather than a corner of `kg` —
-- nothing here is read by validate.py, translate.py, or check_kg.py, and
-- mixing it into `KnowledgeGraph` would make a rule-engine object carry data
-- the engine never evaluates.
--
-- `project_connection` stores literal edges — which service actually talked
-- to which, in one delivered project. That looks like it reverses D2/D27
-- ("validity is derived from node properties at query time, never stored as
-- pairs") and it does not: D2/D27 are about *general* connectivity — whether
-- any Cloud Run may reach any Cloud SQL, a rule the engine computes on demand.
-- This is a one-off fact about what one team built once, closer in kind to
-- `kg.equivalence`/`kg.service_alias` (D27: "genuinely stored... all one
-- hop") than to the derived L1 adjacency. There is no rule to derive it from;
-- it is history, not policy.
--
-- Not exported to YAML the way `kg` is. `app/references/kg/*.yaml` is
-- generated because that data used to be hand-authored and three consumers
-- still need YAML shape (seed input, the CAV_KG_BACKEND=local offline
-- fallback, verdict_grounding's rule-id check — D24/D27). None of that
-- applies here: this was never YAML-authored under the old system, has no
-- offline consumer, and is not checked by verdict_grounding. It goes the
-- other direction instead — hand-authored YAML under
-- `app/references/projects/`, loaded once by `db/seed_past_projects.py`.

BEGIN;

CREATE SCHEMA IF NOT EXISTS project_catalog;
SET search_path TO project_catalog, public;

-- --------------------------------------------------------------- project ----

CREATE TABLE IF NOT EXISTS project (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL,
    use_case     TEXT NOT NULL,

    started_at   DATE NOT NULL,
    ended_at     DATE,

    -- Nullable: an entry can be catalogued as an anonymised descriptor
    -- ("Regional Retail Chain, NDA") rather than a real name, and whoever
    -- authors past_projects.yaml decides that per entry, not this schema.
    client_name  TEXT,

    -- No `ord`. Unlike kg.service.ord, nothing reads project list order as a
    -- decision input the way validate.py's by_role(...)[0] reads service
    -- order — this is presentation only, and started_at DESC is a more
    -- useful default than authoring order for "what have we built recently."
    -- Deliberate break from the ord convention, not an oversight.

    -- Row audit, distinct from started_at/ended_at above on purpose: those
    -- are the project's own business dates, these are "when this catalog
    -- entry was written." Naming both `created_at` would make the two easy
    -- to confuse at a glance.
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ended_not_before_started
        CHECK (ended_at IS NULL OR ended_at >= started_at)
);

-- No natural key for a person the way a service id is a natural key for a
-- service: two members can share a name, and the same person could appear
-- under two roles. SERIAL, same reasoning as kg.equivalence/
-- kg.service_alternative having no natural id to key on.
CREATE TABLE IF NOT EXISTS project_member (
    id               SERIAL PRIMARY KEY,
    project_id       TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    -- Free text, not a foreign key onto kg.role_catalog: that catalog is the
    -- closed vocabulary of cloud-service roles a rule engine matches against
    -- (D29). "Lead Architect" is not a cloud-service role, and forcing it
    -- through that catalog would be a category error, not reuse.
    role_on_project  TEXT NOT NULL,
    ord              INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS project_member_project_idx
    ON project_member (project_id);

-- ----------------------------------------------------- services and edges ----

-- The services a project actually used. Cross-schema FK onto kg.service —
-- the first one in this repo — so a project's catalog entry can never name a
-- service the knowledge graph doesn't recognise, and the diagram can pull
-- real display names/providers instead of duplicating them here.
CREATE TABLE IF NOT EXISTS project_service (
    project_id  TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    service_id  TEXT NOT NULL REFERENCES kg.service(id),
    ord         INTEGER NOT NULL,
    note        TEXT,
    PRIMARY KEY (project_id, service_id)
);

CREATE INDEX IF NOT EXISTS project_service_service_idx
    ON project_service (service_id);

-- The edges. Without these a "diagram" is just the service list above drawn
-- as N disconnected boxes — the exact failure D30 fixed once already for the
-- validator's own renderer. retroflow's input is one "Label A -> Label B"
-- line per edge with no label segment, so `note` here is surfaced as text
-- under the rendered chart, not inside it.
CREATE TABLE IF NOT EXISTS project_connection (
    id                 SERIAL PRIMARY KEY,
    project_id         TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    source_service_id  TEXT NOT NULL REFERENCES kg.service(id),
    target_service_id  TEXT NOT NULL REFERENCES kg.service(id),
    note               TEXT,
    -- Stable input-line order, so the same project renders the same chart
    -- every time (D30 — this output goes in front of a client's architect).
    ord                INTEGER NOT NULL,

    CONSTRAINT no_self_loop CHECK (source_service_id <> target_service_id)
);

CREATE INDEX IF NOT EXISTS project_connection_project_idx
    ON project_connection (project_id);

-- No ON DELETE on either kg.service FK above (RESTRICT by default):
-- deleting a service still referenced by a past project's recorded history
-- is refused rather than silently erasing what was actually built (CASCADE)
-- or forcing a denormalised name snapshot to survive the FK's removal
-- (SET NULL). Costs little in practice — CURATOR_TOOLS has no
-- delete-service tool at all today — but it documents the intent rather
-- than leaving it to accident.

-- -------------------------------------------------------------------- tags ----

-- Rows, not an array column, for the same reason kg.service_role is rows:
-- what gets filtered belongs in rows. `WHERE tag = 'fintech'` is a plausible
-- explorer query.
CREATE TABLE IF NOT EXISTS project_tag (
    project_id  TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    tag         TEXT NOT NULL,
    PRIMARY KEY (project_id, tag)
);

CREATE INDEX IF NOT EXISTS project_tag_tag_idx ON project_tag (tag);

-- -------------------------------------------------------------------- views ----

-- One statement instead of a join the tool layer reassembles every call,
-- same reasoning as kg.service_search. The only place a cross-schema join to
-- kg.service happens at the SQL layer — filtering by provider genuinely
-- needs it here; display-name enrichment elsewhere resolves from the
-- in-process KnowledgeGraph object instead (see app/project_lib).
CREATE OR REPLACE VIEW project_summary AS
SELECT p.id,
       p.name,
       p.description,
       p.use_case,
       p.started_at,
       p.ended_at,
       p.client_name,
       COALESCE(
           (SELECT array_agg(DISTINCT s.provider ORDER BY s.provider)
            FROM project_service ps
            JOIN kg.service s ON s.id = ps.service_id
            WHERE ps.project_id = p.id),
           ARRAY[]::text[]
       ) AS providers,
       COALESCE(
           (SELECT array_agg(t.tag ORDER BY t.tag)
            FROM project_tag t WHERE t.project_id = p.id),
           ARRAY[]::text[]
       ) AS tags,
       (SELECT count(*) FROM project_service ps
        WHERE ps.project_id = p.id) AS service_count,
       (SELECT count(*) FROM project_member m
        WHERE m.project_id = p.id) AS member_count
FROM project p;

COMMIT;
