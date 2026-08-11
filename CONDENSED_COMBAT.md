# Condensed Combat — Design Log

This is a parallel track to `CLASSES.md`. `CLASSES.md` documents a direct, 1:1-scale
translation of AGGRO's 10-card deck / 5-card hand / 3-Energy system into QUEST terms —
that translation and its simulator (`engine.py`, `simulate.py`) still exist untouched.
This document tracks a different, smaller combat model being explored as a possible
replacement, prototyped so far only for Warrior.

## Why this exists

The AGGRO-scale translation kept needing more machinery to stay faithful to AGGRO's own
granularity: Exhaust (cards sideline, dummy placeholders, class-specific refresh
currencies), a separate Held/Power-card mechanism, Winded/OOM tracking, and a rollout AI
just to play the resulting decks correctly (common random numbers, win-speed tiebreaks,
top-k pruning fixes). That complexity is appropriate to AGGRO, where the fight *is* the
game. QUEST's own design pillars say combat is a logistics "toll check," not the main
event — the trip/Bag-Tetris/loot-decay loop is supposed to carry the real weight. By the
time Blessed Fortitude's held-card duplication bug got fixed, combat-level complexity was
rivaling or exceeding the macro loop's, which is backwards for what QUEST is trying to be.

The condensed model is an attempt to shrink combat down to match its intended weight.

## Core structure

- **Deck = 6, hand = 4, 3 rounds per pull.** If the mob isn't dead by the end of round 3,
  it flees (no reward, no further attrition — matches the same "give up on a slog" logic
  the AGGRO-scale model used at MAX_ROUNDS, just recalibrated for a smaller kit).
- **One card played per round**, not a subset chosen within an Energy budget. You draw 4,
  sequence 3 of them across the 3 rounds; the 4th is deliberately left unplayed. That's a
  real decision (which 3 of 4, in what order), not filler.
- **No Energy pool, no per-card cost accounting.** The old system's "which subset fits my
  3 Energy" knapsack problem is gone; it's replaced by a pure sequencing/ordering problem.
- **No dice inside a pull.** Mob intents are fixed and fully known in advance, round by
  round — this is *more* faithful to AGGRO's own "card draws are the only randomness"
  rule than the AGGRO-scale QUEST translation currently is, since that one still resolves
  incoming damage from a flat mob ATK stat with no round-to-round shape.
- **The only randomness is which 4-of-6 hand you draw.** The deck fully resets every
  pull — nothing persists between pulls at the card level (see Exhaust, below).

## Stance: Guardian / Champion, locked for the whole pull

**Corrected 2026-08-07** — this section previously documented a "one free flip" rule
(pick a stance before round 1, flip to the other stance exactly once at any point). That
rule was proposed, tested once as a one-off experiment, found to have a real cost (it made
Vanguard Shield nearly unplayable) without fixing the problem it was tested against, and
was left as an open, unresolved question in conversation — then a context compaction lost
that open status, and every downstream Warrior balance pass for the rest of that session
(the full Vanguard Blade/Shield rework, Shield Block's tuned value, the stance-balance
numbers, all of it) was actually run against the *old* flip-enabled solver while everyone
involved believed no-flip was already locked in. Corrected in code and here once the
mismatch was caught and the full diagnostic suite re-run against the real rule. See
`CLASS_BALANCE_GUIDE.md` for the general lesson (verify a rule against the file, not
against memory of a conversation) this produced.

A global toggle, not a per-card branch. **Pick a stance before round 1 and it's locked for
the entire pull — no flipping, ever.** Because mob intent is visible in advance, this makes
stance choice a real per-mob read: which stance is correct depends on the specific mob
you're about to fight, not just your hand. Confirmed empirically (not assumed) that this
produces a genuine, deliberate identity split rather than arbitrary noise: Guardian is the
stronger pick against weak/low-HP mobs (block matters less there, so preserving HP wins
outright), Champion is the stronger pick against strong/high-HP mobs (raw damage output
becomes the binding constraint). That mob-dependent split was deliberately kept rather than
flattened toward artificial 50/50 parity — it's an intentional puzzle dimension, not a bug.
See `CLASS_BALANCE_GUIDE.md`, "Mob-dependent performance can be a feature, not a bug."

**Physical implementation, locked:** every Warrior card is printed with its Guardian and
Champion values as mirrored/rotated text, one on each end of the card. Stance isn't tracked
with a separate token at all — lay all three played cards the same way up for the whole
pull, Guardian side showing or Champion side showing, decided before round 1 and never
changed. No flip to enforce, no turning mid-row — simpler than the old one-flip version,
not just different from it.

**Sunder wording note:** Sundering Blow is the only card in the deck carrying the "sunder"
tag, and the deck has no duplicate cards, so the bonus it grants can never exceed a single
stack within one pull — it's not really a counter, it's a binary "has Sundering Blow been
played yet" check, fully readable from the play area. Describe it as "the mob is marked
Sundered; your next damaging card deals +2" rather than "stacking token," since the
stacking framing implies bookkeeping that was never actually required. This generalizes:
**as long as every card in a 6-card deck stays unique (no duplicate copies), any mechanic
tied to a single card's tag is automatically capped at 0-or-1 and needs no separate token**
— true for Sunder, Spellweave, and the proposed stacking mechanic for Cleric alike. Worth
keeping "one copy of everything" as a deliberate constraint on every future class's deck,
not an accident.

## Exhaust dropped entirely

Working theory: HP becomes the *only* attrition currency. Instead of cards being spent and
refreshed via Food/Water (the single largest source of bugs and bookkeeping in the
AGGRO-scale build), attrition comes from **hand-draw variance** — if your best defensive
or offensive tool isn't in the 4 cards you drew this pull, you face the mob's known
pattern without it, and that's a real, recurring cost across many pulls. This removes an
entire subsystem (dummy cards, exhausted/held index tracking, refresh policies) at the
cost of an unproven assumption: that draw variance alone produces *enough* attrition over
a multi-pull trip. Not yet tested past single-pull win rates — flagged as open below.

## Out-of-combat healing (proposed, not yet built)

