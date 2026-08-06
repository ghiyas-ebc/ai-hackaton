"""
Knowledge graph integrity checker + regression against the original draft.

Run this after every KG change. It guards three things:

1. Internal consistency — dangling references, roles required by rules that no
   node provides, rules that can never fire.
2. Regression — every edge that used to be hand-written in the draft SQL must
   still receive the correct verdict. This is the evidence that the property
   model replaced the pair-list model without losing knowledge.
3. Rule reachability — connectivity-rules.yaml is first-match-wins, so a rule
   inserted too high silently starves every rule below it that it also matches.
   Regression cannot see this: it only replays old pairs, which the shadowing
   rule may still decide correctly. Reachability brute-forces every directed
   node pair and attributes the verdict to the rule that produced it; a rule
   that never wins any pair is dead.

    python3 check_kg.py
"""

import json
import os
from collections import defaultdict
from pathlib import Path

import kg as kg_module
from validate import _match, _should_reverse, validate

FIXTURE = Path(__file__).resolve().parent.parent / "evals" / "regression_draft_edges.json"
ICON_FIXTURE = Path(__file__).resolve().parent.parent / "evals" / "icon_regression.json"


def check_integrity(kg):
    problems = []

    # roles required by rules must exist for every provider
    needed = {r["needs_role"] for r in kg.conn_rules if r.get("needs_role")}
    providers = {s["provider"] for s in kg.services.values()}
    for role in needed:
        for prov in providers:
            if not kg.by_role(role, provider=prov):
                problems.append(
                    f"No node holds role '{role}' for provider '{prov}'. "
                    "NEEDS_COMPONENT rules will not be able to suggest a component."
                )

    # aliases and alternatives must point at real nodes
    for alias in kg.aliases.values():
        if alias["resolves_to"] not in kg.services:
            problems.append(f"Alias '{alias['alias']}' points at an unknown node.")
    for alt in kg.alternatives:
        for sid in alt["pair"]:
            if sid not in kg.services:
                problems.append(f"Alternative references an unknown node: {sid}")

    # equivalences must point at real nodes and cross provider boundaries
    for entry in kg.equivalences:
        src = kg.services.get(entry["source"])
        if not src:
            problems.append(f"Unknown equivalence source: {entry['source']}")
            continue
        if len(entry["targets"]) > 1 and not entry.get("selection_criteria"):
            problems.append(
                f"'{entry['source']}' has {len(entry['targets'])} equivalents but no "
                "selection_criteria — translation would be ambiguous."
            )
        for tgt in entry["targets"]:
            t = kg.services.get(tgt["id"])
            if not t:
                problems.append(f"Unknown equivalence target: {tgt['id']}")
            elif t["provider"] == src["provider"]:
                problems.append(
                    f"Equivalence {entry['source']} -> {tgt['id']} stays within one "
                    "provider; that is an alternative, not a cross-provider equivalent."
                )

    # every node must carry the properties that drive decisions
    for s in kg.services.values():
        for field in ("provider", "network_placement", "reachability", "roles", "region_scope"):
            if not s.get(field):
                problems.append(f"Node '{s['id']}' is missing property '{field}'.")

    return problems


def check_icons(kg):
    """Validate the icon mapping against the service table and env dirs.

    Does not bundle icons; it only checks that the YAML mapping is complete
    and that the referenced files exist when the official icon directories are
    configured via CAV_GCP_ICON_DIR / CAV_AZURE_ICON_DIR.
    """
    problems = []
    icon_root = {
        "gcp": os.environ.get("CAV_GCP_ICON_DIR"),
        "azure": os.environ.get("CAV_AZURE_ICON_DIR"),
    }
    svc_icons = kg.icons.get("services", {})
    cats = kg.icons.get("categories", {})

    # every service must have a mapping
    for sid in kg.services:
        if sid not in svc_icons:
            problems.append(f"No icon mapping for service '{sid}'.")
            continue
        mapping = svc_icons[sid]
        svc = kg.services[sid]
        if svc["provider"] != mapping["provider"]:
            problems.append(
                f"Icon mapping for '{sid}' says provider '{mapping['provider']}' "
                f"but services.yaml says '{svc['provider']}'."
            )
        if mapping["type"] == "category":
            cat = mapping.get("category")
            if not cat:
                problems.append(f"Icon mapping for '{sid}' is category type but missing category.")
            elif cat not in cats.get(svc["provider"], {}):
                problems.append(f"Icon mapping for '{sid}' references unknown category '{cat}'.")
        elif mapping["type"] == "core":
            icon = mapping.get("icon")
            if not icon:
                problems.append(f"Icon mapping for '{sid}' is core type but missing icon path.")
            elif icon_root[svc["provider"]]:
                path = Path(icon_root[svc["provider"]]) / icon
                if not path.exists():
                    problems.append(f"Missing icon file for '{sid}': {path}")

    # no icon entry for unknown service
    for sid in svc_icons:
        if sid not in kg.services:
            problems.append(f"Icon mapping references unknown service '{sid}'.")

    return problems


