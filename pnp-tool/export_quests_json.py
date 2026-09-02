import os
import json
import sys

sim_path = os.path.join(os.path.dirname(__file__), '..', 'sim')
sys.path.append(sim_path)

import macro_sim as M

out = {
    "quests": {},
    "consumables": {},
    "loot": {}
}

# Quests
for name, data in M.QUESTS.items():
    out["quests"][name] = {
        "tier": "Level 1",
        "required": data["required"],
        "base_xp": data["base_xp"],
        "gold_ladder": data["gold_ladder"]
    }

for name, data in M.LEVEL2_QUESTS.items():
    out["quests"][name] = {
        "tier": "Level 2",
        "required": data["required"],
        "base_xp": data["base_xp"],
        "gold_ladder": data["gold_ladder"]
    }

# Consumables
consumables_info = {
    "Food": {"cost": M.FOOD_COST, "effect": "Fully restores HP.\nCan be eaten anywhere."},
    "Potion": {"cost": M.POTION_COST, "effect": f"Restores {M.POTION_HEAL} HP mid-trip."},
    "Scroll of Vanquishing": {"cost": M.SCROLL_COST, "effect": "Guaranteed win, no combat played.\nStandard-tier mobs only."},
    "Smoke Bomb": {"cost": M.SMOKE_BOMB_COST, "effect": "Guaranteed flee, no reward.\nCan back out of a Border toll."},
    "Preserving Charm": {"cost": M.PRESERVING_CHARM_COST, "effect": "Resets one active quest's\ndecay stage to 0 at Town."}
}
for name, info in consumables_info.items():
    out["consumables"][name] = info

# Loot
out["loot"] = {
    "Red Loot": {"color": "#b71c1c", "desc": "Quest Loot Token"},
    "Blue Loot": {"color": "#0d47a1", "desc": "Quest Loot Token"},
    "Green Loot": {"color": "#1b5e20", "desc": "Quest Loot Token"}
}

with open(os.path.join(os.path.dirname(__file__), 'src', 'quests_items.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2)

print("Exported quests_items.json successfully.")
