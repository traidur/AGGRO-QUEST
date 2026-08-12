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

## Anti-patterns

- Do not add class-specific mob variants to fix a single matchup.
- Do not propose a heal-cap or any other hidden-conditional combat rule.
- Do not treat "average pulls survived" as sufficient on its own in any report.
- Do not assume a card/number fix validated on one mob pool holds on another without
  re-validating.
- Do not price a bigger quest's gold reward as a flat multiple of its loot-count without
  measuring real trip/decay cost first (`sim/quest_cost_gauntlet.py`).

## Class roster (built so far — 6 of 9)

| Class | HP | Identity |
|---|---|---|
| Warrior | 18 | Guardian/Champion stance (locked per pull, see above), stance-payoff cards |
| Cleric | 14 | Sacred Balance (auto-heal trigger on Smite), Heal/Cleansing Barrier sustain |
| Wizard | 14 | Weave (arms a bonus for the next payoff card) + Positioning (evades melee when playing a ranged-tagged card) |
| Paladin | 17 | Invocation of Sanctuary/Grace — pick exactly one per pull, simultaneously a payoff for earlier STRIKE cards and a setup bonus for later ones |
| Rogue | 16 | Cutthroat/Envenom — finishers scaling off STRIKE cards played since the last finisher, resetting on use; killing-blow rider on Cutthroat only |
| Ranger | 15 | Beast Bond: Wolf — persistent multi-round Block (unique in this codebase); Positioning payoff reads whether the previous round granted Range |

Necromancer, Druid, Runecaster remain unbuilt. Rogue and Ranger were both built through a
fully user-driven iterative process, not an AI-first draft — see `CLASS_BALANCE_GUIDE.md`'s
"Rogue, locked" and "Ranger, locked" sections and `DECK_CONDENSING_GUIDE.md`'s
checkpoint-discipline section.
