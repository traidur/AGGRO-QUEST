# QUEST Simulator

Two layers: **condensed combat** (exact-solver, per-pull card math) and the **macro loop**
(Town/Bag/Quest/Gold, built on top of condensed combat). See `../CLAUDE.md` for which
top-level doc explains which decision, and `../CLASS_BALANCE_GUIDE.md` /
`../DECK_CONDENSING_GUIDE.md` for methodology.

## Condensed combat

- `condensed_<class>.py` (`warrior`, `wizard`, `cleric`, `paladin`, `rogue`, `ranger`) --
  one exact solver per class. 6-card unique deck, 4-card hand, exactly 3 rounds, no Energy
  cost, deck fully resets every pull. Each exposes `CARDS` (the actual card values --
  authoritative, read this before trusting any doc's description of what a card does),
  `simulate()`, `best_line_for_hand()`, `win_rate()`. See `CLASS_BALANCE_GUIDE.md`'s "module
  interface" section for the exact required shape.
- `condensed_trip.py` -- the shared toolkit every class plugs into: the locked Standard mob
  roster (`MOBS`, `MOB_TIERS`), the full diagnostic suite (`full_diagnostic`,
  `damage_distribution`, `flee_preference`, `pairwise_genuine_difference`,
  `mob_difficulty_ranking`, `tuning_report`, `full_report`/`compare_reports`), and
  `register_class_for_testing()` for iterating on a class before it's locked in.

## Macro loop

- `macro_sim.py` -- Town/Bag/Quest/Gold, built on top of condensed combat's per-pull solvers.
  See `MACRO_LOOP_GUIDE.md` for the reward formulas, risk policy, and pricing derivations.

## Mob / content derivation tools (permanent, rerunnable)

- `stat_gauntlet.py` -- brute-force mob-shape sweep (writes `stat_gauntlet.csv`).
- `pool_search.py` / `pool_search_decay.py` / `pool_search_target.py` -- random-search whole
  mob-pool combinations against the real chained diagnostics, using `stat_gauntlet.csv` as
  candidates. This is how the locked Standard tier was actually found -- see
  `CLASS_BALANCE_GUIDE.md`'s "stat gauntlet" section.
- `quest_cost_gauntlet.py` -- measures real pulls/trips/decay cost per quest `required` count,
  the basis for the locked quest gold-reward formula in `MACRO_LOOP_GUIDE.md`.

## Interactive playtest

- `playtest_cli.py` / `playtest_engine.py` / `playtest_web.py` (+ `playtest_templates/`) --
  step-by-step engine (separate from, but numerically synced with, the exhaustive solvers)
  plus terminal and Flask front ends. Lets a human actually draw a hand and play a pull.

## Legacy, superseded -- not used by anything above, kept for historical reference only

`engine.py`, `simulate.py`, `calibrate.py`, `data/cards.csv`, `data/mobs.csv` are an earlier,
AGGRO-scale Monte Carlo simulator (Energy costs, Engagement/Cast Penalty, a full multi-card
per-round hand) that predates the condensed-combat rewrite entirely. Nothing in the current
system imports or reads any of them (confirmed directly, not assumed). Do not treat anything
in this list as describing current mechanics or numbers.
