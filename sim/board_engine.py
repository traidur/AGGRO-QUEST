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
        # A class can have its mandatory upgrade locked before any purchased upgrades exist
        # yet (checkpointed 2026-08-24, Runecaster's own in-progress leveling pass -- caught
        # live as a real KeyError, not just a defensive guard added on spec): don't assume
        # LEVEL2_PURCHASED_ORDER has an entry just because LEVEL2_MANDATORY does. Matches
        # _build_purchase_queue's own identical guard for the same reason.
        if class_name in M.LEVEL2_PURCHASED_ORDER:
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
                       suppress_loot=False, decide_fn=None, hand=None):
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
    at all).

    decide_fn (checkpointed 2026-08-23): passed straight through to _pull_and_resolve --
    None (every existing caller) keeps the pull solver-automatic; a human-facing driver
    supplies its own terminal-input callback instead. Purely additive, see _pull_and_resolve's
    own docstring. hand: same passthrough, see _pull_and_resolve's own docstring for why a
    web-facing caller needs to pre-draw and reuse a specific hand rather than let this function
    draw its own."""
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
                    M._remove_food(hero.bag, i)
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

        return _pull_and_resolve(hero, class_name, mod, mob_name, loot_name, rng, suppress_loot,
                                  decide_fn=decide_fn, hand=hand)


def _pull_and_resolve(hero, class_name, mod, mob_name, loot_name, rng, suppress_loot, decide_fn=None,
                       hand=None):
    """Shared tail of resolve_node_pull and commit_node_pull -- draws a hand, runs the actual
    combat_engine pull, and resolves win/loss/loot bookkeeping. Must be called from inside an
    already-open LV.leveled_kit(...) scope (both callers open one for their own risk-gate/
    hand-draw work). Factored out 2026-08-22 so the AI-automatic risk-gated path and the
    human-facing unconditional-commit path can't drift apart on the one piece they genuinely
    share -- only what happens BEFORE the pull differs between them.

    decide_fn (checkpointed 2026-08-23): forwarded to macro_sim._engine_pull unchanged --
    None keeps the pull itself solver-automatic (QuestIntelligence), matching every existing
    caller exactly; a human-facing driver's own (state, actions) -> action callback plays the
    hand instead. Nothing else about this function's bookkeeping (turn count, HP, Gold, loot,
    death) changes either way -- decide_fn only ever affects WHICH cards get played, never
    what happens as a result of the outcome.

    hand (checkpointed 2026-08-23, web-UI slice): optional pre-drawn hand tuple, skipping the
    rng.choice(mod.ALL_HANDS) draw below -- None (every existing caller) is unchanged. Exists
    for a driver that needs to SHOW the hand to a human before resolving the pull (a terminal
    can just print-then-resolve in the same blocking call, but a web request/response can't --
    the route has to draw the hand, render it, then use that SAME hand once the human's full
    card-order submission comes back in a later request, not draw a second, different hand).

    Mutates hero in place. Returns {"outcome": "win"/"flee"/"died"/"no_room", "mob_name": ...}."""
    pattern, mob_hp = M._pattern_hp_for_mob(class_name, mob_name)
    if hand is None:
        hand = rng.choice(mod.ALL_HANDS)
    win, final_hp, final_rounds = M._engine_pull(class_name, mob_name, hand, pattern, mob_hp, hero.hp,
                                                  decide_fn=decide_fn)
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


def commit_node_pull(hero, class_name, node_name, mob_name, rng, suppress_loot=False, decide_fn=None,
                      hand=None):
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

    decide_fn (checkpointed 2026-08-23): forwarded to _pull_and_resolve unchanged -- None
    keeps this pull solver-automatic; a human-facing driver's own callback plays the hand.
    hand: same passthrough, see _pull_and_resolve's own docstring.

    Mutates hero in place. Returns {"outcome": "win"/"flee"/"died"/"no_room", "mob_name": ...}."""
    mod = M.CARD_SOURCE[class_name]
    _tier, loot_name = M.NODES[node_name]
    with LV.leveled_kit(mod, _level2_swaps_for(class_name, hero.acquired)):
        return _pull_and_resolve(hero, class_name, mod, mob_name, loot_name, rng, suppress_loot,
                                  decide_fn=decide_fn, hand=hand)


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


def _trainer_automatic_setup(hero, class_name):
    """The free, automatic part of a Trainer visit -- the mandatory upgrade grant. Split out
    2026-08-24 from _town_automatic_setup once the Class Trainer became its own turn-costing
    node type, separate from Town: OPEN_QUESTIONS.md's "What a turn is" lists Town and Class
    Trainer as parallel, independently-turn-costing node types ("Class Trainer: same structure
    as Town... One turn total per visit"), but the code had bundled the mandatory grant (and,
    until this same pass, purchased-skill buying) into Town's own single turn -- a real,
    caught implementation gap against the always-intended rule, not a redesign. See
    LEVELING_GUIDE.md and this session's own audit for the finding.

    No zone-eligibility check here (unlike the old bundled version, which re-checked
    `zone_id in M.TRAINER_ZONES` inline) -- this function is only ever called once a hero's
    position is already `(zone_id, "trainer")`, which itself is only reachable through
    apply_travel_action's visit_trainer handling, which in turn is only ever offered by
    get_travel_actions when the current zone is already in M.TRAINER_ZONES. The eligibility
    gate lives at the action-offering layer, same as every other Travel action's legality.

    Mutates hero in place. Returns {"mandatory_turn": bool}."""
    mandatory_turn = False
    if (hero.xp >= M.LEVEL2_XP_THRESHOLD and class_name in M.LEVEL2_MANDATORY
            and "mandatory" not in hero.acquired):
        hero.acquired.add("mandatory")
        mandatory_turn = True
    return {"mandatory_turn": mandatory_turn}


