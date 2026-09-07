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

# Quest -> (node name, zone number), inverted from macro_sim.py's own NODES/NODE_ZONE --
# the real, locked source of truth (DESIGN_DOC.md's "Node/quest table, locked" sections),
# never hand-duplicated here so this can't drift out of sync with the actual node map.
quest_node = {}
quest_zone = {}
for node_name, (tier, quest_name) in M.NODES.items():
    quest_node[quest_name] = node_name
    quest_zone[quest_name] = M.NODE_ZONE[node_name]

def _node_label(node_name):
    return node_name.replace("_", " ").title()

# Quests
for name, data in M.QUESTS.items():
    out["quests"][name] = {
        "tier": "Level 1",
        "zone": quest_zone.get(name),
        "node": _node_label(quest_node[name]) if name in quest_node else None,
        "required": data["required"],
        "base_xp": data["base_xp"],
        "gold_ladder": data["gold_ladder"]
    }

for name, data in M.LEVEL2_QUESTS.items():
    out["quests"][name] = {
        "tier": "Level 2",
        "zone": quest_zone.get(name),
        "node": _node_label(quest_node[name]) if name in quest_node else None,
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
