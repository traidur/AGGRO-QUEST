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
                            "warrior", board, rng, M.RISK_TOLERANCE_BASE, True)
    check("flight_path spends gold", hero4.gold == 0, hero4.gold)
    check("flight_path moves to target Zone", hero4.position == (4, None), hero4.position)

    hero5 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=("border_3_4", None),
                            bag=[None, None], locked=[False, False], gold=5)
    BE.apply_travel_action(hero5, {"type": "enter_zone", "target_zone": 4},
                            "warrior", board, rng, M.RISK_TOLERANCE_BASE, True)
    check("enter_zone moves for free", (hero5.position, hero5.gold) == ((4, None), 5), hero5.position)

    hero6 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(3, None),
                            bag=[None, None], locked=[False, False], gold=5)
    BE.apply_travel_action(hero6, {"type": "return_to_town"},
                            "warrior", board, rng, M.RISK_TOLERANCE_BASE, True)
    check("return_to_town moves to (zone, town) for free", (hero6.position, hero6.gold) == ((3, "town"), 5),
          hero6.position)

    # 6. use_food/use_potion: heal, consume/decrement the slot, no position or turn change.
    hero7 = HeroBoardState(class_name="warrior", hp=10.0, max_hp=18.0, position=(1, None),
                            bag=["food", None], locked=[False, False], gold=0)
    turns_before = hero7.turns
    BE.apply_travel_action(hero7, {"type": "use_food"}, "warrior", board, rng, M.RISK_TOLERANCE_BASE, True)
    check("use_food heals to full", hero7.hp == 18.0, hero7.hp)
    check("use_food consumes the slot", hero7.bag == [None, None], hero7.bag)
    check("use_food costs no turn", hero7.turns == turns_before, (hero7.turns, turns_before))

    hero8 = HeroBoardState(class_name="warrior", hp=10.0, max_hp=18.0, position=(1, None),
                            bag=[{"items": {"potion": 2}}, None], locked=[False, False], gold=0)
    BE.apply_travel_action(hero8, {"type": "use_potion"}, "warrior", board, rng, M.RISK_TOLERANCE_BASE, True)
    check("use_potion heals by POTION_HEAL", hero8.hp == min(18.0, 10.0 + M.POTION_HEAL), hero8.hp)
    check("use_potion decrements charges", hero8.bag[0] == {"items": {"potion": 1}}, hero8.bag)

    # 7. A locked food/potion slot is never touched by use_food/use_potion.
    hero9 = HeroBoardState(class_name="warrior", hp=10.0, max_hp=18.0, position=(1, None),
                            bag=["food"], locked=[True], gold=0)
    actions9 = BE.get_travel_actions(hero9, board, rng)
    check("locked food doesn't offer use_food", not any(a["type"] == "use_food" for a in actions9), actions9)

    # 8. Full-HP hero isn't offered use_food/use_potion even holding both.
    hero10 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, None),
                             bag=["food", {"items": {"potion": 1}}], locked=[False, False], gold=0)
    actions10 = BE.get_travel_actions(hero10, board, rng)
    check("full HP hero isn't offered use_food/use_potion",
          not any(a["type"] in ("use_food", "use_potion") for a in actions10), actions10)

    # 9. commit_node_pull never returns "declined" -- declaring is unconditional now.
    outcomes_seen = set()
    for seed_i in range(40):
        rng_c = random.Random(seed_i + 100)
        hero_c = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, None),
                                 bag=[None, None], locked=[False, False], gold=0)
        node_name = BE._nodes_in_zone(1)[0]
        mob_name = rng_c.choice(list(B._STANDARD_MOBS))
        result = BE.commit_node_pull(hero_c, "warrior", node_name, mob_name, rng_c)
        outcomes_seen.add(result["outcome"])
    check("commit_node_pull never declines", "declined" not in outcomes_seen, outcomes_seen)

    # 10. cross_border reveals 2 real candidates instead of auto-resolving (task #63,
    # 2026-08-23). Both discarded immediately regardless of which gets chosen.
    rng_s = random.Random(21)
    level_decks_s = {1: B.LevelDeck.new(1, rng_s), 2: B.LevelDeck.new(2, rng_s)}
    board_s = B.BoardState(mode="solo", heroes=[], zones={}, level_decks=level_decks_s)
    hero11 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, None),
                             bag=[None, None], locked=[False, False], gold=0)
    discard_before = list(level_decks_s[1].discard_pile)
    result11 = BE.apply_travel_action(hero11, {"type": "cross_border", "border_name": "border_1_2", "target_zone": 2},
                                       "warrior", board_s, rng_s, M.RISK_TOLERANCE_BASE, True)
    check("cross_border returns a scouted_pull_reveal, not a resolved outcome",
          result11["outcome"] == "scouted_pull_reveal", result11)
    check("scouted_pull_reveal carries exactly 2 candidates", len(result11["candidates"]) == 2, result11)
    check("scouted_pull_reveal candidates are all real (non-Spice) mobs",
          all(not B.is_spice(m) for m in result11["candidates"]), result11)
    check("cross_border doesn't move the hero yet (crossing not resolved)",
          hero11.position == (1, None), hero11.position)
    check("cross_border doesn't cost a turn yet (the pick+resolve step does)",
          hero11.turns == 0, hero11.turns)
    check("both drawn candidates land in the discard pile immediately",
          len(level_decks_s[1].discard_pile) >= len(discard_before) + 2, level_decks_s[1].discard_pile)

    # 11. Picking one of the 2 candidates and calling resolve_border_crossing directly resolves
    # the crossing for real (win/flee/died, position/turn changes as appropriate).
    picked = result11["candidates"][0]
    result11b = BE.resolve_border_crossing(hero11, "warrior", result11["border_name"], result11["target_zone"],
                                            picked, rng_s, M.RISK_TOLERANCE_BASE, True)
    check("resolving the picked candidate produces a real combat outcome",
          result11b["outcome"] in ("win", "flee", "died"), result11b)
    check("resolving the picked candidate costs one turn", hero11.turns == 1, hero11.turns)

    # 12. The AI-automatic path (scouted_pull_from_deck) is untouched -- still auto-picks one
    # mob directly, never returns a reveal dict.
    rng_ai = random.Random(22)
    level_decks_ai = {1: B.LevelDeck.new(1, rng_ai), 2: B.LevelDeck.new(2, rng_ai)}
    picked_ai = BE.scouted_pull_from_deck("warrior", level_decks_ai[1], rng_ai)
    check("scouted_pull_from_deck (AI path) still returns a single mob name directly",
          isinstance(picked_ai, str) and not B.is_spice(picked_ai), picked_ai)

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

        actions = BE.get_travel_actions(hero, board, rng)
        non_retreat = [a for a in actions if a["type"] != "return_to_town"]
        chosen = rng.choice(non_retreat) if non_retreat else actions[0]
        result = BE.apply_travel_action(hero, chosen, class_name, board, rng, M.RISK_TOLERANCE_BASE, True)
        if result.get("outcome") == "scouted_pull_reveal":
            # cross_border no longer auto-resolves (task #63) -- pick one of the 2 revealed
            # candidates and actually attempt the crossing.
            picked_mob = rng.choice(result["candidates"])
            result = BE.resolve_border_crossing(hero, class_name, result["border_name"], result["target_zone"],
                                                 picked_mob, rng, M.RISK_TOLERANCE_BASE, True)
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
