"""Postgres is the source of truth; the YAML is its export. Keep them equal.

Before this existed, the two could disagree and nothing said so. The YAML was
simultaneously the seed input, the offline fallback, and the list of valid rule
ids the verdict-grounding metric checks against — three jobs, no owner, and a
silent failure mode in each: seed a fresh database from a stale file and get an
old graph, run the `local` backend and get different verdicts than production,
add a rule in SQL and watch the metric score its id as fabricated.

The direction is now fixed. The database is written; the YAML is generated from
it. These tests hold that:

  round trip   exporting and re-importing produces the same graph, so the
               export is not quietly lossy
  drift        the committed files match what the database would produce

The round trip runs without Postgres — it chains the two pure halves. The drift
check needs a database and skips without one, because it is asking a question
about a specific database's contents rather than about the code.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_AGENT_ROOT = Path(__file__).resolve().parents[2]
_KG_LIB = _AGENT_ROOT / "app" / "kg_lib"
if str(_KG_LIB) not in sys.path:
    sys.path.insert(0, str(_KG_LIB))

import kg as kg_module  # noqa: E402
import kg_pg  # noqa: E402

KG_DIR = _AGENT_ROOT / "app" / "references" / "kg"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, _AGENT_ROOT / "db" / filename
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed = _load("seed_from_yaml", "seed_from_yaml.py")
export = _load("export_to_yaml", "export_to_yaml.py")

ATTRIBUTES = [
    "services", "conn_rules", "conn_fallback", "arch_rules", "arch_layers",
    "aliases", "overrides", "alternatives", "regenerate_roles",
    "equivalences", "icons",
]


# ------------------------------------------------------- round trip, no DB --


@pytest.fixture(scope="module")
def committed_rows():
    return seed.build_rows(KG_DIR)


@pytest.fixture(scope="module")
def reexported_rows(committed_rows, tmp_path_factory):
    """rows -> YAML -> rows, entirely in memory and a temp dir."""
    out = tmp_path_factory.mktemp("kg-export")
    for name, text in export.build_documents(committed_rows).items():
        (out / name).write_text(text, encoding="utf-8")
    return seed.build_rows(out)


def _normalise(rows):
    """Compare row sets without asserting a row order the export does not fix.

    Table order is only load-bearing where a column records it — `service.ord`
    and `connectivity_rule.seq` — and those are compared as data here and as
    sequence in the graph assertions below.
    """
    out = []
    for row in rows:
        row = {k: v for k, v in row.items() if k not in ("rationale", "note")}
        out.append(json.dumps(row, sort_keys=True, default=str))
    return sorted(out)


@pytest.mark.parametrize("table", seed.TABLE_ORDER)
def test_export_reimports_to_the_same_rows(committed_rows, reexported_rows, table):
    assert _normalise(reexported_rows[table]) == _normalise(committed_rows[table])


@pytest.mark.parametrize("attr", ATTRIBUTES)
def test_export_reimports_to_the_same_graph(committed_rows, reexported_rows, attr):
    before = kg_pg.kg_from_rows(committed_rows)
    after = kg_pg.kg_from_rows(reexported_rows)
    assert getattr(after, attr) == getattr(before, attr)


def test_export_preserves_the_two_orderings_that_decide_verdicts(
    committed_rows, reexported_rows
):
    """`by_role(...)[0]` reads service order; Layer 1 is first-match-wins.

    Both survive a byte-level reshuffle of the YAML without complaint, and both
    change verdicts when they move, so neither can rest on the row comparison
    above.
    """
    before = kg_pg.kg_from_rows(committed_rows)
    after = kg_pg.kg_from_rows(reexported_rows)
    assert list(after.services) == list(before.services)
    assert [r["id"] for r in after.conn_rules] == [r["id"] for r in before.conn_rules]


def test_generated_files_say_they_are_generated():
    """A file that does not announce itself gets hand-edited exactly once."""
    for name in export.build_documents(seed.build_rows(KG_DIR)):
        text = (KG_DIR / name).read_text(encoding="utf-8")
        assert text.startswith("# GENERATED FILE"), f"{name} lost its banner"


def test_the_authored_reasoning_is_still_in_the_files():
    """The comments are the documentation; an export that drops them is lossy.

    Not covered by the row comparison, which deliberately ignores `rationale`
    because comments do not survive a YAML parse. They have to be checked as
    text.
    """
    services = (KG_DIR / "services.yaml").read_text(encoding="utf-8")
    assert "serverless_offvpc" in services, "field definitions lost"
    assert "WAF is a feature" in services, "per-entry notes lost"

    conn = (KG_DIR / "connectivity-rules.yaml").read_text(encoding="utf-8")
    assert "FIRST MATCH WINS" in conn.upper(), "evaluation-order warning lost"


# ------------------------------------------------------------ drift, needs DB --


def _database_available():
    try:
        import pgconn

        return pgconn.reachable()
    except Exception:
        return False


needs_db = pytest.mark.skipif(
    not _database_available(),
    reason="no Postgres at CAV_PG_DSN; drift is a question about a database",
)


@needs_db
def test_committed_yaml_matches_the_database():
    """The whole point. Fails when someone changes the graph and skips the export.

    The fix is never to edit the YAML — it is to run
    `python3 db/export_to_yaml.py` and commit what it writes.
    """
    generated = export.build_documents(kg_pg.fetch_rows())
    stale = [
        name
        for name, text in generated.items()
        if (KG_DIR / name).read_text(encoding="utf-8") != text
    ]
    assert not stale, (
        f"{len(stale)} file(s) out of date with the database: {stale}. "
        "Run `python3 db/export_to_yaml.py` and commit the result."
    )


@needs_db
def test_the_database_and_the_local_backend_agree():
    """Both backends must answer the same, or the fallback is a trap."""
    from_db = kg_module.load(backend="postgres")
    from_yaml = kg_module.load(backend="local")
    for attr in ATTRIBUTES:
        assert getattr(from_yaml, attr) == getattr(from_db, attr), attr
