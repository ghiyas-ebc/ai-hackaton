"""The Gap Report is the product's own feedback, so it has to survive.

Every UNCOVERED verdict and unknown service logs a record. That list is the
evidence for what the graph should cover next, and it is the one dataset here
that cannot be regenerated from anything — it is what real users actually asked.
It used to append to a JSONL file inside the container, which made it the least
durable data in the system.

Two things are checked. That records reach Postgres, and that a gap can never
fail a verdict: the log exists to be read later, and a user waiting on an answer
should not get an error because the log's storage is unavailable.
"""

import sys
from pathlib import Path

import pytest

_AGENT_ROOT = Path(__file__).resolve().parents[2]
if str(_AGENT_ROOT / "app" / "kg_lib") not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT / "app" / "kg_lib"))

from app import tools  # noqa: E402

kg_write = tools.kg_write_module


def test_missing_services_are_identified_by_the_caller(monkeypatch):
    """Which service is missing is decided against the loaded graph.

    An earlier version inferred it in SQL by matching the element text against
    known ids, which on "cloud-run -> cloud-composer" found `cloud-run` — the
    half that exists — and reported the gap as being about a known service.
    Exactly backwards, and it is the field the triage depends on.
    """
    captured = []
    monkeypatch.setattr(
        kg_write, "record_gaps", lambda conn, records: captured.extend(records)
    )
    monkeypatch.setattr(tools.pgconn, "connect", lambda: _NullConn())

    tools.generate_verdict_card("cloud-run>totally-made-up-service")

    assert captured, "no gap record was produced"
    missing = captured[0]["missing_services"]
    assert missing == ["totally-made-up-service"]
    assert "cloud-run" not in missing, "flagged the service that does exist"


def test_a_pair_of_known_services_reports_no_missing_node():
    """An uncovered pair between two known services is a missing rule.

    Empty `missing_services` is what separates 'write a rule' from 'add a node',
    so it has to be empty rather than merely falsy-ish.
    """
    records = [{"unresolved_element": "cloud-run -> cloud-sql"}]
    for r in records:
        named = [t.strip() for t in r["unresolved_element"].replace("->", " ").split()]
        r["missing"] = [t for t in named if tools._KG.resolve(t)[0] is None]
    assert records[0]["missing"] == []


def test_a_failing_database_falls_back_instead_of_failing_the_verdict(monkeypatch):
    """A gap is logged while answering a user. Storage being down is not their
    problem, and it must not turn a good verdict into an error."""
    def boom():
        raise RuntimeError("database is down")

    monkeypatch.setattr(tools.pgconn, "connect", boom)

    fell_back = []
    monkeypatch.setattr(
        tools.verdict_card_module,
        "_append_gap_records",
        lambda records: fell_back.extend(records),
    )

    card = tools.generate_verdict_card("cloud-run>totally-made-up-service")

    assert card["difficulty"], "the verdict still came back"
    assert fell_back, "the record was dropped instead of falling back to the file"


# ------------------------------------------------------------ needs database --


def _database_available():
    try:
        import pgconn

        return pgconn.reachable()
    except Exception:
        return False


needs_db = pytest.mark.skipif(
    not _database_available(), reason="no Postgres at CAV_PG_DSN"
)


@needs_db
def test_records_land_in_postgres_and_are_not_deduplicated():
    """The same gap seen twice is a stronger signal than one seen once, so
    repeats are kept rather than collapsed on write."""
    import pgconn

    element = "cloud-run -> totally-made-up-service"
    with pgconn.connect() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM kg.gap_record WHERE unresolved_element = %s", (element,)
        )
        conn.commit()

    tools.generate_verdict_card("cloud-run>totally-made-up-service")
    tools.generate_verdict_card("cloud-run>totally-made-up-service")

    with pgconn.connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT times_seen, missing_services FROM kg.gap_summary "
            "WHERE unresolved_element = %s",
            (element,),
        )
        row = cur.fetchone()
        cur.execute(
            "DELETE FROM kg.gap_record WHERE unresolved_element = %s", (element,)
        )
        conn.commit()

    assert row is not None, "nothing reached the database"
    times_seen, missing = row
    assert times_seen == 2
    assert missing == ["totally-made-up-service"]


class _NullConn:
    """Stands in for a connection in tests that replace record_gaps entirely."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        pass
