"""
Verification for the 3 new Bag-slot consumables wired 2026-08-22 (task #62): Scroll of
Vanquishing, Smoke Bomb, Preserving Charm. Whetstone is deliberately not covered here -- see
task #61, it needs a class-agnostic card-buff mechanism that doesn't exist yet.

Direct mechanical checks only (matching verify_board_engine_travel_actions.py's own pattern):
buy_consumable/use_charm through the Town seam, use_scroll/use_smoke_bomb through the Travel
seam, the Standard-tier-only restriction on Scroll, and that the AI-automatic path
(decide_travel/resolve_node_pull/resolve_border_crossing/run_solo_chain) is completely
unaffected by any of it (these items only exist behind the new action types, never touched by
old code paths)."""
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

    purchase_queue = M._build_purchase_queue("warrior", 0)

    # 1. buy_consumable offered when affordable + Bag has room, not otherwise.
    hero = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, "town"),
                           bag=[None, None], locked=[False, False], gold=20)
    actions = BE.get_town_actions(hero, purchase_queue)
    buys = [a for a in actions if a["type"] == "buy_consumable"]
    check("all 3 consumables offered with full gold and room",
          {a["item_name"] for a in buys} == set(M.CONSUMABLE_ITEMS), buys)

    hero_poor = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, "town"),
                                bag=[None, None], locked=[False, False], gold=0)
    actions_poor = BE.get_town_actions(hero_poor, purchase_queue)
    check("no buy_consumable offered with 0 gold",
          not any(a["type"] == "buy_consumable" for a in actions_poor), actions_poor)

    hero_full = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, "town"),
                                bag=[{"items": {"potion": 3}}, {"items": {"potion": 3}}],
                                locked=[False, False], gold=20)
    actions_full = BE.get_town_actions(hero_full, purchase_queue)
    check("no buy_consumable offered with a full bag (no room)",
          not any(a["type"] == "buy_consumable" for a in actions_full), actions_full)

    # 2. apply_town_action buy_consumable spends gold and adds the item.
    hero2 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, "town"),
                            bag=[None, None], locked=[False, False], gold=20)
    action = {"type": "buy_consumable", "item_name": "scroll_of_vanquishing", "cost": M.SCROLL_COST}
    BE.apply_town_action(hero2, action, purchase_queue)
    check("buy_consumable spends gold", hero2.gold == 20 - M.SCROLL_COST, hero2.gold)
    check("buy_consumable adds the item",
          M._accessible_count(hero2.bag, hero2.locked, "scroll_of_vanquishing") == 1, hero2.bag)

    # 3. use_charm offered only for a decayed active quest, only with a Charm in bag.
    hero3 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, "town"),
                            bag=[None, None], locked=[False, False], gold=0,
                            active_quests=["Pilfered Goods"], decay_stage={"Pilfered Goods": 2})
    actions3 = BE.get_town_actions(hero3, purchase_queue)
    check("no use_charm without a Charm in bag", not any(a["type"] == "use_charm" for a in actions3), actions3)
    hero3.bag[0] = {"items": {"preserving_charm": 1}}
    actions3b = BE.get_town_actions(hero3, purchase_queue)
    charm_actions = [a for a in actions3b if a["type"] == "use_charm"]
    check("use_charm offered once Charm is in bag and quest is decayed",
          charm_actions == [{"type": "use_charm", "loot": "Pilfered Goods"}], charm_actions)

    # 4. apply_town_action use_charm resets decay and consumes the Charm.
    BE.apply_town_action(hero3, {"type": "use_charm", "loot": "Pilfered Goods"}, purchase_queue)
    check("use_charm resets decay_stage to 0", hero3.decay_stage["Pilfered Goods"] == 0, hero3.decay_stage)
    check("use_charm consumes the Charm",
          M._accessible_count(hero3.bag, hero3.locked, "preserving_charm") == 0, hero3.bag)

    # 5. get_travel_actions offers use_scroll only for Standard-tier mobs, use_smoke_bomb for any.
    rng = random.Random(11)
    level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
    board = B.BoardState(mode="solo", heroes=[], zones={}, level_decks=level_decks)
    hero4 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, None),
                            bag=[{"items": {"scroll_of_vanquishing": 1, "smoke_bomb": 1}}, None],
                            locked=[False, False], gold=0)
    actions4 = BE.get_travel_actions(hero4, board, rng)
    declares = [a for a in actions4 if a["type"] == "declare_node"]
    scrolls = [a for a in actions4 if a["type"] == "use_scroll"]
    bombs_node = [a for a in actions4 if a["type"] == "use_smoke_bomb" and "node_name" in a]
    bombs_border = [a for a in actions4 if a["type"] == "use_smoke_bomb" and "border_name" in a]
    check("use_scroll only offered for Standard-tier mobs",
          all(a["mob_name"] in B._STANDARD_MOBS for a in scrolls), scrolls)
    check("use_scroll never exceeds the number of Standard-tier declare_node options",
          len(scrolls) <= len(declares), (scrolls, declares))
    check("use_smoke_bomb offered for every declared Node regardless of tier",
          len(bombs_node) == len(declares), (bombs_node, declares))
    check("use_smoke_bomb also offered for Border crossings",
          len(bombs_border) >= 1, bombs_border)

    # 6. use_scroll never offered without a Scroll in bag.
    hero5 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, None),
                            bag=[None, None], locked=[False, False], gold=0)
    actions5 = BE.get_travel_actions(hero5, board, rng)
    check("no use_scroll/use_smoke_bomb without holding either item",
          not any(a["type"] in ("use_scroll", "use_smoke_bomb") for a in actions5), actions5)

    # 7. apply_travel_action use_scroll: guaranteed win, no HP loss, item consumed, gold+loot granted.
    hero6 = HeroBoardState(class_name="warrior", hp=5.0, max_hp=18.0, position=(1, None),
                            bag=[{"items": {"scroll_of_vanquishing": 1}}, None],
                            locked=[False, False], gold=0)
    node_name = BE._nodes_in_zone(1)[0]
    _tier, loot_name = M.NODES[node_name]
    result = BE.apply_travel_action(hero6, {"type": "use_scroll", "node_name": node_name, "mob_name": "Grunt"},
                                     "warrior", board, rng, M.RISK_TOLERANCE_BASE, True)
    check("use_scroll outcome is win", result["outcome"] == "win", result)
    check("use_scroll costs no HP", hero6.hp == 5.0, hero6.hp)
    check("use_scroll grants +1 gold", hero6.gold == 1, hero6.gold)
    check("use_scroll grants the Node's loot",
          M._accessible_count(hero6.bag, hero6.locked, loot_name) == 1, hero6.bag)
    check("use_scroll consumes the item",
          M._accessible_count(hero6.bag, hero6.locked, "scroll_of_vanquishing") == 0, hero6.bag)
    check("use_scroll costs one turn", hero6.turns == 1, hero6.turns)

    # 8. apply_travel_action use_smoke_bomb (Node case): guaranteed flee, no HP/gold/loot change.
    hero7 = HeroBoardState(class_name="warrior", hp=5.0, max_hp=18.0, position=(1, None),
                            bag=[{"items": {"smoke_bomb": 1}}, None], locked=[False, False], gold=0)
    result7 = BE.apply_travel_action(hero7, {"type": "use_smoke_bomb", "node_name": node_name, "mob_name": "Enforcer"},
                                      "warrior", board, rng, M.RISK_TOLERANCE_BASE, True)
    check("use_smoke_bomb (Node) outcome is flee", result7["outcome"] == "flee", result7)
    check("use_smoke_bomb (Node) costs no HP", hero7.hp == 5.0, hero7.hp)
    check("use_smoke_bomb (Node) grants no gold", hero7.gold == 0, hero7.gold)
    check("use_smoke_bomb (Node) consumes the item",
          M._accessible_count(hero7.bag, hero7.locked, "smoke_bomb") == 0, hero7.bag)
    check("use_smoke_bomb (Node) costs one turn", hero7.turns == 1, hero7.turns)

    # 9. apply_travel_action use_smoke_bomb (Border case): no position change, item consumed.
    hero8 = HeroBoardState(class_name="warrior", hp=5.0, max_hp=18.0, position=(1, None),
                            bag=[{"items": {"smoke_bomb": 1}}, None], locked=[False, False], gold=0)
    result8 = BE.apply_travel_action(hero8, {"type": "use_smoke_bomb", "border_name": "border_1_2", "target_zone": 2},
                                      "warrior", board, rng, M.RISK_TOLERANCE_BASE, True)
    check("use_smoke_bomb (Border) outcome is flee", result8["outcome"] == "flee", result8)
    check("use_smoke_bomb (Border) doesn't move the hero", hero8.position == (1, None), hero8.position)
    check("use_smoke_bomb (Border) consumes the item",
          M._accessible_count(hero8.bag, hero8.locked, "smoke_bomb") == 0, hero8.bag)

    print(f"\n{len(failures)} failures" if failures else "\nAll direct checks passed")
    return not failures


