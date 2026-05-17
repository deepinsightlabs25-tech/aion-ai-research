"""Role Nodes — build specialized sub-agent runners."""

from __future__ import annotations

from ..sub_agents import build_role_runners


def create_role_nodes(llm):
    """Return one node-callable per specialized sub-agent role.

    Sub-agents are built **once** here (at graph-build time) via
    :func:`sub_agents.build_role_runners`. The returned runners are
    lightweight callables that simply invoke the pre-built agents.
    """
    return build_role_runners(llm)
