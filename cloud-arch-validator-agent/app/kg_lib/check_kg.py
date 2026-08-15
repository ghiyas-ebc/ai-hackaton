"""
Knowledge graph integrity checker + regression against the original draft.

Run this after every KG change. It guards five things:

1. Internal consistency — dangling references, roles required by rules that no
   node provides, rules that can never fire.

2. Role vocabulary — roles are a closed set, and the catalog's `kind` must
   agree with what the rules actually match. A misspelled role is structurally
   a valid string, so check 1 walks straight past it.
3. Regression — every edge that used to be hand-written in the draft SQL must
   still receive the correct verdict. This is the evidence that the property
   model replaced the pair-list model without losing knowledge.
4. Rule reachability — connectivity-rules.yaml is first-match-wins, so a rule
   inserted too high silently starves every rule below it that it also matches.
   Regression cannot see this: it only replays old pairs, which the shadowing
   rule may still decide correctly. Reachability brute-forces every directed
   node pair and attributes the verdict to the rule that produced it; a rule
   that never wins any pair is dead.
5. Provenance — every node must declare who wrote it, and any node an agent
   proposed must carry a human sign-off. This does not verify semantic truth
   (see D6 — nothing here can); it verifies that somebody claims to have
   checked, which is the part a script can actually enforce.

    python3 check_kg.py
"""

import datetime
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import kg as kg_module
from validate import _match, _should_reverse, validate

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


def _roles_named_by_rules(kg):
    """Roles a connectivity rule matches on, read out of its `when` clause.

    Only the YAML-declared half. validate.py and verdict_card.py also match
    roles, in Python, and no cheap introspection finds those — which is exactly
    why the catalog records where each load-bearing role is read rather than
    leaving a reader to grep for it.
    """
    named = set()
    for rule in kg.conn_rules:
        if rule.get("needs_role"):
            named.add(rule["needs_role"])
        for side in ("source", "target"):
            cond = (rule.get("when") or {}).get(side) or {}
            for key in ("any_role", "all_roles", "none_role"):
                named.update(cond.get(key) or [])
    return named


def check_role_catalog(kg):
    """Roles are a closed vocabulary, and `kind` must not lie.

    Two failures this catches that nothing else did. A role nobody declared —
    usually a typo — inserts cleanly, matches no rule, and leaves a node that
    reads as fully specified; the integrity check above walks straight past it
    because a role is structurally just a string. And a role the catalog calls
    `descriptive` while a rule matches it tells the curator not to bother with
    a field that decides verdicts, which is worse than saying nothing.

    Returns (problems, warnings). An unused role is a warning: vocabulary
    ahead of the graph is untidy, not wrong.
    """
    problems, warnings = [], []
    catalog = kg.role_catalog

    if not catalog:
        # The local backend on a tree with no export, or a database migrated
        # past 0004 and never seeded. Say so rather than passing every check
        # below vacuously.
        return (["The role catalog is empty — `role-catalog.yaml` is missing or "
                 "`role_catalog` was never seeded. Every role check below is "
                 "silently skipped while it stays empty."], warnings)

    held = {r for s in kg.services.values() for r in s.get("roles", [])}
    for role in sorted(held - set(catalog)):
        owners = sorted(s["id"] for s in kg.services.values()
                        if role in s.get("roles", []))
        problems.append(
            f"Role '{role}' is held by {', '.join(owners)} but is not in the "
            "role catalog. A role outside the catalog is matched by nothing — "
            "check the spelling, or add it with a `kind`."
        )

    for role in sorted(_roles_named_by_rules(kg) | set(kg.regenerate_roles)):
        entry = catalog.get(role)
        if entry is None:
            problems.append(
                f"Rules match role '{role}' but it is not in the role catalog."
            )
        elif entry.get("kind") != "load_bearing":
            problems.append(
                f"Role '{role}' is catalogued as '{entry.get('kind')}' while a "
                "rule matches it. Promote it to load_bearing — the curator is "
                "currently being told this role is optional."
            )

    for role in sorted(set(catalog) - held):
        warnings.append(
            f"Role '{role}' is in the catalog but held by no service."
        )

    return problems, warnings


VALID_PROVENANCE_STATUS = {"manual", "unverified", "verified"}


