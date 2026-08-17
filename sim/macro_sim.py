"""
Minimal macro-loop simulator -- tests the locked Bag Tetris / Food-Potion /
Decaying Bounty design (DESIGN_DOC.md SS3/SS5/SS6) against the same
exact-enumeration combat layer the rest of this project already trusts,
instead of trusting the design as an untested instinct.

Sits on top of condensed_trip.py, doesn't modify it. Reuses its exact
solver (_best_line/_simulate) for every pull -- no averaging anywhere,
matching how this project caught real bugs (Cleric's equilibrium exploit,
Wizard's real glass-cannon shape) specifically by checking distributions
and extremes, not means.

Map model, confirmed directly rather than assumed: a Zone contains several
Nodes, including Town itself, and intra-Zone movement between any of them
is free (0 cost -- Golden Rule 1, no movement tax). The actual cost of
visiting Town is Decaying Bounty quest decay, not distance.

Bag model: a slot holds a mix of whatever loot is won while it's "open" --
not one-type-per-slot ("identical cards stack infinitely" describes what
happens with duplicates, it isn't a restriction against mixing). The bag
is now persistent state across a whole chain of trips, not reset each
call, because Town only does specific, limited things to it (see below) --
everything else about the bag carries forward exactly as the hero left it.

What actually happens at Town (confirmed directly, not assumed):
- HP restores to full. Always, automatically.
- Every non-locked slot's "closed" flag clears (Food's mid-trip lock lifts).
  LOCKED slots (see Death, below) do NOT unlock just by visiting Town.
- Whatever's still incomplete in the quest log decays one stage. This is
  triggered by *leaving* Town (heading back out), not by the visit itself.
- Everything else is the player's choice: turn in whatever's complete,
  sell whatever they want, buy a consumable if they can afford it. Loot
  left unsold just sits in the bag -- and if it's still occupying a slot,
  that's one less slot available for a fresh consumable next trip, which
  is a real, self-enforcing cost for not selling promptly.

Death: if a pull actually kills the hero (see RISK_TOLERANCE below -- this
can only happen if risk_tolerance > 0, since at 0 the hero never attempts
a pull any hand could lose), a corpse marker is left at that node and the
hero returns to Town. Every bag slot that currently holds anything --
loot or an unused consumable -- LOCKS: its contents don't count toward
quest completion and can't be added to, until the hero physically returns
to the death node. All quests currently in the active log take an
immediate 2-stage decay hit (vs. 1 for a normal incomplete return), still
capped at "nothing." Locking persists across Town visits (unlike a
Food-closed slot); if the corpse is never retrieved, that capacity is
gone for good.

Corpse recovery: the trip *after* a death is forced to spend its first
pull at the death node before any normal questing -- a random mob still
drawn from that node's tier, same as any visit, and it earns no loot
either way. Surviving that pull (win or flee, doesn't matter) unlocks
every previously locked slot. Dying on it triggers the exact same death
handling again (a fresh corpse at that same node) -- a real spiral risk,
not special-cased away. If the hero can't safely attempt it (no
consumable to make the risk acceptable), the trip ends with the corpse
still unrecovered and tried again next trip.

RISK_TOLERANCE: replaces a hard "never attempt a pull any single hand
could lose" rule with a tunable fraction -- at 0.0, behavior is identical
to the old hard block; above 0 (0.15 by default now -- a real human
wouldn't refuse a pull just because one bad hand out of many exists),
the policy will knowingly attempt pulls with some chance of death,
trading risk for progress.

Scope: Zone 1 only, four farmable Standard-tier Nodes/quests, of which a
given trip's quest log only holds ACTIVE_QUEST_COUNT (3) at a time. All
four nodes draw from the same Standard mob pool, so which 3-of-4 quests a
given trip gets is cosmetic, not a different challenge. Town's Spike-tier
Elite node is still deferred. Inter-Zone Border Toll travel isn't modeled
at all.
"""
import random

import condensed_cleric as C
import condensed_paladin as P
import condensed_ranger as G
import condensed_rogue as R
import condensed_runecaster as N
import condensed_trip as T
import condensed_warrior as W
import condensed_wizard as Z
import condensed_druid as D
import condensed_necromancer as Nc

CARD_SOURCE = {"warrior": W, "wizard": Z, "cleric": C, "paladin": P, "rogue": R, "ranger": G, "runecaster": N,
               "druid": D, "necromancer": Nc}
HP_ATTR = {"warrior": "WARRIOR_HP", "wizard": "WIZARD_HP", "cleric": "CLERIC_HP", "paladin": "PALADIN_HP",
           "rogue": "ROGUE_HP", "ranger": "RANGER_HP", "runecaster": "RUNECASTER_HP", "druid": "DRUID_HP",
           "necromancer": "NECROMANCER_HP"}
HAS_STANCE = {"warrior": True, "wizard": False, "cleric": False, "paladin": False,
              "rogue": False, "ranger": False, "runecaster": False, "druid": False, "necromancer": False}

