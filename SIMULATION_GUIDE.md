# SIMULATION_GUIDE.md: QUEST Simulation & Bot Harness Architecture

## Overview & Purpose

QUEST relies on empirical, exact-enumeration simulations rather than theoretical averages or design intuition. Every balance metric, economic cost, and combat survival rate is derived from reproducible simulation runs.

This guide defines:
1. **The Architectural Hierarchy (The 4 Layers)** — how pure combat math, board state, user drivers (Human vs. Bot), and simulation harnesses fit together.
2. **Catalog of Existing Simulators** — which script to use for what question, avoiding "reinventing the wheel."
3. **The Standard Bot Simulation Harness Pattern** — the required pattern when writing any new bot simulation or benchmark.

---

## 1. The Architectural Hierarchy

```
+--------------------------------------------------------------------------+
| Layer 3: Simulation & Diagnostic Harnesses                              |
|   - sim/_campaign_boss_sim.py (End-to-End Campaign to Boss Gauntlet)     |
|   - sim/_milestone_sim.py (Progression & Economy Milestones)             |
|   - sim/macro_sim.py (90-Turn Decay, Attrition, Risk Stress Tests)       |
|   - sim/_level2_pacing.py, sim/quest_cost_gauntlet.py                    |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
| Layer 2: Player & Agent Drivers                                          |
|   - Human Web UI: sim/playtest_board_web.py (Browser UI, PRG pattern)    |
|   - Human CLI:    sim/playtest_board_cli.py (Interactive Terminal)       |
|   - Headless AI:  best_line_for_hand (Combat Solver), resolve_town_turn  |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
| Layer 1: Authoritative Board Engine & State                              |
|   - sim/board_state.py (HeroBoardState, BoardState, Decks, Bags)         |
|   - sim/board_engine.py (Town, Travel, Death, Recovery, Boss Resolution) |
|   - sim/equipment_data.py (Crafting, Recipes, Armory Markets)           |
|   - sim/boss_data.py (Tier Gatekeeper Boss Profiles, Matchup Tables)    |
+--------------------------------------------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
| Layer 0: Pure Combat Engine & Card Solvers                               |
|   - sim/combat_engine.py (Single-source-of-truth round & action rules)   |
|   - sim/condensed_trip.py (Exact-enumeration best_line_for_hand solver)  |
|   - sim/condensed_<class>.py (Per-class base cards, stances, HP)         |
|   - sim/equipment_solver.py (Equipment rider integration into combat)    |
+--------------------------------------------------------------------------+
```

### Key Architectural Invariant: Shared Engine, Pluggable Driver
- **The Core Rule:** All game state transitions live strictly in **Layer 1** (`sim/board_engine.py`) and **Layer 0** (`sim/combat_engine.py`).
- **Human vs. Bot:**
  - When a human plays via Web (`playtest_board_web.py`) or CLI (`playtest_board_cli.py`), choices are captured from forms/stdin and passed to `board_engine.py` via a callback `decide_fn`.
  - When a bot runs headlessly, `decide_fn` is omitted (`None`), causing `board_engine.py` to invoke the optimal mathematical solver (`best_line_for_hand`).
- **Zero Frontend Drift:** Web routes and CLI menus must **never** reimplement phase logic, combat rounds, or rewards. They must strictly call `board_engine` functions.

---

## 2. Catalog of Existing Simulators & Scripts

Before writing a new test script, consult this catalog:

| Script Path | Scope & Purpose | Input Parameters | Key Outputs |
| :--- | :--- | :--- | :--- |
| `sim/_campaign_boss_sim.py` | **Full End-to-End Campaign** (L1 start → L2 leveling → Zone 4 Boss Gate & Boss Gauntlet). Evaluates Speedrunner vs. Completionist strategies. | Class, Mode (`speedrunner`/`completionist`), Seeds | Pacing (turns), Gold in purse, Deaths, Broken gear rate, Boss Win% (Blind vs Scout). |
| `sim/_milestone_sim.py` | **Macro Progression to XP Thresholds** (e.g., 7 XP L2 or 14 XP Boss Gate). Evaluates crafting, town shopping, and loot flow. | Class, Target XP, Seeds | Turns to threshold, Gold, Material counts, Equipment crafted. |
| `sim/macro_sim.py` | **Foundational 90-Turn Macro Simulator**. Tests bag Tetris, food/potion economy, quest decay, and risk exposure. | Class, Strategy (`food_only`, etc.), Risk Persona | Quests/turn, Death rate, Worst decay stage, Gamble counts. |
| `sim/_level2_pacing.py` | **Turns to Level 2 Benchmark**. Measures exact solo and competitive pacing to 6 XP. | Class / Party list, Seeds | Mean/Median/Stdev turns to L2, group contention drag. |
| `sim/_contention_investigation.py` | **Multiplayer Contention Tracing**. Traces contested node frequency across 2, 3, and 4 hero parties. | Group size (2-4), Seeds | Contention count, node declaration volume, turn drag. |
| `sim/_bag_model_baseline.py` | **Inventory & Bag Capacity Diagnostic**. Tests 6-slot bag capacity, deadlock checks, and loot accumulation. | Class, Turns, Seeds | Bag room deadlocks, slot utilization, flee rates. |
| `sim/quest_cost_gauntlet.py` | **Isolated Quest Opportunity Cost**. Measures pulls and trips spent per quest requirement size. | Required loot count, Class | Pulls/trip overhead, death overhead per quest requirement. |
| `sim/sweep_equipment_full.py` | **Per-Recipe Equipment Balance Sweep**. Tests survival curves across 9 classes x all items x all mobs. | Class, Equipment loadout | Crack point HP, survival curves across mob roster. |
| `sim/_run_rebalanced_sweep.py` | **Tier Gate Boss Matchup Matrix**. Tests the 3 asymmetric bosses across all 9 classes. | Class, Boss profiles | 3-way boss spread, win rates across kit archetypes. |
| `sim/verify_board_engine_recovery.py` | **Regression Suite: Death & Corpse Recovery**. Proves corpse locking, recovery pulls, and bag unlocks. | Automated test suite | PASS / FAIL assertion against engine recovery invariants. |
| `sim/verify_boss_engine.py` | **Regression Suite: Boss Mechanics**. Proves 2-phase combat, P1 knockout, Scout Tokens, durability breakage, and forge repairs. | Automated test suite | PASS / FAIL assertion across 7 boss test suites. |

