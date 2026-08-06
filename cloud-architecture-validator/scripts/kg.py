"""
Knowledge graph loader.

Default: local YAML files under ../references/kg/. No network, no credentials,
no cloud account required — which matters because this skill is also used to
demo Azure architectures, and requiring an active GCP account for that makes no
sense.

A BigQuery backend sits behind the same interface for later, once the KG grows
large enough to need multi-editor governance. Enable it with:
    export CAV_KG_BACKEND=bigquery
    export CAV_BQ_PROJECT=<project-id>
While the local backend is sufficient, leave it off — it only adds a failure
point with no benefit.
"""

import os
from pathlib import Path

import yaml

KG_DIR = Path(__file__).resolve().parent.parent / "references" / "kg"


class KnowledgeGraph:
    def __init__(self, services, conn_rules, conn_fallback, arch_rules,
                 aliases, overrides, alternatives, equivalences,
                 regenerate_roles):
        self.services = {s["id"]: s for s in services}
        self.conn_rules = conn_rules
        self.conn_fallback = conn_fallback
        self.arch_rules = arch_rules
        self.aliases = {a["alias"]: a for a in aliases}
        self.overrides = {(o["source"], o["target"]): o for o in overrides}
        self.alternatives = alternatives
        self.regenerate_roles = set(regenerate_roles)
        self.equivalences = equivalences
        self._eq_index = self._build_eq_index(equivalences)

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


def _read(name):
    with open(KG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load(backend=None):
    backend = backend or os.environ.get("CAV_KG_BACKEND", "local")
    if backend == "bigquery":
        return _load_bigquery()
    return _load_local()


def _load_local():
    services = _read("services.yaml")["services"]
    conn = _read("connectivity-rules.yaml")
    arch = _read("architecture-rules.yaml")["rules"]
    ov = _read("overrides.yaml")
    eq = _read("equivalences.yaml")
    return KnowledgeGraph(
        services=services,
        conn_rules=conn["rules"],
        conn_fallback=conn["fallback"],
        arch_rules=arch,
        aliases=ov.get("aliases", []) or [],
        overrides=ov.get("overrides", []) or [],
        alternatives=ov.get("alternatives", []) or [],
        equivalences=eq["equivalences"],
        regenerate_roles=eq.get("regenerate_roles", []),
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
    print("architecture rules:", len(kg.arch_rules))
    print("equivalence entries:", len(kg.equivalences))
