# QUEST — Design Draft v0.1

Origin: first brainstorming pass (jam session), reorganized and lightly edited. Treat everything here as a strong first draft, not canon — items that need resolution before prototyping live in `OPEN_QUESTIONS.md`, not here.

## Concept

A prequel/companion to AGGRO. AGGRO is the claustrophobic, 10-minute micro-puzzle of a raid boss. QUEST is the sprawling, push-your-luck macro-logistics of MMO "leveling and farming." Genre: **logistical engine-builder**, not a raid encounter.

**Vibe:** greed, inventory management, exponential power scaling.

## Golden Rules

1. **No Movement Tax.** Commuting across the map costs 0 Energy. Movement is a tempo choice, never an Energy tax.
2. **Carrots, Not Sticks.** No Doom Track, no "Game Over in 15 Turns" clock. Players are pulled forward by decaying loot bonuses and the hard math walls of higher-tier zones.
3. **Determinism Over Dice.** Combat is a strict 5-card, 3-Energy math puzzle. No dice. You die because your deck is inefficient, not because you rolled poorly.
4. **Shared DNA.** Uses AGGRO's class logic, keywords, and action economy (3E, Instants, Casts, Stances) unchanged.

## Core Gameplay Systems

### 1. The Turn Structure — The 4-Phase Round

Split into drafting and simultaneous execution, to avoid multiplayer solitaire while staying fast.

- **Phase 1 — Commute & Spawn (simultaneous):** Players freely move pawns to any node. Board refreshes (new mobs in field rows, new upgrades in market rows).
- **Phase 2 — The Claim (turn order):** First Player Token passes clockwise; each player claims exactly one target at their node (a specific mob to fight, or a specific market card to buy). Creates competitive resource drafting.
- **Phase 3 — Execution (simultaneous):** Everyone plays their 3-Energy hand to solve their combat math, or buys upgrades in town. No waiting on others' math.
- **Phase 4 — Clean Up (simultaneous):** Quest tokens decay (if in Town). Hands discarded. Draw back to 5. Pass First Player Token.

### 2. Combat as a Toll — the OTK Goal

Strips out AGGRO's multi-phase enemy AI. One-round mathematical check.

- **The Pull:** Face a mob's static stat block (e.g. HP 12 / ATK 5).
- **The Goal (OTK):** Play 3 Energy to generate DMG ≥ Mob HP. Success: mob dies, you take 0 damage, loot is immediate.
- **The Slog (failure):** Fail to kill in one hand → mob strikes. Take (ATK − your Block) as HP damage — HP only, no Durability wound (see §3, Durability cut entirely). Mob survives at its **remaining** HP — damage dealt this round is not wasted, it whittles the mob down. You finish it off next round with a fresh hand against that reduced total, not a repeat attempt at the original threshold. Ruins tempo either way, but progress persists.
- **Melee vs. Ranged:** Melee decks (Warrior/Rogue) have Block to mitigate the Slog. Casters (Wizard) have ~0 Block — they must OTK or get crushed by unmitigated ATK.

**Opening range (decided).** Unless a mob states otherwise, a pull opens with the mob at range — the hero's first Hero Phase happens **unengaged**, free of AGGRO's Cast Penalty (+1 Energy on Cast-type cards while Engaged). If the mob is a melee type and the OTK fails, it Engages during the Enemy Phase, and the Cast Penalty applies to every subsequent round of that Slog. This is AGGRO's existing kiting identity (Wizard: "glass cannon, Spellweaving engine, kiting"), ported directly: a caster who opens strong enough to OTK in round one never pays the penalty at all; one who whiffs gets punished twice over — unmitigated ATK from having ~0 Block, and a worse Energy rate to finish the whittled-down mob from round two on. Ranged-type mobs presumably never Engage at all, which would mean the Cast Penalty never triggers against them regardless of how long the Slog runs — see `OPEN_QUESTIONS.md`.

### 3. HP: The Sole Attrition Currency (superseded — see below)

