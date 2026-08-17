-- First data for best_practice_tag / best_practice_reference (schema created
-- empty by 0008). Four popular, currently-live Google Cloud reference
-- architectures, picked because they sit closest to what this company
-- actually builds: RAG/vector-search and serverless-web-app both match
-- delivered work in project_catalog (Sodagr, Identiqo, Data Insight AI);
-- event-driven and multi-agent are adjacent patterns reps get asked about
-- without a delivered project to cite yet — exactly the gap this table
-- exists to cover per 0008's header comment.
--
-- Every title/summary/URL below was pulled from the live page, not written
-- from memory — this table's whole job is to be a citation a rep can put in
-- front of a client's architect, so a stale or guessed URL would defeat it.
-- Left out a fifth "microservices" candidate: the old Architecture Center
-- URL for it now 301-redirects to a generic "what is microservices"
-- marketing page, not a reference architecture, so it didn't clear the same
-- bar as the four below.
--
-- Seeded here rather than by a script because, like role_catalog (0004),
-- this is hand-curated reference data with no YAML authoring file of its
-- own — see 0008's header for why it doesn't inherit D27's generated-YAML
-- obligations.

BEGIN;
SET search_path TO project_catalog, public;

INSERT INTO best_practice_tag (tag, note) VALUES
    ('rag_genai_app', 'Retrieval-augmented generation: grounding an LLM''s answers in ingested documents via a vector index.'),
    ('serverless_web_app', 'A public web app on serverless compute behind a load balancer, reaching its datastore over a private path.'),
    ('event_driven_pubsub', 'Services that communicate asynchronously through Pub/Sub instead of direct synchronous calls.'),
    ('multi_agent_ai_system', 'Multiple specialized AI agents coordinating on a task, as opposed to one monolithic agent or prompt.')
ON CONFLICT (tag) DO NOTHING;

INSERT INTO best_practice_reference (id, tag, provider, title, note, reference_url, ord) VALUES
    ('ref-rag-vertex-ai-vector-search', 'rag_genai_app', 'gcp',
     'RAG infrastructure for generative AI using Agent Platform and Vector Search',
     'Uses Vector Search, Cloud Run, Cloud Storage, Pub/Sub and Agent Platform to ground LLM '
     'responses in ingested data — the same shape as the RAG/face-embedding pattern this company '
     'has delivered on Sodagr, Identiqo and Data Insight AI.',
     'https://docs.cloud.google.com/architecture/gen-ai-rag-vertex-ai-vector-search', 0),
    ('ref-serverless-cloud-run-blueprint', 'serverless_web_app', 'gcp',
     'Deploy a secured serverless architecture using Cloud Run',
     'Cloud Run behind a Shared VPC, with an external Application Load Balancer, Cloud Armor, '
     'and a Serverless VPC Access connector reaching private backends — the same connector-fronted '
     'pattern this company''s own Cloud Run + Cloud SQL projects follow.',
     'https://docs.cloud.google.com/architecture/blueprints/serverless-blueprint', 0),
    ('ref-event-driven-pubsub', 'event_driven_pubsub', 'gcp',
     'Event-driven architecture with Pub/Sub',
     'Compares queue-driven and event-streaming designs, and why publishing an event a subscriber '
     'reacts to scales and decouples better than a direct synchronous call.',
     'https://docs.cloud.google.com/solutions/event-driven-architecture-pubsub', 0),
    ('ref-multiagent-ai-system', 'multi_agent_ai_system', 'gcp',
     'Multi-agent AI system in Google Cloud',
     'Coordinates multiple specialized agents on Cloud Run / GKE via the Agent2Agent (A2A) protocol '
     'and Model Context Protocol (MCP) — the same coordinator-plus-specialists split this repo''s '
     'own agent (D25) uses.',
     'https://docs.cloud.google.com/architecture/multiagent-ai-system', 0)
ON CONFLICT (id) DO NOTHING;

COMMIT;
