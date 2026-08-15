"""The sub-agent split has to be enforced by structure, not by instruction.

Every rule in this file could also be written as a sentence in a prompt, and
each of those sentences is in fact there. The difference is that a prompt can be
argued with — under a plausible-sounding request, a model that holds a writing
tool can be talked into writing. A model that was never handed the tool cannot.

So these tests assert the boundaries that hold regardless of what any agent is
told: who can write, who decides verdicts, and what is exposed at all.
"""

from app import tools
from app.agent import root_agent
from app.sub_agents import curator_agent, explorer_agent, validator_agent

WRITE_TOOLS = {tools.add_service_to_kg, tools.mark_service_verified}
VERDICT_TOOLS = {
    tools.validate_architecture,
    tools.generate_verdict_card,
    tools.translate_architecture,
}


def _tools_of(agent):
    return set(agent.tools)


def test_the_coordinator_holds_no_tools():
    """It routes. A coordinator that could answer would stop transferring."""
    assert root_agent.tools == []
    assert {a.name for a in root_agent.sub_agents} == {
        "validator_agent",
        "explorer_agent",
        "curator_agent",
    }


def test_read_only_agents_cannot_write():
    """The two agents a rep talks to during a client call hold no writer.

    This is the one that matters most in practice: a validation conversation
    should never be able to end with a row added to the graph, whatever the
    conversation drifted into.
    """
    assert not _tools_of(validator_agent) & WRITE_TOOLS
    assert not _tools_of(explorer_agent) & WRITE_TOOLS


def test_the_curator_cannot_issue_verdicts():
    """Separated so a gap cannot be closed by writing to the graph.

    An agent that could both validate and add would have an obvious way out of
    an inconvenient UNKNOWN_SERVICE: add the service, then validate. Adding a
    service is a decision requiring an engineer, not a step in getting an
    answer.
    """
    assert not _tools_of(curator_agent) & VERDICT_TOOLS


def test_every_agent_can_look_a_service_up():
    """Checking an id is cheap and each agent needs it to avoid guessing one."""
    for agent in (validator_agent, explorer_agent, curator_agent):
        assert tools.lookup_service in _tools_of(agent)


def test_the_broken_drawio_path_is_exposed_to_nobody():
    """`--embed-icons` is a known-broken code path, and a broken diagram in
    front of a client is worse than no diagram."""
    assert tools.render_drawio_diagram not in tools.ALL_TOOLS
    for agent in (validator_agent, explorer_agent, curator_agent):
        assert tools.render_drawio_diagram not in _tools_of(agent)


def test_all_tools_is_the_union_of_what_agents_actually_hold():
    """Otherwise the exposure surface the other tests assert on is fiction."""
    union = (
        _tools_of(validator_agent) | _tools_of(explorer_agent) | _tools_of(curator_agent)
    )
    assert union == set(tools.ALL_TOOLS)
