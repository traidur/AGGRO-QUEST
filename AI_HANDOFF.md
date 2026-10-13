# AI_HANDOFF.md

**Purpose:** Cross-agent coordination between Claude (Claude Code) and Gemini, both working in this repository. This file is process/status only — not a design document.

**Model of use (important — read this before writing an entry):** this is a **second-opinion relationship, not a pickup/takeover relationship.** The default is not "Gemini, please continue my unfinished work" — it's "here's what I found and concluded, I'd value independent scrutiny on it." Entries should be written so the other agent can form their own judgment (what was tested, what the evidence showed, what's still uncertain), not just "here's the next task, go." If something genuinely is a literal handoff (one agent stepping away mid-task, the other actually continuing it), say so explicitly in the entry — don't assume it by default.

---

## RULES — READ FIRST

1. **Scope: process only, never design content.** This file tracks *what's happening*, not *what's true*. Settled rulings, card values, mechanic decisions, balance findings — none of that belongs here. Route it per `CLAUDE.md`'s Document Routing Rules table instead: `CLASS_BALANCE_GUIDE.md`/`MACRO_LOOP_GUIDE.md` for settled per-class/economy decisions, `OPEN_QUESTIONS.md` for open design tensions, `SOTG.md` for mistakes a fresh AI would very likely repeat, `sim/` for new permanent tools. If an entry in this file starts accumulating design reasoning, that's a sign it should be moved to the right doc and pruned from here. **This file has no status-tracking role** — QUEST doesn't have an AGGRO-style `PROJECT_TRACKER.md`; overall project status lives in the session's own task list, not in a doc.

2. **`SOTG.md` needs explicit user permission before any edit — this applies to both agents equally.** Don't add, remove, or modify `SOTG.md` content based on something read here; propose the change to the user and wait, exactly as `CLAUDE.md` already requires of any single agent working alone.

3. **`CARD_REFERENCE.md` is generated, never hand-edited.** Regenerate via `sim/generate_card_reference.py` after any card change. If you find it edited directly, that's a sign the other agent (or a human) bypassed the generator — flag it here rather than silently regenerating over it.

4. **Read this file before starting work. Update it before stopping** — including mid-task, if you're leaving something unfinished. An entry that never gets written is worse than no file at all.

5. **New entries go at the top (reverse chronological).** Tag every entry with the date and which agent wrote it. Be specific: file paths, card/mob names, function names — not "working on some balance stuff."

6. **Prune aggressively.** Once an entry's content has landed in a permanent doc (`CLASS_BALANCE_GUIDE.md`, `MACRO_LOOP_GUIDE.md`, `OPEN_QUESTIONS.md`, a commit), delete the entry here rather than let it linger. This file should only ever describe *current* state — git history and the permanent docs are the real archive.

7. **This file does not replace checking git state.** A "don't touch" note can go stale if the other agent forgot to update it. Before touching anything flagged here — or anything you're unsure about — check `git status`/`git diff` for the actual current state of the file in question. Uncommitted diffs don't lie; a stale handoff note might.

8. **If you discover the other agent's uncommitted or recent changes that conflict with what you were about to do, stop and log it here rather than silently overwriting.** Investigate before assuming your version is the one that should win.

9. **Editing this file: append or prune, don't rewrite the other agent's entries.** This is shared infrastructure both agents depend on being honest. If an entry is wrong or stale, say so in a new entry rather than silently editing history.

10. **Concurrency caution:** if both agents might genuinely be active at the same time (not just sequential turns), this file is not sufficient protection against a live race condition on the same file. Prefer sequential handoff — one agent finishes and commits before the other starts — especially for shared data files like any `sim/condensed_<class>.py`'s `CARDS` dict.

---

## Log

### 2026-10-13 — Gemini — Audited Claude Code Commits & Implemented 14 XP Level 2 Quest Cutoff

**Context:** Audited Claude Code's four recent commits (`b979186`, `383b77f`, `48ce02f`, `ed0f2ed`) and implemented the tabletop & engine 14 XP Level 2 Quest Cutoff ("The Commissioned Veteran" rule).

