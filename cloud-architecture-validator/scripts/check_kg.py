"""
Knowledge graph integrity checker + regression against the original draft.

Run this after every KG change. It guards two things:

1. Internal consistency — dangling references, roles required by rules that no
   node provides, rules that can never fire.
2. Regression — every edge that used to be hand-written in the draft SQL must
   still receive the correct verdict. This is the evidence that the property
   model replaced the pair-list model without losing knowledge.

    python3 check_kg.py
"""

import json
from pathlib import Path

import kg as kg_module
from validate import validate

FIXTURE = Path(__file__).resolve().parent.parent / "evals" / "regression_draft_edges.json"


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

    print("\n== Regression against the original draft ==")
    passed, failed, deviations = check_regression(kg)
    total = passed + len(failed)
    print(f"  passed {passed}/{total}  (including {deviations} verdicts that deliberately differ from the draft)")
    for f in failed:
        print("  [X]", f)

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

    return 1 if (problems or failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
