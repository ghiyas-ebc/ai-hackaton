"""Draw.io XML emitter for the cloud architecture validator.

Consumes the output of validate.py (or the revalidation section of
translate.py) and writes an uncompressed .drawio file. Icons are embedded as
base64 SVG data URIs only when the user passes --embed-icons; no official icon
files are copied into the repository.

This module uses only the Python standard library so the skill keeps its
"no runtime dependency beyond PyYAML" guarantee.
"""

import argparse
import base64
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import kg as kg_module

# ---------------------------------------------------------------- layout ---
NODE_W, NODE_H = 48, 48
GENERIC_W, GENERIC_H = 96, 48
CONNECTOR_W, CONNECTOR_H = 24, 24
H_SPACING = 140
V_SPACING = 90
CONTAINER_PAD = 50
BADGE_SIZE = 24
NOTE_W, NOTE_H = 220, 52
MARGIN = 40

COLORS = {
    "gcp": {"fill": "#E3F2FD", "stroke": "#1565C0"},
    "azure": {"fill": "#E8EAF6", "stroke": "#283593"},
    "unknown": {"fill": "#F5F5F5", "stroke": "#616161"},
}

SEVERITY_COLOR = {
    "ERROR": {"fill": "#FFCDD2", "stroke": "#C62828"},
    "WARNING": {"fill": "#FFE082", "stroke": "#F57F17"},
    "INFO": {"fill": "#B3E5FC", "stroke": "#0277BD"},
}


def _safe_id(s):
    return s.replace("-", "_").replace(".", "_")


def _geometry(x, y, width, height, relative=False):
    g = ET.Element(
        "mxGeometry",
        {
            "x": str(x),
            "y": str(y),
            "width": str(width),
            "height": str(height),
            "as": "geometry",
        },
    )
    if relative:
        g.set("relative", "1")
    return g


def _edge_geometry(points=None):
    g = ET.Element("mxGeometry", {"relative": "1", "as": "geometry"})
    if points:
        arr = ET.SubElement(g, "Array", {"as": "points"})
        for x, y in points:
            ET.SubElement(arr, "mxPoint", {"x": str(x), "y": str(y)})
    return g


def _cell(parent_el, cid, parent_id, value=None, style=None, vertex=False,
          edge=False, source=None, target=None, geometry=None):
    attrs = {"id": cid}
    if parent_id is not None:
        attrs["parent"] = parent_id
    cell = ET.SubElement(parent_el, "mxCell", attrs)
    if value is not None:
        cell.set("value", value)
    if style:
        cell.set("style", style)
    if vertex:
        cell.set("vertex", "1")
    if edge:
        cell.set("edge", "1")
    if source:
        cell.set("source", source)
    if target:
        cell.set("target", target)
    if geometry is not None:
        cell.append(geometry)
    return cell


