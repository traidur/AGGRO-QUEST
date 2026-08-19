# Class Balance Guide

How to balance a new condensed-combat class using the tools and methodology developed while
tuning Warrior, Wizard, and Cleric. This is a process document, not a history — see
`CONDENSED_COMBAT.md` for how those three classes actually got to their current numbers,
warts and all. Everything here generalizes to a fourth, fifth, sixth class.

**Read `DECK_CONDENSING_GUIDE.md` first if the class's 6-card kit doesn't exist yet** — this
doc assumes a legal, identity-expressing kit is already built and starts from tuning it.

## The module interface a new class must expose

Every class lives in its own `condensed_<name>.py` in `sim/`, and every diagnostic tool
in `condensed_trip.py` works against any class that exposes this exact surface (verified
against `condensed_cleric.py`):

- `<CLASS>_HP` — a module-level constant, the class's max HP.
- `CARDS` — dict of card name to its numbers (shape is class-specific: Warrior's has
  `G`/`C` stance variants, Wizard's has a `dmg` tuple for the Weave-boosted state, Cleric's
  is flat). `DECK = list(CARDS.keys())` must have exactly 6 entries.
- `simulate(seq_cards, [stance_seq,] mob_pattern, mob_hp, starting_hp=<CLASS>_HP)` — plays
  a fixed 3-card sequence, returns `(win, hp_left, rounds)`.
- `best_line_for_hand(hand, [mob_pattern,] mob_hp, starting_hp=<CLASS>_HP)` — searches
  every ordering (and stance sequence, if the class has one) of a 4-card hand, returns the
  best 3-card line by `(win, hp_left)` — a win always beats a non-win regardless of HP
  cost (see "always take the win" below).
- `win_rate(mob_pattern, mob_hp, verbose=False, starting_hp=None)` — single-pull win rate
  across all `C(6,4)=15` hands.

**Critical, hard-won detail on that last one:** `starting_hp` must default to `None` in
the function *signature*, then resolve to the live module constant *inside the function
body* — never `starting_hp=<CLASS>_HP` as the parameter default itself. Python evaluates
default parameter values exactly once, at import time. A parameter default frozen that way
will silently keep using the class's HP as it was when the module first loaded, even after
you deliberately reassign `Z.WIZARD_HP = 14` to test a lever. This bug existed in all three
classes' `win_rate()` for most of this project and produced at least one wrong "no effect"
finding before being caught. See the fixed versions in any of the three existing modules.

If a class needs a mechanic none of the three existing ones have (a resource that persists
differently, a new evasion type, whatever), the shape of `CARDS` can flex, but the four
function signatures above are load-bearing — every tool in `condensed_trip.py` calls
through them generically via `_simulate()`/`_best_line()`, never touching a class's
internals directly. Confirmed on a real fourth class (Paladin) — the interface held with
zero changes, only the internal `simulate()` body grew a new mechanic.