# node name -> (difficulty tier in condensed_trip.MOB_TIERS, loot card name)
# A node is a difficulty, not one fixed mob -- each pull draws a random mob
# from that tier's pool (condensed_trip.MOB_TIERS), specifically so no
# single mob's kit-specific skew defines what "farming this node" means
# for every class (exactly the failure mode that sank the old, hand-picked
# roster -- see CLASS_BALANCE_GUIDE.md's "Retired roster" section).
NODES = {
    "waystation": ("standard", "Pilfered Goods"),
    "cove": ("standard", "Syndicate Ledger"),
    "ridge": ("standard", "Contraband Crates"),
    "marsh": ("standard", "Stolen Signet"),
}
ACTIVE_QUEST_COUNT = 3  # each trip's quest log holds this many of the below, not all of them

# loot card name -> quest requirement (keyed by loot type -- one quest per node)
#
# XP = required, flat 1-XP-per-loot (locked -- see CLASS_BALANCE_GUIDE.md).
# Gold_ladder derived from quest_cost_gauntlet.py, not hand-picked: measured
# that a 2/3/4-loot quest's "quicker half" of completions land at full
# Gold-tier ~100% of the time (they reliably finish in a single trip), so
# there's no reason for gold to scale with required in that range -- they
# all pay the same 1-trip rate G. A 5-loot quest is where that stops being
# true (quicker-half split ~37% Gold / ~63% Silver, avg 1.63 trips), so its
# Gold-tier is set higher (~2.2x G) so that blended outcome still averages
# out to fair per-trip pay for the players who ARE finishing it quickly, not
# just the unlucky slow tail. Silver/Bronze step down at roughly 60% of the
# previous stage, matching the decay-ladder shape already used elsewhere.
QUESTS = {
    "Pilfered Goods":    dict(required=2, base_xp=2, gold_ladder=[4, 2, 1, 0]),
    "Syndicate Ledger":  dict(required=3, base_xp=3, gold_ladder=[4, 2, 1, 0]),
    "Contraband Crates": dict(required=4, base_xp=4, gold_ladder=[4, 2, 1, 0]),
    "Stolen Signet":     dict(required=5, base_xp=5, gold_ladder=[9, 5, 3, 0]),
}

FOOD_COST = 2
POTION_COST = 4
POTION_HEAL = 8
BAG_UPGRADE_COST = 16  # back-solved via run_to_bag_upgrade sweeps against the
# new required-varied QUESTS table to land at ~4.5 trips (~30 pulls) before
# affording the upgrade -- targeted range for "earned, not repetitive yet"
# given a 5-mob Standard roster (see macro_sim.py's BAG_UPGRADE_COST usage
# and the conversation that derived this in CLASS_BALANCE_GUIDE.md).
BAG_SIZE = 2
RISK_TOLERANCE = 0.15  # fraction of hands allowed to be lethal, when this pull would complete a quest
RISK_TOLERANCE_BASE = 0.0  # fraction allowed otherwise (quest not one pull from done, or a recovery pull)


def _pull_exceeds_risk(mod, has_stance, mob_name, class_name, hp, risk_tolerance):
    """True if the fraction of hands that would be lethal this pull (under
    optimal play) exceeds risk_tolerance. Short-circuits as soon as the
    answer is settled instead of always enumerating every hand -- each
    T._best_line call is a real exact solve (permutation enumeration), so
    this matters a lot at scale. At risk_tolerance=0 (the default) this
    stops at the very first lethal hand found, exactly matching the old
    hard-block rule's cost; higher tolerances still short-circuit once
    enough lethal hands are found to already exceed the threshold, even
    if not every hand has been checked."""
    pattern, mob_hp = T.MOBS[mob_name][class_name]
    hands = mod.ALL_HANDS
    threshold_count = risk_tolerance * len(hands)
    lethal = 0
    for hand in hands:
        if T._best_line(mod, has_stance, hand, pattern, mob_hp, hp)[2] <= 0:
            lethal += 1
            if lethal > threshold_count:
                return True
    return False


def _open_loot_slot_index(bag, locked):
    """Index of the currently open (unclosed, unlocked) loot-holding slot, if any."""
    for i, slot in enumerate(bag):
        if not locked[i] and isinstance(slot, dict) and not slot["closed"]:
            return i
    return None


def _bag_has_room(bag, locked):
    """Is there an open loot slot, or an empty unlocked slot to open one?"""
    if _open_loot_slot_index(bag, locked) is not None:
        return True
    return any(not locked[i] and bag[i] is None for i in range(len(bag)))


def _add_loot(bag, locked, loot_name):
    """Add one unit of loot_name to the open loot slot -- any mix of loot
    types shares one slot while it's open. Opens a fresh (unlocked, empty)
    slot if there's no open one right now. Returns False only if there's
    truly no room (every slot closed, locked, or held by an unused
    consumable) -- callers should check _bag_has_room before relying on
    this to always succeed."""
    i = _open_loot_slot_index(bag, locked)
    if i is not None:
        bag[i]["loot"][loot_name] = bag[i]["loot"].get(loot_name, 0) + 1
        return True
    for j, slot in enumerate(bag):
        if not locked[j] and slot is None:
            bag[j] = {"loot": {loot_name: 1}, "closed": False}
            return True
    return False


def _close_active_loot_slot(bag, locked):
    """Locks (closes) whatever's in the currently-open loot slot, if any.
    A no-op if there's no open slot right now."""
    i = _open_loot_slot_index(bag, locked)
    if i is not None:
        bag[i]["closed"] = True


def _accessible_count(bag, locked, loot_name):
    """Total loot_name sitting in non-locked slots -- what the hero can
    actually use toward quest completion right now. Locked (post-death)
    contents don't count until recovered."""
    return sum(
        slot["loot"].get(loot_name, 0)
        for i, slot in enumerate(bag)
        if not locked[i] and isinstance(slot, dict)
    )


