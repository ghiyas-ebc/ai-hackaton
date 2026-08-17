-- Descriptive labels for Vertex AI Search, added while cataloguing it.
--
-- No load-bearing role fits: 'search_engine' isn't in the catalog, and
-- there's no distinct rule to write it against — the connectivity case
-- (compute reaching it over its global api_endpoint) is already decided by
-- CONN-ANY-TO-API-ENDPOINT for any target with that reachability, same as
-- gemini-api. Uses ml_platform as the load-bearing role instead, matching
-- the rest of the Vertex AI family (vertex-ai, gemini-api).
BEGIN;
SET search_path TO kg, public;

INSERT INTO role_catalog (role, kind, note) VALUES
    ('enterprise_search', 'descriptive',
     'Describes the product category on Vertex AI Search; ml_platform is what rules match.'),
    ('rag', 'descriptive',
     'Describes a usage pattern (retrieval-augmented generation) on Vertex AI Search; no rule matches it.'),
    ('agent_builder', 'descriptive',
     'Names the console family Vertex AI Search ships under; no rule matches it.'),
    ('discovery_engine', 'descriptive',
     'Names the underlying API Vertex AI Search is built on; no rule matches it.')
ON CONFLICT (role) DO NOTHING;

COMMIT;
