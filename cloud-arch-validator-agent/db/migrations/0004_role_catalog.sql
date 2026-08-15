-- A vocabulary for `roles`, and the line between the ones that decide and the
-- ones that describe.
--
-- Roles were free text. Two things followed, both silent.
--
-- A typo is invisible. `datstore` inserts cleanly, matches no rule, and leaves
-- a node that reads as present and fully specified. That is the same failure
-- class D6 describes for `reachability` — a wrong value producing confident
-- wrong verdicts with `check_kg.py` reporting clean, because it verifies
-- structural consistency and not spelling. A foreign key puts the refusal at
-- the storage layer, where D26 already put the other closed sets.
--
-- And the curator asked for all of them with equal weight. 19 of the 40 roles
-- in the graph are matched by something: a connectivity rule's `when` clause,
-- a `needs_role`, one of validate.py's L2-L8 checks, verdict_card.py's
-- MISMATCH_RULES, or `regenerate_roles`. The other 21 appear in no rule at
-- all. `wide_column_db` on Bigtable is true and useful to a person reading the
-- entry, and it changes no verdict. Asking an engineer to get all forty right
-- with nothing saying which ones move anything spends their attention evenly
-- across a set where it is not evenly needed.
--
-- `kind` records which is which. It is not a permission: a descriptive role is
-- a real role, and a rule may start matching one, at which point it is
-- promoted here and the curator begins insisting on it. The flow is
-- rules-first — the catalog follows what the engine reads, it does not license
-- it.

BEGIN;
SET search_path TO kg, public;

CREATE TABLE IF NOT EXISTS role_catalog (
    role  TEXT PRIMARY KEY,

    -- load_bearing  something in the engine matches this role, so a missing or
    --               misspelled one changes verdicts
    -- descriptive   carried for the reader; no rule reads it
    kind  TEXT NOT NULL CHECK (kind IN ('load_bearing', 'descriptive')),

    -- For a load-bearing role, where it is matched. That is the fact worth
    -- recording: it is what a future editor needs before renaming or removing
    -- one, and it is what makes the load_bearing claim checkable by reading.
    note  TEXT
);

-- Seeded here rather than by the seed script because the foreign key below
-- cannot be added to a populated database until the vocabulary exists, and
-- migrations run against populated databases. `seed_from_yaml.py` re-asserts
-- these rows from the export afterwards, so the file stays authoritative for
-- their contents.
INSERT INTO role_catalog (role, kind, note) VALUES
    ('analytics_sink', 'load_bearing',
     'Matched by CONN-PROCESSING-TO-SINK as a pipeline''s target.'),
    ('compute', 'load_bearing',
     'Matched by CONN-MESSAGING-TO-PROCESSING, and read by the direction '
     'convention that flips an edge pointing out of a passive store.'),
    ('connector', 'load_bearing',
     'SEC-001 reads it to decide whether a private path exists anywhere in the '
     'architecture, and equivalences regenerates it at the target provider '
     'rather than translating it.'),
    ('data_processing', 'load_bearing',
     'Matched by CONN-MESSAGING-TO-PROCESSING and CONN-PROCESSING-TO-SINK.'),
    ('datastore', 'load_bearing',
     'Matched by CONN-EDGE-TO-NON-HTTP and CONN-PROCESSING-TO-SINK, and read by '
     'SEC-002, REL-003, GOV-001 and the direction convention.'),
    ('edge_entry', 'load_bearing',
     'Matched by CONN-EDGE-TO-HTTP, CONN-EDGE-TO-NON-HTTP and '
     'CONN-POLICY-ATTACH-VALID. SEC-003 fires on its absence.'),
    ('event_consumer', 'load_bearing',
     'Matched by CONN-MESSAGING-TO-PROCESSING and by verdict_card''s '
     'tech-mismatch rules.'),
    ('event_router', 'load_bearing',
     'Matched by verdict_card''s tech-mismatch rules.'),
    ('event_source', 'load_bearing',
     'Matched by CONN-MESSAGING-TO-PROCESSING, and what keeps a store that also '
     'emits events from being normalized as a passive target.'),
    ('http_target', 'load_bearing',
     'Matched by CONN-EDGE-TO-HTTP and read by SEC-003.'),
    ('kubernetes', 'load_bearing',
     'Matched by CONN-K8S-TO-RELATIONAL-DB and CONN-K8S-TO-SECRET.'),
    ('load_balancer_l7', 'load_bearing',
     'Matched by CONN-POLICY-ATTACH-VALID — a WAF attaches here and nowhere '
     'else.'),
    ('message_queue', 'load_bearing',
     'Matched by verdict_card''s tech-mismatch rules.'),
    ('messaging', 'load_bearing',
     'Matched by CONN-MESSAGING-TO-PROCESSING and by verdict_card''s '
     'tech-mismatch rules.'),
    ('ml_platform', 'load_bearing',
     'Matched by CONN-PROCESSING-TO-SINK.'),
    ('relational_db', 'load_bearing',
     'Matched by CONN-K8S-TO-RELATIONAL-DB.'),
    ('secret_store', 'load_bearing',
     'Matched by CONN-K8S-TO-SECRET. SEC-002 fires on its absence.'),
    ('serverless_vpc_connector', 'load_bearing',
     'The needs_role on every NEEDS_COMPONENT rule, resolved to a concrete '
     'service of the target provider with by_role(...)[0].'),
    ('stream_processing', 'load_bearing',
     'Matched by verdict_card''s tech-mismatch rules.'),

    ('batch_etl', 'descriptive',
     'Describes the processing style; data_processing is what rules match.'),
    ('cache', 'descriptive',
     'Describes what the store is for; datastore is what rules match.'),
    ('cdn', 'descriptive',
     'Describes the edge service''s function; edge_entry is what rules match.'),
    ('container_runtime', 'descriptive',
     'Describes how the compute runs; compute is what rules match.'),
    ('data_warehouse', 'descriptive',
     'Describes the sink''s shape; analytics_sink is what rules match.'),
    ('db_auth_proxy', 'descriptive',
     'Names the pattern CONN-K8S-TO-RELATIONAL-DB recommends in its message; no '
     'rule matches the role itself.'),
    ('ddos_protection', 'descriptive',
     'Describes the policy''s function; where it may attach is decided by '
     'network_placement = policy.'),
    ('document_db', 'descriptive',
     'Describes the database model; datastore is what rules match.'),
    ('function_runtime', 'descriptive',
     'Describes how the compute runs; compute is what rules match.'),
    ('global_scale_db', 'descriptive',
     'Describes the database''s reach; region_scope is the field rules read.'),
    ('load_balancer_l4', 'descriptive',
     'Describes the layer it balances at. Only load_balancer_l7 is matched, '
     'because a WAF cannot attach to L4.'),
    ('network_fabric', 'descriptive',
     'Describes the node. Rules match network_fabric as a network_placement, '
     'not as a role.'),
    ('object_store', 'descriptive',
     'Describes the storage model; datastore is what rules match.'),
    ('paas_app_host', 'descriptive',
     'Describes the hosting model; compute is what rules match.'),
    ('path_routing', 'descriptive',
     'Describes an L7 feature; load_balancer_l7 is what rules match.'),
    ('policy', 'descriptive',
     'Describes the node. Rules match policy as a network_placement, not as a '
     'role.'),
    ('private_endpoint', 'descriptive',
     'Describes the connector''s mechanism; connector is what rules match.'),
    ('vm', 'descriptive',
     'Describes the compute unit; compute is what rules match.'),
    ('waf', 'descriptive',
     'Carried by the azure-waf alias as a feature; no rule matches the role.'),
    ('waf_host', 'descriptive',
     'Describes what the edge service can carry; edge_entry is what rules '
     'match.'),
    ('wide_column_db', 'descriptive',
     'Describes the database model; datastore is what rules match.')
