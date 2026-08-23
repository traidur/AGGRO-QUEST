# QUEST -- Leveling Guide

Process doc for the hero power curve across the 6 hero levels (3 tiers x 2 levels each, see
`OPEN_QUESTIONS.md`'s "Tier/level/zone structure" entry). Mirrors `CLASS_BALANCE_GUIDE.md`'s
role for per-class tuning and `DECK_CONDENSING_GUIDE.md`'s role for building a new class --
this is the equivalent process doc for leveling a class *up* once it already exists.

## Status

**Not yet built.** `DESIGN_DOC.md`'s Section VII ("Progression") has stated intent (XP, Leveling,
Cull, Final Boss) but is explicitly marked not implemented past Level 2, and that original vision
predates the now-locked "always exactly 6 unique cards" rule -- see that section for why any
real progression system has to work as a **1-for-1 card swap or in-place numeric bump**, never
additive deck growth. ("Market Row" was on this list until 2026-08-22 -- retired as a separate
system once it became clear the Class Trainer, already built, is Market Row under a different
name; see Section VII.) This guide is the methodology for whenever leveling actually gets built,
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
2. **Max HP moves up by +1 -- but per Tier, not per Level (locked 2026-08-21).** The 6 hero
   levels group into 3 Tiers of 2 Levels each (Tier 1: Levels 1-2, Tier 2: Levels 3-4, Tier 3:
   Levels 5-6, per OPEN_QUESTIONS.md's "Tier/level/zone structure" entry). HP moves up only on
   the level that *enters* a new Tier -- Level 3 and Level 5 -- not on Level 2, 4, or 6, which
   stay within the Tier they're already in. This is why none of the 6 classes' real, locked
   Level 2 slates ever touched their `_HP` constant: Level 2 never crosses a Tier boundary, so
   under this rule it was never supposed to. Card upgrades (mandatory + purchased) still land
   every Level; HP is the slower-cadence system -- a uniform, passive baseline bump, not a
   targeted fix, directly tested earlier (see "HP vs. mitigation" below) and confirmed to have
   wildly uneven, threshold-dependent effects on survivability if applied more aggressively.
   Whether this HP gain requires a Trainer visit (like the mandatory card upgrade now does) or
   applies automatically on crossing the Tier's XP threshold is still open -- unlike a card
   technique, HP reads more like accumulated toughness from the adventuring already done,
   which leans toward automatic, but this hasn't been decided for real yet, and doesn't need to
   be until Tier 2 content actually exists.
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

   **Writing this rule down did not stop it from recurring -- it was violated twice more
   while building Rogue (Relentless Ambush's sweep included Quicker Slash already locked;
   Backstab and Dodge's sweep included both prior purchased upgrades), in the same session
   that has this exact paragraph already written. Prose alone doesn't work here. Use
   `sim/leveling_validation.py`'s `sweep_purchased_candidate(mod, has_stance, mob_key,
   max_hp, mandatory_swap, candidate_old_name, candidate_variants, L1_cost, L1_win,
   L1_pulls)` for every purchased-upgrade sweep from here on -- it raises `ValueError` if
   `mandatory_swap` contains anything other than exactly the one locked mandatory upgrade,
   so a swap dict that's grown to include a previously-locked purchased upgrade fails loudly
   at the point of the mistake instead of silently producing contaminated numbers three steps
   later. Never build `mandatory_swap` by copy-pasting and extending a previous candidate's
   swap dict -- construct it fresh from scratch every single time, containing only the
   mandatory upgrade, no matter how many purchased upgrades are already locked.**
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

## The unplayed-card diagnostic has a tie-artifact bug -- found on Rogue, checked against all three finished classes (2026-08-20)

**The raw `unplayed_card_diagnostic` (Step 1's main tool) counts a card as "unplayed" every
time it's excluded from the reported best line, even when that exclusion was an arbitrary
tie-break, not a genuine weakness.** Found while leveling Rogue: giving Quick Slash a strict,
no-downside +1 Block (never worse in any hand, sometimes better) made its raw unplayed% go
*up*, not down (23.3% -> 31.1%). Traced every one of the 15 hand/mob pairs that flipped --
all 15 were exact ties (Quick Slash and some other card landing on the identical (win,
hp_left)), where a `leveled_kit` side effect (swapping a card under its own name moves it to
the end of dict insertion order, reordering `DECK` and therefore which hand-tuples get
enumerated) flipped which of two equally-good options the solver's first-found tie-break
happened to report. Zero genuine changes. **The raw stat isn't wrong about what the solver
did, but it isn't the number that answers "is this card actually weak" -- ties are real noise
sitting on top of real signal, not a rounding error.**

**Fix: `condensed_trip.py`'s new `unplayed_card_diagnostic_genuine`** -- only tallies a card as
unplayed when *every* 3-card set achieving the best (win, hp_left) for that hand excludes it,
i.e. no tied alternative would have kept it in. Skips (and separately counts) hand/mob pairs
where multiple different 3-card sets tie for best, since no single card can be honestly blamed
as "the" unplayed one there.

**Re-ran it against all three already-finished classes' unmodified Level 1 kits, not just
Rogue, to check whether the noise had already caused a real misdiagnosis anywhere:**

| Class | Raw diagnostic's top pick | Genuine diagnostic's actual top | Verdict |
|---|---|---|---|
| Warrior | Shield Block | Shield Block, 65.0% (39/60) vs. Heavy Swing 20.0% | **Confirmed** -- still dominant with ties removed |
| Cleric | Heal (58.9% raw, looked dominant) | Heal 45.8% (11/24) vs. Void Mark 41.7% (10/24) | **Weakened** -- was "dominant," is actually a near-coin-flip once ties are filtered, though still technically #1 |
| Paladin | Invocation of Sanctuary (42.2% raw) | **Sacred Light 50.0% (12/24) vs. Invocation of Sanctuary 33.3% (8/24)** | **Reversed** -- Sacred Light was the more genuinely weak card, not the one that actually got the mandatory slot |

Also worth noting how much of the raw diagnostic's total sample is tie-noise, not signal: 61 of
90 Rogue pairs (68%), 30 of 90 Warrior pairs, 66 of 90 each for Cleric and Paladin -- the
majority of every one of these diagnostics' raw counts, across every class checked, was ties.

**None of the three finished classes got reopened over this.** Warrior's pick holds up cleanly
regardless. Cleric's still technically wins even with the weaker margin. Paladin's is a real,
deliberate difference (Sacred Light became Sanctified Light, a *purchased* upgrade instead of
the mandatory one) that the user confirmed they're comfortable with on its own terms -- not an
oversight, a genuine choice to give Paladin's slate a different shape than Cleric's, backed by
the fact that Paladin's full four-card slate already passed its complete cost%/win%/pulls
validation regardless of which specific card carries the mandatory label. Recorded here as a
real finding and a real, considered non-fix, the same way this guide already records the
Warrior Dominate and Cleric contamination incidents -- **use `unplayed_card_diagnostic_genuine`
for every class going forward, not the raw version, and don't retroactively second-guess a
class whose full slate already passed real validation just because this tool would have
pointed somewhere slightly different at the diagnosis step.**

## Fourth class worked example: Rogue

**Diagnosis exposed the tie-artifact bug described above -- this class's worked example starts
mid-correction, not from a clean raw-diagnostic read.** The raw `unplayed_card_diagnostic`
pointed at Quick Slash (23.3%) as the top candidate. Swept Quick Slash's Block (+1, the value
the user picked directly rather than the numerically-stronger alternative found in an earlier,
broader sweep) as the mandatory upgrade -- but its own unplayed% then went *up* after the buff
(23.3% -> 31.1%), which is impossible for a strict, no-downside improvement and is what
surfaced the tie-artifact bug in the first place (see the section above for the full
investigation). Re-ran the diagnosis with the fixed `unplayed_card_diagnostic_genuine`:
**Evasion, not Quick Slash, is the class's actual most genuinely weak card** (51.7% of real,
non-tied comparisons, more than double Quick Slash's genuine 20.7%) -- 68% of the raw
diagnostic's total sample (61 of 90 pairs) was tie-noise, which is why the raw version never
surfaced this.

**Evasion's own stat (Block, already 10) is a confirmed dead lever** -- swept 10 through 16,
completely flat, zero movement on any metric at any value. Makes sense once named directly:
Evasion isn't cut for being *too weak* (10 Block already fully absorbs anything a Standard mob
throws in one round), it's cut on pure opportunity cost -- a 0-damage card competing against
cards that deal damage. More of the same stat can't fix a problem that was never about
magnitude.

**Locked: Evasion -> Evasion and Riposte, gains 2 DMG** (Block unchanged at 10). Swept damage
1-3; 3 was still climbing and hadn't saturated, but the user chose to stop at 2 deliberately,
matching this guide's own repeated pattern of landing short of the strongest legal value on
purpose (see Shield Bash's X=3 vs. X=4, Cleric's Void Mark) rather than always taking the
biggest number swept. Cost margin -2.4, win margin -3.2 (structurally near-untouched by a
+2 DMG bump on a card whose real job is defense, matching every other class's mandatory slot
never fully closing win% alone), pulls margin -0.44 -- still short of fully closing the L1/L2
gap on its own, same as every other class's mandatory pick, left for purchased upgrades.
Verified as a genuine fix, not another tie artifact: Evasion and Riposte's genuine unplayed
rate dropped from 51.7% to 8.0% after the change. Clean diagnostic otherwise -- equilibrium
clear, no hidden-domination, damage floor/ceiling unchanged (9/15, correct for a card that
doesn't touch the top end of the damage distribution).

**Re-diagnosed for the first purchased-upgrade candidate against the correct mandatory-only
baseline, using the genuine (tie-filtered) diagnostic this time:** Quick Slash, 48.0% of real
comparisons (12 of 25) -- the clear next candidate. Swept its damage (deliberately not Block --
the user's own call, to avoid an unknown interaction with the STRIKE-tag/finisher-curve
mechanic Quick Slash already feeds into): win margin saturates at dmg=4 (-3.2 -> -0.7, flat
through dmg=5). **Locked: Quick Slash -> Quicker Slash, damage 3->4.** Cost margin -1.9, pulls
margin -0.27 -- still short of closing alone, expected with two more purchased-upgrade slots
still open.

**Third candidate, re-diagnosed against the correct baseline (mandatory + Quicker Slash both
locked):** Ambush, 40.9% of genuine comparisons, just ahead of Quicker Slash's own remaining
36.4%. Swept its damage/round1_dmg pair together (3/5 through 6/8): win margin saturates at
5/7. Also tried a genuinely different lever, not just a bigger number: widening *when* the
existing round-1 bonus can fire, from round 1 only to round 1 or 2 -- a real mechanic change
(`bonus_rounds` field added to `condensed_rogue.py`'s `simulate()`, defaulting to `(0,)` so the
locked Level-1 card is an exact no-op; verified directly, cost/win/pulls unchanged from
baseline). The wider window improved every damage level tested over the round-1-only version
(e.g. at 5/7: +0.6/+0.3/+0.28 vs. round-1-only's +0.3/+0.3/+0.21). **Locked: Ambush ->
Relentless Ambush, damage/round1_dmg left at the original 3/5 -- gains bonus_rounds=(0,1)
(the existing +2 round-1 bonus now also fires in round 2)**, a deliberately conservative pick
matching this guide's repeated pattern: cost margin -1.5, win margin -0.7, pulls margin -0.18 --
a real, positive move over the unmodified card (-1.9/-0.7/-0.27) without taking the strongest
swept combination.

**Contamination caught and corrected (2026-08-20) -- both Relentless Ambush's and Backstab and
Dodge's sweeps above were run against a kit that already included previously-locked purchased
upgrades, the exact mistake this guide's own Step 3 already warns about, violated twice more
in the same session that has the warning written down.** See the section above ("The
unplayed-card diagnostic has a tie-artifact bug") and `sim/leveling_validation.py`'s new
`sweep_purchased_candidate` (raises `ValueError` on a contaminated baseline going forward) for
the full incident and the fix. Corrected, true-isolation numbers for both, against a baseline
with *only* Evasion and Riposte applied:

| Candidate | Contaminated win margin | True-isolation win margin |
|---|---|---|
| Relentless Ambush (3/5) | -0.7 | **-3.2** |
| Backstab and Dodge (dmg=4) | -0.7 | **-3.2** |

**Fourth candidate, Backstab and Dodge, re-swept clean:** damage sweep (block fixed at 2) and
Block sweep (damage fixed at 4) both tested independently against the true mandatory-only
baseline. Damage is the only lever that moves win margin (block stays flat at -3.2 across its
whole range, matching every other pure-Block sweep this guide has ever run). **First lock
attempt (superseded below): Backstab and Dodge -> Backstab and Dodge [Lv 2], damage 4->5,
Block unchanged at 2.** Cost margin +0.1, win margin -2.6, pulls margin +0.27 -- a deliberately
conservative pick short of where win margin would saturate (dmg=7, -1.6).

**Revised (2026-08-20) via the new `armor_pierce` mechanic** (opt-in field added to
`condensed_rogue.py`'s `simulate()` -- ignores the mob's own block value entirely for that
card's damage; absent on every base card, verified no-op). Swept four ways against the true
mandatory-only baseline:

```
                       variant  cost_marg  win_marg  pulls_marg
   4/2, no pierce (unmodified)       -2.4      -3.2       -0.44
             4/2 + armor_pierce       -1.1      -2.9       -0.11
       5/2, no pierce (1st lock)        0.1      -2.5        0.25
             5/2 + armor_pierce        0.6      -2.5        0.44
```

Different shape than Evasion and Riposte's own armor-pierce finding: win margin barely moves
with pierce at either damage level (4-5 damage already overkills through the game's max Block
of 2 most of the time, so win rate doesn't care), but cost/pulls both get a real, additional
gain layered on top of the flat damage bump. **Locked: Backstab and Dodge -> Backstab and Dodge
[Lv 2], damage held at 4 (unbumped from Level 1), gains armor_pierce, Block unchanged at 2.**
Cost margin -1.1, win margin -2.9, pulls margin -0.11 -- deliberately the unbumped-damage
variant rather than 5/2+pierce (the numerically stronger combination), matching this guide's
repeated discipline of not automatically taking the strongest swept value, and keeping the
same "different lever, not a strictly bigger number" spirit as the mandatory-slot exploration
above.

**Relentless Ambush's locked value (3/5) has not yet been re-confirmed against the corrected,
true-isolation numbers** -- flagged here explicitly rather than silently left as-is, since its
contaminated win margin (-0.7) and true win margin (-3.2) are a real, large gap the user should
see before treating 3/5 as final.

## Fifth class worked example: Ranger

**Diagnosis, genuine-diagnostic version used from the start this time.** `unplayed_card_diagnostic_genuine` on the unmodified Level 1 kit found a very thin sample -- only 13 of 90 pairs genuine (77 ties, 85.6%, the highest tie rate of any class checked so far). Beast's Challenge topped it (53.8%, 7/13), Sure Shot second (30.8%, 4/13); flagged explicitly as a real but low-confidence lead given the sample size, not treated as a settled answer. L1 baseline: cost 18.0%, win 95.6%, pulls 6.07. Unmodified L2: cost 21.7%, win 92.4%, pulls 5.36 (margins -3.7/-3.2/-0.71).

**Traced *why* Beast's Challenge loses, not just accepted the diagnostic number.** Every genuine unplayed case for it (6 of 7) shares the same mechanism: a hand containing *both* grants_range cards (Withdrawing Hip Shot and Crippling Shot) plus Sniper/Point Blank Shot -- Sniper's damage depends on whether the *previous* round's card granted Range (7 dmg vs. 5), so an evasion card played right before it is a real, deliberate combo. Beast's Challenge doesn't grant Range and doesn't feed that combo at all, and its own bonus (5 dmg if Beast Bond: Wolf active, 2 otherwise) usually can't fire either since Beast Bond usually isn't in the same hand. It loses to combo synergy, not raw weakness -- a flat buff patches around this rather than fixing it, a legitimate but explicitly acknowledged tradeoff, not an oversight.

**Swept three ways: secondary damage alone, Block alone, both together.** Damage alone (block=0) actually made cost margin *worse* (-3.7 -> -4.6 at dmg_else=4) before recovering slightly -- matches the established pattern that pure damage bumps with zero Block backing them hurt survivability via faster-but-riskier throughput. Block alone (dmg_else=2 unchanged) was a clean, purely positive lever (cost -3.7 -> +2.7 at block=3, win margin flat throughout, as always for pure Block). Combined, the two levers were strongly superadditive -- e.g. dmg_else=5/block=3 hit cost +5.0/win +1.5/pulls +3.18, far more than either alone predicts. **Flagged directly: at dmg_else=4/block=2 and above, the combined sweep closes *both* cost margin and win margin at once -- exactly what rule 2b says a mandatory upgrade must not do.** Only dmg_else=3/block=1 stayed inside that boundary.

**First lock attempt (superseded below): Beast's Challenge, secondary damage 2->3, Block 0->1**
(the 5-dmg Beast-Bond-active payoff untouched). Cost margin -1.4, win margin -0.7, pulls margin
-0.01. Clean diagnostic: equilibrium clear, damage floor/ceiling unchanged (9/14), no real
hidden-domination (the one still-flagged pair is the same pre-existing, already-explained Beast
Bond: Wolf vs. Withdrawing Hip Shot thin-sample flag from lock-in, not new).

**Revised after the first purchased-upgrade sweep (Sure Shot) showed win margin crossing
positive at just dmg=5 -- one purchased upgrade in, with two more slots still to come.** User
flagged this as overshooting too early given the stated concern above, and asked to check
whether pulling the mandatory card back further (rather than tuning Sure Shot down) bought
more headroom. **Locked: Beast's Challenge -> Beast's Stand, secondary damage held at 2
(unchanged from Level 1), Block 0->1** -- a full rename, not a `[Lv 2]` tag, since dropping the
damage lever changes the card's actual identity from an offensive payoff to a purely defensive
one. Confirmed structurally, not just by the numbers: `simulate()`'s
`payoff_wolf` branch only ever touches `dmg` (`dmg_if_wolf` vs `dmg_else`); Block is read
straight from the card's own flat `block` field with no conditional at all, so the +1 Block
lands whether or not Beast Bond: Wolf was played this pull. Mandatory-only margins: cost -1.0,
win **-3.2**, pulls +0.05. The win-margin number looks alarming next to the first attempt's
-0.7 until you check it against the *unmodified*, zero-upgrade L2 baseline quoted above
(margins -3.7/-3.2/-0.71) -- it's essentially identical. That's expected, not a regression: a
pure-Block lever has already been shown in this same sweep (and independently on Crippling
Shot) to leave win margin flat, since Block never changes whether the mob dies. Cost and pulls
both did genuinely improve over that same raw baseline (-3.7 -> -1.0, -0.71 -> +0.05), consistent
with Block being a real, clean, purely defensive contribution. Net effect: 100% of the win-margin
recovery now has to come from the three purchased upgrades, none from the mandatory slot -- a
bigger ask of the purchased slate than the first attempt, but it buys one more grain-step of
headroom (Sure Shot's own sweep now crosses positive at dmg=6 instead of dmg=5).

**Locked: Sure Shot -> Bullseye, damage 4->5.** A full rename by explicit user choice, not the
usual `[Lv 2]` tag a same-shape flat numeric bump would otherwise get (matching the "the
user's call, not a strict application of the convention" precedent set by Invocation of
Grace). Swept fresh against the revised 2/1 mandatory baseline:

```
   variant  cost_marg  win_marg  pulls_marg
         4       -1.0      -3.2       -0.02
         5       -1.1      -1.3       -0.04
         6       -0.3       1.3        0.15
         7       -0.0       1.6        0.21
```

Landed on dmg=5 -- win margin still negative (-1.3), leaving real room for the next two
purchased-upgrade slots rather than closing the gap off one card at a time.

**Third candidate, re-diagnosed via `unplayed_card_diagnostic_genuine` on the mandatory+Bullseye
kit:** 24 genuine comparisons, 66 ties. Bullseye and Beast's Stand (the two cards just buffed)
topped the left-out list (41.7%, 25.0%) -- not a weakness signal, just other hands finding a
stronger combo elsewhere now that those two are stronger. Of the untouched cards, Sniper/Point
Blank Shot (20.8%) and Beast Bond: Wolf (8.3%) read as the real remaining candidates; Crippling
Shot is never left out (0.0%).

**Withdrawing Hip Shot checked and rejected for this slot.** Its own earlier side-candidate
finding (win margin +3.1 at dmg=4, isolated) was confirmed to still apply once actually stacked
with Bullseye: dmg=3 alone already pushed the three-upgrade combined win margin to +2.5 --
well past Paladin's own final reference (-0.7) with one purchased slot still open after it.
Same lever, same overshoot risk already flagged for the mandatory slot -- set aside again, not
locked.

**Sniper/Point Blank Shot swept two ways.** First pass moved only one conditional branch at a
time (`dmg_if_prev_range` alone, or `dmg_else` alone) -- flagged as not a fair equivalent to a
flat-damage card's single-value bump, since Sniper has two damage numbers. Re-swept bumping
both branches together (the honest "+1" equivalent): 8/6 only reached win margin -2.5, 9/7
(+2 both) only -2.2 -- confirms the earlier single-branch finding wasn't an artifact of testing
the wrong thing. Root cause traced directly: only 9 of 15 hands even contain both Sniper and a
grants_range card together, and of the resulting 54 hand-mob pairs, the best line only actually
sequences them adjacent (realizing the combo) 24 times -- a hard structural cap on how much of
the deck this card's bonus can ever reach, on top of the payoff itself being already
near-saturated at its own Level 1 value (win rate barely moves between dmg_if_prev_range 5, 7,
and 8 on the plain 6-mob set).

**Locked anyway, by explicit user choice: Sniper/Point Blank Shot -> Deadeye/Point Blank Shot,
dmg_if_prev_range 7->8 only** (dmg_else held at 5, the weaker single-branch variant rather than
the fairer-but-still-weak 8/6 pair). Margin in isolation (mandatory-only baseline): cost -0.4,
win -2.5, pulls +0.12 -- a small, real improvement over mandatory-only alone, not enough on its
own to be a strong purchased upgrade, but a deliberate, modest pick given the two stronger
candidates in this slot (Withdrawing Hip Shot's damage) were rejected specifically for
overshoot risk.

**Running three-upgrade total (mandatory Beast's Stand + Bullseye + Deadeye/Point Blank
Shot, all stacked):** cost 18.5% (margin -0.5), win 94.9% (margin -0.6), pulls 6.20 (margin
+0.12). Landing close to Paladin's own final reference (cost +0.7, win -0.7, pulls +0.55) --
win margin in particular is nearly identical (-0.6 vs -0.7) -- without the earlier overshoot
risk materializing. Cost and pulls still trail Paladin's reference somewhat, leaving room for
a possible fourth purchased-upgrade slot if the class ends up needing one, matching the
variable per-class purchased-upgrade count already established (Warrior/Rogue: 3, Cleric/
Paladin: 2).

**Fourth-slot investigation: both remaining untouched cards (Beast Bond: Wolf, Withdrawing Hip
Shot) turned out to be dead ends, not the deck as a whole.** Swept Beast Bond: Wolf four ways,
adding a new opt-in `beast_block_value_decayed` field to `simulate()` (verified no-op for the
unmodified card -- defaults to `beast_block_value` itself when absent) to let the persistent
Block bonus step down starting two rounds after Wolf is played, instead of staying flat forever:

```
   variant           dmg  R1/R2/R3  cost_marg  win_marg  pulls_marg
   Wolf unchanged      4     2/1/1       -1.0      -3.2        0.05
   candidate A         4     2/2/1        1.7      -3.2        1.13
   candidate B         5     2/1/1        1.2      -2.5        0.71
   candidate C         3     2/2/1        1.4      -6.0        0.99
   candidate D         2     2/2/2       -0.0     -12.7        0.43
```

Win margin tracked damage directly (worse at lower dmg, matching the established damage/win-rate
lever pattern), while every variant's cost/pulls margin ran well past what a single purchased
slot should contribute -- even the smallest possible single-step bump (own Block 1->2 only, dmg
and persistent otherwise untouched) still posted pulls margin +0.83, bigger than the entire
three-upgrade stack's own total (+0.12). Confirmed this is a property of Wolf's persistent-
stacking mechanic itself, not the specific variants tried: the same mechanism already forced a
correction during the class's own macro-loop fix (+2 Block landed past Paladin before settling
on +1). Withdrawing Hip Shot's damage lever was already known to overshoot (see the three-way
sweep above); its Block lever swept clean but nearly inert (0->2 only moved cost -1.0 -> -0.7,
win margin flat at -3.2 throughout) -- and buffing it to block=1 would make it numerically
identical to Crippling Shot's own base stats (dmg=2/block=1/grants_range=True), a real
duplicate-identity problem flagged directly by the user, not just a numbers concern.

**Locked: Crippling Shot -> Crippling Shot [Lv 2], Block 1->2** (damage held at 2). Deliberately
not Withdrawing Hip Shot's matching lever, specifically to keep the two cards' identities
distinct rather than converging them. Margin in isolation (mandatory-only baseline): cost -0.8,
win -3.2 (flat, as expected for a pure-Block bump), pulls +0.15 -- the smallest, safest of the
three untouched cards' minimum bumps by a wide margin (compare Wolf's own smallest bump at
pulls +0.83 above).

**Final four-upgrade total (mandatory Beast's Stand + Bullseye + Deadeye/Point Blank Shot +
Crippling Shot [Lv 2], all stacked):** cost 18.2% (margin -0.2), win 94.9% (margin -0.6), pulls
6.35 (margin +0.26). Still trailing Paladin's own final reference (+0.7/-0.7/+0.55) on cost and
pulls, win margin nearly identical -- no overshoot at any step across the whole slate.

**Two side candidates checked and set aside, not locked, kept for the record since they're
real data points:** Withdrawing Hip Shot's damage (already the class's most-played card, 0%
genuinely cut) still had real upside at dmg=4 (win margin +3.1, the single largest win-margin
jump found anywhere in this guide) but cost margin stayed slightly negative there (-0.3) --
a pure win%-lane candidate, not the right shape for the mandatory slot's actual job. Crippling
Shot's Block is a near-dead lever (block 1->3 moved cost margin only -3.7 -> -3.3) since its
evasion already covers 5 of 6 mobs; more Block only ever matters against Scout specifically.

**User flagged a real, session-informed risk before locking anything further: Ranger's earlier
macro-loop fix overshot once already (Beast Bond: Wolf's Block, +2 landed past Paladin before
correcting to +1) and Rogue's own leveling pass overshot on its first purchased-upgrade
attempt too.** Explicit plan going forward: check the running cumulative cost/win/pulls
margins against Paladin's own final locked numbers (cost +0.7, win -0.7, pulls +0.55) as a
rough ceiling reference at every step, not just at the final chart, so an overshoot gets
caught early rather than after the whole slate is already locked.

## Sixth class worked example: Wizard

**Started, then paused mid-pass to correct a real factual error in the class's own docstring
before continuing -- see `condensed_wizard.py`'s "Level 2 leveling infrastructure" note.** The
docstring claimed "Wizard has exactly one full-block card" as the explanation for a set of
mathematically-unavoidable deaths found during an earlier tempo fix. Checked directly and found
this wrong: `grants_range` (Snap Freeze, Frozen Shot) also fully answers a melee round, same as
Ice Barricade's block=10 does unconditionally -- the kit actually has three such cards. Re-ran
the check separating genuine death (`hp_left<=0` in the best available line) from flee
(`win=False` but `hp_left>0`, since the two were being conflated by a naive "any loss" count):
genuine deaths clear entirely by HP=7 (50% of WIZARD_HP), and the real, much narrower mechanism
is that a handful of specific hands draw only one of the three defensive-capable cards, letting
the other two exposed rounds' combined damage exceed a low starting HP -- a hand-composition
edge case, not a fixed one-card ceiling. Confirms `defense_floor_sweep`'s own documented 42.9%
crack point was measured correctly, and that crack point is safer than Paladin's own locked
35.3% -- not a blocker for leveling. Task #29 closed on this finding.

**Diagnosis:** L1 baseline cost=21.0%, win=96.7%, pulls=5.31. Unmodified L2: cost=24.4%,
win=92.4%, pulls=4.98 (margins -3.3/-4.3/-0.33). `unplayed_card_diagnostic_genuine` found the
cleanest, most decisive signal of any class checked this session: **Fire Blast left out in
77.8% of genuine comparisons (14 of 18, only 72 ties)** -- every other card at 11.1% or below.

**Traced why, not just accepted the number.** Fire Blast is `weave_source=True`, same as Snap
Freeze and Ice Barricade -- but Weave only needs one source card to arm and doesn't stack, so
any hand holding Fire Blast alongside either other weave-source has a redundant arming option.
In all 14 genuine cases, the solver picks Snap Freeze or Ice Barricade instead, because they
arm Weave *and* provide real Block/evasion, while Fire Blast arms Weave and contributes nothing
else (block=0, no grants_range). Its own raw damage (3, flat -- the "weave-boosted" second
value doesn't even move, since Fire Blast is never itself a payoff card) is also the lowest of
any damage card in the kit.

**Swept plain damage first (dmg 3-6):** matches the established pattern -- pure damage with no
Block backing it actually *worsens* cost/pulls margin while win margin climbs and saturates
around dmg=5-6 (+0.5). Cost margin never gets better than -3.3 anywhere in this sweep, since
Fire Blast starts with zero Block.

**Explored `killing_blow` (Warrior's Execute pattern) as an alternative lever -- rejected,
wildly overpowered.** Added as a new opt-in field to `condensed_wizard.py`'s `simulate()`
(verified no-op). Win margin tracked identically to the plain-damage sweep at every value
(killing blow doesn't touch whether the mob dies, only whether its attack lands that round --
a pure survivability lever). But cost/pulls exploded: even at dmg=3 (unbumped), cost margin
alone hit +1.4 and pulls +0.65 -- bigger than Ranger's entire four-card *stacked* slate. At
dmg=6, pulls margin hit +3.53, the largest single-lever swing found anywhere this session.
Rejected for the mandatory slot as a fundamentally different order of magnitude, not a tuning
nuance -- landing the kill was simply too frequent an event to treat as an incremental buff.

**Explored `armor_pierce` (new concept: ignores the mob's own block value entirely for that
card's damage) -- much better-behaved.** New opt-in field added to `simulate()` (verified
no-op). Cost/pulls margins stayed essentially identical to the plain-damage sweep (armor pierce
doesn't touch survivability, a pure offense mechanic), but win margin improved meaningfully at
low damage specifically: dmg=3 went from -4.3 (plain) to **-1.4** (pierced) -- a real +2.9pp
gain from ignoring mob block at Fire Blast's own unbuffed value. The gain shrinks to nothing by
dmg=5-6, where both sweeps converge to the same +0.5 (mob block stops mattering once raw damage
already overkills through it).

**User pushback, correctly caught a thematic mismatch:** a Block bump on "Fire Blast" -- floated
as the next lever to pair with damage -- doesn't read as a fire-attack spell's identity. Agreed:
kept Fire Blast purely offensive (damage + armor pierce, no Block at all), deferring the
cost/pulls recovery to a purchased upgrade on one of the kit's actual defensive cards later
(Ice Barricade, Snap Freeze, or Frozen Shot -- all already carry Block or evasion, on-theme for
a bump). Mirrors Ranger's own mandatory shape in reverse: Beast's Stand ended up purely
defensive and left all win-margin recovery to purchased upgrades; Fire Blast purely offensive
leaves all cost/pulls recovery to purchased upgrades.

**Locked: Fire Blast, damage 3->4, gains `armor_pierce`, Block stays 0.** Chosen over dmg=5
(where win margin would already flip positive, +0.5) specifically to leave real headroom for
the purchased-upgrade slots, matching the "don't recover the whole gap in one card" balance
principle reinforced by the Rogue/Ranger armor-pierce tangent below. Cost margin -3.8, win
margin -0.5, pulls margin -0.41.

**First purchased-upgrade candidate, re-diagnosed against the mandatory-only baseline:** Fire
Ball, 18.2% of a thin genuine sample (2 of 11, 79 ties -- flagged low-confidence given the
sample size). Traced why: both genuine cases lose specifically when Arcane Volley is also in
the hand -- Arcane Volley (dmg 6/8) strictly outdamages Fire Ball (dmg 5/7) on both its base and
weave-boosted faces, so Fire Ball is dominated whenever they're both available. Checked how
often Fire Ball even gets to show its boosted value when it *is* played: only 30.4% of the time
(14 of 46) -- the other 69.6% it fires at its weaker 5-damage base, making the domination
problem worse than the card-vs-card comparison alone suggests.

**Redesigned rather than just bumped: dropped the Weave dependency entirely, flat 7 damage.**
Swept both `payoff=True` (still consumes an armed Weave bonus for no benefit) and `payoff=False`
(never touches Weave) at the same flat value:

```
                    variant  cost_marg  win_marg  pulls_marg
   5/7 payoff (unmodified)       -3.8      -0.5       -0.36
      flat 7, payoff=False       -2.6       0.2       -0.21
       flat 7, payoff=True       -2.7       0.2       -0.21
```

`payoff=False` is marginally cleaner (avoids wasting an armed Weave bonus on a card that no
longer needs it) and reads as the more honest design -- this card genuinely doesn't interact
with Weave anymore, so it shouldn't still be flagged as a payoff consumer. **Locked: Fire Ball
-> Fire Ball [Lv 2], damage flat 7 (was 5/7 weave-conditional), `payoff` flipped to False.**
Cost margin -2.6, win margin +0.2, pulls margin -0.21. Win margin flips positive here, but this
is a purchased (optional, paid) upgrade rather than the free mandatory slot, so the "don't close
it in one card" bar is looser than it is for the mandatory pick -- accepted deliberately given
how little headroom the class has left overall (mandatory + this one purchased upgrade still
leaves cost/pulls solidly negative).

**Second purchased-upgrade candidate: Ice Barricade**, re-diagnosed with the unplayed-card
signal effectively exhausted (only 8 genuine comparisons left after the first two upgrades, all
of them just the newly-buffed Fire Blast -- the sample is too thin to point at anything past
this point, so the pick came from direct review of the remaining four cards instead). Confirmed
it's actually a well-used card first, not a neglected one -- played in 81.7% of hand-mob pairs
where drawn (49 of 60) against the current locked kit.

**Block confirmed a completely dead lever, same as Evasion's own finding.** Swept 10/12/15,
identical margins at every value -- max mob ATK anywhere in the game (including Elites) is 6,
already fully absorbed by block=10. **Damage, by contrast, is a clean, strong lever** (same
opportunity-cost shape as Evasion -> Evasion and Riposte -- a 0-damage card competing purely on
opportunity cost against cards that deal damage):

```
   variant  cost_marg  win_marg  pulls_marg
     dmg=0       -3.8      -0.5       -0.36
     dmg=1       -2.9      -0.5       -0.20
     dmg=2       -1.3        1.1        0.04
     dmg=3        0.8        2.1        0.47
```

**Locked: Ice Barricade -> Ice Palisade, damage 0->1, Block unchanged at 10.** Cost margin -2.9,
win margin -0.5, pulls margin -0.20 -- chosen over dmg=2 (win margin +1.1) specifically because
dmg=2 was judged to overshoot, leaving dmg=1 as the more conservative pick that doesn't move win
margin off its mandatory-only value at all.

**Third purchased-upgrade candidate: Snap Freeze**, picked from direct card review rather than
the unplayed diagnostic (effectively exhausted by this point -- see above). Swept damage and
Block independently, both against the mandatory-only baseline (Fire Blast alone):

```
--- damage (block held at 1) ---          --- block (damage held at 1) ---
   dmg=1 (unmodified)  -3.8  -0.5  -0.37      block=1 (unmodified)  -3.8  -0.5  -0.37
   dmg=2               -2.4   1.1  -0.20      block=2               -3.4  -0.5  -0.28
   dmg=3               -1.0   2.1   0.10      block=3               -3.4  -0.5  -0.25
   dmg=4                1.3   3.3   0.59      block=4               -3.4  -0.5  -0.25
```

Damage turned out to be the much stronger lever, correcting an initial guess that Block would
matter more here (Snap Freeze's Block only ever activates against Scout, same reason it's a
near-dead lever for Ranger's Crippling Shot) -- Block saturates fast (identical at 3 and 4) and
never moves win margin at all, the usual pure-Block signature. dmg=4 already reads as a likely
overshoot (cost margin alone reaches +1.3, higher than anything else locked this pass). Checked
the combined 2/2 pairing: cost -2.0, win +1.1, pulls -0.11 -- mildly superadditive over damage
alone (-2.4/-0.20), same pattern seen everywhere else this session when damage and Block are
paired; win margin matches the damage-alone result exactly, as expected.

**Locked: Snap Freeze -> Deep Freeze, damage 1->2, Block 1->2.** A full rename (not a `[Lv 2]`
tag) since both fields moved together -- a big enough combined shift to earn a new name, same
convention used for Ranger's Beast's Stand and Bullseye. (Named Deep Chill at first lock,
renamed to Deep Freeze immediately after.) Cost margin -2.0, win margin +1.1, pulls margin
-0.11.

**Combined total (mandatory + all 3 purchased) overshoots Paladin's own final reference on win
margin -- left as-is, not re-tuned, by explicit user call.** Full chart:

| Kit | Cost margin | Win margin | Pulls margin |
|---|---|---|---|
| Baseline (unmodified L1 kit) | -3.3 | -4.3 | -0.33 |
| Mandatory only (Fire Blast) | -3.8 | -0.5 | -0.41 |
| Mandatory + Fire Ball [Lv 2] | -2.6 | +0.2 | -0.21 |
| Mandatory + Ice Palisade | -2.9 | -0.5 | -0.20 |
| Mandatory + Deep Freeze | -2.0 | +1.1 | -0.11 |
| **Mandatory + all 3 purchased** | **0.0** | **+2.1** | **+0.25** |

Every individual card looked conservative in isolation against the mandatory-only baseline --
the overshoot only appears once all three are actually stacked together, since each purchased
upgrade in this guide's procedure only ever gets checked against mandatory-only, never against
the running combined total as more cards get locked. Cost (0.0 vs. Paladin's +0.7) and pulls
(+0.25 vs. +0.55) both land close to the reference; win margin (+2.1 vs. -0.7) is the one that
runs away, more than 2.5x past it. **Explicitly not re-tuned this session** -- the user's own
call, given how hard these small per-card swings are to keep track of cumulatively once several
of them stack. Flagged here so a future pass doesn't mistake this for an oversight.

**Side tangent this session, not Wizard-specific: a cross-class armor-pierce retrospective.**
Prompted by Fire Blast's finding, checked which already-locked Level 2 upgrades (across Warrior,
Cleric, Paladin, Rogue, Ranger) were flat damage bumps that could instead have kept damage flat
and added `armor_pierce` -- purely as a "different lever, not necessarily better" exploration,
not a re-litigation of anything already locked. Quantitatively (against the real L2 mob pool,
63 rounds, block distribution 44@0/7@1/12@2 -- max block anywhere is 2), the lower a card's
damage, the larger the fraction lost to block and the more pierce can recover: Warrior's
Dominate (pre-bump dmg=1) topped the list at 30.2% of its own damage lost to block on average.

One real change came out of this and was locked into Rogue (see its own worked example above,
"Revised" paragraph added 2026-08-20): **Backstab and Dodge [Lv 2]'s damage held at 4** (not
the first-attempt 5) **plus `armor_pierce`** -- deliberately the unbumped-damage variant over
the numerically stronger 5+pierce combination, same "leave real margin" discipline. **Evasion
and Riposte (Rogue's mandatory) was swept the same way but explicitly NOT changed** -- dmg=2+
pierce was found and rejected on sight as too strong for a free mandatory slot (it alone nearly
closed cost margin, +0.1, using nothing but the mandatory card), dmg=1+pierce was floated as the
more balance-consistent alternative but never actually confirmed -- Evasion and Riposte stays
at its original locked value (gains 2 DMG, no `armor_pierce`, see above). Quicker Slash was also
tested at its original unbumped damage (3) plus `armor_pierce`, briefly locked, then explicitly
reverted by the user in the same turn -- it stays at its original locked value too (damage
3->4, no `armor_pierce`, see above). Flagging both non-changes explicitly here so a future
session doesn't mistake "we explored it" for "we locked it."

Ranger's own cards were swept the same way (Bullseye, Deadeye/Point Blank Shot, Withdrawing Hip
Shot, Crippling Shot, Beast Bond: Wolf all tested with `armor_pierce`) but none were locked --
results kept for the record: Withdrawing Hip Shot and Crippling Shot both showed large,
well-rounded gains from pierce alone (e.g. Hip Shot: cost -1.0->+0.6, win -3.2->-0.3, pulls
+0.07->+0.59), Beast Bond: Wolf improved cost/pulls but never win margin (its one-time pounce
damage is never the deciding factor for a kill even unblocked), and Deadeye/Point Blank Shot
showed *zero*
aggregate effect despite 114 real, verified per-sequence differences -- traced to `
best_line_for_hand` already routing that card around blocked rounds whenever a better-scoring
ordering exists, so a real, confirmed mechanic effect never surfaces in the hand-level optimum.
Ranger's slate was left as originally locked (mandatory + Bullseye + Deadeye + Crippling Shot
[Lv 2], no `armor_pierce` anywhere) -- "good as-is, no room for armor pierce," user's own call.

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
| Rogue | 18.4% | 6.04 | 97.8% | 23.4% | 5.00 | 94.6% | +5.0pp | -1.04 | -3.2pp |
| Ranger | 18.0% | 6.07 | 95.6% | 21.7% | 5.36 | 92.4% | +3.7pp | -0.70 | -3.2pp |
| Runecaster | 23.3% | 5.40 | 97.8% | 27.2% | 4.74 | 93.0% | +3.9pp | -0.65 | -4.8pp |
| Druid | 25.0% | 5.83 | 100.0% | 28.2% | 5.00 | 91.4% | +3.3pp | -0.82 | -8.6pp |
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

## Purchased upgrade order: randomized per hero, not fixed, not player-selected (locked 2026-08-23)

`sim/macro_sim.py`'s `LEVEL2_PURCHASED_ORDER` list was originally walked in a single fixed
sequence -- the same order for every hero of a given class, every playthrough. Corrected: each
hero now gets their own shuffled permutation of that list's indices
(`HeroBoardState.skill_purchase_order`, set once at hero creation), revealed one at a time as
they're bought -- a personally-shuffled deck of upgrade cards, not a script. The mandatory
upgrade (still free, automatic, earned the instant a hero reaches Level 2 and visits a Trainer)
is completely unaffected -- this only concerns the *purchased* ones beyond it.

**Why not player-selected instead, letting a human pick which of the remaining upgrades to
buy:** QUEST is a quick, one-shot, non-legacy game -- sit down, play a session, done, not a
persistent campaign. Free selection among a known set of upgrades converges over repeated
sessions: once a table has played enough times, everyone learns which purchased upgrade is
strongest and just buys that one first, every time, at every table. Randomizing which upgrade
becomes available removes that convergence entirely -- the real decision left to a player is
whether to spend the Gold on whatever's offered (or save it, or spend on the Bag Upgrade
instead), never which specific card.

**Why this is safe to randomize at all, rather than a break from validated balance:** the
methodology above (see "always run it against the minimum kit that's actually guaranteed")
already diagnosed each purchased upgrade candidate independently, against the mandatory-only
baseline, never against a kit assuming some other purchased upgrade came first -- "Purchased
upgrades are independent choices a player can take in any combination, not a fixed sequence"
(verbatim, above). The list's own stored order was only ever the sequence each card happened to
get derived and locked in during this guide's own worked examples, never a claim that buying
them in a different order changes anything about their safety. Randomizing acquisition order
doesn't touch that validation at all -- the final, fully-stacked kit (all purchased upgrades
owned) is identical regardless of what order they arrived in, and every intermediate state
along the way was already validated on its own, independent of what came before it.

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

## Purchased-upgrade pricing, locked (2026-08-20)

**Every purchased (non-mandatory) upgrade costs a flat 8 Gold, bought at the Class Trainer
(Zone 2), not Town** -- matches `DESIGN_DOC.md`'s locked map shape and the separately-locked
Bag Upgrade reprice (16G -> 12G). Both numbers were checked against real Gold-at-Level-2 data,
not picked cold: at the (since-changed) 12-XP Level-2 threshold, a player had ~11.7-13.1 Gold
on average (Warrior/Cleric/Paladin) -- enough to comfortably afford one skill (8G, leaving a
real 3.7-5.1G cushion) or the Bag Upgrade (12G, landing right at the edge, -0.3 to +1.1
leftover) but not both at once. That's a real, meaningful first choice, not a foregone
conclusion either way -- re-validated after the Ranger/Rogue/Druid macro-loop fixes and again
after the real two-zone/Border-Node map replaced the earlier flat estimate; the price held both
times without needing adjustment.

**Stale as of 2026-08-21, not yet re-checked:** the Level 2 XP threshold moved 12 -> 6 (Level 1
quest compression) and Gold-at-Level-2 moved to ~17-18 (both that change and the new +1
Gold-per-won-pull rule -- see `MACRO_LOOP_GUIDE.md`'s own entry). ~17-18 Gold no longer sits
exactly at either the "one skill, real cushion" or "Bag Upgrade, right at the edge" shape this
paragraph describes -- it's close to affording both at once (8+12=20 vs. ~17-18 available),
which may or may not still produce a real first choice. Re-sweep before trusting this pricing
again, don't assume it still holds.

**Applied to every purchased upgrade locked so far, all at 8G each:**

| Class | Purchased upgrade | Price |
|---|---|---|
| Warrior | Dominate | 8G |
| Warrior | Colossal Swing | 8G |
| Warrior | Vanguard Blade [Lv 2] | 8G |
| Cleric | Holy Fiery Fortitude | 8G |
| Cleric | Void Storm | 8G |
| Cleric | Void Mark [Lv 2] | 8G |
| Paladin | Sanctified Light | 8G |
| Paladin | Invocation of Grace [Lv 2] | 8G |
| Paladin | Bastion's Breaker | 8G |

A player buying all 3 of a class's purchased upgrades needs 24G total, well past the ~12G a
Level-2 player typically has on hand -- matches the "Three skills (24G)" pacing check from the
Gold-accumulation work (~4.5-6.1 trips, ~33-40 XP by then), meaning a full purchased slate is a
real mid-game goal, not something bought all at once the moment Level 2 unlocks.

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
