# Deck Condensing Guide

How to turn an AGGRO class's ~10-card kit into a legal QUEST condensed-combat kit — exactly
6 unique cards, no Energy costs, one card played per round for 3 rounds (draw 4, sequence 3,
one card deliberately left unplayed). This is the step *before* balancing: get a kit that
legally fits the format and actually expresses the class's identity first, then hand off to
`CLASS_BALANCE_GUIDE.md` to tune the actual numbers. Extracted and generalized from how
Warrior, Wizard, Cleric, and Paladin were each actually built — see `CONDENSED_COMBAT.md`'s
per-class "kit (built)" sections for the real, warts-and-all history this is distilled from.

## Checkpoint discipline: this is a set of proposals, not a script to run unsupervised

Every class that actually exists in this project got there through **visible drafts and
revisions**, not one uninterrupted pass. Warrior's original v1 kit wasn't even a literal
AGGRO port — it got diagnosed (one card played in only 11.4% of winning lines), shown, and
reworked into v2 with a documented before/after. Paladin's Invocation mechanic is described
in its own build notes as arrived at by "iterating with real numbers in hand," and its exact
boundary condition (does the second copy played get a bonus or not) was ambiguous in an early
draft and only pinned down after being hand-traced against a real example. Cleric's kit
dropped a whole DOT mechanic between an early draft and the actual condensed build. The
through-line across all of them is checkpoints: draft, show it, get real pushback, revise.

**This guide describes what a good set of condensing decisions looks like. It does not
license running Steps 1-5 below start-to-finish, writing the module, and wiring it into
shared infrastructure (`condensed_trip.py`'s `CLASSES`/`MOBS`/lookup dicts) before anyone
else has seen a single decision.** A first real attempt at building a class this way (Rogue)
did exactly that — drafted every cut, every reframe, a brand-new scaling-resource mechanic,
and a starting HP value, wrote the full module, wired it permanently into shared code, ran
the full diagnostic suite, and only then reported it as a finished, validated result. Every
individual call might even have been defensible; the problem was that none of them were
shown before they hardened into code, on a project explicitly framed as design
*collaboration* (see `CLAUDE.md`: "push back on bad ideas... do not be a yes-man" — that cuts
both directions, an AI running solo for twenty steps isn't collaborating either).

**The actual rule:** after Steps 1-5 below produce a proposed cut/reframe list, any new
mechanic, and a starting HP guess — stop. Present the proposal (what's cut and why, what's
reframed and how, the mechanic shape, the HP starting point) before writing `condensed_<name>.py`,
and *definitely* before touching any shared file (`condensed_trip.py`'s `CLASSES`, `MOBS`,
or any `*_BY_LABEL` dict). Only implement after that's been discussed. The same applies again
at the handoff into `CLASS_BALANCE_GUIDE.md` — numeric tuning is still a design decision, not
just arithmetic, and it deserves the same checkpoint before locking anything in.

## Step 1: verify the source yourself, don't trust a summary

Pull the class's real AGGRO kit directly from `StS_WoW_Sim/data/cards.csv` (authoritative
stat values) and `StS_x_WoW_Classes_v7_4.md` (rules text), and spot-check the load-bearing
cards against the raw file yourself, even if a research agent already summarized it. A real
discrepancy was found this way on Paladin: Invocation's CSV numeric `dmg`/`heal` columns
didn't match its own rules text — most likely a derived balance-tool column, not the literal
card effect. When they disagree, **the rules text wins**, not the aggregated numeric column.
This isn't paranoia for its own sake — the research-agent summary was mostly accurate, one
real discrepancy was still found, and it was on a card that mattered.

## Step 2: what gets cut outright

- **Threat-only cards.** No shared aggro/targeting system exists in QUEST at all (that's the
  entire point of the prequel). Any card whose sole function is Threat manipulation has no
  QUEST equivalent — cut, not reworked.
- **Ally/zone/"End of Hero Phase" clauses with no solo-pull equivalent.** QUEST combat is one
  hero against one static mob, no party, no zones. A card whose whole function only makes
  sense with allies present (Paladin's Aura of Sanctuary) gets cut, not force-fit.
- **Cards that would just be a second, redundant instance of a kept card.** Paladin's Holy
  Renewal read as a second Cleric-style heal sitting right next to Sacred Light — cut for
  lack of distinct texture, not lack of power.
- **A class's Level-2+ AGGRO content.** A physical card only has two sides (dmg/block/heal
  values for the base kit) — there's no clean way to cram in a 3rd kit option some classes
  get at AGGRO's Level 2 (Paladin's third Virtue, Warrior's Frenzy). Defer explicitly to a
  future upgrade tier; don't force it into the base 6.
- **Overheal-generates-Threat clauses**, since Threat itself is gone — overhealing is still a
  wasted card, just not a mechanical penalty on top of that.

## Step 3: what gets reframed, not cut

Some AGGRO mechanics don't have a direct QUEST equivalent but clearly matter to the class's
identity — these get rebuilt in condensed-native terms rather than dropped:

- **Anything built on "play multiple cards in one round under an Energy budget."** AGGRO's
  Spellweaving (chain Instants before Casts, same round) and Stance-combo texture (multiple
  synergistic cards under one round's Energy) don't translate directly — condensed combat is
  one card per round, no within-round multi-card play. Rebuilt as **cross-round sequencing**
  instead: Wizard's Weave (playing a tagged card arms a single-use trigger; the *next*
  eligible payoff card consumes it) is the worked example. Stance itself got reframed the
  same way — from an in-round combo enabler into a timing/commitment choice made once per
  pull, held across all 3 rounds (see `CLASS_BALANCE_GUIDE.md`'s "Mob-dependent performance
  can be a feature" section for why locking it per-pull, not per-round, turned out to be
  correct rather than a downgrade).
- **AoE ("all mobs in your Zone") cards** — repurposed as bigger single-target hits, since
  there's only ever one mob to hit. Use AGGRO's own designer-note expected-value shorthand if
  one exists (e.g. "1 DMG × ~2 average targets" becomes a flat 2 DMG single-target card)
  rather than inventing a new number from scratch.
- **Positional/evasion tags** (`evades_melee`, Untargetable-style immunity). Don't assume
  these are cuttable just because there's no Zone system — check whether the class's
  identity actually leans on that axis first. Warrior's cards never referenced mob type, so
  dropping it cost nothing. Wizard's did (Snap Freeze, Ice Barricade, Confound all leaned on
  it), so a `mob_type` tag got reintroduced on mobs specifically to keep it. When reused,
  prefer the **per-round, granted-fresh-by-whichever-card-you-play** model over a persistent
  state — it re-hosts the original logic cleanly in a round-by-round structure instead of
  inventing a new stance-like mechanic on top of an existing one.

