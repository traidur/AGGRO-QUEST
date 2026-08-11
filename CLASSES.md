# QUEST — Class Translations (AGGRO → QUEST)

Working translations of AGGRO's starter decks into QUEST's card economy. Source of truth for the AGGRO side: `C:\Users\steph\StS_x_WoW\StS_x_WoW_Classes_v7_4.md` (card list/effects) and `StS_WoW_Sim\data\cards.csv` (balance numbers — cost, dmg, block, heal). QUEST keeps the numbers close to AGGRO's as a starting point (same 3-Energy/turn economy) and strips or simplifies what doesn't have a job in QUEST's combat shape.

**Correction note (second pass, engine audit):** a full audit of `sim/engine.py` against every card's real text found that several tags had been written into `cards.csv` as notes but never actually wired into the solver's logic — Vanguard Blade/Shield's order-sensitive stance bonuses, Sundering Blow's Sunder-token stacking, Stance Dance's Guardian counter-damage, Teleport's Disengage, and Confound's Incapacitate all silently did nothing in every number generated before this pass. Wall of Ice was worse — modeled as a flat 10 Block value instead of its real effect (Untargetable, full immunity). All of these are now implemented and verified against constructed test hands; see `sim/engine.py`'s module docstring for the remaining documented approximations (order-of-play assumptions, boolean vs. stacking charges).

**Correction note (first pass):** the first draft of this doc pulled numbers from `cards.csv`'s aggregated `dmg`/`heal` columns without cross-checking the `notes` column, which carries the actual card text. Several of those aggregated numbers are AGGRO's own expected-value shorthand, not literal effects — Stomp/Snap Freeze's "2 DMG" bakes in "1 DMG × ~2 average targets" for an AoE card, Execute's "2.5 DMG" bakes in "5 DMG × 50% uptime" for a conditional card. Reading those as flat single-target numbers, then further inventing bumps on top when repurposing AoE cards (Stomp became "3 DMG" with no basis), produced real errors. Every table below has been re-derived from the actual `notes` text, with corrections called out inline.

**What gets stripped or changed on every card, and why:**

