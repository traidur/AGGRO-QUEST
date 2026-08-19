# QUEST -- Leveling Guide

Process doc for the hero power curve across the 6 hero levels (3 tiers x 2 levels each, see
`OPEN_QUESTIONS.md`'s "Tier/level/zone structure" entry). Mirrors `CLASS_BALANCE_GUIDE.md`'s
role for per-class tuning and `DECK_CONDENSING_GUIDE.md`'s role for building a new class --
this is the equivalent process doc for leveling a class *up* once it already exists.

## Status

**Not yet built.** `DESIGN_DOC.md`'s Section VII ("Progression") has stated intent (XP,
Leveling, Cull, Market Row) but is explicitly marked not implemented, and that original vision
predates the now-locked "always exactly 6 unique cards" rule -- see that section for why any
real progression system has to work as a **1-for-1 card swap or in-place numeric bump**, never
additive deck growth. This guide is the methodology for whenever leveling actually gets built,
derived directly from working through the Necromancer Death Pact rework and the resulting
hero-power-curve discussion -- not yet applied to real card numbers for any class.

## The locked per-level rule

When a class moves up one hero level, four things should hold:

1. **Damage floor and ceiling both move up by about +1.** Checked with `condensed_trip.py`'s
   existing `damage_floor_ceiling` (and `damage_distribution`, for the full shape -- floor and
   ceiling alone can hide a distorted mean/stdev underneath, see that function's own
   docstring). Chosen because the whole roster is already validated to sit in a tight 14-16
   ceiling / 8-10 floor band at Level 1 -- a uniform +1 preserves that tightness rather than
   requiring re-validating relative class balance from scratch.
2. **Max HP moves up by about +1.** A uniform, passive baseline bump, not a targeted fix --
   directly tested (see "HP vs. mitigation" below) and confirmed to have wildly uneven,
   threshold-dependent effects on survivability. It's cheap and safe to apply uniformly
   precisely *because* it isn't relied on to close any specific class's gap.
3. **Survivability against the new level's appropriate mobs must not regress meaningfully**
   compared to that same class's own previous-level baseline -- not an absolute target, a
   self-comparison. "Survivability" here means **cost%** (average HP lost per pull, win or
   lose), not win rate and not raw death/no-death -- see "Which metric measures what" below for
   why the other two were tried first and either rejected or reassigned.
4. **Offensive output against the new level's appropriate mobs must not regress meaningfully**
   compared to that same class's own previous-level baseline -- the same self-comparison shape
   as #3, locked as its own equal-standing rule, not a soft "also worth tracking" footnote.
   "Offensive output" means **win rate** (`win_rate_for_level` in `leveling_validation.py`):
   every hand against the level's real, weighted mob pool, counting the fraction that actually
   kill the mob. This is the one place win rate is the *correct*, direct metric rather than a
   rejected stand-in -- it isn't measuring survivability here, it's measuring the thing it's
   actually good at measuring. Not the same promise as #3 -- a class can regress on win rate
   while staying perfectly safe on cost% (see Druid below), so this is a genuinely different
   question with its own answer, and both have to hold, not just one.

## The per-class upgrade-slate procedure

The ordered checklist for building any class's Level 2 upgrade slate, distilled from actually
building Warrior's -- every step exists because skipping it (or doing it out of order) caused a
real, caught mistake somewhere in that process. Follow in order; the order itself is load-
bearing, not just organization.

1. **Diagnose the mandatory-upgrade candidate against the unmodified Level 1 kit.** Run
   `unplayed_card_diagnostic` (`condensed_trip.py`) as-is, no swaps applied. The clearest
   candidate is most-unplayed *and* independently tied to survivability (a Block/Heal/Evasion
   card) -- if the most-unplayed card isn't obviously defensive, don't force it into the
   mandatory slot just because it topped the list; the mandatory slot's whole job is closing
   the survivability gap (rule 3), and a card that doesn't touch that mechanism won't do that
   job regardless of how often it's left unplayed.
2. **Sweep the mandatory upgrade's numbers against two boundaries, not one target.** (a) The
   damage ceiling should stay flat, or as close to flat as possible -- if a candidate value
   moves it, that value is doing rule 1's job too, which blurs a distinction this guide
   deliberately keeps separate. (b) The candidate must **not** close both cost margin and win
   margin on its own -- deliberately stop short, at the largest value still inside the ceiling
   boundary that leaves real margin unclaimed. Getting this wrong the first time (Shield Bash's
   original version fully closed the gap alone) is exactly the failure mode this step exists to
   catch -- isolate *which part* of a multi-stat change is responsible for an overshoot before
   accepting or rejecting the whole candidate, don't just discard it.
3. **Lock the mandatory upgrade, then both diagnose AND sweep/tune every purchased-upgrade
   candidate's actual numbers against a kit with *only* the mandatory upgrade applied --
   never against a kit that assumes any other optional upgrade was already bought, at either
   step.** This rule was already written down after Warrior's Dominate-vs-Heavy-Swing mistake,
   for the *diagnosis* step specifically -- and then violated again immediately, for the
   *sweeping* step, while building Cleric: Holy Fiery Fortitude was correctly swept against
   Greater-Heal-only, but Void Storm's sweep included Holy Fiery Fortitude already locked in,
   and Void Mark's sweep included *both* prior purchased upgrades already locked in. The
   symptom was invisible until a completely separate, later table (each purchased upgrade
   paired with only the mandatory one, built for an unrelated reason) showed numbers that
   flatly contradicted the sweep tables -- Void Mark's win margin read +1.6 to +1.9 across the
   contaminated sweep, but only -0.3 in true isolation, because Holy Fiery Fortitude and Void
   Storm were doing most of that work in the background the whole time. **Diagnosis and
   sweeping are the same contamination risk, not two different rules** -- every purchased-
   upgrade candidate's numbers, not just which card gets picked, must be derived against the
   mandatory-only baseline, and re-verified against it if the sweep script's swap dict ever
   drifts to include a previously-locked purchased upgrade for convenience.
4. **For each purchased-upgrade candidate, test whether its distinctive mechanic (a combo
   bonus, a conditional trigger, anything beyond flat stats) actually has a measurable effect
   before investing further sweep time in it.** Don't assume the flavorful lever is
   automatically the right one to push -- Vanguard Shield's combo bonus turned out to be
   completely dead (zero effect at every tested value), while Vanguard Blade's had a real
   effect but a plain flat stat bump still beat it on every axis, because a flat bump applies
   every time the card is played and a conditional bonus only applies when its trigger
   actually lines up. Check this directly (hold everything else fixed, sweep just that one
   lever) rather than assume a card's special mechanic is automatically its best upgrade path.
5. **Sweep the chosen direction for each candidate, stopping where cost margin and win margin
   both flip from negative to positive at the same point.** That point is usually the natural
   "smallest sufficient value" -- there's rarely a reason to push further once both margins
   clear, since win margin in particular tends to saturate immediately after (see step 7).
