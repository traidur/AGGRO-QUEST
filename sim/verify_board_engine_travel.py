"""
Verification for board_engine.decide_travel -- deliberately NOT a mocked-replay diff against
run_one_trip the way the other three board_engine pieces are (see verify_board_engine*.py).

decide_travel is a pure, stateless decision function assembled entirely from already-tested,
unchanged primitives (macro_sim's _hop_distance/_reachable_free/_next_border_toward/
_best_case_mob/_pull_exceeds_risk/_bag_has_room -- reused, not reimplemented) and consumes no
randomness. run_one_trip's own routing block keeps its chosen node_name in a local variable
with no hookable capture point (unlike mob_name, which flows through _engine_pull/
_scouted_pull_mob and so was capturable for the other three pieces) -- building a mocked-
replay harness for this specific function would cost more than it proves, given every
sub-decision it delegates to is already independently regression-tested. Instead this is a
direct, explicit test: one scenario per real branch in the ported logic, each with a hand-
verified expected action.
"""
import macro_sim as M
import board_engine as BE
from board_state import HeroBoardState


def _hero(class_name, position, active_quests=(), bag=None, locked=None, gold=0, hp=None):
    mod = M.CARD_SOURCE[class_name]
    max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
    return HeroBoardState(class_name=class_name, hp=hp if hp is not None else max_hp, max_hp=max_hp,
                           position=position, bag=list(bag) if bag is not None else [None, None],
                           locked=list(locked) if locked is not None else [False, False],
                           active_quests=list(active_quests), gold=gold)


def _node_for_loot(loot):
    return next(n for n, (t, l) in M.NODES.items() if l == loot)


def _zone1_loot():
    return next(l for n, (t, l) in M.NODES.items() if M.NODE_ZONE[n] == 1)


def _zone2_loot():
    return next(l for n, (t, l) in M.NODES.items() if M.NODE_ZONE[n] == 2)


