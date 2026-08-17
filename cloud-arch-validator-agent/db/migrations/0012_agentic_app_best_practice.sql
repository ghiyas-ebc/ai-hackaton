-- Captures a tag + reference row that were already live in this database's
-- project_catalog schema but untracked by any migration — found while
-- verifying 0011's seed via list_best_practice_tags, which returned five
-- tags instead of the four 0011 adds. Whoever added 'agentic_app' did it
-- directly against a running container, so it would not survive a fresh
-- db/migrate.py + seed anywhere else. This migration is that data, moved
-- into the tracked history it should have been in from the start.
--
-- reference_url is genuinely NULL here, not an omission: this is Google's
-- own recommended pattern rather than a citable public reference-architecture
-- page, which the schema's own comment on best_practice_reference.provider
-- already anticipates ("NULL = cross-provider/generic guidance").

BEGIN;
SET search_path TO project_catalog, public;

INSERT INTO best_practice_tag (tag, note) VALUES
    ('agentic_app', 'Conversational or autonomous AI agents needing persistent memory or state across sessions or users.')
ON CONFLICT (tag) DO NOTHING;

INSERT INTO best_practice_reference (id, tag, provider, title, note, reference_url, ord) VALUES
    ('gcp-agentic-app-reference-architecture', 'agentic_app', 'gcp',
     'GCP reference pattern: Agent Runtime + Memory Bank',
     'GCP''s own recommended pattern for a production agentic application: Agent Runtime for '
     'execution, Memory Bank for persistent cross-session/user memory, both integrable with '
     'Gemini Enterprise for the user-facing surface. This is principal guidance, not something '
     'the company has delivered — cite it only when there is no internal Proven or Partial Proven '
     'evidence, and say plainly that it is a vendor pattern, not our own track record.',
     NULL, 0)
ON CONFLICT (id) DO NOTHING;

COMMIT;