def _remove_loot(bag, locked, loot_name, amount):
    """Removes up to `amount` of loot_name from accessible (non-locked)
    slots -- used when a quest is turned in and its loot is handed over.
    A slot that ends up holding nothing of any type goes back to None
    (reopens), even if it was previously closed."""
    remaining = amount
    for i, slot in enumerate(bag):
        if remaining <= 0:
            break
        if locked[i] or not isinstance(slot, dict):
            continue
        have = slot["loot"].get(loot_name, 0)
        if have <= 0:
            continue
        take = min(have, remaining)
        slot["loot"][loot_name] -= take
        if slot["loot"][loot_name] <= 0:
            del slot["loot"][loot_name]
        remaining -= take
        if not slot["loot"]:
            bag[i] = None


def run_one_trip(class_name, strategy, rng, bag=None, locked=None, active_quests=None,
                  bag_size=BAG_SIZE, risk_tolerance=RISK_TOLERANCE,
                  risk_tolerance_base=RISK_TOLERANCE_BASE, corpse_node=None,
                  risk_only_as_last_resort=True):
    """One field trip: alternates between the active Nodes, prioritizing
    whichever quest isn't yet satisfied.

    If bag/locked aren't passed in, this is a standalone one-off trip (the
    single-trip completion-rate measurement) -- a fresh bag is created and
    seeded with the strategy's one consumable, matching the locked "1 Food
    item" starting loadout. A chained multi-trip run (_trip_chain) instead
    passes in the *persisted* bag/lock state from Town, since the bag no
    longer resets between trips (see module docstring for what Town
    actually does to it).

    If active_quests isn't passed in, a fresh random log is drawn; a
    chained run passes in the persisted log so an incomplete quest is
    actually followed up on, not randomly swapped out.

    Corpse recovery: if corpse_node is set, the *first* pull this trip is
    forced to be at that node (a random mob still drawn from its tier, same
    as any visit) instead of normal quest routing -- getting there is free,
    but arriving forces this pull, whether or not the hero wanted it for
    any quest. No loot is gained from it even on a win. Surviving it (win
    or flee, doesn't matter which) recovers the corpse -- every previously
    locked slot unlocks, contents fully usable again -- and normal quest
    routing resumes for the rest of the trip. Dying on it triggers the
    same death handling as any other death (a fresh corpse at that same
    node, see module docstring) -- a real spiral risk, not special-cased
    away. If the hero can't survive the recovery pull and has no
    consumable to make it safe, the trip ends with the corpse still
    unrecovered, tried again next trip.

    Bag-deadlock: if there's truly no room for more loot (every slot
    closed, locked, or holding an unused consumable) and Food is
    available, it's eaten specifically to free its own slot (this is a
    capacity move, not a survival one, but Food's heal-to-max effect is
    unconditional regardless of motive). If there's no Food either, the
    trip ends -- no further progress is possible this excursion.

    Risk: a pull is only attempted if the fraction of hands that would be
    lethal is <= risk_tolerance; otherwise a consumable is used (Food
    heals to max and closes the active loot slot; Potion heals
    POTION_HEAL and touches nothing else) if available, or the trip ends.
    At risk_tolerance > 0, a pull can still actually kill the hero if the
    drawn hand is one of the lethal ones -- that's a real death, handled
    by the caller (see module docstring)."""
    mod = CARD_SOURCE[class_name]
    has_stance = HAS_STANCE[class_name]
    max_hp = float(getattr(mod, HP_ATTR[class_name]))
    hp = max_hp

    if active_quests is None:
        active_quests = rng.sample(list(QUESTS.keys()), ACTIVE_QUEST_COUNT)

    if bag is None:
        bag = [None] * bag_size
        locked = [False] * bag_size
        if strategy == "food_only":
            bag[0] = "food"
        elif strategy == "potion_only":
            bag[0] = "potion"

    consumables_used = {"food": 0, "potion": 0}
    pulls = 0
    recovered = False
    pending_recovery = corpse_node

    while True:
        if pending_recovery is not None:
            node_name = pending_recovery
            tier, loot_name = NODES[node_name]
            loot_name = None  # a recovery pull earns no loot, regardless of outcome
        else:
            incomplete = [loot for loot in active_quests
                          if _accessible_count(bag, locked, loot) < QUESTS[loot]["required"]]
            if not incomplete:
                return dict(completed=True, died=False, recovered=recovered, hp=hp, pulls=pulls,
                            bag=bag, locked=locked, active_quests=active_quests,
                            consumables_used=consumables_used)

            if not _bag_has_room(bag, locked):
                food_index = next((i for i, s in enumerate(bag) if not locked[i] and s == "food"), None)
                if food_index is None:
                    return dict(completed=False, died=False, recovered=recovered, hp=hp, pulls=pulls,
                                bag=bag, locked=locked, active_quests=active_quests,
                                consumables_used=consumables_used)
                hp = max_hp
                bag[food_index] = None
                consumables_used["food"] += 1

            # route to whichever node produces the first still-incomplete quest's loot
            node_name = next(n for n, (tier, loot) in NODES.items() if loot == incomplete[0])
            tier, loot_name = NODES[node_name]

        # the specific mob is revealed on arrival, same as turning over a
        # monster token at the table -- drawn before the consumable
        # decision, not hidden from it. Weighted, not uniform -- see
        # condensed_trip.MOB_TIER_WEIGHTS (same weights for every class,
        # only how often each mob comes up changes).
        pool, weights = T.mob_pool_weights(tier)
        mob_name = rng.choices(pool, weights=weights, k=1)[0]

        # Fluid risk: worth the higher tolerance only when this specific pull,
        # if won, would complete the quest being pursued -- a recovery pull
        # (loot_name is None) or a quest still 2+ away uses the lower base
        # tolerance instead. Matches how an actual player weighs the bet:
        # push your luck to close something out, don't for a quest you've
        # barely started.
        one_pull_from_done = (loot_name is not None
                               and _accessible_count(bag, locked, loot_name) == QUESTS[loot_name]["required"] - 1)
        # Default policy (locked): even a near-completion pull only gets the
        # higher tolerance as a genuine last resort -- if there's still an
        # unlocked Food or Potion sitting in the bag, a rational player would
        # rather use it (or just retreat) than gamble with a safety net
        # unused. Only once truly out of options does risk become worth it.
        # Proven via decay_report(): cuts death rates substantially with no
        # observed downside (Cleric -58%, Wizard -36%, Warrior -17%, Paladin
        # -34% on avg deaths/run, food_only strategy). risk_only_as_last_resort
        # stays a parameter (not hardcoded) only so a future test can turn it
        # off to compare against a less-rational baseline; every call site
        # defaults it True.
        if risk_only_as_last_resort:
            has_consumable = any(not locked[i] and bag[i] in ("food", "potion") for i in range(len(bag)))
            worth_the_risk = one_pull_from_done and not has_consumable
        else:
            worth_the_risk = one_pull_from_done
        effective_risk_tolerance = risk_tolerance if worth_the_risk else risk_tolerance_base

        if _pull_exceeds_risk(mod, has_stance, mob_name, class_name, hp, effective_risk_tolerance):
            consumed = None
            for i, slot in enumerate(bag):
                if locked[i]:
                    continue
                if slot == "food":
                    hp = max_hp
                    bag[i] = None  # Food itself frees its own slot on use
                    _close_active_loot_slot(bag, locked)
                    consumed = "food"
                    break
                if slot == "potion":
                    hp = min(max_hp, hp + POTION_HEAL)
                    bag[i] = None  # drinking a Potion frees its slot back to empty, no other effect
                    consumed = "potion"
                    break
            if consumed:
                consumables_used[consumed] += 1
                if _pull_exceeds_risk(mod, has_stance, mob_name, class_name, hp, effective_risk_tolerance):
                    return dict(completed=False, died=False, recovered=recovered, hp=hp, pulls=pulls,
                                bag=bag, locked=locked, active_quests=active_quests,
                                consumables_used=consumables_used)
            else:
                return dict(completed=False, died=False, recovered=recovered, hp=hp, pulls=pulls,
                            bag=bag, locked=locked, active_quests=active_quests,
                            consumables_used=consumables_used)

        pattern, mob_hp = T.MOBS[mob_name][class_name]
        hand = rng.choice(mod.ALL_HANDS)
        seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, pattern, mob_hp, hp)
        win, final_hp, final_rounds = T._simulate(mod, has_stance, seq, stance, pattern, mob_hp, hp)
        hp = final_hp
        pulls += 1

        if hp <= 0:
            return dict(completed=False, died=True, recovered=recovered, death_node=node_name, hp=0,
                        pulls=pulls, bag=bag, locked=locked, active_quests=active_quests,
                        consumables_used=consumables_used)

        if pending_recovery is not None:
            # survived the recovery pull -- win or flee, doesn't matter, the corpse is retrieved
            pending_recovery = None
            recovered = True
            continue

        if win:
            if not _add_loot(bag, locked, loot_name):
                # shouldn't happen given the _bag_has_room check above, but stay safe
                return dict(completed=False, died=False, recovered=recovered, hp=hp, pulls=pulls,
                            bag=bag, locked=locked, active_quests=active_quests,
                            consumables_used=consumables_used)
        # if not win (fled), no loot gained, but the pull still happened -- loop continues