6. **Once every individual candidate is locked, run the full combined slate together** --
   mandatory plus every purchased upgrade at once -- and, for any class with a real mode/stance
   choice (Warrior's Guardian/Champion, or an equivalent mutually-exclusive line like Druid's
   Shapeshift/Eclipse split), check the play-rate split too. Cost%/win%/pulls are all blind to
   *which* line gets used, only to the outcome -- a slate that quietly collapses a real choice
   into "always pick X" wouldn't show up in any of the other three numbers.
7. **Don't assume margins stack additively, especially win margin -- always compute the
   combined-slate numbers directly rather than sum the individual upgrades'.** Cost margin
   happened to climb monotonically for every Warrior combination checked, but win margin did
   not (all three purchased upgrades together scored a *lower* win margin than the single
   strongest one alone) -- traced directly to a real cause, not noise: swapping multiple cards
   changes which of the 15 possible hands even exist (a hand with Dominate is a different hand
   than one with the original Sundering Blow, not a stronger version of the same hand), so
   combined-slate win rate is an average over a different hand population entirely, not the
   same population made stronger. Always re-check the actual combined number.
8. **Decide naming last, after the numbers are locked, and check for cross-references before
   renaming anything.** A change big enough to feel like a new card (Shield Bash, Dominate,
   Colossal Swing -- all meaningfully different from their base cards) earns a new name. A
   smaller, same-identity tweak (Vanguard Blade's flat damage bump) doesn't need one -- use a
   bracketed level tag on the unchanged root name instead (`[Lv 2]`). Check first whether any
   other card's rules text names the card being renamed (Vanguard Shield and Vanguard Blade
   reference each other by name in their own combo text) -- renaming one breaks the other's
   text unless the tag convention is used instead.

**What's still yours to decide at each step, on purpose:** which card becomes which named
identity (a design/flavor call, not a computable one), whether a candidate's numbers feel right
even when multiple values pass the mechanical checks (Shield Bash's X=3 vs. X=4 was deliberately
chosen below the strongest legal value, for headroom reasons no sweep could have surfaced on its
own), and the final go/no-go on locking anything. The procedure above is meant to remove the
repeated methodology mistakes from the process, not the judgment calls -- every step produces
options and evidence, not a single forced answer, and the last call stays a design decision.

## Which metric measures what -- one was reassigned, one was rejected outright