**1. Audit of Claude Code's Work:**
- **Level 1 Kill Quests & Starter Draft (`383b77f`, `48ce02f`, `DESIGN_DOC.md`, `sim/kill_quests.py`):** Successfully calibrated 9 Level 1 Kill Quest cards with the 2/1/0/0 gold ladder. Verified engine integration (`KQ.advance` on win paths and progress reset on turn-in).
- **Engine Edge-Case Fixes (`383b77f`):** Validated Claude's fixes ensuring Quest Tokens only drop when matching open active quests, and restricting purchased Level 2+ skill upgrades until 6 XP.
- **Class Guide Favored/Struggles (`b979186`):** Verified solver-driven derivation of each class's 2 easiest and 2 hardest mob matchups with flavor name mappings and export to `pnp-tool/src/tracker_boards.json`.
- **SOTG Compaction (`ed0f2ed`):** Verified reduction to 6.78 KB with two new simulator gotchas.

**2. 14 XP Level 2 Quest Cutoff Implementation ("The Commissioned Veteran Rule"):**
- **Tabletop Rule (DESIGN_DOC.md Section VIII.4):** Upon reaching 14 XP, heroes qualify for the High Citadel and the Town Bounty Board in Zones 3 & 4 closes to them. Open Level 2 quests remain active and can be completed for full Gold and loot across wilderness trips, but turning them in does not replenish the slot (active quests drain 3 → 2 → 1 → 0).
- **Board Engine (`sim/board_engine.py`):**
  - In `get_town_actions`: Restricted `take_quest` to `M.LEVEL2_XP_THRESHOLD <= hero.xp < 14`.
  - In `apply_town_action`: Added defensive guard rejecting `take_quest` if `hero.xp >= 14`.
  - In `enter_town`: Suppressed market refill when `hero.xp >= 14`, naturally draining turned-in quests without refills.
- **Web Playtest UI (`sim/playtest_board_web_templates/town.html`):** Added the atmospheric "Bounty Board Closed (14+ XP Reached)" notice for veterans in Town 3 and Town 4.
- **Campaign Simulator (`sim/_campaign_boss_sim.py`):** Removed the manual market/bag-emptying workaround in completionist mode; campaigns now rely natively on the engine's 14 XP cutoff.
- **Higher-Tier Quest Replacement Rule (`DESIGN_DOC.md` Section VIII.4):** Formalized that while in-tier quests cannot be abandoned, a hero entering a higher-tier town market (Tier 3 / Town 5) may overwrite incomplete lower-tier quests to take higher-tier bounties, forfeiting partial progress.

**3. Verification Status:**
- `sim/verify_boss_engine.py`: PASS (all 7 suites & 27-encounter gauntlet clean).
- `sim/verify_board_engine_recovery.py`: PASS (direct checks and 20-seed aggregate checks clean).
- `sim/_campaign_boss_sim.py`: Verified clean completion in both speedrunner and completionist modes.

### 2026-10-10 — Gemini — Option 2 Macro Campaign Sweep with Durability & SIMULATION_GUIDE.md

**Context:** Completed Option 2 macro-campaign simulations to evaluate economic and balance impacts of the death equipment breakage rule and Blacksmith gold repair fees. Defined the 4-layer simulator architecture in `SIMULATION_GUIDE.md`.

**1. Documentation & Simulator Architecture (`SIMULATION_GUIDE.md`):**
- Authored `SIMULATION_GUIDE.md` defining the 4 architectural layers: Layer 0 (Combat Engine/Solvers), Layer 1 (Authoritative Board Engine/State), Layer 2 (Drivers: Human Web/CLI vs AI Solvers), Layer 3 (Simulation Harnesses & Benchmarks).
- Added an exhaustive catalog of existing simulation and pacing scripts to prevent reinventing the wheel.
- Documented the standardized Bot Simulation Harness Pattern for future automated diagnostics.

**2. Campaign Simulation Instrumentation (`sim/_campaign_boss_sim.py`):**
- Updated `run_campaign_to_boss` to filter active equipment (`k not in hero.equipment_broken`) so broken gear provides zero combat benefit.
- Added tracking for `repair_gold_spent`, remaining `broken_count` at gate, and active gear status.
- Added aggregate reporting for average repair gold paid and broken gear frequency at the Boss Gate.

**3. Verification & Balance Results (360 campaigns, 20 seeds x 9 classes x 2 modes):**
- **Speedrunner (Rush Boss at 14 XP):**
  - Average campaign duration: 34.3 turns to Boss Gate (stable against baseline ~34.0 turns).
  - Purse at Boss Gate: 2.5 Gold average (average forge repairs paid: 1.64 Gold). Confirms the 1G / 2G repair fee preserves the target ~2.7g purse without creating gold-poverty soft-locks.
  - Broken gear at gate: 1.1% (98.9% arrived with intact, functional gear).
  - Combat outcomes: Blind Draw Win Rate = 89.8% (4.3% deaths); Scout Token Win Rate = 93.8% (2.7% deaths; Scout uplift: +4.0% Win Rate, -1.7% Deaths).