def _leaving_town_setup(strategy, bag, locked, gold):
    """Everything automatic that happens before heading back out: closed
    (not locked) slots reopen, and the strategy's one consumable gets
    restocked into an open empty slot if the hero doesn't already have
    one and can afford it. Returns the (possibly reduced) gold."""
    for i, slot in enumerate(bag):
        if not locked[i] and isinstance(slot, dict):
            slot["closed"] = False

    wanted = "food" if strategy == "food_only" else "potion" if strategy == "potion_only" else None
    if wanted:
        already_have = any(not locked[i] and bag[i] == wanted for i in range(len(bag)))
        cost = FOOD_COST if wanted == "food" else POTION_COST
        if not already_have and gold >= cost:
            empty_index = next((i for i in range(len(bag)) if not locked[i] and bag[i] is None), None)
            if empty_index is not None:
                bag[empty_index] = wanted
                gold -= cost
    return gold


def _trip_chain(class_name, strategy, rng, risk_tolerance=RISK_TOLERANCE,
                 risk_tolerance_base=RISK_TOLERANCE_BASE, bag_size=BAG_SIZE,
                 risk_only_as_last_resort=True):
    """Yields one (trip_num, result, gold, xp, decay_stage, corpse_node,
    quests_completed_this_trip) per trip, forever -- callers apply their
    own stop condition. Town behavior and death handling live here, once
    (see module docstring)."""
    gold = 0
    xp = 0
    decay_stage = {loot: 0 for loot in QUESTS}  # 0=Gold,1=Silver,2=Bronze,3=nothing
    active_quests = rng.sample(list(QUESTS.keys()), ACTIVE_QUEST_COUNT)
    bag = [None] * bag_size
    locked = [False] * bag_size
    corpse_node = None  # set on death; the next trip's first pull is forced there to recover it

    trip_num = 0
    while True:
        trip_num += 1
        gold = _leaving_town_setup(strategy, bag, locked, gold)

        result = run_one_trip(class_name, strategy, rng, bag=bag, locked=locked,
                               active_quests=list(active_quests), risk_tolerance=risk_tolerance,
                               risk_tolerance_base=risk_tolerance_base, corpse_node=corpse_node,
                               risk_only_as_last_resort=risk_only_as_last_resort)

        if result["recovered"]:
            for i in range(len(locked)):
                locked[i] = False
            corpse_node = None

        quests_completed_this_trip = 0
        if result["died"]:
            for i in range(len(bag)):
                if bag[i] is not None:
                    locked[i] = True
            for loot in active_quests:
                q = QUESTS[loot]
                decay_stage[loot] = min(decay_stage[loot] + 2, len(q["gold_ladder"]) - 1)
            corpse_node = result["death_node"]
        else:
            still_incomplete = []
            turned_in = []
            for loot in active_quests:
                q = QUESTS[loot]
                collected = _accessible_count(bag, locked, loot)
                if collected >= q["required"]:
                    gold += q["gold_ladder"][min(decay_stage[loot], len(q["gold_ladder"]) - 1)]
                    xp += q["base_xp"]
                    decay_stage[loot] = 0
                    _remove_loot(bag, locked, loot, collected)
                    turned_in.append(loot)
                else:
                    decay_stage[loot] = min(decay_stage[loot] + 1, len(q["gold_ladder"]) - 1)
                    still_incomplete.append(loot)

            refill_pool = [loot for loot in QUESTS if loot not in still_incomplete]
            newly_active = rng.sample(refill_pool, len(turned_in))
            active_quests = still_incomplete + newly_active
            quests_completed_this_trip = len(turned_in)

        yield trip_num, result, gold, xp, dict(decay_stage), corpse_node, quests_completed_this_trip


