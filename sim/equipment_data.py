# Equipment definitions for Base + Ingredient crafting system.

# Base material follows what the Base actually is thematically:
# 1-Hander/2-Hander/Heavy Armor are metal (Ore).
# Wand/Staff are wooden implements (Herb).
# Light/Medium Armor are cloth/leather (Skin).
#
# Pure-Tier Rule & Material Substitution (Locked 2026-09-28, see EQUIPMENT_GUIDE.md Section 6):
# Grade 1 recipes require Grade 1 gathering materials as their baseline.
# Grade 2 recipes require Grade 2 gathering materials as their baseline.
# Any requirement defines the MINIMUM tier of that material category (Ore, Herb, Skin) needed.
# Higher-tier items can always satisfy lower-tier requirements.
BASES = {
    "1-Hander": {
        "slot": "weapon",
        "costs": {1: {"Crag-Iron": 1}, 2: {"Sun-Copper": 1}},
        "cost": {"Crag-Iron": 1},
        "allowed_classes": ["warrior", "paladin", "rogue", "ranger", "runecaster", "druid"],
    },
    "2-Hander": {
        "slot": "weapon",
        "costs": {1: {"Crag-Iron": 2}, 2: {"Sun-Copper": 2}},
        "cost": {"Crag-Iron": 2},
        "allowed_classes": ["warrior", "paladin", "rogue", "ranger", "runecaster", "druid"],
    },
    "Wand": {
        "slot": "weapon",
        "costs": {1: {"Snap-Root": 1}, 2: {"River-Mint": 1}},
        "cost": {"Snap-Root": 1},
        "allowed_classes": ["wizard", "cleric", "necromancer", "druid"],
    },
    "Staff": {
        "slot": "weapon",
        "costs": {1: {"Snap-Root": 2}, 2: {"River-Mint": 2}},
        "cost": {"Snap-Root": 2},
        "allowed_classes": ["wizard", "cleric", "necromancer", "druid"],
    },
    "Light Armor": {
        "slot": "armor",
        "costs": {1: {"Scavenged Pelt": 1}, 2: {"Bristle-Pelt": 1}},
        "cost": {"Scavenged Pelt": 1},
        "allowed_classes": ["wizard", "cleric", "necromancer"],
    },
    "Medium Armor": {
        "slot": "armor",
        "costs": {1: {"Scavenged Pelt": 1}, 2: {"Bristle-Pelt": 1}},
        "cost": {"Scavenged Pelt": 1},
        "allowed_classes": ["rogue", "ranger", "runecaster", "druid"],
    },
    "Heavy Armor": {
        "slot": "armor",
        "costs": {1: {"Crag-Iron": 1}, 2: {"Sun-Copper": 1}},
        "cost": {"Crag-Iron": 1},
        "allowed_classes": ["warrior", "paladin"],
    },
}

# "grade" (1 or 2) AND the Gold price both come from the 2026-09-08 balance sweep in
# EQUIPMENT_SWEEP_RESULTS.md -- Gold is set proportional to each ingredient's measured
# cross-class average win-rate uplift (a rough "1 Gold per ~2.2 percentage points" conversion,
# floored at 1), not assigned by feel. Grade 1 ingredients use Tier-1 materials; Grade 2
# ingredients use Tier-2 materials.
INGREDIENTS = {
    # Weapons
    "Honed": {"rider": "honed", "grade": 1, "allowed_bases": ["1-Hander", "2-Hander", "Wand", "Staff"], "cost": {"Scavenged Pelt": 1, "Gold": 1}},
    "Pierce": {"rider": "pierce", "grade": 1, "allowed_bases": ["1-Hander", "Wand"], "cost": {"Crag-Iron": 1, "Gold": 1}},
    "Blessed": {"rider": "blessed", "grade": 1, "allowed_bases": ["Staff"], "cost": {"Snap-Root": 1, "Gold": 2}},
    "Greater Blessed": {"rider": "greater_blessed", "grade": 2, "allowed_bases": ["Staff"], "cost": {"River-Mint": 1, "Gold": 4}},
    "Ruthless": {"rider": "ruthless", "grade": 2, "allowed_bases": ["2-Hander"], "cost": {"Sun-Copper": 1, "Gold": 4}},
    "Sunder": {"rider": "sunder", "grade": 2, "allowed_bases": ["2-Hander", "Staff"], "cost": {"Sun-Copper": 1, "Gold": 3}},

    # Armor
    "Reinforced": {"rider": "reinforced", "grade": 1, "allowed_bases": ["Light Armor", "Medium Armor", "Heavy Armor"], "cost": {"Crag-Iron": 1, "Gold": 3}},
    "Elusive": {"rider": "elusive", "grade": 2, "allowed_bases": ["Light Armor", "Medium Armor"], "cost": {"River-Mint": 1, "Gold": 5}},
    "Thorns": {"rider": "thorns", "grade": 2, "allowed_bases": ["Medium Armor", "Heavy Armor"], "cost": {"Sun-Copper": 1, "Gold": 3}},
    "Persistent": {"rider": "persistent", "grade": 2, "allowed_bases": ["Light Armor", "Medium Armor", "Heavy Armor"], "cost": {"Bristle-Pelt": 1, "Gold": 5}},
}

