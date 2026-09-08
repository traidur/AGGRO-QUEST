# Equipment System Handoff (Audit Ready)

This document outlines the complete teardown and rebuild of the Tier 1 Equipment system following the previous audit. All structural damage to the combat engine has been reverted, the original design constraints have been respected, and the physical tabletop presentation has been finalized.

## 1. Engine Cleanup & Revert
*   **The Revert:** `sim/combat_engine.py` was reverted to its locked `e3d7460` state. The slow, 646ms recursive action search was completely deleted. The downward `import macro_sim` layering violation was removed.
*   **The Fix:** Instead of branching the action tree, equipment logic is now handled by `scratch_equipment_solver.py:best_line_with_equipment`. This is a thin wrapper that calls the original, verified `best_line_for_hand` solvers. It calculates the optimal equipment activation round (`0`, `1`, `2`, or `None`) by looping `apply_equipment_mechanics` over the already-optimized combat permutations. This perfectly preserves the solver architecture while maintaining sub-15ms speeds.
*   **Cross-Round State:** `Sunder` (persistent damage) and `Persistent` (carryover block) are now tracked cleanly in an external `eq_state` dictionary on the `PullState`, meaning the opaque `RoundState` logic inside the 9 class modules didn't have to be polluted or rewritten.

## 2. The Modular Crafting Data (Base + Ingredient)
The hardcoded 14-item list was deleted. The system is now driven by `sim/equipment_data.py`, which defines 7 **Bases** and 9 **Ingredients**. The engine dynamically generates valid combinations using a strict class-gating matrix:

**Armor Gating:**
*   **Light Armor:** Necromancer, Wizard, Cleric (Allowed: `Reinforced`, `Elusive`)
*   **Medium Armor:** Runecaster, Rogue, Ranger, Druid (Allowed: `Reinforced`, `Elusive`, `Thorns`)
*   **Heavy Armor:** Paladin, Warrior (Allowed: `Reinforced`, `Thorns`, `Persistent`)

**Weapon Gating & Scaling:**
*   **1-Hander / Wand** (Cost: 2 materials): Standard impact. Allowed: `Honed` (+1 DMG), `Pierce` (Ignore 2 Block).
*   **2-Hander / Staff** (Cost: 3 materials): High impact. Allowed: `Honed` (+2 DMG), `Ruthless` (Prevent DMG on kill), `Sunder` (+1 DMG to all rounds).
*   **Class Restrictions:** Magic classes get Wands/Staves. Melee classes get 1H/2H. Druid gets all four. 
*   **Flavor Gating:** `Blessed` (+2 Heal) is restricted strictly to Staves. `Ruthless` is restricted strictly to 2-Handers. 

## 3. Tier-Based Equipment Progression
To prevent recipe/card bloat across 6 Levels, crafted gear is compressed into **Tiers** (Tier 1 = Levels 1 & 2). 

Instead of printing Level 1 versions and Level 2 versions of every item, the Tier 1 Deck is split internally by mechanic complexity:
*   **Early Tier 1 (Level 1 Mats Only):** Bread-and-butter stat boosts. `Honed`, `Reinforced`, `HoT`. A Warrior can build a Honed 1-Hander and Reinforced Plate at Level 1.
*   **Advanced Tier 1 (Combo: Lvl 1 + Lvl 2 Mats):** Complex, game-changing mechanics. `Pierce`, `Ruthless`, `Sunder`, `Elusive`, `Thorns`, `Persistent`. You must level up to Level 2 and harvest advanced materials to unlock these mechanics. 

## 4. Physical Tabletop Presentation
We abandoned the "put a generic token on your board" idea because it strips out the RPG flavor. Instead, we bifurcated the physical item decks:

*   **The Crafting Deck:** Fully printed, named cards (e.g., *"Honed Crag-Iron Blade"*). The material cost is printed directly on the card. Players browse this deck while in Town. Thanks to the Tier compression, the physical PnP generator only needs to print ~34 cards per Tier.
*   **The Treasure Deck:** Fully printed, unique loot drops (e.g., *"The Ashbringer"*). These have **no material costs** printed on them—only a Gold Value. They are drawn randomly when defeating Elites, or sold dynamically in Town for pure Gold. 

## 5. Outstanding Items / Next Steps
*   `Trinkets` remain undercooked (only offering a basic `HoT`), and `Death Pact` was removed to prevent colliding with the Necromancer's class identity.
*   The final mathematical Equilibrium Sweep (verifying that +4 Block on a Paladin doesn't make them mathematically immortal against Tier 1 Elites) needs to be run using the newly restored `verify_combat_engine.py` wrapper.