ON CONFLICT (role) DO NOTHING;

-- The file's own header, carried the same way every other exported file
-- carries its. Seeded here for the same reason the rows above are: the export
-- has to have something to write before there is a file to seed from.
INSERT INTO kg_setting (key, value, note) VALUES (
    'doc:role-catalog',
    NULL,
    'Role vocabulary, and which roles the engine actually reads.'                     || E'\n' ||
    ''                                                                                || E'\n' ||
    '`kind` is the whole point of this file:'                                         || E'\n' ||
    ''                                                                                || E'\n' ||
    'load_bearing — something matches this role: a connectivity rule''s `when`'       || E'\n' ||
    'clause, a `needs_role`, one of validate.py''s L2-L8 checks, verdict_card.py''s'  || E'\n' ||
    'tech-mismatch rules, or `regenerate_roles`. Getting one wrong, or leaving'       || E'\n' ||
    'one off, changes verdicts.'                                                      || E'\n' ||
    'descriptive — carried for the reader. True, useful in a service entry, and'      || E'\n' ||
    'read by nothing. `wide_column_db` on Bigtable is the shape of it.'               || E'\n' ||
    ''                                                                                || E'\n' ||
    'The split is measured rather than declared: it is what the rules and the'        || E'\n' ||
    'engine reference today. A rule that starts matching a descriptive role'          || E'\n' ||
    'promotes it here, and the curator insists on it from then on. Rules lead,'       || E'\n' ||
    'the catalog follows — this file does not license a role, it records that'        || E'\n' ||
    'something reads one.'                                                            || E'\n' ||
    ''                                                                                || E'\n' ||
    'The set is closed at the storage layer: `service_role.role` is a foreign key'    || E'\n' ||
    'onto this table. A misspelled role used to insert cleanly, match nothing, and'   || E'\n' ||
    'leave a node reading as fully specified with the integrity check clean through'  || E'\n' ||
    'it. That is D6''s failure shape, and the fix is D26''s: put the refusal where'   || E'\n' ||
    'no caller can route around it.'
)
ON CONFLICT (key) DO NOTHING;

-- The floor. A role outside the catalog is now refused by the database rather
-- than accepted and silently never matched.
ALTER TABLE service_role
    ADD CONSTRAINT service_role_role_fkey
    FOREIGN KEY (role) REFERENCES role_catalog(role);

CREATE INDEX IF NOT EXISTS role_catalog_kind_idx ON role_catalog (kind);

COMMIT;
