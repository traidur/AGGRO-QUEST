# QUEST

A prequel/companion to **AGGRO** (the StS × WoW raid-boss deckbuilder at `C:\Users\steph\StS_x_WoW`). Where AGGRO simulates the claustrophobic, 10-minute micro-puzzle of a raid boss, QUEST simulates the sprawling, push-your-luck macro-logistics of MMO leveling and farming.

**Status:** pre-prototype. Design is a first brainstorming pass — nothing is locked until it's out of `OPEN_QUESTIONS.md`.

## Documents

| File | What it is |
|---|---|
| `SOTG.md` | **AI onboarding — read first.** Rules and decisions AI models keep getting wrong on this project, simulator gotchas, anti-patterns. |
| `DESIGN_DOC.md` | Current design draft — golden rules, core systems, decided properties |
| `DECK_CONDENSING_GUIDE.md` | Process doc for translating an AGGRO class's ~10-card kit into a legal 6-card condensed kit — what to cut, what to reframe, how to fit the slot budget |
| `CLASS_BALANCE_GUIDE.md` | Process doc for per-pull card/mob balance methodology and tooling, once a kit already exists |
| `MACRO_LOOP_GUIDE.md` | Process doc for the Town/Bag/Quest/Gold macro loop — reward formulas, pricing, risk policy |
| `OPEN_QUESTIONS.md` | Design tensions and unresolved mechanics to settle before prototyping |
| `CLASSES.md` | Stale — predates the condensed-combat rewrite. Flavor reference only. |

## Relationship to AGGRO

QUEST shares AGGRO's class logic, keywords, and action economy: 3 Energy/turn, Instants, Casts, Stances, and the per-class engines (Combo Points, Spellweaving, Sacred Balance, etc.). It does **not** share AGGRO's turn structure, enemy AI, or win condition — those are being built from scratch for QUEST's genre.

For shared vocabulary, the parent project's `StS_x_WoW_Classes_vX_X.md` (class kits) and `sotg_vX_X.md` (AI onboarding / rules-consistency doc) are the canonical reference. When QUEST's docs and AGGRO's docs disagree on a shared term, AGGRO wins unless QUEST explicitly overrides it.