def run_to_bag_upgrade(class_name, strategy, rng, gold_goal=BAG_UPGRADE_COST, max_trips=200,
                        risk_tolerance=RISK_TOLERANCE, risk_tolerance_base=RISK_TOLERANCE_BASE,
                        risk_only_as_last_resort=True):
    """Chains full trip-cycles until gold_goal is reached (or max_trips runs out)."""
    trip_log = []
    for trip_num, result, gold, xp, decay_stage, corpse_node, quests_completed in _trip_chain(
            class_name, strategy, rng, risk_tolerance=risk_tolerance,
            risk_tolerance_base=risk_tolerance_base,
            risk_only_as_last_resort=risk_only_as_last_resort):
        trip_log.append(result)
        if gold >= gold_goal:
            return dict(trips=trip_num, gold=gold, xp=xp, log=trip_log)
        if trip_num >= max_trips:
            return dict(trips=None, gold=gold, xp=xp, log=trip_log)


def decay_stress_test(class_name, strategy, rng, chain_trips=20, risk_tolerance=RISK_TOLERANCE,
                       risk_tolerance_base=RISK_TOLERANCE_BASE, risk_only_as_last_resort=True):
    """Chains a fixed number of trips (not stopping at a gold goal) and
    tracks the worst decay_stage reached by any quest, the total quests
    completed over the whole chain, and whether the hero ever died."""
    worst_decay_stage = 0
    died_count = 0
    total_quests_completed = 0
    for trip_num, result, gold, xp, decay_stage, corpse_node, quests_completed in _trip_chain(
            class_name, strategy, rng, risk_tolerance=risk_tolerance,
            risk_tolerance_base=risk_tolerance_base,
            risk_only_as_last_resort=risk_only_as_last_resort):
        worst_decay_stage = max(worst_decay_stage, max(decay_stage.values()))
        total_quests_completed += quests_completed
        if result["died"]:
            died_count += 1
        if trip_num >= chain_trips:
            return dict(gold=gold, xp=xp, worst_decay_stage=worst_decay_stage,
                        final_decay_stage=decay_stage, died_count=died_count,
                        total_quests_completed=total_quests_completed,
                        avg_quests_per_trip=total_quests_completed / chain_trips,
                        ended_with_corpse=corpse_node is not None)


