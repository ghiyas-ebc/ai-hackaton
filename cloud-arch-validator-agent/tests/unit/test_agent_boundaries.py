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


def test_there_is_exactly_one_renderer():
    """The draw.io emitter is gone, and nothing may quietly reintroduce one.

    It was exposed to no agent for the whole of its life — its icon-embedding
    path was known broken and never diagnosed — while costing an icon mapping
    in the schema, one of the generated YAML files, and two sections of the
    graph's own health gate. A second renderer that nobody can reach is not a
    feature in reserve; it is a surface that rots.
    """
    renderers = [t for t in tools.ALL_TOOLS if "render" in t.__name__]
    assert renderers == [tools.render_ascii_diagram]
    assert not hasattr(tools, "render_drawio_diagram")


def test_past_project_tools_are_explorer_only():
    """Past-project browsing is presales catalog material — not part of
    validating an architecture, and not a write surface.
    """
    past_project_tools = {tools.search_past_projects, tools.get_past_project}
    assert past_project_tools <= _tools_of(explorer_agent)
    assert not past_project_tools & _tools_of(validator_agent)
    assert not past_project_tools & _tools_of(curator_agent)


def test_all_tools_is_the_union_of_what_agents_actually_hold():
    """Otherwise the exposure surface the other tests assert on is fiction."""
    union = (
        _tools_of(validator_agent) | _tools_of(explorer_agent) | _tools_of(curator_agent)
    )
    assert union == set(tools.ALL_TOOLS)
