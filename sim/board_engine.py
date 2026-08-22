"""
Node-pull, Town-turn, Border-crossing, and travel-routing declare/resolve mechanisms -- four
slices of BoardState's turn loop, deliberately built and checkpointed one at a time
(2026-08-21, see unified-sprouting-aurora.md's Part 3a). Not yet built: stitching all four
into one cohesive turn-by-turn driver (the advance_board barrier), and wiring the real
LevelDeck into Scouted Pull / choose_node_to_declare (both still source mobs via macro_sim's
old rng-based functions, kept that way deliberately so each piece stayed Layer-1-verifiable
against run_one_trip -- see each function's own docstring).

**Leveled-kit wiring (2026-08-21, fixed after being missed in the first pass):**
resolve_node_pull, resolve_border_crossing, and decide_travel's own risk-gate check all wrap
their combat-touching work in `with LV.leveled_kit(mod, _level2_swaps_for(class_name,
hero.acquired)):` -- matching _trip_chain's own `with LV.leveled_kit(...): run_one_trip(...)`
scope, which covers risk-gate checks and hand draws, not just the final pull. Without this, a
BoardState hero could buy every Level 2 upgrade in Town and never actually fight with the
upgraded cards -- caught by taking stock of what was built, not by a test (see
verify_board_engine_leveled_kit.py, the one suite that actually exercises a non-empty swap;
every other verify_board_engine*.py suite runs with an empty hero.acquired, where leveled_kit
is a documented no-op, so they couldn't have caught this).

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
import condensed_trip as T
import leveling_validation as LV
import macro_sim as M
from board_state import HeroBoardState

# tier string (macro_sim's own ZONE_TIER values) -> level deck key (board_state.LevelDeck's
# own numbering, 1 or 2). Two independently-declared vocabularies for the same underlying
# concept -- this is the one place they need to line up.
TIER_TO_LEVEL = {"standard": 1, M.LEVEL2_TIER: 2}


def _level2_swaps_for(class_name, acquired):
    """The same level2_swaps dict _trip_chain computes fresh every trip, right before its own
    `with LV.leveled_kit(...): result = run_one_trip(...)` block -- factored out here so every
    combat-touching resolver (resolve_node_pull, resolve_border_crossing, and decide_travel's
    own risk-gate check) can wrap itself in the identical context. Old code's leveled_kit scope
    covers the ENTIRE run_one_trip call for a trip -- risk-gate checks, hand draws, and pull
    resolution all read the leveled CARDS/DECK/ALL_HANDS, not just the final combat_engine
    call -- so every one of those call sites needs this same wrapping, not just the pull
    itself. Safe to recompute and re-enter once per resolver call rather than once per whole
    trip: hero.acquired only changes during Town turns, never mid-trip, so this dict is
    identical across every pull within one trip either way, and leveled_kit's own contract
    (mutate-then-restore CARDS/DECK/ALL_HANDS, no persistent state) makes repeated re-entry
    with the same swaps a no-op layered on a no-op. Empty for a class with no Level 2 slate
    yet, or before the mandatory upgrade has been collected -- leveled_kit with an empty swap
    dict is itself a harmless no-op (verified in leveling_validation.py's own docstring)."""
    swaps = {}
    if class_name in M.LEVEL2_MANDATORY and "mandatory" in acquired:
        _, old_name, new_name, new_card = M.LEVEL2_MANDATORY[class_name]
        swaps[old_name] = (new_name, new_card)
        for i in range(len(M.LEVEL2_PURCHASED_ORDER[class_name])):
            if f"skill_{i}" in acquired:
                old_name, new_name, new_card = M.LEVEL2_PURCHASED_ORDER[class_name][i]
                swaps[old_name] = (new_name, new_card)
    return swaps


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

    # Old code's `with LV.leveled_kit(...): result = run_one_trip(...)` scope covers the
    # ENTIRE trip -- risk-gate checks and hand draws read the leveled CARDS/DECK/ALL_HANDS
    # too, not just the final combat_engine call -- so this wraps everything from here down,
    # not just the pull itself. See _level2_swaps_for's own docstring for why re-entering this
    # once per pull (rather than once per whole trip) is safe.
    with LV.leveled_kit(mod, _level2_swaps_for(class_name, hero.acquired)):
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
        # One turn -- OPEN_QUESTIONS.md's "What a turn is" (locked): "Quest node: one pull is
        # one turn." A "declined" pull (returned above, before reaching here) does NOT count --
        # nothing was actually attempted at the table.
        hero.turns += 1

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

    Mutates hero in place. Returns a dict: {"quests_completed": int, "trainer_turn": bool,
    "gold_after_turnin": int}. gold_after_turnin is hero.gold's value right after turn-in,
    before restock/Purchase-Queue spend it further this same call -- exposed purely for
    external observability/verification (e.g. a UI wanting to show "you earned X from
    quests" separately from "then spent Y at the shop"), not used internally."""
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

    gold_after_turnin = hero.gold
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

    # One turn, always -- "a hero may do as much business as they want in one visit... One
    # turn total per Town visit, no matter how much gets done there" (OPEN_QUESTIONS.md,
    # locked, verbatim). Unconditional: even a Town call that turns in nothing and buys
    # nothing still counts (the hero still visited).
    hero.turns += 1

    return {"quests_completed": quests_completed, "trainer_turn": mandatory_turn or purchase_trainer_turn,
            "gold_after_turnin": gold_after_turnin}


def resolve_border_crossing(hero, class_name, border_name, target_zone, mob_name, rng,
                             risk_tolerance_base, risk_only_as_last_resort):
    """Resolves one Scouted Pull toll crossing -- faithful port of run_one_trip's own
    _cross_to. mob_name is supplied by the caller, not sourced internally (mirrors
    resolve_node_pull's own shape) -- today's real caller uses macro_sim._scouted_pull_mob
    (the OLD rng-based 2-draw, kept for Layer-1 verifiability against run_one_trip, see this
    module's own docstring), but resolve_border_crossing itself doesn't know or care where
    mob_name came from, so swapping in the real LevelDeck's 2-card draw later is a pure
    caller-side change, not a rewrite here.

    Always uses risk_tolerance_base (never the higher "fluid risk" tolerance Node-pulls get
    when one pull from completing a quest) -- a Border crossing is never itself a
    quest-completing action, matching the old code's own asymmetry there. Also unlike
    resolve_node_pull: after a consumable is used, old _cross_to does NOT re-check risk and
    cannot decline -- once a crossing is committed to, the pull always happens, matching that
    faithfully (no "declined" outcome exists for this function).

    On success, hero.position becomes (border_name, None) -- a Border Node is its own
    physical position, not part of either Zone it connects (OPEN_QUESTIONS.md's "Border
    Nodes and Scouted Pull" entry). On death, position is left untouched (the hero hadn't
    actually left their origin Zone when the toll pull happened) and the returned dict
    carries a death_marker string in the same "border:{border_name}:{origin_zone}:
    {target_zone}" shape run_one_trip's own death_node encoding uses, so a later corpse-
    recovery chunk can parse it identically.

    Mutates hero in place. Returns a dict: {"outcome": "win"/"flee"/"died", "mob_name": ...,
    "death_marker": ... (died only)}."""
    mod = M.CARD_SOURCE[class_name]
    has_stance = M.HAS_STANCE[class_name]
    origin_zone, _node = hero.position

    # Same leveled_kit scope reasoning as resolve_node_pull -- old code's per-trip
    # `with LV.leveled_kit(...): run_one_trip(...)` covers this crossing's risk-gate check and
    # hand draw too, not just the final pull.
    with LV.leveled_kit(mod, _level2_swaps_for(class_name, hero.acquired)):
        pattern, mob_hp = M._pattern_hp_for_mob(class_name, mob_name)

        if risk_only_as_last_resort:
            has_consumable = any(not hero.locked[i] and (hero.bag[i] == "food" or M._is_potion_slot(hero.bag[i]))
                                  for i in range(len(hero.bag)))
        else:
            has_consumable = False

        if (M._pull_exceeds_risk(mod, has_stance, mob_name, class_name, hero.hp, risk_tolerance_base,
                                  mob_pattern_hp=(pattern, mob_hp))
                and has_consumable):
            for i, slot in enumerate(hero.bag):
                if hero.locked[i]:
                    continue
                if slot == "food":
                    hero.hp = hero.max_hp
                    hero.bag[i] = None
                    M._close_active_loot_slot(hero.bag, hero.locked)
                    hero.consumables_used["food"] += 1
                    break
                if M._is_potion_slot(slot):
                    hero.hp = min(hero.max_hp, hero.hp + M.POTION_HEAL)
                    remaining = slot[1] - 1
                    hero.bag[i] = ("potion", remaining) if remaining > 0 else None
                    hero.consumables_used["potion"] += 1
                    break

        hand = rng.choice(mod.ALL_HANDS)
        win, final_hp, final_rounds = M._engine_pull(class_name, mob_name, hand, pattern, mob_hp, hero.hp)
        hero.hp = final_hp
        # One turn -- "Border Node: one turn, same as any other node -- the Scouted Pull toll
        # pull is the action taken there" (OPEN_QUESTIONS.md, locked). Unlike resolve_node_pull,
        # a crossing has no "declined" outcome to exclude -- every call here is a real turn.
        hero.turns += 1

        if hero.hp <= 0:
            hero.hp = 0
            hero.alive = False
            death_marker = f"border:{border_name}:{origin_zone}:{target_zone}"
            return {"outcome": "died", "mob_name": mob_name, "death_marker": death_marker}

        hero.position = (border_name, None)
        if win:
            hero.gold += 1
        return {"outcome": "win" if win else "flee", "mob_name": mob_name}


def decide_travel(hero, class_name, quest_pool, fallback_target_zones, risk_tolerance_base,
                   risk_only_as_last_resort):
    """Decides what a hero does THIS turn when they're not already standing somewhere with a
    dealt Node to declare -- faithful port of run_one_trip's own routing block (target-zone
    selection, bag-deadlock consumable use, Flight Path, Border-crossing risk gate). Does NOT
    resolve a pull or a crossing itself -- returns an action descriptor for the caller to act
    on next:
      {"action": "arrived", "zone_id": ..., "node_name": ...} -- target reached this turn
          (Flight Path already applied to hero.position/hero.gold if that's how it got here).
          node_name is None if there were no active quests to route toward at all (arrived at
          a fallback zone with nothing to pull) -- old code's own "travel with zero active
          quests costs no turn, loop immediately" rule (a bare `continue`, no _engine_pull
          call) means a caller seeing node_name=None should call decide_travel again rather
          than counting this as a resolved turn.
      {"action": "cross_border", "border_name": ..., "target_zone": ...} -- attempt this
          crossing via resolve_border_crossing next (that IS its own turn).
      {"action": "end_trip"} -- nothing left to do (quests already satisfied, bag deadlocked
          with no consumable, or a crossing judged not worth the risk with no consumable to
          back it up).

    Corpse-recovery routing (run_one_trip's pending_recovery branches) is NOT covered here --
    death/recovery handling isn't built yet, matching resolve_node_pull/resolve_border_
    crossing's own scope notes. Mutates hero in place (position/gold/hp/bag/consumables_used,
    depending on which branch fires)."""
    mod = M.CARD_SOURCE[class_name]
    has_stance = M.HAS_STANCE[class_name]
    zone_id, _node = hero.position

    if not hero.active_quests:
        if isinstance(zone_id, int) and zone_id in fallback_target_zones:
            return {"action": "end_trip"}
        target_zone = min(fallback_target_zones, key=lambda z: M._hop_distance(zone_id, z))
        node_name = None
    else:
        incomplete = [loot for loot in hero.active_quests
                      if M._accessible_count(hero.bag, hero.locked, loot) < quest_pool[loot]["required"]]
        if not incomplete:
            return {"action": "end_trip"}

        if not M._bag_has_room(hero.bag, hero.locked):
            food_index = next((i for i, s in enumerate(hero.bag) if not hero.locked[i] and s == "food"), None)
            if food_index is not None:
                hero.hp = hero.max_hp
                hero.bag[food_index] = None
                hero.consumables_used["food"] += 1
            else:
                potion_index = next((i for i, s in enumerate(hero.bag)
                                      if not hero.locked[i] and M._is_potion_slot(s)), None)
                if potion_index is None:
                    return {"action": "end_trip"}
                hero.hp = min(hero.max_hp, hero.hp + M.POTION_HEAL)
                remaining = hero.bag[potion_index][1] - 1
                hero.bag[potion_index] = ("potion", remaining) if remaining > 0 else None
                hero.consumables_used["potion"] += 1

        same_zone_first = sorted(incomplete, key=lambda loot: M._hop_distance(
            zone_id, M.NODE_ZONE[next(n for n, (t, l) in M.NODES.items() if l == loot)]))
        node_name = next(n for n, (tier, loot) in M.NODES.items() if loot == same_zone_first[0])
        target_zone = M.NODE_ZONE[node_name]

    can_fly = (isinstance(zone_id, int) and zone_id in M.FLIGHT_PATH_ZONES
               and target_zone in M.FLIGHT_PATH_ZONES and zone_id != target_zone
               and hero.gold >= M.FLIGHT_PATH_COST)
    if can_fly:
        hero.gold -= M.FLIGHT_PATH_COST
        hero.position = (target_zone, None)
        return {"action": "arrived", "zone_id": target_zone, "node_name": node_name}

    if not M._reachable_free(target_zone, zone_id):
        border_name, next_zone = M._next_border_toward(zone_id, target_zone)
        if risk_only_as_last_resort:
            has_consumable = any(not hero.locked[i] and (hero.bag[i] == "food" or M._is_potion_slot(hero.bag[i]))
                                  for i in range(len(hero.bag)))
        else:
            has_consumable = False
        # Same leveled_kit scope reasoning as resolve_node_pull/resolve_border_crossing --
        # this risk-gate check reads mod.ALL_HANDS (via _best_case_mob/_pull_exceeds_risk)
        # too, inside old code's per-trip leveled_kit scope.
        with LV.leveled_kit(mod, _level2_swaps_for(class_name, hero.acquired)):
            best_mob = M._best_case_mob(class_name, M.ZONE_TIER[next_zone])
            exceeds = M._pull_exceeds_risk(mod, has_stance, best_mob, class_name, hero.hp, risk_tolerance_base)
        if exceeds and not has_consumable:
            return {"action": "end_trip"}
        return {"action": "cross_border", "border_name": border_name, "target_zone": next_zone}

    hero.position = (target_zone, None)
    return {"action": "arrived", "zone_id": target_zone, "node_name": node_name}


def _best_scouted_candidate(class_name, candidates):
    """Picks whichever candidate mob has the lower cost% for this class -- the exact
    comparison macro_sim._scouted_pull_mob already uses (shares its cache,
    _scouted_pull_costpct_cache, so no duplicated cost computation between the old rng-based
    path and this one), decoupled from HOW the candidates were drawn."""
    cache = M._scouted_pull_costpct_cache.setdefault(class_name, {})
    mod = M.CARD_SOURCE[class_name]
    has_stance = M.HAS_STANCE[class_name]
    max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
    best_mob, best_cost = None, None
    for mob_name in candidates:
        if mob_name not in cache:
            pattern, mob_hp = M._pattern_hp_for_mob(class_name, mob_name)
            total_cost = 0.0
            for hand in mod.ALL_HANDS:
                seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, pattern, mob_hp, max_hp)
                total_cost += max_hp - hp_left
            cache[mob_name] = 100 * (total_cost / len(mod.ALL_HANDS)) / max_hp
        cost = cache[mob_name]
        if best_cost is None or cost < best_cost:
            best_mob, best_cost = mob_name, cost
    return best_mob


def scouted_pull_from_deck(class_name, level_deck, rng):
    """Real Scouted Pull, replacing macro_sim._scouted_pull_mob's independent rng.choices
    2-draw with an actual draw from the shared level deck -- checkpointed 2026-08-22. Draws
    until 2 real (non-Spice) mob cards are gathered, discarding every card drawn along the
    way -- Spice has no combat mechanic yet, so a Spice draw is simply skipped and discarded,
    not treated as a candidate and not reshuffled back in (matches the locked "cards go to
    discard" rule; drawing again on a Spice hit was checkpointed directly rather than assumed
    -- the alternative of treating Spice as an automatic-loss candidate or forcing the OTHER
    drawn card was considered and rejected). Reveals both real candidates and picks whichever
    has the lower cost% for this class via _best_scouted_candidate."""
    candidates = []
    while len(candidates) < 2:
        card = level_deck.draw(rng)
        level_deck.discard(card)
        if not B.is_spice(card):
            candidates.append(card)
    return _best_scouted_candidate(class_name, candidates)


def _nodes_in_zone(zone_id):
    return [n for n in M.NODES if M.NODE_ZONE[n] == zone_id]


def run_solo_trip(hero, class_name, quest_pool, fallback_target_zones, board, rng,
                   risk_tolerance, risk_tolerance_base, risk_only_as_last_resort):
    """One full field trip -- matches run_one_trip's own scope -- driven by decide_travel plus
    resolve_node_pull/resolve_border_crossing. board is a board_state.BoardState (zones +
    level_decks) -- both Border crossings (via scouted_pull_from_deck) and Node-pulls (via
    Deal + choose_node_to_declare) now source their mob from the REAL level deck, not
    independent rng draws. This means run_solo_trip/run_solo_chain are no longer bit-for-bit
    comparable against _trip_chain at all (a real deck is a structurally different random
    process than independent rng.choices, same reasoning as every other real-deck swap this
    session) -- verified by aggregate stats instead (see verify_board_engine_scouted_pull.py
    and verify_board_engine_node_deal.py).

    Node-pull mechanics, checkpointed 2026-08-22: every turn spent in a Zone gets a FULL,
    unconditional Deal to every one of that Zone's Nodes (OPEN_QUESTIONS.md's own words: "a
    full refresh every turn, not a partial one") -- not just once on first entry -- followed
    by an end-of-turn Discard of everything dealt, played or not ("nothing persists into next
    turn"). choose_node_to_declare picks which of the freshly-dealt Nodes to pull (already
    built to skip a Spice-dealt Node in favor of the next incomplete quest, see its own
    docstring) -- if NOTHING declarable exists this turn (every relevant Node came up Spice,
    or nothing here serves an incomplete quest despite decide_travel routing here), the trip
    ends, matching resolve_node_pull's own "declined" shape (there's no equivalent old-code
    branch for "the thing I need to fight isn't a fight yet").

    Mutates hero and board in place. Returns True if the hero is still alive when the trip
    ends (quests exhausted, or a crossing/pull declined), False if they died this trip.
    Corpse recovery is explicitly NOT handled -- a caller sees hero.alive=False and hero.
    position/hp exactly as they were the instant of death; respawn/corpse-lock bookkeeping is
    a separate, later chunk (matching every other resolver's same scope boundary)."""
    # HP does NOT carry across trips -- run_one_trip's own very first line is `hp = max_hp`,
    # unconditional, every trip (implicit "resting" at Town between excursions; HP only
    # carries across PULLS within one trip, never across trip boundaries). Missing this was a
    # real bug, not a design choice -- caught via a live divergence against _trip_chain
    # (trip 2's first pull showed hp=18 in the old code, hp=2 -- carried over from trip 1's
    # ending wounds -- in this driver, cascading into every downstream decision that trip).
    hero.hp = hero.max_hp
    while True:
        action = decide_travel(hero, class_name, quest_pool, fallback_target_zones,
                                risk_tolerance_base, risk_only_as_last_resort)
        if action["action"] == "end_trip":
            return hero.alive

        if action["action"] == "cross_border":
            tier = M.ZONE_TIER[action["target_zone"]]
            level_deck = board.level_decks[TIER_TO_LEVEL[tier]]
            mob_name = scouted_pull_from_deck(class_name, level_deck, rng)
            outcome = resolve_border_crossing(hero, class_name, action["border_name"], action["target_zone"],
                                               mob_name, rng, risk_tolerance_base, risk_only_as_last_resort)
            if outcome["outcome"] == "died":
                return False
            continue

        # action["action"] == "arrived"
        if action["node_name"] is None:
            continue  # traveled with zero active quests -- nothing to pull for, loop
                      # re-evaluates fresh (matches run_one_trip's own bare `continue` here)

        zone_id = action["zone_id"]
        level = TIER_TO_LEVEL[M.ZONE_TIER[zone_id]]
        node_names = _nodes_in_zone(zone_id)
        B.deal_zone(board, zone_id, level, node_names, rng)
        zone_board = board.zones[zone_id]

        node_name = choose_node_to_declare(hero, zone_board, quest_pool)
        if node_name is None:
            B.discard_zone(board, zone_id, level)
            return hero.alive  # nothing declarable this turn -- see docstring

        mob_name = zone_board.dealt[node_name]
        outcome = resolve_node_pull(hero, class_name, node_name, mob_name, quest_pool, rng,
                                     risk_tolerance, risk_tolerance_base, risk_only_as_last_resort)
        B.discard_zone(board, zone_id, level)  # end-of-turn cleanup regardless of outcome
        if outcome["outcome"] == "died":
            return False
        if outcome["outcome"] in ("declined", "no_room"):
            # Matches run_one_trip's own behavior exactly: a declined pull (too risky, no
            # consumable left) or a bag-deadlock fallback both end the trip right there
            # (`return _make_result(completed=False, ...)`), they don't just skip this one
            # Node and keep going. Missing this check was a real bug, not a design choice --
            # decide_travel would otherwise see the identical hero state next iteration and
            # make the identical decision forever (caught via a genuine hang in
            # verify_board_engine_solo_chain.py, not by reasoning about it in advance).
            return hero.alive
        # win/flee just loop back to decide_travel again


def run_solo_chain(class_name, strategy, rng, chain_trips, risk_tolerance=M.RISK_TOLERANCE,
                    risk_tolerance_base=M.RISK_TOLERANCE_BASE, risk_only_as_last_resort=True,
                    purchase_policy="save", bag_queue_position=0):
    """Chains solo trips together -- the BoardState-driven equivalent of _trip_chain.

    Structured as [chain-init resolve_town_turn] then, per trip, [run_solo_trip] then
    [resolve_town_turn] -- NOT [resolve_town_turn] then [run_solo_trip] the way an earlier
    version of this function had it. That ordering had a real bug: every trip's OWN turn-in
    only ever happened at the START of the FOLLOWING resolve_town_turn call, which meant the
    very last trip's turn-in reward never got flushed at all (there's no trip after it to
    trigger it) -- caught via a live comparison against _trip_chain showing every trip
    missing its own gold/xp/quests_completed, not by reasoning about it in advance.

    Because resolve_town_turn bundles turn-in(trip N) with shopping(trip N+1) into one call
    (see its own docstring for why that's the correct real-Town-visit model), a clean yield
    for trip N needs pieces from TWO different resolve_town_turn calls: quests_completed and
    gold_after_turnin from the call that just ran (turnin(N)), but trainer_turn from the
    PREVIOUS call (shopping(N), which happened before trip N's own field excursion, not
    after it) -- tracked via prev_trainer_turn across loop iterations.

    Yields (trip_num, alive, gold, xp, quests_completed, trainer_turn, turns) per trip. turns
    is hero.turns, the cumulative real-turn count (OPEN_QUESTIONS.md's "What a turn is,"
    locked) -- "trips" is NOT a comparable cross-class/cross-run unit (a trip's own length
    varies wildly by class and luck, the same reason macro_sim.decay_stress_test computes its
    own gold_per_turn instead of reporting a raw per-trip figure); this field is what a caller
    should actually divide by for any gold/turn or xp/turn comparison, not trip_num.

    Death handling is a stub -- the chain simply stops without calling resolve_town_turn
    again (a dead hero doesn't do Town business), no respawn/corpse-recovery yet (a separate
    later chunk); the final yielded tuple has alive=False and gold/xp/quests_completed=0/
    unchanged/0, matching _trip_chain's own death-branch shape (it doesn't touch gold/xp and
    leaves quests_completed_this_trip at its initialized 0 on a death trip either)."""
    mod = M.CARD_SOURCE[class_name]
    max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
    hero = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(1, "town"),
                           bag=[None] * M.BAG_SIZE, locked=[False] * M.BAG_SIZE)
    hero.bag[0] = "food"  # matches _trip_chain's own starting loadout
    purchase_queue = M._build_purchase_queue(class_name, bag_queue_position)
    level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
    board = B.BoardState(mode="solo", heroes=[hero], zones={}, level_decks=level_decks)

    # Chain-init Town moment: picks up the initial active_quests log (nothing to turn in yet,
    # matching _trip_chain's own pre-loop `active_quests = rng.sample(...)`).
    init_result = resolve_town_turn(hero, class_name, strategy, purchase_queue, purchase_policy, rng)
    prev_trainer_turn = init_result["trainer_turn"]

    for trip_num in range(1, chain_trips + 1):
        pending_mandatory = (class_name in M.LEVEL2_MANDATORY and hero.xp >= M.LEVEL2_XP_THRESHOLD
                              and "mandatory" not in hero.acquired)
        valid_quest_zones = M.LEVEL2_QUEST_ZONES if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.LEVEL1_QUEST_ZONES
        fallback_target_zones = M.TRAINER_ZONES if pending_mandatory else valid_quest_zones
        quest_pool = M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS

        alive = run_solo_trip(hero, class_name, quest_pool, fallback_target_zones, board, rng,
                               risk_tolerance, risk_tolerance_base, risk_only_as_last_resort)
        if not alive:
            # trainer_turn here is the shopping that happened BEFORE this trip started (same
            # as any other trip -- _trip_chain computes trainer_turn_this_trip once at the top
            # of its iteration and yields it unconditionally at the bottom, regardless of how
            # the trip itself ends), not hardcoded False -- caught via a live divergence, a
            # death trip preceded by a real purchase showed trainer_turn=True in _trip_chain.
            yield (trip_num, False, hero.gold, hero.xp, 0, prev_trainer_turn, hero.turns)
            return

        town_result = resolve_town_turn(hero, class_name, strategy, purchase_queue, purchase_policy, rng)
        yield (trip_num, True, town_result["gold_after_turnin"], hero.xp,
               town_result["quests_completed"], prev_trainer_turn, hero.turns)
        prev_trainer_turn = town_result["trainer_turn"]