def run_checks(verbose=True):
    failures = []

    def check(name, condition, detail=""):
        if not condition:
            failures.append((name, detail))
            if verbose:
                print(f"FAIL: {name} -- {detail}")
        elif verbose:
            print(f"ok: {name}")

    class_name = "warrior"

    # 1. Same-zone, node already present in the current Zone -- should just arrive.
    loot = _zone1_loot()
    hero = _hero(class_name, (1, "town"), active_quests=[loot])
    action = BE.decide_travel(hero, class_name, M.QUESTS, {1, 2}, M.RISK_TOLERANCE_BASE, True)
    check("same-zone arrival", action == {"action": "arrived", "zone_id": 1, "node_name": _node_for_loot(loot)},
          action)

    # 2. All active quests already satisfied -> end_trip, no travel needed.
    loot = _zone1_loot()
    q = M.QUESTS[loot]
    bag = [{"loot": {loot: q["required"]}, "closed": False}, None]
    hero = _hero(class_name, (1, "town"), active_quests=[loot], bag=bag)
    action = BE.decide_travel(hero, class_name, M.QUESTS, {1, 2}, M.RISK_TOLERANCE_BASE, True)
    check("quests already satisfied", action == {"action": "end_trip"}, action)

    # 3. Needs a Border crossing, low risk (Warrior vs Standard tier at full HP should never
    # exceed risk_tolerance_base=0 for the best-case mob) -> should commit to the crossing.
    loot = _zone2_loot()
    hero = _hero(class_name, (1, "town"), active_quests=[loot])
    action = BE.decide_travel(hero, class_name, M.QUESTS, {1, 2}, M.RISK_TOLERANCE_BASE, True)
    check("cross border, safe", action == {"action": "cross_border", "border_name": "border_1_2", "target_zone": 2},
          action)

    # 4. Needs a Border crossing, hero critically wounded (best-case mob now lethal for SOME
    # hand), no consumable available -> should decline and end the trip.
    loot = _zone2_loot()
    hero = _hero(class_name, (1, "town"), active_quests=[loot], hp=1.0)
    action = BE.decide_travel(hero, class_name, M.QUESTS, {1, 2}, M.RISK_TOLERANCE_BASE, True)
    check("cross border, too risky, no consumable", action == {"action": "end_trip"}, action)

    # 5. Same setup as #4, but WITH a Food in the bag -- risk_only_as_last_resort means the
    # crossing is judged worth attempting since a consumable can back it up.
    loot = _zone2_loot()
    hero = _hero(class_name, (1, "town"), active_quests=[loot], hp=1.0, bag=["food", None])
    action = BE.decide_travel(hero, class_name, M.QUESTS, {1, 2}, M.RISK_TOLERANCE_BASE, True)
    check("cross border, risky but has consumable", action["action"] == "cross_border", action)

    # 6. Flight Path: standing in Zone 2, target Zone 4, affordable -> arrives directly,
    # spending FLIGHT_PATH_COST, no Border crossing attempted. Zone 4's loot names live in
    # LEVEL2_QUESTS, not the base QUESTS pool -- use the matching quest_pool.
    loot = next(l for n, (t, l) in M.NODES.items() if M.NODE_ZONE[n] == 4)
    hero = _hero(class_name, (2, "town"), active_quests=[loot], gold=M.FLIGHT_PATH_COST)
    action = BE.decide_travel(hero, class_name, M.LEVEL2_QUESTS, {1, 2}, M.RISK_TOLERANCE_BASE, True)
    check("flight path taken", action == {"action": "arrived", "zone_id": 4, "node_name": _node_for_loot(loot)},
          action)
    check("flight path spent gold", hero.gold == 0, hero.gold)
    check("flight path moved hero", hero.position == (4, None), hero.position)

    # 7. Same as #6 but can't afford it -- falls through to Border-crossing routing instead
    # (Zone 2 -> Zone 4 isn't directly bordered, so _next_border_toward picks the first hop).
    loot = next(l for n, (t, l) in M.NODES.items() if M.NODE_ZONE[n] == 4)
    hero = _hero(class_name, (2, "town"), active_quests=[loot], gold=0)
    action = BE.decide_travel(hero, class_name, M.LEVEL2_QUESTS, {1, 2}, M.RISK_TOLERANCE_BASE, True)
    check("flight path unaffordable falls back to border", action["action"] == "cross_border", action)

    # 8. No active quests at all, already standing in a fallback Zone -> end_trip (pickup
    # itself happens at the next Town turn, not here).
    hero = _hero(class_name, (1, "town"), active_quests=[])
    action = BE.decide_travel(hero, class_name, M.QUESTS, {1, 2}, M.RISK_TOLERANCE_BASE, True)
    check("no quests, already at fallback zone", action == {"action": "end_trip"}, action)

    # 9. No active quests, NOT standing in a fallback Zone -- routes toward the nearest one.
    # Zone 3/4 aren't fallback zones here, so from a border between 3/4 heading toward {1,2}.
    hero = _hero(class_name, ("border_3_4", None), active_quests=[])
    action = BE.decide_travel(hero, class_name, M.QUESTS, {1, 2}, M.RISK_TOLERANCE_BASE, True)
    check("no quests, routes toward fallback zone", action["action"] in ("arrived", "cross_border"), action)

    # 10. Bag deadlock (every slot closed/locked, no room) with Food available -- consumes
    # Food to free a slot, then continues routing normally (arrives, since target is Zone 1
    # itself).
    loot = _zone1_loot()
    bag = ["food", {"loot": {"Something else": 1}, "closed": True}]
    hero = _hero(class_name, (1, "town"), active_quests=[loot], bag=bag, hp=5.0)
    action = BE.decide_travel(hero, class_name, M.QUESTS, {1, 2}, M.RISK_TOLERANCE_BASE, True)
    check("bag deadlock consumes food", hero.hp == hero.max_hp and hero.bag[0] is None,
          (hero.hp, hero.bag))
    check("bag deadlock then arrives", action["action"] == "arrived", action)

    # 11. Bag deadlock, no consumables available at all -> end_trip.
    bag = [{"loot": {"Something else": 1}, "closed": True}, {"loot": {"Other": 1}, "closed": True}]
    loot = _zone1_loot()
    hero = _hero(class_name, (1, "town"), active_quests=[loot], bag=bag)
    action = BE.decide_travel(hero, class_name, M.QUESTS, {1, 2}, M.RISK_TOLERANCE_BASE, True)
    check("bag deadlock, no consumables", action == {"action": "end_trip"}, action)

    print(f"\n{len(failures)} failures out of 11 checks" if failures else "\nAll 11 checks passed")
    return not failures


if __name__ == "__main__":
    ok = run_checks()
    raise SystemExit(0 if ok else 1)
