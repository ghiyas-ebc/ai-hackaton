"""Reads over `project_catalog` — the past-projects schema, not the KG.

Unlike `kg_pg.py`, this does not bulk-load into an in-memory object at import
time: `project_catalog` isn't part of the rule engine's `KnowledgeGraph`, has
no hot path reading it, and changes rarely enough that a live query per call
is simpler than a cache with no invalidation story. Each function takes an
open connection rather than opening its own, same as `kg_write.py`'s write
functions — the caller (`app/tools.py`) owns the connection's lifetime.

Every statement re-sets `search_path` to `project_catalog, public` on its own
cursor, the same belt-and-suspenders `kg_pg.fetch_rows`/`kg_write.add_service`
do for `kg, public` — `pgconn.connect()` hardcodes `search_path=kg,public` at
the connection level, so without this every unqualified table name here would
resolve into the wrong schema (or nowhere).
"""

from psycopg.rows import dict_row

_LIST_SQL = """
    SELECT id, name, description, use_case, started_at, ended_at,
           client_name, providers, tags, service_count, member_count
    FROM project_summary p
    WHERE (%(q)s = '' OR p.name ILIKE %(q_like)s
                      OR p.description ILIKE %(q_like)s
                      OR p.use_case ILIKE %(q_like)s)
      AND (%(tag)s = '' OR %(tag)s = ANY(p.tags))
      AND (%(provider)s = '' OR %(provider)s = ANY(p.providers))
      AND (%(service_id)s = '' OR EXISTS (
              SELECT 1 FROM project_service ps
              WHERE ps.project_id = p.id AND ps.service_id = %(service_id)s
          ))
    ORDER BY p.started_at DESC, p.id
"""

_PROJECT_SQL = "SELECT * FROM project WHERE id = %(id)s"

_MEMBERS_SQL = """
    SELECT name, role_on_project, ord FROM project_member
    WHERE project_id = %(id)s ORDER BY ord
"""

_SERVICES_SQL = """
    SELECT service_id, ord, note FROM project_service
    WHERE project_id = %(id)s ORDER BY ord
"""

_CONNECTIONS_SQL = """
    SELECT source_service_id, target_service_id, note, ord
    FROM project_connection
    WHERE project_id = %(id)s ORDER BY ord
"""


def list_projects(conn, *, q: str = "", tag: str = "", provider: str = "",
                  service_id: str = "") -> list[dict]:
    """`project_summary` rows matching every supplied filter. Empty matches all."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET search_path TO project_catalog, public")
        cur.execute(_LIST_SQL, {
            "q": q, "q_like": f"%{q}%",
            "tag": tag, "provider": provider, "service_id": service_id,
        })
        return cur.fetchall()


def get_project(conn, project_id: str) -> dict | None:
    """One project's full row plus members/services/connections, or `None`."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SET search_path TO project_catalog, public")
        cur.execute(_PROJECT_SQL, {"id": project_id})
        project = cur.fetchone()
        if project is None:
            return None
        cur.execute(_MEMBERS_SQL, {"id": project_id})
        project["members"] = cur.fetchall()
        cur.execute(_SERVICES_SQL, {"id": project_id})
        project["services"] = cur.fetchall()
        cur.execute(_CONNECTIONS_SQL, {"id": project_id})
        project["connections"] = cur.fetchall()
    return project