**Superseded, locked via the macro-loop design pass (Gemini-assisted, condensed-combat era).**
The original three-pillar model below is kept for history, not as current design — Winded/OOM
and Durability were both cut entirely, not just deferred. Condensed combat's own 6-card deck
already resets fully every pull with no Exhaust/OOM tracking at the card level (see
`CONDENSED_COMBAT.md`), and once the macro loop was designed around that same combat engine, the
same logic extended upward: **raw HP is the sole currency of attrition**, full stop. The
combat solver's own "pulls before HP≤0" output (extensively computed and verified per class in
`sim/condensed_trip.py`) *is* the macro-loop attrition metric directly, with no second resource
layered on top. This keeps combat a blazing-fast, fully deterministic toll check and avoids
maintaining two separate attrition systems that would need to be balanced against each other.
Durability specifically had already gone concept-only with no working trigger before this
pass (see the original note below, kept for the history) — this final cut just makes that
permanent instead of "not yet revived."

Bag Tetris (§5, since rewritten) now carries the pacing-engine role that Winded/Durability were
originally meant to fill — not through deck pollution, but through a spatial/logistics
constraint on loot capacity instead. See §5 for the current mechanic.

<details>
<summary>Original three-pillar draft (historical, not current design)</summary>

Taking damage or pushing your luck clogs your deck with dead weight, pushing players back to town naturally.

1. **Health (HP):** Hard limit, tracked on Hero Board. 0 HP = dead.
2. **Winded / OOM (sustain):** Unplayable dead weight. Gained from heavy spells or chain-pulling. Cleared via a Rest action + consuming a Food/Water token from the bag.
3. **Durability (gear damage):** Passive debuffs (e.g. −1 DMG on attacks). Gained from massive unblocked hits or failed OTKs. Cannot be cleared in the field — only repaired at a Town Blacksmith for Gold. **Status: concept only, no active trigger.** A specific implementation (flat escalating mob ATK per pull) was built and tested in the sim, found to be solving a problem that a separate fix (removing Cleric's Sacred Balance passive) already handled, and was removed. See `OPEN_QUESTIONS.md` for the full history before reviving this pillar with a new trigger.

</details>

### 4. Field Levers — Slower-Downers & Speeder-Uppers

The combat/field puzzle runs on two opposing lever sets. Slower-downers erode a player's capacity to keep pulling; speeder-uppers restore or spike it. This axis is the core engine of the field-side game — see `INSPIRATIONS.md` for external precedent on individual levers.

**Slower-downers (erode capacity)**

1. **HP loss** — direct damage from a Slog. Core, and per §3, now the *only* core attrition
   lever — items 2 and 3 below are kept for history but no longer part of the design.
2. ~~**Deck trash**~~ — Winded/OOM cards forced into the draw pile as dead weight. **Cut, see §3.**
   Condensed combat's deck fully resets every pull; there's no persistent deck to pollute.
3. ~~**Stat debuffs**~~ — Durability's passive penalties. **Cut, see §3.** Already concept-only
   before this pass; now permanently removed rather than deferred.
4. **DOTs** — reuses AGGRO's existing Affliction vocabulary. Proposed: a failed OTK could leave a DOT ticking into the *next* pull, compounding the Slog instead of dealing one lump sum.
5. **Hard CC as tempo denial** — reuses AGGRO's STUN/INCAPACITATE/FEAR/ROOT/SLOW/INTERRUPT. Proposed: a mob Roots you (can't flee to Town this round) or Interrupts Cast-type cards, forcing a worse hand than the one drawn.
6. **Cast Penalty extension** — AGGRO's existing +1 Energy cost while Engaged. Proposed: a mob ability could carry this penalty into the next pull.
7. **Bag clutter** — Vendor Trash loot eating a Bag slot without helping. Logistics-layer, not combat, but the same capacity-erosion idea, and it competes for the same slots as Food/Potions (now 2 starting slots, not 8 — see §5).
8. ~~**Gear breaking outright**~~ — Durability hitting 0 disabling a card type entirely. **Moot, Durability cut entirely per §3** — was already "explicitly not adopted" even when Durability existed as a concept, now doubly so.

**Speeder-uppers (recover capacity / spike tempo)**

1. **Heals** — direct HP restore. Core.
2. **Food / Potions** — locked via the macro-loop pass, replacing the old Food/Water/Bandages
   framing (which existed to clear Winded, now cut per §3). Two consumables, two different
   trade-offs on the *same* Bag Tetris slot economy (§5) rather than a Winded-clearing role:
   **Food** (cheap, heals to full, closes the active Bag Slot — breaks the loot chain) vs.
   **Potion** (pricier, partial heal, preserves the active Bag Slot — keeps the loot chain
   alive). The choice is capacity vs. tempo, not "clear a resource."
