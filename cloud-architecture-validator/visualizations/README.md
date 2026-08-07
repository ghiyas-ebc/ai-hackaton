# KG explorer

Explores the source knowledge graph itself (`references/kg/services.yaml` +
`connectivity-rules.yaml`) — a neo4j-browser-style view, separate from the
skill's own draw.io output for a user-described architecture.

## Regenerate the graph

Edges come from `validate_connectivity()` in `scripts/validate.py` — the exact
function the skill uses at runtime — run over every same-provider service
pair. No separate/reinvented rule logic.

```bash
cd scripts
python3 export_kg_graph.py --output ../visualizations/kg_graph.json
```

Only `ALLOWED`, `ALLOWED_WITH_NOTE`, and `NEEDS_COMPONENT` edges are kept.
`BLOCKED` and `UNCOVERED` are dropped — this is a map of what can connect, not
the full N² matrix (cross-provider pairs are always `BLOCKED`, so only
same-provider pairs are even checked).

## View

```bash
cd visualizations
python3 -m http.server 8000
# open http://localhost:8000/kg_explorer.html
```

Must be served over http — `kg_explorer.html` fetches `kg_graph.json`, which
`file://` blocks. Filter by provider/category/verdict, click a node for its
KG properties, click an edge for the rule that produced it.

`lib/nvl.bundle.js` is [Neo4j NVL](https://neo4j.com/docs/nvl/current/) —
`@neo4j-nvl/base`, the same rendering engine Neo4j Bloom uses — bundled to a
single offline IIFE with esbuild (`window.__NVL__.NVL`). Telemetry is
disabled explicitly via `disableTelemetry: true`. It ships web-worker layout
code that can't resolve its worker URL once bundled flat; NVL detects that and
falls back to synchronous layout automatically, so the graph still renders,
just without the worker thread.

The bundle also includes `@neo4j-nvl/interaction-handlers` (`PanInteraction`,
`ZoomInteraction`, `DragNodeInteraction`, `ClickInteraction`,
`HoverInteraction`) — `@neo4j-nvl/base` alone only renders and hit-tests
(`getHits`); it does not wire mouse events to pan/zoom/drag on its own.

To rebuild the bundle after an NVL version bump:
```bash
mkdir /tmp/nvl-build && cd /tmp/nvl-build
npm init -y && npm install @neo4j-nvl/base @neo4j-nvl/interaction-handlers esbuild
cat > entry.js <<'JS'
import { NVL } from '@neo4j-nvl/base';
import { PanInteraction, ZoomInteraction, DragNodeInteraction, ClickInteraction, HoverInteraction } from '@neo4j-nvl/interaction-handlers';
window.__NVL__ = { NVL, PanInteraction, ZoomInteraction, DragNodeInteraction, ClickInteraction, HoverInteraction };
JS
npx esbuild entry.js --bundle --minify --format=iife --outfile=nvl.bundle.js
cp nvl.bundle.js <repo>/cloud-architecture-validator/visualizations/lib/
```

**Do not use NVL's built-in `caption`/`captionAlign`/`captionSize` fields on
nodes or relationships.** They render via an internal canvas text pass that
silently stops drawing after certain `nvl.fit()`/zoom sequences — same node,
same props, works in an isolated repro, breaks once `fit()` has run once on
the instance. Root-caused by testing the same minimal node in and out of that
code path; never traced further into the minified bundle than that. Labels
here are instead done via NVL's documented DOM-overlay fields — `html` on
nodes, `captionHtml` on relationships — which hand NVL a real DOM element to
position over the node/edge itself, so there's no silent-drop failure mode.
See `makeNodeLabel`/`makeEdgeLabel` in `kg_explorer.html`. If a future NVL
version fixes the canvas caption bug, this workaround can be dropped, but
verify with `nvl.fit()` in the repro before trusting it.

Dev-only tool — not part of the shipped skill zip.
