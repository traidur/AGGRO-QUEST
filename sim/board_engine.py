"""
Node-pull declare/resolve mechanism -- the FIRST slice of BoardState's turn loop, deliberately
scoped to just "hero stands in an already-occupied Zone, sees dealt Nodes, declares one,
resolves the pull" (checkpointed 2026-08-21, see unified-sprouting-aurora.md's Part 3a).
Town visits, Border crossings, the Purchase Queue, and XP/leveling are NOT here -- those are
later chunks, each getting their own checkpoint the same way this one did.

Reuses macro_sim.py's own helpers directly rather than reimplementing them (_pull_exceeds_risk,
_is_potion_slot, _add_loot, _accessible_count, _engine_pull, POTION_HEAL, NODES, etc.) --
per the plan, "every existing helper... stays exactly as-is, becoming the guts of
QuestIntelligence.decide_macro rather than being rewritten." resolve_node_pull below is a
faithful line-for-line port of run_one_trip's own per-pull block (its risk-gate/consumable/
combat_engine-pull/win-loss-bookkeeping shape), NOT a reinvention -- verified against it
directly by sim/verify_board_engine.py's mocked-deck replay check.

**Why "declined" is a new outcome this file introduces that run_one_trip never had:** the old
code always had a real mob_name once it decided to pull (risk-checked before or after a
consumable, but a pull always eventually happens once committed). Under BoardState, a hero can
be blocked from pulling the ONE Node their active quest needs because that Node is currently
Spice-dealt (an inert placeholder, see board_state.py) -- there's no equivalent "the mob I need
isn't safe to fight and I have nothing to make it safer" branch in the old code that maps to
"the thing I need to fight isn't a fight yet." choose_node_to_declare simply skips a
Spice-dealt Node in the routing preference, same as it would skip a Node that doesn't serve any
incomplete quest.
"""
import board_state as B
import macro_sim as M


def legal_node_declares(zone_board):
    """Nodes in this Zone whose dealt card is a real, fightable mob right now -- excludes
    anything currently Spice-dealt (see board_state.SPICE's own docstring: no mechanic exists
    yet for declaring one)."""
    return [node_name for node_name, card in zone_board.dealt.items() if not B.is_spice(card)]


def choose_node_to_declare(hero, zone_board, quest_pool):
    """Which dealt Node in this Zone to pull at this turn -- mirrors run_one_trip's own
    quest-routing preference (whichever incomplete quest's Node is present) exactly, restricted
    to Nodes actually dealt in THIS Zone (cross-zone routing is a later chunk) and skipping any
    Node currently Spice-dealt. Returns a Node name, or None if nothing declarable here serves
    an incomplete quest right now."""
    incomplete = [loot for loot in hero.active_quests
                  if M._accessible_count(hero.bag, hero.locked, loot) < quest_pool[loot]["required"]]
    for loot in incomplete:
        node_name = next((n for n, (tier, l) in M.NODES.items() if l == loot and n in zone_board.dealt), None)
        if node_name is not None and not B.is_spice(zone_board.dealt[node_name]):
            return node_name
    return None


def resolve_node_pull(hero, class_name, node_name, mob_name, quest_pool, rng,
                       risk_tolerance, risk_tolerance_base, risk_only_as_last_resort):
    """Resolves one declared Node pull for a single hero -- faithful port of run_one_trip's own
    per-pull block: fluid risk-tolerance gate (higher tolerance only when this pull, if won,
    would complete the quest being pursued), consumable use if the gate trips, the actual pull
    via macro_sim._engine_pull (the same combat_engine-backed path run_one_trip itself now
    uses), and win/loss Gold + loot bookkeeping. Mutates hero in place. Returns a dict:
    {"outcome": "win"/"flee"/"died"/"declined"/"no_room", "mob_name": ...}."""
    mod = M.CARD_SOURCE[class_name]
    has_stance = M.HAS_STANCE[class_name]
    tier, loot_name = M.NODES[node_name]
    pattern, mob_hp = M._pattern_hp_for_mob(class_name, mob_name)

    one_pull_from_done = (M._accessible_count(hero.bag, hero.locked, loot_name)
                           == quest_pool[loot_name]["required"] - 1)
    if risk_only_as_last_resort:
        has_consumable = any(not hero.locked[i] and (hero.bag[i] == "food" or M._is_potion_slot(hero.bag[i]))
                              for i in range(len(hero.bag)))
        worth_the_risk = one_pull_from_done and not has_consumable
    else:
        worth_the_risk = one_pull_from_done
    effective_risk_tolerance = risk_tolerance if worth_the_risk else risk_tolerance_base

    if M._pull_exceeds_risk(mod, has_stance, mob_name, class_name, hero.hp, effective_risk_tolerance,
                             mob_pattern_hp=(pattern, mob_hp)):
        consumed = None
        for i, slot in enumerate(hero.bag):
            if hero.locked[i]:
                continue
            if slot == "food":
                hero.hp = hero.max_hp
                hero.bag[i] = None
                M._close_active_loot_slot(hero.bag, hero.locked)
                consumed = "food"
                break
            if M._is_potion_slot(slot):
                hero.hp = min(hero.max_hp, hero.hp + M.POTION_HEAL)
                remaining = slot[1] - 1
                hero.bag[i] = ("potion", remaining) if remaining > 0 else None
                consumed = "potion"
                break
        if consumed:
            hero.consumables_used[consumed] += 1
            if M._pull_exceeds_risk(mod, has_stance, mob_name, class_name, hero.hp, effective_risk_tolerance,
                                     mob_pattern_hp=(pattern, mob_hp)):
                return {"outcome": "declined", "mob_name": mob_name}
        else:
            return {"outcome": "declined", "mob_name": mob_name}

    hand = rng.choice(mod.ALL_HANDS)
    win, final_hp, final_rounds = M._engine_pull(class_name, mob_name, hand, pattern, mob_hp, hero.hp)
    hero.hp = final_hp

    if hero.hp <= 0:
        # Clamped to exactly 0, matching run_one_trip's own death result (_make_result(...,
        # hp=0) -- hardcoded, not whatever raw negative value the pull actually produced.
        hero.hp = 0
        hero.alive = False
        return {"outcome": "died", "mob_name": mob_name}

    if win:
        hero.gold += 1
        if not M._add_loot(hero.bag, hero.locked, loot_name):
            return {"outcome": "no_room", "mob_name": mob_name}
        return {"outcome": "win", "mob_name": mob_name}
    return {"outcome": "flee", "mob_name": mob_name}
