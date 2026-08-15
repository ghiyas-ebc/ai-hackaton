"""The three specialists the coordinator delegates to.

Split by the job being done, not by provider and not by validation layer:
validating an architecture, exploring the graph, and changing the graph are
three different tasks with three different risk profiles. Two are read-only and
safe to run all day; the third writes, and needs a human in the loop for fields
no lookup can answer.

Splitting by layer instead was considered and dropped: L1 through L8 is a
decision tree inside `validate.py`, and giving a layer its own agent would put a
model between rungs of it. The layers are evaluated by code, reported as one
result, and explained by one agent.
"""

from .curator import curator_agent
from .explorer import explorer_agent
from .validator import validator_agent

SUB_AGENTS = [validator_agent, explorer_agent, curator_agent]

__all__ = ["SUB_AGENTS", "curator_agent", "explorer_agent", "validator_agent"]