MATERIAL_INFO = {
    # Ore
    "Crag-Iron": {"category": "Ore", "tier": 1},
    "Sun-Copper": {"category": "Ore", "tier": 2},
    "Ember-Vein Ore": {"category": "Ore", "tier": 3},
    "Glacier-Metal": {"category": "Ore", "tier": 4},
    "Nether-Slag": {"category": "Ore", "tier": 5},
    "Crown-Gold": {"category": "Ore", "tier": 6},
    # Herb
    "Snap-Root": {"category": "Herb", "tier": 1},
    "River-Mint": {"category": "Herb", "tier": 2},
    "Scorch-Blossom": {"category": "Herb", "tier": 3},
    "Lantern-Spore": {"category": "Herb", "tier": 4},
    "Astral-Moss": {"category": "Herb", "tier": 5},
    "Tyrant's-Crest": {"category": "Herb", "tier": 6},
    # Skin
    "Scavenged Pelt": {"category": "Skin", "tier": 1},
    "Bristle-Pelt": {"category": "Skin", "tier": 2},
    "Ridge-Scale": {"category": "Skin", "tier": 3},
    "Iron-Fleece": {"category": "Skin", "tier": 4},
    "Phantom-Web": {"category": "Skin", "tier": 5},
    "Behemoth Leather": {"category": "Skin", "tier": 6},
}

def get_recipes_for_class(class_name):
    recipes = []
    for base_name, base_data in BASES.items():
        if class_name not in base_data["allowed_classes"]:
            continue
        for ing_name, ing_data in INGREDIENTS.items():
            if base_name in ing_data["allowed_bases"]:
                grade = ing_data.get("grade", 1)
                base_cost = base_data.get("costs", {}).get(grade, base_data.get("cost", {}))
                # Combine costs
                cost = {"Gold": ing_data["cost"].get("Gold", 0)}
                for k, v in base_cost.items():
                    cost[k] = cost.get(k, 0) + v
                for k, v in ing_data["cost"].items():
                    if k != "Gold":
                        cost[k] = cost.get(k, 0) + v

                # Deduplicate cost entries that are 0
                cost = {k: v for k, v in cost.items() if v > 0}

                recipes.append({
                    "name": f"{ing_name} {base_name}",
                    "slot": base_data["slot"],
                    "rider": ing_data["rider"],
                    "grade": grade,
                    "base": base_name,
                    "ingredient": ing_name,
                    "cost": cost,
                    "cost_gold": cost.get("Gold", 0),
                    "cost_items": [f"{v} {k}" for k, v in cost.items() if k != "Gold"],
                })
    return recipes

def can_craft_recipe(recipe, hero_gold, bag_counts):
    """Checks if a hero can craft a recipe under the minimum-tier rule (locked 2026-09-28).
    Returns (can_afford: bool, to_consume: dict|None).
    Consumes lowest-tier eligible materials first to preserve high-tier materials."""
    cost_gold = recipe.get("cost_gold", recipe["cost"].get("Gold", 0))
    if hero_gold < cost_gold:
        return False, None

    counts = dict(bag_counts)
    to_consume = {}
    reqs = []

    for item, qty in recipe["cost"].items():
        if item == "Gold":
            continue
        if item in MATERIAL_INFO:
            reqs.append((MATERIAL_INFO[item]["category"], MATERIAL_INFO[item]["tier"], qty))
        else:
            if counts.get(item, 0) < qty:
                return False, None
            counts[item] -= qty
            to_consume[item] = to_consume.get(item, 0) + qty

    # Sort requirements by min_tier descending so higher-tier requirements take high-tier items first
    reqs.sort(key=lambda r: r[1], reverse=True)
    for cat, min_tier, qty in reqs:
        needed = qty
        candidates = [m for m, info in MATERIAL_INFO.items() if info["category"] == cat and info["tier"] >= min_tier]
        candidates.sort(key=lambda m: MATERIAL_INFO[m]["tier"])  # Lowest eligible tier first
        for cand in candidates:
            avail = counts.get(cand, 0)
            if avail > 0:
                take = min(needed, avail)
                counts[cand] -= take
                needed -= take
                to_consume[cand] = to_consume.get(cand, 0) + take
                if needed == 0:
                    break
        if needed > 0:
            return False, None

    return True, to_consume