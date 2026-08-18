import sys
import os
import json

sim_path = os.path.join(os.path.dirname(__file__), '..', 'sim')
sys.path.append(sim_path)

import condensed_trip as T
import _party_elite_test as E

mobs = []

for name, (pattern, hp) in T._RAW_MOBS.items():
    mob_type = T._MOB_TYPES.get(name, "melee")
    mobs.append({
        "name": name,
        "tier": "Standard",
        "hp": hp,
        "type": mob_type,
        "pattern": pattern
    })

for name, (pattern, hp) in E.ELITES.items():
    mobs.append({
        "name": name,
        "tier": "Elite",
        "hp": hp,
        "type": "melee",
        "pattern": [(r[0], r[1]) for r in pattern]
    })

out_path = os.path.join(os.path.dirname(__file__), "src", "mobs_text.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(mobs, f, indent=2)

print(f"Exported mobs text to {out_path}")