**Win rate isn't a survivability stand-in -- it measures something real, just not that.** It
answers "how often does this class actually finish the fight," not "was the hero ever in
danger." A class that survives an Elite fight by fleeing 60% of the time reads as "bad" on win
rate but may be perfectly safe -- and the two can point in *opposite* directions for the same
class (Druid: worst win-rate delta in the roster, tied-*best* cost% delta -- its low win rate
reflects fleeing early from a bad matchup rather than fighting to the bone, which is cheap in
HP even though it's a loss on the scoreboard). Using it as a stand-in for survivability would
have pointed a targeted mitigation fix at the wrong classes (Druid, not Cleric/Paladin, who
actually pay the most HP). Correctly used for what it *does* measure -- offensive output, rule
#4 above -- it's the right, direct metric: every hand against the level's real, weighted mob
pool, counting the fraction that actually kill the mob versus the fraction that don't. No
synthetic dummy needed for this one; real content answers it directly.

**Raw survival (hp_left > 0, "did they die") is rejected outright, not reassigned -- it's too
lenient to differentiate anything.** Checked directly: every one of the 9 classes hits 100%
survival against both the Level 1 and Level 2 real mob mix, at current, un-bumped power. Nobody
ever actually dies at full HP against the current roster (the Elite trio was deliberately
derived to be a real, calculable risk rather than a true trap), so this metric shows zero
signal and isn't used anywhere in this guide.

**Cost% (`100 * mean(max_hp - hp_left) / max_hp`, the same formula `class_mob_matchup_chart.py`
already uses) is what actually measures rule #3.** Continuous, not a binary cliff; captures
"how close to death did this get" directly, across every hand whether it won, lost, or fled.

## The three required checks

Single-pull risk (cost%), offensive output (win%), and multi-pull endurance (pulls survived per
trip) are three genuinely different axes, not overlapping views of the same thing -- cost% and
win% both reset to full HP every measurement and can disagree with each other (Druid), while
pulls-before-death is the one place a bigger HP pool's *cumulative* value actually shows up, and
neither of the other two can see it. All three live in `sim/leveling_validation.py`, built
specifically for this guide (existing chained-trip tools in `condensed_trip.py` draw mobs
uniformly from the 6 Standard-only `MOB_NAMES` -- implicitly a Level 1 number already, no
Elite-weighted variant existed before this).

**Level pools, matching the real locked deck composition exactly** (`OPEN_QUESTIONS.md`'s
"Zone-node mob dealing" entry): Level 1 = the 6 Standard mobs, uniform. Level 2 = the same 6
Standard mobs plus the 3 Elites (Bulwark/Berserker/Warlord), weighted 3:1 by literally
duplicating each mob's pattern in the pool the same number of times its card appears in the
real physical deck (18 Standard : 3 Elite) -- not an arbitrary weighting choice.

**Current baseline (all 9 classes, current un-bumped Level 1 stats, all three metrics, Level 1
pool vs. Level 2 pool):**

| Class | L1 cost% | L1 pulls | L1 win% | L2 cost% | L2 pulls | L2 win% | cost d | pulls d | win d |
|---|---|---|---|---|---|---|---|---|---|
| Warrior | 22.2% | 5.66 | 98.9% | 25.4% | 4.99 | 94.6% | +3.2pp | -0.66 | -4.3pp |
| Wizard | 21.0% | 5.34 | 96.7% | 24.4% | 4.98 | 92.4% | +3.3pp | -0.36 | -4.3pp |
| Cleric | 23.3% | 5.62 | 97.8% | 27.9% | 4.75 | 91.7% | +4.6pp | -0.87 | -6.0pp |
| Paladin | 21.6% | 5.53 | 97.8% | 26.2% | 4.75 | 93.7% | +4.6pp | -0.79 | -4.1pp |
| Rogue | 20.8% | 5.47 | 97.8% | 24.8% | 4.81 | 94.6% | +3.9pp | -0.66 | -3.2pp |
| Ranger | 21.6% | 5.10 | 95.6% | 25.4% | 4.60 | 92.4% | +3.8pp | -0.50 | -3.2pp |
| Runecaster | 23.3% | 5.40 | 97.8% | 27.2% | 4.74 | 93.0% | +3.9pp | -0.65 | -4.8pp |
| Druid | 26.1% | 5.64 | 97.8% | 29.3% | 4.86 | 89.5% | +3.2pp | -0.78 | -8.3pp |
| Necromancer | 22.5% | 5.68 | 97.8% | 26.1% | 5.05 | 93.0% | +3.5pp | -0.62 | -4.8pp |

**This is the baseline gap, not a verdict.** These deltas are what happens today, with *no*
level-up bump applied at all, if a Level 1 class is simply thrown at Level 2's real mob mix.
Cleric and Paladin have the largest cost% gap to close; Druid has by far the largest win% gap
(more than double anyone else) despite having one of the *smallest* cost% gaps -- a direct
illustration of why cost% and win% needed to stay separate checks rather than one standing in
for the other. Once real Level 2 numbers are proposed, re-running this exact table with the
bumped stats is the actual verification step -- success looks like each class's deltas
shrinking toward its Level 1 self, on all three axes, not this table being repeated unchanged.

## How to validate a specific proposed card change

1. Apply the proposed card/HP bump using `leveled_kit` (`sim/leveling_validation.py`) -- a
   context manager that temporarily swaps one or more cards in a class module's real `CARDS`
   (rebuilding `DECK`/`ALL_HANDS` to match) so every existing tool runs against the leveled
   kit unmodified, then restores the real Level 1 kit exactly on exit, even if the code inside
   raises. Never hand-edit a class module's `CARDS` dict directly to test a proposed change --
   that risks leaving a class's locked kit corrupted if a test script exits early.
2. Re-run `damage_floor_ceiling` and `damage_distribution` -- confirms the ceiling moved by
   about the intended amount without distorting the mean/stdev shape underneath.
3. Re-run `leveling_validation.py`'s `level_comparison_table` -- confirms cost%, win%, and
   pulls-before-death deltas all shrink toward zero (or better) relative to the baseline above,
   not just that the raw numbers moved somewhere. A change that fixes cost% but leaves win%
   regressed (or vice versa) isn't done -- see Druid for why the two don't move together.
4. If the change targets a specific diagnosed weak point (e.g. a class's ranged exposure),
   also re-check `survivability_chart.py` for that specific mob-type/ATK combination.

## How to generate a valid upgrade card

- **Prefer "reskin + retune" over inventing a new mechanic.** Take an existing card's exact
  field shape (same tags, same mechanic relationships to other cards in the kit) and adjust its
  numbers, then give it a new name. Zero new solver architecture required -- it's the same
  pattern Warrior's Guardian/Champion stance duality already uses, just evaluated as a second
  named variant instead of a same-pull choice. Full swap (a genuinely new mechanic) stays
  available for cases that actually call for it, but costs real design and validation time per
  card, same as building a new class did.
- **Everything moves in the game's existing grain size: +1, occasionally +2. Never a big jump.**
  Every real card value in the locked roster already lives in this range (2-6 damage typical,
  0-5 block typical, two purpose-built defense cards breaking out to 10). A "power curve" that
  ignores this and jumps by round percentages would be the first thing in the project to break
  its own established texture.
- **HP bumps stay uniform across the whole roster; mitigation bumps stay per-class and
  diagnosis-driven.** Directly tested, not assumed: a uniform +1 HP had wildly uneven effects
  on survivability (rescued a large chunk of Rogue's failing hands at one ATK level, moved
  Cleric and Druid not at all) -- its payoff depends on whether a class's failures happen to sit
  exactly 1 HP short, which has nothing to do with which classes actually need help. Mitigation
  (block/heal/evasion) is the lever that closes a *diagnosed* gap, because it strengthens the
  specific mechanism that's failing. Use `survivability_chart.py` (constant-ATK dummy, melee
  and ranged) to find *where* a class's toolkit structurally breaks before deciding which card
  gets the bump -- e.g. the roster's evasion-vs-block asymmetry (5 of 9 classes have zero
  `grants_range` cards and fall off a cliff against sustained ranged pressure that the other 4
  don't) is exactly the kind of structural gap a targeted mitigation bump should address, not a
  uniform one.
- **Variance between classes is fine -- it's flavor, not a bug.** The bar isn't "every class
  converges to the same number," it's "no class's survivability collapses toward zero against
  content that will actually exist." Squishier-but-still-viable is a legitimate archetype
  choice; a genuine viability cliff (0% survival, not just a worse cost%) is the only thing that
  actually needs fixing.

## The mandatory upgrade -- how rule 4 gets guaranteed, not hoped for

**Every level grants exactly one upgrade automatically, free, no player choice -- and it must
specifically target that class's own diagnosed survivability gap (rule 3/4 above).** Beyond
that guaranteed one, a player can spend Gold to buy further upgrades (how many, capped or
open-ended, is still undecided -- see Explicitly Open). This split matters for more than
flavor: it's what makes rules 3 and 4 *provable* rather than merely likely.

Earlier in this guide's own history, a flexible player-chosen take-count raised a real problem:
if a player picks which upgrades to take, "survivability must not regress" has to hold for the
*worst* legal combination they could pick, not the average one -- meaning every subset would
need checking, and the floor would only be as strong as the worst case. Making the
survivability fix mandatory and automatic removes that problem instead of working around it:
the "must not regress" promise is satisfied by construction the moment a class levels up, before
a single Gold-purchased choice ever enters the picture. Whatever gets bought on top can only
add to that guaranteed floor.

Which card gets the mandatory upgrade, and how, is diagnosed the same way any other targeted
mitigation gap is found in this guide -- `condensed_trip.py`'s `unplayed_card_diagnostic`
(part of `full_diagnostic`) is a good first pass: a card the solver leaves unplayed unusually
often is a real candidate, since an upgrade there has room to actually change behavior instead
of improving a card that was already being played every time.

**When running `unplayed_card_diagnostic` to pick a *purchased* upgrade candidate, always run
it against the minimum kit that's actually guaranteed -- base kit plus every mandatory upgrade
earned so far, and nothing else.** Never include another *optional* purchased upgrade in that
baseline, even one that's already been designed and locked, unless it's specifically the
candidate being evaluated. Purchased upgrades are independent choices a player can take in any
combination, not a fixed sequence -- diagnosing one candidate against a kit that already
assumes a *different* purchased upgrade was bought skews the comparison toward whatever that
other upgrade happened to leave unused, not toward what's genuinely most underused for a
player who hasn't bought anything yet. **Caught directly, not theoretically:** Dominate
(upgraded Sundering Blow) was picked as Warrior's first purchased-upgrade candidate using the
original, untouched Level 1 diagnostic (Sundering Blow 16.7% unplayed vs. Heavy Swing 13.3%).
Once Shield Bash was locked and the diagnostic was re-run against the *correct* minimum
baseline (Shield Bash applied, nothing else), the real numbers flipped: Heavy Swing was 28.9%
unplayed against that baseline, Sundering Blow only 21.1% -- Heavy Swing was actually the
stronger first candidate the whole time, and would have been chosen first under the correct
method. Dominate's own validated numbers still stand on their own merits, but the *selection*
that led there wasn't run against the right baseline, and that's the mistake this rule exists
to prevent from repeating.

**This gets genuinely harder, not just more tedious, at higher levels.** By Level 3+, "the
minimum kit that's actually guaranteed" means base kit plus *every* mandatory upgrade earned
across all levels so far, correctly excluding every optional purchased one regardless of how
many levels ago it might have been bought -- the guaranteed-vs-optional line has to be tracked
per card, not assumed from level number alone, since a player could easily have skipped buying
anything at Level 2 and still be evaluating a Level 4 mandatory upgrade's candidates from a
kit that's genuinely different from another player's at the same level.

## Worked example: Warrior's Shield Bash (mandatory) + Dominate (first purchased upgrade)

**Diagnosis.** `unplayed_card_diagnostic` on Warrior found Shield Block left unplayed in
56.7% of (hand, mob) pairs -- more than 3x the next-most-cut card (Sundering Blow, 16.7%),
and by far the least-played card in the kit. It's also Warrior's single largest Block value
(Guardian: 5 Block), making it the natural target for the mandatory survivability slot on both
counts: most underused, and most directly tied to the mechanism (Block) that actually keeps a
hero alive. Sundering Blow, the next-most-cut card, became the natural first *purchased*
upgrade candidate (Dominate) -- its own base damage is trivial, but its Sunder mark multiplies
value through the other two cards played, making it a natural fit for finally moving the
offense ceiling, which Shield Bash was deliberately built to leave untouched.

**Shield Bash went through a real correction after its first pass overshot.** The original
version (Guardian 2 DMG/5 Block, Champion 3 DMG/2 Block) fully closed the survivability gap
*by itself* -- checked directly: even Guardian's damage bump alone (Champion untouched at
0/0) already beat the original Level 1 cost% baseline. That defeats the purpose of a
mandatory-plus-purchased split: if the free upgrade alone already solves survivability, a
purchased upgrade has nothing left to meaningfully add on that axis. Isolating which half of
the change caused it (Guardian's own damage bump, not Champion's stat line) mattered directly:
Guardian +2 DMG alone already overshoots the target; Guardian +1 DMG alone leaves it open.
**Locked, corrected: Shield Bash -- Guardian 1 DMG/5 Block, Champion 2 DMG/2 Block.** Ceiling
stays at 14 (unchanged from Level 1, confirming it's still a pure survivability card, not an
offense one). Alone, against the real Level 2 mob mix, it leaves both gaps genuinely open
(cost% 22.4%, +0.2pp *worse* than the original Level 1 baseline; win% 95.6%, -3.3pp short) --
real, deliberate headroom, not close-to-zero rounding.

