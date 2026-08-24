"""
Terminal front end for a full human-played career: Town shopping, field travel (Node pulls,
Border crossings/Scouted Pull, consumables), and the actual round-by-round combat inside every
pull -- solo mode only (BoardState's mode="solo"). Built 2026-08-23 per
unified-sprouting-aurora.md's Part 5 step 7 ("Human UI extension"), now that combat_engine.py
(all 9 classes) and board_engine.py's Town/Travel/competitive seams are all complete and
regression-clean (tasks #44-#67).

Deliberately NOT playtest_cli.py's replacement -- that file (and playtest_web.py) still drive
the old 4-class playtest_engine.py prototype and are left untouched, out of scope here. This is
a new, additive sibling that drives the real macro+combat stack instead: get_town_actions/
apply_town_action, get_travel_actions/apply_travel_action, and the SAME combat_engine
get_legal_actions/apply_action loop QuestIntelligence.decide_combat drives -- just with a
terminal-input decide_fn in place of the solver, threaded through via board_engine's decide_fn
parameter (checkpointed 2026-08-23, see board_engine.py's _pull_and_resolve/commit_node_pull/
resolve_border_crossing/_resolve_forced_recovery docstrings). Every AI-automatic driver
(run_solo_chain, run_competitive_chain, decay_stress_test, etc.) is completely unaffected --
decide_fn defaults to None everywhere, which is exactly the solver-automatic behavior those
callers already relied on before this parameter existed.

Reuses apply_death_post_processing/apply_recovery_post_processing (extracted from
run_solo_chain's own inline blocks for exactly this reason) and _resolve_forced_recovery (with
decide_fn threaded through) rather than reimplementing solo's death/recovery rules a second
time -- see board_engine.py's own docstrings for the full reasoning behind each piece.

Usage:
    python playtest_board_cli.py --class warrior
    python playtest_board_cli.py --class runecaster --seed 7
"""
from __future__ import annotations

import argparse
import random

import board_engine as BE
import board_state as B
import macro_sim as M
from board_state import HeroBoardState


def _current_quest_pool(hero):
    return M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS


def _fmt_combat_action(i, a):
    if not a["legal"]:
        stance_str = f" [{a['stance']}]" if a["stance"] else ""
        return f"  {i}) {a['card']}{stance_str} -- ILLEGAL this round"
    stance_str = f" [{a['stance']}]" if a["stance"] else ""
    variant_str = f" ({a['variant']})" if a["variant"] != a["card"] else ""
    return (f"  {i}) {a['card']}{stance_str}{variant_str} -- "
            f"dmg {a['dmg_dealt']:.0f} to mob, take {a['dmg_taken']:.0f}  "
            f"(you: {a['resulting_hp']:.0f} HP, mob: {a['resulting_mob_hp']:.0f} HP left)")


def _prompt_choice(prompt, actions, fmt_fn):
    while True:
        for i, a in enumerate(actions):
            print(fmt_fn(i, a))
        choice = input(prompt).strip()
        try:
            idx = int(choice)
            a = actions[idx]
        except (ValueError, IndexError):
            print("Invalid choice.")
            continue
        if not a.get("legal", True):
            print("That's not legal right now.")
            continue
        return a


def human_decide_combat(state, actions):
    """The decide_fn passed down into board_engine -- same (state, actions) -> action shape as
    QuestIntelligence.decide_combat, so it drops into the identical get_legal_actions/
    apply_action loop macro_sim._engine_pull already runs, no separate combat loop needed."""
    print(f"\n--- Round {state.round_num + 1} --- you: {state.hero_hp:.0f} HP, "
          f"mob ({state.mob_name}): {state.mob_hp_remaining:.0f}/{state.mob_hp_total:.0f} HP")
    return _prompt_choice("Play: ", actions, _fmt_combat_action)


def _fmt_town_action(i, a):
    if a["type"] in ("leave_town", "leave_trainer"):
        return f"  {i}) Leave {'Trainer' if a['type'] == 'leave_trainer' else 'Town'}"
    if a["type"] == "buy":
        return f"  {i}) Buy {a['tag']} ({a['kind']}) -- {a['cost']}g"
    if a["type"] == "buy_consumable":
        return f"  {i}) Buy {a['item_name']} -- {a['cost']}g"
    if a["type"] == "use_charm":
        return f"  {i}) Use Preserving Charm on {a['loot']} (reset decay)"
    return f"  {i}) {a}"