def verify_ai_path_unaffected(trials=10, seed=1, verbose=True):
    """The AI-automatic path (decide_travel/resolve_node_pull/resolve_border_crossing/
    run_solo_chain) never touches CONSUMABLE_ITEMS, use_scroll, use_smoke_bomb, or use_charm --
    a hero driven purely by run_solo_chain should never hold any of the 3 new items (nothing
    ever buys or grants them outside the new human-facing action types), same shape as
    verify_board_engine_travel_actions.py's own smoke test."""
    ok = True
    for class_name in M.CARD_SOURCE:
        rng = random.Random(seed)
        final_hero = None
        for entry in BE.run_solo_chain(class_name, "food_only", rng, max_turns=90):
            pass
        # Re-run driving hero directly to inspect bag contents at the end.
        mod = M.CARD_SOURCE[class_name]
        max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
        hero = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(1, "town"),
                               bag=[None] * M.BAG_SIZE, locked=[False] * M.BAG_SIZE)
        hero.bag[0] = "food"
        purchase_queue = M._build_purchase_queue(class_name, 0)
        level_decks = {1: B.LevelDeck.new(1, random.Random(seed)), 2: B.LevelDeck.new(2, random.Random(seed))}
        board = B.BoardState(mode="solo", heroes=[hero], zones={}, level_decks=level_decks)
        rng2 = random.Random(seed)
        BE.resolve_town_turn(hero, class_name, "food_only", purchase_queue, "save", rng2)
        while hero.turns < 90:
            quest_pool = M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS
            valid_quest_zones = M.LEVEL2_QUEST_ZONES if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.LEVEL1_QUEST_ZONES
            BE.run_solo_trip(hero, class_name, quest_pool, valid_quest_zones, board, rng2,
                              M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)
            BE.resolve_town_turn(hero, class_name, "food_only", purchase_queue, "save", rng2)
        held_new_items = any(
            isinstance(slot, dict) and any(k in M.CONSUMABLE_ITEMS for k in slot["items"])
            for slot in hero.bag)
        if held_new_items:
            ok = False
            if verbose:
                print(f"FAIL: {class_name} AI-driven hero somehow holds a new consumable: {hero.bag}")
        elif verbose:
            print(f"ok: {class_name} AI-driven hero never touches the new consumables")
    return ok


if __name__ == "__main__":
    ok1 = run_direct_checks()
    print()
    ok2 = verify_ai_path_unaffected()
    raise SystemExit(0 if (ok1 and ok2) else 1)