- **Threat is gone entirely.** No aggro/positional targeting system in QUEST (that's the entire point of the prequel — see `README.md`). Any card whose only function was Threat manipulation has no QUEST equivalent.
- **Range/Zone tags are gone.** AGGRO cards target across a multi-zone battlefield; QUEST combat is one hero against one static mob (or, in a Party Pull, one hero against their own linked sub-mob — still 1-to-1). No positioning within a fight.
- **AoE ("all Mobs in your Zone") cards get repurposed as bigger single-target hits.** There's only ever one mob to hit.
- **Overheal-generates-Threat clauses are dropped** along with Threat itself. Overhealing is still a wasted card, just not a mechanical penalty.
- **Class passives are kept, simplified to fit a single-hero-vs-static-mob math check.** These are exactly what makes the field-lever framing in `DESIGN_DOC.md` (§4, §Class Archetypes) differ class to class, so they're worth preserving even at the cost of a straight translation.
- **Deck size:** AGGRO's starter decks are exactly 10 cards. Where cutting Threat-only cards drops a class below 10, that gap is called out explicitly below rather than papered over with a filler card — it's a real signal that the class needs 1-2 QUEST-native cards, not a straight translation.

---

## Warrior

AGGRO: HP 18, Bulwark, Stance passive (Guardian/Champion), 10 cards.

**Passive — Stance (simplified, corrected against actual card text):** Declare Guardian or Champion at the start of each round, free, locked for that round (matches AGGRO — re-declared every Hero Phase, not fixed for the whole pull).
- **Guardian:** +1 Block whenever you play a card that generates Block. Generic, applies broadly — matches AGGRO as written.
- **Champion:** +1 DMG, but **only on cards tagged BRUTAL** (Heavy Swing, Stomp, Execute, Stance Dance's Champion side) — not a blanket damage bonus. Vanguard Blade and Vanguard Shield are deliberately *not* BRUTAL in AGGRO; they carry their own separate order-sensitive bonuses instead, specifically so the two bonuses don't stack. Flattening this to "generic +1 DMG on any damage card" (my first draft) would double-dip Vanguard Blade/Shield and was wrong — corrected here.

| Card | Cost | Type | Effect | Change from AGGRO |
|---|---|---|---|---|
| Heavy Swing | 1E | Attack, BRUTAL | 2 DMG. Pay +1E to deal 4 DMG instead. | Unchanged. |
| Vanguard Blade | 1E | Attack | 2 DMG. Champion: +2 DMG if last card played was an Attack (not BRUTAL, no generic stance bonus applies). Guardian: gain 2 Block. | **Corrected** — first draft said Champion's bonus was +1 DMG; actual text is +2 DMG. |
| Sundering Blow | 1E | Attack | 1 DMG. Places 1 Sunder token (max 3); mob takes +1 DMG per token from all sources. | Dropped Threat clause. Sunder ramp fits the whittle-HP Slog rule well — kept intact. |
| Vanguard Shield | 1E | Attack | 2 DMG, gain 2 Block. Guardian: +1 DMG if last card played was an Attack (not BRUTAL). | Unchanged — this one was already right. |
| Stomp | 1E | Attack, BRUTAL | 2 DMG. | **Corrected** — AGGRO's actual text is "1 DMG to ALL Mobs in your Zone," and AGGRO's own designer note prices the card at "1 DMG × ~2 targets" (2 EV) for balance purposes. First draft invented 3 DMG for the single-target version; corrected to preserve AGGRO's own EV assumption (2) instead of inventing a number. |
| Execute | 1E | Attack, BRUTAL | 5 DMG. Only usable if mob's remaining HP ≤ 50% of its max. | **Corrected** — first draft used AGGRO's aggregated balance-sheet value (2.5 = "5 DMG × 50% uptime," an EV shorthand, not a real card value) as if it were the literal effect. The actual card deals 5 DMG under a real condition. Now that the sim models multi-round whittling directly, the real conditional effect can just be checked round-to-round instead of pre-baked into an average — a strong natural fit for the whittle-HP Slog rule, since round two of a Slog is exactly when a mob is likely to cross the 50% line. |
| Shield Block | 1E | — | Gain 4 Block. | Unchanged. |
| Stance Dance | 1E | — | Guardian: Gain a Charge Marker. If the mob strikes you this round (Slog), remove the marker to deal 3 DMG back (counts toward the whittle). | **Corrected** — first draft left the counter-damage amount unspecified ("bonus damage"); actual text is 3 DMG. AGGRO's Champion-side effect (hit two separate targets) is still dropped — no second target exists in QUEST's 1-to-1 pulls. |
| ~~Taunt~~ | — | — | — | **Cut.** Pure Threat-drop-and-redirect utility, no function without a shared threat system. |
| ~~Intercept~~ | — | — | — | **Cut.** Same — ally-threat redirection, no QUEST equivalent for now. Possible reuse later as a Party Pull "cover a struggling ally's sub-mob" card, if that's wanted (see `DESIGN_DOC.md` §Class Archetypes). |

**Result: 8 cards, 2 short of the 10-card floor.** The two cuts were both pure-Threat cards with nothing to repurpose — this is a real gap, not an oversight. Warrior needs 1-2 QUEST-native cards (not translated from AGGRO) to hit the deck-size target; flagging rather than inventing filler.

---

## Cleric

AGGRO: HP 12, Architect, Sacred Balance passive, 10 cards.

**Passive — Sacred Balance (simplified):** Whenever you play a Cast-type card that deals damage, you may heal yourself for 2 HP, free. (AGGRO's version can target any hero; solo-only for now since the sim starts single-hero. Extend to ally-targeting once co-op/Party Pull combat is modeled.)

| Card | Cost | Type | Effect | Change from AGGRO |
|---|---|---|---|---|
| Blessed Barrier | **0E** | — | Gain 4 Block. **Waives the Cast Penalty for every card played this round** (same mechanism as Wizard's Teleport). | **QUEST-native change, not an AGGRO translation** — AGGRO's real version costs 1E, targets an ally for a bonus card draw, and has no Cast Penalty interaction. Added here to give Cleric a partial answer to the Engagement tax its Cast-heavy kit takes (see `OPEN_QUESTIONS.md`, Wizard outcome variance / Class Archetypes). Tested at 1E first (only recovered ~11% of the engaged-round damage gap, since its own Energy cost ate most of the savings); moved to 0E, which recovers ~40% of the gap instead. Simplified to self-only pending co-op modeling, independent of this change. |
| Quick Mend | 1E | Heal | Heal self 4 HP. | Dropped Overheal-Threat clause. |
| Blessed Recovery | 1E | Heal, HOT | Heal self 2 HP now, 2 HP again next Recovery step (4 total). | **Corrected** — first draft said 4 HP now + 4 HP on the tick (8 total). Actual text is 2 HP + 2 HP; the CSV's aggregated `heal` value (4.0) is the *sum* of both ticks, not the per-tick amount — misread the first time. |
| Smite ×2 | 1E | Cast, Attack | 2 DMG. Triggers Sacred Balance (currently inert, `SACRED_BALANCE_HEAL`=0 — see `OPEN_QUESTIONS.md`). | Dropped the "+2 vs Undead" conditional — no mob-type taxonomy defined yet for QUEST. **QUEST-native change:** second copy added, replacing Void's Veil (below), to give Cleric more raw damage — its measured weak point across the whole trip dataset — without touching its heal kit. |
| Call of the Void | 2E | Cast, Attack | 5 DMG. Triggers Sacred Balance. | Unchanged apart from Threat. Cleric's big single nuke. |
| Cleansing Fire | 1E | Cast, Attack, DOT | 2 DMG immediate + 1 DMG DOT tick (resolves after the mob acts this round). Triggers Sacred Balance. | **Corrected** — first draft said a flat "3 DMG + DOT," collapsing the immediate/delayed split. Actual text is 2 DMG on cast, 1 more via the DOT tick; the CSV's aggregated value (3.0) is the sum. The split matters once the sim tracks real rounds: the DOT tick lands *after* the mob's strike this round, not during the OTK check itself. |
| Blessed Fortitude | 1E | Instant, Power card | Heal self 4 HP. Also raises Max HP by 4 while **held** (not exhausted — a third card-lifecycle state, see `sim/simulate.py`'s `held_power_cards`). Discarded, buff ending, the moment the hero uses *either* Food or Water (not just Cleric's own refresh resource) or visits Town. | **Reworked from fully inert to functional.** First draft gave this zero playable modes (a one-time permanent effect doesn't fit a per-pull combat model) — correct as far as it went, but left the card doing nothing in every simulated pull. Reframed as a temporary buff scoped to "until the next real rest," which fits the trip model directly instead of fighting it. |
| Heal | 2E | Cast, Heal | Heal self 6 HP. | Dropped Overheal-Threat clause. |
| Void Mark | 0E | Attack, DOT | 1 DMG immediate + 2 DMG DOT tick. | **Corrected** — first draft said a flat "3 DMG + DOT." Actual text is 1 DMG on cast, 2 more via the DOT tick; CSV's aggregated value (3.0) is the sum. Still a notable 0-Energy efficiency outlier once totaled. |

**Result: 10 cards.** Void's Veil (originally "Draw 1 card") was cut — `draw` was never wired into the engine anywhere, making it a fully dead card once that was actually checked; replaced by the second Smite above rather than fixing draw itself.

---

## Wizard

AGGRO: HP 10, Channeler, Spellweaving passive, 10 cards (Fireball ×2).

**Passive — Spellweaving (simplified):** Playing an Instant-type card grants a Charge (max 2). Spend a Charge to reduce a Cast card's Energy cost by 1 (min 0). Approximation for the solver: if the chosen hand includes at least one Instant, the first Cast in the line costs 1 less; with two or more Instants, up to two Casts cost 1 less each. This assumes optimal sequencing (Instants before Casts), which is always at least as good as any other order, so it's a safe simplification rather than a nerf.

| Card | Cost | Type | Effect | Change from AGGRO |
|---|---|---|---|---|
| Fireball ×2 | 2E | Cast, Attack | 6 DMG. | Unchanged. Two copies in the deck, matching AGGRO. |
| Frozen Shot | 1E | Cast, Attack | 3 DMG. | Dropped the SLOW (Zone-lock) clause — no positioning within a single QUEST pull. |
| Fire Blast | 1E | Attack | 3 DMG. | Unchanged. Cheap Instant, also feeds Spellweaving. |
| Arcane Volley | 2E | Cast, Attack | 6 DMG total (2 DMG × 3 hits to the same target). | Clarified the multi-hit structure — AGGRO's text is "deal 2 DMG 3 times," not a flat single hit. Same total either way for a solver that only cares about the OTK sum, but worth stating accurately in case a future card cares about hit count. |
| Shoot Wand | 1E | Attack | 2 DMG, draw 1 card. | Unchanged. Instant that feeds Spellweaving and hand refill. |
| Teleport | 1E | — | Waives the Cast Penalty for every card played **this round only** — an opener, not a standing ward. Has no effect on next round's Engagement; if the mob is still alive and melee, it re-engages normally regardless of this round's Teleport. Feeds Spellweaving. | AGGRO's version repositions across Zones and breaks melee lock. Repurposed as the Wizard's answer to the Opening Range/Engagement rule (`DESIGN_DOC.md` §2) — a real kiting tool. **Corrected** — the sim's first implementation made this permanent for the rest of the pull, which overstated it; it's a repeatable one-round reset, not a one-time permanent fix. |
| Snap Freeze | 1E | Attack | 2 DMG. **Evades melee**: if the mob is a melee type, take zero damage from its strike this round and it doesn't Engage — a "step back," conditional on mob type, unlike Untargetable's unconditional immunity. Does nothing against a ranged mob. | **QUEST-native addition.** Original translation was just the EV-corrected 2 DMG (see prior note on the Stomp-style AoE fix). The evasion clause is new — gives Wizard a second, repeatable (non-Exhaust) defensive option instead of everything riding on Ice Barricade/Confound. |
| Ice Barricade | 0E | — | Gain 10 Block. Exhausts (removed from deck after use, cannot be redrawn for the rest of the pull). | **QUEST-native rework of Wall of Ice**, not a straight translation. AGGRO's real card ("Disengage all. Untargetable this Enemy Phase. Place OVERCHILL on top of your draw pile. Exhaust") grants full immunity plus a real drawback (OVERCHILL, never implemented in this sim at all — confirmed absent from the code, not merely simplified). Playing the old Untargetable version *without* its OVERCHILL cost meant Wizard was getting AGGRO's full defensive power for free the whole session. Ice Barricade is a deliberately simpler, weaker QUEST-native card instead: flat Block (loses to very high ATK, unlike true immunity) with no offsetting drawback of its own — trading AGGRO fidelity for something easier to reason about and balance. |
| Confound | 1E | Cast | Mob skips its Intent (Incapacitate). Must be sequenced **last** in the turn — damage dealt *after* Incapacitate is applied would break it, but damage from other cards played earlier the same round doesn't, since it already landed first. Exhausts. | **Corrected twice** — first draft let it stack for free with no ordering constraint at all; then over-corrected to forbid any damage the same round, which isn't right either. The actual rule is purely about sequencing: play your damage cards, then Confound last, and it holds. Same "assume optimal ordering" convention already used for Spellweaving and the Vanguard order-sensitive bonuses. |

**Result: 10 cards (9 unique + 1 extra Fireball), clean translation, no cuts.**

---

## Next

Rogue, Paladin, Ranger, Necromancer, Druid, Runecaster remain untranslated. Warrior's 2-card gap needs either new QUEST-native cards or a decision to run it at 8. Both are good next steps once the sim confirms the three translated decks land in a sane HP/ATK range.
