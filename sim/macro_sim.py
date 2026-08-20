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

**Known divergence from the locked design, not yet built here:** DESIGN_DOC.md now describes
loot as colored quest tokens (one Bag slot per quest color, up to 3 same-colored tokens per
slot, Food no longer closes anything) -- see MACRO_LOOP_GUIDE.md's "Bag Tetris revision" entry.
This file's actual loot tracking (_add_loot/_open_loot_slot_index/_close_active_loot_slot,
below) still implements the *previous* any-mix-one-open-slot model, since only the Food/Potion
pricing and stacking half of that revision was actually validated here -- the loot-token half
is locked as a design decision but not yet ported into this simulator. Re-running decay_report
after that port lands is the thing to do before trusting today's numbers past the Food/Potion
question specifically.

What actually happens at Town (confirmed directly, not assumed):
- HP restores to full. Always, automatically.
- Every non-locked slot's "closed" flag clears (Food's mid-trip lock lifts) -- current-code
  behavior; per the divergence note above, the locked design no longer has Food do this at all.
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

Scope: two Zones now (2026-08-19), eight farmable Standard-tier Nodes/quests total, of which
a given trip's quest log only holds ACTIVE_QUEST_COUNT (3) at a time, drawn from both Zones'
pools together (see the shuffled-bag quest-refill note above). All eight nodes draw from the
same Standard mob pool, so which node a given trip's quest routes to is cosmetic within a
Zone, not a different challenge -- crossing *between* Zones is the real difference, since it
costs a Scouted Pull toll (NODE_ZONE/_cross_to in run_one_trip). Town's Spike-tier Elite node
is still deferred. Flight Path (paying Gold to skip the toll) is explicitly not built --
Border Node crossing is the only way to change Zones right now.
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
    "shoal": ("standard", "Smuggled Cargo"),
    "lagoon": ("standard", "Forged Ledger"),
    "bluff": ("standard", "Plundered Chest"),
    "wreckage": ("standard", "Buried Treasure"),
}
# node -> which Zone it's in. Zone 1 has Town; Zone 2 has the Class Trainer instead
# (DESIGN_DOC.md's "Starting map, locked" section) -- crossing between them costs a
# Scouted Pull toll (below), free movement only within a single Zone.
NODE_ZONE = {"waystation": 1, "cove": 1, "ridge": 1, "marsh": 1,
             "shoal": 2, "lagoon": 2, "bluff": 2, "wreckage": 2}
ZONE_TIER = {1: "standard", 2: "standard"}  # both zones are Standard-tier only for now
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
    # Zone 2 -- mirrors Zone 1's required/reward shape exactly (DESIGN_DOC.md's "Zone 2's
    # nodes and quests, locked" section), same coastal-plunder naming thread.
    "Smuggled Cargo":    dict(required=2, base_xp=2, gold_ladder=[4, 2, 1, 0]),
    "Forged Ledger":     dict(required=3, base_xp=3, gold_ladder=[4, 2, 1, 0]),
    "Plundered Chest":   dict(required=4, base_xp=4, gold_ladder=[4, 2, 1, 0]),
    "Buried Treasure":   dict(required=5, base_xp=5, gold_ladder=[9, 5, 3, 0]),
}

FOOD_COST = 4
POTION_COST = 3
POTION_HEAL = 8
POTION_STACK_SIZE = 2  # up to this many Potions can share a single Bag slot -- Food does not stack
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


_scouted_pull_costpct_cache = {}


