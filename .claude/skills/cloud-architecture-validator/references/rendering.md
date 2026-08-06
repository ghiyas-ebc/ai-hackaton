# Diagram rendering rules

Evidence status: the rules below are **unverified heuristics** in the context of
this skill, except where marked VERIFIED. The original draft presented similar
rules as trial-and-error findings with no checkable source — for a skill whose
whole premise is refusing unverified claims, that was inconsistent. Verify before
treating any of this as settled.

## Layer order

Write elements back to front: boundary box → service node → label. For nodes,
write order determines stacking. For edges, the original draft's claim that write
order has no effect is **unverified** — if lines overlap, fix it through routing
and position rather than through ordering.

## Labels

- Attach labels to the line, not to a separate legend. Non-technical readers
  read a diagram locally, not by looking back and forth to a corner.
- For `NEEDS_COMPONENT`, draw the component as a **small node on the edge path**,
  not as a text annotation. That is what makes the user see that something was
  added rather than merely being told.
- For `FEATURE_ON_NODE`, draw a small badge on the parent node. Do not create a
  separate box. (VERIFIED: the original draft modelled WAF as a node, which
  produced a dangling box with no correct position in the traffic path.)

## Layout

- Progress left→right or top→bottom, consistently within a diagram.
- Side components (logging, secret store) belong on a branch to the side, not at
  the end of the main flow — readers interpret a diagram as a sequence, and
  putting them last makes them read as the final step.
- Group nodes into boundary boxes per VPC/VNet or per project. Floating nodes
  make security boundaries hard to read.
- The readability ceiling is around 20 nodes (see VIZ-001). Beyond that, split.

## Icons

Do not re-bundle official Google/Microsoft icon sets into the skill — brand
guidelines restrict it, and the icons change often (Azure especially). Use
draw.io's built-in GCP/Azure shape libraries. Where a service isn't covered, use
a generic shape with a clear label and say so, rather than borrowing a
similar-looking icon from another service.

## Post-generation verification

If the diagram is produced by code, run automated checks: do any node coordinates
overlap? does any edge have a dangling source or target? Do not rely on visually
estimating from the XML text.