def compare_strategies(class_name, trials=500, seed=42, risk_tolerance=RISK_TOLERANCE,
                        risk_tolerance_base=RISK_TOLERANCE_BASE, risk_only_as_last_resort=True):
    """Prints both measurements (single-trip completion rate, trips-to-
    Bag-Upgrade) for food_only/potion_only/none, same table style as
    condensed_trip.full_report()."""
    strategies = ["none", "food_only", "potion_only"]
    print(f"=== {class_name.capitalize()}: single-trip completion rate ({trials} trials) ===")
    for strategy in strategies:
        rng = random.Random(seed)
        completed = sum(
            1 for _ in range(trials)
            if run_one_trip(class_name, strategy, rng, risk_tolerance=risk_tolerance,
                             risk_tolerance_base=risk_tolerance_base,
                             risk_only_as_last_resort=risk_only_as_last_resort)["completed"]
        )
        print(f"  {strategy:12s} {100*completed/trials:5.1f}% of trips complete all {ACTIVE_QUEST_COUNT} active quests")

    print()
    print(f"=== {class_name.capitalize()}: trips to afford a {BAG_UPGRADE_COST}G Bag Upgrade ===")
    for strategy in strategies:
        rng = random.Random(seed)
        trip_counts = []
        for _ in range(trials):
            result = run_to_bag_upgrade(class_name, strategy, rng, risk_tolerance=risk_tolerance,
                                         risk_tolerance_base=risk_tolerance_base,
                                         risk_only_as_last_resort=risk_only_as_last_resort)
            if result["trips"] is not None:
                trip_counts.append(result["trips"])
        avg = sum(trip_counts) / len(trip_counts) if trip_counts else float("nan")
        print(f"  {strategy:12s} avg {avg:5.2f} trips  ({len(trip_counts)}/{trials} reached the goal within the cap)")


DECAY_LABELS = ["Gold", "Silver", "Bronze", "nothing"]


def risk_exposure_report(class_name, strategy="food_only", trials=300, seed=42, chain_trips=20,
                          risk_tolerance=RISK_TOLERANCE, risk_tolerance_base=RISK_TOLERANCE_BASE,
                          risk_only_as_last_resort=True):
    """The throughput-side complement to condensed_trip.py's defense_floor_sweep. Instruments
    _pull_exceeds_risk to report how often this class actually reaches the macro loop's one
    risk-bearing decision (a quest-completing pull with no consumable left) and how dangerous
    those specific gambles are -- not just the raw deaths/run number decay_report() prints.

    Why this exists: deaths/run alone can't tell you whether a card change made the class more
    dangerous or just more efficient. A strictly-better card (more damage, nothing reduced)
    finishes quests faster, which means the class reaches the risk-gate more *often* over a
    fixed-length run -- more gambles at the same or better odds still produces more total
    deaths, purely as counting, with nothing about combat getting worse. Confirmed directly:
    Ranger's Crippling Shot 2dmg/3block -> 3dmg/3block nearly tripled deaths/run (0.11 -> 0.34)
    while gambles_taken rose ~15% and avg_lethal_frac barely moved -- the death-rate jump was
    almost entirely a throughput effect, not a combat one. See MACRO_LOOP_GUIDE.md's "Clean vs.
    aggregate metrics" for the full incident.

    **Always run this alongside condensed_trip.py's defense_floor_sweep for any damage-touching
    card change**, never decay_report() alone -- if the defense floor didn't move but deaths/run
    did, that's this function's story to tell (gambles_taken went up), not a balance regression.

    **Deaths/run alone is never sufficient, here either** — this function also reports
    avg_quests_per_trip and the decay-tier distribution alongside it, matching the project's
    own locked rule (never report a survival number without productivity/decay next to it).
    An earlier version of this report skipped that and nearly led to treating a legitimate
    aggressive-but-productive tradeoff (Ranger's 3dmg/3block test) as a plain regression.

    Returns dict: gambles_taken, avg_hp, avg_lethal_frac (both only over gambles actually taken,
    not every moment the risk-gate was checked -- an earlier version of this diagnostic included
    declined gambles too and produced a misleadingly inflated sample), deaths, trials,
    deaths_per_run, avg_quests_per_trip, decay_pct (dict of {label: percent}), per_mob (dict of
    {mob_name: {n, avg_hp, avg_lethal_frac}})."""
    mod = CARD_SOURCE[class_name]
    has_stance = HAS_STANCE[class_name]
    orig = globals()["_pull_exceeds_risk"]
    log = []

    def wrapped(mod_, has_stance_, mob_name, class_name_, hp, rt):
        result = orig(mod_, has_stance_, mob_name, class_name_, hp, rt)
        if rt == risk_tolerance and not result:
            pattern, mob_hp = T.MOBS[mob_name][class_name_]
            hands = mod_.ALL_HANDS
            lethal = sum(1 for hand in hands if T._best_line(mod_, has_stance_, hand, pattern, mob_hp, hp)[2] <= 0)
            log.append((mob_name, hp, lethal / len(hands)))
        return result

    globals()["_pull_exceeds_risk"] = wrapped
    try:
        rng = random.Random(seed)
        deaths = 0
        quests_totals = []
        decay_counts = [0] * len(DECAY_LABELS)
        for _ in range(trials):
            r = decay_stress_test(class_name, strategy, rng, chain_trips=chain_trips,
                                   risk_tolerance=risk_tolerance, risk_tolerance_base=risk_tolerance_base,
                                   risk_only_as_last_resort=risk_only_as_last_resort)
            deaths += r["died_count"]
            quests_totals.append(r["avg_quests_per_trip"])
            decay_counts[r["worst_decay_stage"]] += 1
    finally:
        globals()["_pull_exceeds_risk"] = orig

    n = len(log)
    per_mob = {}
    for mob, hp, frac in log:
        per_mob.setdefault(mob, []).append((hp, frac))
    per_mob_summary = {m: dict(n=len(v), avg_hp=sum(x[0] for x in v) / len(v),
                                avg_lethal_frac=sum(x[1] for x in v) / len(v))
                        for m, v in per_mob.items()}
    return dict(gambles_taken=n,
                avg_hp=(sum(x[1] for x in log) / n) if n else None,
                avg_lethal_frac=(sum(x[2] for x in log) / n) if n else None,
                deaths=deaths, trials=trials, deaths_per_run=deaths / trials,
                avg_quests_per_trip=sum(quests_totals) / len(quests_totals),
                decay_pct={DECAY_LABELS[i]: 100 * c / trials for i, c in enumerate(decay_counts)},
                per_mob=per_mob_summary)


