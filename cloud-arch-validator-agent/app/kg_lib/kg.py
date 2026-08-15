"""
Knowledge graph loader.

Default: Postgres, reached over a DSN in `CAV_PG_DSN`. The graph outgrew what a
folder of YAML could do — not in size, but in access: several agents now read
it and one of them writes to it, which a file cannot arbitrate. Every backend
below returns the same `KnowledgeGraph` object, so `validate.py` and the rest of
the rule engine never learn where the rows came from.

    export CAV_KG_BACKEND=postgres   # default
    export CAV_PG_DSN=postgresql://cav:cav@localhost:5432/cav

The YAML loader survives as `CAV_KG_BACKEND=local`. It is no longer the source
of truth — `db/seed_from_yaml.py` moved that into Postgres — but it stays
because it needs no database, which makes it the reference the migration is
tested against and a working fallback when the DSN is unreachable.

The BigQuery stub predates both and remains unimplemented.
"""

import os
from pathlib import Path

import yaml

KG_DIR = Path(__file__).resolve().parent.parent / "references" / "kg"


class KnowledgeGraph:
    def __init__(self, services, conn_rules, conn_fallback, arch_rules,
                 aliases, overrides, alternatives, equivalences,
                 regenerate_roles, icons=None, arch_layers=None):
        self.services = {s["id"]: s for s in services}
        self.conn_rules = conn_rules
        self.conn_fallback = conn_fallback
        self.arch_rules = arch_rules
        # L0..L8 taxonomy. Ordered as declared so output and reports walk the
        # ladder in the same order every time.
        self.arch_layers = arch_layers or []
        self.layers_by_id = {l["id"]: l for l in self.arch_layers}
        self.aliases = {a["alias"]: a for a in aliases}
        self.overrides = {(o["source"], o["target"]): o for o in overrides}
        self.alternatives = alternatives
        self.regenerate_roles = set(regenerate_roles)
        self.equivalences = equivalences
        self._eq_index = self._build_eq_index(equivalences)
        self.icons = icons or {"categories": {}, "services": {}}
        self._icon_root = {
            "gcp": os.environ.get("CAV_GCP_ICON_DIR"),
            "azure": os.environ.get("CAV_AZURE_ICON_DIR"),
        }

    # -- resolusi id ------------------------------------------------------
    def resolve(self, service_id):
        """Return (node, alias_info|None). A non-None alias_info means the id
        given is not a standalone node."""
        if service_id in self.services:
            return self.services[service_id], None
        alias = self.aliases.get(service_id)
        if alias:
            return self.services.get(alias["resolves_to"]), alias
        return None, None

    def by_role(self, role, provider=None):
        return [
            s for s in self.services.values()
            if role in s.get("roles", [])
            and (provider is None or s["provider"] == provider)
        ]

    # -- equivalence ------------------------------------------------------
    def _build_eq_index(self, equivalences):
        """Bidirectional index: entries are written once, read from both sides."""
        index = {}
        for entry in equivalences:
            src = entry["source"]
            index.setdefault(src, []).append(entry)
            for tgt in entry["targets"]:
                mirrored = {
                    "source": tgt["id"],
                    "selection_criteria": entry.get("selection_criteria"),
                    "targets": [{
                        "id": src,
                        "level": tgt["level"],
                        "when": tgt.get("when"),
                        "caveats": tgt.get("caveats"),
                        "as": tgt.get("as"),
                        "feature": tgt.get("feature"),
                    }],
                }
                index.setdefault(tgt["id"], []).append(mirrored)
        return index

    def equivalents(self, service_id, target_provider):
        """All equivalents of service_id at target_provider, merged across entries."""
        out, criteria = [], None
        for entry in self._eq_index.get(service_id, []):
            for tgt in entry["targets"]:
                node = self.services.get(tgt["id"])
                if node and node["provider"] == target_provider:
                    out.append({**tgt, "name": node["name"]})
                    if entry.get("selection_criteria"):
                        criteria = entry["selection_criteria"]
        return out, criteria

    def alternatives_for(self, service_id):
        return [a for a in self.alternatives if service_id in a["pair"]]

    # -- icons ---------------------------------------------------------------
    def icon_for(self, service_id):
        """Return a resolved icon descriptor for a service.

        If the official icon directory env var for the provider is set, the
        result includes `icon_path` (an absolute Path). Otherwise `icon_path` is
        None and the caller can still draw the label and generic shape.
        """
        svc = self.services.get(service_id)
        if not svc:
            return None
        mapping = self.icons.get("services", {}).get(service_id)
        if not mapping:
            return {
                "service_id": service_id,
                "name": svc.get("name", service_id),
                "provider": svc["provider"],
                "type": "generic",
                "icon_path": None,
                "note": "No icon mapping defined.",
            }
        out = {
            "service_id": service_id,
            "name": svc.get("name", service_id),
            "provider": mapping["provider"],
            "type": mapping["type"],
        }
        if mapping.get("note"):
            out["note"] = mapping["note"]
        root = self._icon_root.get(mapping["provider"])
        if mapping["type"] == "core":
            out["icon"] = mapping["icon"]
            if root:
                out["icon_path"] = Path(root) / mapping["icon"]
            else:
                out["icon_path"] = None
        elif mapping["type"] == "category":
            cat = mapping["category"]
            out["category"] = cat
            cat_def = self.icons.get("categories", {}).get(mapping["provider"], {}).get(cat)
            if cat_def:
                out["category_name"] = cat_def["name"]
                out["icon"] = cat_def["file"]
                if root:
                    out["icon_path"] = Path(root) / cat_def["file"]
                else:
                    out["icon_path"] = None
            else:
                out["note"] = f"Unknown category: {cat}"
                out["icon_path"] = None
        else:
            out["icon_path"] = None
        return out