3. **Buffs** — temporary Strength/DMG/Block bonuses, reusing AGGRO's class-kit vocabulary.
4. **Block/Armor stacking** — pre-empts a future Slog instead of reacting to one.
5. **Combo-point / build-up payoffs** — Rogue's Combo Points, Wizard's Spellweaving. A speeder-upper a player earns through patience rather than buys — different texture than a consumable.
6. **Card draw / hand-size boosts** — raises OTK odds directly without touching the underlying math.
7. **HOTs** — reuses AGGRO's existing vocabulary. A HOT staged before a pull turns a future Slog into a non-event.
8. **Cleanse / dispel** — removes a DOT or debuff in the field. Still applies to DOTs (item 4
   above survives this pass); the Durability-specific half of this item is moot now that
   Durability is cut entirely per §3, not just paused.
9. **"Well Rested" bonus** — WoW's rested-XP analog. Sleeping at a Town/Inn node grants a bonus (bonus DMG, or a free re-draw) on the first pull after leaving. Gives Town a carrot beyond bounty decay.
10. ~~**Field repair kit**~~ — item that patches Durability without a Town trip. **Moot, Durability cut entirely per §3.**

*Items 1–3 in each list are load-bearing (they define the Three Pillars above); everything else here is proposed and needs playtesting before being called core vs. later-tier unlocks.*

### 5. Bag Tetris (the pacing engine) — rewritten, locked via the macro-loop pass

**Superseded from the original 8-slot draft below.** Starting Bag is **2 Slots**, not 8 —
deliberately tight (per §3/§4, this is now the *only* pacing lever, since Winded/Durability are
gone). Bag Upgrades (+1 Slot, priced 12G at the Port Town Market) are the core early-game goal.

- **Starting loadout:** 2-Slot Bag, 1 Food item occupying Slot 1, 0 Gold, 0 XP, Level 1.
- **Loot chain:** winning a pull drops a deterministic loot card (tied to the specific mob, no
  RNG loot table) into your active Bag Slot. **Identical loot cards stack infinitely in a
  single open slot** — a slot's constraint is how many *different* loot types you're
  collecting simultaneously, not a raw item count.
- **The Break:** Food (2G) heals to full HP in the field but **closes the active Bag Slot**,
  forcing subsequent loot into a new, empty one — this is the actual "push your luck" lever now
  that deck-trash/stat-debuff attrition is gone. Potion (4G) heals a flat, partial amount (7 HP)
  but does *not* close the slot, preserving the loot chain at a steeper gold cost. See §4.
- **Deliberately tight starting math, confirmed not accidental:** the two starter quests (§6)
  each require 3x of a *different* deterministic loot type — exactly 2 slots for 2 simultaneous
  quest lines, filling the starting Bag exactly. Eating Food to survive genuinely costs a full
  active quest line that trip, not abstract capacity.
- **Currency Cap** (from the original draft, not touched by this pass — still open, not
  confirmed or contradicted): currencies don't convert. Tier 3 cards cost Gold; you cannot hold
  enough Tier 1 Copper to buy them. Forces players into harder zones for denser wealth.

### 6. Decaying Bounties (the hidden stick)

Prevents safe turtling via FOMO instead of a clock.

- **Quest Log:** Players hold exactly 3 Quests at all times, forcing routes across multiple map nodes.
- **Bounty Tokens:** A drawn Quest gets a Gold Token (large Gold/XP bonus).
- **Decay:** Every time a player's pawn touches a Town Node, any Quest in the log that isn't ready to turn in downgrades (Gold → Silver → Bronze → nothing).
- **Result:** Players take bigger field risks to complete all 3 Quests in one trip and bank the Gold tier, which speeds the game up without a Doom Track.
- **Refined and locked via the macro-loop pass:** base XP reward is fixed and does not decay —
  only the Gold Token does. Decay erodes the bonus, never the guaranteed baseline progress,
  matching the "Carrots, Not Sticks" golden rule more precisely than the original draft
  specified. Concrete Tier 1 quest examples now exist (thematically tied to AGGRO's own IP —
  the Gilded Syndicate, Silas Thorne — rather than placeholder WoW zone names); see
  `gemini_prompt_state_of_the_game.md`-adjacent design notes for the worked examples once the
  macro sim exists to test them.