# RISK_TOLERANCE=0.15 was never derived -- no sweep, no target, just an assumed placeholder
# (see MACRO_LOOP_GUIDE.md's "Clean vs. aggregate metrics"). Rather than picking a single
# "correct" replacement number (which would just be a different assumption dressed up as a
# fix), RISK_PERSONAS tests a spread instead -- a class whose macro-loop outlier status holds
# across every persona is a robust finding; one that only shows up at the current default is
# threshold-sensitive, not confirmed. Only the quest-completing tolerance varies between
# personas; RISK_TOLERANCE_BASE (0.0, never gamble off-quest) and risk_only_as_last_resort
# (True, consumable before risk) stay fixed for all three -- those are separately validated,
# not part of what's in question here.
RISK_PERSONAS = {
    "conservative": 0.05,
    "balanced": 0.15,  # today's default RISK_TOLERANCE
    "aggressive": 0.30,
}


def persona_comparison_report(class_name, strategy="food_only", trials=300, seed=42, chain_trips=20,
                               personas=None):
    """Runs risk_exposure_report once per named persona in RISK_PERSONAS (or a custom dict of
    {name: risk_tolerance}), instead of trusting the single, unvalidated RISK_TOLERANCE=0.15 as
    ground truth for a class's macro-loop numbers. Returns {persona_name: risk_exposure_report
    dict}. See persona_roster_report for the multi-class comparison table."""
    if personas is None:
        personas = RISK_PERSONAS
    return {name: risk_exposure_report(class_name, strategy, trials=trials, seed=seed,
                                        chain_trips=chain_trips, risk_tolerance=tolerance)
            for name, tolerance in personas.items()}


def persona_roster_report(class_names=None, strategy="food_only", trials=300, seed=42, chain_trips=20,
                           personas=None):
    """persona_comparison_report across multiple classes at once, printed as a side-by-side
    table per persona -- the actual tool to run when checking whether an apparent outlier class
    (e.g. Rogue/Ranger's elevated deaths/run) is a robust finding or an artifact of the default
    15% threshold specifically. class_names defaults to the full roster (CARD_SOURCE.keys())."""
    if class_names is None:
        class_names = list(CARD_SOURCE.keys())
    if personas is None:
        personas = RISK_PERSONAS
    all_results = {c: persona_comparison_report(c, strategy, trials, seed, chain_trips, personas)
                    for c in class_names}
    for persona_name, tolerance in personas.items():
        print(f"=== Persona: {persona_name} (risk_tolerance={tolerance}) ===")
        for c in class_names:
            r = all_results[c][persona_name]
            print(f"  {c:12s} deaths/run={r['deaths_per_run']:.2f}  quests/trip={r['avg_quests_per_trip']:.2f}"
                  f"  nothing-tier={r['decay_pct']['nothing']:.1f}%  gambles_taken={r['gambles_taken']:5d}"
                  f"  avg_lethal_frac={100*r['avg_lethal_frac']:.2f}%")
        print()
    return all_results