def _do_town(hero, class_name, strategy, purchase_queue, rng):
    setup = BE.enter_town(hero, class_name, strategy, rng)
    print(f"\n=== Town (Zone {hero.position[0]}) ===")
    if setup["quests_completed"]:
        print(f"Turned in {setup['quests_completed']} quest(s).")
    print(f"Gold: {hero.gold}  XP: {hero.xp}  HP: {hero.hp:.0f}/{hero.max_hp:.0f}")
    print(f"Active quests: {hero.active_quests}")

    while True:
        actions = BE.get_town_actions(hero, purchase_queue)
        a = _prompt_choice("Choose: ", actions, _fmt_town_action)
        still_in_town = BE.apply_town_action(hero, a, purchase_queue)
        if not still_in_town:
            print("Leaving Town, fully rested.")
            return
        print(f"Gold: {hero.gold}")


def _do_trainer(hero, class_name, purchase_queue):
    """Human-facing Trainer visit -- checkpointed 2026-08-24, Class Trainer split from Town
    into its own turn-costing node type (see board_engine.get_town_actions/enter_trainer's own
    docstrings for the full finding). Mirrors _do_town's shape exactly, using the SAME
    get_town_actions/apply_town_action functions (filtered by hero.position's "trainer"
    marker) -- only enter_trainer/leave_trainer differ from Town's own enter_town/leave_town."""
    setup = BE.enter_trainer(hero, class_name)
    print(f"\n=== Class Trainer (Zone {hero.position[0]}) ===")
    if setup["mandatory_turn"]:
        print("You've been granted your mandatory Level 2 upgrade!")
    print(f"Gold: {hero.gold}")

    while True:
        actions = BE.get_town_actions(hero, purchase_queue)
        a = _prompt_choice("Choose: ", actions, _fmt_town_action)
        still_at_trainer = BE.apply_town_action(hero, a, purchase_queue)
        if not still_at_trainer:
            print("Leaving the Trainer.")
            return
        print(f"Gold: {hero.gold}")


def _fmt_travel_action(i, a):
    if a["type"] == "declare_node":
        return f"  {i}) Fight at {a['node_name']} -- {a['mob_name']}"
    if a["type"] == "cross_border":
        return f"  {i}) Cross {a['border_name']} -> Zone {a['target_zone']} (Scouted Pull)"
    if a["type"] == "enter_zone":
        return f"  {i}) Enter Zone {a['target_zone']}"
    if a["type"] == "flight_path":
        return f"  {i}) Flight Path -> Zone {a['target_zone']} ({a['cost']}g)"
    if a["type"] == "use_scroll":
        return f"  {i}) Use Scroll of Vanquishing on {a['node_name']} ({a['mob_name']})"
    if a["type"] == "use_smoke_bomb":
        target = a.get("node_name") or a.get("border_name")
        return f"  {i}) Use Smoke Bomb to bail on {target}"
    if a["type"] == "use_food":
        return f"  {i}) Eat Food (full heal)"
    if a["type"] == "use_potion":
        return f"  {i}) Drink Potion (+{M.POTION_HEAL:.0f} HP)"
    if a["type"] == "visit_trainer":
        return f"  {i}) Visit the Class Trainer"
    return f"  {i}) Return to Town"


def _report_outcome(result):
    # mob_name is absent from a Smoke Bomb's flee outcome (commit_smoke_bomb_flee -- no combat
    # was ever played, nothing to name), so this reads it defensively rather than assuming
    # every outcome dict shares the exact same keys.
    if result["outcome"] == "win":
        print(f"Victory over {result.get('mob_name', 'the foe')}! +1 Gold.")
    elif result["outcome"] == "flee":
        mob = result.get("mob_name")
        print(f"Survived but didn't finish off {mob} -- no loot this time." if mob
              else "Bailed out with a Smoke Bomb -- no fight, no loot.")
    elif result["outcome"] == "no_room":
        print("Won, but your Bag has no room -- loot lost!")
    elif result["outcome"] == "healed":
        pass  # HP printed by the caller's next loop header


