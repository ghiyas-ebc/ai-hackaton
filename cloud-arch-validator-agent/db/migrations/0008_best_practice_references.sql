-- A principal's own published reference architectures, for the capability
-- assessment feature to cite when the company has no delivery history of its
-- own.
--
-- Lives in project_catalog, not kg, on purpose. It is tempting to bulk-load
-- this into the in-memory KnowledgeGraph object the way kg.role_catalog and
-- kg.equivalence are, since it is principal-authored reference knowledge in
-- the same spirit — but that would mean touching app/kg_lib/ (the directory
-- this repo's own CLAUDE.md singles out as sensitive), adding a new file to
-- the generated-YAML round trip (D27), and updating seed_from_yaml.py /
-- export_to_yaml.py / the drift test, for two small hand-authored tables
-- that were never part of that pipeline. Same reasoning that put
-- project_catalog outside kg in the first place (0007's own header): this
-- was never YAML-authored under the old system, so it does not inherit
-- D27's obligations. It sits next to project/project_service instead of a
-- third schema, because it exists only in service of this one feature and
-- shares app/project_lib with it.
--
-- Matched by a closed, hand-curated tag (best_practice_tag), not by service
-- id — the services a reference is about (e.g. Agent Runtime, Memory Bank)
-- may not be modeled as kg.service rows at all, so id-matching would miss
-- exactly the case this table exists to cover. Same closed-vocabulary
-- discipline kg.role_catalog uses for roles (D29): a caller reads the
-- vocabulary (list_best_practice_tags) and selects from it, it does not
-- invent a tag.

BEGIN;

SET search_path TO project_catalog, public;

CREATE TABLE IF NOT EXISTS best_practice_tag (
    tag   TEXT PRIMARY KEY,
    note  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS best_practice_reference (
    id             TEXT PRIMARY KEY,
    tag            TEXT NOT NULL REFERENCES best_practice_tag(tag),

    -- NULL = cross-provider/generic guidance, not tied to one cloud.
    provider       TEXT CHECK (provider IN ('gcp', 'azure')),

    title          TEXT NOT NULL,
    note           TEXT NOT NULL,
    reference_url  TEXT,

    -- Authored order, for stable listing when more than one reference
    -- shares a tag.
    ord            INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS best_practice_reference_tag_idx
    ON best_practice_reference (tag);

COMMIT;