def _town_automatic_setup(hero, class_name, strategy, rng, board, restock=True, refill_quests=True):
    """Everything about a Town visit that is NOT a discretionary player choice -- quest
    turn-in/decay/refill, and Phase 1 quest pickup (the free mandatory-upgrade grant moved to
    _trainer_automatic_setup, 2026-08-24 -- see its own docstring for why). Factored out of
    resolve_town_turn (2026-08-22) so both the AI-automatic path (resolve_town_turn, unchanged)
    and the new human-facing macro seam (get_town_actions/apply_town_action) share the
    identical logic for this part -- only the Purchase Queue (genuinely discretionary: which
    upgrade, in what order, whether to stop) differs between the two callers, matching how
    turn-in/pickup aren't real choices in the physical game either (you don't decline a
    completed quest's reward, or decline being handed a new quest by the quest-giver).

    restock=True runs the automatic Food/Potion restock (M._leaving_town_setup) too -- the
    right default for AI-driven trips, which have no other way to stay supplied. A human,
    though, now has a real Buy Food/Buy Potion action (checkpointed 2026-08-26, replacing the
    automatic restock for humans specifically, not removing it for the AI): enter_town passes
    restock=False so a human's Bag only ever changes because they chose to spend Gold on it,
    not invisibly on arrival. resolve_town_turn (AI path) keeps the default.

    refill_quests=False skips the automatic Level 2 quest fill. Used by human-facing drivers
    (enter_town) because Level 2 quests are physically pulled from a face-up 3-card market,
    making which quest to pull a discretionary player choice handled via take_quest actions.

    Mutates hero in place. Returns a dict: {"quests_completed": int, "gold_after_turnin": int}."""
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
            for loot in turned_in:
                board.quest_discard.append(loot)
            newly_active = []
            # board.town_markets only has entries for zones 3/4 -- a hero can turn in an
            # already-active Level 2 quest at ANY Town (zones 1/2 included), which crashed with
            # KeyError until this guard (found live, 2026-08-28, same gap as macro_sim.py's
            # _trip_chain -- see that function's own comment for the full finding). No market
            # here means no refill opens at THIS turn-in; deliberately not deciding whether a
            # non-market Town should refill from somewhere else instead.
            market = board.town_markets.get(zone_id) if refill_quests else None
            if market is not None:
                while len(newly_active) < len(turned_in) and market:
                    newly_active.append(market.pop(0))
                board.draw_unique_quest(market, 3 - len(market), rng)
            hero.active_quests = still_incomplete + newly_active
        quests_completed = len(turned_in)

    gold_after_turnin = hero.gold
    if restock:
        hero.gold = M._leaving_town_setup(strategy, hero.bag, hero.locked, hero.gold)

    # Re-read: xp may have just risen from a quest turned in above, crossing LEVEL2_XP_THRESHOLD
    # mid-call -- the same live-lookup discipline run_one_trip's own win_rate uses.
    pool = M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS
    valid_quest_zones = M.LEVEL2_QUEST_ZONES if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.LEVEL1_QUEST_ZONES
    if not hero.active_quests and zone_id in valid_quest_zones:
        if pool is M.LEVEL2_QUESTS:
            if refill_quests:
                hero.active_quests = []
                while len(hero.active_quests) < M.ACTIVE_QUEST_COUNT and board.town_markets[zone_id]:
                    hero.active_quests.append(board.town_markets[zone_id].pop(0))
                board.draw_unique_quest(board.town_markets[zone_id], 3 - len(board.town_markets[zone_id]), rng)
                hero.acquired.add("started_l2_quests")
        else:
            hero.active_quests = rng.sample(list(pool.keys()), min(M.ACTIVE_QUEST_COUNT, len(pool)))

    return {"quests_completed": quests_completed, "gold_after_turnin": gold_after_turnin}


def resolve_town_turn(hero, class_name, strategy, purchase_queue, purchase_policy, rng, board):
    """Resolves one full Town turn, plus a separate Trainer turn if the hero is standing in a
    Trainer Zone and actually has Trainer business to do -- "Town... one turn total per visit"
    and "Class Trainer: same structure as Town... One turn total per visit" are two PARALLEL
    entries in OPEN_QUESTIONS.md's "What a turn is" (locked), each its own turn, not one
    combined stop. An earlier version of this function bundled both into a single turn --
    a real, caught implementation gap against the always-intended rule (found via direct user
    audit, 2026-08-24), not a design change; see LEVELING_GUIDE.md and _trainer_automatic_
    setup's own docstring for the full finding. Faithful port of _trip_chain's Town bookkeeping
    otherwise (quest turn-in/decay/refill, the leaving-town restock, Phase 1 Logistics, Phase 3
    Purchase Queue). This is the AI-automatic path -- see get_town_actions/apply_town_action
    for the human-facing equivalent, which shares _town_automatic_setup/_trainer_automatic_
    setup for everything here except the Purchase Queue walk.

    The Trainer turn only fires if there's real business there (the mandatory grant becoming
    eligible, or an affordable next skill) -- unlike Town, which is always the hero's
    deliberate destination this stop, a hero has no reason to spend a turn at the Trainer's
    counter with nothing to receive or buy, matching OPEN_QUESTIONS.md's already-locked
    "opportunistic, not deliberate travel" stance on purchased upgrades specifically.

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
    setup = _town_automatic_setup(hero, class_name, strategy, rng, board)

    town_queue = [item for item in purchase_queue if item["kind"] != "skill"]
    hero.gold, _ = M._walk_purchase_queue(
        town_queue, hero.acquired, hero.bag, hero.locked, zone_id, hero.gold, purchase_policy)

    # One turn, always -- "a hero may do as much business as they want in one visit... One
    # turn total per Town visit, no matter how much gets done there" (OPEN_QUESTIONS.md,
    # locked, verbatim). Unconditional: even a Town call that turns in nothing and buys
    # nothing still counts (the hero still visited).
    hero.turns += 1

    mandatory_turn = False
    purchase_trainer_turn = False
    if zone_id in M.TRAINER_ZONES:
        trainer_setup = _trainer_automatic_setup(hero, class_name)
        mandatory_turn = trainer_setup["mandatory_turn"]
        trainer_queue = [item for item in purchase_queue if item["kind"] == "skill"]
        hero.gold, purchase_trainer_turn = M._walk_purchase_queue(
            trainer_queue, hero.acquired, hero.bag, hero.locked, zone_id, hero.gold, purchase_policy,
            skill_purchase_order=hero.skill_purchase_order or None)
        if mandatory_turn or purchase_trainer_turn:
            hero.turns += 1

    return {"quests_completed": setup["quests_completed"],
            "trainer_turn": mandatory_turn or purchase_trainer_turn,
            "gold_after_turnin": setup["gold_after_turnin"]}


def enter_town(hero, class_name, strategy, rng, board):
    """Human-facing equivalent of resolve_town_turn's Town half -- runs the automatic parts of
    a Town visit (turn-in, quest pickup, see _town_automatic_setup) and marks the ONE turn this
    visit costs (unconditional, charged on arrival, not per purchase, since "one turn total per
    Town visit, no matter how much gets done there" is the locked rule). Call this ONCE when a
    hero arrives at Town, then drive purchases (including Buy Food/Buy Potion, checkpointed
    2026-08-26) via get_town_actions/apply_town_action in a loop until leave_town is chosen.
    Does NOT grant the mandatory upgrade -- see enter_trainer, the Trainer's own separate
    turn/visit (checkpointed 2026-08-24). Passes restock=False (unlike resolve_town_turn's
    AI-automatic path) -- a human's Bag only changes here because they chose to spend Gold on
    it, never invisibly on arrival.

    Mutates hero in place. Returns _town_automatic_setup's own dict (quests_completed,
    gold_after_turnin)."""
    setup = _town_automatic_setup(hero, class_name, strategy, rng, board, restock=False, refill_quests=False)
    hero.turns += 1
    return setup


def enter_trainer(hero, class_name):
    """Human-facing equivalent of resolve_town_turn's Trainer half -- runs the free, automatic
    part of a Trainer visit (the mandatory upgrade grant, see _trainer_automatic_setup) and
    marks the ONE turn this visit costs, separate from any Town turn (checkpointed 2026-08-24,
    Class Trainer split from Town into its own turn-costing node type -- see
    _trainer_automatic_setup's own docstring for the full finding). Call this ONCE when a
    hero's position becomes (zone_id, "trainer") (via apply_travel_action's visit_trainer
    handling), then drive purchases via get_town_actions/apply_town_action (the SAME functions
    Town uses, filtered by position) in a loop until leave_trainer is chosen.

    Unlike enter_town, this is always charged unconditionally too -- a human declaring
    visit_trainer has already made the deliberate choice to spend the turn, same as a Town
    visit; only the AI-automatic path (resolve_town_turn) skips the Trainer turn when there's
    nothing to do there, since it isn't making a deliberate per-turn choice the way a human is.

    Mutates hero in place. Returns _trainer_automatic_setup's own dict ({"mandatory_turn": bool})."""
    setup = _trainer_automatic_setup(hero, class_name)
    hero.turns += 1
    return setup


