"""Vendored copy of the cloud-architecture-validator skills' scripts.

Copied verbatim from `cloud-architecture-validator-create-architect/scripts/`
and its three sibling skills, with one edit: `export_kg_graph.py` no longer
resolves a cross-skill path, because here there is no sibling skill to resolve.
Keeping the rest byte-identical is deliberate — a diff against the skills should
show drift, not reformatting. `app/kg_lib/` and `app/evals/` are excluded from
ruff for the same reason.

These are flat CLI modules that import each other by bare name (`import kg`,
`from validate import validate`). `app/tools.py` puts this directory on
`sys.path` before importing them. The vendored layout reproduces the skill's
own layout exactly — `kg.py` derives `KG_DIR` from `__file__.parent.parent /
references / kg`, and `check_kg.py` derives its fixtures from `.. / evals` —
so neither file needed editing.

Importing this package also performs the `sys.path` insert, so `kg_lib` works
standalone; `tools.py` does not rely on that, since isort would reorder the
import out from under the modules it enables.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