def _embed_svg(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _image_style(icon_path):
    b64 = _embed_svg(icon_path)
    return (
        f"shape=image;image=data:image/svg+xml;base64,{b64};"
        "html=1;verticalLabelPosition=bottom;verticalAlign=top;"
        "align=center;"
    )


def _generic_style(provider, rounded=True):
    c = COLORS.get(provider, COLORS["unknown"])
    shape = "rounded=1;" if rounded else ""
    return (
        f"{shape}whiteSpace=wrap;html=1;fillColor={c['fill']};"
        f"strokeColor={c['stroke']};align=center;verticalAlign=middle;"
        "fontSize=12;"
    )


def _edge_style(verdict):
    base = (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;"
        "jettySize=auto;html=1;"
    )
    if verdict in ("UNCOVERED", "UNKNOWN_SERVICE"):
        return base + "strokeColor=#9E9E9E;dashed=1;"
    if verdict == "NEEDS_COMPONENT":
        return base + "strokeColor=#757575;"
    return base + "strokeColor=#6C6C6C;"


def _label_style(severity):
    base = (
        "edgeLabel;html=1;align=center;verticalAlign=middle;"
        "resizable=0;points=[];fontSize=10;"
    )
    c = SEVERITY_COLOR.get(severity, SEVERITY_COLOR["INFO"])
    return base + f"fillColor={c['fill']};strokeColor={c['stroke']};"


def _badge_style(severity):
    c = SEVERITY_COLOR.get(severity, SEVERITY_COLOR["INFO"])
    return (
        f"rounded=1;whiteSpace=wrap;html=1;fillColor={c['fill']};"
        f"strokeColor={c['stroke']};align=center;verticalAlign=middle;"
        "fontSize=9;"
    )


def _note_style(severity):
    c = SEVERITY_COLOR.get(severity, SEVERITY_COLOR["INFO"])
    return (
        f"shape=note;whiteSpace=wrap;html=1;fillColor={c['fill']};"
        f"strokeColor={c['stroke']};align=left;verticalAlign=top;"
        "fontSize=11;spacingLeft=6;spacingTop=4;"
    )


def _resolve_nodes(kg, edges, include_inserted=True):
    """Collect unique nodes from edges, including inserted components."""
    seen, nodes = set(), []
    for c in edges:
        if isinstance(c, tuple):
            src, tgt = c
        else:
            src, tgt = c["source"], c["target"]
        for sid in (src, tgt):
            node, _ = kg.resolve(sid)
            if node and node["id"] not in seen:
                seen.add(node["id"])
                nodes.append(node)
        if include_inserted and isinstance(c, dict) and c.get("insert_component"):
            ic = c["insert_component"]
            if ic["id"] not in seen:
                seen.add(ic["id"])
                nodes.append(kg.services.get(ic["id"]) or {
                    "id": ic["id"],
                    "name": ic["name"],
                    "provider": "unknown",
                    "network_placement": "connector",
                    "roles": ["connector"],
                })
    return {n["id"]: n for n in nodes}


def _edge_pairs(edges):
    """Return normalized (source, target) for each edge."""
    out = []
    for c in edges:
        if isinstance(c, tuple):
            out.append(c)
        else:
            out.append((c["source"], c["target"]))
    return out


def _compute_layout(nodes, edges):
    """Assign (x, y) to each node. Returns positions, container assignments."""
    pairs = _edge_pairs(edges)
    incoming = {nid: [] for nid in nodes}
    for s, d in pairs:
        if s in nodes and d in nodes:
            incoming[d].append(s)

    # Topological rank: sources at column 0, downstream at max(parent)+1.
    rank = {nid: 0 for nid in nodes}
    changed = True
    while changed:
        changed = False
        for nid in nodes:
            if incoming[nid]:
                new_rank = max(rank[p] for p in incoming[nid] if p in rank) + 1
                if new_rank > rank[nid]:
                    rank[nid] = new_rank
                    changed = True

    # Group by column, preserve input order for rows.
    by_col = {}
    for nid in nodes:
        by_col.setdefault(rank[nid], []).append(nid)

    positions = {}
    max_row = 0
    for col, nids in sorted(by_col.items()):
        for row, nid in enumerate(nids):
            x = MARGIN + col * H_SPACING
            y = MARGIN + row * V_SPACING
            positions[nid] = (x, y)
            max_row = max(max_row, row)

    # Place inserted connector nodes at the midpoint of the edge that needs them.
    for c in edges:
        if isinstance(c, dict) and c.get("verdict") == "NEEDS_COMPONENT":
            ic = c.get("insert_component")
            if not ic:
                continue
            ic_id = ic["id"]
            if ic_id not in nodes or ic_id not in positions:
                continue
            src, tgt = c["source"], c["target"]
            if src in positions and tgt in positions:
                sx, sy = positions[src]
                tx, ty = positions[tgt]
                # Center the connector on the horizontal midpoint between nodes.
                positions[ic_id] = (
                    (sx + tx) / 2 + NODE_W / 2,
                    (sy + ty) / 2,
                )

    # Container membership: nodes inside the VPC/VNet for their provider.
    containers = {}
    for nid, node in nodes.items():
        if node.get("network_placement") == "in_vpc":
            prov = node.get("provider", "unknown")
            containers.setdefault(prov, []).append(nid)

    return positions, containers, max_row


def _node_size(node):
    if node.get("network_placement") == "connector":
        return CONNECTOR_W, CONNECTOR_H
    return NODE_W, NODE_H


def _build_root():
    root = ET.Element("root")
    _cell(root, "0", None)
    _cell(root, "1", "0")
    return root


def _build_model(root):
    model = ET.Element(
        "mxGraphModel",
        {
            "dx": "1000",
            "dy": "700",
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": "850",
            "pageHeight": "1100",
            "math": "0",
            "shadow": "0",
        },
    )
    model.append(root)
    return model


def _build_diagram(model, name="Page-1"):
    diagram = ET.Element("diagram", {"name": name})
    diagram.append(model)
    return diagram


def _build_mxfile(diagram):
    mxfile = ET.Element(
        "mxfile",
        {
            "host": "app.diagrams.net",
            "version": "24.0.0",
            "type": "device",
            "pages": "1",
        },
    )
    mxfile.append(diagram)
    return mxfile


def _node_right_mid(pos, size):
    x, y = pos
    w, h = size
    return x + w, y + h / 2


def _node_left_mid(pos, size):
    x, y = pos
    w, h = size
    return x, y + h / 2


def _node_center(pos, size):
    x, y = pos
    w, h = size
    return x + w / 2, y + h / 2


def _collect_badges(edges):
    """Map node_id -> list of badge items from FEATURE_ON_NODE verdicts."""
    badges = {}
    for c in edges:
        if isinstance(c, tuple):
            continue
        node_id = c.get("render_as", {}).get("node")
        if node_id:
            badges.setdefault(node_id, []).append({
                "text": c.get("render_as", {}).get("badge", "feature"),
                "severity": c.get("severity", "INFO"),
            })
    return badges


def _add_findings(root, findings, start_y):
    if not findings:
        return start_y
    x = MARGIN
    y = start_y + MARGIN
    for i, f in enumerate(findings):
        text = f"{f['rule_id']}: {f['title']}"
        if f.get("message"):
            text += f"\n{f['message']}"
        _cell(
            root,
            f"f_{i}",
            "1",
            value=text,
            style=_note_style(f.get("severity", "INFO")),
            vertex=True,
            geometry=_geometry(x, y, NOTE_W, NOTE_H),
        )
        y += NOTE_H + 20
    return y


def emit(edges, report, kg=None, embed_icons=False, output_path=None):
    """Generate a .drawio file from the given edges and validation report.

    edges may be a list of connectivity dicts (from validate.py) or plain
    (source, target) tuples (from translate.py). report should contain at least
    an `architecture` key with layer-2 findings.
    """
    kg = kg or kg_module.load()
    nodes = _resolve_nodes(kg, edges)
    positions, container_members, max_row = _compute_layout(nodes, edges)

    findings = list(report.get("architecture", []))
    if len(nodes) > 20:
        findings.insert(0, {
            "rule_id": "VIZ-001-TOO-MANY-NODES",
            "severity": "WARNING",
            "title": "Diagram may be too dense",
            "message": (
                f"{len(nodes)} nodes exceed the ~20 node readability ceiling. "
                "Consider splitting the diagram."
            ),
        })

    root = _build_root()
    node_cells = {}
    container_cells = {}

    # Boundary boxes (rendered behind nodes).
    for prov, members in container_members.items():
        xs = [positions[n][0] for n in members]
        ys = [positions[n][1] for n in members]
        widths = [_node_size(nodes[n])[0] for n in members]
        heights = [_node_size(nodes[n])[1] for n in members]
        min_x = min(xs)
        min_y = min(ys)
        max_x = max(x + w for x, w in zip(xs, widths))
        max_y = max(y + h for y, h in zip(ys, heights))
        cx = max(0, min_x - CONTAINER_PAD)
        cy = max(0, min_y - CONTAINER_PAD)
        cwidth = max_x - min_x + CONTAINER_PAD * 2
        cheight = max_y - min_y + CONTAINER_PAD * 2
        cid = f"container_{prov}"
        label = "VPC" if prov == "gcp" else "VNet" if prov == "azure" else f"{prov} network"
        container_cells[prov] = {
            "id": cid,
            "x": cx,
            "y": cy,
            "width": cwidth,
            "height": cheight,
        }
        _cell(
            root,
            cid,
            "1",
            value=label,
            style=(
                "group;swimlane;rounded=1;whiteSpace=wrap;html=1;"
                "verticalAlign=top;fillColor=#F5F5F5;strokeColor=#616161;fontSize=12;"
            ),
            vertex=True,
            geometry=_geometry(cx, cy, cwidth, cheight),
        )

    # Service nodes.
    for nid, node in nodes.items():
        pos = positions[nid]
        size = _node_size(node)
        icon_meta = kg.icon_for(nid)
        parent_id = "1"
        container = container_cells.get(node.get("provider"))
        if node.get("network_placement") == "in_vpc" and container:
            parent_id = container["id"]
            rel_x = pos[0] - container["x"]
            rel_y = pos[1] - container["y"]
        else:
            rel_x, rel_y = pos

        style = None
        if embed_icons and icon_meta and icon_meta.get("icon_path") and icon_meta["icon_path"].exists():
            style = _image_style(icon_meta["icon_path"])
        else:
            style = _generic_style(node.get("provider", "unknown"))

        cid = f"n_{_safe_id(nid)}"
        _cell(
            root,
            cid,
            parent_id,
            value=node.get("name", nid),
            style=style,
            vertex=True,
            geometry=_geometry(rel_x, rel_y, size[0], size[1]),
        )
        node_cells[nid] = {
            "id": cid,
            "pos": pos,
            "size": size,
            "parent": parent_id,
        }

    # Edges.
    edge_index = 0
    for c in edges:
        if isinstance(c, tuple):
            src, tgt = c
            verdict = "ALLOWED"
            severity = None
            message = None
        else:
            src, tgt = c["source"], c["target"]
            verdict = c.get("verdict", "ALLOWED")
            severity = c.get("severity")
            message = c.get("message")

        if verdict in ("BLOCKED", "FEATURE_ON_NODE"):
            continue
        if src not in node_cells or tgt not in node_cells:
            continue

        src_info = node_cells[src]
        tgt_info = node_cells[tgt]
        src_rm = _node_right_mid(src_info["pos"], src_info["size"])
        tgt_lm = _node_left_mid(tgt_info["pos"], tgt_info["size"])
        mid_x = (src_rm[0] + tgt_lm[0]) / 2

        if verdict == "NEEDS_COMPONENT" and isinstance(c, dict) and c.get("insert_component"):
            ic_id = c["insert_component"]["id"]
            ic_info = node_cells.get(ic_id)
            if not ic_info:
                continue
            ic_c = _node_center(ic_info["pos"], ic_info["size"])
            _cell(
                root,
                f"e_{edge_index}_a",
                "1",
                style=_edge_style("NEEDS_COMPONENT"),
                edge=True,
                source=src_info["id"],
                target=ic_info["id"],
                geometry=_edge_geometry([(mid_x, src_rm[1]), (mid_x, ic_c[1])]),
            )
            _cell(
                root,
                f"e_{edge_index}_b",
                "1",
                style=_edge_style("NEEDS_COMPONENT"),
                edge=True,
                source=ic_info["id"],
                target=tgt_info["id"],
                geometry=_edge_geometry([(mid_x, ic_c[1]), (mid_x, tgt_lm[1])]),
            )
            edge_index += 1
            continue

        points = [(mid_x, src_rm[1]), (mid_x, tgt_lm[1])]
        eid = f"e_{edge_index}"
        _cell(
            root,
            eid,
            "1",
            style=_edge_style(verdict),
            edge=True,
            source=src_info["id"],
            target=tgt_info["id"],
            geometry=_edge_geometry(points),
        )
        if message and verdict in ("ALLOWED_WITH_NOTE", "UNCOVERED", "UNKNOWN_SERVICE"):
            _cell(
                root,
                f"el_{edge_index}",
                eid,
                value=message[:120],
                style=_label_style(severity or "INFO"),
                vertex=True,
                geometry=_geometry(0.5, -15, 0, 0, relative=True),
            )
        edge_index += 1

    # Badges for FEATURE_ON_NODE verdicts.
    badges = _collect_badges(edges)
    for node_id, badge_list in badges.items():
        if node_id not in node_cells:
            continue
        info = node_cells[node_id]
        bx = info["size"][0] - BADGE_SIZE + 6
        by = -BADGE_SIZE + 6
        for i, badge in enumerate(badge_list):
            _cell(
                root,
                f"b_{_safe_id(node_id)}_{i}",
                info["id"],
                value=badge["text"],
                style=_badge_style(badge["severity"]),
                vertex=True,
                geometry=_geometry(
                    bx, by + i * (BADGE_SIZE + 4), BADGE_SIZE + 4, BADGE_SIZE
                ),
            )

    # Findings lane.
    xs = [p[0] + NODE_W for p in positions.values()]
    ys = [p[1] + NODE_H for p in positions.values()]
    if container_cells:
        xs += [c["x"] + c["width"] for c in container_cells.values()]
        ys += [c["y"] + c["height"] for c in container_cells.values()]
    max_y = max(ys + [(max_row + 1) * V_SPACING + MARGIN], default=0)
    _add_findings(root, findings, max_y)

    model = _build_model(root)
    diagram = _build_diagram(model)
    mxfile = _build_mxfile(diagram)

    ET.indent(mxfile, space="  ")
    xml_bytes = ET.tostring(mxfile, encoding="utf-8", xml_declaration=True)
    xml_text = xml_bytes.decode("utf-8")

    if output_path:
        Path(output_path).write_text(xml_text, encoding="utf-8")
    else:
        sys.stdout.write(xml_text)
        if not xml_text.endswith("\n"):
            sys.stdout.write("\n")

    return xml_text


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--edges", required=True)
    p.add_argument("--output", default=None)
    p.add_argument("--embed-icons", action="store_true")
    p.add_argument("--environment", default="poc")
    p.add_argument("--residency", default="none")
    p.add_argument("--sla", default="standard")
    a = p.parse_args()

    from validate import validate, _parse_edges
    kg = kg_module.load()
    edges_raw = _parse_edges(a.edges)
    report = validate(
        edges_raw,
        {"environment": a.environment, "data_residency": a.residency, "sla_tier": a.sla},
        kg=kg,
    )
    emit(edges_raw, report, kg=kg, embed_icons=a.embed_icons, output_path=a.output)


if __name__ == "__main__":
    main()
