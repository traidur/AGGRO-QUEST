# QUEST - State of the Game

*AI onboarding handoff: the specific mistakes a fresh AI keeps making on this project. Not a rules
reference (current rules: `DESIGN_DOC.md`; macro loop: `MACRO_LOOP_GUIDE.md`; building a class:
`DECK_CONDENSING_GUIDE.md`; card balance: `CLASS_BALANCE_GUIDE.md`; undecided questions:
`OPEN_QUESTIONS.md`). Modeled on AGGRO's sotg. The simulator is the primary design tool here, so
simulator gotchas are included.*

## What QUEST actually is

Prequel/companion to AGGRO (a StS-x-WoW raid deckbuilder at `C:\Users\steph\StS_x_WoW`). QUEST reuses
AGGRO's classes and card economy but is a logistics engine-builder simulating MMO questing, not raid
combat. Two layers: **per-pull combat** (a fast toll-check, exact-enumeration solved: 6-card unique
deck, 4-card hand, exactly 3 rounds, one card drawn-but-unplayed, no Energy, deck resets every pull,
no RNG except which 4-of-6 hand is drawn) and the **macro loop** (Town, Bag slots, Decaying Bounty
quests, Gold, trip chaining). The macro loop is the real game; combat is the toll gating loot.

## Rules and decisions AI models get wrong on this project

1. **The mob roster changed.** The old 11-mob roster is retired. Standard tier is 6 mobs -
   **Grunt/Bruiser/Enforcer/Raider/Ambusher/Scout** - found by brute-force search
   (`sim/stat_gauntlet.py`, `sim/pool_search.py`). Scout is the only ranged mob; Spike tier is
   empty. Don't resurrect old names.
2. **Mob stats stay class-agnostic.** Never tune a mob to fix one class's matchup; tried, rejected.
3. **"Average pulls survived" alone is not a valid balance metric.** It diverges from decay/death
   rate. Always report both together.
4. **No hidden conditional rules - flat, always-true printed numbers only.** A heal-cap tested well
   (closed ~88% of a gap) and was rejected: *"it will not work in a board game."*
5. **A numeric fix tuned on one mob pool does not generalize** (+15% to -7% across four pools),
   which is why exactly one Standard pool is canonical. Re-validate on the locked pool.
6. **Quest Gold is not proportional to loot count.** It comes from measured trip cost and
   self-decay fairness (bigger quests cost few extra pulls but many extra trips); don't price one as
   a flat multiple without measuring (`sim/quest_cost_gauntlet.py`, `MACRO_LOOP_GUIDE.md`). XP is
   flat, 1 per loot required.
7. **Warrior's stance is locked once per pull**, no mid-pull flip.
8. **Not every mob is melee.** Scout is ranged: Wizard's and Ranger's evasion do nothing to it.
9. **Full-information solvability is not evidence of a tabletop fun problem.** Raised and walked
   back twice. Blackjack, poker and chess openings are solved and fine; a player running a
   calculator opted out. The real question is whether pulls feel good without a tool, a playtest
   question - don't engineer countermeasures (forced randomness, hidden info). One precise
   correction: starting HP is a third variable, but optimal lines average only ~2.5 distinct
   sequences per (hand, mob) across all HPs (~2.5x the naive count, not ~14x).
10. **The simulator validates ideas; it doesn't gate them.** A hidden-info PvP duel was judged on
    "does the exact solver still work" and a blander, easier-to-simulate substitute was offered as
    equivalent. If a mechanic is hard to validate, say so and find another way; never swap in a
    blander one.

## Simulator gotchas

- A class module's `win_rate()` must read `starting_hp` from the live module constant *inside* the
  body, never as a default parameter (evaluated once at import; a later `X.CLASS_HP = N` is silently
  ignored). This produced a false "no effect" finding.
- `risk_only_as_last_resort` **defaults to True** in `macro_sim.py`: the higher risk tolerance
  applies only if no unused consumable is in the Bag.
- Eating Food mid-trip **closes the open loot slot** (locks progress, doesn't destroy it) and frees
  Food's own slot. Easy to get backwards.
- Gold comes entirely from `QUESTS[...]["gold_ladder"]`; `NODES`' old `loot_gold` field is gone.
- **A macro-loop aggregate (`decay_report` deaths/run, `run_to_bag_upgrade` trips) is not a verdict
  on a damage-touching card change.** A strictly better card can raise deaths/run (it finishes
  faster and hits the risk policy's gamble more often). Run `defense_floor_sweep` too, or use
  `compare_card_change` (`MACRO_LOOP_GUIDE.md`, "Clean vs. aggregate metrics").
- **PvP baseline is `sim/sim_pvp.py` + `sim/playtest_board_web.py`.** `sim_final_pvp.py` implemented
  rejected mechanics (Glancing Blows, universal Unlocked Execute) and was deleted; check
  `PVP_BALANCE_GUIDE.md` before trusting a PvP script by name.
- Necromancer has **no in-pull randomness** (Death Pact is flat: may lose 4 HP to deal 3 extra).
  `effective_win_rate` and `draw_random_card` no longer exist; don't call it "Life Tap".
- **Gold in hand at a checkpoint is not a cost measure.** `run_solo_chain`'s `gold_after_turnin`
  mixes earnings with Food restocks and Trainer/Bag purchases. Compare Gold *earned* and *spent*
  separately. A quest that skips a Town visit (kill quests: no Bag slot, they ride along with loot
  pulls) skips a restock and a turn of decay and looks like extra Gold otherwise.
- **Purchased (Level 2+) skills need 6 XP.** Before 2026-10-12 the solo engine let a Level 1 hero buy
  one at the Zone 2 Trainer for 8 Gold. Solo timing numbers from before that date predate the fix.

## Anti-patterns

- Don't add class-specific mob variants to fix one matchup, or propose a heal-cap or any other
  hidden-conditional rule (rules 2 and 4).
- Don't report "average pulls survived" alone, or assume a fix validated on one mob pool holds on
  another (rules 3 and 5).

## Class roster (9 of 9, built)

| Class | HP | Identity |
|---|---|---|
| Warrior | 18 | Guardian/Champion stance (locked per pull), stance payoffs |
| Cleric | 14 | Sacred Balance: auto-heal on Smite; Heal/Cleansing Barrier |
| Wizard | 14 | Weave (arms the next payoff) + Positioning (evades melee on a ranged-tagged card) |
| Paladin | 17 | Invocation of Sanctuary/Grace, exactly one per pull; payoff for earlier STRIKEs, setup for later |
| Rogue | 16 | Cutthroat/Envenom finishers scale off STRIKEs since the last finisher |
| Ranger | 15 | Beast Bond: Wolf, persistent multi-round Block; Positioning reads prior-round Range |
| Runecaster | 16 | Chain bonus (Lightning after Chain Lightning) + Echo (Earth Strike Rune repeats) |
| Druid | 15 | Shapeshift: Grizzly boosts Maul/Swipe but cancels Eclipse stacking after it |
| Necromancer | 14 | Boneguard's Offering carries Death Pact; Sowing Dread/Blight DOTs for Reap |

Druid through Necromancer were built user-driven (`CLASS_BALANCE_GUIDE.md` "<class>, locked";
`DECK_CONDENSING_GUIDE.md` checkpoint discipline).
