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

## Score formula bug: max-HP bonus (found and fixed 2026-09-02)

`sim_pvp.py`'s `evaluate_matchup` used to score each duel as
`(damage_dealt + own_max_hp) - (damage_taken + opponent_max_hp)`. The max-HP term does not
exist in the locked rule — `DESIGN_DOC.md` Section X's Score Tiebreaker is exactly
`(Unblocked Damage Dealt) + (Battle Hardened Tokens)`, no HP component at all. Since Warrior
(18 HP) is the tankiest class in the roster, this bug systematically inflated its matchup
numbers and masked a real, severe weakness. Fixed to plain `damage_dealt - damage_taken`.

**Impact, re-measured after the fix (dominant-win % across the field, via
`sim/pvp_win_matrix.py`):** Warrior drops from "roughly mid-pack, tied with Wizard/Cleric" to
**dead last in the entire roster (2.9%)** — a 0.0% dominant-win rate against Cleric, Wizard,
Paladin, and Druid (four of eight matchups where no hand/sequence Warrior can draw ever forces
a win). This is the real, current confirmation of the zero-ranged-cards structural gap: every
Warrior card is `combat_type="melee"`, so any opponent's `grants_range` evasion shuts it out
completely, every round, with no exception. Corrected full ranking: Druid 58.9, Wizard 54.1,
Cleric 45.7, Paladin 39.7, Ranger 29.4, Runecaster 18.4, Necromancer 12.2, Rogue 14.2,
**Warrior 2.9**.

## Execute-unlock bug (found and fixed 2026-09-03)

