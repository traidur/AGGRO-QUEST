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
- **The Slog (failure):** Fail to kill in one hand → mob strikes. Take (ATK − your Block) as HP damage, plus a Fatigue/Durability wound. Mob survives; you must finish it next round, ruining tempo.
- **Melee vs. Ranged:** Melee decks (Warrior/Rogue) have Block to mitigate the Slog. Casters (Wizard) have ~0 Block — they must OTK or get crushed by unmitigated ATK.

### 3. The Three Pillars of Attrition (field limits)

Taking damage or pushing your luck clogs your deck with dead weight, pushing players back to town naturally.

1. **Health (HP):** Hard limit, tracked on Hero Board. 0 HP = dead.
2. **Winded / OOM (sustain):** Unplayable dead weight. Gained from heavy spells or chain-pulling. Cleared via a Rest action + consuming a Food/Water token from the bag.
3. **Durability (gear damage):** Passive debuffs (e.g. −1 DMG on attacks). Gained from massive unblocked hits or failed OTKs. Cannot be cleared in the field — only repaired at a Town Blacksmith for Gold.

### 4. Bag Tetris (the pacing engine)

Each player has exactly **8 Bag Slots**.

- Consumables (Food/Bandages) and Loot (Quest Items/Vendor Trash) share the same 8 slots.
- **Push-your-luck puzzle:** 6 Bandages = safe but only 2 loot slots, forces an early return. 0 Bandages = vacuum up loot, but highly vulnerable to Winded/Durability cascades.
- **Currency Cap:** Currencies don't convert. Tier 3 cards cost Gold; you cannot hold enough Tier 1 Copper to buy them. Forces players into harder zones for denser wealth.

### 5. Decaying Bounties (the hidden stick)

Prevents safe turtling via FOMO instead of a clock.

- **Quest Log:** Players hold exactly 3 Quests at all times, forcing routes across multiple map nodes.
- **Bounty Tokens:** A drawn Quest gets a Gold Token (large Gold/XP bonus).
- **Decay:** Every time a player's pawn touches a Town Node, any Quest in the log that isn't ready to turn in downgrades (Gold → Silver → Bronze → nothing).
- **Result:** Players take bigger field risks to complete all 3 Quests in one trip and bank the Gold tier, which speeds the game up without a Doom Track.

### 6. Win Condition — the Dungeon Final Exam

Game ends when players defeat the Final Boss Node (e.g. The Deadmines) — a static, monstrous math check (e.g. 50 DMG + 20 Block in a single Party Pull, in one round). Players spend the game building a deck capable of meeting that check, and attempt it whenever ready.

## Deckbuilding & Scaling

Player arcs from Level 1 Adventurer to Level 6 Raider.

- **Starter Deck:** 10 unoptimized cards, heavy on Basic Strike/Basic Block. Establishes the class's baseline math and passive identity (Stances, Spellweaving, Combo Points).
- **Market Row (Gold):** Buying from the Town Market adds tuned, tactical AGGRO-grade cards (Heavy Swing, Fireball) to the deck.
- **Leveling Up (XP):** Turning in Quests grants XP. Leveling lets players **Cull** (permanently destroy) basic starter cards, thinning the deck so Market upgrades draw consistently.

## Implementation Note

Because QUEST uses AGGRO's card anatomy and deterministic math, it's script-ready the same way AGGRO is — a Monte Carlo sim could tune the economy (Market costs vs. Bag fill-rates) before physical prototyping.