def _do_travel(hero, class_name, board, rng):
    """Runs one field trip until the hero returns to Town, visits the Trainer, or dies. Mirrors
    run_solo_trip's own scope, human-driven. Returns "town", "trainer", or "died" -- "trainer"
    checkpointed 2026-08-24, Class Trainer split from Town into its own turn-costing node
    type, reachable from this same Travel menu via visit_trainer."""
    while True:
        actions = BE.get_travel_actions(hero, board, rng)
        zone_or_border, _node = hero.position
        print(f"\n--- At {zone_or_border} --- HP: {hero.hp:.0f}/{hero.max_hp:.0f}  "
              f"Gold: {hero.gold}  Bag: {hero.bag}")
        a = _prompt_choice("Choose: ", actions, _fmt_travel_action)

        result = BE.apply_travel_action(hero, a, class_name, board, rng,
                                         M.RISK_TOLERANCE_BASE, True, decide_fn=human_decide_combat)

        if result["outcome"] == "scouted_pull_reveal":
            cand = result["candidates"]
            print(f"Scouted Pull reveals two possible foes: 1) {cand[0]}   2) {cand[1]}")
            while True:
                pick = input("Which will you face? [1/2]: ").strip()
                if pick in ("1", "2"):
                    break
                print("Enter 1 or 2.")
            mob_name = cand[0] if pick == "1" else cand[1]
            result = BE.resolve_border_crossing(hero, class_name, result["border_name"],
                                                 result["target_zone"], mob_name, rng,
                                                 M.RISK_TOLERANCE_BASE, True,
                                                 decide_fn=human_decide_combat)

        if result["outcome"] == "died":
            print(f"\nYou fell to {result.get('mob_name', 'the enemy')}...")
            death_node = result.get("death_marker", a.get("node_name"))
            BE.apply_death_post_processing(hero, _current_quest_pool(hero), death_node)
            return "died"

        _report_outcome(result)
        if a["type"] == "return_to_town":
            return "town"
        if a["type"] == "visit_trainer":
            return "trainer"


def play(class_name, strategy="food_only", seed=None):
    rng = random.Random(seed)
    mod = M.CARD_SOURCE[class_name]
    max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
    hero = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(1, "town"),
                           bag=[None] * M.BAG_SIZE, locked=[False] * M.BAG_SIZE)
    hero.bag[0] = "food"
    if class_name in M.LEVEL2_PURCHASED_ORDER:
        hero.skill_purchase_order = list(range(len(M.LEVEL2_PURCHASED_ORDER[class_name])))
        rng.shuffle(hero.skill_purchase_order)
    purchase_queue = M._build_purchase_queue(class_name, 0)
    level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
    board = B.BoardState(mode="solo", heroes=[hero], zones={}, level_decks=level_decks)

    print(f"=== {class_name.title()} begins their career ===")
    _do_town(hero, class_name, strategy, purchase_queue, rng)

    while True:
        if hero.corpse_node is not None:
            print(f"\n--- Your corpse lies at {hero.corpse_node} -- forced recovery attempt ---")
            died = BE._resolve_forced_recovery(hero, class_name, _current_quest_pool(hero), board, rng,
                                                M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True,
                                                decide_fn=human_decide_combat)
            if died is not None:
                print(f"\nYou died again attempting recovery...")
                BE.apply_death_post_processing(hero, _current_quest_pool(hero), died["death_node"])
                _do_town(hero, class_name, strategy, purchase_queue, rng)
                if input("\nContinue? [Y/n]: ").strip().lower() == "n":
                    break
                continue
            hero.alive = True
            print("You've recovered your gear.")

        outcome = _do_travel(hero, class_name, board, rng)
        if outcome == "trainer":
            _do_trainer(hero, class_name, purchase_queue)
            continue
        _do_town(hero, class_name, strategy, purchase_queue, rng)
        if input("\nContinue? [Y/n]: ").strip().lower() == "n":
            break

    print(f"\n=== Session ended -- Gold: {hero.gold}  XP: {hero.xp}  Turns: {hero.turns} ===")


def _fmt_hero_status(hero):
    return f"HP {hero.hp:.0f}/{hero.max_hp:.0f}  Gold {hero.gold}  XP {hero.xp}  @ {hero.position[0]}"


def _pass_device(label):
    """The multi-human 'blind simultaneous declaration' approximation (checkpointed 2026-08-23,
    scoping this feature): a single shared terminal can't literally hide information the way a
    real table's simultaneous-and-secret declaration does, so this is the closest practical
    stand-in -- a deliberate pause naming whose turn it is, so the group can enforce "everyone
    else looks away" themselves the same way they'd self-police not peeking at a hidden hand.
    A no-op for the common 1-human-vs-AI case (nothing to hide from AI opponents), only prints
    anything when a second human is actually in the game."""
    print(f"\n{'=' * 50}")
    input(f"Pass the device to {label}. Everyone else, look away, then press Enter...")
    print(f"{'=' * 50}")