**Dominate, the purchased upgrade, swept against Shield Bash's corrected numbers, not the
original ones.** Same field shape as Sundering Blow (Guardian/Champion damage, unchanged
Sunder mark), damage value swept 0-5. Two things bounded the choice: the offense ceiling jumps
from 14 to 16 between DMG=1 and DMG=2 -- no integer value lands exactly on the "+1 ceiling"
target, so the closest achievable value overshoots by one extra point, same shape of finding
as Shield Bash's own earlier boundary search. And both gaps (cost%, win%) flip from open to
closed at exactly that same DMG=2 step -- below it, Shield Bash's deliberate headroom stays
unclaimed; at and above it, the purchased upgrade is what actually finishes the job. Win%
saturates immediately after (barely moves DMG=2 through DMG=5), so pushing damage higher only
buys cost%/pulls gains while overshooting the ceiling further for no real reason.

**Locked: Dominate -- Guardian 2 DMG/0 Block, Champion 2 DMG/0 Block, Sunder mark unchanged.**

**Validated (Level 1 original vs. Level 2 with both upgrades, against the real Level 2 mob
mix throughout):**

| | Original L1 (no upgrades) | Shield Bash alone | Shield Bash + Dominate |
|---|---|---|---|
| L2 cost% | 22.2% (L1 baseline) | 22.4% (+0.2pp, still open) | **22.0% (-0.2pp, closed)** |
| L2 win% | 98.9% (L1 baseline) | 95.6% (-3.3pp, still open) | **98.1% (-0.8pp, closed)** |
| Dmg ceiling | 14 | 14 (untouched) | 16 |

Both gaps stay genuinely open on the mandatory upgrade alone, and both close only once the
purchased upgrade is added -- exactly the shape the mandatory/purchased split was supposed to
produce, confirmed against real numbers rather than assumed from the design intent alone.

This pair is the template for every other class's mandatory + first-purchased upgrade going
forward: diagnose the most underused/most-relevant cards via `unplayed_card_diagnostic`, sweep
each against `leveled_kit` + the real Level 1/2 mob pools, stop the mandatory one short of
fully closing either gap on its own, and confirm the purchased one is what actually finishes
the job -- not just that the combined numbers look fine.

## Second worked example: Colossal Swing (Heavy Swing), a second independent purchased upgrade

