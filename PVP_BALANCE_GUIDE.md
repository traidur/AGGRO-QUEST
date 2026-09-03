# PvP Balance Guide

Settled decisions and derivation history for Competitive PvP (`DESIGN_DOC.md` Section X).
Mirrors `CLASS_BALANCE_GUIDE.md`'s role for PvE — this is where a settled PvP balance
decision goes, not `AI_HANDOFF.md` (a rolling cross-AI log, not a stable reference) or
`SOTG.md` (mistake-prevention only, not a decision history).

## The true PvP baseline

`sim/sim_pvp.py` is the correct PvP duel simulator, and `sim/playtest_board_web.py` is the
correct implementation of the full Battle Hardened token pendulum on top of it. Together they
are the source of truth for "what does PvP actually do right now" — not `DESIGN_DOC.md`'s
prose alone, which can drift out of sync with tuned numbers (see the token table below).

**`sim/sim_final_pvp.py` was a rejected experimental branch — deleted 2026-09-02, present in
git history only.** It implemented two rules that were explicitly rejected: "Glancing Blows"
(half damage on an evaded melee attack instead of the locked 0 damage) and a universal
Unlocked Execute rule (`DESIGN_DOC.md` only unlocks Execute for the Warrior). Its output file,
`pvp_final_matrix_new.md`, was a raw pre-token EV matrix computed under those rejected rules —
also deleted. Despite the filename, treat any future "final" or "new" prefixed PvP script as
unproven until checked against `sim_pvp.py`'s actual rules, not the other way around.

## Battle Hardened starting token counts — history

Live values (`sim/playtest_board_web.py`, `_new_hero`):

| Class | Starting Tokens |
|---|---|
| Necromancer | 3 |
| Rogue, Warrior | 2 |
| Ranger, Wizard, Cleric, Runecaster | 1 |
| Paladin, Druid | 0 |

- **Necromancer (2→3, 2026-08-30):** `Reap` and `Death Blow` were originally
  `combat_type="melee"`, so any opponent's `grants_range` evasion (Wizard, Ranger, etc.)
  zeroed the Necromancer's two biggest payoff cards for free — an "evasion trap" that had its
  PvP win rate at 1-7. Confirmed thematically as magic/dark-magic effects rather than physical
  strikes, both were retagged `combat_type="ranged"` in `condensed_necromancer.py`. Re-running
  `sim/sim_avg_tokens.py` (steady-state token simulation) after the fix still showed a token
  bleed of ~3.8, so starting tokens were bumped 2→3 to buffer the early campaign.
- **Runecaster (2→1), Paladin (1→0), Ranger/Wizard/Cleric (0→1):** these differ from
  `DESIGN_DOC.md`'s original table but match the live code with no recovered rationale in
  `AI_HANDOFF.md` or elsewhere. `DESIGN_DOC.md` Section X was synced to match live code on
  2026-09-02 pending that reasoning resurfacing — flag here if it's ever reconstructed.

## Diagnostic tools

- `sim/sim_pvp.py` — the true baseline duel resolver + minimax matchup-matrix generator
  (raw damage+maxHP EV, pre-token).
- `sim/sim_avg_tokens.py` — steady-state Battle Hardened token simulator; use this (not a new
  one-off script) to re-derive starting token counts after any PvP-relevant card change.
- `sim/playtest_board_web.py` — the actual live web app; authoritative for current starting
  token values and the real pendulum implementation.
