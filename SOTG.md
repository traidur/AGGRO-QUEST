# QUEST — State of the Game

*AI onboarding handoff. Read this before engaging with any QUEST design or balance question.
Not a rules reference — for the macro Town/Bag/Quest loop, read `MACRO_LOOP_GUIDE.md`; for
translating an AGGRO class's kit into a legal 6-card condensed kit, read
`DECK_CONDENSING_GUIDE.md`; for per-class card balance methodology (once that kit exists),
read `CLASS_BALANCE_GUIDE.md`; for undecided design tensions, read `OPEN_QUESTIONS.md`.
Modeled directly on AGGRO's own `sotg_vX_X.md` — same
job (prevent the specific mistakes a fresh AI keeps making on this project), same discipline
(narrow scope, not a comprehensive summary). Adapted with one addition AGGRO's version
doesn't need: QUEST's simulator *is* the primary design tool here, not a secondary
verification layer, so a short simulator-gotchas section is included below.*

## What QUEST actually is

Prequel/companion to AGGRO (a StS-x-WoW raid deckbuilder at `C:\Users\steph\StS_x_WoW`).
QUEST reuses AGGRO's classes/card economy but is a logistics engine-builder simulating MMO
questing/farming, not raid combat. Two layers: **per-pull combat** (a fast toll-check,
exact-enumeration solved — 6-card unique deck, 4-card hand, exactly 3 rounds, one card
drawn-but-unplayed each pull, no Energy cost, deck fully resets every pull, no RNG except
which 4-of-6 hand is drawn) and the **macro loop** (Town, Bag slots, Decaying Bounty quests,
Gold, trip chaining) — the macro loop is the real game; combat is the toll gating loot.

## Rules and decisions AI models get wrong on this project

1. **The mob roster is not what it used to be.** The old 11-mob hand-designed roster
   (Whelp/Grunt/Skirmisher/Ambusher/Sentinel/Brute/Elite/Champion/Footman/Marauder/Brawler)
   is retired. Current Standard tier is 6 mobs — **Grunt/Bruiser/Enforcer/Raider/Ambusher/
   Scout** — derived by brute-force search (`sim/stat_gauntlet.py`, `sim/pool_search.py`), not
   hand-designed. Scout is the first and only ranged mob; everything else is melee. Don't
   reference or resurrect the old names. Spike tier is empty/deferred.
2. **Mob stats must stay class-agnostic.** Never tune a mob's numbers to fix one class's
   matchup — any hero can face any mob. Per-class mob tuning was explicitly tried and
   rejected.
3. **"Average pulls survived" alone is not a valid balance metric.** Shown repeatedly to
   diverge from decay/death rate — a pool can look tightest on pulls-survived and not even
   be top-3 on decay. Always report both together, every time, no exceptions.
4. **No hidden conditional rules — flat, always-true printed numbers only.** A heal-cap-at-
   round-damage mechanic was tested, worked mathematically (closed ~88% of a real balance
   gap), and was explicitly rejected: *"it will not work in a board game."* Any future combat
   fix must be a simple printed number, not a rule a player has to remember to check.
5. **A numeric fix tuned against one mob pool does not generalize to another.** The same
   card change produced results ranging +15% to -7% across four different test pools. This
   is why exactly one Standard-tier pool is locked as canonical, rather than continuing to
   chase a number that works everywhere.
6. **Quest gold reward is not proportional to loot-count required.** It's derived from
   measured trip-cost (bigger quests barely cost more pulls, but disproportionately more
   trips) and self-decay fairness for players who finish quickly — not a hand-picked curve.
   Read `MACRO_LOOP_GUIDE.md` before proposing a new formula. XP *is* simply flat
   (1 XP per loot required) — that part was never the hard part.
7. **Warrior's stance is locked once per pull, no mid-pull flip.** Guardian or Champion is
   chosen at the start of a pull and held for all 3 rounds.