def _read(name):
    with open(KG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load(backend=None):
    backend = backend or os.environ.get("CAV_KG_BACKEND", "postgres")
    if backend == "bigquery":
        return _load_bigquery()
    if backend == "local":
        return _load_local()
    if backend != "postgres":
        raise ValueError(
            f"Unknown CAV_KG_BACKEND {backend!r}. Expected postgres, local, or "
            "bigquery."
        )
    return _load_postgres()


def _load_postgres():
    # Imported here, not at module scope: the YAML backend must keep working on
    # a machine with no psycopg installed and no database running.
    import kg_pg

    return kg_pg.load()


def _load_local():
    services = _read("services.yaml")["services"]
    conn = _read("connectivity-rules.yaml")
    arch_doc = _read("architecture-rules.yaml")
    arch = arch_doc["rules"]
    ov = _read("overrides.yaml")
    eq = _read("equivalences.yaml")
    icons = _read("icons.yaml")
    return KnowledgeGraph(
        services=services,
        conn_rules=conn["rules"],
        conn_fallback=conn["fallback"],
        arch_rules=arch,
        arch_layers=arch_doc.get("layers", []) or [],
        aliases=ov.get("aliases", []) or [],
        overrides=ov.get("overrides", []) or [],
        alternatives=ov.get("alternatives", []) or [],
        equivalences=eq["equivalences"],
        regenerate_roles=eq.get("regenerate_roles", []),
        icons=icons,
    )


def _load_bigquery():
    raise NotImplementedError(
        "The BigQuery backend is not enabled. It is only worth using once the "
        "KG outgrows file scale (thousands of nodes) or needs many concurrent "
        "editors. Until then the local backend is faster and cannot fail due to "
        "network or credentials."
    )


if __name__ == "__main__":
    kg = load()
    providers = {}
    for s in kg.services.values():
        providers[s["provider"]] = providers.get(s["provider"], 0) + 1
    print("nodes:", providers)
    print("connectivity rules:", len(kg.conn_rules))
    print("architecture rules:", len(kg.arch_rules), "across", len(kg.arch_layers), "layers")
    print("equivalence entries:", len(kg.equivalences))
