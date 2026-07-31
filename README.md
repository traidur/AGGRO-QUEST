# QUEST

A prequel/companion to **AGGRO** (the StS × WoW raid-boss deckbuilder at `C:\Users\steph\StS_x_WoW`). Where AGGRO simulates the claustrophobic, 10-minute micro-puzzle of a raid boss, QUEST simulates the sprawling, push-your-luck macro-logistics of MMO leveling and farming.

**Status:** pre-prototype. Design is a first brainstorming pass — nothing is locked until it's out of `OPEN_QUESTIONS.md`.

## Documents

| File | What it is |
|---|---|
| `DESIGN_DOC.md` | Current design draft — golden rules, core systems, decided properties |
| `OPEN_QUESTIONS.md` | Design tensions and unresolved mechanics to settle before prototyping |

## Relationship to AGGRO

QUEST shares AGGRO's class logic, keywords, and action economy: 3 Energy/turn, Instants, Casts, Stances, and the per-class engines (Combo Points, Spellweaving, Sacred Balance, etc.). It does **not** share AGGRO's turn structure, enemy AI, or win condition — those are being built from scratch for QUEST's genre.

For shared vocabulary, the parent project's `StS_x_WoW_Classes_vX_X.md` (class kits) and `sotg_vX_X.md` (AI onboarding / rules-consistency doc) are the canonical reference. When QUEST's docs and AGGRO's docs disagree on a shared term, AGGRO wins unless QUEST explicitly overrides it.
