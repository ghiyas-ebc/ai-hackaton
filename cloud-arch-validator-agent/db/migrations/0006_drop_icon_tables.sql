-- Drop the icon mapping. The renderer that needed it is gone.
--
-- `icon_category` and `service_icon` existed for one consumer: the draw.io
-- emitter, which resolved a service to an official Google or Microsoft SVG on
-- disk and embedded it in the XML. That emitter is deleted. It was never
-- reachable from any agent — `tests/unit/test_agent_boundaries.py` asserted
-- that on purpose, because its `--embed-icons` path was known broken and never
-- diagnosed — and the one renderer that ships now draws ASCII, where an icon
-- has nowhere to go.
--
-- What the tables cost while they stayed: 55 rows nothing read, a `doc:icons`
-- header, one of the seven generated YAML files, two sections of the health
-- check the graph's own gate ran on every change, a ten-case regression
-- fixture, and an insert on the curator's write path so that adding a service
-- did not make the next health check report the graph unclean over a missing
-- icon row. That is a lot of machinery held up by a consumer that had already
-- been switched off.
--
-- This is recoverable if a graphical emitter ever comes back: the mapping was
-- derived from the providers' own published icon sets, and 0001 plus the last
-- exported `icons.yaml` are both in git history. What is not worth carrying is
-- a schema that no code reads and a gate section that can only ever pass.

BEGIN;
SET search_path TO kg, public;

DROP TABLE IF EXISTS service_icon;
DROP TABLE IF EXISTS icon_category;

DELETE FROM kg_setting WHERE key = 'doc:icons';

COMMIT;
