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
