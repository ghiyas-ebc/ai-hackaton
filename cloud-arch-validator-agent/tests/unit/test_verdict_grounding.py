"""Cases here mirror real baseline traces; see verdict_grounding.py for why."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "eval"))

import verdict_grounding as vg  # noqa: E402


def _trace(text, tools=()):
    events = [
        {"content": {"parts": [{"function_response": {"name": name, "response": {}}}]}}
        for name in tools
    ]
    events.append({"content": {"parts": [{"text": text}]}})
    return {"agent_data": {"turns": [{"turn_index": 0, "events": events}]}}


def test_verdict_backed_by_tool_passes():
    result = vg.evaluate(
        _trace("## Kartu Keputusan\nKesulitan: Tinggi", ["generate_verdict_card"])
    )
    assert result["score"] == 1.0


def test_verdict_without_tool_call_fails():
    result = vg.evaluate(_trace("Berikut Kartu Keputusan dari mesin aturan.\nKesulitan: Sedang"))
    assert result["score"] == 0.0
    assert "no generate_verdict_card" in result["explanation"]


def test_no_verdict_claim_is_not_penalised():
    # E07: a conceptual question that correctly uses no tool at all.
    result = vg.evaluate(_trace("Event Grid dan Service Bus berbeda pola komunikasi."))
    assert result["score"] == 1.0


def test_invented_rule_id_fails():
    result = vg.evaluate(_trace("Aturan L3-D-01 melarang ini.", ["generate_verdict_card"]))
    assert result["score"] == 0.0
    assert "L3-D-01" in result["explanation"]


def test_shortened_real_rule_id_passes():
    # The agent routinely cites SEC-003 for SEC-003-COMPUTE-EXPOSED.
    result = vg.evaluate(_trace("Temuan SEC-003 terdeteksi.", ["generate_verdict_card"]))
    assert result["score"] == 1.0


def test_tool_call_emitted_as_text_fails():
    result = vg.evaluate(_trace("```tool_code\ndefault_api:generate_verdict_card(edges: a>b)\n```"))
    assert result["score"] == 0.0
    assert "instead of invoking it" in result["explanation"]
