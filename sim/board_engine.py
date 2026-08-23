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
                       risk_tolerance, risk_tolerance_base, risk_only_as_last_resort,
                       suppress_loot=False):
    """Resolves one declared Node pull for a single hero -- faithful port of run_one_trip's own
    per-pull block: fluid risk-tolerance gate (higher tolerance only when this pull, if won,
    would complete the quest being pursued), consumable use if the gate trips, the actual pull
    via macro_sim._engine_pull (the same combat_engine-backed path run_one_trip itself now
    uses), and win/loss Gold + loot bookkeeping. Mutates hero in place. Returns a dict:
    {"outcome": "win"/"flee"/"died"/"declined"/"no_room", "mob_name": ...}.

    suppress_loot=True is for corpse-recovery pulls only ("a recovery pull earns no loot,
    regardless of outcome" -- run_one_trip's own comment, verbatim) -- matches the OLD code's
    exact mechanism (setting loot_name=None before this whole block runs) in both of its real
    effects: no loot is granted on a win, AND the fluid risk-tolerance bonus never applies
    (old code's own guard is `one_pull_from_done = loot_name is not None and ...` -- a
    recovery pull can never be "one pull from completing a quest" since it isn't pursuing one
    at all)."""
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

        # loot_name may not be a key in quest_pool at all -- quest_pool is picked per-trip by
        # the hero's own XP level, but a Node's loot tier is a fixed property of its Zone
        # ("never the hero's XP", macro_sim.py's own NODES comment). Under the old
        # decide_travel-only routing this never mismatched (fallback_target_zones kept a low-
        # level hero out of high-tier Zones entirely), but get_travel_actions/apply_travel_action
        # deliberately show every reachable Zone regardless of level -- a human can walk into a
        # Zone whose Node loot isn't in their current pool at all. In that case this pull simply
        # isn't "one pull from completing a quest" (it can't be pursuing a quest for loot outside
        # its own pool), not a crash.
        one_pull_from_done = (not suppress_loot and loot_name in quest_pool
                               and M._accessible_count(hero.bag, hero.locked, loot_name)
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
                    consumed = "food"
                    break
                if M._is_potion_slot(slot):
                    hero.hp = min(hero.max_hp, hero.hp + M.POTION_HEAL)
                    M._remove_item(hero.bag, hero.locked, "potion", 1)
                    consumed = "potion"
                    break
            if consumed:
                hero.consumables_used[consumed] += 1
                if M._pull_exceeds_risk(mod, has_stance, mob_name, class_name, hero.hp, effective_risk_tolerance,
                                         mob_pattern_hp=(pattern, mob_hp)):
                    return {"outcome": "declined", "mob_name": mob_name}
            else:
                return {"outcome": "declined", "mob_name": mob_name}

        return _pull_and_resolve(hero, class_name, mod, mob_name, loot_name, rng, suppress_loot)


def _pull_and_resolve(hero, class_name, mod, mob_name, loot_name, rng, suppress_loot):
    """Shared tail of resolve_node_pull and commit_node_pull -- draws a hand, runs the actual
    combat_engine pull, and resolves win/loss/loot bookkeeping. Must be called from inside an
    already-open LV.leveled_kit(...) scope (both callers open one for their own risk-gate/
    hand-draw work). Factored out 2026-08-22 so the AI-automatic risk-gated path and the
    human-facing unconditional-commit path can't drift apart on the one piece they genuinely
    share -- only what happens BEFORE the pull differs between them.

    Mutates hero in place. Returns {"outcome": "win"/"flee"/"died"/"no_room", "mob_name": ...}."""
    pattern, mob_hp = M._pattern_hp_for_mob(class_name, mob_name)
    hand = rng.choice(mod.ALL_HANDS)
    win, final_hp, final_rounds = M._engine_pull(class_name, mob_name, hand, pattern, mob_hp, hero.hp)
    hero.hp = final_hp
    # One turn -- OPEN_QUESTIONS.md's "What a turn is" (locked): "Quest node: one pull is
    # one turn." A "declined" pull (returned above, before reaching here, resolve_node_pull
    # only) does NOT count -- nothing was actually attempted at the table.
    hero.turns += 1

    if hero.hp <= 0:
        # Clamped to exactly 0, matching run_one_trip's own death result (_make_result(...,
        # hp=0) -- hardcoded, not whatever raw negative value the pull actually produced.
        hero.hp = 0
        hero.alive = False
        return {"outcome": "died", "mob_name": mob_name}

    if win:
        # Gold is unconditional on any win, recovery pull or not -- "the +1 Gold still
        # requires an actual win though, not just survival -- same win-only standard as
        # every other pull, not a separate rule for recovery" (run_one_trip's own comment,
        # verbatim). Only the quest LOOT is suppressed.
        hero.gold += 1
        if suppress_loot:
            return {"outcome": "win", "mob_name": mob_name}
        if not M._add_loot(hero.bag, hero.locked, loot_name):
            return {"outcome": "no_room", "mob_name": mob_name}
        return {"outcome": "win", "mob_name": mob_name}
    return {"outcome": "flee", "mob_name": mob_name}


def commit_node_pull(hero, class_name, node_name, mob_name, rng, suppress_loot=False):
    """Human-facing equivalent of resolve_node_pull, used by apply_travel_action's declare_node
    handling -- checkpointed 2026-08-22 after confirming the shape directly: get_travel_actions
    already shows every dealt Node's mob up front (OPEN_QUESTIONS.md: "what's currently at each
    node, visible before committing to a pull"), across every active quest at once, not just
    one AI-preselected candidate -- so there's no separate "reveal, then decide" moment left to
    gate here. use_food/use_potion are their own standalone Travel actions (see
    get_travel_actions/apply_travel_action), available beforehand for anyone wanting better odds
    before committing. Declaring a Node IS the commitment, so this goes straight to the pull --
    no decline path (a human who doesn't want this fight simply doesn't choose this declare_node
    action in the first place; retreating lives in the Travel menu itself, not as a second gate
    bolted on after declaring).

    The AI-automatic path (decide_travel + resolve_node_pull, used by run_solo_trip/
    run_solo_chain) is completely untouched -- this is an additive sibling, not a replacement.

    Mutates hero in place. Returns {"outcome": "win"/"flee"/"died"/"no_room", "mob_name": ...}."""
    mod = M.CARD_SOURCE[class_name]
    _tier, loot_name = M.NODES[node_name]
    with LV.leveled_kit(mod, _level2_swaps_for(class_name, hero.acquired)):
        return _pull_and_resolve(hero, class_name, mod, mob_name, loot_name, rng, suppress_loot)


def commit_scroll_vanquish(hero, node_name, mob_name):
    """Resolves a Scroll of Vanquishing used on a declared Node -- checkpointed 2026-08-22, the
    Bag-slot consumables slice. No combat played at all: the mob is defeated automatically,
    hero takes 0 damage, gains the normal +1 Gold and the Node's loot (reuses the SAME win
    bookkeeping resolve_node_pull/_pull_and_resolve use for an ordinary win, not a separate
    path, so a Scroll-won pull can never diverge from what an ordinary win grants). Still costs
    the pull's one turn -- the Node's action still happened, just without cards played.

    Callers are responsible for the Standard-tier-only restriction (get_travel_actions only
    offers use_scroll for Standard-tier mobs in the first place) -- this function itself doesn't
    re-check, matching every other resolver's "the action menu is the gate" convention.

    Mutates hero in place. Returns {"outcome": "win", "mob_name": ...} or {"outcome": "no_room",
    "mob_name": ...} if the Node's loot can't fit."""
    _tier, loot_name = M.NODES[node_name]
    hero.turns += 1
    hero.gold += 1
    if not M._add_loot(hero.bag, hero.locked, loot_name):
        return {"outcome": "no_room", "mob_name": mob_name}
    return {"outcome": "win", "mob_name": mob_name}


def commit_smoke_bomb_flee(hero):
    """Resolves a Smoke Bomb used to bail out of a revealed mob (a declared Node) or a
    committed Border crossing -- checkpointed 2026-08-22. No combat played, 0 damage, 0 Gold,
    0 loot -- the pull/crossing just ends. Still costs the turn (the action -- declaring a
    Node, or committing to a crossing's toll -- still happened).

    Mutates hero in place. Returns {"outcome": "flee"}."""
    hero.turns += 1
    return {"outcome": "flee"}


def _town_automatic_setup(hero, class_name, strategy, rng):
    """Everything about a Town visit that is NOT a discretionary player choice -- quest
    turn-in/decay/refill, the leaving-town restock, Phase 1 quest pickup, and the free
    mandatory-upgrade grant. Factored out of resolve_town_turn (2026-08-22) so both the
    AI-automatic path (resolve_town_turn, unchanged) and the new human-facing macro seam
    (get_town_actions/apply_town_action) share the identical logic for this part -- only the
    Purchase Queue (genuinely discretionary: which upgrade, in what order, whether to stop)
    differs between the two callers, matching how none of turn-in/restock/pickup/mandatory-
    grant are real choices in the physical game either (you don't decline a completed
    quest's reward, or decline being handed a new quest by the quest-giver).

    Mutates hero in place. Returns a dict: {"quests_completed": int, "mandatory_turn": bool,
    "gold_after_turnin": int}."""
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

    return {"quests_completed": quests_completed, "mandatory_turn": mandatory_turn,
            "gold_after_turnin": gold_after_turnin}


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
    Purchase Queue. This is the AI-automatic path -- see get_town_actions/apply_town_action
    for the human-facing equivalent, which shares _town_automatic_setup for everything here
    except the Purchase Queue walk.

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
    setup = _town_automatic_setup(hero, class_name, strategy, rng)

    hero.gold, purchase_trainer_turn = M._walk_purchase_queue(
        purchase_queue, hero.acquired, hero.bag, hero.locked, zone_id, hero.gold, purchase_policy)

    # One turn, always -- "a hero may do as much business as they want in one visit... One
    # turn total per Town visit, no matter how much gets done there" (OPEN_QUESTIONS.md,
    # locked, verbatim). Unconditional: even a Town call that turns in nothing and buys
    # nothing still counts (the hero still visited).
    hero.turns += 1

    return {"quests_completed": setup["quests_completed"],
            "trainer_turn": setup["mandatory_turn"] or purchase_trainer_turn,
            "gold_after_turnin": setup["gold_after_turnin"]}


def enter_town(hero, class_name, strategy, rng):
    """Human-facing equivalent of resolve_town_turn's first half -- runs the automatic parts
    of a Town visit (turn-in, restock, quest pickup, mandatory grant, see
    _town_automatic_setup) and marks the ONE turn this whole visit costs (unconditional,
    matching resolve_town_turn's own timing exactly -- charged on arrival, not per purchase,
    since "one turn total per Town visit, no matter how much gets done there" is the locked
    rule). Call this ONCE when a hero arrives at Town, then drive purchases via
    get_town_actions/apply_town_action in a loop until leave_town is chosen.

    Mutates hero in place. Returns _town_automatic_setup's own dict (quests_completed,
    mandatory_turn, gold_after_turnin)."""
    setup = _town_automatic_setup(hero, class_name, strategy, rng)
    hero.turns += 1
    return setup


def get_town_actions(hero, purchase_queue):
    """Legal Town actions available RIGHT NOW: any Purchase Queue item that's currently
    eligible (right location for a Trainer-gated skill, Level-2-quests-started for the Bag
    Upgrade, not already owned) AND affordable this instant, plus leave_town (always legal).
    Deliberately does NOT apply purchase_policy's save-vs-skip ordering at all -- that's an AI
    heuristic for walking the queue unattended; a human sees every affordable option and picks
    freely, in whatever order they want, same as combat_engine.get_legal_actions doesn't
    pre-filter down to "the AI's preferred card" either.

    Also offers buy_consumable (checkpointed 2026-08-22) for each of M.CONSUMABLE_ITEMS the
    hero can afford AND has Bag room for -- a genuinely different kind of purchase from the
    Purchase Queue's one-time acquired-tracked items (Bag Upgrade, Skills): these are
    repeatable, same category as the Food/Potion restock, so they don't belong in
    purchase_queue/hero.acquired at all. use_charm is offered once per currently-decayed active
    quest, if the hero holds an unlocked Preserving Charm."""
    zone_id, _node = hero.position
    actions = []
    for item in purchase_queue:
        if item["tag"] in hero.acquired:
            continue
        if item["requires_trainer"] and zone_id not in M.TRAINER_ZONES:
            continue
        if item["requires_l2_started"] and "started_l2_quests" not in hero.acquired:
            continue
        if hero.gold < item["cost"]:
            continue
        actions.append({"type": "buy", "tag": item["tag"], "kind": item["kind"], "cost": item["cost"]})

    for item_name, cost in M.CONSUMABLE_ITEMS.items():
        if hero.gold >= cost and M._bag_has_room(hero.bag, hero.locked):
            actions.append({"type": "buy_consumable", "item_name": item_name, "cost": cost})

    if M._accessible_count(hero.bag, hero.locked, "preserving_charm") > 0:
        for loot in hero.active_quests:
            if hero.decay_stage.get(loot, 0) > 0:
                actions.append({"type": "use_charm", "loot": loot})

    actions.append({"type": "leave_town"})
    return actions


def apply_town_action(hero, action, purchase_queue):
    """Resolves one Town action from get_town_actions. Mutates hero in place. Returns True if
    the hero is still at Town (call get_town_actions again for the next choice), False if
    they just left (leave_town) -- no separate turn cost either way, matching enter_town's own
    "the whole visit is one turn, charged on arrival" accounting.

    leave_town also clears hero.position's node marker from "town" back to None -- the
    symmetric counterpart of apply_travel_action's return_to_town, which sets it TO "town".
    Without this, a human-facing driver checking hero.position for "am I in Town right now"
    (the natural way to decide whether to call get_town_actions or get_travel_actions next)
    would see "town" forever after the first visit and never actually leave -- caught live via
    verify_board_engine_travel_actions.py's end-to-end smoke drive, which got stuck re-entering
    Town every iteration with zero declares or crossings ever happening. decide_travel/
    resolve_node_pull/resolve_border_crossing never read this marker (only zone_or_border, the
    first element) so nothing in the AI-automatic path was ever affected by its absence."""
    if action["type"] == "leave_town":
        zone_id, _node = hero.position
        hero.position = (zone_id, None)
        return False

    if action["type"] == "buy_consumable":
        hero.gold -= action["cost"]
        M._add_item(hero.bag, hero.locked, action["item_name"])
        return True

    if action["type"] == "use_charm":
        M._remove_item(hero.bag, hero.locked, "preserving_charm", 1)
        hero.decay_stage[action["loot"]] = 0
        return True

    item = next(i for i in purchase_queue if i["tag"] == action["tag"])
    hero.gold -= item["cost"]
    hero.acquired.add(item["tag"])
    if item["kind"] == "bag":
        hero.bag.append(None)
        hero.locked.append(False)
    return True


def get_travel_actions(hero, board, rng):
    """Legal Travel actions right now -- the human-facing equivalent of decide_travel's
    single auto-picked target, checkpointed 2026-08-22. Unlike decide_travel (which only ever
    considers whichever incomplete quest's Node is closest), this shows EVERY currently real
    option: any non-Spice dealt Node in the hero's own Zone (regardless of whether it serves
    an active quest -- a human might want the easy mob, the Gold, or just to explore), every
    Border Node reachable from here (not just the one leading toward the AI's preferred
    target), Flight Path if eligible, and returning to Town (always legal -- a human can
    retreat mid-trip for no forced reason, unlike the AI which only stops per its own rules).

    Dealing a Zone happens here, automatically, the FIRST time this is called for that Zone
    this turn (matching Deal-on-entry / the full-refresh-every-turn rule -- flipping the cards
    face-up is not a player choice) -- calling this again without an intervening
    apply_travel_action returns the SAME menu, it does not re-deal.

    Standing on a Border Node is a distinct, smaller case: no Node declares or further
    crossings are offered there (a Border Node has no Nodes of its own and the hero hasn't
    entered a Zone yet to consider crossing onward) -- only entering either connected Zone,
    or returning to Town (free, matching "travel itself is free," Golden Rule 1 -- the hero
    can just walk back into a Zone they can already freely reach and declare Town there,
    represented here as a direct return_to_town option for convenience rather than forcing a
    two-step "enter_zone then return_to_town").

    use_food/use_potion (checkpointed 2026-08-22, the Risk-gate slice) are offered whenever
    the hero holds an unlocked one and isn't at full HP, regardless of position (Zone or
    Border Node) -- eating/drinking isn't tied to any specific declared fight, matching
    "What a turn is" (OPEN_QUESTIONS.md, locked): only the 5 listed node-type actions cost a
    turn, and consuming a Food/Potion isn't one of them (it's already turn-free even inside
    resolve_node_pull's own automatic version). This is what actually replaces the AI's old
    reactive "use a consumable if this pull looks too risky" heuristic for the human path --
    not a second gate after declare_node (see commit_node_pull's own docstring for why that
    isn't needed once the mob is already visible in this same menu).

    use_scroll/use_smoke_bomb (checkpointed 2026-08-22, the Bag-slot consumables slice) are
    offered per-target, alongside declare_node/cross_border: use_scroll only for a declared
    Node whose mob is Standard-tier (never Elite/Boss -- DESIGN_DOC.md's own restriction,
    enforced here since this is the one place that knows both the mob's identity and its tier);
    use_smoke_bomb for both declared Nodes and Border crossings (its real value is the crossing
    case, since resolve_border_crossing has no ordinary decline path once committed -- see
    commit_smoke_bomb_flee's own docstring). Neither needs the mob known in advance for
    smoke_bomb's Border case -- it's a blind, unconditional bail, matching how Scouted Pull
    itself doesn't reveal a Border crossing's mob before committing to the toll.

    Returns a list of action dicts, does not mutate hero."""
    zone_or_border, _node = hero.position
    actions = []
    has_scroll = M._accessible_count(hero.bag, hero.locked, "scroll_of_vanquishing") > 0
    has_smoke_bomb = M._accessible_count(hero.bag, hero.locked, "smoke_bomb") > 0

    if isinstance(zone_or_border, int):
        zone_id = zone_or_border
        level = TIER_TO_LEVEL[M.ZONE_TIER[zone_id]]
        if zone_id not in board.zones or not board.zones[zone_id].dealt:
            B.deal_zone(board, zone_id, level, _nodes_in_zone(zone_id), rng)
        zone_board = board.zones[zone_id]
        for node_name in legal_node_declares(zone_board):
            mob_name = zone_board.dealt[node_name]
            actions.append({"type": "declare_node", "node_name": node_name, "mob_name": mob_name})
            if has_scroll and mob_name in B._STANDARD_MOBS:
                actions.append({"type": "use_scroll", "node_name": node_name, "mob_name": mob_name})
            if has_smoke_bomb:
                actions.append({"type": "use_smoke_bomb", "node_name": node_name, "mob_name": mob_name})
        for border_name, connects in M.BORDER_NODES.items():
            if zone_id in connects:
                target_zone = next(iter(connects - {zone_id}))
                actions.append({"type": "cross_border", "border_name": border_name, "target_zone": target_zone})
                if has_smoke_bomb:
                    actions.append({"type": "use_smoke_bomb", "border_name": border_name,
                                     "target_zone": target_zone})
        if zone_id in M.FLIGHT_PATH_ZONES and hero.gold >= M.FLIGHT_PATH_COST:
            target_zone = next(iter(M.FLIGHT_PATH_ZONES - {zone_id}))
            actions.append({"type": "flight_path", "target_zone": target_zone, "cost": M.FLIGHT_PATH_COST})
    else:
        border_name = zone_or_border
        for target_zone in M.BORDER_NODES[border_name]:
            actions.append({"type": "enter_zone", "target_zone": target_zone})

    if hero.hp < hero.max_hp:
        if any(not hero.locked[i] and hero.bag[i] == "food" for i in range(len(hero.bag))):
            actions.append({"type": "use_food"})
        if any(not hero.locked[i] and M._is_potion_slot(hero.bag[i]) for i in range(len(hero.bag))):
            actions.append({"type": "use_potion"})

    actions.append({"type": "return_to_town"})
    return actions


def apply_travel_action(hero, action, class_name, board, rng,
                         risk_tolerance_base, risk_only_as_last_resort, defer_zone_discard=False):
    """Resolves one Travel action from get_travel_actions. declare_node now commits
    unconditionally via commit_node_pull -- no automatic risk-gate or consumable substitution
    (checkpointed 2026-08-22, the Risk-gate slice: see commit_node_pull's own docstring for
    why that gate isn't needed once the mob is already visible in this same menu).
    resolve_border_crossing's own risk-gate/consumable logic is UNCHANGED and still automatic
    once a candidate is chosen -- only WHICH candidate is picked became a real choice
    (checkpointed 2026-08-23, task #63): cross_border no longer auto-resolves combat, it reveals
    both real Scouted Pull candidates and lets the caller pick.

    Mutates hero and board in place. Returns a dict: {"outcome": str, ...} -- shape depends on
    action type:
      declare_node: whatever commit_node_pull returned ("win"/"flee"/"died"/"no_room"), plus
          the Zone gets Discarded afterward (end-of-turn cleanup, matching run_solo_trip's own).
      cross_border: {"outcome": "scouted_pull_reveal", "candidates": [mob1, mob2],
          "border_name": ..., "target_zone": ...} -- no combat played yet. The caller picks one
          of the 2 candidates and calls resolve_border_crossing directly with that mob_name
          (resolve_border_crossing already takes mob_name as a plain externally-sourced
          parameter -- no new resolver needed) to actually attempt the crossing and get the
          real "win"/"flee"/"died" outcome. The crossing itself is already committed to at this
          point (matching resolve_border_crossing's own "once committed, the pull always
          happens" rule) -- there's no way to back out AFTER seeing both candidates; a Smoke
          Bomb bail-out has to be chosen at the ORIGINAL cross_border decision (see
          get_travel_actions), before this reveal happens, not after.
      flight_path/enter_zone/return_to_town: {"outcome": "moved"} -- no combat, just position
          (and Gold, for flight_path) changes.
      use_food/use_potion: {"outcome": "healed"} -- no position/turn change.
      use_scroll: whatever commit_scroll_vanquish returned ("win"/"no_room") -- guaranteed win,
          no combat played, Zone gets Discarded afterward same as declare_node.
      use_smoke_bomb: {"outcome": "flee"} from commit_smoke_bomb_flee -- guaranteed flee, no
          combat played; Zone gets Discarded afterward for the Node case, no Discard for the
          Border case (no Zone was ever dealt for a crossing).
    A caller should check outcome == "died" the same way run_solo_trip does; a death here
    does NOT do the death/recovery post-processing itself (that lives in run_solo_chain's own
    loop, matching every other resolver's scope boundary -- this function resolves one action,
    it doesn't own the surrounding chain bookkeeping).

    defer_zone_discard (checkpointed 2026-08-23, task #64): when True, skips this function's
    own inline B.discard_zone call for declare_node/use_scroll/use_smoke_bomb -- used by
    advance_board's multi-hero barrier, where a second hero's pull at the SAME Zone this same
    round would otherwise get wiped out from under them by the first hero's own per-action
    discard. The caller (advance_board) is responsible for discarding every touched Zone once,
    after every hero's declaration this round has resolved. Solo mode never sets this, so its
    behavior is completely unchanged."""
    if action["type"] == "declare_node":
        zone_id, _node = hero.position
        level = TIER_TO_LEVEL[M.ZONE_TIER[zone_id]]
        result = commit_node_pull(hero, class_name, action["node_name"], action["mob_name"], rng)
        if not defer_zone_discard:
            B.discard_zone(board, zone_id, level)
        return result

    if action["type"] == "cross_border":
        level_deck = board.level_decks[TIER_TO_LEVEL[M.ZONE_TIER[action["target_zone"]]]]
        candidates = reveal_scouted_pull_candidates(level_deck, rng)
        return {"outcome": "scouted_pull_reveal", "candidates": candidates,
                "border_name": action["border_name"], "target_zone": action["target_zone"]}

    if action["type"] == "flight_path":
        hero.gold -= action["cost"]
        hero.position = (action["target_zone"], None)
        return {"outcome": "moved"}

    if action["type"] == "enter_zone":
        hero.position = (action["target_zone"], None)
        return {"outcome": "moved"}

    if action["type"] == "use_scroll":
        zone_id, _node = hero.position
        level = TIER_TO_LEVEL[M.ZONE_TIER[zone_id]]
        M._remove_item(hero.bag, hero.locked, "scroll_of_vanquishing", 1)
        result = commit_scroll_vanquish(hero, action["node_name"], action["mob_name"])
        if not defer_zone_discard:
            B.discard_zone(board, zone_id, level)
        return result

    if action["type"] == "use_smoke_bomb":
        M._remove_item(hero.bag, hero.locked, "smoke_bomb", 1)
        if "node_name" in action:
            zone_id, _node = hero.position
            level = TIER_TO_LEVEL[M.ZONE_TIER[zone_id]]
            result = commit_smoke_bomb_flee(hero)
            if not defer_zone_discard:
                B.discard_zone(board, zone_id, level)
            return result
        return commit_smoke_bomb_flee(hero)

    if action["type"] == "use_food":
        for i, slot in enumerate(hero.bag):
            if hero.locked[i]:
                continue
            if slot == "food":
                hero.hp = hero.max_hp
                hero.bag[i] = None
                hero.consumables_used["food"] += 1
                break
        return {"outcome": "healed"}

    if action["type"] == "use_potion":
        hero.hp = min(hero.max_hp, hero.hp + M.POTION_HEAL)
        M._remove_item(hero.bag, hero.locked, "potion", 1)
        hero.consumables_used["potion"] += 1
        return {"outcome": "healed"}

    # return_to_town -- free, matches Golden Rule 1 ("travel itself is free"). If currently on
    # a Border Node, "returning to Town" means walking into whichever connected Zone is
    # closer -- picks the first one listed, since both are equally free from a Border Node and
    # neither is objectively "closer" in hop terms; a real UI would let the human pick which
    # Zone's Town to walk into instead of defaulting.
    zone_or_border, _node = hero.position
    zone_id = zone_or_border if isinstance(zone_or_border, int) else next(iter(M.BORDER_NODES[zone_or_border]))
    hero.position = (zone_id, "town")
    return {"outcome": "moved"}


def declare_for_hero(board, hero_idx, action):
    """Records hero_idx's chosen Travel action for this round without resolving it -- the
    Move-and-declare barrier's first half (OPEN_QUESTIONS.md's locked turn-phase order, step 2:
    "every hero moves and declares their target node simultaneously"), checkpointed 2026-08-23,
    task #64. Call once per hero per round (get_travel_actions to see the legal menu, pick one,
    declare_for_hero to submit it); advance_board waits until every hero in board.heroes has an
    entry here before resolving anything.

    Scope note: only Travel-seam actions (get_travel_actions/apply_travel_action's vocabulary)
    go through this barrier. Town visits are handled separately, exactly as they already are
    for solo mode (enter_town + a get_town_actions/apply_town_action loop whenever a hero's
    position lands on "town") -- Town "has unlimited capacity and is never contested... it's a
    hub, not a fight" (board_state.py's own docstring), so it never needs a barrier at all."""
    board.pending_declarations[hero_idx] = action


def _priority_order(board):
    """Hero indices in this round's priority order, starting from whoever currently holds the
    token -- "a rotating 'pass the buck' Player-One token that shifts one seat to the left
    every round, giving a straight 1-2-3 priority count from whoever's holding it that round"
    (OPEN_QUESTIONS.md, locked, verbatim)."""
    n = len(board.heroes)
    return [(board.priority_token_holder + i) % n for i in range(n)]


def _blind_redraw(board, zone_id, level, rng):
    """A contested Node's second-or-later hero (in priority-token order) doesn't get the
    already-dealt mob -- they draw a fresh, unpreviewed replacement from the level deck
    instead: "whoever's second (etc.) at that *same* node the *same* round draws a fresh
    replacement blind -- no preview before committing" (OPEN_QUESTIONS.md, locked, verbatim) --
    the one deliberate hidden-information exception in this whole project. Does NOT touch
    board.zones[zone_id].dealt -- this is a personal draw for one hero's own pull, not a change
    to the shared board state the winning hero (who keeps the original dealt card) still needs
    to see. Discards the drawn card immediately, same convention as deal_zone/
    scouted_pull_from_deck -- it's a one-off personal draw, never placed on the shared board, so
    nothing else would ever sweep it into discard otherwise."""
    deck = board.level_decks[level]
    card = deck.draw(rng)
    while B.is_spice(card):
        deck.discard(card)
        card = deck.draw(rng)
    deck.discard(card)
    return card


def advance_board(board, class_names, rng, risk_tolerance_base, risk_only_as_last_resort):
    """The Move-and-declare barrier's second half -- resolves contested Nodes and every hero's
    declared action once everyone has one (checkpointed 2026-08-23, task #64). Returns None
    if any hero in board.heroes hasn't declared yet ("still waiting," matching the tabletop
    reality that a real round can't resolve until every player has chosen). Once complete:

    1. Groups this round's declare_node declarations by target Node. Any Node claimed by 2+
       heroes is contested: priority-token order decides who's "first" (sees the already-dealt
       mob, unchanged) versus every other claimant (gets a fresh blind redraw, see
       _blind_redraw's own docstring) -- OPEN_QUESTIONS.md's locked rule, step 3.
    2. Resolves every hero's action via the existing single-hero apply_travel_action, with Zone
       Discard deferred (defer_zone_discard=True) until every hero touching a given Zone this
       round has resolved -- doing it per-action the way solo mode always has would wipe a
       second hero's own still-pending dealt mob out from under them mid-round.
    3. Discards every Zone any hero declared into this round (end-of-turn cleanup, step 5),
       advances the priority token one seat, and clears pending_declarations for next round.

    Explicitly NOT handled by this first slice (real, documented gaps, not oversights):
    simultaneous Border-crossing arrivals at the same border+target_zone this round (Scouted
    Pull's own multiplayer-contention sub-case isn't fully locked yet -- see
    unified-sprouting-aurora.md's open question (part of the "Revision" section)); multi-hero
    corpse recovery/death interaction with this barrier (run_solo_chain's own death
    post-processing was built and verified for exactly one hero, never re-checked against a
    barrier where OTHER heroes are still resolving their own turns the same round).

    class_names is a {hero_idx: class_name} dict -- every other resolver in this file only ever
    handled one hero (and so one class) at a time; this is the first one where different heroes
    can be different classes within the same call.

    Mutates every declared hero and board in place. Returns {hero_idx: result_dict} (same
    per-action-type shapes apply_travel_action's own docstring already documents), or None if
    still waiting on at least one hero's declaration."""
    if len(board.pending_declarations) < len(board.heroes):
        return None

    declarations = dict(board.pending_declarations)
    node_claims = {}
    for hero_idx, action in declarations.items():
        if action["type"] == "declare_node":
            node_claims.setdefault(action["node_name"], []).append(hero_idx)

    order = _priority_order(board)
    for node_name, claimants in node_claims.items():
        if len(claimants) < 2:
            continue
        claimants.sort(key=order.index)
        for hero_idx in claimants[1:]:
            hero = board.heroes[hero_idx]
            zone_id, _node = hero.position
            level = TIER_TO_LEVEL[M.ZONE_TIER[zone_id]]
            blind_mob = _blind_redraw(board, zone_id, level, rng)
            declarations[hero_idx] = dict(declarations[hero_idx], mob_name=blind_mob)

    touched_zone_levels = set()
    results = {}
    for hero_idx, action in declarations.items():
        hero = board.heroes[hero_idx]
        zone_or_border, _node = hero.position
        if isinstance(zone_or_border, int) and action["type"] in ("declare_node", "use_scroll", "use_smoke_bomb"):
            touched_zone_levels.add((zone_or_border, TIER_TO_LEVEL[M.ZONE_TIER[zone_or_border]]))
        results[hero_idx] = apply_travel_action(hero, action, class_names[hero_idx], board, rng,
                                                  risk_tolerance_base, risk_only_as_last_resort,
                                                  defer_zone_discard=True)

    for zone_id, level in touched_zone_levels:
        B.discard_zone(board, zone_id, level)

    board.priority_token_holder = (board.priority_token_holder + 1) % len(board.heroes)
    board.pending_declarations.clear()
    return results


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
                    hero.consumables_used["food"] += 1
                    break
                if M._is_potion_slot(slot):
                    hero.hp = min(hero.max_hp, hero.hp + M.POTION_HEAL)
                    M._remove_item(hero.bag, hero.locked, "potion", 1)
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
                M._remove_item(hero.bag, hero.locked, "potion", 1)
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


def _draw_scouted_candidates(level_deck, rng):
    """Draws until 2 real (non-Spice) mob cards are gathered, discarding every card drawn
    along the way -- Spice has no combat mechanic yet, so a Spice draw is simply skipped and
    discarded, not treated as a candidate and not reshuffled back in (matches the locked "cards
    go to discard" rule; drawing again on a Spice hit was checkpointed directly rather than
    assumed -- the alternative of treating Spice as an automatic-loss candidate or forcing the
    OTHER drawn card was considered and rejected). Shared by both the AI-automatic path
    (scouted_pull_from_deck) and the human-facing one (reveal_scouted_pull_candidates) --
    the draw/discard mechanics are identical either way; only WHO picks the winner differs."""
    candidates = []
    while len(candidates) < 2:
        card = level_deck.draw(rng)
        level_deck.discard(card)
        if not B.is_spice(card):
            candidates.append(card)
    return candidates


def scouted_pull_from_deck(class_name, level_deck, rng):
    """Real Scouted Pull, replacing macro_sim._scouted_pull_mob's independent rng.choices
    2-draw with an actual draw from the shared level deck -- checkpointed 2026-08-22. AI-
    automatic path only (decide_travel/run_solo_trip) -- picks whichever of the 2 real
    candidates has the lower cost% for this class via _best_scouted_candidate. See
    reveal_scouted_pull_candidates for the human-facing equivalent, which exposes both
    candidates instead of auto-picking (checkpointed 2026-08-23, task #63)."""
    candidates = _draw_scouted_candidates(level_deck, rng)
    return _best_scouted_candidate(class_name, candidates)


def reveal_scouted_pull_candidates(level_deck, rng):
    """Human-facing equivalent of scouted_pull_from_deck -- checkpointed 2026-08-23 (task #63).
    Draws and discards the same 2 real candidates via the identical mechanism
    (_draw_scouted_candidates), but returns BOTH instead of auto-picking one, matching Scouted
    Pull's own locked tabletop rule ("draw 2, reveal both face-up, the hero chooses which one")
    -- the AI-automatic path always just picked the statistically safer one, which was never
    actually a real choice for a human player. Both drawn cards are already discarded by the
    time this returns (matching the locked "cards go to discard" rule) -- the candidate NOT
    chosen doesn't get reshuffled back in, there's nothing left to "un-discard" for it.

    Used by apply_travel_action's cross_border handling: it returns a
    {"outcome": "scouted_pull_reveal", "candidates": [...], ...} dict instead of resolving
    combat immediately: a caller picks one of the 2 candidates, then calls
    resolve_border_crossing directly with that chosen mob_name (resolve_border_crossing already
    takes mob_name as a plain parameter, sourced externally, so no new resolver was needed for
    the actual combat step -- only the reveal-instead-of-auto-pick step was missing).

    Mutates level_deck (draw + discard). Returns a list of 2 mob names."""
    return _draw_scouted_candidates(level_deck, rng)


def _nodes_in_zone(zone_id):
    return [n for n in M.NODES if M.NODE_ZONE[n] == zone_id]


def _resolve_forced_recovery(hero, class_name, quest_pool, board, rng,
                              risk_tolerance, risk_tolerance_base, risk_only_as_last_resort):
    """The trip's forced first action when hero.corpse_node is set -- faithful port of
    run_one_trip's own pending_recovery branches. Two shapes, matching the two ways a corpse
    can form:
      - hero.corpse_node == "border:{border_name}:{origin_zone}:{target_zone}": retry that
        EXACT crossing (same border_name/target_zone) via a fresh Scouted Pull. A second
        death here produces a fresh death_marker for the SAME crossing, same spiral-risk
        shape as dying twice at an ordinary Node.
      - hero.corpse_node == a Node name: forced pull at that exact Node, loot suppressed
        (suppress_loot=True -- "a recovery pull earns no loot, regardless of outcome",
        verbatim). Sources its mob from the real deck like any other Node-pull (Deal that
        Node's Zone, pull specifically the corpse's Node regardless of quest priority,
        Discard) -- Spice can never block a recovery attempt since deal_zone now redraws a
        Spice hit away (see its own docstring).

    Returns None if recovery succeeded (hero.corpse_node already cleared, caller proceeds to
    normal routing), or a result dict ({"alive": False, "recovered": False, "death_node":
    ...}) if the hero died again attempting it."""
    corpse = hero.corpse_node
    if isinstance(corpse, str) and corpse.startswith("border:"):
        _, border_name, _origin_zone, target_zone_s = corpse.split(":")
        target_zone = int(target_zone_s)
        tier = M.ZONE_TIER[target_zone]
        level_deck = board.level_decks[TIER_TO_LEVEL[tier]]
        mob_name = scouted_pull_from_deck(class_name, level_deck, rng)
        outcome = resolve_border_crossing(hero, class_name, border_name, target_zone, mob_name, rng,
                                           risk_tolerance_base, risk_only_as_last_resort)
        if outcome["outcome"] == "died":
            return {"alive": False, "recovered": False, "death_node": outcome["death_marker"]}
        hero.corpse_node = None
        return None

    node_name = corpse
    zone_id = M.NODE_ZONE[node_name]
    level = TIER_TO_LEVEL[M.ZONE_TIER[zone_id]]
    node_names = _nodes_in_zone(zone_id)
    B.deal_zone(board, zone_id, level, node_names, rng)
    zone_board = board.zones[zone_id]
    mob_name = zone_board.dealt[node_name]  # forced -- the corpse's own Node, not a quest choice
    outcome = resolve_node_pull(hero, class_name, node_name, mob_name, quest_pool, rng,
                                 risk_tolerance, risk_tolerance_base, risk_only_as_last_resort,
                                 suppress_loot=True)
    B.discard_zone(board, zone_id, level)
    if outcome["outcome"] == "died":
        return {"alive": False, "recovered": False, "death_node": node_name}
    hero.corpse_node = None
    return None


def run_solo_trip(hero, class_name, quest_pool, fallback_target_zones, board, rng,
                   risk_tolerance, risk_tolerance_base, risk_only_as_last_resort):
    """One full field trip -- matches run_one_trip's own scope -- driven by decide_travel plus
    resolve_node_pull/resolve_border_crossing. board is a board_state.BoardState (zones +
    level_decks) -- both Border crossings (via scouted_pull_from_deck) and Node-pulls (via
    Deal + choose_node_to_declare) source their mob from the REAL level deck, not independent
    rng draws. This means run_solo_trip/run_solo_chain are no longer bit-for-bit comparable
    against _trip_chain at all (a real deck is a structurally different random process than
    independent rng.choices, same reasoning as every other real-deck swap this session) --
    verified by aggregate stats instead (see verify_board_engine_scouted_pull.py and
    verify_board_engine_node_deal.py).

    Node-pull mechanics, checkpointed 2026-08-22: every turn spent in a Zone gets a FULL,
    unconditional Deal to every one of that Zone's Nodes (OPEN_QUESTIONS.md's own words: "a
    full refresh every turn, not a partial one") -- not just once on first entry -- followed
    by an end-of-turn Discard of everything dealt, played or not ("nothing persists into next
    turn"). choose_node_to_declare picks which of the freshly-dealt Nodes to pull (already
    built to skip a Spice-dealt Node in favor of the next incomplete quest, see its own
    docstring) -- if NOTHING declarable exists this turn, the trip ends, matching
    resolve_node_pull's own "declined" shape.

    Corpse recovery, checkpointed 2026-08-22: if hero.corpse_node is set (from a previous
    trip's death, see run_solo_chain's own death post-processing), the trip's FIRST action is
    forced to retry that exact crossing/pull -- see _resolve_forced_recovery. Only once that
    succeeds (or if there was no corpse to begin with) does normal decide_travel routing take
    over for the rest of the trip.

    Mutates hero and board in place. Returns a dict: {"alive": bool, "recovered": bool,
    "death_node": str|None}. recovered is True only if a corpse was successfully retrieved
    THIS trip (independent of alive -- a trip can recover an old corpse and then die again
    elsewhere, matching run_one_trip's own result shape, where "recovered" and "died" are
    separate flags, not mutually exclusive). death_node is the new corpse's location if
    alive=False, matching run_one_trip's own death_node encoding exactly (either a Node name,
    or "border:{border_name}:{origin_zone}:{target_zone}")."""
    # HP does NOT carry across trips -- run_one_trip's own very first line is `hp = max_hp`,
    # unconditional, every trip (implicit "resting" at Town between excursions; HP only
    # carries across PULLS within one trip, never across trip boundaries). Missing this was a
    # real bug, not a design choice -- caught via a live divergence against _trip_chain
    # (trip 2's first pull showed hp=18 in the old code, hp=2 -- carried over from trip 1's
    # ending wounds -- in this driver, cascading into every downstream decision that trip).
    hero.hp = hero.max_hp
    recovered = False

    if hero.corpse_node is not None:
        died_result = _resolve_forced_recovery(hero, class_name, quest_pool, board, rng,
                                                 risk_tolerance, risk_tolerance_base, risk_only_as_last_resort)
        if died_result is not None:
            return died_result
        recovered = True
        # hero.alive is only ever SET to False (on a death, inside resolve_node_pull/
        # resolve_border_crossing) -- nothing else resets it back to True, so a hero who just
        # survived their own recovery pull is still marked dead from the ORIGINAL death unless
        # explicitly cleared here. Missing this was a real bug, not a design choice -- caught
        # via a live trace showing a successfully-recovered hero's trip still reporting
        # alive=False for the rest of that same trip.
        hero.alive = True

    while True:
        action = decide_travel(hero, class_name, quest_pool, fallback_target_zones,
                                risk_tolerance_base, risk_only_as_last_resort)
        if action["action"] == "end_trip":
            return {"alive": hero.alive, "recovered": recovered, "death_node": None}

        if action["action"] == "cross_border":
            tier = M.ZONE_TIER[action["target_zone"]]
            level_deck = board.level_decks[TIER_TO_LEVEL[tier]]
            mob_name = scouted_pull_from_deck(class_name, level_deck, rng)
            outcome = resolve_border_crossing(hero, class_name, action["border_name"], action["target_zone"],
                                               mob_name, rng, risk_tolerance_base, risk_only_as_last_resort)
            if outcome["outcome"] == "died":
                return {"alive": False, "recovered": recovered, "death_node": outcome["death_marker"]}
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
            return {"alive": hero.alive, "recovered": recovered, "death_node": None}  # nothing declarable

        mob_name = zone_board.dealt[node_name]
        outcome = resolve_node_pull(hero, class_name, node_name, mob_name, quest_pool, rng,
                                     risk_tolerance, risk_tolerance_base, risk_only_as_last_resort)
        B.discard_zone(board, zone_id, level)  # end-of-turn cleanup regardless of outcome
        if outcome["outcome"] == "died":
            return {"alive": False, "recovered": recovered, "death_node": node_name}
        if outcome["outcome"] in ("declined", "no_room"):
            # Matches run_one_trip's own behavior exactly: a declined pull (too risky, no
            # consumable left) or a bag-deadlock fallback both end the trip right there
            # (`return _make_result(completed=False, ...)`), they don't just skip this one
            # Node and keep going. Missing this check was a real bug, not a design choice --
            # decide_travel would otherwise see the identical hero state next iteration and
            # make the identical decision forever (caught via a genuine hang in
            # verify_board_engine_solo_chain.py, not by reasoning about it in advance).
            return {"alive": hero.alive, "recovered": recovered, "death_node": None}
        # win/flee just loop back to decide_travel again


def run_solo_chain(class_name, strategy, rng, max_turns, risk_tolerance=M.RISK_TOLERANCE,
                    risk_tolerance_base=M.RISK_TOLERANCE_BASE, risk_only_as_last_resort=True,
                    purchase_policy="save", bag_queue_position=0):
    """Runs a hero's career until hero.turns reaches max_turns -- the BoardState-driven
    equivalent of _trip_chain, restructured 2026-08-22 to be turn-denominated rather than
    trip-denominated, since a real turn (OPEN_QUESTIONS.md's "What a turn is," locked) is the
    only unit that's actually meaningful at the table; a "trip" is pure simulator-side
    bookkeeping for grouping the turns between two Town departures, never something a player
    declares or a rule references. This was the entire stated point of building BoardState in
    the first place -- an earlier version of this function still took chain_trips and yielded
    trip_num, which meant the ONE thing this whole rewrite was for hadn't actually reached the
    outermost, caller-visible layer yet, even though every resolver underneath it already
    resolved exactly one real turn each.

    Internally still advances one [run_solo_trip] + [death/recovery post-processing, if
    needed] + [resolve_town_turn] cycle at a time (interrupting mid-trip would need a bigger
    declare/resolve statechart change -- decide_travel would have to expose "visit Town" as
    an ordinary per-turn action instead of something the driver triggers between trips,
    tracked as a real follow-up, not done here) -- so a chain can overshoot max_turns by
    however many turns its last cycle took, and never undershoots it. Each cycle's own
    resolve_town_turn call still costs exactly one turn on top of whatever the trip itself
    cost, same as it always has.

    Death does NOT stop the chain -- matching _trip_chain's own respawn-and-continue behavior
    exactly. On a death: lock every non-empty Bag slot, apply +1 decay to every active quest
    (see below for why +1 here, not +2 directly), set hero.corpse_node to the death's
    location, and respawn hero.position to the nearest Town's Zone (the Zone containing the
    death Node, or the ORIGIN Zone of a mid-crossing death -- the hero hadn't actually left
    that Zone yet when the toll pull happened). On a recovery (hero.corpse_node successfully
    cleared this cycle, see run_solo_trip/_resolve_forced_recovery): unlock every Bag slot.
    Both checks are independent, not mutually exclusive -- a single cycle can recover an old
    corpse AND then die again forming a new one, matching _trip_chain's own two separate (not
    elif-chained) `if` blocks for this.

    resolve_town_turn is called UNCONDITIONALLY every cycle, death or not -- skipping it on
    death broke the very next cycle's "shopping happens before the recovery attempt"
    guarantee in an earlier version of this function (_trip_chain's shopping/Phase-1/
    Purchase-Queue always runs at the top of every iteration, recovery-attempt or not). Since
    every Bag slot just got locked on a death, its own turn-in loop naturally sees 0
    accessible loot for every active quest (matching _accessible_count's own "locked slots
    don't count" contract) -- no quest can look complete, so quests_completed comes out 0
    automatically, and its own per-incomplete-quest +1 decay bump fires too, landing on TOP
    of the +1 already applied here for a combined +2 -- reproducing _trip_chain's single
    `decay_stage[loot] = min(decay_stage[loot] + 2, ...)` death penalty exactly (two separate
    capped +1 bumps land identically to one capped +2 bump, checked directly:
    min(min(x+1,cap)+1,cap) == min(x+2,cap) for every x), without needing a second, parallel
    turn-in implementation just for the death case.

    Yields (alive, gold, xp, quests_completed, trainer_turn, turns) once per cycle. turns is
    hero.turns, the cumulative real-turn count -- the field a caller should actually track
    for any gold/turn or xp/turn comparison. No trip index is yielded at all; if a caller
    needs to know how many cycles ran, that's len() of the collected results, not something
    this function hands out as a meaningful unit."""
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

    while hero.turns < max_turns:
        pending_mandatory = (class_name in M.LEVEL2_MANDATORY and hero.xp >= M.LEVEL2_XP_THRESHOLD
                              and "mandatory" not in hero.acquired)
        valid_quest_zones = M.LEVEL2_QUEST_ZONES if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.LEVEL1_QUEST_ZONES
        fallback_target_zones = M.TRAINER_ZONES if pending_mandatory else valid_quest_zones
        quest_pool = M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS

        trip_result = run_solo_trip(hero, class_name, quest_pool, fallback_target_zones, board, rng,
                                     risk_tolerance, risk_tolerance_base, risk_only_as_last_resort)

        if trip_result["recovered"]:
            hero.locked = [False] * len(hero.locked)

        if not trip_result["alive"]:
            for i, slot in enumerate(hero.bag):
                if slot is not None:
                    hero.locked[i] = True
            for loot in hero.active_quests:
                q = quest_pool[loot]
                hero.decay_stage[loot] = min(hero.decay_stage.get(loot, 0) + 1, len(q["gold_ladder"]) - 1)
            death_node = trip_result["death_node"]
            hero.corpse_node = death_node
            if death_node.startswith("border:"):
                _, _, origin_zone_s, _ = death_node.split(":")
                hero.position = (int(origin_zone_s), "town")
            else:
                hero.position = (M.NODE_ZONE[death_node], "town")

        town_result = resolve_town_turn(hero, class_name, strategy, purchase_queue, purchase_policy, rng)
        yield (trip_result["alive"], town_result["gold_after_turnin"], hero.xp,
               town_result["quests_completed"], prev_trainer_turn, hero.turns)
        prev_trainer_turn = town_result["trainer_turn"]
