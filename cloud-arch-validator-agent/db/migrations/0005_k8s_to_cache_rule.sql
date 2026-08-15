-- A pod reaching a managed cache gets its own rule, and `cache` becomes
-- load-bearing.
--
-- The role catalog made a gap visible that nothing reported before. Of the
-- seven database-model roles in the graph, exactly one — `relational_db` — was
-- load-bearing, and only because CONN-K8S-TO-RELATIONAL-DB happens to name it.
-- The consequence showed up as inconsistent advice for the same concern:
--
--   gke-autopilot -> cloud-sql     WARNING  use an auth proxy, not static credentials
--   gke-autopilot -> memorystore   INFO     valid if both sit in the same network
--
-- Both are a pod holding a long-lived credential for a datastore. The second
-- said nothing about it, because `cache` appeared in no rule and so the pair
-- fell through to the generic same-VPC note.
--
-- Why a separate rule rather than adding `cache` to the relational one: the
-- remediation genuinely differs. The relational message names an auth proxy
-- sidecar, which is a real product for managed SQL and has no counterpart for
-- a managed cache. Widening the rule would have meant softening its message
-- until it stopped naming the fix, which costs the rule its usefulness on the
-- pairs it already handles well. Two rules, each saying something true, beats
-- one saying something vague.
--
-- Severity is INFO, not WARNING, on D14's rule: this severity is reasoned
-- rather than measured, and an untuned rule renders at INFO until it has been
-- checked against real client material. It fires on every GKE-plus-cache
-- architecture, which is a common shape, and a WARNING that turns out to be
-- noise teaches people to skim the whole report. Promoting it later is one
-- UPDATE; recovering from alarm fatigue is not.

BEGIN;
SET search_path TO kg, public;

-- Layer 1 is FIRST MATCH WINS, so this has to sit above CONN-INVPC-TO-PRIVATE,
-- which is what currently decides these pairs. Placed directly after the
-- relational rule to keep the two pod-to-datastore rules adjacent.
--
-- `seq` is UNIQUE, and a single `seq = seq + 1` can hit a transient duplicate
-- depending on the order rows are updated. Negating first moves them out of
-- the way of the values they are about to occupy.
UPDATE connectivity_rule SET seq = -seq WHERE seq >= 11;
UPDATE connectivity_rule SET seq = (-seq) + 1 WHERE seq < 0;

-- Guarded on the table already having rows, and the two UPDATEs above are
-- no-ops on an empty one. This is a data migration, not a schema change: it
-- moves an existing database to where a freshly seeded one already is. On a
-- fresh database `connectivity_rule` is empty when migrations run and
-- `seed_from_yaml.py` loads every rule from the export a moment later, this
-- one included — inserting here as well would collide on both the primary key
-- and `seq`.
INSERT INTO connectivity_rule (id, seq, when_clause, verdict, severity, message)
SELECT
    'CONN-K8S-TO-CACHE',
    11,
    '{"source": {"any_role": ["kubernetes"]}, "target": {"any_role": ["cache"]}}'::jsonb,
    'ALLOWED_WITH_NOTE',
    'INFO',
    'A managed cache is reached with a long-lived auth string by default, and '
    'that string tends to live in a manifest or an environment variable rather '
    'than in the secret store. Prefer the provider''s identity-based '
    'authentication with workload identity where the cache supports it; where '
    'the auth string is used, mount it from the secret store and keep '
    'in-transit encryption on.'
WHERE EXISTS (SELECT 1 FROM connectivity_rule);

UPDATE role_catalog
   SET kind = 'load_bearing',
       note = 'Matched by CONN-K8S-TO-CACHE. Promoted from descriptive when '
              'that rule was written — the catalog follows the rules rather '
              'than licensing them.'
 WHERE role = 'cache';

COMMIT;