def check_provenance(kg, today=None):
    """Refuse a KG containing entries no human has vouched for.

    D6 says a wrong `reachability` fails silently across ~20 pairs and this
    script cannot catch it, because it checks structural consistency rather
    than semantic truth. That remains true. What this check *can* see is the
    weaker but still useful thing: whether anybody claims to have looked.
    An agent-written entry lands as `unverified` and fails here until a human
    flips it, which turns D6 from a discipline into a gate.

    Returns (problems, warnings). Warnings do not fail the run — a stale date
    means "re-check this", not "this is wrong".
    """
    problems, warnings = [], []
    today = today or datetime.date.today()

    for s in kg.services.values():
        prov = s.get("provenance")
        if not prov:
            problems.append(
                f"Node '{s['id']}' has no `provenance`. Every entry must say who "
                "wrote it and whether the judgment fields were human-confirmed."
            )
            continue
        status = prov.get("status")
        if status not in VALID_PROVENANCE_STATUS:
            problems.append(
                f"Node '{s['id']}' has provenance.status '{status}'; expected one "
                f"of {sorted(VALID_PROVENANCE_STATUS)}."
            )
            continue
        if status == "unverified":
            problems.append(
                f"Node '{s['id']}' is provenance.status 'unverified' — proposed by "
                f"'{prov.get('generated', 'unknown')}' and not yet human-confirmed. "
                "Confirm network_placement, reachability and roles, then set "
                "status: verified with a verified: date."
            )
            continue
        if status == "verified" and not prov.get("verified"):
            problems.append(
                f"Node '{s['id']}' claims status 'verified' but carries no "
                "`verified:` date. Say when, or it is not a sign-off."
            )
        for field in ("verified", "stale_after"):
            raw = prov.get(field)
            if raw is None:
                continue
            date = raw if isinstance(raw, datetime.date) else None
            if date is None:
                try:
                    date = datetime.date.fromisoformat(str(raw))
                except ValueError:
                    problems.append(
                        f"Node '{s['id']}' provenance.{field} is '{raw}'; expected "
                        "YYYY-MM-DD."
                    )
                    continue
            if field == "stale_after" and date < today:
                warnings.append(
                    f"Node '{s['id']}' went stale on {date} — re-check its "
                    "judgment fields against the provider's current docs."
                )

    return problems, warnings


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


def check_layer_coverage(kg):
    """Per-layer: does every rule in the layer still fire on something?

    One global coverage number hides a layer narrowing to zero — L5 could stop
    finding anything at all and the headline percentage would barely move. The
    sweep runs each GCP pair through the validator under the most permissive
    context (production / residency id / critical), because rules behind
    `applies_when` never fire under the default PoC context and would look
    dead for the wrong reason.

    Reported, not enforced. Unlike a connectivity rule — which is unreachable
    if no node pair satisfies it — an architecture rule can legitimately need
    a shape no two-node pair produces. Failing the build on that would push
    people to weaken rules to keep the check green.
    """
    ctx = {"environment": "production", "data_residency": "id", "sla_tier": "critical"}
    fired = Counter()
    gcp = [i for i in kg.services if kg.services[i]["provider"] == "gcp"]
    for a in gcp:
        for b in gcp:
            if a == b:
                continue
            for f in validate([(a, b)], ctx, kg=kg)["architecture"]:
                fired[f["rule_id"]] += 1

    enabled = [r for r in kg.arch_rules if r.get("enabled", True)]
    report = []
    for layer in kg.arch_layers:
        if layer["id"] == "L1":
            continue
        rules = [r for r in enabled if r.get("layer") == layer["id"]]
        report.append({
            "id": layer["id"], "title": layer["title"],
            "rules": [(r["id"], fired[r["id"]]) for r in rules],
            "uncovered": layer.get("status") == "uncovered" or not rules,
        })
    return report


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

    print("\n== Role catalog ==")
    role_problems, role_warnings = check_role_catalog(kg)
    if role_problems:
        for p in role_problems:
            print("  [!]", p)
    else:
        load_bearing = len(kg.load_bearing_roles)
        print(f"  clean — {len(kg.role_catalog)} roles, {load_bearing} "
              f"load-bearing, {len(kg.role_catalog) - load_bearing} descriptive")
    for w in role_warnings:
        print("  [~]", w)

    print("\n== Provenance ==")
    prov_problems, prov_warnings = check_provenance(kg)
    if prov_problems:
        for p in prov_problems:
            print("  [!]", p)
    else:
        print("  clean — every node is human-authored or human-confirmed")
    for w in prov_warnings:
        print("  [~]", w)

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
    print(f"  L1 directed GCP pairs: {pairs}, decided: {covered} ({covered/pairs:.0%})")
    print("  (original draft: 20/462 = 4%)")

    print("\n== Layer coverage (L2-L8) ==")
    for layer in check_layer_coverage(kg):
        if layer["uncovered"]:
            print(f"  [~] {layer['id']} {layer['title']}: UNCOVERED — no rules, reports honestly")
            continue
        dead = [rid for rid, n in layer["rules"] if n == 0]
        mark = "[~]" if dead else "[ok]"
        print(f"  {mark} {layer['id']} {layer['title']}: "
              + ", ".join(f"{rid}={n}" for rid, n in layer["rules"]))
        for rid in dead:
            print(f"       {rid} fired on no pair in the sweep — may need a shape "
                  "two nodes cannot produce, or may have silently narrowed.")

    return 1 if (
        problems or role_problems or prov_problems or failed or unreachable
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
