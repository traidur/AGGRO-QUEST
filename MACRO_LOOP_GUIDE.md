# Macro Loop Guide

How the Town/Bag/Quest/Gold layer (`sim/macro_sim.py`) works and how its numbers were
derived. This sits on top of `condensed_trip.py`'s exact-solver combat (never modifies it)
and chains individual pulls into trips, trips into a Town economy. Companion to
`CLASS_BALANCE_GUIDE.md` (per-pull card/mob balance) — this document is the trip-and-above
layer instead.

## Locked rule: risk policy defaults to "consumable before risk, always"

`run_one_trip` decides whether a pull is worth attempting at the higher risk tolerance
(some chance of a lethal hand is acceptable) or only the strict base tolerance (effectively
zero lethal-hand risk allowed), via `risk_only_as_last_resort`. Two policies existed:

- **Off** (the old default): any pull that would complete a quest this turn gets the higher
  risk tolerance automatically, even if there's an unused Food/Potion sitting in the bag
  that could heal first.
- **On**: that higher tolerance is only used as a genuine last resort — if there's an
  unlocked consumable available, use it (or retreat) instead of gambling.

**On is now the default everywhere** (all call sites in `macro_sim.py`). Validated via
`decay_report()` across all four classes, `food_only`/`potion_only` strategies, 500 trials
x 20-trip chains: average deaths/run roughly halved for every class (Warrior 0.23->0.09,
Cleric 0.30->0.16, Wizard 0.31->0.16, Paladin 0.20->0.10), and worst-decay ("nothing" tier)
rates dropped alongside deaths rather than trading off against them (e.g. Wizard food_only
28.2%->14.4%). The `none` strategy is unaffected by construction (it never carries a
consumable, so the condition is always vacuously true) -- confirmed bit-for-bit identical
before/after, a useful sanity check that the change only touches what it's supposed to.

## Quest reward formula: XP = required, Gold derived from measured trip cost

**XP is flat and simple:** `base_xp = required` (1 XP per loot item a quest asks for). No
formula needed beyond that -- it was the one piece that didn't need simulation to get right.

**Gold is not simply proportional to `required`**, and this took actual measurement to get
right, using the permanent `quest_cost_gauntlet.py` tool (see below). Two things had to be
found empirically, not guessed:

**1. Pulls barely scale with `required`, but trips do, and it's steep.** Isolating a single
quest type (no competition from other active quests) and chaining it: a 6-loot quest costs
about 6.3 actual pulls (~5% overhead over the 6 raw wins needed) -- almost the same overhead
as a 2-loot quest (~3%). Fights don't get meaningfully harder to complete as `required`
grows. But **trips** per completion grow much faster: 2-loot ~1.00, 3-loot ~1.07, 4-loot
~1.37, 5-loot ~1.85. The mechanism: only one Food is carried per trip, and the risk policy
above means the first HP scare gets healed through, but a second one (more likely on a
longer quest, since more pulls means more chances to get chipped down) forces a retreat with
no more loot gained that trip. So the real "cost" of a bigger quest isn't combat difficulty,
it's the chance of getting interrupted and needing a second trip.

**2. Bigger quests are also more likely to have already decayed their own reward by the time
they're turned in** -- a compounding penalty, not a separate one. Measured decay-stage-at-
turn-in: a 2-loot quest pays at full Gold-tier 99.8% of the time; a 5-loot quest pays at
full Gold-tier only 18.6% of the time (79.5% Silver). So pricing a big quest's Gold-tier as
if Gold-tier were the typical outcome overpays it on paper and underpays it in practice.

**The actual pricing rule, derived from both findings together:** price for the *quicker
half* of players (split by trips actually spent on that quest instance), not the population
average. Measured that the quicker half of 2/3/4-loot completions land at full Gold-tier
100% of the time (they reliably finish in one trip) -- so **gold does not need to scale with
`required` at all across 2-4**, XP is already doing that job. A 5-loot quest is where the
quicker half stops being all-Gold (37% Gold / 63% Silver, avg 1.63 trips), so its Gold-tier
is set high enough (~2.2x the flat rate) that this blended, realistic outcome still averages
out to fair per-trip pay for the players actually finishing it quickly -- not just the slow
tail. Silver/Bronze step down at roughly 60% of the previous stage, matching the shape
already used elsewhere in the ladder.

Locked `QUESTS` table (`sim/macro_sim.py`), G=4 as the flat 1-trip baseline rate:

| Quest | required | XP | Gold ladder (Gold/Silver/Bronze/nothing) |
|---|---|---|---|
| Pilfered Goods | 2 | 2 | 4 / 2 / 1 / 0 |
| Syndicate Ledger | 3 | 3 | 4 / 2 / 1 / 0 |
| Contraband Crates | 4 | 4 | 4 / 2 / 1 / 0 |
| Stolen Signet | 5 | 5 | 9 / 5 / 3 / 0 |

## `NODES`'s dead `loot_gold` column, removed

`NODES` used to carry a third tuple element (`loot_gold`) alongside tier and loot-card name.
Checked and confirmed it was never actually read anywhere -- gold is entirely computed from
`QUESTS[loot]["gold_ladder"]` at turn-in, a completely separate table. Removed the dead
column (`NODES` is now `(tier, loot_name)` pairs) rather than leave unused, misleading data
sitting next to the table that actually matters.

## `BAG_UPGRADE_COST`, repriced from 12 to 16, derived empirically

Old value (12) was inherited scaffolding, never deliberately paced -- measured that a player
could afford it in ~2 trips / ~3.7 quests / ~11 XP, which is barely a decision, closer to a
starting-loadout choice than an earned milestone.

Target chosen by design judgment, not simulation: **4-5 trips (~25-35 pulls)** before the
upgrade and a zone change. Reasoning: with only 5 Standard-tier mobs, mob variety *is* the
zone's content -- at ~7 pulls/trip (measured, the real 3-active-quest system), 4-5 trips
means each mob comes up ~5-7 times, enough to master the matchups without the puzzle going
stale.

Solved for the actual price by sweeping `run_to_bag_upgrade` across candidate gold goals
against the real (non-isolated) 4-quest system, all four classes, `food_only`, 300 trials
each, until the measured trips landed in the target band. **Locked at 16 gold**, validated:

| Metric | avg | median |
|---|---|---|
| Trips to afford | 4.50 | 4 |
| Pulls (actual fights) | 27.3 | 27 |
| XP earned by that point | 25.4 | 25 |

This number is coupled to the current 4-quest pool. If the curated-quest-pool work below
changes what's available to draw, or the mob roster changes, this needs to be re-swept, not
assumed to still hold.

## Tools

**`sim/quest_cost_gauntlet.py`** -- permanent, rerunnable (same convention as
`stat_gauntlet.py`/`pool_search.py` for mobs). Isolates a single quest type at a given
`required` count and measures real pulls/trips/decay-stage-at-turn-in cost, pooled across
all four classes. This is the tool that produced every number in the Gold-formula section
above. Re-run it whenever `required` options, the mob roster, or the risk policy change --
don't hand-guess a new curve.

## Not yet done

- **Player-chosen quest pool.** `active_quests` is still randomly sampled by the sim
  (`rng.sample`) every refill, not actually chosen by the player from a curated set. The
  reward math above is ready for this, the selection mechanic itself isn't built.
- **Node-difficulty as a second axis** (some nodes predetermined harder, independent of
  `required`) -- blocked on Spike-tier mobs, which are still empty/deferred.
- **Potion pricing vs. Food** -- never tuned against the new quest economy above.
