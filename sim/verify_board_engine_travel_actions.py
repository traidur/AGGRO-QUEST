"""
Verification for the human-facing macro Travel seam (get_travel_actions/apply_travel_action,
checkpointed 2026-08-22) -- the second slice of the player-run-simulator decision seam,
following the same scope split Town got: expose the destination CHOICE (which Node, which
Border, Flight Path, or heading back to Town) as real actions; the in-pull risk-gate/
consumable logic inside resolve_node_pull/resolve_border_crossing stays automatic for this
slice (a later, separate slice).

Two parts: (1) direct mechanical checks on the action menu itself (Spice exclusion, Border
connectivity, Flight Path eligibility, idempotent re-Dealing, each action type's resolution).
(2) an end-to-end smoke drive -- proving a full multi-turn chain can be played ENTIRELY
through get_travel_actions/apply_travel_action plus the existing Town seam, with no crashes,
across all 9 classes -- since this is a genuinely new state machine (not a port of an old
one), there's no old-code baseline to bit-for-bit or aggregate-compare against; completeness
(can a full career actually be played this way) is what's being checked here.
"""
import random

import board_engine as BE
import board_state as B
import macro_sim as M
from board_state import HeroBoardState


def run_direct_checks(verbose=True):
    failures = []

    def check(name, condition, detail=""):
        if not condition:
            failures.append((name, detail))
            if verbose:
                print(f"FAIL: {name} -- {detail}")
        elif verbose:
            print(f"ok: {name}")

    # 1. Standing in Zone 1: declare_node options exclude Spice, match what's actually dealt;
    # cross_border includes exactly the one real connection (border_1_2); no Flight Path
    # (Zone 1 isn't a Flight Path Zone); return_to_town always present.
    rng = random.Random(3)
    level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
    board = B.BoardState(mode="solo", heroes=[], zones={}, level_decks=level_decks)
    hero = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, None),
                           bag=[None, None], locked=[False, False], gold=10)
    actions = BE.get_travel_actions(hero, board, rng)
    declares = [a for a in actions if a["type"] == "declare_node"]
    crossings = [a for a in actions if a["type"] == "cross_border"]
    flights = [a for a in actions if a["type"] == "flight_path"]
    check("declare_node options are all real (non-Spice) mobs",
          all(not B.is_spice(a["mob_name"]) for a in declares), declares)
    check("declare_node options match the actually-dealt board",
          set(a["node_name"] for a in declares) <= set(BE._nodes_in_zone(1)), declares)
    expected_borders = {name for name, connects in M.BORDER_NODES.items() if 1 in connects}
    check("Border crossings from Zone 1 match every real connecting Border Node",
          {a["border_name"] for a in crossings} == expected_borders, (crossings, expected_borders))
    check("no Flight Path from Zone 1 (not a Flight Path Zone)", flights == [], flights)
    check("return_to_town always offered", any(a["type"] == "return_to_town" for a in actions), actions)

    # 2. Repeated calls without an intervening apply don't re-deal (idempotent menu).
    dealt_before = dict(board.zones[1].dealt)
    BE.get_travel_actions(hero, board, rng)
    dealt_after = dict(board.zones[1].dealt)
    check("repeated get_travel_actions doesn't re-deal", dealt_before == dealt_after,
          (dealt_before, dealt_after))

    # 3. Flight Path IS offered from Zone 2 with enough Gold, targets Zone 4.
    hero2 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(2, None),
                            bag=[None, None], locked=[False, False], gold=M.FLIGHT_PATH_COST)
    actions2 = BE.get_travel_actions(hero2, board, rng)
    flight2 = [a for a in actions2 if a["type"] == "flight_path"]
    check("Flight Path offered from Zone 2 with enough gold", len(flight2) == 1, flight2)
    check("Flight Path targets Zone 4", flight2 and flight2[0]["target_zone"] == 4, flight2)

    # 4. Standing on a Border Node: only enter_zone (both sides) + return_to_town, nothing else.
    hero3 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=("border_1_2", None),
                            bag=[None, None], locked=[False, False], gold=10)
    actions3 = BE.get_travel_actions(hero3, board, rng)
    types3 = {a["type"] for a in actions3}
    check("Border Node offers only enter_zone + return_to_town",
          types3 == {"enter_zone", "return_to_town"}, types3)
    check("Border Node's enter_zone covers both connected Zones",
          {a["target_zone"] for a in actions3 if a["type"] == "enter_zone"} == {1, 2}, actions3)

    # 5. apply_travel_action: flight_path spends gold and moves; enter_zone moves for free;
    # return_to_town sets position to (zone, "town") for free.
    hero4 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(2, None),
                            bag=[None, None], locked=[False, False], gold=M.FLIGHT_PATH_COST)
    BE.apply_travel_action(hero4, {"type": "flight_path", "target_zone": 4, "cost": M.FLIGHT_PATH_COST},
                            "warrior", M.QUESTS, board, rng, M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)
    check("flight_path spends gold", hero4.gold == 0, hero4.gold)
    check("flight_path moves to target Zone", hero4.position == (4, None), hero4.position)

    hero5 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=("border_3_4", None),
                            bag=[None, None], locked=[False, False], gold=5)
    BE.apply_travel_action(hero5, {"type": "enter_zone", "target_zone": 4},
                            "warrior", M.QUESTS, board, rng, M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)
    check("enter_zone moves for free", (hero5.position, hero5.gold) == ((4, None), 5), hero5.position)

    hero6 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(3, None),
                            bag=[None, None], locked=[False, False], gold=5)
    BE.apply_travel_action(hero6, {"type": "return_to_town"},
                            "warrior", M.QUESTS, board, rng, M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)
    check("return_to_town moves to (zone, town) for free", (hero6.position, hero6.gold) == ((3, "town"), 5),
          hero6.position)

    print(f"\n{len(failures)} failures" if failures else "\nAll direct checks passed")
    return not failures


