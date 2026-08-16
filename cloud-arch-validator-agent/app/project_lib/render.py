"""Draw a past project's recorded topology.

Thin wrapper over `app/renderer.py::render_flowchart` — the one retroflow
call site in the repo. Display names are the caller's job (see
`app/tools.py`): this module only shapes `projects_pg.get_project()`'s
`connections` rows into the source/target pairs the renderer wants.
"""

from app.renderer import render_flowchart


def build_diagram(connections: list[dict], labels: dict[str, str], *,
                  ascii_only: bool = False) -> str:
    """`connections`: `get_project()`'s `connections` list.

    `labels`: service id -> display name, resolved by the caller from the
    knowledge graph rather than looked up here — keeps this module's only
    dependency on `kg` being the ids it was handed, not a second lookup.
    """
    pairs = [
        {"source": c["source_service_id"], "target": c["target_service_id"]}
        for c in connections
    ]
    return render_flowchart(pairs, labels, ascii_only=ascii_only)