Idea in play: classes with a heal kit (currently just Cleric) get a resource-free heal
between pulls that doesn't cost a Bag slot and doesn't break the pull chain (no trip back
to town required). This narrows Food back down to a single job — a pure HP consumable —
now that it no longer also has to serve as the Exhaust-refresh currency. Open question:
Cleric-exclusive, or a smaller trickle for every class scaled by how much healing is in
its kit?

## Solver methodology

At this scale (15 possible hands × a few dozen orderings × a handful of stance sequences),
the full decision space is only a few thousand combinations — small enough to **enumerate
exactly** rather than simulate with random trials. `condensed_warrior.py` does this: for
every possible hand, it finds the provably optimal line (card order + stance sequence,
including branching on Brace's reactive choice) instead of estimating a win rate from
sampled trials. This sidesteps rebuilding anything like the AGGRO-scale rollout AI —
exact search is both cheaper and more precise than Monte Carlo at this size.

## Warrior kit — v1 draft (superseded)

First-pass condensation of the original 8-card AGGRO-scale Warrior kit, spreading total
damage/mitigation across 6 cards rather than preserving AGGRO fidelity card-for-card:

| Card | Category | v1 values |
|---|---|---|
| Heavy Strike | Attack | flat 5 DMG |
| Sunder Strike | Attack + ramp | 3 DMG, stacking Sunder token |
| Execute | Finisher | flat 8 DMG, legal only below 50% mob HP |
| Rally Blow | Attack + Defense | 4 DMG + 3 Block, small G/C bonus deltas |
| Shield Wall | Defense | 6 Block, small G/C bonus deltas |
| Brace | Defense | flat 7 Block, no stance interaction |

**Diagnostics run against v1:**
- Mob variety validated as a real source of decision depth — 13 of 15 hands required a
  distinct optimal line against at least 3 of 5 candidate mob patterns.
- No fully dead card, but Brace was played in only **11.4%** of winning lines vs 43–71%
  for everything else — alive but functionally near-dead.
- Stance flip looked universal at first glance (100% of winning lines included one), but
  that was a tie-break artifact of the solver, not a real finding — checking whether the
  chosen flip was *strictly* better than the best same-card-order line without it showed
  the flip was only actually load-bearing in **8.6%** of winning lines. Two of six cards
  (Heavy Strike, Sunder Strike) had zero stance interaction at all, diluting its impact.

## Warrior kit — v2 rework (current)

Reworked to make stance and the weak card both do real work — moved from "flat value +
small delta bonus" to explicit per-stance values, and replaced Brace with a
sequence-reactive card instead of a third flat-Block option:

| Card | Guardian | Champion | Notes |
|---|---|---|---|
| Heavy Strike | 2 DMG | 4 DMG | — |
| Sunder Strike | 2 DMG | 2 DMG | Stance-neutral; places a stacking Sunder token (+DMG/stack) |
| Execute | 3 DMG, unconditional | 6 DMG if mob HP ≤ 50%, else 3 DMG | Never illegal to play in either stance — Champion's bonus is conditional, not the play itself |
| Rally Blow | 2 DMG / 4 Block | 4 DMG / 2 Block | Full value swap, not a small delta |
| Shield Wall | 6 Block | 3 Block | — |
| Brace | — | — | **Reactive, stance-neutral.** Effect depends on the *previous round's* card: if it was pure-Block, Brace deals 4 DMG; if pure-DMG, Brace grants 4 Block; if it was both (only Rally Blow qualifies), player's choice. No effect if played first (nothing to react to). |

**Diagnostics rerun against v2:**

| Metric | v1 | v2 |
|---|---|---|
| Flip strictly needed | 8.6% | **40.6%** |
| Weakest card usage | Brace, 11.4% | Shield Wall, 23.4% |
| Usage spread | 11–71% | 23–78% (tighter) |
| Dead cards | none | none |

Both diagnosed v1 problems fixed by giving stance real teeth (bigger, per-stance value
swaps instead of small deltas) and turning the weak defense card into something whose
value comes from sequencing rather than a static number.

## Mob intent patterns

Mobs have a fixed, fully visible 3-round intent pattern (ATK, and optionally some Block
that reduces the Warrior's damage output that round) — no hidden information, no dice.
Five first-draft archetypes tested:

- **Standard Grunt** — 4 / 4 / 6 (flat aggression, enrage close)
- **Defensive Brute** — 4 / 4+block3 / 6
- **Turtle then Burst** — 3+block4 / 4+block2 / 8
- **Glass Cannon** — 7 / 5 / 3 (front-loaded, fading)
- **Sustained Pressure** — 5 / 5 / 5 (flat, no shape at all)

None of these have real HP values locked yet — see Open Questions.

## Finding: the win-rate cliff, and the mobs-vs-cards lesson

Scanning win rate against mob HP for Standard Grunt didn't produce a smooth curve — it
jumped straight from 100% (HP ≤ 8) to 80% (HP 9–12), with nothing near 90% achievable at
all. Tracing every hand's individual "max beatable HP" showed why: across all 15 hands,
only **3 distinct breakpoints exist** (8, 12, 14), and which tier a hand falls into is
almost entirely determined by whether it holds Rally Blow and/or Execute — the two
highest-damage cards. Against a mob with zero Block, damage ceiling is the only axis that
matters, so hands collapse onto just those two cards' presence/absence.

Checking the same thing against Defensive Brute (same kit, but the mob blocks in round 2)
showed **4 tiers, packed tightly** (7, 8, 9, 10) instead of 3 widely-spaced ones. Adding
a mob-side Block pulls a second axis (timing/sequencing around the block) into relevance,
so more of a hand's specific composition matters, not just its two best attackers.

**Conclusion: mob variety is the right lever for smoothing difficulty, not card
rebalancing.** Flattening Rally Blow/Execute's damage lead would smooth the curve too,
but at the cost of erasing the exact identity difference the v2 rework just established.
Mobs with *some* Block or timing wrinkle in at least one round pull the kit's other axes
(Block, sequencing, stance) into relevance for free.

## What this loses versus the AGGRO-scale translation

- **Ranged vs melee / Engagement.** The flat "mob does Attack X, sometimes Block Y" model
  has no `mob_type` dimension at all. Not a loss for Warrior specifically — none of its
  AGGRO-scale cards ever referenced mob type. It **is** a real problem for Wizard, whose
  AGGRO-scale identity leaned on exactly this axis (Snap Freeze's `evades_melee`, Wall of
  Ice/Ice Barricade's Untargetable, Confound's Incapacitate). Needs a decision before
  Wizard gets condensed — likely reintroducing a `mob_type` tag on mobs even in this
  simpler model.
- **The old stance "combo within a subset played same round" texture.** Guardian/Champion
  used to reward playing multiple synergistic cards together in one round under an Energy
  budget. That structure doesn't exist anymore (one card per round), so stance was
  reframed as a timing/commitment choice across the whole sequence instead. Different
  mechanic, not a strict downgrade, but genuinely different from the original.

## Wizard kit (built)

No Stance system — that was always Warrior-specific (tied to Vanguard in the source kit),
not a universal mechanic. Wizard's second decision layer is **positioning timing** instead:
when you spend your Range-granting cards against a known mob pattern does the same job
stance-timing does for Warrior. Resolved open question #2 (below) in favor of the
Block-like model: positioning is **per-round, granted fresh by whichever card you play**,
not a persistent state — reuses the AGGRO-scale `evades_melee` logic exactly (conditional
on `mob_type == "melee"`), just re-hosted in the condensed round-by-round model instead of
inventing a new stance-like mechanic.

Also added **Spellweave**, a repurposing of AGGRO's Spellweaving mechanic (which doesn't
translate directly — it relied on chaining Instants before Casts within one round, and
condensed combat has no within-round multi-card play). Spellweave instead rewards cross-round
sequencing: playing a Spellweave-tagged card arms a single-use trigger; the *next* eligible
payoff card played consumes it for a bonus. Does not stack — a second Spellweave source only
re-arms the trigger for a future payoff, it doesn't double up on the current one.

| Card | Effect | Notes |
|---|---|---|
| Fire Blast | 3 DMG | Spellweave source |
| Arcane Volley | 6 DMG, 8 if consuming an armed Spellweave trigger | Payoff |
| Snap Freeze | 1 DMG + grants At Range this round | Spellweave source; positioning |
| Ice Barricade | 10 Block | No Spellweave/positioning interaction — pure flat defense |
| Fire Ball | 5 DMG, 7 if consuming Spellweave | Payoff |
| Frozen Shot | 2 DMG + grants At Range, 4 DMG if consuming Spellweave | Payoff; positioning |

Implemented in `condensed_wizard.py`, same exact-enumeration solver approach as Warrior
(no stance dimension to search, so actually simpler — just hand × ordering).

## Multi-pull trip simulator (`condensed_trip.py`)

Chains pulls together with **no recovery between them** (testing the no-Food theory
directly): HP carries forward pull to pull, each pull draws a fresh random hand (deck
resets every pull), and the trip ends when HP would hit 0. Reuses each class's
`best_line_for_hand` with a `starting_hp` parameter threaded through — since more HP now
is never worse for the future in this model, the per-pull-optimal choice is also the
multi-pull-optimal one for a *fixed* hand, no extra lookahead needed (but see the HP note
under Open Questions — the *value* of winning vs surviving is genuinely HP-dependent in a
way that isn't just "more HP is better," addressed there).

**Finding: baseline numbers came in far short of the "several pulls without Food" goal.**
Both classes averaged under 3 total pulls before HP hit 0, and under 1.3 of those were
actual wins — Warrior's average HP cost per win (~10.9, later ~18.5 against a harder mob)
was close to or exceeding its *entire* max HP (18), meaning it could barely afford one win
before needing Food.

**Finding: DMG is a stronger lever than mitigation for pulls-completed, not just a
slightly-better one.** A/B test on Warrior: +25% DMG raised wins-before-Food by +67%
(0.97 → 1.62); +25% Block raised it by only +4% (0.97 → 1.01), despite Block extending raw
survival *time* slightly more (+34% pulls vs DMG's +20%). Reason: nearly every mob pattern
tested escalates (hardest round last), so killing faster doesn't just reduce exposure
linearly, it specifically skips the worst round. Block only ever saves a flat amount per
round it's used — real, but not compounding the way "the round never happens" does. This
result is pattern-dependent, not a universal law — it would weaken or reverse against a
flat or front-loaded mob.

**Finding: Warrior and Wizard were not equally behind.** Wizard (max HP 10) averaged 1.29
wins before Food vs Warrior's (max HP 18) 0.97 — about a third more, despite half the HP
pool. Cost-per-win as a fraction of max HP: Warrior ~18.5/18 (essentially its whole pool),
Wizard ~7.8/10 (~78%). Ties back to the earlier single-pull finding that Wizard finishes
wins with a higher fraction of HP intact (47.3% vs Warrior's 39.6%) — its kit is more
efficient per card play since Snap Freeze/Frozen Shot bundle damage and defense into one
card slot, where Warrior's Block always costs a dedicated card.

## Mob roster must be class-agnostic (hard rule)

**Never tune mob stats or patterns per-class.** Any hero can conceivably attack any mob,
so the roster has to be one shared set of numbers, not per-class variants — this was
floated as one of several brainstormed levers for closing the Warrior/Wizard gap and
explicitly rejected. See `[[feedback-mob-roster-class-agnostic]]` in the memory system.
Class balance has to come from hero kits or from roster-wide adjustments that hit every
class identically, never from quietly making one class's mobs easier.

## Mob roster iteration

Started from the original 5 archetypes above (still untuned at the time), then iterated
under the class-agnostic constraint:

1. **First revision** — uniform −1 ATK across every round, +1 Block on every round that
   had none. Result: raw survival time jumped a lot (Warrior pulls-before-Food +42%), but
   **wins barely moved (-3%)**. Root cause: "mob Block" has always meant *reduces the
   hero's damage output that round* (not mitigation of incoming damage) — spreading it
   across every round made every kill slower, which increases total rounds of exposure
   even though each individual round hits softer. Adding Block and lowering ATK were
   pulling in opposite directions for the wins-per-trip goal, bundled into one edit.
2. **Second revision** — stripped the scattered +1s, kept only the substantive Block
   values already present (Defensive Brute round 2, Turtle-then-Burst rounds 1–2), and
   gave the two mobs that would've had zero Block anywhere a real value in exactly one
   round each (Standard Grunt: 3 Block round 2; Glass Cannon: 2 Block round 1, its biggest
   round). Sustained Pressure kept as the one deliberate pure-race outlier — that was its
   original design intent. Result: wins up substantially for both classes (Warrior +51%,
   Wizard +36% vs the original roster), confirming it was Block *density* (every round)
   that hurt, not Block's existence.

Current 5-mob state (in `condensed_trip.py`):

| Mob | Round 1 | Round 2 | Round 3 | HP |
|---|---|---|---|---|
| Standard Grunt | 3/0 | 3/1 | 5/0 | 9 |
| Defensive Brute | 3/0 | 3/3 | 5/0 | 8 |
| Turtle then Burst | 2/4 | 3/2 | 6/0 | 6 |
| Glass Cannon | 6/2 | 4/0 | 2/0 | 9 |
| Sustained Pressure (deliberate pure race) | 4/0 | 4/0 | 4/0 | 9 |

## Backward-designed mobs: working from the target instead of the roster

Given the goal directly ("design a mob that wins ~90% and lets each class complete 3–5
pulls before Food"), searched mob HP/pattern space per class independently as a
*diagnostic* (not a proposal to violate the class-agnostic rule — see below), landing on:

| | Pattern | HP | Single-pull win% | Avg wins before Food |
|---|---|---|---|---|
| Warrior's derived mob | 2/1, 2/1, 3/0 | 7 | 93.3% (closest tier to 90%) | 3.73 |
| Wizard's derived mob | 1/0, 2/1, 3/0 | 9 | 93.3% | 3.81 |

Both landed close to each other despite being tuned independently, and both are
**substantially weaker than anything in the current 5-mob roster** — hitting "3–5 pulls
without Food" isn't a small nudge from where the roster stood, it needs roughly half the
threat level. These two became the anchor points for the 8-mob roster below (renamed
Grunt and Skirmisher).

## Mob damage on the kill round (rule, decided)

Question: if a hero's damage this round kills the mob, does the mob still land its attack
that same round, or does the kill interrupt it?

**Decision: the mob still acts — no interrupt.** Tested both ways directly:

| | Single-pull win rate | Multi-pull avg wins before Food |
|---|---|---|
| Current rule (mob still hits) | 93.3% (both anchor mobs) | Warrior 3.73, Wizard 3.81 |
| Kill interrupts mob | 93.3% (unchanged) | **Warrior 11.96, Wizard 18.99** |

Single-pull win rate never changes (the only losses in both anchor mobs are timeouts, not
death-races), but multi-pull performance explodes 3–5x under the interrupt rule — most of
the per-pull HP cost was coming specifically from "the mob's last hit still lands even as
it dies," not from the rounds where the fight was genuinely contested. Kept the no-interrupt
rule for two reasons: **thematically**, mob intent is a fixed, fully-known script — making
it conditional on the hero's own success mid-round cracks that determinism. **Strategically**,
it preserves a real decision ("do I have enough to finish this round, and is it worth the
exposure") instead of making "go for the kill" unconditionally correct whenever available.
If the actual goal were specifically "make multi-pull trips much easier without touching
any card kit," the interrupt rule is a legitimate one-line lever — but the roster would need
retuning meaningfully harder to land back on the same single-pull target.

Checked whether "kill order round" analysis reveals anything about round-ending
distribution too: for the Warrior anchor mob, all 15 hands' optimal lines run the full 3
rounds (no hand bursts it down early); for the Wizard anchor mob, 9/15 finish by round 2
(when Spellweave lines up with a payoff card) and 6/15 need round 3. Neither anchor mob's
single loss turned out to be a near-death race — both are clean timeouts where the losing
hand simply lacked its kit's biggest damage cards.

## Final 8-mob roster (draft, class-agnostic)

Generated as intentional variants around the two anchor mobs — some front-loaded, some
back-loaded, some flat, spanning trivial to genuinely hard:

| Mob | Pattern | HP | Warrior win% / trip | Wizard win% / trip |
|---|---|---|---|---|
| Whelp | 2/0, 1/0, 1/0 | 4 | 100% / 42.5 | 100% / 15.6 |
| Grunt (Warrior anchor) | 2/1, 2/1, 3/0 | 7 | 93.3% / 3.73 | 93.3% / 3.24 |
| Skirmisher (Wizard anchor) | 1/0, 2/1, 3/0 | 9 | 80.0% / 3.58 | 93.3% / 3.81 |
| Ambusher (front-loaded) | 4/0, 2/1, 1/0 | 8 | 93.3% / 4.30 | 93.3% / 6.03 |
| Sentinel (Block-heavy, low ATK) | 1/2, 1/2, 2/1 | 6 | 80.0% / 5.78 | 93.3% / 6.20 |
| Brute (hard tier) | 2/1, 3/1, 5/0 | 10 | 80.0% / 1.44 | 73.3% / 1.00 |
| Elite (hard tier) | 3/0, 3/0, 5/0 | 12 | 80.0% / 1.33 | 66.7% / 0.91 |
| Champion (hardest, spike content) | 3/1, 4/1, 5/0 | 9 | 80.0% / 0.99 | 86.7% / 1.09 |

First draft of Champion (3/1, 4/1, 6/0 HP 13) came back at a literal **0% win rate for
both classes** — flagged and retuned rather than left in, since "unwinnable" and "hardest"
aren't the same thing. Brute/Elite/Champion are intentionally *not* meant to be pulled
repeatedly (sub-1.5 wins-before-Food) — they're spike/checkpoint encounters, not part of
the repeatable-farming loop the other five serve.

## Design research: comparable games and what to steal

- **Slay the Spire** — almost certainly the unstated parent influence already, via AGGRO.
  Its real contribution is the visible-intent icon convention (attack/block/buff shown as
  a glyph, not a number to re-derive every time) — worth stealing directly for
  communicating a mob's round-by-round pattern at the table without a wall of text.
- **Marvel Champions / Arkham Horror LCG's villain "scheme" decks** — escalating threat is
  a *known countdown* the player is racing, and it's presented as a physical, filling
  track rather than a silent rule. Worth stealing the presentation, since QUEST's
  round-3-flee cutoff is mechanically the same idea but currently has no equivalent
  physical tell.
- **Mario & Luigi / Paper Mario boss fights** — validates the small-deck bet directly: a
  tiny, fixed toolkit against many distinct, telegraphed boss patterns, where skill is
  pattern recognition and correct application rather than raw option count. Also a lesson
  in giving each mob archetype (Sentinel, Ambusher, etc.) a recognizable identity by
  silhouette/theme, not just backend numbers.

## Reflection: is this actually a good puzzle, and does it feel like combat?

Real measured evidence of decision depth (13/15 hands need distinct lines across mobs,
stance-flip load-bearing in 40% of wins, no dead cards, state space small enough to be
human-tractable but not trivially obvious) supports **yes, these are genuine, well-sized
tactical puzzles**, not complexity theater.

**Does it feel like combat, though — honestly, no, and that's probably the correct
outcome given the stated design pillars.** A fully deterministic, exactly-solvable system
doesn't produce the momentum swings or "oh shit" moments dice or hidden information do —
this reads as a tactical puzzle wearing combat's skin, closer to a tight logic problem
than a visceral fight. Given "no dice, carrots not sticks, combat as a toll-check not the
main event," that's consistent with the goal, not a failure of it — the macro trip-planning
loop is supposed to carry the emotional weight, this is supposed to be a fast, legible gate.

## Reflection: memorization risk, properly quantified

Initial concern ("15 hands is a small, memorizable space") was too narrow — revised down
significantly after computing the real scale. The actual unit of memorization is (hand,
mob) pairs, not hands alone: 15 hands × 8 mobs = 120 situations per class; × a possible
9 classes with non-transferable decks = ~1,080 across the whole game, growing further as
the roster grows past 8 mobs. Realistic repeat-exposure per exact situation (even for a
dedicated player doing ~500 pulls) works out to only 2–4 repeats each — not enough for
rote recall, more likely to produce genuine heuristic intuition, which is the desirable
kind of mastery, not a design flaw.

**A sharper version of the same pushback turned out to be correct, though — starting HP
is a hidden third variable that breaks simple (hand, mob) memorization entirely.** Proven
directly: same hand, same mob (6 HP, pattern 1/0-2/1-3/0), the solver's actual optimal
*sequence* changes depending on starting HP, not just the outcome —

| Starting HP | Best sequence | Result |
|---|---|---|
| 3 | Rally Blow → Sunder Strike → Execute | Loss (best possible) |
| 5+ | Rally Blow → **Brace** → Sunder Strike | Win |

A "memorized answer" would need to be keyed on (hand, mob, current HP), and HP is
continuous and shaped by entire trip history, not a small discrete set like hands or mobs
— this doesn't just enlarge the memorization table, it changes what's being memorized from
a static lookup into something that has to be reasoned about live. Also clarifies where
the game's actual tension lives: mob selection and the hand draw are where real
uncertainty exists; once the hand is down, the skill is reading current HP against a known
target and knowing when to abandon the "efficient" line for the survival line — exactly
the judgment a lookup table can't shortcut.

Related, resolved finding: searched directly for cases where deliberately giving up on a
winning line (accepting a timeout) would preserve more HP than the best available winning
line for the same hand — found **zero cases**, across a full HP sweep against two mobs
including a deliberately harsh one. Structural reason: winning ends the pull immediately
(mob stops attacking), while timing out guarantees enduring all 3 rounds regardless of how
defensively you play — so "kill it, even at a real cost" almost always beats "give up and
survive," because giving up doesn't reduce total exposure, it guarantees experiencing all
of it. (It *is* possible to construct a mob where going for a kill is fatal while playing
safe survives — did so deliberately — but because the system has no dice, that "risk" is
never actually uncertain: the solver, or any sufficiently careful player with the pattern
visible, simply never picks the fatal line. The genuinely uncertain version of "is it worth
the risk" can only live one level up, at the trip-planning layer — whether to pull again at
all before seeing the hand — not inside an already-fully-known single fight.)

## Paladin kit (built)

Fourth class, built after Warrior/Wizard/Cleric were locked, using `CLASS_BALANCE_GUIDE.md`'s
methodology end to end — the first real test of whether that guide actually works on a class
it wasn't written from.

**Source verification.** AGGRO's real level-1 Paladin kit (10 cards) was pulled directly from
`StS_WoW_Sim/data/cards.csv` and `StS_x_WoW_Classes_v7_4.md`, spot-checked line-by-line against
the raw CSV rather than trusted from a research-agent summary alone — the summary's citations
turned out mostly accurate, but flagged one real discrepancy: Invocation's CSV numeric
`dmg`/`heal` columns (4.5/2.0) don't match its own rules text ("Deal 2 DMG", no heal), most
likely a derived balance-tool column rather than the literal card stat. Used the rules text as
ground truth, consistent with every other card. Worth remembering for future source-pulls: spot
check the raw file yourself for at least the load-bearing cards, don't take a research agent's
citations fully on faith even when they look precise.

**Mechanic redesign, mid-build.** The original design note above (still accurate for the
*first* version) specified three cards: two Virtue-Attacks plus a separate shared Invocation
card, restricted to one Virtue ever active per pull. Iterating with real numbers in hand, this
collapsed to **two self-contained cards** — Invocation of Sanctuary, Invocation of Grace — each
folding setup, payoff, and finisher into one card instead of spreading it across three. Final
locked text:

> **Invocation of Sanctuary** — On Play: Deal 3 DMG, +1 DMG per STRIKE card already played this
> pull. If no Invocation has been played yet this pull, this becomes your Active Invocation:
> STRIKE cards played after it gain +1 DMG for the rest of the pull.
>
> **Invocation of Grace** — same shape, +1 Heal instead of +1 DMG, both the retroactive and the
> forward-looking half.

The load-bearing clause, clarified explicitly after an early ambiguity: **only the first
Invocation played each pull gets any bonus at all — the second one played is flat base damage
only** (3 for Sanctuary, its own separate base for Grace), no retroactive credit, does not
become Active. Not "only one is playable" (the original three-card design's rule) — both are
always legal, but the mechanic itself makes the second one weak, a softer and more flexible
exclusivity than a hard legality restriction. Worth the explicit callout: a state-dependent
mechanic like this needs its exact boundary condition ("first vs. second," not just "is one
active") stated in so many words before implementing — an early draft implicitly assumed the
second Invocation also got the retroactive bonus, silently double-counting value versus what was
actually intended, and it wasn't caught until manually traced round-by-round against a real hand.

**6-card kit, freed slot spent on real texture.** Folding Invocation from 3 cards to 2 opened a
4th slot beyond the original 3-card proposal (Might of the Aegis, Bastion's Hammer, Sacred
Light). Filled with **Holy Fortress**, simplified from AGGRO's real charge/reactive-damage
sub-mechanic to a flat dmg+block card for this first pass (a second layer of state on top of a
brand-new mechanic was too much for a first pass; revisit if Paladin gets an upgrade tier, same
treatment as the deferred third Virtue below). Aura of Sanctuary and Holy Renewal stayed cut —
Aura's "End of Hero Phase, allied heroes in your zone" clauses don't map onto a solo, round-based
pull at all, and Holy Renewal reads as a second, redundant Cleric-style heal next to Sacred
Light rather than adding real texture.

**Numeric iteration, in order:**
1. First-pass support-card numbers derived from the per-round economy formula (see
   `CLASS_BALANCE_GUIDE.md`) — landed the aggregate mitigation in the right ballpark, but damage
   floor came in at 5 (half of every other class's 8-10), because the formula only targets an
   *average*, not the worst-case hand.
2. Redesigning Invocation from 3 cards to 2 (above) mechanically fixed part of this for free —
   floor moved 5→8 — because a strikeless hand could now double-dip both Invocations' base
   damage instead of being stuck on one.
3. Damage ceiling still trailed the other three classes (10 vs. their 14-16) until Bastion's
   Hammer was bumped to 6 — the single biggest lever in the kit, since it's the card most first
   floor-and-ceiling checks kept landing on.
4. Separately, a hand-level check (not caught by the floor/ceiling average) found **8 of 15
   possible hands were mathematically incapable of killing Brute or Elite at all**, regardless of
   play — every one missing at least one of the two STRIKE cards, since only two exist in the
   whole 6-card deck. Fixed via Bastion's Hammer (again) and an asymmetric bump to Invocation of
   Grace specifically (not Sanctuary) — Grace's bonus is healing, not damage, so a Grace-heavy
   hand is *structurally* weaker at closing out a kill than a Sanctuary-heavy hand in the same
   slots; that's supposed to be true (it's the class's whole heal/damage identity split), so the
   fix targeted Grace's own base damage only, not its signature heal-per-strike bonus. Brought
   the unwinnable-hand count down to 3/15.
5. This overshot: Paladin became the single strongest class on the mixed-roster aggregate (3.56
   wins vs. Warrior's 3.02) and re-inflated the same "dominates the easiest mob" pattern found
   earlier with Warrior. Dialed back with two levers tested independently and combined: Sacred
   Light's heal (4→3) and `PALADIN_HP` (18→17). The heal cut did almost all the work on the
   Whelp-dominance specifically (-3.33 wins) while the HP cut barely touched it (-0.77) — the two
   levers aren't redundant, heal cuts "healing outpaces trivial content," HP is a smaller uniform
   tax across the whole roster. Combined, landed at 3.03 mixed-roster wins — an exact tie with
   Warrior's 3.02 — and the Whelp outlier normalized from towering above every other class to
   sitting between Cleric and Warrior where it belongs.

**Final locked kit:**

| Card | dmg | block | heal | mechanic |
|---|---|---|---|---|
| Might of the Aegis | 4 | 2 | — | STRIKE |
| Bastion's Hammer | 6 | 0 | — | STRIKE |
| Sacred Light | 0 | 0 | 3 | plain heal |
| Holy Fortress | 2 | 4 | — | plain block+dmg |
| Invocation of Sanctuary | 3 base | — | — | see mechanic text above |
| Invocation of Grace | 4 base | — | — | see mechanic text above |

`PALADIN_HP = 17`.

**Formula validation, after the fact.** Once locked, the final kit's per-round economy
(raw incoming dmg 3.32/round, total mitigation 1.65/round, net -1.67/round) landed almost dead
center of the ~1.57-1.81 mitigation band the other three classes established — despite the
actual path to those numbers being driven by hand-level bug fixes, not the formula directly. The
formula predicts the right neighborhood fast; it doesn't replace the hand-level floor/ceiling and
kill-feasibility checks that caught the real bugs (the formula would never have surfaced "8/15
hands can't kill Brute" on its own, since that's about distribution across specific hands, not an
average). Use both, in that order — formula for a fast first draft, hand-level checks for what
actually ships.

**Interactive engine.** Deferred until numbers were locked (verified against the source module
via 120 cross-checks, same as every other class), then added to `playtest_engine.py` with zero
template changes needed — `setup.html`'s class dropdown and `game.html`'s card rendering are
both fully generic over whatever's registered in `CARD_SOURCE`. The mechanic-tag pattern
(live "-- ACTIVE this round" suffixes, already used for Wizard's Spellweave and Warrior's
Vanguard combo) extended cleanly to a genuinely novel mechanic shape with no precedent in the
other three classes — confirms the tag pattern generalizes, not just the numeric interface.

**Known limitation, deferred not solved:** AGGRO's real Paladin gets a third Virtue at Level 2.
Same wall as Warrior's Frenzy — a physical card only has two sides, so a genuine third option
can't live in this trick once it exists. Fine for a first/base kit; will need its own answer
whenever Paladin gets an upgrade tier, same as Holy Fortress's simplified reactive mechanic
above.

## Cleric kit (built, damage-floor problem resolved)

Third axis is **Heal** — resolves before the mob acts (same timing slot as Block/Positioning),
capped at max HP (no overhealing banked forward), and unlike Block/Positioning it isn't tied
to a specific round's threat — any "excess" persists as a real buffer for whatever round
tests it next.

**The problem, found by measuring best-possible 3-round damage per hand (both the best hand
and the worst hand's ceiling) across all three classes:**

| | Ceiling (best hand) | Floor (worst hand) |
|---|---|---|
| Warrior | 14 | 7 |
| Wizard | 16 | 8 |
| Cleric (first draft) | 10 | **2** |

(Warrior's numbers here were corrected after an initial pass wrongly suppressed Execute's
Champion-stance wounded bonus — the first calculation used a fixed dummy mob HP high enough
that Execute's "mob ≤ 50%" condition could never trigger, understating both its ceiling and
floor. Wizard and Cleric were unaffected, since neither has a mechanic that depends on the
mob's actual remaining HP the way Execute does.)

Root cause: Warrior and Wizard each have 5 of 6 cards capable of dealing some damage;
Cleric's first draft had only 3 of 6 (Heal, Blessed Barrier, Blessed Fortitude were pure
0-damage support). With only 3 non-damage cards in the deck and a 4-card hand, "all 3
support cards + weakest attack" is a real, unavoidable draw, not an edge case.

**Fix, verified against all 15 hands:** reworked Sacred Balance from a stacking modifier
into a **binary ON/OFF state** — still card-only, no token, same family as Sunder/Spellweave.
Setup cards arm it; Payoff cards consume it for bonus damage *in addition to* their normal
effect (not a trade-off — Heal still heals its full value even when the bonus fires).

| Card | Effect |
|---|---|
| Void Mark | 2 DMG. Setup — arms Sacred Balance. |
| Blessed Fortitude | +2 Max HP, Heal 2. Setup — arms Sacred Balance. |
| Heal | Heal 6. Payoff — if Sacred Balance is ON, also deal 5 DMG, then turn it OFF. |
| Blessed Barrier | 4 Block. Payoff — if Sacred Balance is ON, also deal 5 DMG, then turn it OFF. |
| Smite | 3 DMG, 3 heal. No Sacred Balance interaction. |
| Call of the Void | 5 DMG, 2 heal. No Sacred Balance interaction. |

This closes the structural gap directly rather than just inflating flat numbers — Heal and
Blessed Barrier become *conditionally* capable of damage, bringing Cleric to 5-of-6
damage-capable cards, matching Warrior and Wizard. The 5-DMG payload (rather than buffing
Void Mark's base damage instead, which tests as mathematically identical) was chosen
deliberately: keeps Void Mark as the humble unconditional poke it's meant to be, and puts
the reward specifically on successful sequencing rather than a flat card buff.

**Result:**

| | Ceiling | Floor |
|---|---|---|
| Warrior | 14 | 7 |
| Wizard | 16 | 8 |
| **Cleric (fixed)** | **12** | **7** |

Floor now *ties* Warrior's (corrected) floor exactly and sits close to Wizard's; ceiling is
between the two. Lands cleanly on the actual design target too — 7 damage from the single
worst possible hand, against the 7 HP Grunt anchor mob, played perfectly. Not pure DPS: the
fix works by making *support* cards conditionally capable of damage rather than adding new
dedicated attack cards, and the burst only exists because support infrastructure (a Setup
card) got played first — reinforces the healer identity rather than competing with it.

## Finding: Cleric's healing created a "cannot die" equilibrium (found and fixed)

Running all three classes against the full 8-mob roster (not just isolated single-mob
tests) surfaced something none of the earlier per-mob checks caught: Cleric was hitting a
50-pull safety cap against five of the eight mobs in the multi-pull trip test — not just
performing well, literally never dying within the test horizon.

Diagnosed by checking net HP change per pull at a range of *starting* HP values (not just
from full health) against Grunt: at HP=12 it lost ~2.4/pull, but at HP=8 and below it
*gained* HP on average, drifting back up toward an equilibrium around HP≈9. Confirmed this
was categorically different from an expected "very easy mob, dies slowly" case (like
Warrior's ~43-pull average against Whelp) by checking Warrior's own curve against the same
mob — a flat −0.40/pull at *every* HP level, a genuine slow decline toward death, not an
equilibrium. Cleric's problem was structural: Heal's flat value (6, against a 12-HP pool)
combined with incidental heals on Smite/Call of the Void/Blessed Fortitude simply
outpaced what the weaker mobs in the roster could ever deal.

**Fix, verified by grid search rather than guessing at one card:** searched combinations of
cuts to Heal's value, Smite's heal, Call of the Void's heal, and Blessed Barrier's Block,
looking for the smallest total cut that broke the equilibrium against Grunt. Found: Heal
6→4, Smite's heal 3→1, Call of the Void's heal 2→1, **Blessed Barrier's Block needed no
change at all**. Spreading the cut across three cards instead of gutting Heal alone avoided
a new problem — reducing Heal in isolation to the value needed (1) would have made it worse
at pure healing than Smite's incidental heal, an odd place for a card named "Heal" to land.
Confirmed the damage-floor fix from the previous pass was untouched (still 12/7 ceiling/floor
— Sacred Balance's damage bonus lives in a separate field from heal amount).

That fixed Grunt, but the full 8-mob sweep afterward showed the same bug persisting,
smaller, against Whelp and Sentinel (both very low-ATK mobs, ≤2/round) even after the card
nerf, and a subtler version against Skirmisher/Ambusher — not hitting the 50-cap, but still
showing a positive equilibrium right at HP=1 (hovering near-death forever instead of either
dying or comfortably surviving). Rather than cutting Cleric's cards further (risking
re-breaking Grunt or the damage floor), fixed these on the **mob** side instead: a uniform
+2 ATK/round bump on Whelp and Sentinel, +1 on Skirmisher and Ambusher. Verified this had
**zero effect on Warrior or Wizard's win rates** at every mob before locking it in — the
bump was small enough to only tip Cleric's specific equilibrium, not the other two classes'
already-correct numbers.

**Final verified state (`condensed_trip.py`, `condensed_cleric.py`):** swept all 8 mobs
checking for a genuine decline at every starting HP level (12, 8, 4, 1) for Cleric — all 8
confirmed clean, no remaining equilibrium anywhere in the roster. Mixed-roster multi-pull
averages now land close together across all three classes (Warrior 4.57 pulls/2.19 wins,
Wizard 3.87/2.04, Cleric 4.56/2.10) instead of Cleric being a wild outlier.

**Methodology note worth keeping**: this bug was invisible to every test done up to this
point (single-pull win rate, isolated damage-floor checks, even the first multi-pull test
against one mob at a time) because "average pulls before Food" alone doesn't distinguish a
genuine slow decline from a stable equilibrium — both produce a high number. The check that
actually caught it was scanning net HP change across a *range* of starting HP values and
confirming the sign never flips. Worth running that specific check on any future
healing-capable class before trusting its multi-pull numbers.

## External review: Gemini puzzle-quality critique, tested empirically

Asked Gemini for an independent critique of puzzle quality (not correctness) across all
three built classes. It made five claims; rather than accept or dismiss them by feel, each
testable one was checked directly against the solvers.

- **"The unplayed card should often be a deceptively strong one, not just the weakest
  card"** — tested by tallying, across every hand × mob combination, which of the 4 drawn
  cards gets left out of the optimal 3-card line. Warrior: **Shield Wall (a strong 6/3
  Block card) is cut most often, 30.8%** — more than Execute or Sunder Strike, and Heavy
  Strike/Rally Blow are never cut at all. Real, favorable tension — the card a human would
  instinctively hold onto is often exactly the one the solver says to discard. Wizard:
  partial match (Ice Barricade, a strong 10-Block card, cut ~21% of the time). Cleric: weak
  match (Smite cut most, but see the domination finding below — that wasn't genuine
  tension, it was a bug).
- **"Mob timing should force setup cards out of their preferred round, not just card
  variety in general"** — tested by checking how often Warrior's Sunder Strike gets pushed
  past round 1, and *why*. It's delayed 41% of the time, but only 6 of those 23 cases
  (26%) are because round 1 was spent on genuine defense — the other 17 are attack-vs-attack
  sequencing (stance/Execute timing), not mob-forced disruption. Gemini's specific
  mechanism is real but a minor contributor, not the dominant one, in the current roster.
- **"Doesn't matter if this becomes rote/memorized, the low friction is the point (like
  Skyrim lockpicking)"** — tested directly by comparing solver-optimal play to a plausible
  "naive/rote" baseline (always play the 3 highest-raw-number cards, fixed stance, no
  sequencing thought) across all 120 Warrior hand×mob combinations. **Optimal play: 85.8%
  win rate. Naive play: 30.0%.** That gap is decisive evidence against the argument, not for
  it — if playing on autopilot triples your loss rate, the sequencing skill is real and
  worth exercising every time, which is the opposite of a mechanic where memorization would
  make engagement optional. (HP-left looked similar between the two, which is misleading —
  naive losses are mostly timeouts, not deaths, so it "looks" survivable while failing the
  actual objective.)

**Real regression found via the unplayed-card check, not by inspection:** Cleric's
domination-avoidance fix from before the equilibrium bug (Smite 3dmg/3heal vs Call of the
Void 5dmg/2heal, deliberately asymmetric) had been silently destroyed by the equilibrium
fix, which cut both cards' heal to the same value (1 each) — leaving Call of the Void
strictly better in every dimension. Fixing it by simply raising Smite's heal back up
reopens the equilibrium bug almost immediately (margin breaks at heal=1.5, against a
razor-thin −0.07 margin at heal=1) — the two fixes are in direct tension, not independently
solvable. Resolved by moving the asymmetry to Call of the Void instead: **Smite stays 3
DMG/1 heal, Call of the Void drops to 5 DMG/0 heal.** Verified clean against all 8 mobs
with no equilibrium regression. Honest caveat: this resolves *strict* domination (no card
is worse in every dimension now) but only modestly changes the practical unplayed-card
frequency (32.5% vs 33.3%) — a 1-point heal edge rarely outweighs 2 extra damage in the
solver's judgment, so Smite remains usually-but-not-always the worse pick. Correct
prioritization, not degenerate prioritization — the fix was worth making, but shouldn't be
oversold as having created dramatic new tension.

## Open questions

1. **Does draw-variance-only attrition actually hold up across a multi-pull trip?**
   Partially answered — it does produce real attrition (confirmed via the trip simulator),
   but the *magnitude* was far short of the "several pulls without Food" goal at baseline
   numbers, and the mob roster is still being tuned toward that target. Not fully resolved.
2. **Positioning: persistent state or per-round card-granted effect?** Resolved — built as
   per-round/card-granted, mirroring Block and the AGGRO-scale `evades_melee` tag exactly.
3. **What are Cleric's condensed axes?** Still undesigned — only Warrior and Wizard have
   built kits so far. Working theory unchanged: DMG + a little Block (precedented by
   Blessed Barrier) + healing/undoing damage after the fact.
4. **Cleric's out-of-combat heal** — exclusive to Cleric, or a smaller version for every
   class scaled by kit? Still open.
5. **Mob HP values** — resolved for the 8-mob draft roster above, but still first-draft,
   not stress-tested at the same depth as the two anchor mobs.
6. **Ranged vs melee for mobs beyond Wizard's own kit** — all 8 roster mobs are currently
   melee-only; no ranged mob has been built or tested against either class yet.
7. **Point 1 from the Gemini puzzle-quality review, not yet acted on:** mob timing
   currently only forces a setup card (Sunder Strike, and presumably Spellweave/Sacred
   Balance sources too) out of its preferred round 26% of the time it gets delayed — the
   rest is attack-vs-attack sequencing, not genuine mob-forced disruption. If deliberate
   "brutal round 1, nothing to block it with but your setup card" mob design is worth
   pursuing as a real depth lever (per Gemini's suggestion), it hasn't been built or tested
   yet — would need checking against the same constraint as every other mob change: zero
   disruption to Warrior/Wizard's already-calibrated win rates.
