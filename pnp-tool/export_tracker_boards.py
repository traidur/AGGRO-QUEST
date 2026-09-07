"""
Exports one printable hero tracker board per class -- HP track, Gold/XP/Turn boxes, the
Level 1 and Level 2 Class Guide (best/worst 2 matchups by cost%), and 3 colored quest-card
slots (Red/Green/Blue, poker-card sized) for DESIGN_DOC.md's locked tracker-board mechanic
(Section VIII, "Hero tracker board").

Matchup data is computed the same way playtest_board_web.py's live Class Guide modal does --
class_mob_matchup_chart.py's matchup_table()/the same best_1/best_2/worst_1/worst_2 collapse
logic -- never hand-typed, so this can't drift from the real solver the way an earlier frozen
snapshot did (see that module's own docstring for the incident).

Run: python export_tracker_boards.py (from pnp-tool/), writes src/tracker_boards.json.
"""
import os
import sys
import json

sim_path = os.path.join(os.path.dirname(__file__), '..', 'sim')
sys.path.append(sim_path)

import class_mob_matchup_chart as MC

def _matchup_summary(per_mob):
    """Same collapse logic as playtest_board_web.py's own _matchup_summary -- kept identical
    on purpose so the printed board and the live web Class Guide never show different numbers
    for the same class/level."""
    by_cost = sorted(per_mob.items(), key=lambda kv: kv[1][0])
    (b1, (b1c, _)), (b2, (b2c, _)) = by_cost[0], by_cost[1]
    (w2, (w2c, _)), (w1, (w1c, _)) = by_cost[-2], by_cost[-1]
    return {"best_1": b1, "best_1_cost": round(b1c, 1), "best_2": b2, "best_2_cost": round(b2c, 1),
            "worst_1": w1, "worst_1_cost": round(w1c, 1), "worst_2": w2, "worst_2_cost": round(w2c, 1)}

matchup_l1 = {cls: _matchup_summary(per_mob) for cls, per_mob in MC.matchup_table(level=1).items()}
matchup_l2 = {cls: _matchup_summary(per_mob) for cls, per_mob in MC.matchup_table(level=2).items()}

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