def _scouted_pull_mob(class_name, tier, rng):
    """Scouted Pull, the Border Node toll (OPEN_QUESTIONS.md's "Border Nodes and Scouted
    Pull" entry): draw 2 mobs from the destination Zone's tier, both revealed, the hero
    picks which to fight -- a real, informed choice, not blind. Picks whichever of the 2 has
    the lower average cost% for this class (the same metric class_mob_matchup_chart.py uses
    to differentiate matchups), matching a rational player scouting a genuinely visible
    choice rather than a hand-specific one (the hand isn't drawn until after the mob is
    already chosen, same as every other pull in this sim).

    Doesn't yet model the full physical deck/discard-pile richness the design doc describes
    (a persistent per-Zone deck, cards leaving to discard rather than being redrawable) --
    kept at the same level of abstraction condensed_trip.py's mob draw already uses
    everywhere else in this sim (an independent weighted draw, not a tracked deck), not a
    gap specific to this mechanic. This sim is solo, so the "only happens if the destination
    Zone is unoccupied" condition in the locked design is vacuously always true here -- no
    other hero exists in this model to have already populated the Zone."""
    pool, weights = T.mob_pool_weights(tier)
    candidates = rng.choices(pool, weights=weights, k=2)
    cache = _scouted_pull_costpct_cache.setdefault(class_name, {})
    mod = CARD_SOURCE[class_name]
    has_stance = HAS_STANCE[class_name]
    max_hp = float(getattr(mod, HP_ATTR[class_name]))
    best_mob, best_cost = None, None
    for mob_name in candidates:
        if mob_name not in cache:
            pattern, mob_hp = T.MOBS[mob_name][class_name]
            total_cost = 0.0
            for hand in mod.ALL_HANDS:
                seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, pattern, mob_hp, max_hp)
                total_cost += max_hp - hp_left
            cache[mob_name] = 100 * (total_cost / len(mod.ALL_HANDS)) / max_hp
        cost = cache[mob_name]
        if best_cost is None or cost < best_cost:
            best_mob, best_cost = mob_name, cost
    return best_mob


def _best_case_mob(class_name, tier):
    """The single lowest-cost% mob in a tier's whole pool for this class -- a deterministic,
    no-rng "what's the best matchup I could hope to land" check, used to decide whether an
    optional Border Node crossing is even worth attempting (see run_one_trip). Not the same
    as _scouted_pull_mob, which simulates the real 2-card draw-and-choose toll itself; this
    is a cheaper, non-random proxy for "is there a real chance this goes fine," used only to
    gate the decision to cross at all, not the crossing's own outcome."""
    pool, weights = T.mob_pool_weights(tier)
    cache = _scouted_pull_costpct_cache.setdefault(class_name, {})
    mod = CARD_SOURCE[class_name]
    has_stance = HAS_STANCE[class_name]
    max_hp = float(getattr(mod, HP_ATTR[class_name]))
    best_mob, best_cost = None, None
    for mob_name in set(pool):
        if mob_name not in cache:
            pattern, mob_hp = T.MOBS[mob_name][class_name]
            total_cost = 0.0
            for hand in mod.ALL_HANDS:
                seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, pattern, mob_hp, max_hp)
                total_cost += max_hp - hp_left
            cache[mob_name] = 100 * (total_cost / len(mod.ALL_HANDS)) / max_hp
        cost = cache[mob_name]
        if best_cost is None or cost < best_cost:
            best_mob, best_cost = mob_name, cost
    return best_mob