`DESIGN_DOC.md` Section X's Class-Specific PvP Rules locks an "Unlocked Execute" exception for
Warrior: Execute (6 flat damage, `killing_blow`) should be playable in any round of a PvP duel,
bypassing its normal PvE requirement that the target be at ≤50% HP. `sim_pvp.py` never
implemented this exception — it called each class's plain PvE `resolve_round`, which enforces
the 50% gate. Since every duel opponent starts at 100% HP, Execute was illegal in round 1 of
every duel, and often illegal for the entire duel. Fixed additively: `condensed_warrior.py`'s
`resolve_round` gained an `execute_unlocked=False` kwarg (default off, zero PvE effect);
`sim_pvp.py` wires Warrior's `CLASSES` entry through `functools.partial(warrior.resolve_round,
execute_unlocked=True)` instead of calling it directly.

**Impact:** this was the single largest contributor found to Warrior's PvP weakness — bigger
than either the score-formula bug above or the evasion retags below. Warrior's dominant-win %
across the field went 2.9% → 23.7% (`sim/pvp_win_matrix.py`), and its steady-state Battle
Hardened token bleed dropped 4.08 → 1.75 (`sim/sim_avg_tokens.py`).

## Evasion retags: a general PvP texture rule, not a per-class patch (2026-09-03)

Three cards were retagged `combat_type="ranged"` (thematic justification: thrown-weapon/
magic-adjacent framing, no mechanical change beyond the tag):

| Class | Card | Reasoning |
|---|---|---|
| Warrior | Heavy Swing | thrown/momentum strike |
| Warrior | Execute | thrown/finishing strike |
| Rogue | Ambush | thrown opener |

**Ruled a general texture rule, not a Warrior-specific fix**: every class should carry 1-2
`[Ranged]`-tagged cards so a mixed kit creates a genuine evade-timing read for the opponent
(guessing which round you'll go ranged), rather than every card in a kit being uniformly
evadable or unevadable. Effect is real but bounded — see the Runecaster-vs-Wizard diagnosis
below for a case where retagging was checked and correctly ruled out as the fix. Thematic
framing is not load-bearing (user confirmed no attachment to the specific card chosen, only
that the retag reads as non-silly) — pick whichever 1-2 cards are least thematically awkward
per class.

`version` bumped 1→2 on all three cards (Heavy Swing, Execute, Ambush) — printed card text
changes (`[Melee]` → `[Ranged]`), not a numeric value change, but still a real physical-card
revision. Regenerate `CARD_REFERENCE.md` via `sim/generate_card_reference.py` after any future
retag.

## Runecaster vs. Wizard: diagnosed, not a melee-exposure problem (2026-09-04)

Runecaster's dominant-loss rate against Wizard specifically is severe (0.0% win / 89.8% loss /
10.2% contested, `sim/pvp_win_matrix.py`) despite Runecaster already carrying 3 of 6 cards
`[Ranged]` — ruled out the "give it more ranged cards" fix before trying it, since the evasion
retag pattern above doesn't apply to a kit that's already balanced on card count.

**Confirmed by direct measurement, not guessed:** negating evasion entirely between the two
classes (no card can ever be evaded) only moves the average security-strategy margin from -2.99
to -2.39, and Runecaster's outright-win rate from 0.4% to 1.3% — evasion explains a small
fraction of the gap, not the majority of it. The real mechanism is a raw 3-card damage ceiling
gap: Runecaster's best available 3-card line tops out around 13 damage (e.g. Windstrike 5 +
Chain Lightning 4 + Call of the Glacier 4, no synergy needed to reach this), while Wizard's
tops out around 16 (e.g. Fire Blast 3 + Fire Ball 7-boosted + Arcane Volley 6-base) — Wizard's
Weave payoff cards (Arcane Volley 6/7, Fire Ball 5/7) simply hit harder per card than anything
in Runecaster's kit, and the payoff triggers the same round it's cashed in, while Runecaster's
own multi-round investment (Earth Strike Rune's echo, Lightning Bolt's chain bonus) pays off
across 2 rounds in a format that only has 3 — a real tempo cost with no PvP-side compensation.

**Not treated as a roster-wide problem**: Wizard has the second-highest dominant-win % in the
entire roster (44.2%, behind only Druid's 54.2%), so most classes have a rough time against it
— this reads as "Wizard is a strong class overall," not "Runecaster specifically is broken
against it." Recommendation, not yet acted on: this is the kind of single-matchup gap the
Battle Hardened Token pendulum is designed to absorb, not a candidate for a new Class-Specific
PvP Rule — no rule change proposed here.

## Necromancer: Death Pact is a dead card in PvP duels (diagnosed 2026-09-04)

`sim_pvp.py`'s score is `own_damage_dealt - own_damage_taken`, computed at the end of the duel
as `max_hp - final_hp` on each side. Boneguard's Offering (Boosted) — "Death Pact" — costs the
Necromancer 4 self-inflicted HP to deal 3 bonus damage. That self-inflicted HP loss is
indistinguishable, in the final-HP-delta scoring, from HP lost to the opponent's own attacks:
playing it nets **+3 to your own damage dealt, but +4 to the opponent's damage-dealt score**,
a net -1 differential. Confirmed the solver never plays it in any of the 225 hand pairings
against any opponent — it is strictly a losing move under the current score formula. This is a
different kind of finding than the two bugs above: the self-damage really is visible HP loss
at the table, so this isn't a simulator bug, it's a genuine (and clearly unintended) interaction
between a self-cost mechanic and a pure-HP-delta score formula.

**Two candidate PvP-only rules were simulated** (`sim/_necro_pvp_candidates.py`, throwaway).
The first pass measured **Candidate A ("Death Pact costs no HP in duels") as a flat 0.0 point
delta in every matchup — this was wrong, a diagnostic bug, not a real finding.** Both the
throwaway script and the first real implementation attempt checked
`"(Boosted)" in card_name and card_name not in CARDS` before overriding the HP cost — but
Boneguard's Offering (Boosted) is a **statically pre-registered** `CARDS` entry
(`CARDS[BONEGUARD_OFFERING_BOOSTED]`, built once at module import), not a dynamically-computed
one, so it always took the `else` branch and the override never actually ran in either the
diagnostic or the first patch. Caught by re-verifying the override's actual effect directly
(`resolve_round(... , death_pact_free=True)` still returned `heal=-4`) before trusting the
"zero effect" conclusion — the same "verify, don't just trust the first result" discipline
this project keeps needing. Fixed in `condensed_necromancer.py`'s `resolve_round` by checking
`death_pact_free` a second time, after `card` is resolved via either branch, copying before
mutating so the shared module-level `CARDS` dict is never touched.

**Candidate A, correctly measured, is a real and substantial improvement — locked as
Class-Specific PvP Rule #2** (`DESIGN_DOC.md` Section X), implemented via
`condensed_necromancer.py`'s `death_pact_free=False` kwarg (PvE-inert by default) and
`sim_pvp.py`'s `functools.partial(necro.resolve_round, death_pact_free=True)`, mirroring
Warrior's `execute_unlocked` pattern exactly:

| Matchup | Loss% before | Loss% after | Contested% before | Contested% after |
|---|---|---|---|---|
| vs. Druid | 97.3 | 93.8 | 2.7 | 6.2 |
| vs. Wizard | 88.9 | 71.6 | 9.8 | 27.1 |
| vs. Cleric | 80.4 | 62.7 | 19.6 | 37.3 |
| vs. Paladin | 73.3 | 50.7 | 26.7 | 49.3 |
| vs. Ranger | 56.9 | 21.8 | 32.0 | 65.3 |
| vs. Rogue | 37.3 | 12.4 | 54.7 | 62.7 |
| vs. Warrior | 68.0 | 54.2 | 30.7 | 38.2 |
| vs. Runecaster | 39.1 | 9.3 | 50.7 | 74.7 |

Avg dominant-win % vs. the field: 4.0% → 7.8%. Steady-state token bleed: 2.86 → 1.71
(comfortably under the current 3 starting tokens — no token-count change needed). The four
"blowout" matchups (Druid/Wizard/Cleric/Paladin) still don't flip to outright dominant wins,
but guaranteed losses dropped sharply across nearly every matchup, converting former
hopeless hands into genuinely contested ones. Adopted on principle even before this
correction (a card that is a strictly losing move in every single duel is worth fixing
regardless of aggregate win-rate impact, same reasoning as Warrior's Execute-unlock), and the
corrected measurement shows the practical impact is real and large, not negligible.

- **Candidate B — "DOTs count double for Reap in duels"** (Reap's dot-count payoff multiplier
  1→2, max reachable bonus +2→+4 across a 3-round pull): measured against the pre-Candidate-A
  baseline, real but partial — avg dominant-win 4.0% → 6.2%, concentrated in the matchups that
  were already closer to competitive (Runecaster +6.7pt, Ranger +4.9pt, Rogue +4.0pt, Warrior
  +2.2pt), untouched blowout matchups. **Not implemented** — not re-measured on top of
  Candidate A's now-corrected baseline; if pursued later, re-run against the real post-A
  numbers above, not the stale pre-A ones.

## Battle Hardened starting token counts — history

Live values (`sim/playtest_board_web.py`, `_new_hero`):

| Class | Starting Tokens |
|---|---|
| Rogue, Warrior, Necromancer | 2 |
| Ranger, Runecaster | 1 |
| Wizard, Cleric, Paladin, Druid | 0 |

- **Necromancer (2→3, 2026-08-30):** `Reap` and `Death Blow` were originally
  `combat_type="melee"`, so any opponent's `grants_range` evasion (Wizard, Ranger, etc.)
  zeroed the Necromancer's two biggest payoff cards for free — an "evasion trap" that had its
  PvP win rate at 1-7. Confirmed thematically as magic/dark-magic effects rather than physical
  strikes, both were retagged `combat_type="ranged"` in `condensed_necromancer.py`. Re-running
  `sim/sim_avg_tokens.py` (steady-state token simulation) after the fix still showed a token
  bleed of ~3.8, so starting tokens were bumped 2→3 to buffer the early campaign.
- **Necromancer (3→2), Wizard (1→0), Cleric (1→0), 2026-09-04:** re-derived via
  `sim/sim_avg_tokens.py` after locking the Death Pact PvP rule (see above), which cut
  Necromancer's steady-state bleed from ~4.08 to 1.71 — its old 3-token count was sized for the
  pre-fix bleed and had gone stale. Ran the full roster fresh rather than Necromancer alone,
  since fixing one class's numbers shifts every opponent's own measured win rate too (confirmed
  concretely: Runecaster's own avg dominant-win dropped 9.2%→5.5% purely from Necromancer
  winning more often against it, enough to make Runecaster the new roster floor, not
  Necromancer — see the Runecaster section above, not yet re-examined against this new floor).
  Full before/after:

  | Class | Starting (old) | Steady-state (measured) | Starting (new) |
  |---|---|---|---|
  | Rogue | 2 | 1.85 | 2 (unchanged) |
  | Warrior | 2 | 1.78 | 2 (unchanged) |
  | Necromancer | 3 | 1.71 | **2** |
  | Runecaster | 1 | 1.09 | 1 (unchanged) |
  | Ranger | 1 | 0.89 | 1 (unchanged) |
  | Wizard | 1 | 0.36 | **0** |
  | Paladin | 0 | 0.20 | 0 (unchanged) |
  | Druid | 0 | 0.19 | 0 (unchanged) |
  | Cleric | 1 | 0.16 | **0** |

  Rogue/Warrior/Runecaster/Ranger/Paladin/Druid were already close to their steady-state need
  (within ~0.2) and left untouched. Cleric and Wizard's prior `0→1` moves already had no
  recovered rationale (see below) — this doesn't explain them, just confirms they'd drifted
  loose independent of today's Necromancer-specific cause.
- **Runecaster (2→1), Paladin (1→0):** these differ from `DESIGN_DOC.md`'s original table but
  match the live code with no recovered rationale in `AI_HANDOFF.md` or elsewhere — flagging
  here in case the original reasoning resurfaces and needs reconciling.

## Diagnostic tools

- `sim/sim_pvp.py` — the true baseline duel resolver + minimax matchup-matrix generator (raw
  damage-differential EV, pre-token, no HP term — see the score-formula bug note above).
- `sim/pvp_win_matrix.py` — dominant-win/dominant-loss/contested percentage breakdown per
  matchup, built on `sim_pvp.py`. Use this instead of the raw margin number when the question
  is "who actually wins" rather than "by how many points" — the margin number alone hid the
  Warrior finding above.
- `sim/sim_avg_tokens.py` — steady-state Battle Hardened token simulator; use this (not a new
  one-off script) to re-derive starting token counts after any PvP-relevant card change.
- `sim/playtest_board_web.py` — the actual live web app; authoritative for current starting
  token values and the real pendulum implementation.
