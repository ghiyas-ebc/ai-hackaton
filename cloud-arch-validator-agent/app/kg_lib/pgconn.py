"""Postgres connection handling for the knowledge graph.

One place decides what "the database" means, so the loader, the seed script and
the write tools cannot drift onto different databases.

Configuration is a single DSN in `CAV_PG_DSN`. That is deliberate: it is the
one setting that has to change when this moves from the local docker-compose
Postgres to Cloud SQL, and a DSN is all Cloud SQL needs when reached through
the proxy. No cloud client library appears anywhere in this path — the agent
still starts, and still runs, without a GCP account.
"""

import os

DEFAULT_DSN = "postgresql://cav:cav@localhost:5432/cav"

_POOL = None


def dsn():
    return os.environ.get("CAV_PG_DSN", DEFAULT_DSN)


def _psycopg():
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RuntimeError(
            "psycopg is required for the Postgres backend. Install the "
            "project dependencies (`uv sync`) or set CAV_KG_BACKEND=local."
        ) from exc
    return psycopg


def pool():
    """Shared connection pool.

    The KG is read once per process at import and then only on write, so the
    pool stays small. It exists mainly so a serving process does not open a new
    TCP connection per tool call under a burst of requests.
    """
    global _POOL
    if _POOL is None:
        from psycopg_pool import ConnectionPool

        _POOL = ConnectionPool(
            dsn(),
            min_size=1,
            max_size=int(os.environ.get("CAV_PG_MAX_CONNECTIONS", "4")),
            open=True,
            kwargs={"options": "-c search_path=kg,public"},
        )
    return _POOL


def connect():
    """A single connection, for scripts and tests that do not want the pool."""
    psycopg = _psycopg()
    return psycopg.connect(dsn(), options="-c search_path=kg,public")


def reachable():
    """True when the configured database answers. Used to skip DB-bound tests
    rather than fail them on a machine with no Postgres running."""
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def close():
    global _POOL
    if _POOL is not None:
        _POOL.close()
        _POOL = None
