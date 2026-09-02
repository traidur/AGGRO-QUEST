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

Bag model (Rescaled 2026-08-25): The bag is a 6-slot capacity system. Food occupies
3 slots. Every other item (Potions, Loot, Consumables) occupies exactly 1 slot 
(`ITEM_STACK_CAP = 1`). Nothing stacks. The bag is persistent state across a whole
chain of trips, not reset each call.

**Fixed 2026-08-25** -- migrated from the old 2-slot/stacking model to the 6-slot/no-stacking 
model. `_add_item`/`_remove_item` unified mechanisms were retained, but `ITEM_STACK_CAP` was 
dropped from 3 to 1 to reflect the physical redesign (one token = one physical slot).
Bag Upgrade price and Potion price were both tuned against the OLD model and have not yet been
re-swept against this corrected one -- treat both as unlocked/unvalidated until that happens.

What actually happens at Town (confirmed directly, not assumed):
- HP restores to full. Always, automatically.
- Nothing needs "reopening" anymore -- there's no closed-slot state left to clear (see the
  2026-08-22 fix note above). LOCKED slots (see Death, below) still do NOT unlock just by
  visiting Town; that's a separate mechanism (corpse recovery), untouched by this.
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

Scope: a real 4-Zone loop as of 2026-08-21 (Zone 1 <-> Zone 2 <-> Zone 3 <-> Zone 4 <-> back to
Zone 1), 16 farmable Nodes/quests total (8 Standard-tier in Zone 1/2, 8 real Level 2-tier in
Zone 3/4), of which a given trip's quest log only holds ACTIVE_QUEST_COUNT (3) at a time --
Zone 1/2's is a fixed, non-replenishing starter batch (see QUESTS' own comment), Zone 3/4's
replenishes normally (LEVEL2_QUESTS). Which node a given trip's quest routes to within a Zone
is cosmetic (every Zone 1/2 node draws the same Standard pool, every Zone 3/4 node draws the
same LEVEL2_TIER pool) -- crossing *between* Zones is the real difference, since it costs a
Scouted Pull toll (NODE_ZONE/_cross_to in run_one_trip). Town's Spike-tier Elite node is still
deferred. Flight Path (Zone 2 <-> Zone 4 only, 2 Gold, no turn cost) is built -- the only other
way to change Zones is the Border Node toll.
"""
import collections
import random

import condensed_cleric as C
import condensed_paladin as P
import condensed_ranger as G
import condensed_rogue as R
import condensed_runecaster as N
import condensed_trip as T
import leveling_validation as LV
import condensed_warrior as W
import condensed_wizard as Z
import condensed_druid as D
import condensed_necromancer as Nc
import combat_engine as E

CARD_SOURCE = {"warrior": W, "wizard": Z, "cleric": C, "paladin": P, "rogue": R, "ranger": G, "runecaster": N,
               "druid": D, "necromancer": Nc}
HP_ATTR = {"warrior": "WARRIOR_HP", "wizard": "WIZARD_HP", "cleric": "CLERIC_HP", "paladin": "PALADIN_HP",
           "rogue": "ROGUE_HP", "ranger": "RANGER_HP", "runecaster": "RUNECASTER_HP", "druid": "DRUID_HP",
           "necromancer": "NECROMANCER_HP"}
HAS_STANCE = {"warrior": True, "wizard": False, "cleric": False, "paladin": False,
              "rogue": False, "ranger": False, "runecaster": False, "druid": False, "necromancer": False}

# A Zone/Node tier value meaning "draw from the real Level 2 pool" (18 Standard + 3 Elite,
# weighted 3:1 -- matches leveling_validation.mob_pool_for_level's construction), permanent
# and per-Zone/per-Node, distinct from run_one_trip's mob_level=2 test-only blanket override
# (which forces every node in a trip to draw Level 2 regardless of that node's own tier, kept
# unchanged and separate -- see its own docstring). Zone 3/4's Nodes use this natively, below --
# mob difficulty is a property of the place, never the hero's own XP/level (2026-08-21, a real
# mistake caught and reverted: an earlier version of this session tied it to hero XP instead).
# Elites still can't just be registered in condensed_trip.py's MOBS/MOB_NAMES the way a real
# Standard mob is -- every other diagnostic tool in this codebase assumes MOB_NAMES means the 6
# Standard mobs only, so Elites are resolved here by name via leveling_validation.ELITE_MELEE
# instead.
LEVEL2_TIER = "standard_l2"

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
    # Zone 3/4, "The Pale Wastes"/"The Sunsworn" -- locked 2026-08-20 (DESIGN_DOC.md's "Zones 3
    # and 4, naming locked" section), wired 2026-08-21. LEVEL2_TIER natively, not an override --
    # mob difficulty is a property of the place, the same way "standard" always has been for
    # Zone 1/2, never a function of the hero's own XP/level.
    "mud_trenches":     (LEVEL2_TIER, "Royal Signets"),
    "ruined_abbey":     (LEVEL2_TIER, "Consecrated Ash"),
    "pyre_fields":      (LEVEL2_TIER, "Ashen Vestments"),
    "broken_bridge":    (LEVEL2_TIER, "Shattered Broadswords"),
    "charred_village":  (LEVEL2_TIER, "Rusted Mail"),
    "armory_gates":     (LEVEL2_TIER, "Tarnished Crests"),
    "gleaming_citadel": (LEVEL2_TIER, "Blessed Lamp Oil"),
    "sunward_throne":   (LEVEL2_TIER, "Gilded Penance"),
}
# node -> which Zone it's in. Zone 1 has Town; Zone 2 has the Class Trainer instead
# (DESIGN_DOC.md's "Starting map, locked" section) -- crossing between them costs a
# Scouted Pull toll (below), free movement only within a single Zone.
NODE_ZONE = {"waystation": 1, "cove": 1, "ridge": 1, "marsh": 1,
             "shoal": 2, "lagoon": 2, "bluff": 2, "wreckage": 2,
             "mud_trenches": 3, "ruined_abbey": 3, "pyre_fields": 3, "broken_bridge": 3,
             "charred_village": 4, "armory_gates": 4, "gleaming_citadel": 4, "sunward_throne": 4}
ZONE_TIER = {1: "standard", 2: "standard", 3: LEVEL2_TIER, 4: LEVEL2_TIER}  # Zone 3/4 are
# Level 2 tier for Border-crossing tolls too, not just their own Nodes -- the toll fight
# guarding the way in is appropriately just as hard as what's on the other side of it.

# Border Node name -> frozenset of the Zones it connects (OPEN_QUESTIONS.md's "Border Nodes
# and Scouted Pull" entry). Each Border Node is its own physical position, not part of either
# Zone it connects -- a named registry (not a single hardcoded crossing), so adding the rest of
# the 4-Zone loop (2026-08-21, DESIGN_DOC.md's locked map shape: 1 -> 2 -> 3 -> 4 -> back to 1)
# was a pure data addition, no crossing-logic rewrite needed -- multi-hop routing
# (_next_border_toward/_hop_distance below) was already built generically for this.
BORDER_NODES = {
    "border_1_2": frozenset({1, 2}),
    "border_2_3": frozenset({2, 3}),
    "border_3_4": frozenset({3, 4}),
    "border_4_1": frozenset({4, 1}),
}

_ELITE_NAMES = list(LV.ELITE_MELEE.keys())


def _pattern_hp_for_mob(class_name, mob_name):
    """(pattern, mob_hp) for mob_name against class_name -- checks the Elite lookup first,
    falling back to T.MOBS. The one shared place that knows how to resolve either kind of mob
    name, so _scouted_pull_mob/_best_case_mob/the main node-pull draw don't each need their
    own Elite-vs-Standard branch."""
    if mob_name in LV.ELITE_MELEE:
        return LV._elite_pattern(class_name, mob_name), LV.ELITE_HP
    return T.MOBS[mob_name][class_name]


def _named_pool_for_tier(class_name, tier):
    """(names, weights) for rng.choices -- Standard tiers pass straight through to
    T.mob_pool_weights unchanged (verified no-op for existing content: same pool, same
    weights, same subsequent rng.choices call). LEVEL2_TIER additionally mixes in the Elite
    trio by name, each Elite weighted 1 against each Standard mob's weight tripled --
    reproduces the real Level 2 deck's 18-Standard-copies : 3-Elite-copies ratio without ever
    registering Elites in T.MOBS/MOB_NAMES."""
    if tier == LEVEL2_TIER:
        pool, weights = T.mob_pool_weights("standard")
        names = list(pool) + _ELITE_NAMES
        wts = [w * 3 for w in weights] + [1] * len(_ELITE_NAMES)
        return names, wts
    return T.mob_pool_weights(tier)


def _reachable_free(target_zone, position):
    """True if target_zone is one free move away from position -- either position is already
    that same Zone, or position is a Border Node whose connected set includes target_zone (in
    which case moving there costs no toll, same as any other node-to-node move). False means an
    actual Border Node crossing (a toll) is required to reach target_zone."""
    if isinstance(position, int):
        return target_zone == position
    return target_zone in BORDER_NODES[position]


def _reachable_zones(position):
    """The set of Zones freely reachable (no toll) from position right now -- itself, if
    position is a real Zone, or every Zone a Border Node connects to, if position is standing
    on one. This is also the set a *second* Border Node crossing can be attempted from this
    same turn's routing decision without ever having to stop and pull in an intermediate Zone
    first -- OPEN_QUESTIONS.md's "Border Nodes and Scouted Pull" entry: a hero on a Border Node
    has free rein into any Zone it connects, which transitively includes that Zone's own
    Border Nodes, not just its quest nodes."""
    if isinstance(position, int):
        return {position}
    return set(BORDER_NODES[position])


def _next_border_toward(position, target_zone):
    """BFS over the Zone graph (Border Nodes as edges) for the single Border Node to attempt
    crossing this turn, on a shortest path from position to target_zone. Caller must already
    know target_zone isn't freely reachable (check _reachable_free first) -- this only finds
    the *next* crossing, not a whole pre-planned route, since routing gets re-evaluated fresh
    every turn anyway (same as the existing single-hop logic always has). Returns
    (border_name, next_zone) -- next_zone is specifically the Zone actually being progressed
    toward by that crossing, used to pick which Zone's mob pool the Scouted Pull toll draws
    from (not the ultimate target_zone, which may still be further hops away)."""
    start_zones = _reachable_zones(position)
    visited = set(start_zones)
    frontier = [(zone, None, None) for zone in start_zones]  # (zone, first_border, first_next_zone)
    while frontier:
        next_frontier = []
        for zone, first_border, first_next_zone in frontier:
            for border_name, zones in BORDER_NODES.items():
                if zone not in zones:
                    continue
                for neighbor in zones:
                    if neighbor == zone or neighbor in visited:
                        continue
                    taken_border = first_border if first_border is not None else border_name
                    taken_next_zone = first_next_zone if first_next_zone is not None else neighbor
                    if neighbor == target_zone:
                        return taken_border, taken_next_zone
                    visited.add(neighbor)
                    next_frontier.append((neighbor, taken_border, taken_next_zone))
        frontier = next_frontier
    raise ValueError(f"no path found from {position!r} to Zone {target_zone}")


def _hop_distance(position, target_zone):
    """Fewest Border Node crossings needed to freely reach target_zone from position -- 0 if
    already freely reachable. Used purely for routing preference (which incomplete quest to
    pursue first), a more granular version of the old free-vs-not-free boolean sort key now
    that more than one Border Node can exist."""
    if _reachable_free(target_zone, position):
        return 0
    visited = set(_reachable_zones(position))
    frontier = list(visited)
    hops = 1
    while frontier:
        next_frontier = []
        for zone in frontier:
            for border_name, zones in BORDER_NODES.items():
                if zone not in zones:
                    continue
                for neighbor in zones:
                    if neighbor in visited:
                        continue
                    if neighbor == target_zone:
                        return hops
                    visited.add(neighbor)
                    next_frontier.append(neighbor)
        frontier = next_frontier
        hops += 1
    raise ValueError(f"no path found from {position!r} to Zone {target_zone}")
ACTIVE_QUEST_COUNT = 3  # each trip's quest log holds this many of the below, not all of them

# loot card name -> quest requirement (keyed by loot type -- one quest per node)
#
# Level 1 starter batch, compressed and non-replenishing (locked 2026-08-21, replacing the
# original mixed-required/replenishing design below, now preserved as LEVEL2_QUESTS).
# All 8 quests flattened to required=2, base_xp=2, gold_ladder=[4,2,1,0] -- every one of the
# original required=2/3/4 quests already shared this exact gold_ladder, so flattening required
# down to 2 for the 3/4-required quests costs nothing in Gold, only removes wasted turns
# (the original required=5 quests, Stolen Signet/Buried Treasure, drop their higher [9,5,3,0]
# ladder too -- explicitly decided to flatten everything the same way, not let them keep paying
# more at the reduced required count). _trip_chain draws exactly 3 of these 8 at random as a
# hero's starter batch and does NOT refill it as quests are turned in -- completing all 3 always
# nets exactly 6 XP (3 x 2), which is deliberately identical to LEVEL2_XP_THRESHOLD: hitting 6
# XP *is* reaching Level 2, and from that point on this pool is never drawn from again for that
# hero (Zone 1/2 quest-giving is exhausted for good -- see LEVEL2_QUESTS immediately below
# for what replaces it).
QUESTS = {
    "Pilfered Goods":    dict(required=2, base_xp=2, gold_ladder=[4, 2, 1, 0]),
    "Syndicate Ledger":  dict(required=2, base_xp=2, gold_ladder=[4, 2, 1, 0]),
    "Contraband Crates": dict(required=2, base_xp=2, gold_ladder=[4, 2, 1, 0]),
    "Stolen Signet":     dict(required=2, base_xp=2, gold_ladder=[4, 2, 1, 0]),
    "Smuggled Cargo":    dict(required=2, base_xp=2, gold_ladder=[4, 2, 1, 0]),
    "Forged Ledger":     dict(required=2, base_xp=2, gold_ladder=[4, 2, 1, 0]),
    "Plundered Chest":   dict(required=2, base_xp=2, gold_ladder=[4, 2, 1, 0]),
    "Buried Treasure":   dict(required=2, base_xp=2, gold_ladder=[4, 2, 1, 0]),
}

# Zone 3/4's real quest table (DESIGN_DOC.md's "Node/quest table, locked" section, wired
# 2026-08-21) -- loot names and `required` counts are real and locked, matching the NODES
# entries above exactly.
#
# Gold-ladder, real derivation in progress (2026-08-21), not copied from Zone 1/2 wholesale --
# the original Zone 1/2 formula (flat [4,2,1,0] for required 2-4) assumed 2/3/4-loot quests all
# reliably finish in one trip, measured against Standard-tier mobs; against the real, harder
# Level 2 pool (18 Standard + 3 Elite) that assumption doesn't hold -- measured gold/turn at the
# old flat ladder: required=2 1.55, required=3 1.27 (-18%), required=4 1.04 (-33%), a real,
# growing underpayment as required increases. Required=2 kept as the baseline; required=3 and
# required=4 swept and locked to land close to that same rate (required=3 [5,3,2,0] -> 1.50
# measured, -3%; required=4 [7,4,2,0] -> 1.60 measured, +3%) rather than assumed. Required=5
# still the old placeholder, not yet swept the same way.
LEVEL2_QUESTS = {
    "Royal Signets":          dict(required=2, base_xp=2, gold_ladder=[4, 2, 1, 0]),  # Mud Trenches (Zone 3)
    "Consecrated Ash":        dict(required=3, base_xp=3, gold_ladder=[5, 3, 2, 0]),  # Ruined Abbey (Zone 3)
    "Ashen Vestments":        dict(required=4, base_xp=4, gold_ladder=[7, 4, 2, 0]),  # Pyre Fields (Zone 3)
    "Shattered Broadswords":  dict(required=5, base_xp=5, gold_ladder=[9, 5, 3, 0]),  # Broken Bridge (Zone 3)
    "Rusted Mail":            dict(required=2, base_xp=2, gold_ladder=[4, 2, 1, 0]),  # Charred Village (Zone 4)
    "Tarnished Crests":       dict(required=3, base_xp=3, gold_ladder=[5, 3, 2, 0]),  # Armory Gates (Zone 4)
    "Blessed Lamp Oil":       dict(required=4, base_xp=4, gold_ladder=[7, 4, 2, 0]),  # Gleaming Citadel (Zone 4)
    "Gilded Penance":         dict(required=5, base_xp=5, gold_ladder=[9, 5, 3, 0]),  # Sunward Throne (Zone 4)
}

FOOD_COST = 4
POTION_COST = 3
POTION_HEAL = 8
ITEM_STACK_CAP = 1  # a non-Food Bag slot (Potions, Quest Loot tokens, and any future
# Town-purchasable consumable) holds up to this many total items, any mix -- one unified rule
# instead of a separate cap per item type (locked 2026-08-22, replacing the old Potion-only
# POTION_STACK_SIZE=2 and the old uncapped/closable loot-slot model at the same time -- both
# shared the same real Bag-slot mechanism and needed the same fix together, not one now and one
# later. See DESIGN_DOC.md Section VI and MACRO_LOOP_GUIDE.md for the real-metrics finding that
# forced this: under the old model, `no_room` (bag-deadlock) never fired once in 3000+
# turn-samples per class, and a single loot slot was observed holding up to 11 items despite the
# design doc already claiming a cap of 3 was in effect.

# New Bag-slot consumables (DESIGN_DOC.md Section VI, checkpointed 2026-08-22 -- Scroll of
# Vanquishing/Smoke Bomb/Preserving Charm wired here; Whetstone deferred, see task #61, since
# its "+1 damage/+1 Block for one pull" effect needs a class-agnostic way to modify all 9
# classes' differently-shaped CARDS dicts, not just a Bag/Gold mechanism). Item keys share the
# same _add_item/_remove_item/_accessible_count multiset mechanism as Potions and Quest Loot.
SCROLL_COST = 5   # "scroll_of_vanquishing" -- guaranteed win, no combat played, Standard-tier
# mobs only (never Elite/Boss -- a flat, printed restriction that keeps Elite/Boss fights
# meaningful rather than buyable-around). Priced low relative to an early draft (was 9G) after
# checking real per-pull outcome rates directly: death is under 1% per pull and flee only
# 1.5-8.7% across the roster, so most pulls a Scroll gets used on would have been won anyway.
SMOKE_BOMB_COST = 3   # "smoke_bomb" -- guaranteed flee, no reward. Real value is backing out
# of a Border crossing after committing to the toll (resolve_border_crossing otherwise has no
# decline path at all), though it works on an ordinary declared Node too.
PRESERVING_CHARM_COST = 5   # "preserving_charm" -- Town-only, resets one active quest's
# decay_stage back to 0 without needing to have collected its loot.

CONSUMABLE_ITEMS = {
    "scroll_of_vanquishing": SCROLL_COST,
    "smoke_bomb": SMOKE_BOMB_COST,
    "preserving_charm": PRESERVING_CHARM_COST,
    "food": FOOD_COST,
    "potion": POTION_COST,
}  # Gold-purchasable at Town, repeatable (unlike the Purchase Queue's one-time acquired-tracked
# items) -- Bag-slot-gated. food/potion added 2026-08-26 (checkpointed with the user): a human
# player must be able to deliberately buy Food/Potion as a real action, not just receive it as
# an AI-only automatic leaving-town restock (M._leaving_town_setup, still the only mechanism
# for AI-driven trips, and still a real backstop for a human who forgets -- the "already_have"
# check there means buying manually just makes the automatic restock a no-op, never a double
# purchase). Whetstone isn't listed yet (task #61).

BAG_UPGRADE_COST = 12  # repriced 16 -> 12 (LEVELING_GUIDE.md's "Purchased-upgrade pricing,
# locked" section, 2026-08-20) -- checked against real Gold-at-Level-2 data: a player has
# ~11.7-13.1 Gold on average at 12 XP, enough to comfortably afford one 8G skill (leaving a
# real cushion) or land right at the edge on the Bag Upgrade, but not both -- a real first
# choice. This constant itself was still 16 here despite the doc saying it had been repriced --
# fixed 2026-08-21 while building the Class Trainer, which needed a correct SKILL_COST/
# BAG_UPGRADE_COST relationship to make purchase decisions against.
BAG_SIZE = 6
SKILL_COST = 8  # flat price for every purchased (non-mandatory) Level 2 upgrade, at the Class
# Trainer -- LEVELING_GUIDE.md's "Purchased-upgrade pricing, locked" section.
LEVEL2_XP_THRESHOLD = 6  # repriced 12 -> 6 (locked 2026-08-21, alongside the Level 1 quest
# compression above) -- deliberately identical to the 6 XP the fixed 3-quest starter batch
# always produces (3 x 2 XP), so finishing that batch and reaching Level 2 are the same event
# by construction, not a coincidence to keep in sync by hand. Mandatory upgrade grants on the
# first Trainer visit at or past this threshold; purchased upgrades become buyable at the
# Trainer only once past it too ("a player CAN'T buy a skill upgrade until they're at least
# level 2").
TRAINER_ZONES = {2, 4}  # Zones with a real Class Trainer -- Zone 4 joined 2026-08-21
# (DESIGN_DOC.md's Zone 3/4 section: "Zone 2 and Zone 4 mirror each other -- both get a full
# Town and the Class Trainer"). Zone 3, like Zone 1, is Town-only, no Trainer.

# Flight Path node, present in Zone 2 and Zone 4 (locked 2026-08-21) -- a paid shortcut
# connecting the two Zones directly, skipping the 2-hop Border Node route through Zone 3 (or
# Zone 1) entirely. Costs Gold, not a fight -- no Scouted Pull, no combat risk, unlike every
# other Zone crossing in this game. Using it costs no turn on its own, the same way ordinary
# intra-Zone movement is free -- a hero can fly and then immediately pull at a node in the
# destination Zone within that same turn (run_one_trip's routing below). Only usable standing
# in one of these two Zones already; doesn't shortcut a longer journey (e.g. Zone 1 -> Zone 4
# still needs a real Border Node crossing to reach Zone 2 or Zone 4 first).
FLIGHT_PATH_ZONES = frozenset({2, 4})
FLIGHT_PATH_COST = 2  # Gold

# Which Zones a hero can pick up (and turn in) quests at, by level (locked 2026-08-21). Named
# module-level constants specifically so isolated diagnostic tools (quest_cost_gauntlet.py) can
# patch them to match a synthetic single-Zone test -- _trip_chain's own quest-pickup and
# fallback-travel logic reads these, not a hardcoded literal, so an isolated test's hero doesn't
# wander off toward the real Zone 3/4 map chasing a "valid quest zone" that doesn't match its
# patched single test node.
LEVEL1_QUEST_ZONES = {1, 2}
LEVEL2_QUEST_ZONES = {3, 4}

# Level 2 upgrade data for the 6 classes with a real, locked slate (LEVELING_GUIDE.md).
# Runecaster/Druid/Necromancer don't have one yet, so they're simply absent here -- reaching
# Level 2 XP with one of those classes currently grants nothing (no mandatory upgrade to give),
# which is honest given none has been designed, not a bug to work around.
#
# LEVEL2_MANDATORY: class_name -> (mod, old_card_name, new_card_name, new_card_dict). Free (no
# Gold cost, matching "mandatory" everywhere else this project uses the word), but not
# automatic -- still requires physically visiting the Trainer at least once after reaching
# LEVEL2_XP_THRESHOLD to actually receive it (2026-08-21 revision -- an earlier version granted
# it the instant XP crossed the threshold regardless of location, no visit required at all).
#
# LEVEL2_PURCHASED_ORDER: class_name -> ordered list of (old_card_name, new_card_name,
# new_card_dict) -- this list's OWN order is just the sequence each card was derived/locked in
# during balance work, not a rule about acquisition order. Which one a hero actually buys
# 2nd/3rd/4th is randomized per hero instead (checkpointed 2026-08-23, see LEVELING_GUIDE.md's
# "Purchased upgrade order" entry -- board_engine.py's HeroBoardState.skill_purchase_order is
# a shuffled permutation of this list's indices, one per hero, matching a personally-shuffled
# deck of upgrade cards revealed one at a time). Not player-selected, deliberately: this is a
# quick, one-shot, non-legacy game, and letting players freely pick which upgrade to buy would
# let every table converge on the same "optimal" sequence over repeated sessions. Safe to
# randomize because LEVELING_GUIDE.md's own methodology already diagnosed each purchased
# upgrade independently against the minimum guaranteed baseline (mandatory-only) -- "Purchased
# upgrades are independent choices a player can take in any combination, not a fixed sequence"
# (verbatim) -- order was never a balance dependency to begin with. Callers with no per-hero
# shuffled order (the frozen _trip_chain baseline, or any HeroBoardState that doesn't populate
# skill_purchase_order) still walk this list in its own raw order -- backward compatible, not a
# second behavior to maintain.
LEVEL2_MANDATORY = {
    "warrior": (W, "Shield Block", "Shield Bash",
                dict(G=(1, 5), C=(2, 2), sunder=False, execute_finisher=False, chain_stance=None,
                     chain_bonus=0, chain_target=None, chain_requires=None, aggro_G=4, aggro_C=0)),
    "cleric": (C, "Heal", "Greater Heal",
               dict(dmg=0, heal=4, block=0, sacred_balance=False, max_hp_buff=0, echo_dmg=0, aggro=3)),
    "paladin": (P, "Invocation of Sanctuary", "Invoking Aura of Sanctuary",
                dict(dmg=3, heal=0, block=1, strike=False, invocation="sanctuary", aggro=3,
                     grants_aura_block=True)),
    "rogue": (R, "Evasion", "Evasion and Riposte",
              dict(kind="plain", dmg=2, block=10, strike=False, aggro=1)),
    "ranger": (G, "Beast's Challenge", "Beast's Stand",
               dict(dmg=None, block=1, grants_range=False, beast_bond=False, payoff_prev_range=False,
                    payoff_wolf=True, dmg_if_wolf=5, dmg_else=2, aggro=3)),
    "wizard": (Z, "Fire Blast", "Fire Blast",
               dict(dmg=(4, 4), block=0, grants_range=False, weave_source=True, payoff=False,
                    armor_pierce=True, aggro=1)),
    "runecaster": (N, "Tidal Ward", "Tidal Ward [Lv 2]",
                   dict(dmg=0, heal=2, block=3, grants_range=False, chain_bonus_if_prev=None,
                        chain_bonus_dmg=0, echo_dmg=0, echo_heal=0, aggro=1)),
    "necromancer": (Nc, "Boneguard's Offering", "Boneguard's Bargain",
                    dict(combat_type="melee", dmg=1, heal=0, block=2, grants_range=True, dot=False,
                         dot_payoff=False, echo_dmg=0, killing_blow=False, blood_magic=True,
                         boosted_dmg=4, boosted_heal=-3, boosted_block=2, aggro=0, version=2)),
}
LEVEL2_PURCHASED_ORDER = {
    "warrior": [
        ("Sundering Blow", "Dominate", dict(G=(2, 0), C=(2, 0), sunder=True, execute_finisher=False,
         chain_stance=None, chain_bonus=0, chain_target=None, chain_requires=None, aggro=4)),
        ("Heavy Swing", "Colossal Swing", dict(G=(2, 0), C=(5, 0), sunder=False, execute_finisher=False,
         chain_stance=None, chain_bonus=0, chain_target=None, chain_requires=None, aggro=2)),
        ("Vanguard Blade", "Vanguard Blade [Lv 2]", dict(G=(4, 2), C=(4, 0), sunder=False,
         execute_finisher=False, chain_stance="C", chain_bonus=2, chain_target="dmg", aggro=3,
         chain_requires="Vanguard Shield")),
    ],
    "cleric": [
        ("Fiery Fortitude", "Holy Fiery Fortitude", dict(dmg=4, heal=2, block=0, sacred_balance=False,
         max_hp_buff=2, echo_dmg=0, aggro=2)),
        ("Call of the Void", "Void Storm", dict(dmg=6, heal=0, block=0, sacred_balance=False,
         max_hp_buff=0, echo_dmg=0, aggro=3)),
        ("Void Mark", "Void Mark [Lv 2]", dict(dmg=4, heal=0, block=0, sacred_balance=False,
         max_hp_buff=0, echo_dmg=1, aggro=1)),
    ],
    "paladin": [
        ("Vigil of Light", "Sanctified Light", dict(dmg=0, heal=4, block=1, strike=False, invocation=None,
         aggro=2, grants_aura_block=False)),
        ("Invocation of Grace", "Invocation of Grace [Lv 2]", dict(dmg=5, heal=0, block=0, strike=False,
         invocation="grace", aggro=3, grants_aura_block=False)),
        ("Bastion's Hammer", "Bastion's Breaker", dict(dmg=5, heal=0, block=0, strike=True,
         invocation=None, aggro=2, grants_aura_block=False)),
    ],
    "rogue": [
        ("Quick Slash", "Quicker Slash", dict(kind="plain", dmg=4, block=0, strike=True, aggro=2)),
        ("Ambush", "Relentless Ambush", dict(kind="opener", dmg=3, round1_dmg=5, block=0, strike=True,
         bonus_rounds=(0, 1), aggro=3)),
        ("Backstab and Dodge", "Backstab and Dodge [Lv 2]", dict(kind="plain", dmg=4, block=2,
         strike=True, armor_pierce=True, aggro=3)),
    ],
    "ranger": [
        ("Sure Shot", "Bullseye", dict(dmg=5, block=0, grants_range=False, beast_bond=False,
         payoff_prev_range=False, aggro=2)),
        ("Sniper/Point Blank Shot", "Deadeye/Point Blank Shot", dict(dmg=None, block=0, grants_range=False,
         beast_bond=False, payoff_prev_range=True, dmg_if_prev_range=6, dmg_else=4, aggro=3)),
        ("Crippling Shot", "Crippling Shot [Lv 2]", dict(dmg=2, block=2, grants_range=True,
         beast_bond=False, payoff_prev_range=False, aggro=3)),
    ],
    "wizard": [
        ("Arcane Volley", "Arcane Barrage", dict(dmg=(6, 8), block=0, grants_range=False,
         weave_source=False, payoff=True, aggro=3)),
        ("Ice Barricade", "Ice Palisade", dict(dmg=(1, 1), block=10, grants_range=False,
         weave_source=True, payoff=False, aggro=2)),
        ("Snap Freeze", "Deep Freeze", dict(dmg=(2, 2), block=2, grants_range=True, weave_source=True,
         payoff=False, aggro=3)),
    ],
    "runecaster": [
        ("Lightning Bolt", "Lightning Bolt [Lv 2]", dict(dmg=4, heal=0, block=0, grants_range=False,
         chain_bonus_if_prev="Chain Lightning", chain_bonus_dmg=0, echo_dmg=0, echo_heal=0, aggro=2)),
        ("Earth Strike Rune", "Earth Strike Rune [Lv 2]", dict(dmg=2, heal=1, block=0, grants_range=False,
         chain_bonus_if_prev=None, chain_bonus_dmg=0, echo_dmg=2, echo_heal=1, aggro=0)),
        ("Windstrike", "Windstrike [Lv 2]", dict(dmg=6, heal=0, block=0, grants_range=False,
         chain_bonus_if_prev=None, chain_bonus_dmg=0, echo_dmg=0, echo_heal=0, aggro=3)),
    ],
    "necromancer": [
        ("Soul Harvest", "Soul Feast", dict(combat_type="ranged", dmg=4, heal=2, block=0, grants_range=False,
         killing_blow=False, dot=False, dot_payoff=False, echo_dmg=0, aggro=0, version=2)),
        ("Sowing Dread", "Sowing Dread [Lv 2]", dict(combat_type="ranged", dmg=3, heal=0, block=0, grants_range=True,
         killing_blow=False, dot=True, dot_payoff=False, echo_dmg=0, aggro=0, version=2)),
        ("Reap", "Grim Reap", dict(combat_type="ranged", dmg=4, heal=0, block=0, grants_range=False,
         killing_blow=False, dot=False, dot_payoff=True, dot_multiplier=2, echo_dmg=0, aggro=0, version=3)),
    ],
}
RISK_TOLERANCE = 0.15  # fraction of hands allowed to be lethal, when this pull would complete a quest
RISK_TOLERANCE_BASE = 0.0  # fraction allowed otherwise (quest not one pull from done, or a recovery pull)


def _pull_exceeds_risk(mod, has_stance, mob_name, class_name, hp, risk_tolerance, mob_pattern_hp=None):
    """True if the fraction of hands that would be lethal this pull (under
    optimal play) exceeds risk_tolerance. Short-circuits as soon as the
    answer is settled instead of always enumerating every hand -- each
    T._best_line call is a real exact solve (permutation enumeration), so
    this matters a lot at scale. At risk_tolerance=0 (the default) this
    stops at the very first lethal hand found, exactly matching the old
    hard-block rule's cost; higher tolerances still short-circuit once
    enough lethal hands are found to already exceed the threshold, even
    if not every hand has been checked.

    mob_pattern_hp: optional (pattern, mob_hp) pair, bypassing the mob_name -> T.MOBS lookup.
    Used by the Level 2 test pool (see run_one_trip's mob_level param), which draws directly
    from leveling_validation.mob_pool_for_level's weighted Standard+Elite pool instead of a
    named tier lookup -- Elites were deliberately never registered in T.MOBS/MOB_NAMES (see
    that param's own docstring for why), so there's no name to look up for them. mob_name is
    still required and used for the T.MOBS path when this is None."""
    pattern, mob_hp = mob_pattern_hp if mob_pattern_hp is not None else T.MOBS[mob_name][class_name]
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
    other hero exists in this model to have already populated the Zone. tier == LEVEL2_TIER:
    the destination Zone's real Level 2 pool (18 Standard + 3 Elite) via _named_pool_for_tier,
    otherwise byte-for-byte the same Standard-only draw as before (verified no-op)."""
    pool, weights = _named_pool_for_tier(class_name, tier)
    candidates = rng.choices(pool, weights=weights, k=2)
    cache = _scouted_pull_costpct_cache.setdefault(class_name, {})
    mod = CARD_SOURCE[class_name]
    has_stance = HAS_STANCE[class_name]
    max_hp = float(getattr(mod, HP_ATTR[class_name]))
    best_mob, best_cost = None, None
    for mob_name in candidates:
        if mob_name not in cache:
            pattern, mob_hp = _pattern_hp_for_mob(class_name, mob_name)
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
    gate the decision to cross at all, not the crossing's own outcome. tier == LEVEL2_TIER:
    includes the Elite trio via _named_pool_for_tier, otherwise unchanged."""
    pool, weights = _named_pool_for_tier(class_name, tier)
    cache = _scouted_pull_costpct_cache.setdefault(class_name, {})
    mod = CARD_SOURCE[class_name]
    has_stance = HAS_STANCE[class_name]
    max_hp = float(getattr(mod, HP_ATTR[class_name]))
    best_mob, best_cost = None, None
    # sorted(set(...)), not a bare set(...) -- a bare set's iteration order for string
    # elements is salted by Python's per-process hash randomization, which silently broke
    # this function's own documented "deterministic, no-rng" guarantee whenever a real tie in
    # cost% existed (found 2026-08-20: Warrior's chained-trip results varied run to run at an
    # identical seed, traced to this exact line -- ties are common enough for Warrior
    # specifically, likely due to its stance system, that the effect was visible there and
    # nowhere else). sorted() makes the tie-break reproducible instead of process-dependent.
    for mob_name in sorted(set(pool)):
        if mob_name not in cache:
            pattern, mob_hp = _pattern_hp_for_mob(class_name, mob_name)
            total_cost = 0.0
            for hand in mod.ALL_HANDS:
                seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, pattern, mob_hp, max_hp)
                total_cost += max_hp - hp_left
            cache[mob_name] = 100 * (total_cost / len(mod.ALL_HANDS)) / max_hp
        cost = cache[mob_name]
        if best_cost is None or cost < best_cost:
            best_mob, best_cost = mob_name, cost
    return best_mob


def _slot_total(slot):
    """Total item count in an item-holding slot ({"items": {name: count, ...}}), 0 for
    anything else (None, "food")."""
    return sum(slot["items"].values()) if isinstance(slot, dict) else 0


def _is_potion_slot(slot):
    """True if this slot currently holds at least one Potion -- may also hold other
    non-Food items mixed in, per the unified stacking rule (ITEM_STACK_CAP)."""
    return isinstance(slot, dict) and slot["items"].get("potion", 0) > 0


def _open_item_slot_index(bag, locked):
    """Index of an unlocked item slot with room (< ITEM_STACK_CAP total items), if any."""
    for i, slot in enumerate(bag):
        if not locked[i] and isinstance(slot, dict) and _slot_total(slot) < ITEM_STACK_CAP:
            return i
    return None



def _can_fit_food(bag, locked):
    return sum(1 for i, b in enumerate(bag) if b is None and not locked[i]) >= 3

def _add_food(bag, locked):
    empty = [i for i, b in enumerate(bag) if b is None and not locked[i]]
    if len(empty) >= 3:
        bag[empty[0]] = "food"
        bag[empty[1]] = "food_filler"
        bag[empty[2]] = "food_filler"
        return True
    return False

def _remove_food(bag, index):
    bag[index] = None
    removed = 0
    for i in range(len(bag)):
        if bag[i] == "food_filler":
            bag[i] = None
            removed += 1
            if removed == 2:
                break

def _bag_has_room(bag, locked):
    """Is there an item slot with room, or an empty unlocked slot to open one?"""
    if _open_item_slot_index(bag, locked) is not None:
        return True
    return any(not locked[i] and bag[i] is None for i in range(len(bag)))


def _add_item(bag, locked, item_name):
    """Add one unit of item_name (a Quest Loot name, 'potion', or any other Town-purchasable
    consumable's key) to any unlocked slot with room (< ITEM_STACK_CAP total items, any mix),
    opening a fresh (unlocked, empty) slot if none has room. Returns False only if there's
    truly no room (every slot locked or full) -- callers should check _bag_has_room before
    relying on this to always succeed. Quest Loot and every other non-Food item share this
    same mechanism -- one unified stacking rule, not one cap per item type (locked 2026-08-22,
    see ITEM_STACK_CAP)."""
    i = _open_item_slot_index(bag, locked)
    if i is not None:
        bag[i]["items"][item_name] = bag[i]["items"].get(item_name, 0) + 1
        return True
    for j, slot in enumerate(bag):
        if not locked[j] and slot is None:
            bag[j] = {"items": {item_name: 1}}
            return True
    return False


_add_loot = _add_item  # Quest Loot is just one more item type sharing the same slot mechanism


def _accessible_count(bag, locked, item_name):
    """Total item_name sitting in non-locked slots -- what the hero can actually use toward
    quest completion (for a loot name) or consume (for 'potion' etc.) right now. Locked
    (post-death) contents don't count until recovered."""
    return sum(
        slot["items"].get(item_name, 0)
        for i, slot in enumerate(bag)
        if not locked[i] and isinstance(slot, dict)
    )


def _remove_item(bag, locked, item_name, amount):
    """Removes up to `amount` of item_name from accessible (non-locked) slots -- used when a
    quest is turned in and its loot is handed over, or when a stackable consumable (Potion,
    etc.) is used. A slot that ends up holding nothing of any type goes back to None (reopens)."""
    remaining = amount
    for i, slot in enumerate(bag):
        if remaining <= 0:
            break
        if locked[i] or not isinstance(slot, dict):
            continue
        have = slot["items"].get(item_name, 0)
        if have <= 0:
            continue
        take = min(have, remaining)
        slot["items"][item_name] -= take
        if slot["items"][item_name] <= 0:
            del slot["items"][item_name]
        remaining -= take
        if not slot["items"]:
            bag[i] = None


_remove_loot = _remove_item  # Quest Loot is just one more item type sharing the same mechanism


def _engine_pull(class_name, mob_name, hand, pattern, mob_hp, starting_hp, decide_fn=None):
    """Runs one pull through the new turn-by-turn combat_engine (get_legal_actions/
    apply_action/QuestIntelligence.decide_combat) instead of condensed_trip.py's batch
    T._best_line/T._simulate call -- the macro-loop rewiring named in
    unified-sprouting-aurora.md's Part 5 step 5. Returns (win, final_hp, final_rounds),
    matching T._simulate's own return shape exactly so both of this module's real call
    sites can swap in this one-liner with no other change. decide_combat is a thin
    cache-and-replay wrapper around the same best_line_for_hand this file used to call
    directly (see combat_engine.py's own docstring), so this is not a second search --
    verified bit-for-bit identical to the old T._best_line/T._simulate path via
    sim/verify_combat_engine.py before this function's two call sites were rewired.

    decide_fn (checkpointed 2026-08-23, human-playable-combat slice): optional
    (state, actions) -> action callable, same signature as QuestIntelligence.decide_combat.
    None (every existing caller) preserves the exact AI-automatic behavior above --
    a fresh QuestIntelligence per call, same as before this parameter existed. A human-facing
    driver passes its own terminal-input decide_fn instead, so the identical round-by-round
    get_legal_actions/apply_action loop plays out a real human's choices rather than the
    solver's, without a second, parallel pull-loop implementation."""
    state = E.new_pull_with_hp(class_name, mob_name, hand, pattern, mob_hp, starting_hp)
    decide = decide_fn if decide_fn is not None else E.QuestIntelligence().decide_combat
    while state.outcome is None:
        actions = E.get_legal_actions(state)
        action = decide(state, actions)
        state = E.apply_action(state, action)
    return state.outcome == "win", state.hero_hp, state.round_num


def run_one_trip(class_name, strategy, rng, bag=None, locked=None, active_quests=None,
                  bag_size=BAG_SIZE, risk_tolerance=RISK_TOLERANCE,
                  risk_tolerance_base=RISK_TOLERANCE_BASE, corpse_node=None,
                  risk_only_as_last_resort=True, current_position=1, mob_level=1,
                  quest_pool=None, gold=0, fallback_target_zones=None):
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

    current_position: "a town is a town is a town" -- both Zones have full Town amenities
    (turn-in, decay, Bag Upgrade, Food/Potion restock), only the Class Trainer is
    Zone-2-exclusive, so a trip can end in *either* Zone with nothing special required to
    "get home" first. That means, unlike an earlier version of this function, position state
    persists *across* trips (passed in here, returned in the result for the caller to persist
    forward) rather than always resetting to 1 -- a hero who ended their last trip in Zone 2
    simply starts the next one there too. Either a real Zone number (1, 2, ...) or the name of
    a Border Node the hero is standing on (a string key into BORDER_NODES) -- a Border Node is
    its own physical position, not part of either Zone it connects (OPEN_QUESTIONS.md's
    "Border Nodes and Scouted Pull" entry), so surviving its toll does NOT put the hero "in"
    the destination Zone; it just makes every Zone that Border Node connects freely reachable
    next turn, no second toll.

    mob_level: test-only override, default 1 (the real, current game -- every node's mob draw
    stays Standard-tier-only, byte-for-byte unchanged). At 2, every node-pull mob draw (NOT
    the Border Node Scouted Pull crossing toll, which is left untouched) instead comes from
    leveling_validation.mob_pool_for_level's real Level 2 pool (18 Standard + 3 Elite, weighted
    3:1 to match physical card-copy counts) -- lets a fully-leveled Level 2 hero's card kit run
    through the real Town/Bag/Quest/Gold loop against Level 2 content, without having to first
    build the actual Level 2 zones/nodes this project doesn't have yet. Elites are deliberately
    NOT registered in condensed_trip.py's MOBS/MOB_NAMES for this (see leveling_validation.py's
    own docstring) -- every other diagnostic tool in this codebase assumes MOB_NAMES means the
    6 Standard mobs only, so this reads Elite patterns directly out of mob_pool_for_level's
    (pattern, mob_hp) tuples instead of through a mob-name lookup."""
    mod = CARD_SOURCE[class_name]
    has_stance = HAS_STANCE[class_name]
    max_hp = float(getattr(mod, HP_ATTR[class_name]))
    hp = max_hp

    if active_quests is None:
        active_quests = rng.sample(list(QUESTS.keys()), ACTIVE_QUEST_COUNT)

    if quest_pool is None:
        quest_pool = QUESTS  # which reward table active_quests' loot names resolve against --
        # _trip_chain passes LEVEL2_QUESTS once a hero is past LEVEL2_XP_THRESHOLD, since
        # the same loot names' `required` differs by phase (2026-08-21, Level 1 quest
        # compression). Standalone calls (no _trip_chain) keep defaulting to QUESTS.

    if fallback_target_zones is None:
        fallback_target_zones = {1, 2}  # where to travel when active_quests is empty (2026-08-21
        # -- a hero shouldn't be handed new quests just for crossing an XP threshold while
        # standing anywhere; they have to actually go to a valid quest-giving Zone for their
        # current level, same as picking up a mandatory upgrade requires a real Trainer visit).
        # _trip_chain computes the real value every trip: TRAINER_ZONES if a mandatory upgrade
        # is still owed (that takes priority), else the current level's quest Zones ({1,2} at
        # Level 1, {3,4} at Level 2). Standalone calls default to {1,2}, matching QUESTS' own
        # default above.

    if bag is None:
        bag = [None] * bag_size
        locked = [False] * bag_size
        if strategy == "food_only":
            _add_food(bag, locked)
        elif strategy == "potion_only":
            bag[0] = "potion"

    consumables_used = {"food": 0, "potion": 0}
    pulls = 0
    recovered = False
    pending_recovery = corpse_node
    border_crossings = 0
    flight_paths_used = 0
    zone_pulls = collections.defaultdict(int)  # Zone number -> pulls made there, any Zone --
    # not hardcoded to {1, 2}, since more Zones now exist once BORDER_NODES/NODES grow
    # `gold` (the parameter) is now mutated directly through this trip -- both +1 per won pull
    # (node, recovery, or Border crossing, never a flee -- locked 2026-08-21) and -FLIGHT_PATH_
    # COST whenever a Flight Path is taken (below) apply in real time, so a later decision
    # within the same trip sees the correct running balance (e.g. affordability of a second
    # Flight Path, however unlikely in one trip). The final value is returned via _make_result
    # and simply becomes _trip_chain's new gold -- no separate delta bookkeeping needed.

    def _make_result(**kwargs):
        return dict(pulls=pulls, bag=bag, locked=locked, active_quests=active_quests,
                    consumables_used=consumables_used, border_crossings=border_crossings,
                    flight_paths_used=flight_paths_used, zone_pulls=dict(zone_pulls), gold=gold,
                    current_position=current_position, **kwargs)

    def _cross_to(border_name, target_zone, tier):
        """Resolves one Scouted Pull toll to reach border_name, the Border Node connecting
        current_position's Zone to target_zone. Fully discretionary now that both Zones have
        Town -- the caller decides whether it's worth attempting before ever calling this (see
        the risk check just above each call site); by the time this runs, the hero has already
        committed. Uses a consumable first if the crossing looks risky and one's available,
        then attempts it regardless of outcome once committed -- a real death is possible here,
        same as any other pull.

        On success, current_position becomes border_name itself, NOT target_zone -- a Border
        Node is its own physical position, not part of either Zone it connects
        (OPEN_QUESTIONS.md's "Border Nodes and Scouted Pull" entry). The hero is free to pick
        any node in either connected Zone next turn, no second toll, the same way any other
        node-to-node move works -- they haven't actually entered target_zone yet, just reached
        the crossing point. Returns a death result dict if the hero dies crossing, else None
        (crossing succeeded, current_position/border_crossings/pulls/hp already updated by the
        time this returns). The toll pull itself isn't credited to either Zone in zone_pulls --
        it happens at the Border Node, not inside a Zone."""
        nonlocal hp, pulls, current_position, border_crossings, gold
        origin_zone = current_position
        mob_name = _scouted_pull_mob(class_name, tier, rng)
        # Elite-aware resolution (2026-08-21) -- tier can now be LEVEL2_TIER once wired into
        # real gameplay, and Elites aren't registered in T.MOBS the way Standard mobs are (see
        # _pattern_hp_for_mob's own docstring); a raw T.MOBS[mob_name] lookup here would
        # KeyError the instant a Border crossing drew an Elite name.
        pattern, mob_hp = _pattern_hp_for_mob(class_name, mob_name)
        if risk_only_as_last_resort:
            has_consumable = any(not locked[i] and (bag[i] == "food" or _is_potion_slot(bag[i]))
                                  for i in range(len(bag)))
        else:
            has_consumable = False
        if _pull_exceeds_risk(mod, has_stance, mob_name, class_name, hp, risk_tolerance_base,
                               mob_pattern_hp=(pattern, mob_hp)) and has_consumable:
            for i, slot in enumerate(bag):
                if locked[i]:
                    continue
                if slot == "food":
                    hp = max_hp
                    _remove_food(bag, i)
                    consumables_used["food"] += 1
                    break
                if _is_potion_slot(slot):
                    hp = min(max_hp, hp + POTION_HEAL)
                    _remove_item(bag, locked, "potion", 1)
                    consumables_used["potion"] += 1
                    break
        hand = rng.choice(mod.ALL_HANDS)
        win, final_hp, final_rounds = _engine_pull(class_name, mob_name, hand, pattern, mob_hp, hp)
        hp = final_hp
        pulls += 1
        border_crossings += 1
        if hp <= 0:
            # death_node encodes border_name:origin_zone:target_zone -- origin_zone lets the
            # caller (_trip_chain) respawn at the closest Town (the one in the Zone the hero
            # was departing FROM, since they hadn't actually left it when the toll pull
            # happened); border_name/target_zone let the recovery pull retry this exact
            # crossing attempt.
            return _make_result(completed=False, died=True, recovered=recovered,
                                 death_node=f"border:{border_name}:{origin_zone}:{target_zone}", hp=0)
        current_position = border_name
        if win:  # crossing itself succeeds on any survival (win or flee -- the toll's own
            # purpose is just getting past), but the +1 Gold specifically requires an actual
            # win, not a flee, matching the same standard node pulls use.
            gold += 1
        return None

    while True:
        if pending_recovery is not None and pending_recovery.startswith("border:"):
            # died mid-crossing last time -- recovery means attempting that same crossing
            # again (a fresh Scouted Pull, not a NODES lookup; there's no ordinary node at
            # a Border Node). Reuses _cross_to's own death handling, so a second death here
            # produces the identical death_node marker, same spiral-risk shape as dying
            # twice at an ordinary node. current_position was already set to origin_zone by
            # the caller (_trip_chain, respawning at the closest Town) before this trip
            # started, so only border_name/target_zone need re-extracting here.
            _, border_name, _origin_zone, target_zone_s = pending_recovery.split(":")
            target_zone = int(target_zone_s)
            died_result = _cross_to(border_name, target_zone, ZONE_TIER[target_zone])
            if died_result is not None:
                return died_result
            pending_recovery = None
            recovered = True
            continue
        if pending_recovery is not None:
            node_name = pending_recovery
            tier, loot_name = NODES[node_name]
            loot_name = None  # a recovery pull earns no loot, regardless of outcome
            target_zone = NODE_ZONE[node_name]
        elif not active_quests:
            # No quests at all -- a hero isn't handed new ones just for crossing an XP
            # threshold wherever they happen to be standing (2026-08-21 fix -- an earlier
            # version did exactly that, which made no sense: quests have to be picked up from
            # a real quest-giver, same as a mandatory upgrade requires a real Trainer visit).
            # Travel toward whichever Zone in fallback_target_zones is closest -- _trip_chain
            # sets that to TRAINER_ZONES first if a mandatory upgrade is still owed (that takes
            # priority), otherwise the current level's quest-giving Zones. If already standing
            # in one, there's nothing to actually DO this trip -- the pickup/Trainer service
            # itself happens at the next trip's Town turn (same shape as everything else
            # Town-adjacent) -- just end the trip here, no crossing needed.
            if isinstance(current_position, int) and current_position in fallback_target_zones:
                return _make_result(completed=True, died=False, recovered=recovered, hp=hp)
            target_zone = min(fallback_target_zones, key=lambda z: _hop_distance(current_position, z))
            node_name = None
            loot_name = None
        else:
            incomplete = [loot for loot in active_quests
                          if _accessible_count(bag, locked, loot) < quest_pool[loot]["required"]]
            if not incomplete:
                # A town is a town is a town -- the trip just ends here, wherever "here" is,
                # no crossing needed just to reach a Town that's already present in this Zone.
                return _make_result(completed=True, died=False, recovered=recovered, hp=hp)

            if not _bag_has_room(bag, locked):
                food_index = next((i for i, s in enumerate(bag) if not locked[i] and s == "food"), None)
                if food_index is not None:
                    hp = max_hp
                    _remove_food(bag, food_index)
                    consumables_used["food"] += 1
                else:
                    potion_index = next((i for i, s in enumerate(bag) if not locked[i] and _is_potion_slot(s)),
                                         None)
                    if potion_index is None:
                        return _make_result(completed=False, died=False, recovered=recovered, hp=hp)
                    hp = min(max_hp, hp + POTION_HEAL)
                    _remove_item(bag, locked, "potion", 1)
                    consumables_used["potion"] += 1

            # Route to whichever still-incomplete quest's node to visit next -- a rational
            # hero finishes everything closest to where they're already standing before ever
            # paying a Border Node toll (confirmed directly, not assumed: an earlier version
            # routed to plain incomplete[0], position-blind, and produced wildly inflated
            # crossing counts -- ~11 crossings to reach Level 2 + one skill, because it would
            # zigzag Zone 1 -> Zone 2 -> Zone 1 -> Zone 2 purely by quest-list order). Sorted
            # by _hop_distance (0 = freely reachable, covering both the ordinary same-Zone
            # case and standing on a Border Node) rather than a plain free/not-free boolean,
            # now that more than one Border Node can exist and "not free" isn't all the same
            # distance anymore.
            same_zone_first = sorted(incomplete, key=lambda loot: _hop_distance(
                current_position, NODE_ZONE[next(n for n, (t, l) in NODES.items() if l == loot)]))
            node_name = next(n for n, (tier, loot) in NODES.items() if loot == same_zone_first[0])
            tier, loot_name = NODES[node_name]
            target_zone = NODE_ZONE[node_name]

        can_fly = (isinstance(current_position, int) and current_position in FLIGHT_PATH_ZONES
                   and target_zone in FLIGHT_PATH_ZONES and current_position != target_zone
                   and gold >= FLIGHT_PATH_COST)
        if can_fly:
            # Flight Path: standing directly in Zone 2 or 4 with the target being the other one,
            # affordable -- a rational hero always takes this over the 2-hop Border Node route
            # when it applies, since it strictly dominates (fewer turns, zero combat risk, for a
            # small Gold cost). No `continue` here -- taking it costs no turn of its own (same
            # as ordinary free movement), so the node pull below still happens this same turn,
            # unlike an ordinary Border Node crossing (its own turn, landing on the Border Node
            # itself, one hop closer but not yet arrived).
            gold -= FLIGHT_PATH_COST
            flight_paths_used += 1
            current_position = target_zone
        elif not _reachable_free(target_zone, current_position):
            # Crossing is now fully discretionary in *both* directions -- since both Zones
            # have Town, there's never a "must get home" pressure forcing it the way an
            # earlier version required for the Zone-2 -> Zone-1 leg specifically. A rational
            # hero who judges the crossing too risky, with no consumable to back it up,
            # simply doesn't go -- they end the trip with whatever they've already got
            # (including, if current_position is Zone 2, just staying there and using Zone
            # 2's own Town), rather than being forced into a gamble they'd never actually
            # choose. Multi-hop: only the *next* Border Node on the shortest path gets
            # attempted this turn -- next_zone is the Zone that crossing actually leads to,
            # which may still be short of target_zone if more than one hop is needed; routing
            # re-evaluates fresh next turn the same way it always has (the `continue` below),
            # so further hops just happen one turn at a time rather than needing a pre-planned
            # whole route.
            border_name, next_zone = _next_border_toward(current_position, target_zone)
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
            # _cross_to makes if the hero does go). Judged against next_zone (the Zone this
            # specific crossing leads to), not target_zone (which may be further hops away).
            best_mob = _best_case_mob(class_name, ZONE_TIER[next_zone])
            if (_pull_exceeds_risk(mod, has_stance, best_mob, class_name, hp, risk_tolerance_base)
                    and not has_consumable):
                return _make_result(completed=False, died=False, recovered=recovered, hp=hp)
            died_result = _cross_to(border_name, next_zone, ZONE_TIER[next_zone])
            if died_result is not None:
                return died_result
            continue  # landing on the Border Node is its own turn -- the actual node pull
                      # (in either connected Zone) happens next iteration

        current_position = target_zone

        if node_name is None:
            # Arrived while traveling with zero active quests (the fallback_target_zones
            # branch above) -- nothing to pull for, no mob drawn. Loop back around: next
            # iteration re-evaluates from the top, sees current_position now matches a
            # fallback Zone, and ends the trip there (pickup/Trainer service happens at the
            # next trip's Town turn).
            continue

        # the specific mob is revealed on arrival, same as turning over a
        # monster token at the table -- drawn before the consumable
        # decision, not hidden from it. Weighted, not uniform -- see
        # condensed_trip.MOB_TIER_WEIGHTS (same weights for every class,
        # only how often each mob comes up changes).
        #
        # Two separate ways the real Level 2 pool can apply here, kept as genuinely separate
        # mechanisms rather than merged into one, so mob_level's already-validated numbers
        # from earlier this session stay exactly reproducible:
        #   - mob_level=2: a test-only blanket override forcing EVERY node this trip to draw
        #     Level 2 regardless of that node's own tier -- unchanged mechanism (rng.choice
        #     over leveling_validation's raw repeated-copy pool), see run_one_trip's own
        #     docstring for why.
        #   - tier == LEVEL2_TIER: a real Node/Zone permanently tagged with the Level 2 tier
        #     (no such Node exists yet -- Zones 3/4 aren't built) -- uses _named_pool_for_tier
        #     instead, so it shares the same named-mob caching _scouted_pull_mob/_best_case_mob
        #     already use for Border Node crossings into a Level 2 Zone.
        # Either way, mob_name stays None only for the mob_level=2 path (no name to give an
        # Elite there); the tier-based path always has a name, resolved via
        # _pattern_hp_for_mob, same as any Border Node crossing does.
        if mob_level == 2:
            mob_name = None
            l2_pattern, l2_mob_hp = rng.choice(LV.mob_pool_for_level(class_name, 2))
        elif tier == LEVEL2_TIER:
            pool, weights = _named_pool_for_tier(class_name, LEVEL2_TIER)
            mob_name = rng.choices(pool, weights=weights, k=1)[0]
            l2_pattern, l2_mob_hp = _pattern_hp_for_mob(class_name, mob_name)
        else:
            pool, weights = T.mob_pool_weights(tier)
            mob_name = rng.choices(pool, weights=weights, k=1)[0]
            l2_pattern = l2_mob_hp = None

        # Fluid risk: worth the higher tolerance only when this specific pull,
        # if won, would complete the quest being pursued -- a recovery pull
        # (loot_name is None) or a quest still 2+ away uses the lower base
        # tolerance instead. Matches how an actual player weighs the bet:
        # push your luck to close something out, don't for a quest you've
        # barely started.
        one_pull_from_done = (loot_name is not None
                               and _accessible_count(bag, locked, loot_name) == quest_pool[loot_name]["required"] - 1)
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

        l2_pair = (l2_pattern, l2_mob_hp) if (mob_level == 2 or tier == LEVEL2_TIER) else None
        if _pull_exceeds_risk(mod, has_stance, mob_name, class_name, hp, effective_risk_tolerance,
                               mob_pattern_hp=l2_pair):
            consumed = None
            for i, slot in enumerate(bag):
                if locked[i]:
                    continue
                if slot == "food":
                    hp = max_hp
                    _remove_food(bag, i)  # Food frees 3 slots
                    consumed = "food"
                    break
                if _is_potion_slot(slot):
                    hp = min(max_hp, hp + POTION_HEAL)
                    _remove_item(bag, locked, "potion", 1)
                    consumed = "potion"
                    break
            if consumed:
                consumables_used[consumed] += 1
                if _pull_exceeds_risk(mod, has_stance, mob_name, class_name, hp, effective_risk_tolerance,
                                       mob_pattern_hp=l2_pair):
                    return _make_result(completed=False, died=False, recovered=recovered, hp=hp)
            else:
                return _make_result(completed=False, died=False, recovered=recovered, hp=hp)

        pattern, mob_hp = l2_pair if l2_pair is not None else T.MOBS[mob_name][class_name]
        hand = rng.choice(mod.ALL_HANDS)
        win, final_hp, final_rounds = _engine_pull(class_name, mob_name, hand, pattern, mob_hp, hp)
        hp = final_hp
        pulls += 1
        zone_pulls[current_position] += 1

        if hp <= 0:
            return _make_result(completed=False, died=True, recovered=recovered, death_node=node_name, hp=0)

        if pending_recovery is not None:
            # survived the recovery pull -- win or flee, doesn't matter, the corpse is retrieved.
            # The +1 Gold still requires an actual win though, not just survival -- same
            # win-only standard as every other pull, not a separate rule for recovery.
            pending_recovery = None
            recovered = True
            if win:
                gold += 1
            continue

        if win:
            gold += 1
            if not _add_loot(bag, locked, loot_name):
                # shouldn't happen given the _bag_has_room check above, but stay safe
                return _make_result(completed=False, died=False, recovered=recovered, hp=hp)
        # if not win (fled), no loot gained, but the pull still happened -- loop continues


def _leaving_town_setup(strategy, bag, locked, gold):
    """Everything automatic that happens before heading back out: the strategy's one consumable
    gets restocked into an open item slot (or a fresh empty slot) if the hero doesn't already
    have one and can afford it. No "closed" slot state exists anymore -- every non-Food slot is
    just an item multiset capped at ITEM_STACK_CAP, nothing to reopen. Returns the (possibly
    reduced) gold."""
    if strategy == "food_only":
        already_have = any(not locked[i] and bag[i] == "food" for i in range(len(bag)))
        if not already_have and gold >= FOOD_COST and _can_fit_food(bag, locked):
            _add_food(bag, locked)
            gold -= FOOD_COST
    elif strategy == "food_stockpile":
        # food_only, but actually uses bag capacity beyond the base bag -- added 2026-08-21
        # specifically to test whether the Bag Upgrade's measured value was being understated
        # by food_only's fixed "always cap at exactly 1 consumable, leave everything else for
        # loot" rule, a definition written back when the bag was permanently 2 slots and never
        # revisited once it could grow. Keeps 1 slot's worth of loot capacity always reserved
        # (same balance the original 2-slot design had: 1 consumable, 1 loot), and uses any
        # additional slots for a second Food as a safety buffer, rather than leaving them idle
        # when nothing's currently open for loot.
        #
        # Rescaled 2026-08-25 alongside the bag-tetris migration (Food now costs 3 slots,
        # ITEM_STACK_CAP dropped 3->1): reserved_for_loot_slots is 3, not 1, because 1 old-style
        # loot slot (cap 3) is worth 3 new-style loot slots (cap 1 each) -- same "same balance"
        # property the base bag rescale already established (1 food + 3 items either way), just
        # applied here too. max_food now counts whole 3-slot Food units, not raw slot count. A
        # no-op, byte-identical to food_only, at the unupgraded 6-slot bag size
        # (max_food = max(1, (6-3)//3) = 1).
        food_count = sum(1 for i in range(len(bag)) if not locked[i] and bag[i] == "food")
        reserved_for_loot_slots = 3
        max_food = max(1, (len(bag) - reserved_for_loot_slots) // 3)
        while food_count < max_food and gold >= FOOD_COST and _can_fit_food(bag, locked):
            _add_food(bag, locked)
            gold -= FOOD_COST
            food_count += 1
    elif strategy == "potion_only":
        # Tops off exactly one item slot with Potions up to ITEM_STACK_CAP, never opens a second
        # one -- mirrors food_only's "only ever holds one consumable slot," always leaving the
        # other slot free for loot. A player with a second free slot may well choose to open
        # another Potion stack there instead of chasing loot, but that's a real, separate
        # strategy to test on its own footing, not the default "restock like food_only does"
        # comparison this one represents.
        stack_index = next((i for i in range(len(bag)) if not locked[i] and _is_potion_slot(bag[i])), None)
        if stack_index is None and gold >= POTION_COST:
            stack_index = next((i for i in range(len(bag)) if not locked[i] and bag[i] is None), None)
        if stack_index is not None:
            while gold >= POTION_COST and _slot_total(bag[stack_index]) < ITEM_STACK_CAP:
                if bag[stack_index] is None:
                    bag[stack_index] = {"items": {"potion": 1}}
                else:
                    bag[stack_index]["items"]["potion"] = bag[stack_index]["items"].get("potion", 0) + 1
                gold -= POTION_COST
    return gold


def _build_purchase_queue(class_name, bag_position=0):
    """The ordered list of Gold-costing purchases _trip_chain's Purchase Queue phase walks
    each Town turn (locked 2026-08-21, replacing separate bag_upgraded/owned_upgrades
    bookkeeping with one unified mechanism -- see _walk_purchase_queue). Bag Upgrade applies to
    every class (a general inventory purchase, unrelated to card kits); purchased skills only
    exist for classes with a real Level 2 slate (LEVEL2_PURCHASED_ORDER). bag_position is
    configurable purely for A/B measurement of where it should sit relative to the skills (0 =
    before all of them, len(skills) = after all of them) -- not yet locked to one value.

    Each item: tag (unique, also the key stored in the chain's `acquired` set once bought),
    cost, kind ("bag" or "skill"), requires_trainer (skills only -- must be standing in a
    TRAINER_ZONES Zone), requires_l2_started (bag only -- "started_l2_quests" must already be
    in `acquired`, per the direct instruction to buy it ASAP *after* Level 2 quests start, not
    merely after reaching Level 2 XP)."""
    bag_item = dict(tag="bag_upgrade", cost=BAG_UPGRADE_COST, kind="bag",
                     requires_trainer=False, requires_l2_started=True)
    skill_items = []
    if class_name in LEVEL2_PURCHASED_ORDER:
        for i in range(len(LEVEL2_PURCHASED_ORDER[class_name])):
            skill_items.append(dict(tag=f"skill_{i}", cost=SKILL_COST, kind="skill",
                                     requires_trainer=True, requires_l2_started=False, index=i))
    pos = max(0, min(bag_position, len(skill_items)))
    return skill_items[:pos] + [bag_item] + skill_items[pos:]


def _walk_purchase_queue(queue, acquired, bag, locked, current_position, gold, policy,
                          skill_purchase_order=None):
    """Walks queue in order, buying/applying whichever unowned items are both location-eligible
    and affordable, mutating `acquired`/`bag`/`locked` in place. Returns (gold, trainer_turn) --
    trainer_turn is True only if a skill was bought this call (Bag Upgrade is a general Town
    amenity, not a Trainer visit, matching DESIGN_DOC.md: Bag Upgrade "works identically at
    either" Town, unlike the Trainer-gated skills).

    Location ineligibility (wrong Zone for a Trainer-only skill, or Bag not yet eligible because
    Level 2 quests haven't started) always skips past that item regardless of `policy` -- it's
    not a Gold question, so the save/skip choice doesn't apply to it.

    policy='save': stop at the first item that's location-eligible but not yet affordable --
    Gold accumulates toward it rather than being spent on a lower-priority item further down.
    policy='skip': keep scanning past an unaffordable item for anything else in the queue that
    is affordable right now, buying out of strict order rather than saving up.
    Not yet decided which policy is actually correct -- kept as a parameter specifically so both
    can be measured and compared, not chosen by feel.

    skill_purchase_order (checkpointed 2026-08-23, replacing the old fixed
    LEVEL2_PURCHASED_ORDER sequence as the locked rule -- see LEVELING_GUIDE.md's "Purchased
    upgrade order" entry for the reasoning): optional per-hero shuffled permutation of skill-
    slot indices, matching a personally-shuffled deck of upgrade cards revealed one at a time.
    When provided, a skill item is only ever eligible once its own index is "next" in this
    hero's shuffled sequence -- every other not-yet-acquired skill is treated as temporarily
    ineligible, same as a wrong-Zone Trainer skill. None (the default) preserves the exact old
    fixed-order behavior unchanged -- used by the frozen `_trip_chain` baseline, which has no
    hero object to carry a shuffled order and isn't meant to gain new behavior."""
    trainer_turn = False
    skills_acquired_so_far = None
    if skill_purchase_order is not None:
        skills_acquired_so_far = sum(1 for tag in acquired if tag.startswith("skill_"))
    for item in queue:
        if item["tag"] in acquired:
            continue
        if item["requires_trainer"] and current_position not in TRAINER_ZONES:
            continue
        if item["requires_l2_started"] and "started_l2_quests" not in acquired:
            continue
        if skill_purchase_order is not None and item["kind"] == "skill":
            if (skills_acquired_so_far >= len(skill_purchase_order)
                    or item["index"] != skill_purchase_order[skills_acquired_so_far]):
                continue
        if gold < item["cost"]:
            if policy == "save":
                break
            continue
        gold -= item["cost"]
        acquired.add(item["tag"])
        if item["kind"] == "bag":
            # Appends 3 slots, not 1 -- see board_engine.apply_town_action's identical fix
            # (checkpointed 2026-08-25, bag-tetris rescale) for why.
            for _ in range(3):
                bag.append(None)
                locked.append(False)
        else:
            trainer_turn = True
            if skills_acquired_so_far is not None:
                skills_acquired_so_far += 1
    return gold, trainer_turn


def _trip_chain(class_name, strategy, rng, risk_tolerance=RISK_TOLERANCE,
                 risk_tolerance_base=RISK_TOLERANCE_BASE, bag_size=BAG_SIZE,
                 risk_only_as_last_resort=True, mob_level=1, purchase_policy="save",
                 bag_queue_position=0):
    """Yields one (trip_num, result, gold, xp, decay_stage, corpse_node,
    quests_completed_this_trip, trainer_turn_this_trip) per trip, forever -- callers apply
    their own stop condition. Town behavior and death handling live here, once (see module
    docstring). trainer_turn_this_trip: True only on a trip where a Class Trainer purchase
    actually happened this trip -- a real, separate turn from the Town turn (see its own
    comment above), needed by anything summing total turns for a fair cross-class comparison
    (OPEN_QUESTIONS.md's "What a turn is" entry).

    mob_level: passed straight through to run_one_trip -- see its own docstring. Default 1,
    the real game; a no-op unless explicitly set to 2 for the Level 2 test pool.

    purchase_policy, bag_queue_position: passed straight through to _walk_purchase_queue /
    _build_purchase_queue -- see their own docstrings. Neither is locked yet; both exist as
    parameters specifically so different values can be measured and compared, not assumed."""
    gold = 0
    xp = 0
    decay_stage = {loot: 0 for loot in list(QUESTS) + list(LEVEL2_QUESTS)}  # 0=Gold,
    # 1=Silver,2=Bronze,3=nothing -- covers both pools' loot names since the same hero moves
    # from one to the other mid-chain (2026-08-21, Level 1 quest compression).
    # Level 1 starter batch: exactly 3 of the 8 QUESTS, drawn once, never refilled -- see
    # QUESTS' own comment above. Once all 3 are turned in, xp == LEVEL2_XP_THRESHOLD exactly
    # and active_quests is empty; the turn-in branch below then draws a fresh log from
    # LEVEL2_QUESTS instead, with normal shuffled-refill replenishment from that point on.
    active_quests = rng.sample(list(QUESTS.keys()), ACTIVE_QUEST_COUNT)
    quest_bag = list(LEVEL2_QUESTS.keys()) * 3
    rng.shuffle(quest_bag)
    quest_discard = []

    def _draw_unique(target_list, count):
        nonlocal quest_bag, quest_discard
        drawn = 0
        while drawn < count:
            if not quest_bag:
                quest_bag = quest_discard
                quest_discard = []
                rng.shuffle(quest_bag)
            if not quest_bag:
                break  # completely empty ecosystem
            candidate = quest_bag.pop(0)
            if candidate in target_list:
                quest_discard.append(candidate)
            else:
                target_list.append(candidate)
                drawn += 1

    town_markets = {3: [], 4: []}
    _draw_unique(town_markets[3], 3)
    _draw_unique(town_markets[4], 3)
    bag = [None] * bag_size
    locked = [False] * bag_size
    _add_food(bag, locked)  # free starting Food, matching DESIGN_DOC.md's locked starting loadout --
    # previously missing here, so trip 1 of every chain silently started with an empty bag
    corpse_node = None  # set on death; the next trip's first pull is forced there to recover it
    # Every one-time milestone the hero can reach, unified into one set (locked 2026-08-21,
    # replacing the earlier separate mandatory_granted/bag_upgraded/started_level2_quests
    # booleans and the owned_upgrades set of skill indices) -- "mandatory", "started_l2_quests",
    # "bag_upgrade", and "skill_0"/"skill_1"/etc. (see _build_purchase_queue/
    # _walk_purchase_queue for the Purchase Queue tags specifically). A real, persistent
    # per-hero record, replacing every earlier static leveled_kit test (fully-upgraded,
    # mandatory-only, etc.) with the genuine thing: a kit that grows one purchase/milestone at
    # a time as the hero actually earns Gold and visits the right places.
    acquired = set()
    purchase_queue = _build_purchase_queue(class_name, bag_queue_position)  # constant for the
    # whole chain (class_name/bag_queue_position never change mid-chain) -- built once here
    # rather than every trip.
    # "A town is a town is a town" -- both Zones have full Town amenities, so position state
    # genuinely persists across trips now (a hero who ended a trip in Zone 2 starts the next
    # one there too), unlike an earlier single-Town version where every trip reset to Zone 1
    # by construction. See run_one_trip's own current_position docstring note for the full
    # reasoning. Always a real Zone at this specific point (never a Border Node name) -- a
    # trip only ever ends mid-Border-Node-crossing on death, handled in the death branch below.
    current_position = 1

    trip_num = 0
    while True:
        trip_num += 1
        gold = _leaving_town_setup(strategy, bag, locked, gold)

        # Which reward table active_quests' loot names resolve against this trip -- QUESTS
        # (the non-replenishing Level 1 starter batch) below LEVEL2_XP_THRESHOLD, then
        # LEVEL2_QUESTS permanently afterward (2026-08-21, Level 1 quest compression).
        # Computed once per trip and reused for both run_one_trip's own routing/risk decisions
        # and this trip's turn-in logic below, since active_quests' names were drawn from
        # whichever pool was active when they were set.
        pool = LEVEL2_QUESTS if xp >= LEVEL2_XP_THRESHOLD else QUESTS

        # === Phase 1: Logistics (locked 2026-08-21) -- always resolves before any spending
        # below, as an explicit rule rather than an accident of code order (the earlier version
        # of this function had a real bug from exactly that: a later block silently depended on
        # state a following block computed, and reordering required manually rearranging code).
        # Covers the two things that are about *becoming eligible* for something, not spending
        # Gold on it: quest pickup, and receiving the free mandatory upgrade.

        # Quest pickup: only at a real quest-giver's Zone for the hero's current level (Zone
        # 1/2 at Level 1, Zone 3/4 at Level 2) -- reaching an XP threshold entitles a hero to
        # new quests, it doesn't hand them over (2026-08-21 fix, matching the same "must
        # physically visit" principle the mandatory Trainer upgrade already uses). Only fires
        # when the log is actually empty -- Level 1's starter batch shrinks toward empty as it
        # completes, Level 2's log stays empty until this first fires. Folded into this same
        # Town turn, no extra turn cost, same as the very first batch at the start of the game.
        valid_quest_zones = LEVEL2_QUEST_ZONES if xp >= LEVEL2_XP_THRESHOLD else LEVEL1_QUEST_ZONES
        if not active_quests and current_position in valid_quest_zones:
            if pool is LEVEL2_QUESTS:
                active_quests = []
                while len(active_quests) < ACTIVE_QUEST_COUNT and town_markets[current_position]:
                    active_quests.append(town_markets[current_position].pop(0))
                _draw_unique(town_markets[current_position], 3 - len(town_markets[current_position]))
                acquired.add("started_l2_quests")
            else:
                active_quests = rng.sample(list(pool.keys()), min(ACTIVE_QUEST_COUNT, len(pool)))

        # Mandatory upgrade: free, but still requires physically visiting a Trainer Zone to
        # receive -- reaching Level 2 XP while standing elsewhere does NOT grant it immediately.
        if (current_position in TRAINER_ZONES and xp >= LEVEL2_XP_THRESHOLD
                and class_name in LEVEL2_MANDATORY and "mandatory" not in acquired):
            acquired.add("mandatory")
            mandatory_turn_this_trip = True
        else:
            mandatory_turn_this_trip = False

        # === Phase 3: Purchase Queue (Bag Upgrade + purchased skills, unified 2026-08-21) --
        # a rational hero always spends on a real permanent purchase over sitting on idle Gold,
        # same greedy-but-rational shape every other spending decision in this sim already uses
        # (Food/Potion restocking); the only real choices are *which* order and *whether to
        # save toward an unaffordable priority item or spend on a cheaper one instead* -- both
        # still open, see _build_purchase_queue/_walk_purchase_queue's own docstrings for why
        # they're parameters here rather than hardcoded.
        gold, purchase_trainer_turn = _walk_purchase_queue(
            purchase_queue, acquired, bag, locked, current_position, gold, purchase_policy)

        # trainer_turn_this_trip: a real, separate turn from the Town turn above -- the Class
        # Trainer is its own node (DESIGN_DOC.md: Zone 2 "holds both a second Town and the
        # Class Trainer"), not folded into Town's business despite both happening at the same
        # Zone in this sim's current level of abstraction. Only costs a turn when something
        # actually happens there -- a hero with nothing left to receive or buy doesn't detour
        # to the Trainer for no reason. The Bag Upgrade specifically does NOT count -- it's a
        # general Town amenity, not a Trainer visit (_walk_purchase_queue only sets its own
        # returned flag for skill purchases).
        trainer_turn_this_trip = mandatory_turn_this_trip or purchase_trainer_turn

        # The hero's real, current kit -- mandatory upgrade (free, but only once actually
        # picked up at the Trainer) plus whichever purchased upgrades have actually been
        # bought so far. Empty for a class with no Level 2 slate yet, or before the mandatory
        # upgrade has been collected -- leveled_kit with an empty swap dict is a harmless
        # no-op (verified: CARDS/DECK/ALL_HANDS rebuild identically to themselves), so this is
        # safe to apply unconditionally every trip.
        level2_swaps = {}
        if class_name in LEVEL2_MANDATORY and "mandatory" in acquired:
            _, old_name, new_name, new_card = LEVEL2_MANDATORY[class_name]
            level2_swaps[old_name] = (new_name, new_card)
            # A class can have its mandatory upgrade locked before any purchased upgrades
            # exist yet (checkpointed 2026-08-24, Runecaster's own in-progress leveling pass)
            # -- don't assume LEVEL2_PURCHASED_ORDER has an entry just because LEVEL2_MANDATORY
            # does. Same real KeyError, same fix, as board_engine._level2_swaps_for's sibling
            # guard (this is the older, pre-BoardState driver's own copy of the same logic).
            if class_name in LEVEL2_PURCHASED_ORDER:
                for i in range(len(LEVEL2_PURCHASED_ORDER[class_name])):
                    if f"skill_{i}" in acquired:
                        old_name, new_name, new_card = LEVEL2_PURCHASED_ORDER[class_name][i]
                        level2_swaps[old_name] = (new_name, new_card)

        # Where a hero with nothing to do travels toward (run_one_trip's own routing, when
        # active_quests is empty): the pending mandatory upgrade takes priority over getting
        # new quests, if one's still owed -- go get leveled up before going to find more work.
        # Otherwise, head for wherever this level's real quest-giver is.
        pending_mandatory = (class_name in LEVEL2_MANDATORY and xp >= LEVEL2_XP_THRESHOLD
                              and "mandatory" not in acquired)
        fallback_target_zones = TRAINER_ZONES if pending_mandatory else valid_quest_zones
        if fallback_target_zones == LEVEL2_QUEST_ZONES and not active_quests:
            # Only compare markets when there's something real to compare. An empty market used
            # to read as float('inf') ("infinitely bad"), permanently biasing away from that
            # zone forever -- real bug found live 2026-08-28: a zone whose market emptied under
            # heavy concurrent load never got revisited again for the rest of a 150-round run,
            # since nothing here ever gave it another chance even once its supply recovered. A
            # real player doesn't carry a permanent grudge against a Town they haven't checked
            # recently -- if either market is empty, leave both zones eligible and let normal
            # distance-based routing decide instead of asserting a preference from a comparison
            # that can't honestly be made yet.
            if town_markets[3] and town_markets[4]:
                avg_req_3 = sum(LEVEL2_QUESTS[q]["required"] for q in town_markets[3]) / len(town_markets[3])
                avg_req_4 = sum(LEVEL2_QUESTS[q]["required"] for q in town_markets[4]) / len(town_markets[4])
                if avg_req_3 < avg_req_4:
                    fallback_target_zones = {3}
                elif avg_req_4 < avg_req_3:
                    fallback_target_zones = {4}
        # Mob difficulty is a property of the PLACE (Zone 3/4's NODES/ZONE_TIER entries say
        # LEVEL2_TIER natively, same as Zone 1/2's say "standard"), never the hero's XP -- an
        # earlier version of this session wrongly tied it to LEVEL2_XP_THRESHOLD directly and
        # was reverted once caught (that would have made difficulty jump the instant a hero's
        # quest log flipped over, even while still standing in Zone 1/2, and never come back
        # down if they returned there later). No override needed here -- routing a hero toward
        # a quest whose node lives in Zone 3/4 naturally draws from LEVEL2_TIER via NODES.

        with LV.leveled_kit(CARD_SOURCE[class_name], level2_swaps):
            result = run_one_trip(class_name, strategy, rng, bag=bag, locked=locked,
                                   active_quests=list(active_quests), risk_tolerance=risk_tolerance,
                                   risk_tolerance_base=risk_tolerance_base, corpse_node=corpse_node,
                                   risk_only_as_last_resort=risk_only_as_last_resort,
                                   current_position=current_position, mob_level=mob_level,
                                   quest_pool=pool, gold=gold,
                                   fallback_target_zones=fallback_target_zones)
        current_position = result["current_position"]
        gold = result["gold"]  # run_one_trip now owns the whole in-trip Gold ledger: +1 per
        # won pull (node, recovery, or Border crossing, never a flee -- locked 2026-08-21) and
        # -FLIGHT_PATH_COST per Flight Path taken (below), applied in real time so a Flight
        # Path decision mid-trip sees the correct running balance. Both apply unconditionally,
        # even on a trip that ends in death -- Gold already spent/earned earlier in the trip
        # isn't undone by a later death, same as quest loot already collected isn't either.

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
                q = pool[loot]
                decay_stage[loot] = min(decay_stage[loot] + 2, len(q["gold_ladder"]) - 1)
            corpse_node = result["death_node"]
            # Respawn at whichever Town is closest -- the Town in the same Zone as the death
            # (DESIGN_DOC.md's "Death and corpse recovery" entry, clarified 2026-08-20 now that
            # both Zones have Town -- an earlier version of this always reset to Zone 1
            # regardless of where the death actually happened, which was wrong the same way
            # the old single-Town map assumption was wrong elsewhere). An ordinary node death
            # resolves the Zone directly via NODE_ZONE; a mid-crossing death (died attempting a
            # Border Node toll) respawns in the Zone the hero was departing FROM -- encoded as
            # origin_zone in the death_node marker, since they hadn't actually left that Zone
            # yet when the toll pull happened.
            if corpse_node.startswith("border:"):
                _, _, origin_zone_s, _ = corpse_node.split(":")
                current_position = int(origin_zone_s)
            else:
                current_position = NODE_ZONE[corpse_node]
        else:
            still_incomplete = []
            turned_in = []
            for loot in active_quests:
                q = pool[loot]
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

            if pool is QUESTS:
                # Level 1 starter batch: no replenishment, it just shrinks as quests complete --
                # never auto-refilled, not even once xp crosses LEVEL2_XP_THRESHOLD (2026-08-21
                # fix -- an earlier version handed over a fresh Level 2 log right here, the
                # instant the last starter quest completed, regardless of where the hero was
                # physically standing. Reaching Level 2 makes a hero *eligible* for new quests,
                # it doesn't hand them over -- the pickup logic above only fires on a real visit
                # to a Level 2 quest-giving Zone, same as the mandatory Trainer upgrade already
                # requires a real visit rather than granting on the XP threshold alone).
                active_quests = still_incomplete
            else:
                # LEVEL2_QUESTS: refills from this Town's own Quest Market. Real gap found live
                # (2026-08-28, auditing the Town Quest Market feature): town_markets only has
                # entries for zones 3/4 (TRAINER_ZONES/LEVEL2_QUEST_ZONES), but a hero can turn
                # in an already-active Level 2 quest at ANY Town, including zones 1/2 -- this
                # crashed with KeyError the instant that happened. Guarded here to the minimum
                # fix that stops the crash without inventing a new mechanic: no market means no
                # refill slot opens at THIS turn-in, the hero just carries fewer active quests
                # until they next visit an actual market zone. Whether a non-market Town should
                # refill from somewhere else instead (nearest market? no refill ever, by design?)
                # is a real open question this guard deliberately does not decide -- flagged for
                # the user, not resolved here.
                for loot in turned_in:
                    quest_discard.append(loot)
                newly_active = []
                market = town_markets.get(current_position)
                if market is not None:
                    while len(newly_active) < len(turned_in) and market:
                        newly_active.append(market.pop(0))
                    _draw_unique(market, 3 - len(market))
                active_quests = still_incomplete + newly_active
            quests_completed_this_trip = len(turned_in)

        yield (trip_num, result, gold, xp, dict(decay_stage), corpse_node, quests_completed_this_trip,
               trainer_turn_this_trip)


def run_to_bag_upgrade(class_name, strategy, rng, gold_goal=BAG_UPGRADE_COST, max_turns=1000,
                        risk_tolerance=RISK_TOLERANCE, risk_tolerance_base=RISK_TOLERANCE_BASE,
                        risk_only_as_last_resort=True):
    """Chains full trip-cycles until gold_goal is reached (or max_turns runs out)."""
    trip_log = []
    total_pulls = 0
    trainer_turns = 0
    for trip_num, result, gold, xp, decay_stage, corpse_node, quests_completed, trainer_turn in _trip_chain(
            class_name, strategy, rng, risk_tolerance=risk_tolerance,
            risk_tolerance_base=risk_tolerance_base,
            risk_only_as_last_resort=risk_only_as_last_resort):
        trip_log.append(result)
        total_pulls += result["pulls"]
        if trainer_turn:
            trainer_turns += 1
        town_turns = trip_num
        total_turns = total_pulls + town_turns + trainer_turns
        if gold >= gold_goal:
            return dict(turns=total_turns, gold=gold, xp=xp, log=trip_log)
        if total_turns >= max_turns:
            return dict(turns=None, gold=gold, xp=xp, log=trip_log)


def decay_stress_test(class_name, strategy, rng, max_turns=100, risk_tolerance=RISK_TOLERANCE,
                       risk_tolerance_base=RISK_TOLERANCE_BASE, risk_only_as_last_resort=True,
                       mob_level=1):
    """Chains full trips (not stopping at a gold goal) until total_turns >= max_turns, and
    tracks the worst decay_stage reached by any quest, the total quests
    completed over the whole chain, and whether the hero ever died.

    mob_level: passed straight through to _trip_chain/run_one_trip -- see run_one_trip's own
    docstring. Default 1, a no-op unless explicitly set to 2 for the Level 2 test pool.

    total_turns (OPEN_QUESTIONS.md's "What a turn is" entry, locked 2026-08-20): the real,
    comparable unit of play. A turn is either a pull (quest node,
    corpse recovery, or a Border Node toll -- all already counted in result["pulls"] per trip)
    or a Town visit (exactly one per trip in this chain -- a hero may do unlimited business in
    one Town stop, per the locked rule, so it's always worth exactly 1 turn regardless of how
    much happens there). Class Trainer visits aren't counted -- the simulator doesn't model
    in-trip skill purchases as an actual action yet, only as a static leveled_kit swap applied"""
    worst_decay_stage = 0
    died_count = 0
    total_quests_completed = 0
    total_pulls = 0
    trainer_turns = 0
    for trip_num, result, gold, xp, decay_stage, corpse_node, quests_completed, trainer_turn in _trip_chain(
            class_name, strategy, rng, risk_tolerance=risk_tolerance,
            risk_tolerance_base=risk_tolerance_base,
            risk_only_as_last_resort=risk_only_as_last_resort, mob_level=mob_level):
        worst_decay_stage = max(worst_decay_stage, max(decay_stage.values()))
        total_quests_completed += quests_completed
        total_pulls += result["pulls"]
        if trainer_turn:
            trainer_turns += 1
        if result["died"]:
            died_count += 1
        town_turns = trip_num  # one Town visit per trip in the chain
        total_turns = total_pulls + town_turns + trainer_turns
        if total_turns >= max_turns:
            return dict(gold=gold, xp=xp, worst_decay_stage=worst_decay_stage,
                        final_decay_stage=decay_stage, died_count=died_count,
                        total_quests_completed=total_quests_completed,
                        avg_quests_per_turn=total_quests_completed / total_turns if total_turns else 0,
                        ended_with_corpse=(corpse_node is not None),
                        total_pulls=total_pulls, town_turns=town_turns,
                        trainer_turns=trainer_turns, total_turns=total_turns,
                        gold_per_turn=gold / total_turns if total_turns else 0.0)


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


def risk_exposure_report(class_name, strategy="food_only", trials=300, seed=42, max_turns=20,
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

    def wrapped(mod_, has_stance_, mob_name, class_name_, hp, rt, mob_pattern_hp=None):
        result = orig(mod_, has_stance_, mob_name, class_name_, hp, rt, mob_pattern_hp=mob_pattern_hp)
        if rt == risk_tolerance and not result:
            # mob_pattern_hp is the real (pattern, mob_hp) for a Level 2 pull -- reading it here
            # matches _pull_exceeds_risk's own fallback exactly (real bug found live: this used
            # to always read T.MOBS[mob_name][class_name_], the Level 1 Standard-tier lookup,
            # even for a Level 2 mob passed in via mob_pattern_hp, silently logging the wrong
            # mob's stats for every Level 2 gamble).
            pattern, mob_hp = mob_pattern_hp if mob_pattern_hp is not None else T.MOBS[mob_name][class_name_]
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
            r = decay_stress_test(class_name, strategy, rng, max_turns=max_turns,
                                   risk_tolerance=risk_tolerance, risk_tolerance_base=risk_tolerance_base,
                                   risk_only_as_last_resort=risk_only_as_last_resort)
            deaths += r["died_count"]
            quests_totals.append(r["avg_quests_per_turn"])
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
                avg_quests_per_turn=sum(quests_totals) / len(quests_totals),
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


def persona_comparison_report(class_name, strategy="food_only", trials=300, seed=42, max_turns=20,
                               personas=None):
    """Runs risk_exposure_report once per named persona in RISK_PERSONAS (or a custom dict of
    {name: risk_tolerance}), instead of trusting the single, unvalidated RISK_TOLERANCE=0.15 as
    ground truth for a class's macro-loop numbers. Returns {persona_name: risk_exposure_report
    dict}. See persona_roster_report for the multi-class comparison table."""
    if personas is None:
        personas = RISK_PERSONAS
    return {name: risk_exposure_report(class_name, strategy, trials=trials, seed=seed,
                                        max_turns=max_turns, risk_tolerance=tolerance)
            for name, tolerance in personas.items()}


def persona_roster_report(class_names=None, strategy="food_only", trials=300, seed=42, max_turns=20,
                           personas=None):
    """persona_comparison_report across multiple classes at once, printed as a side-by-side
    table per persona -- the actual tool to run when checking whether an apparent outlier class
    (e.g. Rogue/Ranger's elevated deaths/run) is a robust finding or an artifact of the default
    15% threshold specifically. class_names defaults to the full roster (CARD_SOURCE.keys())."""
    if class_names is None:
        class_names = list(CARD_SOURCE.keys())
    if personas is None:
        personas = RISK_PERSONAS
    all_results = {c: persona_comparison_report(c, strategy, trials, seed, max_turns, personas)
                    for c in class_names}
    for persona_name, tolerance in personas.items():
        print(f"=== Persona: {persona_name} (risk_tolerance={tolerance}) ===")
        for c in class_names:
            r = all_results[c][persona_name]
            print(f"  {c:12s} deaths/run={r['deaths_per_run']:.2f}  quests/turn={r['avg_quests_per_turn']:.2f}"
                  f"  nothing-tier={r['decay_pct']['nothing']:.1f}%  gambles_taken={r['gambles_taken']:5d}"
                  f"  avg_lethal_frac={100*r['avg_lethal_frac']:.2f}%")
        print()
    return all_results


def compare_card_change(class_name, card_name, field_changes, strategy="food_only",
                         trials=300, seed=42, max_turns=20):
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
        before_risk = risk_exposure_report(class_name, strategy, trials=trials, seed=seed, max_turns=max_turns)

        for k, v in field_changes.items():
            mod.CARDS[card_name][k] = v

        after_floor = T.defense_floor_sweep(mod, has_stance, class_name, max_hp)
        after_risk = risk_exposure_report(class_name, strategy, trials=trials, seed=seed, max_turns=max_turns)
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
    print(f"Quests/turn: {before_risk['avg_quests_per_turn']:.2f} -> {after_risk['avg_quests_per_turn']:.2f}")
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


def decay_report(class_name, trials=500, seed=42, max_turns=20, risk_tolerance=RISK_TOLERANCE,
                  risk_tolerance_base=RISK_TOLERANCE_BASE, risk_only_as_last_resort=True):
    """Distribution of the worst decay_stage any quest reached over a
    fixed max_turns-long run, per strategy, plus how often a death
    happened at all (only possible when risk_tolerance > 0)."""
    strategies = ["none", "food_only", "potion_only"]
    print(f"=== {class_name.capitalize()}: worst bounty decay reached over {max_turns} turns ({trials} trials, risk_tolerance={risk_tolerance}/{risk_tolerance_base}) ===")
    for strategy in strategies:
        rng = random.Random(seed)
        counts = [0] * len(DECAY_LABELS)
        deaths = 0
        for _ in range(trials):
            result = decay_stress_test(class_name, strategy, rng, max_turns=max_turns,
                                        risk_tolerance=risk_tolerance,
                                        risk_tolerance_base=risk_tolerance_base,
                                        risk_only_as_last_resort=risk_only_as_last_resort)
            counts[result["worst_decay_stage"]] += 1
            deaths += result["died_count"]
        breakdown = "  ".join(f"{DECAY_LABELS[i]}:{100*c/trials:4.1f}%" for i, c in enumerate(counts))
        print(f"  {strategy:12s} {breakdown}   avg deaths/run: {deaths/trials:.2f}")


def productivity_report(class_name, trials=500, seed=42, max_turns=20, risk_tolerance=RISK_TOLERANCE,
                         risk_tolerance_base=RISK_TOLERANCE_BASE, risk_only_as_last_resort=True):
    """Average quests completed per turn, out of ACTIVE_QUEST_COUNT (3)
    possible, over a max_turns-long run -- the direct "how productive is
    a typical run" number, as distinct from single-trip completion rate
    (all-3-or-nothing) or decay (a distributional worst-case)."""
    strategies = ["none", "food_only", "potion_only"]
    print(f"=== {class_name.capitalize()}: avg quests completed per turn, out of {ACTIVE_QUEST_COUNT} ({max_turns}-turn runs, {trials} trials) ===")
    for strategy in strategies:
        rng = random.Random(seed)
        totals = []
        for _ in range(trials):
            result = decay_stress_test(class_name, strategy, rng, max_turns=max_turns,
                                        risk_tolerance=risk_tolerance,
                                        risk_tolerance_base=risk_tolerance_base,
                                        risk_only_as_last_resort=risk_only_as_last_resort)
            totals.append(result["avg_quests_per_turn"])
        avg = sum(totals) / len(totals)
        print(f"  {strategy:12s} avg {avg:.2f} of {ACTIVE_QUEST_COUNT} quests/turn")


if __name__ == "__main__":
    for class_name in CARD_SOURCE:
        compare_strategies(class_name)
        print()
        productivity_report(class_name)
        print()
        decay_report(class_name)
        print()
