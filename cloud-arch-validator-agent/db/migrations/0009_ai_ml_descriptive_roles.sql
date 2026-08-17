-- Descriptive labels for two new ai_ml services (Gemini API, Vertex AI Vector
-- Search), added while cataloguing the Sodagr past project.
--
-- None of these are matched by a rule, so none go in load_bearing. Same shape
-- as existing labels like document_db/wide_column_db on top of datastore:
-- true, useful to a reader, read by nothing.
--
-- vector_database specifically: the connectivity concern it might have
-- earned a rule for (compute reaching it over a public endpoint) is already
-- decided by CONN-SERVERLESS-TO-DUAL-ENDPOINT for any serverless_offvpc
-- source, generically, regardless of role. A vector_database-specific rule
-- would either be shadowed by that one (if placed below it) or need a
-- remediation message that's actually different from "use a private
-- connector" (if placed above it) -- and no such distinct, role-general
-- concern exists yet. Follows D29's own promotion path: descriptive until a
-- rule reads it, at which point the catalog is updated to match, not before.
BEGIN;
SET search_path TO kg, public;

INSERT INTO role_catalog (role, kind, note) VALUES
    ('generative_ai', 'descriptive',
     'Describes the model''s function on Gemini API; ml_platform is what rules match.'),
    ('llm', 'descriptive',
     'Describes the model type on Gemini API; ml_platform is what rules match.'),
    ('multimodal', 'descriptive',
     'Describes an input-format capability on Gemini API; no rule matches it.'),
    ('vector_database', 'descriptive',
     'Describes the database model on Vertex AI Vector Search; datastore is what rules match.'),
    ('similarity_search', 'descriptive',
     'Describes the query pattern on Vertex AI Vector Search; no rule matches it.'),
    ('embeddings', 'descriptive',
     'Describes the data shape stored on Vertex AI Vector Search; no rule matches it.'),
    ('ann_index', 'descriptive',
     'Describes the indexing technique on Vertex AI Vector Search; no rule matches it.')
ON CONFLICT (role) DO NOTHING;

COMMIT;