def _do_competitive_town(hero, class_name, strategy, purchase_queue, rng, controller, label, human_count):
    """AI branch matches run_competitive_chain's own Town/Trainer heuristic exactly (buy the
    first affordable thing, else leave) -- deliberately not QuestIntelligence or the Purchase
    Queue's own save/skip policy, since this driver isn't trying to reproduce
    run_competitive_chain's bit-for-bit numbers, just its behavior shape, for AI seats a human
    is actually playing against. Dispatches on hero.position's own node marker ("town" vs
    "trainer", checkpointed 2026-08-24) rather than assuming Town -- a hero can arrive at
    either from a previous round's declared return_to_town/visit_trainer."""
    at_trainer = hero.position[1] == "trainer"
    if controller == "ai":
        if at_trainer:
            BE.enter_trainer(hero, class_name)
        else:
            BE.enter_town(hero, class_name, strategy, rng)
        while True:
            actions = BE.get_town_actions(hero, purchase_queue)
            buyable = next((a for a in actions if a["type"] == "buy"), None)
            leave_type = "leave_trainer" if at_trainer else "leave_town"
            chosen = buyable if buyable else next(a for a in actions if a["type"] == leave_type)
            if not BE.apply_town_action(hero, chosen, purchase_queue):
                break
        return
    if human_count > 1:
        _pass_device(label)
    if at_trainer:
        print(f"\n--- {label}'s Trainer turn ---")
        _do_trainer(hero, class_name, purchase_queue)
    else:
        print(f"\n--- {label}'s Town turn ---")
        _do_town(hero, class_name, strategy, purchase_queue, rng)


def _human_field_action(hero, label, board, rng):
    actions = BE.get_travel_actions(hero, board, rng)
    zone_or_border, _node = hero.position
    print(f"\n{label} -- at {zone_or_border}  {_fmt_hero_status(hero)}  Bag: {hero.bag}")
    return _prompt_choice("Declare: ", actions, _fmt_travel_action)


