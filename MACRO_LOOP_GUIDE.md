# Macro Loop Guide

How the Town/Bag/Quest/Gold layer (`sim/macro_sim.py`) works and how its numbers were
derived. This sits on top of `condensed_trip.py`'s exact-solver combat (never modifies it)
and chains individual pulls into trips, trips into a Town economy. Companion to
`CLASS_BALANCE_GUIDE.md` (per-pull card/mob balance) — this document is the trip-and-above
layer instead.

## Clean vs. aggregate metrics — a locked methodology rule, not just a note

**Never trust a macro-loop aggregate metric (`decay_report`'s deaths/run, decay-tier %, or
`run_to_bag_upgrade`'s avg trips) as a verdict on a card change without also checking
`condensed_trip.py`'s `defense_floor_sweep` for the same change.** They answer different
questions, and only one of them is safe to read in isolation.

**The incident this rule comes from.** While root-causing Ranger's macro-loop risk outlier
(see `CLASS_BALANCE_GUIDE.md`'s "Rogue and Ranger's macro-loop risk outlier"), a candidate fix
for Crippling Shot (2 DMG/3 Block, already a validated clean improvement) was tested with one
more point of damage (3 DMG/3 Block — nothing reduced, a strict upgrade on paper). Deaths/run
nearly *tripled* (0.11 -> 0.34). The instinct was to treat this as the card becoming
genuinely riskier. It wasn't: `defense_floor_sweep` proved the fight itself never got worse at
any fixed starting HP, for any mob, at any point in the comparison — mathematically guaranteed
for a change where nothing decreased (the previously-optimal line is always still available to
the exact solver, so the best outcome for any fixed hand/mob/HP can only stay the same or
improve). The real mechanism, confirmed by instrumenting the risk policy directly
(`risk_exposure_report`): the stronger card finishes quests faster, so the class reaches the
policy's *one* risk-bearing decision (a quest-completing pull with no consumable left) more
often over a fixed-length run — gambles taken rose ~15%, and reshaped HP trajectory across the
whole trip left it arriving at some *other*, unrelated matchups (Bruiser, Raider) with less
cushion than before, even though those specific fights were also provably no harder at a fixed
HP. More frequent exposure to an unchanged-or-better risk still produces more total losses,
purely as counting — nothing about combat got worse.

**Why this matters generally, not just for this one card.** `macro_sim.py`'s risk policy
(`RISK_TOLERANCE`/`RISK_TOLERANCE_BASE`) is a fixed, memoryless rule — it has no sense of how
many times it's already gambled this run, no adaptation, nothing beyond "would this pull
finish a quest, and is there no consumable left." Any change that makes a class more
*efficient* (almost always a damage change) will make it reach that trigger more often,
independent of whether the class actually became more dangerous. Block-only and HP-only
changes don't have this problem — they don't speed up kills, so they don't change how often
the risk-gate fires, which is why every clean Block/HP-only test in the Rogue/Ranger
investigation showed aggregate numbers that could be trusted directly. **Any damage-touching
change is a candidate for this artifact and needs the clean check before its aggregate numbers
mean anything.**

**The tooling that exists specifically to make this hard to get wrong again:**
- `condensed_trip.py`'s `defense_floor_sweep(mod, has_stance, class_label, max_hp)` — the
  clean, policy-independent signal. Sweeps lethal-hand-fraction across HP checkpoints and every
  mob; a genuine combat regression shows up here, a throughput artifact never does. Required
  for any new class's lock-in checklist now (`CLASS_BALANCE_GUIDE.md`), not just for
  investigating an existing outlier.
- `macro_sim.py`'s `risk_exposure_report(class_name, strategy, ...)` — the throughput-side
  complement. Reports how often the risk-gate actually fires (gambles taken) and how dangerous
  those specific gambles are, separate from the raw death count.
- `macro_sim.py`'s `compare_card_change(class_name, card_name, field_changes, ...)` — runs
  both of the above, before and after a proposed card edit, and prints an explicit verdict:
  real regression, clean improvement, or throughput artifact. Use this instead of running
  `decay_report` alone whenever evaluating a damage-touching change to a locked class.

**Scope note:** making the risk policy itself adaptive (aware of cumulative risk already taken
this chain, not a fixed threshold every time) would arguably fix this at the source rather than
the measurement, and would likely be a more realistic model of an actual careful player.
Deliberately out of scope here — that's a real game-design change, not a harness change, and it
would require re-validating every already-locked macro-loop number, not just the ones touched
by this incident.

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
`decay_report()` across all four classes then in the roster, `food_only`/`potion_only`
strategies, 500 trials x 20-trip chains: average deaths/run roughly halved for every class
(Warrior 0.23->0.09, Cleric 0.30->0.16, Wizard 0.31->0.16, Paladin 0.20->0.10), and worst-decay
("nothing" tier) rates dropped alongside deaths rather than trading off against them (e.g.
Wizard food_only 28.2%->14.4%). The `none` strategy is unaffected by construction (it never
carries a consumable, so the condition is always vacuously true) -- confirmed bit-for-bit
identical before/after, a useful sanity check that the change only touches what it's supposed
to.

**Rogue, Ranger, and Runecaster were missing from `macro_sim.py` entirely until caught during
the `DESIGN_DOC.md` audit** (`CARD_SOURCE`/`HP_ATTR`/`HAS_STANCE` only had the original four) --
fixed, then measured fresh against the current 6-mob roster (300 trials, `food_only`,
`chain_trips=20`): Warrior 0.09, Paladin 0.14, Wizard 0.18, Ranger 0.18, Cleric 0.19,
Runecaster 0.24, **Rogue 0.31** deaths/run. Rogue sits well outside the range the policy was
originally validated against (roughly 3.4x Warrior's rate, worst "nothing"-tier rate in the
roster at 30.7% vs. Warrior's 11.7%). **Root-caused** -- see `CLASS_BALANCE_GUIDE.md`'s "Rogue
and Ranger's macro-loop risk outlier": Rogue and Ranger are the only two classes whose
lethal-hand-fraction goes nonzero already at 50% HP, a full tier earlier than the rest of the
roster's clean 0% floor down to 33%, which the zero-tolerance risk policy reacts to directly.
Fix not yet decided.

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

**Re-swept against the current 6-mob/7-class roster** (this derivation was originally measured
against 5 mobs and 4 classes; the earlier note here speculated the price would still roughly
hold -- it doesn't, evenly, across the newer classes). 300 trials, `food_only`, average trips
to afford 16 gold: Paladin 3.83, Cleric 4.22, Warrior 4.33, Runecaster 4.34, Wizard 4.45,
**Rogue 5.07, Ranger 5.41**. The original four classes barely moved. Rogue and Ranger sit
noticeably above the rest of the pack -- **confirmed the same root cause as the death-rate
outlier above, not an independent pricing problem** (see `CLASS_BALANCE_GUIDE.md`'s "Rogue and
Ranger's macro-loop risk outlier"). Not yet re-priced; likely resolves on its own once that
root cause is fixed rather than needing its own separate change.

Solved for the actual price by sweeping `run_to_bag_upgrade` across candidate gold goals
against the real (non-isolated) 4-quest system, all four classes locked at the time
(Warrior/Cleric/Wizard/Paladin), `food_only`, 300 trials each, until the measured trips
landed in the target band. **Locked at 16 gold**, validated:

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

## Bag Tetris revision -- colored quest tokens, Food/Potion repricing, and the bugs found tuning it

Locked this session, replacing the previous "one open Bag slot, any mix of loot, Food closes
it" model entirely. Started from a user design pass questioning whether that model's decision
depth was real, checked piece by piece against the actual mechanics rather than accepted on
narrative logic alone.

**Loot representation was the first real problem, not the last.** The initial proposal was a
single generic Quest Loot token, disambiguated by sitting next to its quest card rather than
by a printed zone name -- clean on paper, but traced through and found to break Bag Tetris's
whole premise: if a token's identity is tracked by *position next to the quest card*, it isn't
simultaneously occupying a Bag slot, which means loot stops competing with consumables for
space -- the entire tension Bag Tetris (`CONDENSED_COMBAT.md`, `INSPIRATIONS.md`) exists to
create. **Fix: colored tokens instead of positioned ones.** Each quest gets a color; loot for
that quest is a token of matching color, placed in an empty Bag slot. Color and slot position
now encode two independent things (which quest, and how much Bag capacity it costs) instead of
forcing one position to carry both -- the token still fully competes with consumables for
space, same as before.

**Slots hold any mix of colors, deliberately not restricted to one color per slot -- a real
design correction, not an oversight left uncaught.** An earlier pass of this same idea
(including once already written into the docs before being caught) assumed same-color-only
per slot, reasoning it would keep each slot's contents legible at a glance. That's wrong for a
reason that has nothing to do with legibility: each Node maps to one specific quest's color
(`waystation`->Pilfered Goods, `cove`->Syndicate Ledger, etc.), so a same-color-only rule would
tie a player's *node choice* to their *current Bag state* -- already having Bag progress in one
color would quietly discourage pulling at a different, better-matchup node, since the
resulting token couldn't share space with what's already there. That directly undercuts the
"Comfortable against / Struggles against" hero-board routing this project already built
(`class_mob_matchup_chart.py`) -- the whole point of that system is letting a player route
toward favorable matchups turn to turn, and Bag-color purity has no business constraining that
choice. Mixed colors keep node choice (about the mob) and Bag capacity (about token count)
fully independent, which is what they should always have been.

**Stacking cap of 3, derived against the real quest table, not picked.** Checked every cap
from 1 to 5+ against the locked `required` values (2/3/4/5) and Bag size 2: cap=1 or 2 make
Stolen Signet (`required=5`) mathematically impossible to ever complete, regardless of trips
taken -- the Bag can never hold enough tokens at once. Cap=3 is the smallest limit where every
quest stays completable, and it produces real, escalating tension rather than flattening it:
the two smaller quests coexist with a consumable in the other slot, the two bigger ones force
giving that slot up entirely. Cap=4+ makes that sacrifice disappear for all but the single
biggest quest -- a much weaker version of the same tension.

**Food's slot-close was cut after being traced mechanically, not by feel.** Isolated its one
real effect (separate from healing): capping how much of *one* quest's loot could stack in a
slot, nudging toward diversification. It did not motivate a Town return -- HP and having no
more Food already forced that, with or without the close. With Bag size 2 already forcing a
near-trivial diversification choice on its own, the effect wasn't worth the extra rule a new
player has to learn. Cut. This reopened a real gap, though: Food's whole distinction from
Potion had been "pay more for less healing to avoid the close penalty" -- remove the penalty
and Food becomes strictly better on both price and healing, making Potion dead content.

**Fix: reprice both, and let Potion stack.** Food 2G->4G (still an uncapped full heal, never
stacks). Potion 4G->3G (still a flat 8 HP heal, but now **up to 2 can share one Bag slot**).
For the same one slot: one big guaranteed reset (Food) vs. two smaller heals at a lower total
Gold-per-slot (Potion) -- a real trade-off restored, not a narrative one.

**Validated with `decay_report` (the same 500-trial/20-trip-chain methodology already used for
the risk-policy lock above), and two real bugs were caught in the process, not just a pricing
check:**
1. A genuine **deadlock**: the bag-stuck recovery path only knew how to free a slot by eating
   Food. Once Potions could stack and fill both slots, a `potion_only` hero with no Food could
   get permanently stuck, unable to collect any loot ever again for the rest of that trip.
   Every class showed 100% "nothing"-tier decay for `potion_only` before this was caught --
   fixed by letting the recovery path drink a Potion as a last resort too.
2. An **unfair policy comparison**: the first restocking pass let `potion_only` greedily fill
   *both* Bag slots with Potions, unlike `food_only`, which only ever holds one Food and always
   keeps a slot free for loot. Capped `potion_only` to one Potion-stack slot, matching Food's
   own restocking behavior -- this, not the pricing, was the actual fix for the 100%-nothing
   result.
3. Also caught in passing, unrelated to pricing: `_trip_chain` (the real chained-trip entry
   point behind `decay_report`) never actually seeded the documented free starting Food --
   trip 1 of every chain silently began with an empty Bag. Fixed.

**Post-fix result, all 9 classes:** Food and Potion strategies both clearly and consistently
beat doing nothing, and neither dominates the other -- 6 classes come out ahead on Potion, 3 on
Food, none badly in either direction. A real, healthy choice, not a trap.

**Bag size stays explicitly open.** The proposal that started this (2 -> 4) is not locked --
flagged as the one lever here that needs its own back-solved derivation, the same way the
16-Gold Bag Upgrade price got one, rather than a number chosen by feel.

## Quest refill: shuffled-bag, no repeat until the pool cycles (locked 2026-08-19)

`active_quests` used to refill via a plain `rng.sample` from every quest not currently in the
log, meaning a quest could reappear on the very next roll immediately after being turned in --
a real fairness problem once quests can sit in different, travel-costed Zones (crossing a
Border Node isn't free, per `DESIGN_DOC.md`'s Inter-Zone travel rule), since an instant repeat
could mean doubling back on a trip that was just made. **Fixed with a shuffled bag, the same
"reshuffle on empty" shape already locked for mob decks** (`OPEN_QUESTIONS.md`'s "Zone-node mob
dealing" entry): `_trip_chain` now maintains a `quest_bag` list, shuffled once per full cycle
through every quest in `QUESTS`; each refill draws from the front, and the bag only reshuffles
once it empties. No quest can repeat until every other quest has appeared at least once since
its last appearance -- for the real physical game this would need more printed quest content
than the simulator needs (explicitly not a simulator concern, per direct user confirmation).

**A real bug caught and fixed while validating this, not just a clean implementation:** the
first version excluded only quests still sitting incomplete in the log from the reshuffle pool,
not quests already drawn earlier in the *same* refill batch -- when a bag emptied mid-batch (two
or more quests turning in on the same trip), the reshuffle could immediately hand back a quest
that had been placed into the log moments earlier in that same refill, producing a genuine
duplicate (the same quest appearing twice in one active-quest log). Caught by a direct assertion
check across a 20-trip trace before trusting the mechanic; fixed by also excluding
already-drawn-this-batch quests from the reshuffle pool. Re-verified duplicate-free across 20
trips and confirmed Gold-at-checkpoint numbers are unchanged (13.2 vs. the prior 13.0 for
Warrior at 12 XP, within normal Monte Carlo noise) -- the fix only changes *sequencing*, not the
underlying reward math.

## Level 1 quest compression, and +1 Gold per won pull (both locked 2026-08-21)

**Level 1 quest compression.** All 8 original Level 1 quests (`QUESTS`) flattened to
`required=2, base_xp=2, gold_ladder=[4,2,1,0]` -- every original required=2/3/4 quest already
shared this exact ladder, so flattening required down to 2 for the 3/4-required quests cost
nothing in Gold, only removed wasted turns; the two required=5 quests (Stolen Signet, Buried
Treasure) lose their higher `[9,5,3,0]` ladder too, a deliberate choice to flatten everything
uniformly rather than let them keep paying more at the reduced required count. `_trip_chain`
draws exactly 3 of the 8 at random as a hero's starter batch and does **not** refill it as
quests are turned in -- completing all 3 always nets exactly 6 XP (3 x 2), which is
deliberately identical to `LEVEL2_XP_THRESHOLD` (repriced 12 -> 6 in the same change): hitting
6 XP *is* reaching Level 2, by construction, not by coincidence needing to be kept in sync by
hand. Once the batch is exhausted, Zone 1/2 quest-giving is done for good for that hero --
`LEVEL2_QUESTS` takes over from that point on, with normal shuffled-refill replenishment. As of
2026-08-21 this is the real, locked Zone 3/4 quest table (8 real nodes across a real 4-Zone
loop, real loot names, real mob difficulty tied to those Zones) -- earlier in the same session
this reused the old pre-compression Zone 1/2 numbers/nodes as a stand-in, which was corrected
once the real Zone 3/4 map got built (see `DESIGN_DOC.md`'s Zone 3/4 section). The Gold-ladder/
XP numbers themselves are still a placeholder, not the real Zone 3/4 balance derivation --
`DESIGN_DOC.md` has the current status of what's still owed there.

Real, measured effect: turns to reach Level 2 dropped from 20.16 (old 12-XP threshold, mixed
replenishing pool) to 8.30 (new system) -- a 59% reduction, directly fixing the disproportionate
early-game slowdown found while comparing measured XP pacing against a hand-drawn target curve.
Gold at the Level 2 checkpoint landed almost unchanged (10.95 vs. the prior ~11-13), since the
flattened quests kept the same Gold ladders throughout.

**+1 Gold per won pull**, stacked on top of quest loot if applicable. Applies to any pull that
wins outright -- a quest-node pull, a corpse-recovery pull, or a Border Node toll crossing --
never a flee, matching the same win-only standard across all three pull types (a flee earns
nothing anywhere, not just at quest nodes). Applies at both Level 1 and Level 2 (the stub pool
above), not just one or the other.

Measured effect at the real, bounded Level 2 checkpoint (not an arbitrary long trip-count
average, which was checked first and correctly rejected as meaningless -- see below): Gold at
6 XP rose from 10.95 to 17.85 pooled across the roster, a real but modest +63%, tight and
consistent across all 9 classes (17.13-18.43). A hero now arrives at Level 2 able to
comfortably afford one 8G skill purchase with change left over, versus the old ~11-13 Gold
landing right at "afford one thing or the other, not both."

**Methodology note, worth keeping:** the first attempt to measure this change's effect used
Gold-per-turn averaged over an arbitrary 20-trip chain (193-231 total turns depending on
class) and reported swings of 110-227%. That number was correctly called out as meaningless --
a 20-trip chain runs far longer than an entire real playthrough (the target curve this whole
leveling pass was built against tops out around 90-150 turns for the *whole game*, Level 1
through 6), so an average computed that far past the point of relevance doesn't describe
anything a real player would experience. The real, decision-relevant comparison is Gold at an
actual bounded checkpoint (Level 2 arrival) -- which is the +63% figure above, not the
long-run rate. Default to short, real, bounded playthrough windows for economy questions, not
long stress-test chains, unless a long-run rate is explicitly what's being asked for.

## Bag Upgrade purchase, locked and wired 2026-08-21

Previously priced (`BAG_UPGRADE_COST`) but never actually bought in real gameplay -- the only
place the price was used was `run_to_bag_upgrade`, a diagnostic that measures *when it would
become affordable*, never actually spending the Gold or growing `bag_size`. Real purchase logic
built this session: **bought ASAP at the first Town turn with enough Gold, once Level 2 quests
have actually started** -- not merely reached Level 2 XP, the real quest-pickup event (see
`OPEN_QUESTIONS.md`'s quest-pickup entry). A general Town amenity like Food/Potion restocking,
not location-gated the way the Trainer or quest pickup are. Checked *before* the Trainer's
purchased-skill spending each Town turn, since "as soon as possible" takes priority over a
competing purchase rather than waiting its turn. `bag`/`locked` grow by one slot in place
(`.append`) the moment it fires; every bag-capacity helper (`_bag_has_room`, `_add_loot`, etc.)
already reads `len(bag)` directly, so this needed no other code changes to take effect
correctly. Verified directly: a hero's `bag_len` grows from 2 to 3 exactly once, tied to
`started_level2_quests` flipping True and Gold clearing `BAG_UPGRADE_COST`.

## Not yet done

- **Player-chosen quest pool.** `active_quests` is now a no-repeat-until-cycled shuffled bag
  (see above), but still drawn automatically by the sim, not actually chosen by the player from
  a curated set. The reward math and the no-repeat sequencing are both ready for this; the
  selection mechanic itself isn't built.
- **Node-difficulty as a second axis** (some nodes predetermined harder, independent of
  `required`) -- blocked on Spike-tier mobs, which are still empty/deferred.
- **Bag size derivation.** Currently 2 (unchanged); whether it should move, and to what,
  needs the same back-solved treatment the Bag Upgrade price and the Bag Tetris revision
  above got, not a guessed number.
