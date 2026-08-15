-- Fix the gap triage. 0002 asked SQL a question only Python can answer.
--
-- 0002 resolved `gap_record.service_id` by matching the unresolved element
-- against known service ids with LIKE. On an uncovered pair that reads
-- "cloud-run -> cloud-composer" the match finds `cloud-run` — the half that
-- exists — and records the gap as being about a service the graph knows.
-- Exactly backwards: `cloud-composer` is the missing one, and the field was
-- inverting the triage it existed to support.
--
-- The caller already knows. It resolves every id against the in-memory graph
-- before the verdict is produced, so which ones failed is a fact at that
-- moment rather than something to reconstruct from a formatted string.
-- `missing_services` records it directly; empty means every service named was
-- known and the gap is a missing *rule*, which is different work from a
-- missing *node*.

BEGIN;
SET search_path TO kg, public;

DROP VIEW IF EXISTS gap_summary;

ALTER TABLE gap_record DROP COLUMN IF EXISTS service_id;
ALTER TABLE gap_record
    ADD COLUMN IF NOT EXISTS missing_services TEXT[] NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS gap_record_missing_idx
    ON gap_record USING GIN (missing_services);

CREATE OR REPLACE VIEW gap_summary AS
SELECT unresolved_element,
       count(*)                          AS times_seen,
       min(logged_at)                    AS first_seen,
       max(logged_at)                    AS last_seen,
       -- Empty across every sighting means the services are all in the graph
       -- and the rules simply do not cover the pair: a rule to write, not a
       -- node to add.
       (SELECT COALESCE(array_agg(DISTINCT s), '{}'::text[])
          FROM gap_record g2, unnest(g2.missing_services) AS s
         WHERE g2.unresolved_element = gap_record.unresolved_element)
                                         AS missing_services,
       (array_agg(DISTINCT reason))[1:3]  AS sample_reasons
FROM gap_record
GROUP BY unresolved_element
ORDER BY count(*) DESC, max(logged_at) DESC;

COMMIT;
