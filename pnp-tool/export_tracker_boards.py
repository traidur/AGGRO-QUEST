"""
Exports one printable hero tracker board per class -- HP track, Gold/XP/Turn boxes, the
Level 1 and Level 2 Class Guide (Favored/Struggles lists, by flavor name), and 3 colored
quest-card slots (Red/Green/Blue, poker-card sized) for DESIGN_DOC.md's locked tracker-board
mechanic (Section VIII, "Hero tracker board").

Favored/Struggles come straight from class_mob_matchup_chart.class_guide() -- the same call
playtest_board_web.py's live Class Guide modal makes -- never hand-typed and no longer
duplicated, so this can't drift from the real solver or from the web guide (see that module's
docstring and CLASS_BALANCE_GUIDE.md, "Favored and Struggles derivation").

Run: python export_tracker_boards.py (from pnp-tool/), writes src/tracker_boards.json.
"""
import os
import sys
import json

sim_path = os.path.join(os.path.dirname(__file__), '..', 'sim')
sys.path.append(sim_path)

import class_mob_matchup_chart as MC

matchup_l1 = MC.class_guide(level=1)
matchup_l2 = MC.class_guide(level=2)

out = {"classes": {}}
for cls, (mod, has_stance, max_hp, mob_key) in MC.SPECS.items():
    out["classes"][cls] = {
        "max_hp": int(max_hp),
        "matchup_l1": matchup_l1[cls],
        "matchup_l2": matchup_l2[cls],
    }

with open(os.path.join(os.path.dirname(__file__), 'src', 'tracker_boards.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2)

print("Exported tracker_boards.json successfully.")