def _is_potion_slot(slot):
    """A Potion-holding slot is ('potion', count), count in 1..POTION_STACK_SIZE -- Food stays
    a bare 'food' string since it never stacks."""
    return isinstance(slot, tuple) and slot[0] == "potion"


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
                  risk_only_as_last_resort=True, current_zone=1):
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
    by the caller (see module docstring).

    current_zone: "a town is a town is a town" -- both Zones have full Town amenities
    (turn-in, decay, Bag Upgrade, Food/Potion restock), only the Class Trainer is
    Zone-2-exclusive, so a trip can end in *either* Zone with nothing special required to
    "get home" first. That means, unlike an earlier version of this function, zone state
    persists *across* trips (passed in here, returned in the result for the caller to persist
    forward) rather than always resetting to 1 -- a hero who ended their last trip in Zone 2
    simply starts the next one there too."""
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
    border_crossings = 0
    zone_pulls = {1: 0, 2: 0}

    def _make_result(**kwargs):
        return dict(pulls=pulls, bag=bag, locked=locked, active_quests=active_quests,
                    consumables_used=consumables_used, border_crossings=border_crossings,
                    zone1_pulls=zone_pulls[1], zone2_pulls=zone_pulls[2],
                    current_zone=current_zone, **kwargs)

    def _cross_to(target_zone, tier):
        """Resolves one Scouted Pull toll to enter target_zone. Fully discretionary now that
        both Zones have Town -- the caller decides whether it's worth attempting before ever
        calling this (see the risk check just above each call site); by the time this runs,
        the hero has already committed. Uses a consumable first if the crossing looks risky
        and one's available, then attempts it regardless of outcome once committed -- a real
        death is possible here, same as any other pull. Returns a death result dict if the
        hero dies crossing, else None (crossing succeeded, current_zone/border_crossings/
        zone_pulls/pulls/hp already updated by the time this returns)."""
        nonlocal hp, pulls, current_zone, border_crossings
        mob_name = _scouted_pull_mob(class_name, tier, rng)
        if risk_only_as_last_resort:
            has_consumable = any(not locked[i] and (bag[i] == "food" or _is_potion_slot(bag[i]))
                                  for i in range(len(bag)))
        else:
            has_consumable = False
        if _pull_exceeds_risk(mod, has_stance, mob_name, class_name, hp, risk_tolerance_base) and has_consumable:
            for i, slot in enumerate(bag):
                if locked[i]:
                    continue
                if slot == "food":
                    hp = max_hp
                    bag[i] = None
                    _close_active_loot_slot(bag, locked)
                    consumables_used["food"] += 1
                    break
                if _is_potion_slot(slot):
                    hp = min(max_hp, hp + POTION_HEAL)
                    remaining = slot[1] - 1
                    bag[i] = ("potion", remaining) if remaining > 0 else None
                    consumables_used["potion"] += 1
                    break
        pattern, mob_hp = T.MOBS[mob_name][class_name]
        hand = rng.choice(mod.ALL_HANDS)
        seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, pattern, mob_hp, hp)
        win, final_hp, final_rounds = T._simulate(mod, has_stance, seq, stance, pattern, mob_hp, hp)
        hp = final_hp
        pulls += 1
        zone_pulls[target_zone] += 1
        border_crossings += 1
        if hp <= 0:
            return _make_result(completed=False, died=True, recovered=recovered,
                                 death_node=f"border(zone{target_zone})", hp=0)
        current_zone = target_zone
        return None

    while True:
        if pending_recovery is not None and pending_recovery.startswith("border(zone"):
            # died mid-crossing last time -- recovery means attempting that same crossing
            # again (a fresh Scouted Pull, not a NODES lookup; there's no ordinary node at
            # a border). Reuses _cross_to's own death handling, so a second death here
            # produces the identical "border(zoneN)" corpse marker, same spiral-risk shape
            # as dying twice at an ordinary node.
            target_zone = int(pending_recovery[len("border(zone"):-1])
            died_result = _cross_to(target_zone, ZONE_TIER[target_zone])
            if died_result is not None:
                return died_result
            pending_recovery = None
            recovered = True
            continue
        if pending_recovery is not None:
            node_name = pending_recovery
            tier, loot_name = NODES[node_name]
            loot_name = None  # a recovery pull earns no loot, regardless of outcome
        else:
            incomplete = [loot for loot in active_quests
                          if _accessible_count(bag, locked, loot) < QUESTS[loot]["required"]]
            if not incomplete:
                # A town is a town is a town -- the trip just ends here, wherever "here" is,
                # no crossing needed just to reach a Town that's already present in this Zone.
                return _make_result(completed=True, died=False, recovered=recovered, hp=hp)

            if not _bag_has_room(bag, locked):
                food_index = next((i for i, s in enumerate(bag) if not locked[i] and s == "food"), None)
                if food_index is not None:
                    hp = max_hp
                    bag[food_index] = None
                    consumables_used["food"] += 1
                else:
                    potion_index = next((i for i, s in enumerate(bag) if not locked[i] and _is_potion_slot(s)),
                                         None)
                    if potion_index is None:
                        return _make_result(completed=False, died=False, recovered=recovered, hp=hp)
                    hp = min(max_hp, hp + POTION_HEAL)
                    remaining = bag[potion_index][1] - 1
                    bag[potion_index] = ("potion", remaining) if remaining > 0 else None
                    consumables_used["potion"] += 1

            # Route to whichever still-incomplete quest's node to visit next -- a rational
            # hero finishes everything reachable in the Zone they're already standing in
            # before ever paying a Border Node toll (confirmed directly, not assumed: an
            # earlier version routed to plain incomplete[0], zone-blind, and produced wildly
            # inflated crossing counts -- ~11 crossings to reach Level 2 + one skill, because
            # it would zigzag Zone 1 -> Zone 2 -> Zone 1 -> Zone 2 purely by quest-list order).
            same_zone_first = sorted(incomplete, key=lambda loot: NODE_ZONE[next(
                n for n, (t, l) in NODES.items() if l == loot)] != current_zone)
            node_name = next(n for n, (tier, loot) in NODES.items() if loot == same_zone_first[0])
            tier, loot_name = NODES[node_name]

        target_zone = NODE_ZONE[node_name]
        if target_zone != current_zone:
            # Crossing is now fully discretionary in *both* directions -- since both Zones
            # have Town, there's never a "must get home" pressure forcing it the way an
            # earlier version required for the Zone-2 -> Zone-1 leg specifically. A rational
            # hero who judges the crossing too risky, with no consumable to back it up,
            # simply doesn't go -- they end the trip with whatever they've already got
            # (including, if current_zone is 2, just staying there and using Zone 2's own
            # Town), rather than being forced into a gamble they'd never actually choose.
            if risk_only_as_last_resort:
                has_consumable = any(not locked[i] and (bag[i] == "food" or _is_potion_slot(bag[i]))
                                      for i in range(len(bag)))
            else:
                has_consumable = False
            # Deterministic best-case-matchup check, not a live draw -- a real Scouted
            # Pull reveals 2 mobs and picks the better, so "is this worth trying" is
            # judged against the single best matchup this class has in the zone's pool,
            # not a random preview (which would consume real rng state for a decision
            # that might not lead to an actual crossing, desyncing it from the real draw
            # _cross_to makes if the hero does go).
            best_mob = _best_case_mob(class_name, ZONE_TIER[target_zone])
            if (_pull_exceeds_risk(mod, has_stance, best_mob, class_name, hp, risk_tolerance_base)
                    and not has_consumable):
                return _make_result(completed=False, died=False, recovered=recovered, hp=hp)
            died_result = _cross_to(target_zone, tier)
            if died_result is not None:
                return died_result
            continue  # crossing is its own turn -- the actual node pull happens next iteration

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
            has_consumable = any(not locked[i] and (bag[i] == "food" or _is_potion_slot(bag[i]))
                                  for i in range(len(bag)))
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
                if _is_potion_slot(slot):
                    hp = min(max_hp, hp + POTION_HEAL)
                    remaining = slot[1] - 1
                    bag[i] = ("potion", remaining) if remaining > 0 else None
                    consumed = "potion"
                    break
            if consumed:
                consumables_used[consumed] += 1
                if _pull_exceeds_risk(mod, has_stance, mob_name, class_name, hp, effective_risk_tolerance):
                    return _make_result(completed=False, died=False, recovered=recovered, hp=hp)
            else:
                return _make_result(completed=False, died=False, recovered=recovered, hp=hp)

        pattern, mob_hp = T.MOBS[mob_name][class_name]
        hand = rng.choice(mod.ALL_HANDS)
        seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, pattern, mob_hp, hp)
        win, final_hp, final_rounds = T._simulate(mod, has_stance, seq, stance, pattern, mob_hp, hp)
        hp = final_hp
        pulls += 1
        zone_pulls[current_zone] += 1

        if hp <= 0:
            return _make_result(completed=False, died=True, recovered=recovered, death_node=node_name, hp=0)

        if pending_recovery is not None:
            # survived the recovery pull -- win or flee, doesn't matter, the corpse is retrieved
            pending_recovery = None
            recovered = True
            continue

        if win:
            if not _add_loot(bag, locked, loot_name):
                # shouldn't happen given the _bag_has_room check above, but stay safe
                return _make_result(completed=False, died=False, recovered=recovered, hp=hp)
        # if not win (fled), no loot gained, but the pull still happened -- loop continues


def _leaving_town_setup(strategy, bag, locked, gold):
    """Everything automatic that happens before heading back out: closed
    (not locked) slots reopen, and the strategy's one consumable gets
    restocked into an open empty slot if the hero doesn't already have
    one and can afford it. Returns the (possibly reduced) gold."""
    for i, slot in enumerate(bag):
        if not locked[i] and isinstance(slot, dict):
            slot["closed"] = False

    if strategy == "food_only":
        already_have = any(not locked[i] and bag[i] == "food" for i in range(len(bag)))
        if not already_have and gold >= FOOD_COST:
            empty_index = next((i for i in range(len(bag)) if not locked[i] and bag[i] is None), None)
            if empty_index is not None:
                bag[empty_index] = "food"
                gold -= FOOD_COST
    elif strategy == "potion_only":
        # Tops off exactly one potion-stack slot to POTION_STACK_SIZE, never opens a second one --
        # mirrors food_only's "only ever holds one consumable slot," always leaving the other slot
        # free for loot. A player with a second free slot may well choose to open another Potion
        # stack there instead of chasing loot, but that's a real, separate strategy to test on its
        # own footing, not the default "restock like food_only does" comparison this one represents.
        stack_index = next((i for i in range(len(bag)) if not locked[i] and _is_potion_slot(bag[i])), None)
        if stack_index is None and gold >= POTION_COST:
            stack_index = next((i for i in range(len(bag)) if not locked[i] and bag[i] is None), None)
            if stack_index is not None:
                bag[stack_index] = ("potion", 0)
        if stack_index is not None:
            while gold >= POTION_COST and bag[stack_index][1] < POTION_STACK_SIZE:
                bag[stack_index] = ("potion", bag[stack_index][1] + 1)
                gold -= POTION_COST
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
    # Shuffled-bag refill: no quest can repeat until every other quest has cycled through once --
    # same "reshuffle on empty" shape already locked for mob decks (OPEN_QUESTIONS.md's
    # "Zone-node mob dealing" entry). quest_bag holds the not-yet-drawn-this-cycle quests;
    # refilled drawn from its front, reshuffled fresh (excluding whatever's currently active,
    # so the reshuffle boundary itself can't produce an immediate duplicate) once it empties.
    quest_bag = list(QUESTS.keys())
    rng.shuffle(quest_bag)
    active_quests = [quest_bag.pop(0) for _ in range(ACTIVE_QUEST_COUNT)]
    bag = [None] * bag_size
    locked = [False] * bag_size
    bag[0] = "food"  # free starting Food, matching DESIGN_DOC.md's locked starting loadout --
    # previously missing here, so trip 1 of every chain silently started with an empty bag
    corpse_node = None  # set on death; the next trip's first pull is forced there to recover it
    # "A town is a town is a town" -- both Zones have full Town amenities, so zone state
    # genuinely persists across trips now (a hero who ended a trip in Zone 2 starts the next
    # one there too), unlike an earlier single-Town version where every trip reset to Zone 1
    # by construction. See run_one_trip's own current_zone docstring note for the full reasoning.
    current_zone = 1

    trip_num = 0
    while True:
        trip_num += 1
        gold = _leaving_town_setup(strategy, bag, locked, gold)

        result = run_one_trip(class_name, strategy, rng, bag=bag, locked=locked,
                               active_quests=list(active_quests), risk_tolerance=risk_tolerance,
                               risk_tolerance_base=risk_tolerance_base, corpse_node=corpse_node,
                               risk_only_as_last_resort=risk_only_as_last_resort,
                               current_zone=current_zone)
        current_zone = result["current_zone"]

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
            # A dead hero's remains get returned to Zone 1 -- the recovery pull targets the
            # actual death_node (which _cross_to's own recovery branch in run_one_trip already
            # handles, crossing back out to a Zone-2 death_node if needed), but the hero
            # themself restarts the next trip from Zone 1's Town, not wherever they fell.
            current_zone = 1
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

            newly_active = []
            for _ in range(len(turned_in)):
                if not quest_bag:
                    # exclude both still-incomplete quests AND anything already drawn earlier
                    # in this same refill batch -- otherwise a mid-batch reshuffle can hand back
                    # a quest that was just placed into the log a moment ago
                    quest_bag = [loot for loot in QUESTS if loot not in still_incomplete and loot not in newly_active]
                    rng.shuffle(quest_bag)
                newly_active.append(quest_bag.pop(0))
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