def get_town_actions(hero, purchase_queue, board=None):
    """Legal Town actions available RIGHT NOW: any Purchase Queue item that's currently
    eligible (right location for a Trainer-gated skill, Level-2-quests-started for the Bag
    Upgrade, not already owned) AND affordable this instant, plus leave_town (always legal).
    Deliberately does NOT apply purchase_policy's save-vs-skip ordering at all for the Bag
    Upgrade -- that's an AI heuristic for walking the queue unattended; a human sees it as soon
    as it's affordable and eligible, same as combat_engine.get_legal_actions doesn't pre-filter
    down to "the AI's preferred card" either.

    Skills are a real exception to that "sees every affordable option" framing (checkpointed
    2026-08-23, see LEVELING_GUIDE.md's "Purchased upgrade order" entry): at most ONE skill is
    ever offered at a time, whichever is next in hero.skill_purchase_order -- a personally-
    shuffled deck of upgrade cards, revealed one at a time, replacing the old fixed
    LEVEL2_PURCHASED_ORDER sequence. This isn't player choice among skills, deliberately: the
    whole point is preventing every table from converging on the same optimal purchase
    sequence, so a human's only real decision here is whether to spend the Gold on the one
    skill offered (or save it, or spend on the Bag Upgrade instead), never which skill.

    Also offers buy_consumable (checkpointed 2026-08-22) for each of M.CONSUMABLE_ITEMS the
    hero can afford AND has Bag room for -- a genuinely different kind of purchase from the
    Purchase Queue's one-time acquired-tracked items (Bag Upgrade, Skills): these are
    repeatable, same category as the Food/Potion restock, so they don't belong in
    purchase_queue/hero.acquired at all. use_charm is offered once per currently-decayed active
    quest, if the hero holds an unlocked Preserving Charm. Consumables/use_charm are Town-only
    (checkpointed 2026-08-24, the Trainer's own business is upgrade cards, nothing else,
    matching OPEN_QUESTIONS.md's "Class Trainer: same structure as Town -- buy as many upgrade
    cards as affordable in one visit" -- upgrade cards, not general restock).

    Shared with the Trainer seam (checkpointed 2026-08-24): this same function serves both,
    filtered by hero.position's own node marker -- "town" shows Bag Upgrade + consumables +
    use_charm + leave_town; "trainer" shows only Trainer-gated skill items + leave_trainer.
    Matches item["requires_trainer"] directly against which one it is, rather than the old
    (broken, undefined-variable) attempt at this same split -- Bag Upgrade and skills were
    bundled into one menu here before this pass, a real caught implementation gap against the
    always-intended "Trainer is its own turn-costing node, not folded into Town's shopping
    list" rule (DESIGN_DOC.md Section VII), not a redesign."""
    zone_id, node = hero.position
    at_trainer = node == "trainer"
    actions = []
    skills_acquired_so_far = sum(1 for tag in hero.acquired if tag.startswith("skill_"))
    for item in purchase_queue:
        if item["tag"] in hero.acquired:
            continue
        if item["requires_trainer"] != at_trainer:
            continue
        if item["requires_l2_started"] and "started_l2_quests" not in hero.acquired:
            continue
        if item["kind"] == "skill" and hero.skill_purchase_order:
            if (skills_acquired_so_far >= len(hero.skill_purchase_order)
                    or item["index"] != hero.skill_purchase_order[skills_acquired_so_far]):
                continue
        if hero.gold < item["cost"]:
            continue
        actions.append({"type": "buy", "tag": item["tag"], "kind": item["kind"], "cost": item["cost"]})

    if not at_trainer:
        if board and zone_id in (3, 4) and len(hero.active_quests) < M.ACTIVE_QUEST_COUNT:
            for quest in board.town_markets.get(zone_id, []):
                actions.append({"type": "take_quest", "quest_name": quest})

        for item_name, cost in M.CONSUMABLE_ITEMS.items():
            if hero.gold >= cost:
                if item_name == "food" and not M._can_fit_food(hero.bag, hero.locked):
                    continue
                elif item_name != "food" and not M._bag_has_room(hero.bag, hero.locked):
                    continue
                actions.append({"type": "buy_consumable", "item_name": item_name, "cost": cost})

        if M._accessible_count(hero.bag, hero.locked, "preserving_charm") > 0:
            for loot in hero.active_quests:
                if hero.decay_stage.get(loot, 0) > 0:
                    actions.append({"type": "use_charm", "loot": loot})

    actions.append({"type": "leave_trainer" if at_trainer else "leave_town"})
    return actions