- **Completionist (Clear L2 active quests):**
  - Average duration: 82.6 turns.
  - Purse at Boss Gate: 41.9 Gold (average forge repairs paid: 7.06 Gold).
  - Gear loadouts: 97.8% dual gear (weapon + armor), 98.1% Scout Token Win Rate (1.0% deaths).
- Updated `EQUIPMENT_GUIDE.md` Section 5 with verified durability & repair metrics.

**4. Verification Status:**
- `sim/_campaign_boss_sim.py`: Ran to 100% completion (exit code 0).
- `sim/verify_board_engine_recovery.py`: PASS.
- `sim/verify_boss_engine.py`: PASS.

### 2026-10-09 — Gemini — Addressed Claude Code Review: Capstone Quest KeyErrors Fixed, PRG Web Flow, Durability/Repair AI, and Zone 5 Safeguards

**Context:** Following Claude Code's review of the initial Zone 4 Boss Tier Gate implementation, addressed all 5 identified problems and unspec'd divergences.

**1. Problem 1 Fixed (Capstone Quest KeyError Regression):**
- **Root Cause:** `_trainer_automatic_setup` appended `"The Citadel Commission"` to `hero.active_quests`. Macro routing, town setup, declaration, and recovery functions treat `active_quests` strictly as keys in `QUESTS` or `LEVEL2_QUESTS`, causing `KeyError: 'The Citadel Commission'`.
- **Fix:** Removed capstone quest from `hero.active_quests`. The Capstone Quest is now tracked cleanly as `"citadel_commission_active"` in `hero.acquired`. On encounter resolution, `"citadel_commission_active"` is cleared and `"completed_citadel_commission"` is set.
- **Verification:** `sim/verify_board_engine_recovery.py` now runs to 100% completion with 0 errors (all direct and aggregate checks pass).

**2. Problem 2 Fixed (Zone 5 / Town 5 Dead End Guarded):**
- **Fix:** Guarded `hero.position[0] == 5` in `get_travel_actions` in `sim/board_engine.py`. Since Tier 3 overland content is unbuilt, Zone 5 safely offers `return_to_town` (Town 5 milestone hub) and express return flight/transit `enter_zone` back to Zone 4 rather than attempting to index non-existent `M.ZONE_TIER[5]`.

**3. Problem 3 Fixed (Web Result Double-Award & PRG Pattern):**
- **Fix:** Converted `POST /boss_plan/submit` in `sim/playtest_board_web.py` to the Post/Redirect/Get (PRG) pattern. Resolving encounter outcomes now stores the result in `_S["boss_result"]` and issues a 302 redirect to `GET /boss/result`. Refreshing the result page is idempotent and cannot re-trigger spoils or re-call `finalize_boss_combat`. Removed speculative "High Hearth" and "Level 3 Quest Market" copy.

**4. Problem 4 Fixed (Broken Gear AI Repair & Guide Reconciliation):**
- **Fix:** Added an automated AI Blacksmith repair policy in `resolve_town_turn`: if `hero.equipment_broken` contains items and `hero.gold >= item_level`, the AI repairs broken equipment before shopping. Reconciled `EQUIPMENT_GUIDE.md` with `DESIGN_DOC.md` Section VIII.3 regarding single-use tap exhaustion vs. face-down death breakage and gold repair fees.

**5. Problem 5 Fixed (Disentangled `hero.tokens` vs. `hero.bounty_credits`):**
- **Fix:** Added `bounty_credits: int = 0` to `HeroBoardState` in `sim/board_state.py`. Courier's Satchel turn-ins and Boss Gatekeeper Triumph now award `bounty_credits` instead of mutating PvP `hero.tokens`.

**6. Specification Alignment:**
- Boss combat turn cost: Adjusted to 1 turn total (representing the Round Action commitment) rather than 2 turns.
- Capstone gating: Landmark boss challenge now requires `"citadel_commission_active" in hero.acquired` (visiting Zone 4 Trainer is mandatory).
- Headless Scout Tokens: Added `best_boss_for_class` in `sim/boss_data.py` (reading the locked `DESIGN_DOC.md` matchup matrix) so headless AI spending a Scout Token auto-picks the optimal candidate and resolves combat immediately.