---

## 3. The Standard Bot Simulation Harness Pattern

When writing or extending a headless bot simulator, follow this standardized harness pattern:

### Step 1: Initialize Deterministic State
Always initialize `HeroBoardState` and `BoardState` using explicit seeds. Never rely on global unseeded `random`.

```python
import random
import board_engine as BE
import board_state as B
import macro_sim as M

def run_single_campaign(class_name, seed):
    rng = random.Random(seed)
    mod = M.CARD_SOURCE[class_name]
    max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
    
    # 1. Standard Hero State
    hero = B.HeroBoardState(
        class_name=class_name,
        hp=max_hp,
        max_hp=max_hp,
        position=(1, "town"),
        bag=[None] * M.BAG_SIZE,
        locked=[False] * M.BAG_SIZE
    )
    M._add_food(hero.bag, hero.locked)
    
    # 2. Skill Purchase Queue & Decks
    if class_name in M.LEVEL2_PURCHASED_ORDER:
        hero.skill_purchase_order = list(range(len(M.LEVEL2_PURCHASED_ORDER[class_name])))
        rng.shuffle(hero.skill_purchase_order)
    purchase_queue = M._build_purchase_queue(class_name, 0)
    
    level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
    loot_decks = {1: B.LootDeck.new(1, rng), 2: B.LootDeck.new(2, rng)}
    
    board = B.BoardState(
        mode="solo",
        heroes=[hero],
        zones={},
        level_decks=level_decks,
        loot_decks=loot_decks
    )
    board.setup_quests(rng)
```

### Step 2: Drive the Macro Loop via Authoritative Engine Calls
Never manually subtract gold, increment turns, or mutate decks. Delegate entirely to `board_engine`:

```python
    # Initial Town turn
    BE.resolve_town_turn(hero, class_name, "food_only", purchase_queue, "save", rng, board)
    
    # Main Campaign Loop
    while hero.xp < 14 and hero.turns < 90:
        quest_pool = M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS
        valid_zones = M.LEVEL2_QUEST_ZONES if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.LEVEL1_QUEST_ZONES
        
        # Execute Solo Trip (Field travel, node pulls, combat, corpse recovery)
        trip_res = BE.run_solo_trip(
            hero, class_name, quest_pool, valid_zones, board, rng,
            risk_tolerance=M.RISK_TOLERANCE,
            risk_tolerance_base=M.RISK_TOLERANCE_BASE,
            risk_only_as_last_resort=True
        )
        
        # Post-trip handling
        if trip_res["recovered"]:
            BE.apply_recovery_post_processing(hero)
        if not trip_res["alive"]:
            BE.apply_death_post_processing(hero, quest_pool, trip_res["death_node"])
            
        # Town phase (Food restocking, repairs, skill training)
        BE.resolve_town_turn(hero, class_name, "food_only", purchase_queue, "save", rng, board)
```

### Step 3: Handle Active Equipment vs. Broken Equipment
Equipment broken on death (`hero.equipment_broken`) does not confer combat benefits. Always filter active equipment before evaluating combat or reporting loadouts:

```python
    active_equipment = {
        slot: data for slot, data in hero.equipment.items()
        if slot not in hero.equipment_broken
    }
```

### Step 4: Aggregate Distributions, Not Just Means
QUEST design principles mandate checking distributions, crack points, and failure cases (e.g. death rates, worst decay stage), never just raw averages:
- Report **Distributions:** Percentages across tiers, gear configurations, and outcomes.
- Report **Failure Rates:** Deaths per run, damage fails, timeouts, and soft-lock counts.
- Compare against locked baselines documented in `DESIGN_DOC.md` and `EQUIPMENT_GUIDE.md`.

---

## 4. Engineering Discipline & Agent Boundaries

1. **Native & MCP Tools Only:** Never run shell commands (`cat`, `grep`, `dir`, ad-hoc python scripts) to view or manipulate files; use native tools (`view_file`, `replace_file_content`) or MCP filesystem tools.
2. **Never Edit Generated Docs:** `CARD_REFERENCE.md` is auto-generated by `sim/generate_card_reference.py`. Never edit it manually.
3. **Respect SOTG.md:** Edits to `SOTG.md` require explicit user permission.
4. **Coordinate via AI_HANDOFF.md:** Read `AI_HANDOFF.md` before starting, update it before stopping, maintain reverse-chronological order, and keep it focused strictly on process, testing evidence, and second opinions.