def apply_town_action(hero, action, purchase_queue, board=None, rng=None):
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
    first element) so nothing in the AI-automatic path was ever affected by its absence.

    leave_town also resets hero.hp to hero.max_hp (checkpointed 2026-08-23) -- mirrors
    run_solo_trip's own unconditional first line ("HP does NOT carry across trips... implicit
    'resting' at Town between excursions"). run_solo_trip enforces this itself for the
    AI-automatic path; a human-facing driver has no equivalent "start of trip" hook other than
    this action, since get_travel_actions/apply_travel_action have no trip concept of their
    own (see this module's docstring on why BoardState only tracks turns, not trips) -- so it
    belongs here, the one place every human trip actually begins.

    leave_trainer (checkpointed 2026-08-24) is the same position-clearing shape but does NOT
    reset HP -- resting is a Town-specific amenity, not something that happens at the Trainer's
    counter; only an actual Town visit implies resting between excursions."""
    if action["type"] in ("leave_town", "leave_trainer"):
        zone_id, _node = hero.position
        hero.position = (zone_id, None)
        if action["type"] == "leave_town":
            hero.hp = hero.max_hp
        return False

    if action["type"] == "take_quest":
        zone_id, _node = hero.position
        quest = action["quest_name"]
        if board and quest in board.town_markets.get(zone_id, []):
            board.town_markets[zone_id].remove(quest)
            hero.active_quests.append(quest)
            board.draw_unique_quest(board.town_markets[zone_id], 3 - len(board.town_markets[zone_id]), rng)
            hero.acquired.add("started_l2_quests")
        return True

    if action["type"] == "buy_consumable":
        hero.gold -= action["cost"]
        if action["item_name"] == "food":
            M._add_food(hero.bag, hero.locked)
        else:
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
        # Appends 3 slots, not 1 (checkpointed 2026-08-25, bag-tetris rescale): under the old
        # 2-slot/ITEM_STACK_CAP=3 model, one Bag Upgrade added a whole second stacking slot
        # worth +3 item capacity. Under the new BAG_SIZE=6/ITEM_STACK_CAP=1 model, a single
        # appended slot is only worth +1 item capacity -- appending 3 preserves the same
        # per-upgrade capacity gain the base bag's own 2->6 rescale already established.
        for _ in range(3):
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

    # Offered whenever hurt OR bag-deadlocked (checkpointed 2026-08-23, task #65) -- eating
    # Food/drinking a Potion serves two real purposes, not just healing: Food occupies its own
    # whole slot, so eating it also frees that slot when the Bag has no room, independent of
    # current HP. The original hp-only gate meant a full-HP, bag-deadlocked hero (Food in one
    # slot, loot filled to cap in the other) had no way to ever free space at all -- caught
    # live via a real competitive-mode stall where a hero cycled Town<->field forever, never
    # able to eat the Food that was the ONLY thing blocking their own progress.
    if hero.hp < hero.max_hp or not M._bag_has_room(hero.bag, hero.locked):
        if any(not hero.locked[i] and hero.bag[i] == "food" for i in range(len(hero.bag))):
            actions.append({"type": "use_food"})
        if any(not hero.locked[i] and M._is_potion_slot(hero.bag[i]) for i in range(len(hero.bag))):
            actions.append({"type": "use_potion"})

    actions.append({"type": "return_to_town"})
    if zone_or_border in M.TRAINER_ZONES:
        actions.append({"type": "visit_trainer"})
    return actions


def apply_travel_action(hero, action, class_name, board, rng,
                         risk_tolerance_base, risk_only_as_last_resort, defer_zone_discard=False,
                         decide_fn=None, hand=None):
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
    behavior is completely unchanged.

    decide_fn (checkpointed 2026-08-23): forwarded to commit_node_pull for declare_node only
    (the one action type here that actually plays combat cards) -- None keeps the pull
    solver-automatic, matching every existing caller (including advance_board's competitive
    driver) exactly; a human-facing driver's own callback plays the hand instead. hand: same
    passthrough, also declare_node-only, see _pull_and_resolve's own docstring for why a web
    driver needs to pre-draw and reuse a specific hand. cross_border
    never reaches combat here at all (see the outcome-shape docstring above), so decide_fn is
    unused for it -- the caller passes it to resolve_border_crossing separately, after picking
    a candidate from the reveal."""
    if action["type"] == "declare_node":
        zone_id, _node = hero.position
        level = TIER_TO_LEVEL[M.ZONE_TIER[zone_id]]
        result = commit_node_pull(hero, class_name, action["node_name"], action["mob_name"], rng,
                                   decide_fn=decide_fn, hand=hand)
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
                M._remove_food(hero.bag, i)
                hero.consumables_used["food"] += 1
                break
        return {"outcome": "healed"}

    if action["type"] == "use_potion":
        hero.hp = min(hero.max_hp, hero.hp + M.POTION_HEAL)
        M._remove_item(hero.bag, hero.locked, "potion", 1)
        hero.consumables_used["potion"] += 1
        return {"outcome": "healed"}

    if action["type"] == "visit_trainer":
        # Free (same "travel itself is free" rule as return_to_town), and only ever offered
        # (get_travel_actions) when the hero's CURRENT zone is already in M.TRAINER_ZONES --
        # visiting the Trainer never involves crossing to a different Zone, just a position-
        # marker transition within the same one, matching return_to_town's own shape.
        # Checkpointed 2026-08-24: Class Trainer split from Town into its own turn-costing
        # node type -- see get_town_actions/_trainer_automatic_setup's own docstrings.
        zone_or_border, _node = hero.position
        hero.position = (zone_or_border, "trainer")
        return {"outcome": "moved"}

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


def _resolve_contested_declarations(board, rng):
    """Extracted 2026-08-23 from advance_board's own inline block (web-UI slice, task #79) --
    computes this round's final per-hero mob_name assignments (applying blind-redraw to every
    contested Node's non-first claimant, per OPEN_QUESTIONS.md's locked rule) WITHOUT running
    any combat or mutating board.pending_declarations. Pure other than the level-deck draws a
    redraw itself performs (see _blind_redraw's own docstring) -- reads board.pending_declarations,
    returns a corrected copy.

    Exists as its own callable because a human-facing web driver needs the FINAL mob (post-
    redraw, if contested) before it can show a human their hand and let them plan a pull --
    that has to happen strictly BEFORE advance_board's own combat-resolution loop runs, not
    inside it (a web request/response can't pause mid-loop the way a terminal's blocking input()
    can). advance_board itself still calls this first thing when its own declarations= isn't
    given, so every existing AI-only caller (run_competitive_chain, this file's own docstring
    examples) is completely unaffected -- see advance_board's own docstring for the two-call
    contract a web driver uses instead."""
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
    return declarations


def advance_board(board, class_names, rng, risk_tolerance_base, risk_only_as_last_resort,
                   decide_fns=None, declarations=None):
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

    decide_fns (checkpointed 2026-08-23): optional {hero_idx: decide_fn} dict, forwarded to
    each hero's own apply_travel_action call. None/missing entries default to None (solver-
    automatic), matching every existing caller exactly -- a human-facing multiplayer driver
    supplies a real decide_fn only for its human-controlled hero_idx(es), leaving every
    AI-controlled hero (including every hero in the existing AI-only run_competitive_chain,
    which never passes this parameter at all) untouched.

    declarations (checkpointed 2026-08-23, task #79): optional pre-resolved dict from
    _resolve_contested_declarations, skipping this function's own call to it. None (every
    existing caller) is unchanged -- resolves contested Nodes itself, as always. A web driver
    calls _resolve_contested_declarations directly FIRST (to learn each human's final,
    post-redraw mob before asking them to plan a pull), then passes the SAME dict back in here
    so the blind-redraw math (which draws real cards from the level deck) never runs twice for
    the same round.

    Mutates every declared hero and board in place. Returns {hero_idx: result_dict} (same
    per-action-type shapes apply_travel_action's own docstring already documents), or None if
    still waiting on at least one hero's declaration."""
    decide_fns = decide_fns or {}
    if len(board.pending_declarations) < len(board.heroes):
        return None

    if declarations is None:
        declarations = _resolve_contested_declarations(board, rng)

    touched_zone_levels = set()
    results = {}
    for hero_idx, action in declarations.items():
        hero = board.heroes[hero_idx]
        zone_or_border, _node = hero.position
        if isinstance(zone_or_border, int) and action["type"] in ("declare_node", "use_scroll", "use_smoke_bomb"):
            touched_zone_levels.add((zone_or_border, TIER_TO_LEVEL[M.ZONE_TIER[zone_or_border]]))
        results[hero_idx] = apply_travel_action(hero, action, class_names[hero_idx], board, rng,
                                                  risk_tolerance_base, risk_only_as_last_resort,
                                                  defer_zone_discard=True,
                                                  decide_fn=decide_fns.get(hero_idx))

    for zone_id, level in touched_zone_levels:
        B.discard_zone(board, zone_id, level)

    board.priority_token_holder = (board.priority_token_holder + 1) % len(board.heroes)
    board.pending_declarations.clear()
    return results


def resolve_border_crossing(hero, class_name, border_name, target_zone, mob_name, rng,
                             risk_tolerance_base, risk_only_as_last_resort, decide_fn=None, hand=None):
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

    decide_fn (checkpointed 2026-08-23): forwarded to macro_sim._engine_pull unchanged -- None
    keeps the crossing's pull solver-automatic; a human-facing driver's own callback plays the
    hand instead. The consumable-substitution/risk-gate logic above this stays automatic
    either way (matches this function's own "no decline path once committed" rule) -- decide_fn
    only ever governs which cards get played, never whether the crossing is attempted. hand:
    same passthrough, see _pull_and_resolve's own docstring.

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
                    M._remove_food(hero.bag, i)
                    hero.consumables_used["food"] += 1
                    break
                if M._is_potion_slot(slot):
                    hero.hp = min(hero.max_hp, hero.hp + M.POTION_HEAL)
                    M._remove_item(hero.bag, hero.locked, "potion", 1)
                    hero.consumables_used["potion"] += 1
                    break

        if hand is None:
            hand = rng.choice(mod.ALL_HANDS)
        win, final_hp, final_rounds = M._engine_pull(class_name, mob_name, hand, pattern, mob_hp, hero.hp,
                                                       decide_fn=decide_fn)
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
                M._remove_food(hero.bag, food_index)
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
                              risk_tolerance, risk_tolerance_base, risk_only_as_last_resort,
                              decide_fn=None):
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
    ...}) if the hero died again attempting it.

    decide_fn (checkpointed 2026-08-23): forwarded to resolve_border_crossing/resolve_node_pull
    unchanged -- None keeps the forced recovery pull solver-automatic, matching run_solo_trip's
    own call exactly; a human-facing driver's own callback plays the recovery hand too (WHICH
    Node/crossing is attempted stays forced either way -- decide_fn never affects that)."""
    corpse = hero.corpse_node
    if isinstance(corpse, str) and corpse.startswith("border:"):
        _, border_name, _origin_zone, target_zone_s = corpse.split(":")
        target_zone = int(target_zone_s)
        tier = M.ZONE_TIER[target_zone]
        level_deck = board.level_decks[TIER_TO_LEVEL[tier]]
        mob_name = scouted_pull_from_deck(class_name, level_deck, rng)
        outcome = resolve_border_crossing(hero, class_name, border_name, target_zone, mob_name, rng,
                                           risk_tolerance_base, risk_only_as_last_resort,
                                           decide_fn=decide_fn)
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
                                 suppress_loot=True, decide_fn=decide_fn)
    B.discard_zone(board, zone_id, level)
    if outcome["outcome"] == "died":
        return {"alive": False, "recovered": False, "death_node": node_name}
    hero.corpse_node = None
    return None


def apply_recovery_post_processing(hero):
    """Unlocks every Bag slot after a successful corpse recovery -- extracted 2026-08-23 from
    run_solo_chain's own inline block (task #67-adjacent human-CLI work) so a human-facing
    driver replaying the same trip/death/recovery cycle by hand doesn't reimplement this
    itself. Trivial, but kept as a named function rather than inlined twice for the same
    reason every other shared-tail piece in this module is factored out: a future change to
    the unlock rule (e.g. gating it on WHERE the corpse was recovered) would otherwise have to
    be remembered and applied in two places by hand.

    Mutates hero in place. No return value."""
    hero.locked = [False] * len(hero.locked)


def apply_death_post_processing(hero, quest_pool, death_node):
    """Locks the Bag, bumps decay, sets the new corpse_node, and respawns the hero at the
    nearest Town -- extracted 2026-08-23 from run_solo_chain's own inline death block (see
    that function's own docstring for the full reasoning behind each piece: why bag-lock,
    why +1 decay here specifically rather than +2, why respawn position reads the ORIGIN zone
    for a mid-crossing death). Factored out so a human-facing driver reproducing the same
    solo death/recovery cycle calls the identical code run_solo_chain already uses, rather
    than a second, hand-written copy that could quietly drift from it.

    Mutates hero in place. No return value."""
    for i, slot in enumerate(hero.bag):
        if slot is not None:
            hero.locked[i] = True
    for loot in hero.active_quests:
        q = quest_pool[loot]
        hero.decay_stage[loot] = min(hero.decay_stage.get(loot, 0) + 1, len(q["gold_ladder"]) - 1)
    hero.corpse_node = death_node
    if death_node.startswith("border:"):
        _, _, origin_zone_s, _ = death_node.split(":")
        hero.position = (int(origin_zone_s), "town")
    else:
        hero.position = (M.NODE_ZONE[death_node], "town")


def apply_competitive_death_post_processing(hero, quest_pool):
    """Competitive mode's own death rule -- deliberately NOT apply_death_post_processing (solo's
    version): no Bag lock, no corpse_node, immediate full-HP respawn, hero.alive reset True
    right away. Extracted 2026-08-23 from run_competitive_chain's own inline block (see that
    function's own docstring for the full reasoning: locking with no recovery mechanic to ever
    undo it would be a one-way, permanent loss of already-collected loot, worse than not
    locking at all -- caught live from a real run where a hero re-ground the same already-
    complete quest forever because its loot had gone permanently uncountable).

    Extracted so a human-facing multiplayer driver shares this exact rule for its human-
    controlled hero(es) too, rather than a second hand-written copy that could quietly drift
    from run_competitive_chain's own (e.g. by accidentally applying solo's bag-lock instead).

    Mutates hero in place. No return value."""
    for loot in hero.active_quests:
        q = quest_pool[loot]
        hero.decay_stage[loot] = min(hero.decay_stage.get(loot, 0) + 1, len(q["gold_ladder"]) - 1)
    hero.alive = True
    hero.hp = hero.max_hp
    zone_id = hero.position[0] if isinstance(hero.position[0], int) else 1
    hero.position = (zone_id, "town")


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
    M._add_food(hero.bag, hero.locked)  # matches _trip_chain's own starting loadout
    if class_name in M.LEVEL2_PURCHASED_ORDER:
        hero.skill_purchase_order = list(range(len(M.LEVEL2_PURCHASED_ORDER[class_name])))
        rng.shuffle(hero.skill_purchase_order)
    purchase_queue = M._build_purchase_queue(class_name, bag_queue_position)
    level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
    board = B.BoardState(mode="solo", heroes=[hero], zones={}, level_decks=level_decks)
    board.setup_quests(rng)

    # Chain-init Town moment: picks up the initial active_quests log (nothing to turn in yet,
    # matching _trip_chain's own pre-loop `active_quests = rng.sample(...)`).
    init_result = resolve_town_turn(hero, class_name, strategy, purchase_queue, purchase_policy, rng, board)
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
            apply_recovery_post_processing(hero)

        if not trip_result["alive"]:
            apply_death_post_processing(hero, quest_pool, trip_result["death_node"])

        town_result = resolve_town_turn(hero, class_name, strategy, purchase_queue, purchase_policy, rng, board)
        yield (trip_result["alive"], town_result["gold_after_turnin"], hero.xp,
               town_result["quests_completed"], prev_trainer_turn, hero.turns)
        prev_trainer_turn = town_result["trainer_turn"]


def _route_toward_zone(actions, zone_or_border, target_zone):
    """Shared movement-toward-a-target-Zone logic for _choose_field_action -- factored out
    2026-08-23 after the SAME class of routing bug was found and fixed twice in two separate,
    parallel copies of this logic (once for "no active quests, navigate to any valid-tier
    zone," once for "have an incomplete quest, but its Node isn't in my current zone") --
    keeping one shared implementation instead of two drifting copies.

    Real bugs this closes, both caught live tracing stuck multi-hundred-round runs, neither
    hypothetical: (1) a Zone can have more than one Border crossing (e.g. Zone 2 has both
    border_1_2 and border_2_3) -- grabbing "the first one returned" picks whichever border_name
    happens to sort first in M.BORDER_NODES, not necessarily the one actually closer to
    target_zone, which produced a hero stuck permanently crossing the WRONG border every round.
    (2) Standing on a Border Node, neither connected Zone is necessarily target_zone itself
    (e.g. on border_1_2 trying to reach Zone 3) -- grabbing "the first enter_zone option" was a
    coin flip that could send a hero backward into the Zone it just left, producing an infinite
    Zone<->Border oscillation that never made net progress.

    Fixed by always picking whichever crossing/entry minimizes REMAINING hop-distance to
    target_zone, never just "the first option" or "an exact match only." Returns an action
    dict, or None if zone_or_border already equals target_zone (nothing to route toward)."""
    if zone_or_border == target_zone:
        return None
    if isinstance(zone_or_border, int):
        crossings = [a for a in actions if a["type"] == "cross_border"]
        if crossings:
            return min(crossings, key=lambda a: M._hop_distance(a["target_zone"], target_zone))
    else:
        enters = [a for a in actions if a["type"] == "enter_zone"]
        if enters:
            return min(enters, key=lambda a: M._hop_distance(a["target_zone"], target_zone))
    return None


def _trainer_has_business(hero, class_name, purchase_queue):
    """Whether a hero standing in a Trainer Zone has any real reason to declare visit_trainer
    this round -- either the mandatory upgrade just became eligible, or an affordable skill is
    next in their shuffled purchase order. Shared by _choose_field_action's opportunistic
    Trainer-visit check and run_competitive_chain's Trainer-AI walk, so the two never disagree
    about whether there's business to be done. purchase_queue may be None (no info available,
    e.g. a direct unit-test call) -- treated as "no skill business," matching a class with no
    Level 2 slate at all."""
    if (class_name in M.LEVEL2_MANDATORY and hero.xp >= M.LEVEL2_XP_THRESHOLD
            and "mandatory" not in hero.acquired):
        return True
    if purchase_queue is None:
        return False
    skills_acquired_so_far = sum(1 for tag in hero.acquired if tag.startswith("skill_"))
    for item in purchase_queue:
        if item["kind"] != "skill" or item["tag"] in hero.acquired:
            continue
        if hero.skill_purchase_order:
            if (skills_acquired_so_far >= len(hero.skill_purchase_order)
                    or item["index"] != hero.skill_purchase_order[skills_acquired_so_far]):
                continue
        if hero.gold >= item["cost"]:
            return True
    return False


def _choose_field_action(hero_idx, board, class_names, quest_pools, rng, claimed_this_round,
                          purchase_queues=None):
    """AI decision for one hero's Move-and-declare choice this round (task #65) -- a
    deliberately simple MVP router, not a port of decide_travel's own fuller logic (that
    function's output format predates the Travel-seam's action-dict vocabulary and mutates
    hero state as a side effect of "deciding," which doesn't compose cleanly with a barrier
    where other heroes' choices matter). Priority, matching OPEN_QUESTIONS.md's now-resolved
    "Competitive AI" entry: heal/bag-deadlock relief first (private, doesn't need contention
    awareness); then an opportunistic Trainer visit (checkpointed 2026-08-24 -- only if already
    standing in a Trainer Zone AND there's real business there, per _trainer_has_business,
    matching OPEN_QUESTIONS.md's locked "opportunistic, not deliberate travel" stance on
    purchased upgrades, extended the same way to this newly-split-out node type); then an
    uncontested declare_node serving an incomplete quest (checking claimed_this_round -- what
    higher-priority heroes have ALREADY declared this same round, since advance_board doesn't
    care how pending_declarations got filled, only that it's complete before resolving); then a
    contested one anyway if that's all there is; then Flight Path if it reaches a quest-relevant
    Zone directly; then routing via _route_toward_zone toward whichever Zone actually gets the
    hero closer to their quest (or, with no active quests, toward the nearest zone that hands
    out quests at their XP tier); then return_to_town as the last resort.

    purchase_queues (checkpointed 2026-08-24): optional {hero_idx: purchase_queue} dict, passed
    to _trainer_has_business. None (e.g. a direct unit-test call) disables the opportunistic
    Trainer-visit check entirely rather than crashing -- matches _trainer_has_business's own
    None handling."""
    hero = board.heroes[hero_idx]
    quest_pool = quest_pools[hero_idx]
    actions = get_travel_actions(hero, board, rng)
    zone_or_border, _node = hero.position

    if hero.hp < hero.max_hp * 0.5:
        heal = next((a for a in actions if a["type"] in ("use_food", "use_potion")), None)
        if heal:
            return heal

    if isinstance(zone_or_border, int) and zone_or_border in M.TRAINER_ZONES:
        purchase_queue = purchase_queues[hero_idx] if purchase_queues else None
        if _trainer_has_business(hero, class_names[hero_idx], purchase_queue):
            visit = next((a for a in actions if a["type"] == "visit_trainer"), None)
            if visit:
                return visit

    if not M._bag_has_room(hero.bag, hero.locked):
        # Real bug caught live tracing a 300-round run where gold kept growing but XP froze at
        # exactly the Level 2 threshold forever: both Bag slots were completely full (2 of 3
        # active quests already loot-complete, sitting uncollected), but nothing in this
        # function ever routed toward Town to actually turn them in -- decide_travel's own
        # unconditional bag-deadlock handling never got ported here at all. Mirrors it: use any
        # available consumable to free a slot, else force a trip back to Town regardless of
        # whether any quest looks "incomplete" (a full bag with complete-but-unturned quests
        # can't make forward progress any other way).
        heal = next((a for a in actions if a["type"] in ("use_food", "use_potion")), None)
        if heal:
            return heal
        return next(a for a in actions if a["type"] == "return_to_town")

    incomplete = [loot for loot in hero.active_quests
                  if M._accessible_count(hero.bag, hero.locked, loot) < quest_pool[loot]["required"]]
    # remaining_needed identifies the single globally-closest-to-completion quest -- fixes a
    # real deadlock caught live TWICE: sorting only among whatever's dealt in the CURRENT zone
    # (an earlier version of this fix) still let a hero opportunistically pick up a DIFFERENT,
    # lower-priority quest's loot whenever their true top-priority quest's Node happened to be
    # in a different Zone -- since different active quests can live in different Zones, this
    # still fragmented the Bag across 2-3 partial quests over time, eventually filling every
    # slot with none of them complete and no Food/Potion left to free space. Fixed by ALWAYS
    # beelining for the single quest that needs the least additional loot, everywhere -- never
    # opportunistically declaring a different quest's Node just because it happens to be local.
    if not incomplete:
        # No active quests to route toward -- either the Level 1 starter batch is exhausted, or
        # the hero just crossed the Level 2 XP threshold and hasn't picked up Level 2 quests yet
        # (Town's own Phase 1 pickup only fires while standing IN a valid quest zone -- Zone
        # 1/2 for Level 1, Zone 3/4 for Level 2). Without this fallback a hero with an empty log
        # just bounces off return_to_town forever, since pickup never triggers from the wrong
        # zone -- a real bug caught live tracing a stuck 150-round run, not a hypothetical.
        valid_quest_zones = M.LEVEL2_QUEST_ZONES if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.LEVEL1_QUEST_ZONES
        # Level 2 only: "already in a valid zone" used to always mean "return_to_town is enough,"
        # assuming a fresh quest was guaranteed there -- true under the old unlimited-resample
        # model, false now that Level 2 quests come from a real, sometimes-empty Town Market.
        # Real bug found live 2026-08-28: a hero stuck in a zone whose market had nothing to
        # offer just cycled return_to_town forever, since nothing here ever considered the OTHER
        # quest zone instead. reachable_zones is only the zones whose market actually has
        # something -- falls back to the full set if BOTH are empty (genuine, rare total
        # exhaustion) so this never produces an impossible empty choice.
        reachable_zones = valid_quest_zones
        if hero.xp >= M.LEVEL2_XP_THRESHOLD:
            stocked = {z for z in valid_quest_zones if board.town_markets.get(z)}
            reachable_zones = stocked or valid_quest_zones
        if isinstance(zone_or_border, int) and zone_or_border in reachable_zones:
            return next(a for a in actions if a["type"] == "return_to_town")
        target_zone = min(reachable_zones, key=lambda z: M._hop_distance(zone_or_border, z))
        if isinstance(zone_or_border, int):
            flight = next((a for a in actions if a["type"] == "flight_path"), None)
            if flight and flight["target_zone"] == target_zone:
                return flight
        routed = _route_toward_zone(actions, zone_or_border, target_zone)
        if routed:
            return routed
        return next(a for a in actions if a["type"] == "return_to_town")

    remaining_needed = {loot: quest_pool[loot]["required"] - M._accessible_count(hero.bag, hero.locked, loot)
                         for loot in incomplete}
    top_priority_loot = min(incomplete, key=lambda loot: remaining_needed[loot])
    top_priority_nodes = {n for n, (_tier, loot) in M.NODES.items() if loot == top_priority_loot}

    declares = [a for a in actions if a["type"] == "declare_node"]
    top_declares = [a for a in declares if a["node_name"] in top_priority_nodes]
    uncontested = [a for a in top_declares if a["node_name"] not in claimed_this_round]
    if uncontested:
        return uncontested[0]
    if top_declares:
        return top_declares[0]

    # The single top-priority quest's Node isn't declarable here this round (wrong Zone, or
    # Spice-dealt) -- route toward ITS OWN Zone specifically, never toward "any" quest zone in
    # general (that generality is exactly what let a different, lower-priority quest get
    # opportunistically picked up along the way in the bug this replaces).
    target_zone = M.NODE_ZONE[next(iter(top_priority_nodes))]
    if isinstance(zone_or_border, int):
        flight = next((a for a in actions if a["type"] == "flight_path"), None)
        if flight and flight["target_zone"] == target_zone:
            return flight
    routed = _route_toward_zone(actions, zone_or_border, target_zone)
    if routed:
        return routed

    return next(a for a in actions if a["type"] == "return_to_town")


def run_competitive_chain(class_names_list, strategy, rng, max_rounds,
                           risk_tolerance_base=M.RISK_TOLERANCE_BASE, risk_only_as_last_resort=True):
    """First driver that actually plays a competitive N=2-4 game through declare_for_hero/
    advance_board in a loop (task #65) -- proves the Move-and-declare barrier (task #64) works
    end to end, not just in isolation. class_names_list is a plain list, 2-4 entries (any class
    mix); every hero starts in Zone 1's Town, matching run_solo_chain's own starting loadout.

    Round structure, matching OPEN_QUESTIONS.md's locked turn-phase order: each outer round
    first resolves a full Town visit (independently, no barrier -- Town "is never contested,"
    board_state.py's own docstring) for any hero currently standing there, THEN runs one
    Move-and-declare cycle for whoever's now out in the field. advance_board requires an entry
    in pending_declarations for EVERY hero in board.heroes, not just field-active ones (that
    contract was already built and verified in task #64, not changed here) -- so a hero who
    just resolved their Town visit, or who's dead-and-respawning, submits a harmless
    return_to_town no-op this round instead (their position is already Town, so it changes
    nothing; matches the barrier's own existing shape rather than requiring a change to it).

    AI declaration order follows the priority token each round (see _choose_field_action's own
    docstring for the resolved contested-Node logic this enables) -- computed BEFORE calling
    advance_board, since advance_board only ever reads the final dict, not how it was filled.

    Death handling, deliberately simplified versus run_solo_chain's own -- and simplified
    FURTHER than task #64's original note (which said "locks the Bag... skips the forced-
    recovery-pull mechanic"): the Bag does NOT get locked on death here at all, unlike solo.
    Locking without any way to ever unlock it (no recovery mechanic exists for this driver) is
    strictly worse than not locking -- caught live tracing a real run: once a hero died once,
    every non-empty slot locked permanently, silently making already-collected complete-quest
    loot uncountable forever, so the hero kept re-grinding toward a "still incomplete" quest it
    had actually already finished, dying at the same lethal crossing every single round with no
    way out. On death: applies +1 decay to active quests (matching the real penalty for losing
    a trip to a mistake) and respawns at full HP in the nearest Town, bag untouched. Real
    multi-hero corpse recovery (lock + forced recovery pull, matching solo's actual fidelity)
    is still genuinely unbuilt follow-up work, not silently dropped -- just no longer paired
    with a lock that has nothing to unlock it.

    Yields one dict per round: {hero_idx: (alive, gold, xp, position, turns)} for every hero,
    turns being hero.turns (the real comparable unit, matching run_solo_chain's own yield) --
    letting
    a caller track the whole party's progress round by round."""
    n = len(class_names_list)
    class_names = dict(enumerate(class_names_list))
    heroes = []
    for class_name in class_names_list:
        mod = M.CARD_SOURCE[class_name]
        max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
        hero = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(1, "town"),
                               bag=[None] * M.BAG_SIZE, locked=[False] * M.BAG_SIZE)
        M._add_food(hero.bag, hero.locked)
        if class_name in M.LEVEL2_PURCHASED_ORDER:
            hero.skill_purchase_order = list(range(len(M.LEVEL2_PURCHASED_ORDER[class_name])))
            rng.shuffle(hero.skill_purchase_order)
        heroes.append(hero)
    purchase_queues = {i: M._build_purchase_queue(class_names_list[i], 0) for i in range(n)}
    level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
    board = B.BoardState(mode="competitive", heroes=heroes, zones={}, level_decks=level_decks)
    board.setup_quests(rng)

    for _round_num in range(max_rounds):
        for hero_idx, hero in enumerate(board.heroes):
            if hero.position[1] == "town":
                enter_town(hero, class_names[hero_idx], strategy, rng, board)
                while True:
                    town_actions = get_town_actions(hero, purchase_queues[hero_idx], board)
                    buyable = next((a for a in town_actions if a["type"] == "buy"), None)
                    take = next((a for a in town_actions if a["type"] == "take_quest"), None)
                    chosen = take if take else (buyable if buyable else next(a for a in town_actions if a["type"] == "leave_town"))
                    still_in_town = apply_town_action(hero, chosen, purchase_queues[hero_idx], board, rng)
                    if not still_in_town:
                        break
            elif hero.position[1] == "trainer":
                # Checkpointed 2026-08-24: Class Trainer split from Town into its own turn-
                # costing node type -- a hero can arrive here via a previous round's declared
                # visit_trainer (see _choose_field_action's own opportunistic check below), and
                # this is the AI-automatic Trainer walk, get_town_actions/apply_town_action
                # shared with Town, filtered by this "trainer" position marker.
                enter_trainer(hero, class_names[hero_idx])
                while True:
                    trainer_actions = get_town_actions(hero, purchase_queues[hero_idx], board)
                    buyable = next((a for a in trainer_actions if a["type"] == "buy"), None)
                    chosen = buyable if buyable else next(a for a in trainer_actions if a["type"] == "leave_trainer")
                    still_at_trainer = apply_town_action(hero, chosen, purchase_queues[hero_idx], board, rng)
                    if not still_at_trainer:
                        break

        field_idxs = [i for i, h in enumerate(board.heroes) if h.position[1] not in ("town", "trainer")]
        quest_pools = {i: (M.LEVEL2_QUESTS if board.heroes[i].xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS)
                       for i in field_idxs}
        claimed_this_round = set()
        for hero_idx in [i for i in _priority_order(board) if i in field_idxs]:
            action = _choose_field_action(hero_idx, board, class_names, quest_pools, rng, claimed_this_round,
                                           purchase_queues=purchase_queues)
            if action["type"] == "declare_node":
                claimed_this_round.add(action["node_name"])
            declare_for_hero(board, hero_idx, action)
        for hero_idx in range(n):
            if hero_idx not in field_idxs:
                declare_for_hero(board, hero_idx, {"type": "return_to_town" if board.heroes[hero_idx].position[1] == "town" else "visit_trainer"})

        results = advance_board(board, class_names, rng, risk_tolerance_base, risk_only_as_last_resort)

        for hero_idx in field_idxs:
            hero = board.heroes[hero_idx]
            result = results[hero_idx]
            if result.get("outcome") == "scouted_pull_reveal":
                # cross_border only reveals candidates (task #63) -- it doesn't resolve the
                # crossing. Pick one immediately and actually attempt it, same as any
                # human-facing driver of this seam has to (see verify_board_engine_travel_
                # actions.py's own smoke-test driver for the identical pattern).
                picked_mob = rng.choice(result["candidates"])
                result = resolve_border_crossing(hero, class_names[hero_idx], result["border_name"],
                                                  result["target_zone"], picked_mob, rng,
                                                  risk_tolerance_base, risk_only_as_last_resort)
                results[hero_idx] = result
            if result.get("outcome") == "died":
                apply_competitive_death_post_processing(hero, quest_pools[hero_idx])

        yield {i: (h.alive, h.gold, h.xp, h.position, h.turns) for i, h in enumerate(board.heroes)}
