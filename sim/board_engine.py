"""
Node-pull and Town-turn declare/resolve mechanisms -- the first two slices of BoardState's
turn loop, deliberately built and checkpointed one at a time (2026-08-21, see
unified-sprouting-aurora.md's Part 3a). Border crossings and cross-zone travel routing are
NOT here yet -- next chunk, its own checkpoint.

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


def resolve_town_turn(hero, class_name, strategy, purchase_queue, purchase_policy, rng):
    """Resolves one full Town turn -- "a hero may do as much business as they want in one
    visit... one turn total per Town visit" (OPEN_QUESTIONS.md's "What a turn is," verbatim).
    Faithful port of _trip_chain's Town bookkeeping (quest turn-in/decay/refill, the
    leaving-town restock, Phase 1 Logistics, Phase 3 Purchase Queue), bundled into a single
    call since all of it happens at one Town stop under BoardState -- the OLD code only split
    it across the tail of one _trip_chain loop iteration (turn-in) and the head of the next
    (restock/pickup/purchases) for implementation convenience, not because they're two
    separate turns. Order matches the old code's own dependency chain exactly: turn-in first
    (so its Gold is available to spend this same stop), then restock, then Logistics, then
    Purchase Queue.

    One real, documented difference from _trip_chain: a brand-new hero there starts already
    holding an active_quests log (drawn before turn 0 even begins) -- here, active_quests
    starts empty and gets bootstrapped by this function's own Phase 1 pickup branch on the
    hero's first Town turn instead. Functionally equivalent (a hero standing in Zone 1, a
    valid quest zone, on their very first turn), just deferred by one explicit turn rather
    than happening before any turn exists, since BoardState has no "before turn 0" concept.

    Mutates hero in place. Returns a dict: {"quests_completed": int, "trainer_turn": bool}."""
    zone_id, _node = hero.position
    pool = M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS
    for loot in pool:
        hero.decay_stage.setdefault(loot, 0)

    quests_completed = 0
    if hero.active_quests:
        still_incomplete = []
        turned_in = []
        for loot in hero.active_quests:
            q = pool[loot]
            collected = M._accessible_count(hero.bag, hero.locked, loot)
            if collected >= q["required"]:
                hero.gold += q["gold_ladder"][min(hero.decay_stage[loot], len(q["gold_ladder"]) - 1)]
                hero.xp += q["base_xp"]
                hero.decay_stage[loot] = 0
                M._remove_loot(hero.bag, hero.locked, loot, collected)
                turned_in.append(loot)
            else:
                hero.decay_stage[loot] = min(hero.decay_stage[loot] + 1, len(q["gold_ladder"]) - 1)
                still_incomplete.append(loot)

        if pool is M.QUESTS:
            hero.active_quests = still_incomplete
        else:
            newly_active = []
            for _ in range(len(turned_in)):
                if not hero.quest_bag:
                    hero.quest_bag = [loot for loot in M.LEVEL2_QUESTS
                                       if loot not in still_incomplete and loot not in newly_active]
                    rng.shuffle(hero.quest_bag)
                newly_active.append(hero.quest_bag.pop(0))
            hero.active_quests = still_incomplete + newly_active
        quests_completed = len(turned_in)

    hero.gold = M._leaving_town_setup(strategy, hero.bag, hero.locked, hero.gold)

    # Re-read: xp may have just risen from a quest turned in above, crossing LEVEL2_XP_THRESHOLD
    # mid-call -- the same live-lookup discipline run_one_trip's own win_rate uses.
    pool = M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS
    valid_quest_zones = M.LEVEL2_QUEST_ZONES if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.LEVEL1_QUEST_ZONES
    if not hero.active_quests and zone_id in valid_quest_zones:
        hero.active_quests = rng.sample(list(pool.keys()), min(M.ACTIVE_QUEST_COUNT, len(pool)))
        if pool is M.LEVEL2_QUESTS:
            hero.acquired.add("started_l2_quests")

    mandatory_turn = False
    if (zone_id in M.TRAINER_ZONES and hero.xp >= M.LEVEL2_XP_THRESHOLD
            and class_name in M.LEVEL2_MANDATORY and "mandatory" not in hero.acquired):
        hero.acquired.add("mandatory")
        mandatory_turn = True

    hero.gold, purchase_trainer_turn = M._walk_purchase_queue(
        purchase_queue, hero.acquired, hero.bag, hero.locked, zone_id, hero.gold, purchase_policy)

    return {"quests_completed": quests_completed, "trainer_turn": mandatory_turn or purchase_trainer_turn}