**When adding a class beyond the third, check for hardcoded class-count assumptions in
shared tooling before trusting its output.** Two were found and fixed while adding
Paladin, both silent (no crash, just wrong or missing output): `pairwise_genuine_difference`
computed a card's max HP with `mod.CLERIC_HP if ... else mod.WARRIOR_HP if ... else
mod.WIZARD_HP` — a fourth class hit the `else` and crashed on a missing attribute, easy to
catch; worse, `full_report()`'s single-pull-win-rate section hard-coded exactly `W.win_rate`/
`Z.win_rate`/`C.win_rate`, which would have silently just never shown Paladin's numbers at
all, no error, nothing to notice. Both are now fixed generically (the first takes `max_hp` as
a parameter instead of re-deriving it; the second builds its function-lookup dict from
`CLASSES` itself). The lesson generalizes: any function that lists class names or count
explicitly, instead of iterating over a shared `CLASSES`/`class_specs` list, is a latent bug
for the next class — grep for the previous class's name literally appearing in
`condensed_trip.py` before considering a new class "supported."

## The tool inventory (`condensed_trip.py`)

Run these roughly in this order on a new class:

1. **`full_diagnostic(label, mod, has_stance, mob_key, max_hp, max_hp_attr)`** — the first
   gate. Damage floor/ceiling (now backed by `damage_distribution()`, which also prints the
   *full* sorted per-hand distribution plus mean/stdev/range — see below, floor/ceiling alone
   can hide the shape), healing floor/ceiling, equilibrium check (catches the "cannot die"
   bug class — always check multiple starting-HP levels, not just full health), unplayed-card
   spread, hidden-domination pairwise check, permutation variance, tie density, flee
   preference, waste index. If this isn't clean, nothing downstream is worth trusting.

   **`damage_distribution(mod, has_stance, mob_key, max_hp)`** on its own (returns
   `(ceiling, floor, {per_hand, mean, stdev, range})`) is worth running as a standard part of
   evaluating any class, new or existing, not just when floor/ceiling look off. Two classes
   can have near-identical floor/ceiling and completely different shapes underneath: Warrior
   is the tightest in the roster (stdev ~1.1, range 4 — every hand does roughly the same
   thing, consistent with a binary stance choice rather than a combinatorial one), Wizard the
   widest (stdev ~2.2, range 8, floor of just 8 — the glass-cannon identity showing up
   directly in the distribution's shape, not just its average). Also the tool that resolved a
   real worry about Rogue's early drafts: a near-zero flee-preference rate initially looked
   like it might mean "less likely to hit its own floor" (a distribution-shape explanation),
   but the actual distribution showed Rogue's mean was the *highest* of the five classes, not
   lower — ruling that theory out and pointing at the real mechanism instead (a killing-blow
   rider tying "win" and "preserve HP" together on 92% of that class's wins, see its own
   build notes). Don't assume a plausible-sounding distribution theory without checking the
   actual numbers — this is exactly the kind of thing that's cheap to verify and easy to get
   wrong by eyeballing.
2. **`kill_round_table(class_specs)`** — which round (1/2/3) the optimal line actually
   kills in, per mob and aggregate. Tells you whether the new class's *identity* matches
   its intended pacing (a burst class should show real round-1/2 weight; a grind/sustain
   class will skew round-3 — neither is wrong, but check it matches what you designed for).
3. **The survivability variance/spread check** (no standing function yet — see the
   outcome-spread script used for the Wizard case study, easy to lift and rerun; distinct
   from `damage_distribution()` above, which measures raw damage *output* against a dummy,
   not HP *left over* against a real mob). For a fixed hard mob, look at
   the range of `hp_left` across all 15 hands. A glass-cannon class should show a *wide*
   spread relative to its own max HP (some hands = clean win, some hands = scraping by). A
   tank/sustain class should show a narrow spread. If a class shows a narrow spread AND
   weak numbers, that's a flatly-undertuned kit, not a variance problem, and needs a
   different fix than a class showing wide spread and weak numbers.
4. **The per-round economy decomposition** (still a one-off script as of the Paladin build,
   worth promoting to a standing function now that a fourth class has used it twice) —
   separates "average net HP lost per round" into its actual sources: raw incoming damage,
   block absorbed, healing received, and any evasion-style prevention (Wizard's Range). This
   is the tool that catches the difference between "this class's kit isn't pulling its
   weight" and "this class's kit is fine, its HP pool is just too small for it" — Wizard
   turned out to have the *best* per-round economy of the three original classes and still
   the worst overall survivability, purely because its pool (10) was undersized relative to
   how efficient the kit already was. Always run this before reaching for any card-number
   fix. **Validated as a fast first-draft predictor on Paladin**: targeting the ~1.57-1.81
   mitigation/round band the original three classes established landed Paladin's *final*
   locked kit at 1.65/round almost by construction, even though the actual path there was
   driven by hand-level bug fixes, not the formula directly. Use it to get the right
   neighborhood fast — it will not catch the next item.
4a. **Hand-level kill-feasibility check** (new, added after the Paladin build found a real
   gap the floor/ceiling average couldn't see) — for each mob a class might realistically
   face, count how many of the 15 possible hands are *mathematically incapable* of killing
   it at all, regardless of play. Paladin's damage floor read as "8, close enough to the
   other classes' 8-10" while a full 8 of 15 hands (53%) couldn't kill Brute or Elite under
   any line — the floor number is a single worst-case hand, not a distribution, and a class
   can have a merely-mediocre floor while still having more than half its hands be outright
   dead on arrival against specific content. Compute by checking, per hand, whether any
   ordering's total raw damage (accounting for the real mob's per-round block, not a dummy)
   reaches the mob's HP. Cross-reference which cards are missing from the failing hands —
   that's usually the actual lever (Paladin's failing hands all lacked at least one of its
   two STRIKE cards), not a flat numeric bump across the board.
5. **`flee_preference_table(class_specs)`** — per-mob and aggregate rate of "the
   HP-maximizing line doesn't kill the mob." This is a measurement, not a pass/fail check —
   see "the flee-value question" below for why it can't be graded in isolation.
6. **`full_report()` / `compare_reports()`** — the full three-section report (mixed-roster
   trip stats, per-mob repeated trip stats, single-pull win rate per mob), and a
   before/after diff. This is the standing tool for "twist one lever, see what changed" —
   twist the lever by reassigning a module constant (`Z.WIZARD_HP = 14`) or editing a
   `CARDS` entry, then call `full_report()` again and diff. Don't hand-roll a new print
   script for this; it already exists.

   Both sections also print **wins/pull** (`avg wins / avg pulls survived`) alongside the raw
   pulls and wins numbers, and `compare_reports()` diffs it in percentage points. This is a
   distinct question from either raw number alone: "of the pulls a class actually gets, what
   fraction end in an actual kill rather than a flee/timeout." Two classes can land at the
   same pulls-survived and still convert that survival into wins at different rates — this
   surfaced for real on a Rogue draft whose pulls-survived matched the rest of the roster
   almost exactly (5.24 vs. 5.25-5.74) while its wins/pull sat 2-5 points above everyone else
   (78.1% vs. a 73.0-75.8% band), because a killing-blow rider meant going for the kill rarely
   cost anything extra. Parity on pulls-survived alone doesn't rule this out — always check
   both.

7. **`register_class_for_testing(mob_key, needs_range_tag=...)` + `tuning_report(...)`** —
   the standard way to iterate on a class *before* it's locked into `CLASSES`. Register once
   (wires the class into `MOBS` and, if it has a `grants_range`-style mechanic, into
   `_dummy_pattern`'s range-aware set — no more hand-editing `_dummy_pattern` for a new
   class, it's automatic now), then call `tuning_report(label, mod, has_stance, mob_key,
   max_hp, max_hp_attr, run_trip_fn)` for the complete picture in one call: `full_diagnostic`,
   per-mob win rate, flee-preference, and a chained trip comparison against every locked
   class with the pack's min/max range and an explicit in-range/out-of-range verdict per
   metric. Replaces the ad hoc monkey-patch-`MOBS`-then-copy-a-60-line-script pattern used
   throughout the Rogue and Ranger builds — that pattern got retyped by hand well over a
   dozen times across those two sessions before this got promoted to a real function. See
   "Numeric tuning playbook" below for what the numbers this prints actually mean and which
   levers move which of them.

Every one of these is class-agnostic by construction (`has_stance` flag, generic
`mob_key`) — a fourth class plugs in without modifying any tool, only by adding its own
`(label, mod, has_stance, max_hp)` tuple to a `class_specs` list.

## "Always take the win" — the assumption baked into every tool

`best_line_for_hand`'s sort key is `(win, hp_left)`. Any line that kills the mob beats any
line that doesn't, no matter how much HP the kill costs. Every win-rate and trip-stat
number in this whole toolkit assumes a player who never voluntarily bails on an achievable
kill to save HP.

This was tested, not assumed: a fleeing mob currently gives no reward, and the multi-pull
question — would a HP-maximizing player who deliberately avoids costly kills actually
survive to produce *more total wins* over a long trip — was checked directly (see
`CONDENSED_COMBAT.md`/session history). It does not. A "maximize HP, don't chase costly
kills" strategy survives more *pulls* but produces fewer total *wins*, because the extra
survived pulls are pulls that end in nothing. Under a reward scheme where a voluntary flee
is worth ~0 unless it's the only thing keeping you alive (the locked design conclusion —
see below), always-take-the-win is the mathematically correct strategy, confirmed across
all three existing classes. Re-verify this on a new class only if its kit introduces a
mechanic that could make voluntary fleeing genuinely valuable in a way HP-preservation
alone doesn't capture (e.g., a resource that only builds while alive and not fighting).

## The flee-value question — locked conclusion, still worth restating per class

Flee-preference is explicitly documented as "measurement only" in its own docstring
because a fleeing mob's actual reward was undecided for most of this project. The
resolution: **a tie/flee should be worth approximately nothing unless it's the only thing
that kept the hero alive.** Reasoning:

- Every case the flee-preference metric counts is, by construction, a case where a
  *winning* line was achievable (`best_win_hp is not None`) — the metric explicitly skips
  hands with no winning line at all. So every flee-preference case is a *voluntary*
  trade-off, never a forced one.
- If a voluntary flee pays out near-zero, any positive win reward beats it outright,
  regardless of the HP cost of winning. This collapses the entire "how big does loot need
  to be" question, which otherwise requires modeling an unknown reward-to-HP conversion
  rate (tested at length — for context, closing the gap through raw reward size alone would
  have required a kill's value to be worth roughly a third to half of a class's max HP,
  which is an absurd number to actually put in the game).
- A **round-based loot-decay curve** (faster kills worth disproportionately more loot) was
  also tested as an alternative fix for cross-class balance and rejected: solving for the
  multiplier needed to equalize Wizard with Warrior required a ~3.5x premium on round-2
  kills over round-3 kills. That's not just a big number — it's a universal speed tax that
  would also punish Warrior for playing its own intended identity (Warrior's optimal line
  finishes in round 3 about 88% of the time; a steep decay curve makes Warrior's *correct*
  play feel underrewarded, not just Wizard's incorrect play feel overrewarded). A targeted,
  single-class fix (HP, in Wizard's case) that doesn't touch every other class's incentive
  structure is strictly preferable to a global mechanic that happens to also solve one
  specific cross-class gap.

## HP as a balance lever — when it's right, when it's cheating

Tested directly: mixed-roster wins-per-trip scale almost perfectly linearly with a class's
max HP, roughly **+0.25 wins per +1 HP**, with no diminishing returns detected across a
wide swept range (10-22). This held independently for both Wizard and Cleric sweeps. Two
important caveats before reusing that constant on a new class: it was measured against the
current 8-mob roster and the current card kits of the *other* two classes (since mixed
roster performance depends on the whole roster, not just the one class being swept) — a
new class, new mob, or a rebalanced existing class should get its own fresh sweep, not
assume 0.25 transfers.

The real judgment call isn't "does raising HP work" (it almost always will, since it's a
blunt multiplier on everything) — it's **whether HP is actually the diagnosed problem.**
Before touching a class's HP constant, run the variance check and the per-round economy
decomposition first. If a class's kit already produces intended variance and a competitive
or even best-in-class per-round economy, and it's still underperforming, that's real
evidence the pool itself is undersized — HP is a targeted, correct fix, not a cover-up
(this was Wizard's actual diagnosis). If a class's kit is flatly weak (narrow variance,
poor per-round economy, nothing standing out), raising HP will still make the numbers look
better, but it's masking a card-design problem instead of fixing one, and the class will
likely need the fix revisited every time its cards change anyway.

## State-dependent mechanics need their exact boundary stated, not implied

Two separate incidents, same root cause, worth naming as one pattern: **Cleric's Fiery
Fortitude max-HP buff** and **Paladin's "first vs. second Invocation" rule** were both
implemented once, confidently, based on a natural-sounding description ("+2 Max HP, 2 heal"
for the first; "only one Virtue active" for the second) — and both turned out to silently
double-count or misapply value the moment they were traced round-by-round against a real
hand. Fiery Fortitude's first implementation granted its max-HP buff as *both* a raised
ceiling *and* a separate instant current-HP grant, on top of the card's own already-separate
heal stat — reopening Cleric's previously-fixed "cannot die" equilibrium bug on Grunt and
Skirmisher, for a reason that had nothing to do with the numbers being wrong and everything to
do with the same value being counted twice. Paladin's Invocation mechanic had an equivalent
ambiguity: does the *second* Invocation played in a pull still get its own retroactive bonus,
or none at all? Both were only caught by hand-tracing a specific example round by round against
the actual formula, not by reasoning about the mechanic in the abstract, and in both cases the
person catching it was the user re-deriving the arithmetic by hand, not the diagnostic suite.

The generalizable rule: before implementing any mechanic where a card's effect depends on
prior game state (a buff that persists, a bonus that scales with something already played, a
resource that can be "spent" more than once in different ways), write out the exact boundary
condition in one plain sentence and confirm it, the same way a legal contract disambiguates an
edge case — not "it heals and raises max HP" but "does the max-HP amount itself also count as
current-HP gained, separately from the heal stat, yes or no." If the answer feels like it should
be obvious from the card text, that's exactly when it's worth stating anyway, because "obvious"
readings are exactly where two people (or a person and a model) silently diverge.

## Mob-dependent performance can be a feature, not a bug

Warrior's Guardian/Champion stance balance was, for a long stretch, chased toward a flat
50/50 split as if any deviation were an imbalance. It isn't automatically one. The final,
accepted shape — Guardian dominant against weak mobs (block matters less, so HP
preservation wins outright), Champion dominant against strong mobs (raw damage output
becomes the binding constraint) — was kept deliberately, because it adds a genuine
mob-reading dimension to the puzzle: which stance to commit to depends on *what you're
about to fight*, not just your hand. Don't reflexively flatten a mob-dependent performance
curve on a new class without first asking whether it's actually adding a decision, the way
it did here, versus genuinely failing the class against a whole tier of content.

## Single-pull parity doesn't guarantee chained-pull parity — check the actual subset in use

The 8-mob roster was tuned to near-parity across all four classes (`full_report()`'s
"Mixed roster" trip-chain numbers: Warrior 5.00 pulls, Wizard 4.93, Cleric 4.98, Paladin 4.80
before HP<=0, reckless play, no consumables). That's a real, trusted result — but it's an
average over all 8 mobs. Nothing checked whether parity holds on a *subset*. When the macro
sim's Standard tier (5 of the 8 mobs, chosen for a different reason — difficulty banding, see
`mob_difficulty_ranking()`) was checked the same way restricted to just those 5, a real gap
appeared: Cleric survived ~17-19% more pulls than Warrior/Wizard, invisible in the full-roster
number because the 4 untouched Spike-tier mobs were doing enough of the averaging-out work to
hide it. **Any time a mob subset is used for something (a tier, a zone, a quest pool), check
that subset's own chained parity directly — don't assume the full roster's tuning transfers.**

The mechanism, once found: single-pull cost (`mob_difficulty_ranking()`, cost as % of max HP
from full HP, one isolated fight) doesn't see compounding. A class with any per-pull healing
gets to partially top off HP *every* fight in a chain, even fights that don't start at full
HP — invisible in a full-HP snapshot, real once several pulls run back to back with no
recovery between them (exactly what both the reckless trip-chain diagnostic and the real
macro-loop policy do). Cleric's roster-wide single-pull cost is actually the *highest* of the
four classes (22.0% avg on the Standard tier) — it isn't that Cleric's mobs are individually
cheap, it's that *any* mob cheap enough lets a flat heal compound over a chain in a way flat
mitigation (Warrior's block) or burst (Wizard) can't replicate.

## The stat gauntlet — brute-force mob-shape search, and how to actually use its output

Built to answer "what mob shape would specifically counteract this" without hand-guessing.
Sweep every (dmg, block) combination for all 3 rounds jointly, plus every mob HP in a target
range, computing exact single-pull cost/win-rate/round-1-kill-rate per class for each
combination (`sim/stat_gauntlet.py`, a data-generator script kept in the repo but not imported
by macro_sim.py — regenerate its CSV output as needed rather than treat it as sacred). At 0-5
per parameter (matching the real roster's actual range — going
to 0-10 explores territory nothing has ever used) and block capped at 0-2 (**the real roster
has never gone above block=2 anywhere** — the first, unconstrained version of this sweep
found "great" candidates at block=4-5, which turned out to be a distinct trap, see below), a
full 3-round joint sweep across 9 HP values is ~52k rows and takes about 2.5 minutes — cheap
enough to regenerate per question rather than treat as sacred. Query the CSV afterward
(`csv.DictReader`, no need to hold it all in memory) rather than trying to read raw rows.

Two traps found and fixed while building this, both worth knowing before trusting any output:

- **Degenerate "perfect balance."** The naive closest-single-pull-cost-spread query returns
  patterns with round-1 damage of 0 — technically perfectly equal, because a mob that deals
  no damage costs everyone exactly nothing. Filter out any candidate whose *minimum* cost
  across classes is near 0, not just wins==0%.
- **High block manufactures fake wins, not real balance.** Extreme block (4-5) can produce
  a mob that looks great on paper (low, matched cost; high win rate) purely because low mob
  HP lets it die to a lucky hand before its brutal later rounds ever matter (a "one-shot").
  Raising HP to close that loophole doesn't find a sweet spot — it reveals the *real* problem:
  heavy block caps the total damage any hand can deal in 3 rounds, so past a certain HP the
  mob becomes literally unkillable for everyone, no hand-luck involved. The fix isn't
  "find the right HP," it's constrain the search itself: cap block, and track/filter
  round-1-kill-rate as a hard 0% requirement, not a courtesy check after the fact.

**The "one favorite mob per class" instinct doesn't work, and testing confirmed why, not just
asserted it.** The natural next step after finding Footman (Warrior) and Ambusher (Wizard)
already existed was to go looking for one matched mob each for Cleric and Paladin too,
targeting the same discount magnitude (~10 percentage points below each class's own average).
It failed structurally: Wizard's Ice Barricade (a single 10-block card) can manufacture a much
bigger single-mob discount (up to 28pt) than any other class's best tool can reach (~9-10pt
ceiling for Warrior/Cleric/Paladin) — the four classes' *maximum achievable* favorability
isn't the same size, so forcing matched magnitudes either fails outright or requires
wildly different difficulty levels per "favorite" mob (one hand-picked Warrior-favored
candidate came out at 40-53% cost, Elite/Champion-tier, just to hit the target discount
while staying one-shot-proof). Assembling one mob per class this way — even from individually
reasonable candidates — was tested directly against the chained diagnostic and came out
*worse* than the original ungrouped baseline (spread 1.62 vs. the original 0.95), because
mobs picked for single-pull "who's cheapest here" don't account for how compounding plays out
over a real chain (the same blind spot named above).

**What actually worked: random-search whole pools against the chained diagnostic directly,
not hand-assemble mobs by per-class label** (`sim/pool_search.py`, reads `stat_gauntlet.csv`
as its candidate source). Pull a shortlist of Standard-tier-appropriate
candidates from the gauntlet (reasonable cost band, 93%+ win rate, 0% one-shot risk), then
repeatedly sample random combinations of them into full pools (a fixed anchor mob + N random
picks), score each pool's *cumulative* chained result (avg pulls survived per class, no
per-mob class assignment at all), and keep whichever pool minimizes the spread across all
four classes. 400 random 5-mob pools, ~2 minutes at 300 trials/class for the search pass
(confirm the winner at 3000 trials after) found a pool with spread 0.238 (Warrior 5.31,
Wizard 5.52, Cleric 5.47, Paladin 5.29) — tighter than any hand-assembled attempt, made of
five mobs none of which is individually "for" any one class. The lesson generalizes: **when
the thing that matters is a cumulative, multi-pull property, search and score whole
combinations against that actual property — per-mob single-pull labels are a plausible-looking
proxy that doesn't reliably transfer.**

**Difficulty level (the pool's average pulls-survived) and balance (the spread across
classes) are separate knobs, confirmed empirically, not assumed.** Scaling every mob's raw
damage in the balanced 5-mob pool by 1.8x (to push the ~5.3-pull average down toward ~3, a
genuinely different target difficulty) did shift the magnitude where intended, but blew the
spread up from 0.238 to 1.376 in the process — different classes don't respond to a uniform
damage increase proportionally, so a pool balanced at one difficulty level doesn't stay
balanced when rescaled to another. Retuning the target difficulty requires a fresh pool
search at that HP/damage range, not a multiply-everything-by-X shortcut on an
already-balanced pool.

## Locked rule: never report pulls-survived without decay next to it

Demonstrated wrong, repeatedly, not just theorized. Pulls-spread and decay-spread do not
correlate — the pool search that found the *tightest* pulls-spread (0.238) wasn't even
top-3 on decay-spread when the same 10 pools were checked both ways (one pool with a
*worse* pulls-spread had less than half the decay-spread of the "best" one). A lower death
rate can mean a strategy achieved *less*, not that it played *safer* — Wizard's `food_only`
looked worse than `none` on raw death rate, right up until checking productivity showed
`food_only` was completing nearly double the quests, i.e. reaching the risky "one pull from
done" decision twice as often specifically *because* it was succeeding, not despite it. Most
decisively: comparing all four classes across three mob pools with decay numbers sitting
right next to the pulls numbers showed Wizard as the worst-or-tied-worst on decay in *every*
pool, a pattern completely invisible from pulls-spread alone, while pulls-spread was making
Cleric look like the only class worth worrying about.

Pulls-survived is cheap to compute (no quest/bag/Food/risk machinery, just raw combat), which
is exactly why it's the right tool for a fast search pass across hundreds of candidate pools.
It is not a substitute for actually checking the outcome that matters. Any claim about class
or mob-pool balance from here forward gets both numbers or it doesn't count as checked.

## Cleric and Wizard card fixes, locked against the current roster

**Cleric: Heal 4->3, Cleansing Barrier block 4->5.** Root cause was a specific mechanical
asymmetry, not a vague "healers are strong" problem: heal resolves before damage and isn't
capped by it, so healing past the incoming hit produces a real net-positive swing within a
round in a way block structurally cannot (block's best case is "no change," never a gain).
Traced to one card specifically -- "Heal" was responsible for 100% of round-level overheal
in a full hand x mob sample, Fiery Fortitude and Smite's Sacred Balance bonus never did it
once, because their smaller heal values (+2, +1) usually fall short of a typical round's
damage where Heal's flat +4 usually exceeded it. Two heal-based compensating buffs were
tried and both overshot badly (a new Sacred Balance source on Call of the Void: +9.2% over
Warrior; doubling Smite's existing Sacred Balance: +17.9%, worse than the original problem)
-- any additional healing anywhere in the kit re-triggers the same compounding mechanism.
The fix that actually worked was non-healing: a block buff on Cleansing Barrier (the one
dedicated defense card), landing at +0.9% vs. Warrior, tighter than a full round-level heal
cap would have gotten. Validated clean: equilibrium ALL CLEAR and healthy win rates across
the whole locked roster.

**Wizard: Ice Barricade made a weave_source.** Different shape of problem, found by tracing
death/flee shortfall (how much mob HP remained) against the tankiest Standard-tier mobs,
per starting HP. Two distinct failure modes: fled hands were routinely burning 2-3 of 3
rounds on Snap Freeze/Frozen Shot/Ice Barricade to survive, at a real damage cost -- most
had enough raw damage in hand to win and simply ran out of tempo. Dead hands were a
different, structural problem: Wizard has exactly one card that can fully answer a round
(Ice Barricade), and against a mob whose damage spreads across all three rounds, the *other
two* rounds' combined damage alone can exceed a low starting HP no matter which round gets
blocked -- confirmed by checking that reordering to block first just moves the death to a
later round, doesn't prevent it. The fix only targets the tempo-cost half (the structural
half isn't fixable by a card tweak, it's a starting-HP/damage-output question): arming
Weave on Ice Barricade means its zero-damage round now sets up a real bonus for whatever
payoff card follows, partially recovering the tempo. Reduced flee counts against Bruiser
(7/15 -> 5/15) and Ambusher (2/15 -> 1/15) at low HP, left death counts completely
unchanged (correctly -- those aren't tempo problems). Macro-loop effect: food_only
Nothing-tier decay 32.6% -> 28.2%, death rate 0.39 -> 0.31 per 20-trip run, landing next to
Cleric instead of standing alone as the clear worst class. Equilibrium ALL CLEAR, win rates
93.3-100% across the locked roster.

Both fixes share the same shape worth naming: find the specific mechanism (not just the
symptom), test whether a small change actually closes the mechanism or just masks it, and
validate against the real, currently-locked roster before calling it done.

## Numeric tuning playbook — what moves which number, and by how much

Extracted from the Rogue and Ranger builds, where the same handful of questions kept coming
up in the same shape. Read this before hand-guessing which lever to pull on a new class;
every claim here was measured, not assumed, and `tuning_report()` (see the tool inventory
above) is what to actually run to check any of it on a new kit.

**The five numbers that matter, and what each one actually is:**
- **Damage floor/ceiling** (`damage_distribution`) — best/worst single-pull raw damage
  output, exact enumeration across all 15 hands. Full distribution + mean/stdev/range, not
  just the two endpoints — see "single-pull parity" section above for why the shape matters.
- **Win rate per mob** (`win_rate`) — single-pull, full starting HP, exact.
- **Flee-preference** (`flee_preference`) — single-pull, full starting HP: does the best
  *non*-winning line preserve more HP than the best *winning* line, for hands where a win is
  achievable at all. A relative comparison between two lines for the *same* hand — not
  affected by anything that shifts both lines by the same amount.
- **Pulls-survived / wins-per-trip** (`run_trip_<class>`, chained) — Monte Carlo, HP carries
  forward pull-to-pull with no recovery, random mob and hand each pull, "always take the
  win" policy (never voluntarily flees — see that section above for why this is correct
  under the current reward scheme).
- **Wins/pull** (= wins-per-trip ÷ pulls-survived) — of the pulls a class actually gets, what
  fraction end in an actual kill. A genuinely different question from either chained number
  alone; see the tool-inventory entry above for the Rogue case where pulls-survived matched
  the pack while wins/pull didn't.

**HP moves the three chained numbers and is mathematically inert on flee-preference.**
Proven, not just observed: `flee_preference` compares two outcomes' *relative* HP-left for
the same hand; a uniform HP shift can't change which one comes out ahead. Confirmed
empirically on Rogue across three separate HP passes (14/15/16) that moved pulls-survived
and wins/pull every time while leaving flee-preference bit-for-bit identical, and again on
Ranger (14 vs. 15) with the same result. If flee-preference is the number you're trying to
move, HP will never do it — full stop, not "usually doesn't."

**Wins/pull is dominated by survivability, not raw damage capability — true on every class
checked, not just one.** Measured directly: for every non-win in a chained trip, re-check
whether the same hand+mob draw would have won with *unlimited* HP. If yes, the miss was
survivability-driven (ran out of HP before finishing something winnable); if no, it's
damage-driven (can't kill this mob with this hand, full stop, regardless of HP). Across all
five locked classes: survivability accounts for **84.4-94.8%** of misses, damage-
insufficiency for the rest. This is *why* HP is consistently the reliable lever for
wins/pull — it directly attacks the dominant failure mode — and why a flat damage bump is a
blunter substitute (see below).

**A flat damage bump moves everything at once and tends to overshoot.** Tested directly on
Rogue: +1 DMG on one card closed most of a pulls-survived gap, but also dragged
flee-preference back out of range in the wrong direction *and* pushed wins/pull over the top
of its own range — undoing two already-fixed numbers to fix a third. Damage changes kill
speed, mitigation-relative-to-offense, and floor/ceiling all simultaneously; HP only touches
the chained-survival numbers. Prefer HP when the goal is narrowly "move pulls-survived/
wins-per-pull without disturbing anything else."

**When HP is off the table (a real design constraint, not just a preference) and one chained
number still needs to move, trim the least-entangled offense-only card, not a defensive
one.** Worked cleanly on Ranger: with `RANGER_HP` fixed at 15 for identity reasons (see the
Ranger section below), wins/pull needed to come down without disturbing pulls-survived/
wins-per-trip, which were already correctly positioned. Trimming the one purely-offensive
card with no block/evasion/persistent-effect attached (Sure Shot, 5→4) landed all three
chained numbers inside the pack range at once, because it made fights close out slightly
less reliably without touching any of the already-calibrated defensive tools. Trimming a
card that also carries defense instead (as tried earlier in the same session, cutting a
persistent Block value) moves pulls-survived *and* wins/pull together, which is the right
tool when both need to move the same direction, and the wrong one when they don't.

**Flee-preference's lever is the balance between kill-committed lines and hold-back-only
lines, not any single number.** It reads as "how often does the best non-winning line beat
the best winning line" — so anything that makes a *committed, kill-securing* line cheaper in
HP terms (a killing-blow rider, a defensive tool that applies *during* the kill round) pushes
it **down**; anything that gives a strong *standalone* defensive option that doesn't require
chasing the kill (a pure 0-DMG/high-Block card) pushes it **up**. Diagnosed directly on
Ranger: a pure-defense card (Beast's Challenge, 0 DMG/5 Block) was in 8 of that mob's 10
flee-preferred hold-back lines, while the two purely-offensive cards (Sure Shot, the class's
finisher) appeared in *zero* of them — the split is usually this clean once you look at
which cards actually populate the hold-back lines vs. the winning ones (dig in with a script
like the one used there: for every hand where flee beats winning, print both lines and tally
card frequency in each).

**Low flee-preference isn't automatically a problem — check whether it's bundled with an
overall power problem or standing alone.** Rogue's early overtuned drafts had near-zero
flee-preference *and* were 2x the pack on every other metric — one symptom of a shared cause.
Ranger's final build has flee-preference sitting a bit under the pack's floor while every
other number is in range — a texture signal (the class rarely presents a genuine hold-back
dilemma), not a power imbalance. `CLASS_BALANCE_GUIDE.md`'s own locked design conclusion
(flee is worth ~nothing under the real reward scheme) means it doesn't change outcomes
either way — treat it as informational unless it's moving in lockstep with everything else.

**Small-sample hidden-domination flags can be coincidence, not structure — check the overlap
count before trusting one.** `pairwise_genuine_difference` flagged two Ranger cards as tied
100% of the time on only 2 overlap cases early in tuning; it resolved on its own as other
values changed and never recurred. A later flag on the same two cards held at 13-14 overlap
cases across several iterations — that one was real: both cards ended up dealing identical
damage and granting identical evasion, and against an all-melee roster evasion already
zeroes the hit outright, so one card's extra point of Block can never actually matter.

This observation turned out to generalize past a "check it by hand when something looks
off" habit — auditing every already-locked class the same way found several "clean" pairs
resting on just 2-3 real observations (Warrior's Vanguard Shield/Vanguard Blade among them,
a pair *deliberately designed* to differ). The tool itself has since been redesigned to
report evidence, not just a verdict — see the "Ranger, locked" section's writeup and
`pairwise_genuine_difference`'s docstring for the full fix (`MIN_CONFIDENT_SAMPLE`,
`flagged`/`flagged-thin`/`clean`/`clean-thin`). Don't eyeball the overlap count from
`full_diagnostic`'s raw print anymore — the tool now does the confidence check itself, and
any pair still printed with a `-thin` verdict needs the same direct, out-of-aggregate
confirmation described there before trusting either a flag or a clean pass.

**Ambiguous card text needs two concrete readings spelled out, not a guess — ask.** A
stacking-bonus curve ("+1 then also +3") and a replacement curve ("+1 or +3") produce
opposite dominance relationships between two cards that were otherwise supposed to be a real
choice. Same for "played before" (does it mean the immediately preceding round only, or any
earlier round this pull) — different cards in the same Ranger kit turned out to mean
different things by design (one checked only the previous round, the other checked the whole
pull so far), and guessing either one wrong would have meant building and testing the wrong
mechanic. Costs one message to ask; costs a full tuning pass to discover after the fact.

## Locking a class in — the checklist, once tuning is actually done

1. Wire the class into every shared lookup table in `condensed_trip.py`: `CLASSES`,
   `MOBS` (or just confirm `register_class_for_testing` already did this correctly),
   `HAS_STANCE_BY_LABEL`, `CARD_SOURCE_BY_LABEL`, `HP_ATTR_BY_LABEL`, `MOB_KEY_BY_LABEL`,
   `WIN_RATE_FNS`. Add a `run_trip_<class>` function matching the existing pattern.
2. Update the class's own module docstring with the final kit, the mechanic reasoning, and
   the validated numbers at lock-in (see `condensed_rogue.py` for the template).
3. Add a "`<Class>`, locked" section to this file — mechanic summary, the real findings that
   came out of tuning it (not just the final numbers), validated numbers at lock-in.
4. **Run `condensed_trip.py`'s `defense_floor_sweep`** and confirm the class holds a clean 0%
   lethal-hand-fraction down to at least 33% HP against every mob, matching every other locked
   class — this is what Rogue and Ranger both skipped, and both turned out to have a real gap
   (see "Rogue and Ranger's macro-loop risk outlier," below). If the class doesn't clear this,
   that's a real finding to fix or consciously accept before lock-in, not something to notice
   later via a confusing macro-loop number.
5. **Wire the class into `macro_sim.py`'s `CARD_SOURCE`/`HP_ATTR`/`HAS_STANCE`** — Rogue,
   Ranger, and Runecaster were all missing from this for an entire class's worth of built
   history before it was caught. Confirm with a quick `run_one_trip` sanity call, not just that
   the import succeeds.
6. Propose (don't silently edit — SOTG requires explicit permission) adding the class to
   `SOTG.md`'s class roster table.
7. Update the task list: mark the class-build task's description to reflect what's done and
   what classes remain.

## Rogue, locked -- fifth class, and a different kind of build than the first four

Warrior/Wizard/Cleric/Paladin were each built AI-first (a solo drafting pass, checked and
iterated with the user afterward). Rogue was built the other way around: the user designed
every card and mechanic directly, iteration by iteration, with the AI running the diagnostic
suite and reporting results after each change -- a deliberate process change, not a style
preference. The first attempt at Rogue was AI-solo (cut/reframe decisions, a new mechanic,
an HP guess, all decided and wired into shared code in one uninterrupted pass) and had to be
fully reverted after the user's reaction made clear that wasn't collaboration, just execution
with extra steps. See `DECK_CONDENSING_GUIDE.md`'s checkpoint-discipline section for the full
incident -- it's now a standing rule for this project, not specific to Rogue.

**The mechanic**, entirely user-designed: Cutthroat and Envenom are finishers scaling off how
many STRIKE-tagged cards were played since the last finisher (0/1/2 strikes reachable in a
3-round pull), resetting on use -- closer to AGGRO's real "spend all CP" text than the AI's
first-draft CP-counter had been. Their curves deliberately cross over (Cutthroat 2/3/6,
Envenom 3/4/5) rather than one dominating the other. A killing-blow rider (Warrior's Execute
pattern) sits on Cutthroat only, a flavor call kept even after the numbers showed the
alternative placement tested closer to the rest of the roster -- the gap it reopened was
closed with a different, deliberately separate lever (HP, then a Block buff) rather than by
re-litigating the flavor choice.

**What the iteration actually found, worth generalizing:**
- **A hidden-domination flag isn't always real domination.** An early version's diagnostic
  flagged two cards as tied 100% of the time whenever both were drawn -- but on only 2
  overlap cases total, which turned out to be small-sample coincidence, not structural
  dominance (resolved on its own once other values changed). Check the sample size behind a
  flag before treating it as a finding.
- **Ambiguous card text needs to be pinned down as two concrete readings, not guessed.** A
  stacking-bonus curve ("+1 then also +3") and a replacement curve ("+1 or +3") produce
  opposite dominance relationships between the two finishers -- asking directly, with both
  readings spelled out, took one message and avoided building the wrong one.
- **HP and flee-preference are provably unrelated**, not just empirically uncorrelated: `flee_preference()` compares two outcomes' relative HP-left, and a uniform HP shift can't
  change which one comes out ahead. Confirmed by three separate HP passes (14/15/16) that
  moved pulls-survived and wins/pull while leaving flee-preference bit-for-bit identical
  every time. A card-level change (Block on Dodge/Backstab) was what actually moved it.
- **A flat damage bump is a blunter lever than it looks.** Tested directly: +1 DMG on one
  card closed most of a pulls-survived gap, but also dragged flee-preference back out of
  range and pushed wins/pull over the top of it -- undoing two fixes to make a third one.
  HP closed the same gap without the collateral damage, because (see the wins/pull section
  below) survivability dominates the failure mode HP targets, at a rate a raw damage
  card can't cleanly isolate.
- **"Wins/pull" decomposes cleanly into a damage-capability question and a survivability
  question**, and it's worth checking which one is actually driving a number before reaching
  for a lever. Instrumented directly: for every non-win in a chained trip, re-check whether
  the same hand+mob would have won with unlimited HP. If yes, the miss was
  survivability-driven (ran out of HP before finishing something winnable); if no, it's
  damage-driven (can't kill this mob with this hand, full stop, regardless of HP). Across all
  five classes, survivability accounts for 84.4-94.8% of misses and damage-insufficiency for
  the rest -- true everywhere, not a Rogue-specific finding, and the reason HP is
  consistently the higher-leverage dial for this metric across the whole roster.

**Locked, validated at 30,000-trial chained comparison against the other four classes**:
`ROGUE_HP = 16`. Pulls-survived 5.254 (pack: 5.266-5.767 -- tied at the floor). Flee-preference
21.3% (pack: 20.0-38.7%). Wins/pull 76.78% (pack: 72.96-75.80% -- the one number that didn't
fully close, about 1 point over). Wins/trip 4.034 (pack: 3.863-4.304 -- dead center, confirms
the wins/pull overshoot isn't a real outlier once combined with pulls-survived, since
wins/trip = pulls-survived x wins/pull exactly). Damage floor/ceiling 9/15, win rate
93.3-100% across all 5 Standard mobs, equilibrium clean, no hidden-domination. Full kit and
reasoning in `condensed_rogue.py`'s module docstring.

(Numbers above were measured against the 5-mob Standard tier, before Scout -- see below --
was added. Re-measured against the current 6-mob roster at lock-in time: pulls 5.49, wins/
trip 4.31, wins/pull 78.5%. Still in the same relative position versus the rest of the
roster; Scout doesn't change the read on Rogue.)

## Ranger, locked -- sixth class, built entirely by the user card-by-card

Same collaborative process as Rogue's eventual build (not its first, reverted attempt) --
every card value proposed by the user directly, with the AI running `tuning_report()` after
each change and reporting the numbers. No AI-solo drafting happened at any point in this
build.

**The mechanics, both new to this codebase:** a persistent, multi-round Block effect (Beast
Bond: Wolf -- every other class's Block clears each round; this is the first exception), and
a previous-card-dependent damage payoff (Sniper/Point Blank Shot, reusing Warrior's existing
Vanguard-pair chain-bonus pattern but keyed on the `grants_range` property instead of a
specific card name).

**A design worry, raised before any numbers existed, that turned out real but not absolute:**
would Beast Bond's persistent Block be a card you'd robotically play round 1 every time it's
drawn, making that decision boring? Measured directly once built: chased in 76.0% of hands
where drawn (round 1), 18.0% round 2, 6.0% round 3 -- a real pull, not a hard lock, similar
in shape (if stronger) to Rogue's Ambush round-1 bonus (58.8%). The mechanism for the round-2+
cases: against a mob with a heavy round-1 hit and no block on Beast Bond itself, tanking that
hit with a dedicated block card first and delaying Beast Bond one round can genuinely beat
taking the bonus immediately -- a real mob-reading decision, not noise.

**Numeric tuning, the actual sequence:** the first working draft (Beast's Challenge: flat 0
DMG / 5 Block) pushed single-pull win rate to 100% on every mob -- no hand could lose,
regardless of play. Fixed by making Beast's Challenge's damage conditional on Beast Bond
having been played first (5 DMG if so, 2 otherwise) instead of flat block, which restored a
real floor below the toughest mob's HP. That fix alone didn't touch the chained numbers,
which were still roughly double the rest of the roster (pulls-survived ~13, vs. everyone
else's ~5.3) -- diagnosed directly as Beast Bond's persistent Block compounding across a
chain, the same shape Cleric's early healing overshoot took earlier in the project. Halving
its per-round value (2 -> 1 Block) cut that gap roughly in half by itself. The remaining gap
was closed two different ways, tested and compared explicitly rather than picked blind:
dropping `RANGER_HP` 15 -> 14 closed it completely but was explicitly rejected by design
judgment (Ranger reads as Mail-armor tier in AGGRO's own design, distinct from the Cloth-tier
classes already sitting at 14 -- a real identity signal worth more than a fully-closed
integer gap); trimming Sure Shot's flat damage 5 -> 4 instead closed the same gap without
touching HP, landing all three chained metrics in-range simultaneously. This is the
"least-entangled offense-only card" lever from the tuning playbook above, applied for real.

**Locked, validated at 5000-trial chained comparison against the rest of the roster** (at
lock-in time, against the 6-mob Standard tier including Scout, see below): `RANGER_HP = 15`.
Pulls-survived 5.11 (pack: 5.11-5.63 -- tied at the floor). Wins/trip 3.83 (pack: 3.83-4.33 --
also tied at the floor). Wins/pull 75.0% (pack: 73.9-78.5%). Damage floor/ceiling 8/14, win
rate 93.3-100% across all 6 Standard mobs, equilibrium clean. Flee-preference 13.3-16.0%
across the tuning session's various roster states, sitting a bit under the rest of the
roster's range -- a texture signal (see the tuning playbook's flee-preference section above),
not chased further once every other metric landed in range. Full kit, mechanic reasoning, and
the complete tuning sequence in `condensed_ranger.py`'s module docstring.

One hidden-domination flag remains on the diagnostic: Withdrawing Hip Shot vs. Crippling
Shot, both 2 DMG and both grant Range. This one is real, strong evidence, not a fluke --
`[flagged]`, 14 real (non-vacuous) observed comparisons, all tied, zero genuine differences.
Nearly all 14 come from the other 5 (melee) mobs, where the cards truly are identical --
`grants_range` already zeroes melee damage outright, so Crippling Shot's extra +1 Block can
never do anything there. Confirmed separately, by forcing the swap directly outside the
diagnostic, that the two cards *do* genuinely differ against Scout specifically (the 1-point
Block difference shows up correctly the instant the differing card is actually played) --
but that real difference produced zero valid observations in the natural 15-hand dataset
for that one mob (every hand either played both cards together, or landed the differing card
in a round the fight never reached). Both things are true at once and aren't in tension: the
pair is legitimately near-identical across the large majority of the roster (strong, correct
evidence), and it has one confirmed real exception that this particular check's small,
fixed sample just never happened to catch for that one mob. A future card-pool expansion
(more Standard-tier ranged mobs, more hand-count) would very likely surface it on its own.

**This investigation started because the user pushed back hard on how the original version
of this check reported results, and that pushback was correct.** The pre-redesign version
printed a bare "flagged" or "not flagged" per pair, with no indication of how many real
observations backed the verdict. Auditing every already-locked class against this question
("how much evidence is actually behind each 'clean' verdict?") found the problem wasn't
Ranger-specific: Warrior's Vanguard Shield vs. Vanguard Blade -- a pair *deliberately
designed* to differ, with separate order-sensitive chain bonuses -- had its "not flagged,
these genuinely differ" verdict resting on just **3** real observations out of the whole
roster. Wizard, Cleric, Paladin, and Rogue each had at least one pair in the same 2-3-real-
observation range. None of these were actually wrong (every one had genuine > 0), but the
*method* that produced "not flagged" for them was, in each case, barely more reliable than
the method that produced Ranger's misleading-looking flag -- getting the right answer off
2-3 data points is luck, not confidence, and the tool gave no way to tell the difference
between a verdict built on 3 observations and one built on 20.

**Fixed by redesigning the check itself, not by re-explaining the Ranger result.**
`pairwise_genuine_difference` now returns `(genuine, tied, vacuous, verdict)` per pair
instead of a bare flagged/not-flagged, with `verdict` one of `flagged` / `flagged-thin` /
`clean` / `clean-thin`, gated on `MIN_CONFIDENT_SAMPLE = 5` real (non-vacuous) observations.
`full_diagnostic()` now only prints pairs that aren't a confident `clean` -- so a real,
well-evidenced flag (Ranger's, 14 observations) and a technically-clean-but-thin verdict
(Warrior's, 3 observations) both surface for a human to look at, instead of one being loudly
flagged and the other silently trusted. **Locked rule going forward: never read a single
flagged/not-flagged verdict from this check as settled without also looking at how many real
observations back it** -- a pair sitting below `MIN_CONFIDENT_SAMPLE` (flagged-thin or
clean-thin) needs the same direct, out-of-aggregate confirmation used to resolve the Ranger
case (force the differing card into an actually-played round and check the outcome by hand)
before treating either verdict as fact.

## Sixth Standard-tier mob: Scout (ranged), and the compensating Wizard fix

Two classes (Wizard, Ranger) have a `grants_range`-style evasion mechanic (evades a melee
mob's attack entirely) that was permanently inert with an all-melee Standard tier -- there
was no mob it didn't work against, so the mechanic never actually mattered as a decision, and
one Ranger card pair (Withdrawing Hip Shot / Crippling Shot) was genuinely dead-tied as a
direct result (see the Ranger section above). Fixing this needed a real ranged mob added to
the roster, not a hypothetical.

**The actual question worth naming explicitly, because getting it wrong the first time
produced a wrong recommendation:** "least disruptive" was initially read as "changes
Wizard/Ranger's numbers the least, relative to how much everyone else gains" -- i.e.
maximizing how differentiated the ranged tag reads. That's the wrong question. **The right
one is total footprint across the whole roster** -- how much does adding this mob move
*everyone's* numbers, not just how unevenly it splits between the two affected classes. Five
candidate shapes were compared on both readings and the ranking flipped completely: the
candidate that looked "best" under the first framing (front-loaded, fading damage --
maximally differentiated the two range-aware classes from the rest) had one of the *largest*
total footprints on the whole roster; the candidate that actually minimized total disruption
(`[(2,0),(3,0),(4,0)]`, HP 8 -- a mild, roster-typical escalation, not deliberately
weak-and-forgettable) had less than half the average per-class disturbance of anything else
tested. The mechanism: the weaker candidates were so far below the existing roster's
difficulty that adding them acted like a free win for every class, inflating everyone's
chained numbers substantially -- that's disruption too, just in the generous direction, and
it dwarfed the actual ranged-tag effect being measured. **Locked methodology: when adding
content to an already-balanced pool, measure total footprint across every affected class
first, not just the differential on the classes the new content is "for."**

**Deliberately no Block on Scout.** Considered and rejected: block represents durability
against being hit, a melee-tank trait; a ranged attacker's identity is staying out of the
fight entirely, not tanking it. Giving Scout block would also have stacked a second,
unrelated advantage on top of the one it already has (its evasion-nullifying effect on two
classes) for no real reason -- the same "don't stack uncertainty/advantage on itself" instinct
that shaped the zone-node loot-sourcing decision in `OPEN_QUESTIONS.md`.

**Wizard's small, deliberately narrow compensating fix, precisely because `WIZARD_HP` was
explicitly ruled out as a lever here** (already a locked, previously-tuned number; the user
was clear it wasn't up for revision just because a new mob shifted its numbers slightly):
Snap Freeze (grants Range, 1 DMG, Weave source) gained a flat `block=1`. This is provably
silent against every melee mob in the roster -- `grants_range` already reduces melee damage
to zero, so added Block underneath it can never do anything there, confirmed by re-running
the full 5-mob-baseline diagnostic bit-for-bit identical before and after. It only ever
activates against Scout, where `grants_range` currently does nothing at all. Recovers about
23% of Wizard's pulls-survived loss and 57% of its wins/pull loss from Scout's addition --
partial, deliberately, since the loss itself was small (~0.5 pulls, ~0.7 percentage points).
This is the generalizable pattern for "a new mob costs one class something specific and HP
is off the table": find the exact mechanic the new content defeats, and patch *that*
mechanic narrowly enough that it's structurally inert everywhere else, rather than reaching
for a blanket buff.

**Final shape, locked:** `Scout: ([(2,0), (3,0), (4,0)], 8)`, `mob_type="ranged"`, added to
`MOB_TIERS["standard"]` at the same uniform weight as every other Standard-tier mob (no
special-case weighting -- deliberately, per the existing class-agnostic-roster discipline
extended to "don't special-case a mob either"). Full 6-class chained comparison at lock-in:

| Class | Pulls survived | Wins/trip | Wins/pull |
|---|---|---|---|
| Warrior | 5.59 | 4.14 | 73.9% |
| Wizard | 5.34 | 3.97 | 74.4% |
| Cleric | 5.63 | 4.33 | 77.0% |
| Paladin | 5.57 | 4.28 | 76.9% |
| Rogue | 5.49 | 4.31 | 78.5% |
| Ranger | 5.11 | 3.83 | 75.0% |

All six classes cluster within a roughly 0.5-pull / 4.6-percentage-point band -- no outliers
introduced by the addition. This table is the new locked baseline for any future roster or
mob-pool comparison; the "5-mob" numbers reported in the Rogue section above and elsewhere
predate Scout and are historical, not current.

**Locked rule, going forward: every mob tier must contain at least one ranged mob.** Standard
went all-melee for most of this project before Scout, and it took until Ranger's build (the
second class with a `grants_range` mechanic) for that gap to actually get noticed and fixed.
Whoever derives Spike -- or any future tier -- needs a ranged candidate from the start, not
discovered as a gap again later. Also written as a code comment directly above
`MOB_TIERS` in `condensed_trip.py`.

## Elite trio, derived -- solo single-hero baseline for the future Party Pull mechanic

Derived while designing the Loudness co-op targeting system (see `OPEN_QUESTIONS.md`'s
"Co-op multi-hero vs. one Elite" entry) -- before any party-vs-Elite math could be built, the
solo single-hero matchup needed a real answer first, since that's the baseline everything
else measures against. **Not yet wired into `condensed_trip.py`** -- these are a locked
design decision with real validated numbers, not live game content yet. Wiring them into
`MOB_TIERS`/`MOBS` should happen once the multi-hero Party Pull engine actually exists to use
them against (see the phased build plan in `OPEN_QUESTIONS.md`), not before.

**Target, as given:** a single near-max-HP hero should be able to solo an Elite, but it
shouldn't be much better than a real coinflip -- "no better than a 50/50 prospect."

**Single-mob search was tried first and abandoned -- not because the search was weak, but
because the target is structurally unreachable by a single mob.** Two full brute-force
sweeps (one scoped to HP 12-14/damage 14-18 per the original ask, one much wider at HP
9-16/damage 0-24/block 0-2, ~157K combinations each) both converged on the same result:
**every mob shape close to a genuine 50% win rate produced a 30-40 percentage-point spread
between classes**, with Cleric (and often Paladin) trailing badly and Wizard/Rogue/Ranger
comfortably ahead, regardless of how the damage was shaped (concentrated into 1-2 big hits,
spread evenly across all 3 rounds, front-loaded, back-loaded -- all tested directly, all
showed the same gap). Traced the actual mechanism by hand-tracing real optimal lines:
**classes with a full-negation tool (Warrior/Rogue's killing-blow riders, Wizard/Ranger's
`grants_range` evasion) can cancel an entire round's damage outright; Cleric and Paladin only
have partial mitigation (flat Block), which can't compete with full negation once damage per
round gets high enough to matter.** This isn't a shape-dependent artifact -- it held across
every damage distribution tested, meaning it's a property of which classes have which tools,
not of any particular mob's numbers.

**A separate, harder structural finding: mob HP above ~15-16 makes the fight literally
unwinnable for every class, regardless of the mob's own damage.** Confirmed directly --
even a monstrous 8/8/8 (24 total damage) mob at HP=20 produced a flat 0% win rate for all
six classes. Hero damage ceilings top out at 14-16 across the fixed 3-round pull structure
this game always uses (see the "What is the ceiling range of our heroes" numbers earlier in
this session); once mob HP exceeds that, no hand from any class can finish it in 3 rounds,
full stop. This sets a hard, unavoidable HP ceiling for anything meant to be solo-winnable
under the current combat rules -- a genuinely "big, tanky" Elite in the sense of far
exceeding hero damage ceilings is only achievable via the Party mechanic (combined multi-hero
damage), never solo.

**Cost% (average HP spent, win or lose) turned out to be the metric that pool-averaging
actually fixes -- win rate does not.** Tested directly, side by side: pools of 2-3 candidate
mobs optimized for tight win-rate spread plateaued at 13.3 percentage points no matter how
much the search space was widened (200K random pool combinations, both 2- and 3-mob pools,
all converging on the same floor) and came with real class-agnostic-roster costs (30-38pp
cost spread hidden underneath a superficially tighter win-rate number). The same pool-search
process aimed at cost% instead found meaningfully tighter results (down to ~10-11pp spread)
with more headroom to keep improving. The mechanism: win rate is a hard binary cliff,
quantized to multiples of 1/15 (6.67 percentage points) with only 15 possible hands per
class -- there is no way to hit exactly 50.0% by construction, and pool-averaging two
already-coarse numbers doesn't smooth the underlying cliff-like collapse near a hand's
survival threshold. Cost% is a continuous average with no such quantization floor, and
responds to pool-averaging the way pool-averaging is supposed to work. **Locked takeaway:
for any future multi-mob balance target, cost% is the more tractable metric to pool-optimize
against -- win rate looks like the more natural target but doesn't actually cooperate with
averaging the way cost does.**

**Locked rule, reconfirmed here from the Standard-tier derivation: search whole pools, not
single mobs, for any target that depends on the roster as a whole.** Directly parallels the
"one favorite mob per class doesn't work" finding from the original Standard-tier derivation
(see "The stat gauntlet" section above) -- trying to force one mob shape to be individually
fair to all six classes was asking one data point to do a job a pool does far better. Not
every mob in a pool needs to be individually fair; the pool's *average* needs to be.

**Final locked trio** (all HP=12, searched from a 2,890-candidate pool within HP 12-14/total
damage 13-18/block 0-3, optimized for cost% closest to 50 with tightest cross-class spread,
deliberately including one mob with real Block for shape variety):

| Mob | Pattern | Notes |
|---|---|---|
| Bulwark | `[(3,1), (4,0), (6,0)]` | Only one of the three with any Block (1, round 1); damage also ramps 3->4->6 |
| Berserker | `[(6,0), (6,0), (3,0)]` | Heavy up front (6/6), fades to 3 -- an early rage that burns out |
| Warlord | `[(5,0), (4,0), (5,0)]` | Consistent, sustained pressure across all 3 rounds, no big peak or valley |

Drawn uniformly at random (no special weighting, matching the class-agnostic-roster
discipline used everywhere else), aggregate per-class cost%/win% across the trio:

| Class | Cost% | Win% |
|---|---|---|
| Warrior | 44.7% | 68.9% |
| Wizard | 44.3% | 66.7% |
| Cleric | 55.7% | 55.6% |
| Paladin | 54.0% | 68.9% |
| Rogue | 48.5% | 75.6% |
| Ranger | 48.0% | 73.3% |

Cost spread 11.0pp -- the tightest found across every search this session. Cleric remains
the most expensive and Wizard the cheapest, same underlying pattern found in every single-mob
search, but compressed from a 30-40pp gap down to about 11.

**Backup trio kept in reserve** (one mob each at HP 12, 13, and 14, for visual/thematic size
variety at a modest real cost -- 14.2pp cost spread instead of 11.0pp):

| Mob | Pattern |
|---|---|
| Elite D | HP=14, `[(3,0), (4,0), (6,0)]` |
| Elite E | HP=12, `[(6,0), (6,0), (5,0)]` |
| Elite F | HP=13, `[(3,0), (5,0), (5,1)]` |

**Not yet done:** wiring either trio into `condensed_trip.py`'s `MOB_TIERS`/`MOBS`; building
the actual multi-hero Party Pull combat resolution (combined party damage vs. Elite HP,
combined party Block vs. Elite attack, Loudness-based leftover assignment); re-validating
these specific numbers once that engine exists, since everything here was derived against
the *solo* single-hero baseline only, per the phased plan in `OPEN_QUESTIONS.md`.

## Runecaster, locked -- seventh class, numbers given directly by the user

Same process as Rogue and Ranger: the user designed the kit and every card's numbers
directly, the AI verified the real AGGRO source (`cards.csv` + `StS_x_WoW_Classes_v7_4.md`,
not a summary), proposed cuts/reframes per `DECK_CONDENSING_GUIDE.md`, then ran the
diagnostic suite and reported results after each change.

**The mechanic, entirely user-designed:**
- **Chain bonus (Lightning Bolt):** 3 dmg normally, 4 if the previous round's card was
  Chain Lightning. Reuses Warrior's Vanguard Blade/Shield previous-card pattern, reframing
  AGGRO's "Lightning Bolt costs 0E this turn" (no Energy system in QUEST) into a damage
  payoff instead of a cost discount.
- **Echo (Earth Strike Rune) -- a new mechanic shape for this codebase:** deals 2 dmg + 1
  heal the round it's played, then automatically 1 more dmg + 1 more heal at the very start
  of the *next* round, before that round's own card resolves -- no card slot spent on the
  second round's payoff. Folds AGGRO's two separate Rune cards (a STRIKE-damage buff, a
  recurring Zone heal) into one, and reuses Call of the Volcano's DOT-tick shape (damage
  resolving automatically on a later round) bounded to exactly one echo round, paired with
  a heal component. Played in the pull's last round, the echo simply never fires -- no
  special-case needed, same structural boundary Rogue's Cutthroat curve already relies on.
- **Call of the Glacier:** AGGRO's SLOW rider was cut, not force-fit or reworked -- confirmed
  directly against the rules text that SLOW is a pure Zone/movement-lock keyword ("Cannot
  change Zones... Cannot be dragged") with zero functional meaning in a single-mob,
  no-movement combat model. Repurposed as a positioning card instead (`grants_range=True`,
  reuses Wizard/Ranger's existing evasion mechanic) rather than inventing something new.
- **STRIKE tag dropped entirely** from Windstrike -- confirmed with the user that nothing in
  this kit reads it, so it isn't encoded as a flag at all, not even a vestigial no-op one.
- **Windstep cut outright** -- its only distinguishing clause was Zone movement/disengage,
  with no QUEST equivalent; a bare 2-Block-only card once stripped wasn't worth a slot.

**Tuning path.** First numbers pass (Tidal Ward heal 3/block 3, Earth Strike Rune 2 dmg + 2
heal this round) broke equilibrium on Grunt and Bruiser -- the exact "cannot die" failure
mode Cleric hit originally -- and blew every chained-trip metric far outside the roster's
range (9.14 pulls vs. the pack's 5.12-5.64). Root cause: two separate heal sources plus the
echo's free second round of value added up to more sustain than any other class carries.
Fix: Tidal Ward cut to heal 2/block 2, Earth Strike Rune's first-round heal cut from 2 to 1
(echo's 1/1 untouched) -- closed both problems in one pass.

**What the process found, worth generalizing:**
- **A `clean-thin` hidden-domination flag can mean "rarely compete," not "thin evidence of a
  real problem."** Chain Lightning vs. Call of the Glacier flagged with only 2 real
  observations. Direct manual dig (all 36 hand/mob combos, not just the ones the strict
  filter counted): 34 of 36 play both cards *together* -- they're complementary, not
  fighting for the same slot, so the pairwise-swap check structurally has little to say
  about them. The 2 forced comparisons that did occur were both against Scout, the one
  ranged Standard mob, where `grants_range` is worthless by construction -- expected, not
  domination.
- **A brand-new mechanic shape is worth a manual hand-trace, not just trusting the aggregate
  diagnostic.** The Echo (Earth Strike Rune -> Lightning Bolt -> Windstrike vs. Grunt) was
  traced by hand before running it, confirming the automatic next-round tick resolves
  correctly -- including a subtle detail (the echo's damage was fully absorbed by Grunt's
  round-2 Block, while its heal landed anyway, since heals aren't blocked).
- **Waste Index has no pack-range check printed by `tuning_report()` the way pulls/wins/
  wins-per-pull does** -- worth pulling manually before treating a class as fully validated.
  Runecaster's 1.98 dmg overkill / 0.27 HP overheal both sit inside the existing roster's
  range (1.10-2.85 dmg, 0.00-0.24 HP), with the overheal landing right next to Cleric's, the
  only other real healer.

**Locked, validated:** `RUNECASTER_HP = 16` (Mail-tier, user-set -- not swept against
neighboring values the way Ranger's HP got negotiated across three passes; it landed in
range on the first try and was kept rather than re-litigated). Damage floor/ceiling 9/15
(matches Rogue's exact numbers). Equilibrium ALL CLEAR across all 6 Standard mobs. Chained
trip: 5.43 pulls / 4.14 wins/trip / 76.2% wins/pull, all three inside the pack's range
(5.12-5.64 / 3.83-4.34 / 73.9-78.4%). Elite trio (solo baseline): 50.6% cost / 64.4% win
aggregate, inside the locked 6-class spread (44.3-55.7% cost, 55.6-75.6% win), no single
Elite an outlier (Bulwark 42.9%/60.0%, Berserker 56.2%/66.7%, Warlord 52.5%/66.7%).

## Druid, locked -- eighth class, numbers given directly by the user

Same process as Rogue, Ranger, and Runecaster: the user designed the kit and every card's
numbers directly, iterating through the diagnostic suite after each change. Two lines, six
cards: Shapeshift: Grizzly/Maul/Swipe (Shapeshift), Solar Flare/Moonbeam/Nature's Wildguard
(Eclipse) -- see `condensed_druid.py`'s module docstring for the full mechanic writeup, kept
there rather than duplicated here per this file's own routing convention.

**Tuning path, unusually long for this class -- the central problem was making the two lines
a genuine choice, not a numbers pass.** The first diagnostic surfaced two separate issues: (1)
a real Bruiser gap (3 losing hands, all capped at exactly 9 damage against Bruiser's 10 HP,
all sharing Grizzly+Maul+Wildguard), and (2) Shapeshift: Grizzly played in 100% of hands that
drew it -- not a preference, a strict auto-include, meaning the kit's second line never
actually got chosen over the first. Fixing (1) first (giving Grizzly damage) made (2) worse,
not better, since it raised Grizzly's floor further above Eclipse's. Multiple single-card
levers were tried and rejected before landing on the fix -- see `condensed_druid.py`'s
docstring for the two generalizable findings (a Grizzly-blind Eclipse buff can't create a
decision it isn't structurally positioned to win; a card that appears on both sides of a
comparison can't tip it, it just moves the whole kit's power level). Final fix: Shapeshift:
Grizzly's own DMG (3->2) and Block (4->3) both cut by 1 -- closing the win-rate gap and the
low-HP defense-floor gap on two separate, independently-verified levers -- plus a structural
rule making the two lines mechanically exclusive (Grizzly cancels the Eclipse-stacking bonus
for any Eclipse card played after it), which moved Grizzly's play rate from 100% to 98.3%
(59/60) -- confirmed via direct sensitivity sweep to be the ceiling of what a card-level fix
can do here without unwinding the rest of the balance (two further attempts to push the
remaining ties fully to Eclipse, cutting Maul or buffing Moonbeam, both left the split
completely unchanged while damaging chained-trip pacing in opposite directions).

**Defense-floor break points versus the checklist's literal "0% down to 33% HP" bar (see
"Locking a class in," above): none of the 8 locked classes actually clear this literally** --
direct comparison run at lock-in showed every class breaking above 33% HP against at least one
mob (Ranger's Scout break is HP=8, 53% of its own 15 HP; Rogue's Ambusher break is HP=8, 50%
of its 16). Druid's worst breaks (Enforcer/Ambusher at HP=7, 47% of its 15) are in line with,
not worse than, the rest of the roster. The check's actual purpose (per the Rogue/Ranger
incident that created it) is catching a class that's a real *outlier* from the pack, which
this roster-wide comparison rules out -- worth restating precisely here since the checklist's
literal wording doesn't describe any class that's ever passed it.

**Locked, validated:** `DRUID_HP = 15` (explicit flavor call ruling out the source's 14,
re-tested after the fact and holding -- confirmed HP-independent metrics like win rate and
flee-preference are unaffected by which HP is chosen, only defense-floor and chained-trip
pacing needed re-validation). Win rate 93.3% (Bruiser, Enforcer) / 100% (rest) -- matches the
shape most of the rest of the roster shows, no longer a 100%-everywhere outlier. Damage
floor/ceiling 9/14, matching the pack's most common floor value exactly. Chained trip
(30,000-trial comparison): wins/trip 4.20 and wins/pull 74.7% both inside the pack's range
(3.84-4.31 / 74.1-78.1%); pulls-survived 5.62 vs. a pack ceiling of 5.60 -- confirmed real at
10x the standard sample size, not sampling noise, but the smallest miss of any metric tested
across this whole tuning arc, left as-is. Equilibrium clean. Solar Flare/Moonbeam no longer
hidden-domination-flagged (were tied 19/19 in the first diagnostic pass; now genuinely
differentiated -- Moonbeam carries a flat Heal, Solar Flare doesn't).

**Macro-loop underperformance found and partially fixed (2026-08-19).** See
`condensed_druid.py`'s module docstring for the full derivation. Druid sat dead last in the
9-class roster on Gold-at-a-fixed-XP-checkpoint despite never having the Rogue/Ranger-style
risk-gate problem -- a forced-curve test (borrowing Paladin's defense-floor curve for the
risk-gate decision while keeping Druid's own combat) showed *zero* Gold change alongside a real
death-rate spike, proving the defense-floor crack it does have (HP=7 vs. Enforcer) is real but
not the actual driver. Segment-level tracing found the real cause instead: fewer pulls per
Food-to-Food segment than Paladin (3.59 vs. 3.99) and a slightly lower win rate within them
(96.5% vs. 97.3%), both traced to a genuine, structural damage gap between Druid's two lines --
the Shapeshift line (Grizzly/Maul/Swipe) sits well below the Eclipse line (Solar Flare/Moonbeam,
flat 5 base each) in the low-damage hand clusters. **Locked: Shapeshift: Grizzly's bonus to
later Shapeshift cards changed from flat +1 DMG/+1 Block to a stacking +1 per Shapeshift card
already played this pull** (same trigger as before -- Grizzly must be played first -- only the
flat-vs-stacking shape changed). Damage floor 9->10, Gold-at-checkpoint 18.5->20.6, climbing
from last to 6th in the roster. Deliberately left the defense-floor crack itself unfixed --
traced precisely to the new Block bonus only ever applying to Shapeshift-tagged cards, while
both lethal hands' actual death round lands on an Eclipse card, which structurally can't
receive it -- a real, separate, still-open gap, not something this fix happened to also patch.

## Necromancer, locked -- ninth class, numbers given directly by the user

Same process as Rogue, Ranger, Runecaster, and Druid: the user designed the kit and every
card's numbers directly, iterating through the diagnostic suite after each change. Six
cards: Boneguard's Offering (Death Pact rider), Soul Harvest, Sowing Dread, Reap, Blight,
Death Blow -- see `condensed_necromancer.py`'s module docstring for the full source-to-kit
translation history and mechanic writeup, kept there rather than duplicated here.

**Boneguard's Offering's Death Pact rider originally drew one of your two undrawn deck
cards, genuinely random which -- the one mechanic in this codebase that ever needed real
in-pull randomness -- since reworked into a flat, deterministic "may lose 4 HP to deal 3
extra damage," at the user's explicit request. The name stays Death Pact throughout; only the
rule changed** ("Life Tap" was used as a working name mid-rework and rejected -- it's AGGRO/
WoW source terminology already spoken for elsewhere, not free for reuse here). The original
draft worked and was fully validated (see below for its numbers, kept as a record of what the
rework replaced), but the user flagged it directly as unwanted complexity on two fronts:
**knowledge debt** (the one card in the entire 9-class roster that behaved on a fundamentally
different rule than every other card -- a player has to learn a special exception just for
this one class) and **simulation debt** (the one class needing its own separate solver path:
`best_line_for_hand` had to exclude it, `draw_random_card` had to carry real randomness
inside the chained-trip Monte Carlo layer, `effective_win_rate` had to exist solely to show
what raw `win_rate` couldn't see). Both concerns were correct and the mechanic was reworked,
not just re-tuned. The theme (a Necromancer trading HP for power) carries over unchanged --
and stays genuinely unique in this roster even in its new form, since no other class has an
optional, in-the-moment, resource-for-effect trade with no setup or counter required -- only
the specific mechanism, and the architecture it required, did not survive.

**Death Pact's original draft (kept for the record, since the general lesson -- split the
tooling, don't force one function to serve both purposes -- may matter again for a future
class):** the exact solver (`best_line_for_hand`) stayed fully deterministic and simply never
considered the draw -- correct, not a workaround, since a coin-flip outcome can't be part of a
"certain" line. The draw only became real inside the chained-trip Monte Carlo simulation. Two
real corrections were made before it was ever locked: the first version required Boneguard's
Offering to be played *before* the drawn card, measured directly to make the draw provably
unable to rescue any losing hand (0/60 cases) until decoupled into a free pre-round choice;
and the first gamble policy ("draw whenever not already winning") was measured to gamble 65%
of the time at hero HP<=3 with under a 1% flip-to-win rate, fixed by only gambling when the
worse possible draw still keeps the hero alive. Its final validated numbers: win rate 100%
(Grunt/Raider/Ambusher/Scout), 86.7% raw / 93.3% draw-adjusted (Bruiser/Enforcer), chained
trip pulls=5.56/wins-per-trip=4.21/wins-per-pull=75.7%.

**The reworked Death Pact's numbers were derived, not guessed, the same way every other
class's tuning lever is checked in this project.** Implemented as a second, deterministic
virtual card variant (`BONEGUARD_OFFERING_BOOSTED`) added to `orderings()` alongside the base
card whenever Boneguard's Offering is in the hand -- the same shape Warrior's Guardian/
Champion stance duality already uses, no special-casing needed anywhere. A sweep of every
(cost, bonus) pair found the damage bonus is the only lever that affects single-pull win rate
-- cost 1-5 all produced identical results for a given bonus, since neither of the class's
known weak matchups (Bruiser, Enforcer) are HP-starved, only damage-starved at full HP.
Bonus=3 exactly reproduces 93.3%, the same number the original draft's draw-adjusted rate
already validated -- not a step up in power, a deterministic way to hit the identical target
(bonus=4 overshoots to 100%, stronger than the class was ever tuned to be). Cost was then
found from the chained-trip picture, where HP compounds across pulls: cost 1-3 push every
chained-trip metric out of the pack's range, cost=5 sits with comfortable margin under the
pack's ceiling, cost=4 lands exactly at the pack's current maximum (tied with Druid on pulls
survived) with zero margin. **Cost=4 was chosen over cost=5 deliberately, for table feel** --
the user's call, made explicitly aware of the tighter margin: "4 HP for 3 damage doesn't read
as bad a trade" the way 5-for-3 does, and the numbers didn't force one answer since both are
legitimately in-range.

**Two things checked directly before locking this in, since a flat damage-for-HP trade could
plausibly interact with round-ending or killing-blow mechanics in a way the win/loss numbers
alone wouldn't show:**
- **Does the boost let a fight end a round early (skip round 3, a bigger effect than a simple
  win/loss flip, since `simulate()` exits the instant mob HP hits 0)?** Checked exhaustively
  across every hand/mob pair that normally takes the full 3 rounds: filtering to cases where
  the boosted card is genuinely played (not just sitting unused in a round-3 slot that never
  resolves because the fight already ended -- an artifact that produced a misleading "9 tied"
  result on the first pass, caught and corrected before writing this down), the boost never
  lets a fight end early *and* come out ahead. Every genuine case is strictly worse than
  playing the full 3 rounds, at both cost=4 and cost=5, zero exceptions (0 better, 0 tied, 14
  worse each).
- **Is the boost actually meaningful, not decorative or dominant?** The solver picks it in 3
  of 60 hand/mob pairs containing Boneguard's Offering at cost=4 -- the exact case that flips
  the previously-losing Death Blow hand into a win on Bruiser/Enforcer, not something never
  worth taking or worth taking everywhere.

**Locked, validated:** `NECROMANCER_HP = 14`. Win rate 100% (Grunt, Raider, Ambusher,
Scout), 93.3% (Bruiser, Enforcer) -- one real number now, matching the draw-adjusted rate
Death Pact already validated, no raw/adjusted split needed. Chained trip: pulls~5.68,
wins/trip~4.31, wins/pull~75.9%, all three inside the pack's range (5.13-5.68 / 3.84-4.33 /
74.1-78.3%), pulls sitting at the pack's current maximum by deliberate choice (see above).
macro_sim.py compatibility confirmed via `run_one_trip`.

## Retired roster, and mobs are derived by brute force now, not hand-designed

The original 8-mob draft roster (Whelp/Grunt/Skirmisher/Ambusher/Sentinel/Brute/Elite/
Champion) plus everything added to it by hand across this project (Footman, to fix a
Warrior-specific single-pull gap; Marauder/Brawler, to fix a Cleric-specific chained-pulls
gap) has been retired and removed from `condensed_trip.py` entirely. Every one of those
additions was a real, working fix for the specific problem it targeted — the roster wasn't
*broken*, it was *hand-patched*, one discovered gap at a time, and each patch was only ever
checked against the specific diagnostic that found the gap it was patching. None of it was
ever validated as a whole *pool* against the two metrics that actually matter (chained pulls
*and* decay, see above) at the same time.

When it finally was checked that way — four classes, three candidate pools (the old
hand-patched one, and two pools found via brute-force search for different target
properties), pulls and decay both reported — the hand-patched roster came in **worse
validated** than a pool that was never designed by hand at all. The replacement (`Picket`,
`Bruiser`, `Enforcer`, `Raider`, `Scrapper`) was found by `sim/stat_gauntlet.py` (brute-force
sweep of every mob damage/block shape) feeding `sim/pool_search.py` (random-search whole
5-mob combinations against the real chained-pulls diagnostic, no per-mob class labels). It
was only ever searched for tight *pulls* spread (0.24, tightest of anything tested) — it
turned out to also have the tightest *decay* spread of the three pools compared (13 points
Nothing-tier, vs. 19 for the old roster and 43 for a pool that had been specifically
searched for decay balance and didn't hold up under full cross-checking). That it's better
on a metric it was never optimized for is the actual argument for trusting it over
hand-design: it didn't need a human to notice the gap and patch it after the fact.

**Going forward, mobs for new content (a Spike tier, later zones) get derived the same
way** — brute-force shape sweep, then pool search against the real chained diagnostics
(pulls *and* decay, both), not hand-picked numbers hoped to average out. Hand-design is what
produced a roster that took five separate incremental patches and still didn't hold up once
actually checked properly.

Old roster's shapes are preserved here for reference, not resurrected:
- Whelp `[(4,0),(3,0),(3,0)]` hp4, Grunt `[(2,1),(3,1),(3,0)]` hp7, Skirmisher
  `[(2,0),(3,1),(4,0)]` hp9, Ambusher `[(5,0),(3,1),(2,0)]` hp8 — original anchor mobs.
- Sentinel `[(3,2),(3,2),(4,1)]` hp6, Brute `[(2,1),(3,1),(5,0)]` hp10, Elite
  `[(3,0),(3,0),(5,0)]` hp12, Champion `[(3,1),(4,1),(5,0)]` hp9 — original Spike tier.
- Footman `[(3,0),(3,0),(3,0)]` hp7 — hand-added for Warrior's single-pull gap.
- Marauder `[(4,0),(4,0),(4,0)]` hp8, Brawler `[(4,0),(4,0),(3,0)]` hp8 — hand-added for
  Cleric's chained-pulls gap, dragged everyone's absolute productivity down as a side effect.

## Rogue and Ranger's macro-loop risk outlier — root-caused (2026-08-13)

Found while re-sweeping `macro_sim.py`'s locked numbers after discovering Rogue/Ranger/
Runecaster had never been wired into it (see `MACRO_LOOP_GUIDE.md`). Against the current 6-mob
roster, Rogue dies ~3.4x as often as Warrior per 20-trip chain (0.31 vs. 0.09 avg deaths/run,
`food_only`) and both Rogue and Ranger take noticeably longer to afford the 16G Bag Upgrade
(5.07/5.41 avg trips vs. the rest of the roster's 3.83-4.45) — despite both classes' *average*
chained-trip numbers already being validated in-range against the full roster at lock-in (see
their own "locked" sections above). This is a new instance of the same lesson as "single-pull
parity doesn't guarantee chained-pull parity" (above), extended to a further axis: **average
parity doesn't guarantee worst-case-floor parity, and the macro-loop risk policy runs on the
floor, not the average.**

**Methodology: sweep lethal-hand-fraction (the same value `macro_sim._pull_exceeds_risk`
computes) across every whole-number starting HP, not just chained-trip averages.**
`defense_floor_sweep(mod, has_stance, mob_key, max_hp)` is the tool — for every class, at
every integer HP from max down to 1 (never a handful of round-number checkpoints; see its own
docstring for why an earlier version of this exact check that swept only
`max_hp*(1.0, 0.5, 0.33, 0.2, 0.1)` was wrong — most of those aren't even integers, e.g. 50%
of Paladin's 17 HP is 8.5, checking a starting HP that could never occur at the table), against
every Standard mob, count what fraction of the 15 possible hands have no line (even optimal)
that avoids death this pull. Warrior, Wizard, Cleric, Paladin, and Runecaster all hold a clean
**0.0% lethal-hand-fraction against every mob down through 50% HP** — completely safe on that
metric until below a third HP. **Rogue and Ranger are the only two classes that break this
floor already at 50% HP** (Rogue: 1.1% avg, worst mob Ambusher at 6.7% / 1 of 15 hands; Ranger:
1.1% avg, worst mob Scout at 6.7% / 1 of 15 hands).

**Extended (2026-08-19): the exact HP% where each class's floor first cracks is a strong,
standalone predictor of its Gold-economy outcome, not just a defense-side curiosity.** Across
the full 9-class roster, reading the *first* HP (as % of that class's own max HP, walking down
from a clean 0.0%) where `defense_floor_sweep` turns nonzero: Paladin 35.3%, Necromancer 35.7%,
Runecaster 37.5%, Warrior 38.9%, Wizard/Cleric 42.9%, Druid 46.7%, Rogue 50.0%, Ranger 53.3% —
correlates at r=-0.924 against `avg_quests_per_trip` and r=-0.889 against Gold accumulated by a
fixed XP checkpoint (see `MACRO_LOOP_GUIDE.md`'s persona/risk-gate section for the full
derivation chain this came from). This is the strongest structural (i.e. computable before ever
running a single macro-loop trial) predictor found so far of which classes will lag on
Gold — stronger than deaths/run, decay-tier %, or raw per-round HP economy, none of which
correlate above ~0.5 against the same Gold measurement.

**Why this alone explains both symptoms.** `macro_sim.py`'s risk policy runs at
`RISK_TOLERANCE_BASE = 0.0` outside a quest-completing pull — genuinely zero risk tolerated,
not just "low." The moment a class's lethal-hand-fraction against the mob it's facing ticks
above 0%, the policy stops attempting the pull raw and forces a consumable or a retreat. Rogue
and Ranger cross that trigger a full HP-tier earlier than the rest of the roster (50% vs. 33%),
so over a real trip they (a) burn their one starting Food sooner relative to trip length, or
hit "no consumable left, trip ends" more often — slower Gold/XP, the Bag Upgrade gap — and
(b) get funneled into more actual quest-completing gambles (the only place any risk is ever
taken), each a real chance the drawn hand is one of the lethal ones — the elevated death rate.

**Two distinct root causes, not one shared mechanism -- checked precisely, not just
inferred from similar symptoms.**

**1. Rogue: a clean, generalizable "pure-offense card count" threshold.** Counted each class's
cards carrying zero *static* defensive value (no Block, no Heal, no `grants_range`): Warrior,
Wizard, Cleric, Paladin, and Runecaster each have exactly **3** such cards; Rogue and Ranger
each nominally count as **4** -- but this static per-card count is only actually the right
explanation for Rogue (see #2 below for why Ranger's count is misleading). Hand size is 4.
Below the threshold (3 of 6), it's mathematically impossible to draw a 4-card hand containing
zero defensive cards -- at least one is always included, however unlucky the draw. At the
threshold (4 of 6), there's exactly one hand -- draw all four pure-offense cards, skip both
defensive ones -- with no defense whatsoever. **Rogue vs. Ambusher at 8 HP (50%):** the one
lethal hand is `(Quick Slash, Ambush, Cutthroat, Envenom)` -- exactly Rogue's four pure-offense
cards, missing both Block-capable cards (Dodge/Backstab: 4 Block, Evasion: 10 Block). Ambusher
front-loads 4 ATK/4 ATK in its first two rounds; a hand with zero Block anywhere loses outright
by round 2 no matter how it's sequenced. **Any future class should be checked against this
exact threshold as part of its lock-in ratio check (Step 5 of `DECK_CONDENSING_GUIDE.md`),
alongside the existing damage-capable-card ratio -- this is the same kind of check on the
defensive side.**

**2. Ranger: a different mechanism -- a defensive tool voided by mob type, not a card-count
gap.** Checked directly rather than assumed: Ranger's actual lethal hand,
`(Withdrawing Hip Shot, Beast's Challenge, Sure Shot, Crippling Shot)`, does *not* match its
naive "4 pure-offense cards" list (Beast Bond: Wolf, Sniper/Point Blank Shot, Beast's
Challenge, Sure Shot) -- it actually includes two nominally-defensive cards and excludes two
offense-only ones. The static count was misleading here because Beast Bond: Wolf shows
`block=0` in its own card entry but actually grants *persistent* Block every round once
played -- a dynamic effect a single-card lookup can't see, so it's wrongly counted as
"pure offense." Ranger's real problem: against Scout (the one ranged mob), two of the drawn
cards' only defensive property is `grants_range`, which is completely worthless since Scout
can't be evaded -- leaving just Crippling Shot's flat 1 Block against Scout's 2/3/4 ATK ramp.
**The generalizable lesson here is different from Rogue's: counting "does this card have any
defensive tag" isn't sufficient on its own -- a card's defense has to be checked against every
mob *type* in the roster, not just tallied as present/absent, since evasion-based defense can
be fully neutralized by a single mob property.**

Both cases share the same shape: a narrow slice of the kit carries essentially all of the
class's real defensive capability, and the single hand (of 15) that misses that slice meets
the one mob shaped to punish exactly that gap. Neither is a bug in the per-pull solver — both
lines are genuinely optimal play, the hand is just unwinnable. This is precisely the kind of
worst-case-floor problem the hand-level kill-feasibility check (tool inventory, above) was
built to catch on the *offense* side (can a hand kill the mob at all); this is its mirror on
the *defense* side (can a hand survive the mob at all) — no diagnostic in the current toolkit
checks this directly yet, which is why it went unnoticed through both classes' original lock-in.

**Ranger: fixed (2026-08-19).** Beast Bond: Wolf's base Block 0->1 (stacking with its existing
+1/round persistent bonus, 2 total Block the round it's played) -- see `condensed_ranger.py`'s
docstring for the full derivation, including a real overcorrection caught and walked back
(+2 base initially swung Ranger past Paladin on every metric) and direct proof, via forcing
Ranger's risk-gate decisions onto Paladin's own defense-floor curve while leaving its real
combat untouched, that the gap was real danger, not policy over-caution (Gold barely moved but
deaths/run rose 8x). Landed just under Paladin on Gold/quests-per-trip rather than past it;
confirmed via distribution overlap (35.3% of Ranger runs now beat Paladin's median, up from
0.0%) that the residual gap is ordinary class variance, not a structural one. HP untouched,
same reasoning as always -- this was a specific card-composition gap, not an undersized pool.

**Rogue: fixed (2026-08-19).** See `condensed_rogue.py`'s docstring for the full derivation --
Envenom gains the killing-blow rider (matching Cutthroat's), Backstab and Dodge's Block 4->2,
ROGUE_HP 16->15. Two real overcorrections tried and walked back first (full evasion on a
renamed Ambush, then Envenom's killing-blow alone), both closing the exact worst-case hand but
sending Rogue's Gold/quests-per-trip well past Paladin's -- the final slate lands just under
Paladin instead (Gold 23.1 vs. 23.8, quests/trip 2.09 vs. 2.16, deaths/run 0.000/300 trials).
Notable: the Block and HP cuts are a *macro*-level lever correcting the aggregate overshoot
left by the killing-blow fix, not a stand-in for an undiagnosed single-pull problem -- that
problem was already found and fixed separately, so this doesn't violate the "HP is only right
when it's the diagnosed problem" rule elsewhere in this doc. Also worth naming: Rogue ends up
with strictly less raw Block and HP than it started with and still performs better, entirely
from one mechanic change -- a real identity improvement (both finishers now read as "the
target doesn't get to hit back if you finish it first"), not just a numbers fix.

Add a defense-floor check to the standard toolkit and re-audit every class, not just these
two, in case others are close
to the same cliff without yet showing it in chained-trip averages. See `DESIGN_DOC.md`'s Open
Design Questions.

## Known open items that affect every class, not just one

- **Winded/Food no longer applies — the macro loop was redesigned around HP-only attrition
  instead.** Update from the original version of this item: Winded/OOM and Durability were
  cut entirely, not just left unimplemented (see `DESIGN_DOC.md` §3). Every survivability
  number in this toolkit ("pulls before HP≤0") is no longer a proxy for a different, not-yet-
  built mechanic — it's now intended to be the actual macro-loop attrition metric directly,
  once the macro sim exists to confirm that holds up under the Bag Tetris/Food/Potion economy
  (`DESIGN_DOC.md` §5). Not yet tested end-to-end; the combat-only numbers are trustworthy on
  their own terms, but "balanced" claims about full trips (including Bag/Food/Potion choices)
  are still provisional until that sim is built.
- **The chain-bonus question has a proposed design now, not just rejected alternatives.**
  Bag Tetris answers this differently than an escalating multiplier curve: the "reward" for a
  longer chain is purely spatial (more filled loot slots), not a stacking numeric bonus. This
  avoids the problem that killed the loot-decay-by-round idea (a universal speed tax
  punishing Warrior's own round-3-grind identity, see above) — there's no global multiplier
  applied to every class's every kill, just direct, linear loot accumulation tied to
  survivability that's already measured. Whether this fully closes the original "a
  structurally shorter-chain class needs to be compensated" concern still needs the macro sim
  to check — a class that reliably chains fewer pulls will fill fewer slots per trip, and
  whether that's an acceptable identity trade-off (same category as "mob-dependent
  performance can be a feature," above) or a real gap needing its own fix is untested.