## Step 4: fitting exactly 6

If a mechanic's original AGGRO shape needs more physical cards than the budget allows,
collapse it — don't cut the mechanic, restructure it. Paladin's Invocation was originally
designed as 3 cards (two Virtue-Attacks plus a shared Invocation card); iterating with real
numbers in hand, it collapsed to **2 self-contained cards** (Invocation of Sanctuary /
Invocation of Grace), each simultaneously its own setup, payoff, and finisher instead of
spreading that across three slots. This freed a slot for real texture elsewhere in the kit
rather than a forced filler card.

**Whenever a fold-down like this creates a mechanic whose effect depends on prior state in
the pull** (does the second copy played get the same bonus as the first? does a buff persist
through what triggered it?) — state the exact boundary condition in one plain sentence and
confirm it before implementing, the same discipline `CLASS_BALANCE_GUIDE.md` documents in
detail ("State-dependent mechanics need their exact boundary stated, not implied"). This is
exactly the stage where that kind of ambiguity gets introduced — Paladin's "only the first
Invocation played gets any bonus, the second is flat base damage only" rule was only pinned
down after an early draft silently let both copies double-dip.

## Step 5: check the damage-capable-card ratio before calling the kit done

Count how many of the 6 final cards can deal damage under at least some condition. Warrior
and Wizard both land at 5-of-6. Cleric's first draft had only 3-of-6 (Heal, Blessed Barrier,
Blessed Fortitude were pure 0-damage support) — with a 4-card hand, "all 3 support cards +
the one weak attack" is a real, unavoidable draw, not an edge case, and it produced a
worst-hand damage floor of 2 against Warrior/Wizard's 7-8.

**The fix that worked preserved the healer identity instead of competing with it**: rework
support cards to be *conditionally* damage-capable via the same setup/payoff structure used
elsewhere (Cleric's Sacred Balance — a setup card arms it, a payoff card deals bonus damage
*in addition to* its normal heal/block effect, not a trade-off). This is preferable to
padding in a new dedicated attack card, which would just dilute the class's actual identity
to hit a ratio target. If a class's design genuinely wants fewer damage-capable cards than
5-of-6, that's a legitimate identity choice — but check the resulting worst-hand floor
directly (per `CLASS_BALANCE_GUIDE.md`'s hand-level kill-feasibility check) rather than
assuming a low ratio is fine because the average looks okay.

## Handoff

Once the proposal above has actually been discussed (see the checkpoint section up top —
don't skip it just because Step 5 passed) and the kit is legal (6 cards), cut/reframed
decisions are made deliberately, and every state-dependent mechanic has its boundary
condition pinned down in writing — the kit is ready for `CLASS_BALANCE_GUIDE.md`'s
methodology: implement the module interface, run the diagnostic tool chain in order, and tune
numbers against the locked mob roster. Don't skip straight to number-tuning on a kit that
hasn't been through the steps above — Cleric's damage-floor problem and Paladin's
unwinnable-hand problem were both *design*-stage gaps (missing damage-capable cards, a
mechanic structure that couldn't reach enough hands), not something a numeric pass alone
would have found or fixed. And the same checkpoint discipline applies again here: numeric
tuning is still a design decision, not just arithmetic — show significant swings before
locking them in, don't just report a final validated number.
