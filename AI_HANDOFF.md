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

### 2026-10-08 — Gemini — Media-server workspace transition, git repo repair, and current state

**Context:** The user transitioned active work to a secondary computer (`media-server`) hosting the workspace via a Google Drive-synced directory from the gaming laptop (`MG-VCP15`). MCP `filesystem` tools were configured to eliminate shell prompt overhead.

**1. Git repository repaired on media-server:**
- **Issue:** `git status` failed with `fatal: bad object HEAD` and fetch failed with `fatal: bad object refs/desktop.ini`.
- **Root Cause:** Google Drive created `desktop.ini` files inside `.git/refs/` and subdirectories (`refs/heads`, `refs/remotes`, etc.). Git parsed `desktop.ini` as invalid hex ref hashes. Furthermore, loose object `344995a5` created on the laptop had not synced across Drive.
- **Resolution:** Removed `desktop.ini` files from `.git/refs/` and fetched the missing pack objects directly from remote `origin/master` (GitHub). Added `desktop.ini` to `.gitignore`. Git repository is fully synchronized and healthy on `origin/master`.

**2. Current working tree & locked design state:**
- The working tree incorporates uncommitted design locks from 2026-10-06 in `DESIGN_DOC.md` and `EQUIPMENT_GUIDE.md`:
  - **Town Armory (Ready-Made Market):** Town 2 (Grade 1 items: 6G weapons, 7G armor) and Town 4 (Grade 2 items: 10G weapons, 12G armor). Display size `Heroes + 1` cards with free refresh once per visit.
  - **Economy:** Bag Upgrade repriced 16G → 12G; gathering token sell-back locked at flat 1G each.
  - **Tabletop Tracker Board:** 3 Equipment Slots (Weapon, Armor, Trinket) face-up, 90° tap activation, untap in Town; tucked backpack margin for unequipped items consuming 1 Bag slot via 1×1 "Packed Gear" tokens (swapping is strictly Town-only).
  - **Equipment Recipes & Pricing:** Locked in `sim/equipment_data.py` following 360-run campaign verification (`sim/_campaign_boss_sim.py`).
- Pre-existing commit `344995a5` already locked the Level 2 quest ladder (4-6-9-12), 3x3 bag food fix, and rebalanced Tier Gate Boss matrix (81.1% roster average across Malakor, Citadel Colossus, and Eclipse Sovereign) in `DESIGN_DOC.md` Section VIII.4.

**3. Next implementation roadmap:**
- **Tier Gate Boss Engine Integration:** Standalone sweep scripts (`sim/_boss_phase_sim.py`, `sim/_campaign_boss_sim.py`) proved the boss numbers. The 14 XP gate, Scout Tokens, and 2-phase combat rules must now be wired into `sim/board_engine.py` and visualized in `sim/playtest_board_web.py`.
- **Level 3 Progression:** Explore "Always-Available" Exhaustibles in `OPEN_QUESTIONS.md`.

**Don't touch:** `DESIGN_DOC.md` and `EQUIPMENT_GUIDE.md` contain active 2026-10-06 locks being committed alongside this handoff update.