def play_competitive(specs, strategy="food_only", seed=None, max_rounds=200):
    """specs: list of (class_name, controller) pairs, controller in {"human", "ai"}, 2-4
    entries, any class mix -- mirrors run_competitive_chain's own setup (task #65) but replaces
    its all-AI decision-making with a real per-hero controller, human or AI. Covers both this
    session's checkpointed scope answers at once: a single human vs. AI rivals (the common
    case, _pass_device is a no-op) and true local multiplayer (2+ humans, _pass_device actually
    gates each human's turn) -- same code path either way, since declare_for_hero/advance_board
    never cared who supplied an action, only that every hero in board.heroes has one.

    Round structure matches run_competitive_chain's own docstring exactly (Town phase per hero,
    independent and uncontested, THEN one Move-and-declare cycle for the field) -- see that
    function's own docstring for the full reasoning behind each piece (the token-order
    declaration sequencing, the "return_to_town no-op for a Town-bound hero" contract,
    competitive mode's own deliberately-simplified death rule). AI-controlled heroes reuse
    board_engine._choose_field_action verbatim -- the identical decision function
    run_competitive_chain already uses and this session's regression suite already trusts."""
    rng = random.Random(seed)
    n = len(specs)
    class_names_list = [c for c, _ in specs]
    controllers = {i: ctrl for i, (_, ctrl) in enumerate(specs)}
    labels = {i: f"Player {i + 1} ({c.title()}, {ctrl})" for i, (c, ctrl) in enumerate(specs)}
    class_names = dict(enumerate(class_names_list))
    human_count = sum(1 for ctrl in controllers.values() if ctrl == "human")

    heroes = []
    for class_name in class_names_list:
        mod = M.CARD_SOURCE[class_name]
        max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
        hero = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(1, "town"),
                               bag=[None] * M.BAG_SIZE, locked=[False] * M.BAG_SIZE)
        hero.bag[0] = "food"
        if class_name in M.LEVEL2_PURCHASED_ORDER:
            hero.skill_purchase_order = list(range(len(M.LEVEL2_PURCHASED_ORDER[class_name])))
            rng.shuffle(hero.skill_purchase_order)
        heroes.append(hero)
    purchase_queues = {i: M._build_purchase_queue(class_names_list[i], 0) for i in range(n)}
    level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
    board = B.BoardState(mode="competitive", heroes=heroes, zones={}, level_decks=level_decks)

    print(f"=== Competitive session: {', '.join(labels.values())} ===")

    for round_num in range(max_rounds):
        print(f"\n\n######## Round {round_num + 1} ########")
        for hero_idx, hero in enumerate(board.heroes):
            if hero.position[1] in ("town", "trainer"):
                _do_competitive_town(hero, class_names[hero_idx], strategy, purchase_queues[hero_idx], rng,
                                      controllers[hero_idx], labels[hero_idx], human_count)

        field_idxs = [i for i, h in enumerate(board.heroes) if h.position[1] not in ("town", "trainer")]
        quest_pools = {i: (M.LEVEL2_QUESTS if board.heroes[i].xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS)
                       for i in field_idxs}
        claimed_this_round = set()
        decide_fns = {}
        for hero_idx in [i for i in BE._priority_order(board) if i in field_idxs]:
            hero = board.heroes[hero_idx]
            if controllers[hero_idx] == "human":
                if human_count > 1:
                    _pass_device(labels[hero_idx])
                action = _human_field_action(hero, labels[hero_idx], board, rng)
                decide_fns[hero_idx] = human_decide_combat
            else:
                action = BE._choose_field_action(hero_idx, board, class_names, quest_pools, rng, claimed_this_round,
                                                  purchase_queues=purchase_queues)
            if action["type"] == "declare_node":
                claimed_this_round.add(action["node_name"])
            BE.declare_for_hero(board, hero_idx, action)
        for hero_idx in range(n):
            if hero_idx not in field_idxs:
                still_town = board.heroes[hero_idx].position[1] == "town"
                BE.declare_for_hero(board, hero_idx,
                                     {"type": "return_to_town" if still_town else "visit_trainer"})

        if human_count > 1:
            print("\n(All declarations submitted -- resolving the round...)")
        results = BE.advance_board(board, class_names, rng, M.RISK_TOLERANCE_BASE, True, decide_fns=decide_fns)

        for hero_idx in field_idxs:
            hero = board.heroes[hero_idx]
            result = results[hero_idx]
            if result.get("outcome") == "scouted_pull_reveal":
                if controllers[hero_idx] == "human":
                    cand = result["candidates"]
                    print(f"\n{labels[hero_idx]}'s Scouted Pull reveals: 1) {cand[0]}   2) {cand[1]}")
                    while True:
                        pick = input("Which will you face? [1/2]: ").strip()
                        if pick in ("1", "2"):
                            break
                        print("Enter 1 or 2.")
                    picked_mob = cand[0] if pick == "1" else cand[1]
                    result = BE.resolve_border_crossing(hero, class_names[hero_idx], result["border_name"],
                                                          result["target_zone"], picked_mob, rng,
                                                          M.RISK_TOLERANCE_BASE, True,
                                                          decide_fn=human_decide_combat)
                else:
                    picked_mob = rng.choice(result["candidates"])
                    result = BE.resolve_border_crossing(hero, class_names[hero_idx], result["border_name"],
                                                          result["target_zone"], picked_mob, rng,
                                                          M.RISK_TOLERANCE_BASE, True)
                results[hero_idx] = result
            if result.get("outcome") == "died":
                print(f"\n{labels[hero_idx]} died to {result.get('mob_name', 'the enemy')}!")
                BE.apply_competitive_death_post_processing(hero, quest_pools[hero_idx])

        print("\n--- Round results ---")
        for hero_idx in range(n):
            hero = board.heroes[hero_idx]
            r = results.get(hero_idx, {})
            print(f"  {labels[hero_idx]}: {r.get('outcome', '-')}  {_fmt_hero_status(hero)}")

        if human_count > 0:
            if input("\nContinue to next round? [Y/n]: ").strip().lower() == "n":
                break

    print("\n=== Session ended ===")
    for hero_idx in range(n):
        hero = board.heroes[hero_idx]
        print(f"  {labels[hero_idx]}: Gold {hero.gold}  XP {hero.xp}  Turns {hero.turns}")


def _parse_party_spec(entries):
    specs = []
    for entry in entries:
        if ":" not in entry:
            raise SystemExit(f"--party entries must be class:controller, got {entry!r}")
        class_name, controller = entry.split(":", 1)
        if class_name not in M.CARD_SOURCE:
            raise SystemExit(f"unknown class {class_name!r}")
        if controller not in ("human", "ai"):
            raise SystemExit(f"controller must be 'human' or 'ai', got {controller!r}")
        specs.append((class_name, controller))
    if not 2 <= len(specs) <= 4:
        raise SystemExit("--party needs 2-4 entries")
    return specs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class", dest="class_name", choices=list(M.CARD_SOURCE.keys()),
                         help="solo mode: single class")
    parser.add_argument("--party", nargs="+",
                         help="competitive mode: 2-4 entries shaped class:controller, e.g. "
                              "--party warrior:human wizard:ai cleric:ai")
    parser.add_argument("--strategy", default="food_only")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    if args.party:
        play_competitive(_parse_party_spec(args.party), args.strategy, seed=args.seed)
    elif args.class_name:
        play(args.class_name, args.strategy, seed=args.seed)
    else:
        parser.error("either --class (solo) or --party (competitive) is required")


if __name__ == "__main__":
    main()
