# QUEST

A prequel/companion to **AGGRO** (the StS × WoW raid-boss deckbuilder at `C:\Users\steph\StS_x_WoW`). Where AGGRO simulates the claustrophobic, 10-minute micro-puzzle of a raid boss, QUEST simulates the sprawling, push-your-luck macro-logistics of MMO leveling and farming.

**Status:** actively simulated and iterated, not a first-pass brainstorm anymore. Six classes are built and balance-locked (Warrior/Wizard/Cleric/Paladin/Rogue/Ranger), the Standard-tier mob roster is locked, and the macro Town/Bag/Quest/Gold loop is built with locked reward formulas — see `CLASS_BALANCE_GUIDE.md` and `MACRO_LOOP_GUIDE.md` for what's actually settled, with reasoning. `OPEN_QUESTIONS.md` tracks what's still genuinely undecided.

## Documents

| File | What it is |
|---|---|
| `SOTG.md` | **AI onboarding — read first.** Rules and decisions AI models keep getting wrong on this project, simulator gotchas, anti-patterns. |
| `DESIGN_DOC.md` | Current design draft — golden rules, core systems, decided properties |
| `DECK_CONDENSING_GUIDE.md` | Process doc for translating an AGGRO class's ~10-card kit into a legal 6-card condensed kit — what to cut, what to reframe, how to fit the slot budget |
| `CLASS_BALANCE_GUIDE.md` | Process doc for per-pull card/mob balance methodology and tooling, once a kit already exists |
| `MACRO_LOOP_GUIDE.md` | Process doc for the Town/Bag/Quest/Gold macro loop — reward formulas, pricing, risk policy |
| `OPEN_QUESTIONS.md` | Design tensions and unresolved mechanics, with a Resolved section for settled ones |
| `CONDENSED_COMBAT.md` | Design log for the current combat model itself |
| `sim/` | All simulator code — see `sim/README.md` |

## Relationship to AGGRO

QUEST reuses AGGRO's classes and role identities as a starting point, but the actual combat
model (condensed combat: 6-card unique deck, 4-card hand, exactly 3 rounds, no Energy cost,
deck fully resets every pull) is QUEST-native, not a direct port of AGGRO's turn structure,
Energy economy, or Threat/targeting system. Each class's real, current, authoritative kit
lives in its own `sim/condensed_<name>.py` file's `CARDS` dict — **never** in a prose
description, docstring, or any doc, all of which can drift from the executing code.

For shared class-identity vocabulary (not mechanics), the parent project's
`StS_x_WoW_Classes_vX_X.md` and `sotg_vX_X.md` are the reference. Where QUEST's actual
mechanics diverge from AGGRO's, QUEST's own docs and code win — see `DECK_CONDENSING_GUIDE.md`
for what changed and why on a class-by-class basis.