def compare_card_change(class_name, card_name, field_changes, strategy="food_only",
                         trials=300, seed=42, chain_trips=20):
    """The actual fix for the Ranger/Rogue incident: runs the clean defense-floor sweep
    (condensed_trip.py) and the throughput-side risk exposure report (this module) both
    before and after applying field_changes to CARDS[card_name], then prints an explicit
    verdict distinguishing a real combat regression from a throughput artifact -- instead of
    requiring a human to remember to run both and reason about the difference by hand, which
    is exactly what didn't happen the first three times this session, before the pattern was
    caught. field_changes: dict of {field: new_value}, e.g. {"dmg": 3, "block": 3}. Restores
    the original card values before returning, regardless of outcome.

    See MACRO_LOOP_GUIDE.md's "Clean vs. aggregate metrics" for the incident this exists to
    prevent from recurring."""
    mod = CARD_SOURCE[class_name]
    has_stance = HAS_STANCE[class_name]
    max_hp = float(getattr(mod, HP_ATTR[class_name]))
    original = {k: mod.CARDS[card_name][k] for k in field_changes}

    try:
        before_floor = T.defense_floor_sweep(mod, has_stance, class_name, max_hp)
        before_risk = risk_exposure_report(class_name, strategy, trials=trials, seed=seed, chain_trips=chain_trips)

        for k, v in field_changes.items():
            mod.CARDS[card_name][k] = v

        after_floor = T.defense_floor_sweep(mod, has_stance, class_name, max_hp)
        after_risk = risk_exposure_report(class_name, strategy, trials=trials, seed=seed, chain_trips=chain_trips)
    finally:
        for k, v in original.items():
            mod.CARDS[card_name][k] = v

    regressions = []
    for b, a in zip(before_floor, after_floor):
        for mob in b["per_mob"]:
            if a["per_mob"][mob] > b["per_mob"][mob] + 1e-9:
                regressions.append((b["hp"], mob, b["per_mob"][mob], a["per_mob"][mob]))

    gamble_delta = ((after_risk["gambles_taken"] - before_risk["gambles_taken"])
                     / max(1, before_risk["gambles_taken"]))
    death_delta = after_risk["deaths_per_run"] - before_risk["deaths_per_run"]

    print(f"=== compare_card_change: {class_name} / {card_name} {field_changes} ===")
    print(f"Defense floor (clean, policy-independent): {'REGRESSED' if regressions else 'clean or improved'}")
    for hp, mob, b, a in regressions:
        print(f"  at HP={hp} vs {mob}: {100*b:.1f}% -> {100*a:.1f}% lethal-frac (WORSE)")
    print(f"Deaths/run: {before_risk['deaths_per_run']:.2f} -> {after_risk['deaths_per_run']:.2f}"
          f"  ({death_delta:+.2f})")
    print(f"Quests/trip: {before_risk['avg_quests_per_trip']:.2f} -> {after_risk['avg_quests_per_trip']:.2f}")
    print(f"Nothing-tier: {before_risk['decay_pct']['nothing']:.1f}% -> {after_risk['decay_pct']['nothing']:.1f}%")
    print(f"Gambles taken: {before_risk['gambles_taken']} -> {after_risk['gambles_taken']}"
          f"  ({gamble_delta*100:+.1f}%)")
    print(f"Avg lethal-frac per gamble: {100*before_risk['avg_lethal_frac']:.2f}%"
          f" -> {100*after_risk['avg_lethal_frac']:.2f}%")
    print()
    if not regressions and death_delta > 0:
        print("VERDICT: deaths/run increase is a THROUGHPUT ARTIFACT (more gambles taken, not "
              "riskier ones) -- not a real combat regression. The card is not more dangerous.")
    elif regressions:
        print("VERDICT: REAL combat regression -- the defense floor itself got worse at a fixed HP.")
    elif death_delta <= 0:
        print("VERDICT: clean improvement -- better or equal on both the floor and the aggregate.")
    return dict(before_floor=before_floor, after_floor=after_floor,
                before_risk=before_risk, after_risk=after_risk, regressions=regressions)


def decay_report(class_name, trials=500, seed=42, chain_trips=20, risk_tolerance=RISK_TOLERANCE,
                  risk_tolerance_base=RISK_TOLERANCE_BASE, risk_only_as_last_resort=True):
    """Distribution of the worst decay_stage any quest reached over a
    fixed chain_trips-long run, per strategy, plus how often a death
    happened at all (only possible when risk_tolerance > 0)."""
    strategies = ["none", "food_only", "potion_only"]
    print(f"=== {class_name.capitalize()}: worst bounty decay reached over {chain_trips} trips ({trials} trials, risk_tolerance={risk_tolerance}/{risk_tolerance_base}) ===")
    for strategy in strategies:
        rng = random.Random(seed)
        counts = [0] * len(DECAY_LABELS)
        deaths = 0
        for _ in range(trials):
            result = decay_stress_test(class_name, strategy, rng, chain_trips=chain_trips,
                                        risk_tolerance=risk_tolerance,
                                        risk_tolerance_base=risk_tolerance_base,
                                        risk_only_as_last_resort=risk_only_as_last_resort)
            counts[result["worst_decay_stage"]] += 1
            deaths += result["died_count"]
        breakdown = "  ".join(f"{DECAY_LABELS[i]}:{100*c/trials:4.1f}%" for i, c in enumerate(counts))
        print(f"  {strategy:12s} {breakdown}   avg deaths/run: {deaths/trials:.2f}")


def productivity_report(class_name, trials=500, seed=42, chain_trips=20, risk_tolerance=RISK_TOLERANCE,
                         risk_tolerance_base=RISK_TOLERANCE_BASE, risk_only_as_last_resort=True):
    """Average quests completed per trip, out of ACTIVE_QUEST_COUNT (3)
    possible, over a chain_trips-long run -- the direct "how productive is
    a typical trip" number, as distinct from single-trip completion rate
    (all-3-or-nothing) or decay (a distributional worst-case)."""
    strategies = ["none", "food_only", "potion_only"]
    print(f"=== {class_name.capitalize()}: avg quests completed per trip, out of {ACTIVE_QUEST_COUNT} ({chain_trips}-trip runs, {trials} trials) ===")
    for strategy in strategies:
        rng = random.Random(seed)
        totals = []
        for _ in range(trials):
            result = decay_stress_test(class_name, strategy, rng, chain_trips=chain_trips,
                                        risk_tolerance=risk_tolerance,
                                        risk_tolerance_base=risk_tolerance_base,
                                        risk_only_as_last_resort=risk_only_as_last_resort)
            totals.append(result["avg_quests_per_trip"])
        avg = sum(totals) / len(totals)
        print(f"  {strategy:12s} avg {avg:.2f} of {ACTIVE_QUEST_COUNT} quests/trip")


if __name__ == "__main__":
    for class_name in CARD_SOURCE:
        compare_strategies(class_name)
        print()
        productivity_report(class_name)
        print()
        decay_report(class_name)
        print()