def check_rule_reachability(kg):
    """Attribute every decidable directed pair to the rule that decides it.

    Mirrors the decision path in validate.validate_connectivity (alias
    resolution, direction normalization, overrides, first-match-wins) so the
    attribution matches what a user would actually get. A rule that wins no
    pair is unreachable; the guess names the shadow — the highest rule that
    would have matched pairs this rule also matches.
    """
    hits = defaultdict(list)            # rule_id -> [(src, dst)] it wins
    shadowed_by = defaultdict(lambda: defaultdict(int))  # rule -> shadow -> count

    nodes = list(kg.services.values())
    for raw_src in nodes:
        for raw_dst in nodes:
            src, _ = kg.resolve(raw_src["id"])
            dst, _ = kg.resolve(raw_dst["id"])
            if _should_reverse(src, dst):
                src, dst = dst, src
            if (src["id"], dst["id"]) in kg.overrides:
                continue  # pair taken by an override, no rule fires
            later = []
            for i, rule in enumerate(kg.conn_rules):
                if _match(rule, src, dst):
                    hits[rule["id"]].append((raw_src["id"], raw_dst["id"]))
                    later = kg.conn_rules[i + 1:]
                    break
            for other in later:
                if _match(other, src, dst):
                    shadowed_by[other["id"]][rule["id"]] += 1

    unreachable = []
    for rule in kg.conn_rules:
        rid = rule["id"]
        if hits[rid]:
            continue
        if shadowed_by[rid]:
            shadow, n = max(shadowed_by[rid].items(), key=lambda kv: kv[1])
            guess = (
                f"every pair it matches ({n}) is already decided by '{shadow}' "
                "higher in the file"
            )
        else:
            guess = (
                "no node pair in services.yaml satisfies its 'when' clause at "
                "all — the properties it requires may not exist on any node"
            )
        unreachable.append((rid, guess))

    return hits, unreachable


def check_icon_regression(kg):
    fixture = json.loads(ICON_FIXTURE.read_text(encoding="utf-8"))
    passed, failed = 0, []
    for case in fixture["cases"]:
        got = kg.icon_for(case["service_id"])
        ok = got and got["type"] == case["type"]
        if ok and "category" in case:
            ok = got.get("category") == case["category"]
        if ok:
            passed += 1
        else:
            failed.append(
                f"{case['id']} {case['service_id']}: expected {case['type']}" +
                (f"/{case['category']}" if "category" in case else "") +
                f", got {got.get('type')}/{got.get('category')}"
            )
    return passed, failed, len(fixture["cases"])


def check_regression(kg):
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    passed, failed, deviations = 0, [], 0

    for case in fixture["cases"]:
        rep = validate([tuple(case["edge"])], kg=kg)
        got = rep["connectivity"][0]
        ok = got["verdict"] == case["verdict"]
        if ok and "severity" in case:
            ok = got.get("severity") == case["severity"]
        if ok and case.get("expect_reversed"):
            ok = "direction_normalized" in got
        if ok:
            passed += 1
            if case.get("deviates"):
                deviations += 1
        else:
            failed.append(
                f"{case['id']} {case['edge'][0]}->{case['edge'][1]}: "
                f"expected {case['verdict']}/{case.get('severity')}, "
                f"got {got['verdict']}/{got.get('severity')} ({got['rule_id']})"
            )

    # ALTERNATIVE_TO must never surface as a valid connection
    for case in fixture["must_not_be_connectivity"]:
        rep = validate([tuple(case["pair"])], kg=kg)
        got = rep["connectivity"][0]
        if got["verdict"] in ("ALLOWED", "ALLOWED_WITH_NOTE") and not rep["exclusive_choices"]:
            failed.append(
                f"{case['id']} {case['pair']}: reported as a valid connection with "
                "no mutually-exclusive warning."
            )
        elif not rep["exclusive_choices"]:
            failed.append(f"{case['id']} {case['pair']}: not detected as a mutually-exclusive pair.")
        else:
            passed += 1

    return passed, failed, deviations


def main():
    kg = kg_module.load()

    print("== KG integrity ==")
    problems = check_integrity(kg)
    if problems:
        for p in problems:
            print("  [!]", p)
    else:
        print("  clean")

    print("\n== Rule reachability ==")
    hits, unreachable = check_rule_reachability(kg)
    for rule in kg.conn_rules:
        rid = rule["id"]
        example = hits[rid][0] if hits[rid] else None
        if example:
            print(f"  [ok] {rid}: decides {len(hits[rid])} pair(s), e.g. {example[0]} -> {example[1]}")
        else:
            print(f"  [X]  {rid}: UNREACHABLE — never decides any pair")
    for rid, guess in unreachable:
        print(f"       guess: {guess}.")

    print("\n== Regression against the original draft ==")
    passed, failed, deviations = check_regression(kg)
    total = passed + len(failed)
    print(f"  passed {passed}/{total}  (including {deviations} verdicts that deliberately differ from the draft)")
    for f in failed:
        print("  [X]", f)

    print("\n== Icon mapping ==")
    icon_problems = check_icons(kg)
    if icon_problems:
        for p in icon_problems:
            print("  [!]", p)
    else:
        print("  clean")

    print("\n== Icon regression ==")
    icon_passed, icon_failed, icon_total = 0, [], 0
    if ICON_FIXTURE.exists():
        icon_passed, icon_failed, icon_total = check_icon_regression(kg)
        print(f"  passed {icon_passed}/{icon_total}")
        for f in icon_failed:
            print("  [X]", f)
    else:
        print(f"  skipped ({ICON_FIXTURE.name} not found)")

    print("\n== Coverage ==")
    ids = list(kg.services)
    gcp = [i for i in ids if kg.services[i]["provider"] == "gcp"]
    pairs = len(gcp) * (len(gcp) - 1)
    covered = 0
    for a in gcp:
        for b in gcp:
            if a == b:
                continue
            v = validate([(a, b)], kg=kg)["connectivity"][0]["verdict"]
            if v not in ("UNCOVERED", "UNKNOWN_SERVICE"):
                covered += 1
    print(f"  directed GCP pairs: {pairs}, decided: {covered} ({covered/pairs:.0%})")
    print("  (original draft: 20/462 = 4%)")

    return 1 if (problems or failed or unreachable or icon_problems or icon_failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