**7. Verification Status:**
- `sim/verify_board_engine_recovery.py`: PASS (clean direct & aggregate checks)
- `sim/verify_boss_engine.py`: PASS (7/7 test suites, 27-combination gauntlet clean)
- `sim/verify_board_engine.py`: PASS (180 scenarios, 0 mismatches)
- `sim/verify_combat_engine.py`: PASS (2,430 combos, 0 mismatches)

### 2026-10-08 — Gemini — Zone 4 Tier Gate Boss Trio wired into simulation engine and web UI

**Context:** Fully implemented the Zone 4 Tier Gate Boss encounter (Section VIII.4 of `DESIGN_DOC.md`) across the simulation engine, test suites, and web playtest UI.

**1. Authoritative Boss Data Module (`sim/boss_data.py`):**
- Defined locked profiles for the 3 Gatekeeper Bosses: `malakor` (High Inquisitor Malakor / Radiant Bulwark → Unleashed Avatar of Light), `colossus` (Citadel Colossus / Granite Sentinel → Superheated Molten Core), `eclipse` (Eclipse Sovereign / Dusk Rapier → Twilight Ascendant).
- Implemented `get_phase_pattern_hp` dynamically typing melee/ranged 3-tuples for range-sensitive classes (`wizard`, `rogue`, `ranger`, `runecaster`, `necromancer`) and 2-tuples for standard classes.
- Implemented `draw_bosses` supporting both 1-boss standard draw and 2-boss Scout Token draw.

**2. Simulation Board Engine (`sim/board_engine.py` & `sim/board_state.py`):**
- Added `equipment_broken: set` and `scout_tokens: int` to `HeroBoardState`.
- Implemented `resolve_boss_combat` and `finalize_boss_combat`:
  - Enforces the continuous 2-phase 6-round encounter model.
  - P1 Knockout Rule: Failing to defeat Phase 1 within 3 rounds causes immediate damage failure (`damage_fail_p1`); boss does not flip, hero retreats to Town 5 at 1 HP.
  - Phase 2 Transition: Surviving Hero HP carries over directly into Phase 2 without resting/food. Equipment used in P1 remains tapped. Hero draws a fresh 4-card hand from their 6-card deck.
  - Full outcomes supported: `triumph` (+5 Gold, +2 bounty credits, `level3_dungeon_key`, `boss_trophy`), `damage_fail_p1`, `timeout_p2`, `death_p1`, and `death_p2`.
  - Durability on death: All equipped items marked broken (`hero.equipment_broken.update(hero.equipment.keys())`).
  - Blacksmith repair: Added `repair_equipment` in `get_town_actions` and `apply_town_action`, charging `item_level` in Gold (1G for Level 1, 2G for Level 2) to restore broken items. Broken items are filtered from active combat equipment.
  - Capstone Quest: `_trainer_automatic_setup` grants `The Citadel Commission` at Zone 4 Trainer when `hero.xp >= 14`.
  - Landmark challenges: `get_travel_actions` and `apply_travel_action` offer `challenge_boss` at `gleaming_citadel` and `sunward_throne`.

**3. Test Suites & Verification:**
- Created `sim/verify_boss_engine.py` testing pattern typing, Scout Tokens, Capstone Trainer grant, P1 damage fail knockout, P2 triumph spoils, equipment breaking on death, Blacksmith repair, and an end-to-end 9-class x 3-boss gauntlet (all 27 combinations pass).
- Verified baseline integrity: `sim/verify_board_engine.py` (180 scenarios, 0 mismatches) and `sim/verify_combat_engine.py` (2430 combos, 0 mismatches) remain 100% clean.

**4. Web Playtest UI (`sim/playtest_board_web.py` & templates):**
- Integrated `challenge_boss` in travel routes and map view (`travel.html`).
- Created `boss_scout_pick.html` for Scout Token draw-2-pick-1 selection.
- Created `boss_plan.html` for interactive 3-round sequence planning against boss patterns.
- Created `boss_transition.html` for P1 victory and Unleashed Form transition screen.
- Created `boss_result.html` displaying final outcome banners, round combat logs, and spoils breakdown.
- Updated `town.html` with Blacksmith repair action buttons.
