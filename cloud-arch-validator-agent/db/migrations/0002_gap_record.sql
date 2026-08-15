-- The Gap Report becomes a table.
--
-- It was `app/references/gap_report.jsonl`: appended on every UNCOVERED verdict
-- and every unknown service, gitignored, and living inside the container. That
-- made the one piece of genuine product feedback the system produces — what
-- real users asked about that the graph could not answer — the only data with
-- no durability at all. A rebuild discarded it.
--
-- It belongs here rather than in a file for a reason beyond persistence: the
-- question it exists to answer is "what should the graph cover next", and that
-- is a query against the gaps *and* the graph together. Which unknown services
-- come up most? Are the uncovered pairs clustered on services already in the
-- graph, or on ones missing from it? Those are joins, and they were a
-- hand-written script over a JSONL file.

BEGIN;
SET search_path TO kg, public;

CREATE TABLE IF NOT EXISTS gap_record (
    id                  BIGSERIAL PRIMARY KEY,
    logged_at           TIMESTAMPTZ NOT NULL,

    -- The edge string the user's architecture parsed into, kept verbatim so a
    -- gap can be reproduced by replaying it through the validator.
    request_summary     TEXT NOT NULL,

    -- The specific pair or service id that could not be resolved.
    unresolved_element  TEXT NOT NULL,
    reason              TEXT,

    -- Set when the unresolved element names a service that is in the graph;
    -- NULL when it names one that is not. That distinction is the whole
    -- triage: a known service with an uncovered pair is a missing rule, an
    -- unknown service is a missing node, and they are different work.
    service_id          TEXT REFERENCES service(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS gap_record_logged_at_idx ON gap_record (logged_at);
CREATE INDEX IF NOT EXISTS gap_record_element_idx   ON gap_record (unresolved_element);

-- What the triage question actually looks like: the same gap seen many times
-- is a stronger signal than a long tail seen once, and `last_seen` says whether
-- it is still happening or was fixed.
CREATE OR REPLACE VIEW gap_summary AS
SELECT unresolved_element,
       count(*)                                   AS times_seen,
       min(logged_at)                             AS first_seen,
       max(logged_at)                             AS last_seen,
       bool_or(service_id IS NOT NULL)            AS service_is_known,
       (array_agg(DISTINCT reason))[1:3]          AS sample_reasons
FROM gap_record
GROUP BY unresolved_element
ORDER BY count(*) DESC, max(logged_at) DESC;

COMMIT;