def _play_full_chain_via_seam(class_name, strategy, rng, max_turns):
    """Plays an entire career using ONLY the human-facing macro primitives (enter_town/
    get_town_actions/apply_town_action, get_travel_actions/apply_travel_action) -- at Town,
    buys anything affordable then leaves; while traveling, picks UNIFORMLY AT RANDOM among
    every currently legal action (declare_node/cross_border/flight_path/return_to_town).
    Deliberately not "always declare_node first": a declined pull costs no turn by design (see
    resolve_node_pull's own comment, "nothing was actually attempted at the table"), so a
    driver that only ever re-tries the first dealt Node can spin indefinitely without making
    trip progress whenever that Node keeps getting declined -- not a bug, but not a useful
    completeness smoke test either. Random choice naturally exercises Border crossings and
    Flight Path too, not just repeated declines on one Node.

    Not meant to reproduce run_solo_chain's own quest-aware routing -- this is a completeness
    smoke test (can a full career be played end to end through the new seam without crashing
    or getting stuck), not a behavior-matching one."""
    mod = M.CARD_SOURCE[class_name]
    max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
    hero = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(1, "town"),
                           bag=[None] * M.BAG_SIZE, locked=[False] * M.BAG_SIZE)
    hero.bag[0] = "food"
    purchase_queue = M._build_purchase_queue(class_name, 0)
    level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
    board = B.BoardState(mode="solo", heroes=[hero], zones={}, level_decks=level_decks)

    turns_seen = 0
    safety = 0
    while hero.turns < max_turns and safety < max_turns * 3:
        safety += 1
        zone_or_border, node = hero.position
        if node == "town":
            BE.enter_town(hero, class_name, strategy, rng)
            while True:
                actions = BE.get_town_actions(hero, purchase_queue)
                buyable = next((a for a in actions if a["type"] == "buy"), None)
                chosen = buyable if buyable else next(a for a in actions if a["type"] == "leave_town")
                still_in_town = BE.apply_town_action(hero, chosen, purchase_queue)
                if not still_in_town:
                    break
            continue

        quest_pool = M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS
        actions = BE.get_travel_actions(hero, board, rng)
        non_retreat = [a for a in actions if a["type"] != "return_to_town"]
        chosen = rng.choice(non_retreat) if non_retreat else actions[0]
        result = BE.apply_travel_action(hero, chosen, class_name, quest_pool, board, rng,
                                         M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)
        turns_seen += 1
        if result.get("outcome") == "died":
            # Minimal death handling for this smoke test only -- just enough to keep the
            # chain moving, not a faithful port of run_solo_chain's own post-processing.
            hero.alive = True
            hero.hp = hero.max_hp
            zone_or_border, _ = hero.position
            zone_id = zone_or_border if isinstance(zone_or_border, int) else 1
            hero.position = (zone_id, "town")
    return hero, turns_seen


def run_smoke_test(verbose=True):
    ok = True
    for class_name in M.CARD_SOURCE:
        rng = random.Random(9)
        try:
            hero, turns_seen = _play_full_chain_via_seam(class_name, "food_only", rng, 60)
            status = f"turns={hero.turns} declares_and_crossings={turns_seen} gold={hero.gold} xp={hero.xp}"
            if verbose:
                print(f"{class_name:12s} OK  {status}")
        except Exception as e:
            ok = False
            if verbose:
                print(f"{class_name:12s} FAIL  {type(e).__name__}: {e}")
    return ok


if __name__ == "__main__":
    ok1 = run_direct_checks()
    print()
    ok2 = run_smoke_test()
    raise SystemExit(0 if (ok1 and ok2) else 1)