### 7. Win Condition — the Dungeon Final Exam

Game ends when players defeat the Final Boss Node (e.g. The Deadmines) — a static, monstrous math check (e.g. 50 DMG + 20 Block in a single Party Pull, in one round). Players spend the game building a deck capable of meeting that check, and attempt it whenever ready.

## Deckbuilding & Scaling

Player arcs from Level 1 Adventurer to Level 6 Raider.

- **Starter Deck:** 10 unoptimized cards, heavy on Basic Strike/Basic Block. Establishes the class's baseline math and passive identity (Stances, Spellweaving, Combo Points).
- **Market Row (Gold):** Buying from the Town Market adds tuned, tactical AGGRO-grade cards (Heavy Swing, Fireball) to the deck.
- **Leveling Up (XP):** Turning in Quests grants XP. Leveling lets players **Cull** (permanently destroy) basic starter cards, thinning the deck so Market upgrades draw consistently.

## Class Archetypes (Field-Lever Identity)

QUEST reuses AGGRO's nine classes and their existing role identities, but the field-lever framing above (§4) gives each archetype a distinct *shape* against the Slower-downer/Speeder-upper axis, not just a distinct card list. See `DECK_CONDENSING_GUIDE.md` for how an AGGRO class's kit gets translated into QUEST's condensed 6-card format, and each class's own `sim/condensed_<name>.py` `CARDS` dict for the actual current, authoritative card-by-card values (six classes built so far: Warrior/Wizard/Cleric/Paladin/Rogue/Ranger).

- **Block-sustain (Warrior, Rogue).** Passive Block generation — Warrior's shield/Stance, Rogue's dodge — mitigates the Slog directly. The original framing here was about avoiding Winded/deck pollution (now cut, see §3); the surviving, still-relevant identity is that these classes' failure mode is running out of HP/Block margin, not out of Bag capacity for Food/Potions the way a non-self-sufficient class might be.
- **Glass cannon (Wizard).** ~0 Block. Must OTK or eat unmitigated ATK. Highest outcome variance of any archetype by design — see the Opening Range rule above, which compounds a whiffed round one into a materially worse round two via the Cast Penalty.
- **Bag-loadout flexibility / heal-cost tradeoff (Cleric) — stale, superseded, not yet
  re-derived.** Both bullets here originally described findings from the old AGGRO-scale
  translation (`sim/engine.py`/`sim/simulate.py`, 4+ Bag slots, Bandages, Water, Winded/OOM
  deck-pollution) — a completely different Bag economy than the current locked design (2
  starting slots, Food/Potion, no Winded at all, see §3/§5). That analysis doesn't transfer:
  the specific numbers (5.00 avg pulls, 4 Water) belong to a system that no longer exists, and
  the "heal-cost tradeoff" hypothesis was explicitly about Winded generation, which has been cut
  entirely. Cleric almost certainly still has *some* distinct safety-vs-capacity identity under
  the new Food/Potion/Bag-slot economy — Cleric's in-combat self-heal still exists and still
  reduces Food/Potion dependency relative to Warrior/Wizard/Paladin — but the actual shape needs
  to be re-measured against the new macro sim once it exists, not assumed to carry over.
- **Pet risk (Ranger, Necromancer).** Both classes already have an AGGRO-native summon that intercepts attacks meant for the hero (Ranger's Beast, Necromancer's Boneguard/TORMENT), and both already lose it for "the rest of the encounter" if it drops to 0 HP. Decided: the pet is gone until a Town visit, not just until the hero's next pull — matches AGGRO's original weight rather than trivializing the loss. A future cooldown/token softening short of a full Town visit is still on the table pending real trip-level data. See `OPEN_QUESTIONS.md`.

## Implementation Note

Because QUEST uses AGGRO's card anatomy and deterministic math, it's script-ready the same way AGGRO is — a Monte Carlo sim could tune the economy (Market costs vs. Bag fill-rates) before physical prototyping.