**Diagnosis, against the correct minimum-guaranteed baseline (Shield Bash only -- see the
methodology note above).** Heavy Swing was left unplayed in 28.9% of (hand, mob) pairs at that
baseline, the highest of any remaining card (Sundering Blow was next at 21.1%, which is why
Dominate's own selection is flagged above as having used the wrong baseline at the time).

**Direction considered and rejected: closing the Guardian/Champion gap.** Heavy Swing's 2/4
split isn't a flaw to fix -- it's shared identity with the rest of the kit (every Warrior card
leans into Guardian=safer/Champion=riskier somehow), and flattening it would be a
redistribution, not more value, unlikely to change *why* the card loses out to more
specialized cards (Vanguard Shield/Blade bring Block and combo bonuses, Execute brings a
killing-blow rider, Dominate sets up the other two cards played -- Heavy Swing brings nothing
but flat damage). The fix needed to add real value, not reshuffle existing value.

**Swept as a 2D grid (Guardian delta x Champion delta, 0-3 each), not just a single shared
bump.** Found a real, consistent pattern: win% is almost entirely a Champion-side lever for
this card -- win gap sits flat at -3.3pp for every Guardian-only bump tested (even Guardian
+2), and only starts closing once Champion gets touched at all. Cost% moves more evenly with
either side. **Smallest value that closes both gaps: Guardian left untouched, Champion 4->5
(a single +1 step)** -- cost gap closes to -0.4pp, win gap closes to -1.1pp. Also the more
flavorful choice: leaving Guardian alone and pushing Champion further leans into Heavy
Swing's already-Champion-favored identity ("the big aggressive swing gets bigger") rather
than diluting it with an across-the-board buff.

**Locked: Colossal Swing -- Guardian 2 DMG/0 Block (unchanged), Champion 5 DMG/0 Block.**

**Guardian/Champion play-rate check, across all three locked upgrades together (a new check,
not covered by cost%/win%/pulls alone) -- does stacking upgrades collapse the class into
always-one-stance?** Measured directly, real Level 2 mob mix throughout:

| Kit | Guardian | Champion |
|---|---|---|
| No upgrades (baseline) | 56.8% | 43.2% |
| Shield Bash alone | 60.6% | 39.4% |
| Shield Bash + Dominate | 58.7% | 41.3% |
| Shield Bash + Colossal Swing | 54.6% | 45.4% |
| All three together | **52.7%** | **47.3%** |

Shield Bash alone pulls further toward Guardian (a direct Guardian-side defensive buff, as
expected); Colossal Swing pulls back toward Champion (its whole point). With all three
upgrades stacked, the split lands at the *most* balanced point of anything tested -- closer to
even than even the un-upgraded baseline. The full upgrade path doesn't collapse the class
toward one dominant stance; both stay genuinely live. Worth running this same check for every
other class's upgrade set once built, not just Warrior's -- a class with a real stance/mode
choice (or an equivalent mutually-exclusive line, like Druid's Shapeshift/Eclipse split) could
in principle have its upgrades quietly collapse that choice without any of cost%/win%/pulls
ever showing it, since none of those three are sensitive to *which* line gets used, only to
the outcome.

## Third worked example: Vanguard Blade [Lv 2], and why Vanguard Shield stays unupgraded

**Diagnosis started from a direct empirical question, not just the unplayed-card rate:** given
Vanguard Shield and Vanguard Blade are each other's combo partner (Guardian: Blade-before-
Shield grants Shield +2 Block; Champion: Shield-before-Blade grants Blade +2 DMG), how often
does either combo actually fire at baseline? Measured directly, real hands and mobs: only 6 of
15 hands even contain both cards, and when they do, the Guardian/Block combo triggers far more
often than the Champion/damage one -- 55.6% vs. 19.4% of the pairs where both cards are drawn
(22.2% vs. 7.8% across every possible hand). The less-played combo (Champion/damage, on
Vanguard Blade) was the one picked to fix.

**The combo bonus itself turned out to be the wrong lever, even though it does move something
(unlike Vanguard Shield's, which does nothing at all -- see below).** Sweeping Vanguard
Blade's combo bonus alone did improve win% (saturating around combo=4, -1.8pp from baseline),
but a flat +1 DMG bump on *both* stances, with the combo bonus left completely untouched,
beat it on every axis -- cost gap closed to -2.1pp (vs. the combo-only version's +0.4pp,
still open), win gap improved further to -1.4pp, and the ceiling didn't move at all. The
reason is mechanical, not a coincidence: a flat bump applies every time the card is played,
while the combo bonus only fires on the ~19-22% of uses where the sequencing lines up --
a much smaller lever by construction. Explicitly asked for and swept as its own direction
("buff the non-combo part, dial back the combo if needed") -- the dial-back turned out to mean
all the way to zero.

**Locked: Vanguard Blade [Lv 2] -- Guardian 4 DMG/2 Block, Champion 4 DMG/0 Block (both +1
from base), combo bonus unchanged.**

**Naming convention decided here, worth carrying forward:** Vanguard Shield and Vanguard
Blade reference each other *by name* in their own combo text ("if the previous round's card
was Vanguard Blade" / "...Vanguard Shield"). Renaming either one the way Shield Bash/Dominate/
Colossal Swing were renamed would break the other's rules text, and would need re-patching
every time either side changes again later. Since both of these are also smaller,
same-identity tweaks rather than new cards (unlike the other three, which became different
enough to deserve new flavor names), the fix is a bracketed level tag on the unchanged root
name -- **Vanguard Blade [Lv 2]** -- rather than a rename. The root name staying intact means
any card referencing it by name stays valid regardless of which level's printed numbers are on
the table. Use this convention for any future upgrade that's a modest numeric tweak rather
than a real identity change, instead of forcing a new name where one doesn't add anything.

**Vanguard Shield itself is explicitly *not* upgraded, and Warrior's upgrade slate is complete
at 4 total (matching the originally proposed count): Shield Bash (mandatory) plus three
purchased -- Dominate, Colossal Swing, Vanguard Blade [Lv 2].** Vanguard Shield's own combo
bonus was checked directly and found to have zero measurable effect at any tested value
(confirmed the trigger condition essentially never fires in an optimal line) -- a real, dead
lever, different from Vanguard Blade's case where the combo bonus did something, just less
efficiently than a flat bump. A flat Guardian Block bump was found and would have worked
(2->3 closed the cost gap on its own), but was never explicitly confirmed as locked before the
decision was made to close the slate at 4 without it. Execute was ruled out earlier in the
same process for the opposite reason -- at 2.2% unplayed, it's already almost always chosen,
leaving essentially no room for an upgrade to change behavior.

## Margins, not gaps -- and why they don't stack additively

**"Gap" (L2-actual minus L1-original) is confusing because the same sign means opposite
things on the two metrics** -- positive is bad for cost% (more expensive than target) but
good for win% (higher than target). Renamed to **margin**, defined so positive always means
"ahead of the L1-original target" and negative always means "behind it," on both metrics:

- **Cost margin** = L1-original cost% minus L2-actual cost% (positive = L2 costs *less*, i.e.
  safer than the target).
- **Win margin** = L2-actual win% minus L1-original win% (positive = L2 wins *more* than the
  target).

**Warrior's full slate, in margin terms (L1-original baseline: 22.2% cost%, 98.9% win%) --
corrected after a real sign error was caught (see below), not the first version presented:**

| Kit | Cost margin | Win margin |
|---|---|---|
| Shield Bash (mandatory only) | -0.2 -- short | -3.3 -- short |
| Shield Bash + Dominate | +0.2 -- cleared | -0.8 -- short |
| Shield Bash + Colossal Swing | +0.4 -- cleared | -1.1 -- short |
| Shield Bash + Vanguard Blade [Lv 2] | +0.9 -- cleared | -1.4 -- short |
| Shield Bash + all 3 purchased | +2.3 -- cleared | +0.8 -- cleared |

**Cost margin closes with any single purchased upgrade paired with Shield Bash. Win margin
does not -- it takes all three together to clear it.** Each individual purchased upgrade only
closes part of the -3.3 starting gap (Dominate to -0.8, Colossal Swing to -1.1, Vanguard Blade
[Lv 2] to -1.4), and combining all three only reaches +0.8 -- **noticeably less than naive
addition would predict** (summing each upgrade's own improvement over the -3.3 baseline
suggests roughly +3.3 combined, not the +0.8 actually measured). That gap between predicted
and actual is the real, checked finding, not the specific numbers themselves.

**A first version of this table had the wrong sign on three of these five win-margin values --
caught directly, not assumed correct.** Converting from the earlier "gap" framing to "margin"
only needed cost's sign flipped (gap and margin are the same formula for win, `L2 - L1`);
win's sign was mistakenly flipped too, turning real negative (still-short) values into
incorrect positive (cleared) ones for the three individual-pairing rows. Re-verified directly
against an isolated, single-config check before correcting the table, not just recomputed and
trusted blindly. Worth remembering when reading any margin table this guide produces: a clean,
memorable-looking number is not the same as a verified one.

**Why win margin under-delivers relative to naive addition, traced directly rather than
assumed:** comparing the actual hand pools between "Vanguard Blade [Lv 2] alone" and "all 3
purchased" found only **1 of the 15 possible hands is identical between them** -- the other 14
differ, because swapping in Dominate and Colossal Swing replaces Sundering Blow and Heavy
Swing's card slots with literally different card names, not stronger versions of the same 15
hands. Win margin is an average over whichever hand *population* is actually on the table, and
that population itself changes with every card swapped, not just its strength. A few of the
new hand combinations introduced by stacking multiple upgrades together can land worse on the
win-rate axis than the corresponding hands would have with fewer cards swapped, even though
every individual upgrade is independently validated as an improvement over its own baseline.
Nothing gets weaker in an absolute sense -- the set of things being averaged over changes.

**Practical rule: don't assume margins stack additively when reading or projecting these
tables, especially win margin.** Cost margin has been monotonic in every case checked so far,
but that's an empirical observation for this specific kit, not a guaranteed property --
re-check both margins directly for any new combination rather than adding up individual
upgrades' numbers and assuming the total holds.

## Second class worked example: Cleric (in progress)

**Diagnosis.** `unplayed_card_diagnostic` on the unmodified Level 1 kit found Heal left
unplayed 58.9% of the time -- the same kind of clear, decisive margin Shield Block had for
Warrior (4x the next-most-cut card), and directly tied to survivability (pure healing, no
damage at all in the base card). Natural mandatory-upgrade candidate on both counts.
Cleansing Barrier, at the other extreme, is never left unplayed at all (0 of 90 pairs) --
ruled out as a candidate for the same reason Execute was for Warrior.

**Real methodology gap found and fixed here, not carried over cleanly from Warrior: cost%/win%
are nearly blind to a pure-recovery card's real value, and `pulls_before_death` had to become
the primary metric, not a secondary one.** Sweeping Heal's heal-amount alone (3 up to 8) barely
moved cost% (capping around -3.4 margin even at heal=8) and never moved win% at all (heal
doesn't help kill anything faster). Checked directly why: even at heal=8, the optimal line
still only played Heal 13.3% of the time it was even drawn, barely above baseline's 11.7% --
because playing a 0-damage card risks not securing a fast kill, and taking an extra round of
full mob damage typically costs more than even a large heal recovers. **Re-run against
`pulls_before_death` instead (the chained, HP-carries-forward metric) and the real value
appeared immediately: heal=8 alone pushed Level 1 pulls from a baseline of 5.58 to 22.37** --
a value invisible to cost%/win% because it only shows up across a chain, not within a single,
always-full-HP measurement. Confirmed as a smooth, real, accelerating curve (not a threshold
bug) by filling in every intermediate heal value.

**That same sensitivity is exactly why the locked value is conservative, not aggressive --
a deliberate design call, not a numeric shortfall.** Pulls-before-death behaves like a random
walk toward zero, and gets disproportionately sensitive to small changes once average net HP
per pull approaches breakeven -- the mechanism behind the heal=8 spike is the same mechanism
that could make a hero effectively unkillable ("an unstoppable chain puller") if pushed too
far. **Locked: Heal -> Greater Heal, heal 3->4, no Block added** (Block was tested and found
to close margins far more efficiently than heal alone, but rejected specifically on flavor
grounds -- a card named Heal shouldn't grant armor). Result: cost margin -4.1 (barely moved,
intentionally), win margin -6.1 (structurally always closed by a different card, this one can
never touch it), pulls margin -0.27 (deliberately kept near-neutral, clear of the explosive
zone). The mandatory slot here is doing very little of the real work on purpose -- nearly the
entire survivability gap is left for purchased upgrades to close.

**Second candidate, re-diagnosed against the correct baseline (Greater Heal locked, nothing
else) per the guide's own step 3:** Fiery Fortitude, 13.3% unplayed, unchanged from the
original baseline diagnostic (Greater Heal's modest bump didn't shift anything else's play
rate). Swept damage and the card's Max HP buff independently -- **the Max HP buff turned out
to be another near-dead lever** (barely moves any metric at any damage level), while damage
was the real driver, with a clean landing exactly on the +1 ceiling target at dmg=4 (14->15)
and a large win-margin jump at that same step (-6.1 -> -1.3). **Locked: Fiery Fortitude ->
Holy Fiery Fortitude, damage 3->4, Max HP buff and heal unchanged.**

**Combined (Greater Heal + Holy Fiery Fortitude) result, against the real Level 2 mob mix:**
cost margin -2.6, win margin -1.3, L2 pulls margin -0.09 -- all three still short, none fully
closed by these first two upgrades alone. That's expected, not a problem: this is 2 of a
likely 4-card slate (mandatory plus 3 purchased, matching Warrior's shape), not the finished
picture.

**One reporting mistake caught and corrected while checking this pairing:** an early version
of this check displayed "L1 pulls" (the *upgraded* kit run against *Level 1* content) as if it
were a meaningful reference point, carried over out of habit from the cost%/win% margin tables
where "L1" legitimately means the fixed, unmodified baseline. For pulls specifically, an
upgraded kit's performance against Level 1 content isn't a real scenario worth tracking --
nobody levels up to keep farming easier content. Only L2 pulls (does the upgrade hold up
against the content it was built for) is the number that matters; drop the L1-pool version
from future tables rather than let it imply equal relevance.

**Third candidate, re-diagnosed against the correct baseline (Greater Heal + Holy Fiery
Fortitude both locked, nothing else):** Call of the Void, 18.9% unplayed -- a plain flat-damage
card with no other mechanic, the same shape as Warrior's Heavy Swing. Cleansing Barrier picked
up a small nonzero unplayed count here (1.1%, from a perfect 0% before) now that Holy Fiery
Fortitude's damage increase makes it slightly less uniquely valuable in some hands -- noted,
not acted on, still far too small to be a real candidate.

**A real contamination bug happened here, caught only later and worth stating plainly rather
than smoothed over: Void Storm's sweep (and Void Mark's, below) were run with the *other*
already-picked purchased upgrade already included in the swap dict, not just the mandatory
Greater Heal.** That's exactly the mistake step 3 of this guide's own procedure exists to
prevent, violated immediately after being written down for Warrior -- see that step's own text
for the full account. Re-swept Void Storm properly, against Greater-Heal-only: win margin
saturates at dmg=7 (-4.5), the same point the contaminated sweep found, but at a much lower real
value than the -0.7 the contaminated test showed -- Holy Fiery Fortitude had been doing most of
that apparent work. Damage 8 was also tested and buys a stronger cost/pulls cushion for free
(-1.7/+0.14 vs. dmg=7's -2.5/-0.04) since win margin is already saturated either way -- **Locked:
Call of the Void -> Void Storm, damage 6->7**, chosen over 8 specifically to keep the card's
printed number more restrained on an 8-damage-feels-like-a-lot-for-a-Cleric basis, accepting the
smaller cost/pulls cushion as a deliberate tradeoff rather than taking the free efficiency gain
8 offered. A full rename (not a `[Lv 2]` tag) since this reads as a genuinely bigger identity
shift, the same bucket as Shield Bash/Dominate/Colossal Swing -- safe to rename outright since
nothing in Cleric's kit references another card by name.

**Fourth candidate: Void Mark -- the first upgrade in this whole project that needed a real
code change, not just new `CARDS` values, and a deliberate one, not a workaround around the
cost.** Void Mark is this project's translation of AGGRO's Shadow Word: Pain, and the flat,
no-mechanic version it shipped with never carried that DOT identity forward. Explicitly
decided *not* to let implementation convenience drive the design here -- the fix was to
actually port the mechanic, not settle for a plain damage bump because that was cheaper to
build. Cleric's `simulate()` had no echo/DOT handling of any kind before this (only
`dmg`/`heal`/`block`/`sacred_balance`/`max_hp_buff`); ported `echo_dmg` in directly from the
already-proven pattern `condensed_necromancer.py`'s Blight and `condensed_runecaster.py`'s
Earth Strike Rune both use (deal damage now, automatically deal more at the start of the next
round, no card spent) -- reusing a validated mechanic shape, not inventing a new one, and
confirmed as a pure no-op against the untouched baseline before sweeping anything.

**This candidate's original sweep was the one that exposed the contamination bug above --
worth keeping the actual discovery story, not just the corrected numbers.** The first,
*contaminated* sweep (Holy Fiery Fortitude and Void Storm already included) showed win margin
reaching +1.6 to +1.9 across a wide band of base/echo combinations. A completely separate,
later table (each purchased upgrade paired with *only* the mandatory one, built to answer an
unrelated question) showed base=4/echo=1 -- the exact combination that table had shown at
+1.6 -- actually sitting at only +0.9 when Void Storm was included instead of excluded, and a
still-different number again in true isolation. Chasing that contradiction down to its root
(the swap dicts) is what surfaced the bug. **Re-swept properly, against Greater-Heal-only: win
margin saturates at only +0.9** (not +1.9), first reached at ceiling=18, tied three ways
(base=4/echo=3, base=5/echo=2, base=6/echo=1).

**Locked: Void Mark -> Void Mark [Lv 2], base damage 3->4, gains echo_dmg=1** ("4 DMG now, 1
more automatically next round," 5 total over its life) -- the *original* candidate value, kept
deliberately rather than moved to one of the higher-margin, saturated options the corrected
sweep surfaced. A `[Lv 2]` tag, not a full rename -- unlike Void Storm, this stays the same
identity (a mark that now bites twice, if anything reading closer to its Shadow Word: Pain
source material than the flat-damage original did), not a big enough shift to earn a new name.
In true isolation (Greater-Heal-only) this value's own win margin is only -0.3, still short of
even the -1.3-to-+0.9 range the rest of the grid spans -- a genuinely weak standalone showing,
accepted anyway because the combined-slate result (all four upgrades together, below) is what
actually matters, and that number holds up fine. A real, considered tradeoff, not an oversight:
chosen to stay conservative alongside Void Storm's dmg=7 rather than push every card to its
saturated value at once.

**Cleric's four-upgrade slate is complete, matching Warrior's shape (1 mandatory + 3
purchased):** Greater Heal (mandatory, heal=4, no Block), Holy Fiery Fortitude (damage 3->4),
Void Storm (damage 6->7), Void Mark [Lv 2] (base damage 3->4, echo_dmg=1). Cleansing Barrier and
Smite remain unupgraded, same reasoning as Warrior's Execute -- both already close to always
being played, leaving little room for a change to matter.

**Final combined chart, all against the real Level 2 mob mix, correctly isolated at every
step:**

| Kit | Cost margin | Win margin | Pulls margin |
|---|---|---|---|
| Baseline (no upgrades) | -4.6 | -6.1 | -0.82 |
| Greater Heal (mandatory only) | -4.1 | -6.1 | -0.27 |
| Greater Heal + Holy Fiery Fortitude | -2.6 | -1.3 | -0.09 |
| Greater Heal + Void Storm (dmg=7) | -2.5 | -4.5 | -0.02 |
| Greater Heal + Void Mark [Lv 2] (4/1) | -4.5 | -0.3 | -0.36 |
| Greater Heal + all 3 purchased | -1.5 | +1.6 | +0.12 |

Also re-checked Greater Heal at heal=5 before finalizing (a real, considered alternative, not
skipped) -- pulls margin more than doubled on that single +1 step (-0.27 -> +0.65 alone,
+0.12 -> +1.17 combined with everything else), the same non-linear sensitivity that made
heal=8 spike to 22+ pulls earlier in this trial. Treated as a real signal to stay conservative,
not a free upgrade -- **Greater Heal confirmed and locked at heal=4**, matching the original,
deliberately weak pick.

## Third class worked example: Paladin

**Diagnosis.** `unplayed_card_diagnostic` on the unmodified Level 1 kit found Invocation of
Sanctuary left unplayed 42.2% of the time, far ahead of everything else. Checked directly
whether this was a real weakness or just an artifact of the two Invocation cards being
mutually exclusive (only one can ever be played per pull, so any hand holding both
automatically leaves one unplayed regardless of strength): of the 38 total unplayed counts,
22 came from a genuine head-to-head loss against Invocation of Grace when both were drawn
(Sanctuary loses that matchup 61% of the time), and 16 came from Sanctuary being cut even when
Grace wasn't in hand at all (vs. Grace only being cut alone in 11 cases). Real, not just
structural noise.

**First candidate considered and abandoned: a plain numeric bump on Invocation of Sanctuary's
base damage.** Swept dmg 3->8 and found the usual saturating win-margin curve (+0.6 by dmg=7-8).
**Rejected as too shallow a fix for what the card actually is** -- Invocation of Sanctuary is a
combo card (retroactive + forward-looking bonus tied to STRIKE cards), and a flat damage bump
doesn't touch that identity at all. Redirected into a real mechanic upgrade instead, matching
the same principle Void Mark's DOT conversion established for Cleric: **implementation
convenience must never be the reason a design gets flattened into a numeric tweak.**

**Locked: Invocation of Sanctuary -> Invoking Aura of Sanctuary, the mandatory upgrade.** Same
combo shape, but the existing per-STRIKE damage bonus (retroactive on this card's own play,
forward on every STRIKE played afterward) is now mirrored 1:1 in Block -- even on a STRIKE card
that has no Block of its own (Bastion's Hammer, for example, picks up Block it never normally
has). Base card also gains a flat 1 Block on its own play. A **real code change**, not a data
edit: `condensed_paladin.py`'s `simulate()` had no Block-bonus path of any kind before this.
Added a new `grants_aura_block` field (`False` on every real card, pure schema addition) so the
new Block-mirroring branch only ever fires for the upgraded card -- verified as a byte-for-byte
no-op against the untouched L1 baseline (21.6% / 97.8% / 5.53) before any sweeping, and the
mechanic itself hand-verified against a raw HP-loss trace (expected 2+2+1=5 total Block across a
3-round combo line; simulator returned exactly 5). A full rename, not a `[Lv 2]` tag, matching
Void Storm/Shield Bash/Dominate/Colossal Swing's bucket -- this is a bigger identity shift than
a numeric tweak, and nothing else in Paladin's kit references this card by name.

Base damage/Block left unchanged from the original candidate (3 dmg / 1 Block) -- the mechanic
addition alone does essentially all the mandatory slot's job: cost margin -4.6 -> -0.7, pulls
margin -0.78 -> -0.04, **win margin completely untouched at -4.1** (expected: no damage was
added, only Block). Same clean division of labor Shield Bash and Greater Heal had -- mandatory
closes cost/pulls, leaves win% for purchased upgrades.

**A real process mistake, worth stating plainly:** after locking Invoking Aura of Sanctuary as
*the* mandatory upgrade, Sacred Light's heal 3->4 bump (tested purely to check its marginal
contribution once the mandatory slot's own game was already known) got silently folded into
"mandatory" alongside it for several sweeps afterward, without the user ever confirming that --
a repeat, in spirit, of the "you make the final call" violation caught during Cleric's trial.
**The precedent is unambiguous and was already established twice over (Shield Bash alone for
Warrior, Greater Heal alone for Cleric): exactly one mandatory upgrade per class per level.**
Caught when presenting a chart that read "mandatory: Invoking Aura of Sanctuary + Sanctified
Light" and the user immediately flagged it. Sacred Light was demoted back to a purchased-upgrade
candidate and every downstream sweep (Grace, Bastion's Hammer, the diagnostic used to find
Bastion's Hammer in the first place) had to be re-run against the correct mandatory-only
baseline.

**A second, independent contamination-bug repeat, caught in the same re-derivation pass:**
Bastion's Hammer's damage sweep was run with Invocation of Grace's dmg=5 already included in the
swap dict -- the identical mistake documented in this guide's own Step 3 after Cleric's Void
Storm/Void Mark incident, violated again despite the write-up already existing. Symptom: the
contaminated sweep showed Bastion(7)'s win margin at -0.7; the corrected, true-isolation sweep
showed -3.2 -- Grace was doing most of the apparent work. The saturation *point* (dmg=7) held up
in both versions; only the absolute value was wrong. Re-swept properly before locking anything.

**Second candidate, correctly diagnosed against the true mandatory-only baseline (Invoking Aura
of Sanctuary alone):** Invocation of Grace, 37.8% unplayed -- now the clear top candidate (Sacred
Light second at 26.7%, Holy Fortress a distant third at 15.6%, Bastion's Hammer still weak at
5.6%). Swept damage 4->8: win margin saturates at dmg=7 (+0.3, rising slightly to +0.6 at
dmg=8) -- the only purchased-upgrade candidate that can push win margin *positive* on its own.
**Locked: Invocation of Grace -> Invocation of Grace [Lv 2], damage 4->5** -- short of the dmg=7 saturation point, a
deliberately conservative pick (win margin -1.3 alone, not yet positive) matching the same
"don't take the strongest legal value just because it's available" discipline Cleric's Void Mark
used.

**Third candidate: Sacred Light -> Sanctified Light, heal 3->4.** Same pure-recovery shape as
Cleric's Heal and Paladin's own mandatory slot before the Aura pivot -- cost%/win% nearly blind
to it (win margin frozen at -4.1 across the entire sweep), `pulls_before_death` the only metric
that moves, and it moves explosively: heal=8 reaches **+10.73 pulls margin**, deep in
"unstoppable chain puller" territory. **Locked: heal 3->4**, the same conservative point Cleric's
Greater Heal landed on, for the same reason -- pulls margin +0.56 alone, clear of the explosive
zone.

**Fourth candidate: Bastion's Hammer, a plain flat-damage STRIKE card, same shape as Warrior's
Heavy Swing / Cleric's Call of the Void.** Corrected sweep (see contamination note above): win
margin saturates at dmg=7 (-3.2), essentially flat afterward. Weakest of the three purchased
candidates by a wide margin (never gets win margin above -3.2 no matter how high damage goes,
since -3.2 is baked in structurally by something the card itself can't touch) -- diagnostic
signal was correctly weak (5.6% unplayed) and held up under a properly isolated sweep.
**Locked: Bastion's Hammer -> Bastion's Breaker, damage 6->7**, the saturation point, same
reasoning as Void Storm/Colossal Swing. A full rename despite being a plain numeric bump --
the user's call, not a strict application of the "numeric tweak gets a `[Lv 2]` tag" convention.

**Paladin's four-upgrade slate is complete, matching Warrior's and Cleric's shape (1 mandatory +
3 purchased):** Invoking Aura of Sanctuary (mandatory), Sanctified Light (heal 3->4), Invocation
of Grace [Lv 2] (damage 4->5), Bastion's Breaker (damage 6->7). Holy Fortress and Might of the
Aegis remain unupgraded -- Might of the Aegis is never cut at all (0%), and Holy Fortress's
mid-pack 15.6% never got swept since Grace and Sacred Light's signal was clearly stronger.

**Final combined chart, all against the real Level 2 mob mix, correctly isolated at every
step:**

| Kit | Cost margin | Win margin | Pulls margin |
|---|---|---|---|
| Baseline (no upgrades) | -4.6 | -4.1 | -0.78 |
| Mandatory only (Invoking Aura of Sanctuary) | -0.7 | -4.1 | -0.04 |
| Mandatory + Sanctified Light (heal 4) alone | -0.4 | -4.1 | +0.56 |
| Mandatory + Invocation of Grace [Lv 2] (dmg 5) alone | -0.4 | -1.3 | +0.02 |
| Mandatory + Bastion's Breaker (dmg 7) alone | 0.0 | -3.2 | +0.10 |
| Mandatory + all 3 purchased | +0.7 | -0.7 | +0.55 |

Cost and pulls margins land solidly positive. Win margin does not fully close (-0.7), unlike
Warrior and Cleric, which both closed to positive with everything stacked -- flagged, not
resolved; accepted as this class's landing spot rather than pushed further.

## Explicitly open

- **How many Gold-purchased upgrades a player can take beyond the mandatory one** -- capped at
  some number, or open-ended limited only by Gold on hand. Not decided. Warrior's finished
  slate (1 mandatory + 3 purchased) is a real data point for this question, not the answer to
  it -- whether 3 purchased upgrades is the right number for every class, or specific to what
  Warrior's kit happened to need, is still open.
- Exact per-level mitigation bump sizes for the other 8 classes -- the *rule* (targeted,
  diagnosis-driven, one mandatory + N purchased) is locked, Warrior's four-card slate is the
  one fully worked example so far.
- Tier 2/3 mob content and hero levels 3-6 entirely -- blocked on this same guide's rule being
  applied through Level 2 first, then re-deriving Tier 2 mobs against whatever Level 3-4 hero
  stats result (see `OPEN_QUESTIONS.md`'s mob-tier discussion for why mob derivation has to
  follow hero power, not precede it).
- The real deck-level swap-in mechanism (how a player actually acquires/chooses an upgrade card
  at the table) -- this guide covers the *numbers*, not the acquisition UX.
- Elite trio re-validation for multi-hero Party Pull math -- every number in this guide's
  current baseline table uses the solo baseline (HP=12 each); `CLASS_BALANCE_GUIDE.md` already
  flags this as pending, and it would shift the Level 2 numbers above once resolved.