8. **`grants_range` evasion is no longer always-on.** Scout (Standard tier's 6th mob) is
   ranged — Wizard's and Ranger's evasion cards do nothing against it. Don't assume every
   mob is melee anymore; that assumption is stale as of Scout's addition.
9. **Full-information solvability (the simulator can brute-force the optimal line for a
   hand/mob pair) is not, by itself, evidence of a real tabletop fun problem.** Raised and
   walked back at least twice in this project's history: treating "a computer can exhaustively
   solve this" as inherently dangerous to player enjoyment, and reaching for mechanical
   countermeasures (forced randomness, hidden information) as a fix, doesn't hold up against
   real precedent — blackjack's basic strategy chart, poker hand-equity calculators, and
   decades of published chess opening theory are all fully or near-fully solved, and none of
   those games are considered broken for it. A player who brings a calculator to compute
   optimal play every round has opted out of the intended experience voluntarily; that isn't a
   design failure to defend against. The real, testable question is whether resolving a pull
   by feel, without a tool, feels satisfying to a normal player — a playtesting question, not
   something to preemptively engineer around with combinatorial scale or forced randomness.
   (Necromancer's Death Pact — since reworked from a random draw into a deterministic
   HP-for-damage trade, same name kept throughout, at the user's request over the "knowledge
   debt"/"simulation debt" it cost being the only card in the roster on a genuinely different
   rule — was a fine mechanic on its own merits either way; the point stands regardless of
   which specific card illustrates it.)
   **One real correction to the "small, memorizable space" framing, worth stating precisely
   instead of re-guessing it later: starting HP is a genuine third variable, not just hand and
   mob — the naive "15 hands x N mobs" count silently assumes full HP.** Checked directly
   (swept every integer starting HP for every hand/mob pair, Necromancer): the optimal line
   does shift with HP, but nowhere near once per HP value — mean 2.47 distinct optimal
   sequences per (hand, mob) pair across all 14 possible starting HPs, median 2.0, and some
   pairs use the exact same sequence at every HP from 1 to max with zero variation at all.
   Consistent with the already-locked flee-preference finding that HP shifts only flip which
   line is optimal near a specific threshold, not continuously. Real effect, real number to
   cite (roughly ~2.5x the naive count, not ~14x and not 1x) — but still nowhere near enough
   to change the conclusion above.

## Simulator gotchas

- A class module's `win_rate()` must resolve `starting_hp` from the live module constant
  *inside* the function body, never as the literal parameter default — Python evaluates
  defaults once at import time and silently ignores a later `X.CLASS_HP = N` reassignment.
  This bug existed in all the original classes and produced a wrong "no effect" finding
  before being caught. Any new class must follow the same pattern.
- `risk_only_as_last_resort` **defaults to True** everywhere in `macro_sim.py` — a pull only
  gets the higher risk tolerance if no unused consumable is available in the Bag.
- Eating Food mid-trip **closes the currently-open loot slot** (locks in progress on it, does
  not destroy it) while freeing Food's own slot — easy to get backwards.
- `NODES`'s old third tuple field (`loot_gold`) was dead code and has been removed. Gold
  comes entirely from `QUESTS[...]["gold_ladder"]`.
- **A macro-loop aggregate metric (`decay_report`'s deaths/run, `run_to_bag_upgrade`'s avg
  trips) is not a valid verdict on a damage-touching card change by itself.** A strictly-better
  card (more damage, nothing reduced) can make deaths/run go *up*, purely because the class
  finishes quests faster and reaches the risk policy's one gamble trigger more often — not
  because any fight got more dangerous. Always run `condensed_trip.py`'s `defense_floor_sweep`
  alongside it, or just call `macro_sim.py`'s `compare_card_change`, which runs both and prints
  the correct verdict. See `MACRO_LOOP_GUIDE.md`'s "Clean vs. aggregate metrics" for the
  incident this came from.
- **Necromancer no longer has any in-pull randomness.** Boneguard's Offering's Death Pact
  was reworked from its original random-draw rule into a flat, deterministic "may lose 4 HP
  to deal 3 extra damage" — same card name throughout, only the rule changed (don't call the
  new version "Life Tap"; that name was used briefly mid-rework and rejected as AGGRO/WoW
  source terminology already spoken for elsewhere). `win_rate`/`best_line_for_hand` need no
  special-casing for it now, same as every other class. `effective_win_rate` and
  `draw_random_card` no longer exist; don't reference them. If a future class ever needs
  genuine in-pull randomness again, the split-tooling approach that supported Death Pact's
  original draft is documented in `CLASS_BALANCE_GUIDE.md`'s "Necromancer, locked" section as
  a starting point, but weigh it against the exact complexity cost that got this one reworked.

## Anti-patterns

- Do not add class-specific mob variants to fix a single matchup.
- Do not propose a heal-cap or any other hidden-conditional combat rule.
- Do not treat "average pulls survived" as sufficient on its own in any report.
- Do not assume a card/number fix validated on one mob pool holds on another without
  re-validating.
- Do not price a bigger quest's gold reward as a flat multiple of its loot-count without
  measuring real trip/decay cost first (`sim/quest_cost_gauntlet.py`).

## Class roster (9 of 9, built)

| Class | HP | Identity |
|---|---|---|
| Warrior | 18 | Guardian/Champion stance (locked per pull, see above), stance-payoff cards |
| Cleric | 14 | Sacred Balance (auto-heal trigger on Smite), Heal/Cleansing Barrier sustain |
| Wizard | 14 | Weave (arms a bonus for the next payoff card) + Positioning (evades melee when playing a ranged-tagged card) |
| Paladin | 17 | Invocation of Sanctuary/Grace — pick exactly one per pull, simultaneously a payoff for earlier STRIKE cards and a setup bonus for later ones |
| Rogue | 16 | Cutthroat/Envenom — finishers scaling off STRIKE cards played since the last finisher, resetting on use; killing-blow rider on Cutthroat only |
| Ranger | 15 | Beast Bond: Wolf — persistent multi-round Block (unique in this codebase); Positioning payoff reads whether the previous round granted Range |
| Runecaster | 16 | Chain bonus (Lightning Bolt deals more if played right after Chain Lightning) + Echo (Earth Strike Rune's damage/heal partially repeats automatically next round, no card spent) |
| Druid | 15 | Two mutually exclusive lines — Shapeshift: Grizzly boosts Maul/Swipe if played first, but cancels the Eclipse-stacking bonus (Solar Flare/Moonbeam/Nature's Wildguard) on any Eclipse card played after it |
| Necromancer | 14 | Boneguard's Offering carries Death Pact — may lose 4 HP to deal 3 extra damage when played. Sowing Dread/Blight tag DOTs for Reap to pay off |

All 9 classes are now built. Druid, Rogue, Ranger, Runecaster, and Necromancer were all built
through a fully user-driven iterative process, not an AI-first draft — see
`CLASS_BALANCE_GUIDE.md`'s "Druid, locked", "Rogue, locked", "Ranger, locked", "Runecaster,
locked", and "Necromancer, locked" sections and `DECK_CONDENSING_GUIDE.md`'s checkpoint-
discipline section.
