# Equipment definitions for Base + Ingredient crafting system.

# Base material follows what the Base actually is thematically, not a Level/grade signal --
# locked 2026-09-08. 1-Hander/2-Hander are metal weapons (Ore). Wand/Staff are wooden implements
# (Herb, NOT Ore -- corrected from an earlier draft that had them costing Crag-Iron like a metal
# weapon). Light/Medium Armor are cloth/leather (Skin). Heavy Armor is metal plate (Ore, NOT
# Skin -- corrected from an earlier draft that had it costing Scavenged Pelt like leather).
BASES = {
    "1-Hander": {"slot": "weapon", "cost": {"Crag-Iron": 1}, "allowed_classes": ["warrior", "paladin", "rogue", "ranger", "runecaster", "druid"]},
    "2-Hander": {"slot": "weapon", "cost": {"Crag-Iron": 2}, "allowed_classes": ["warrior", "paladin", "rogue", "ranger", "runecaster", "druid"]},
    "Wand": {"slot": "weapon", "cost": {"Snap-Root": 1}, "allowed_classes": ["wizard", "cleric", "necromancer", "druid"]},
    "Staff": {"slot": "weapon", "cost": {"Snap-Root": 2}, "allowed_classes": ["wizard", "cleric", "necromancer", "druid"]},
    "Light Armor": {"slot": "armor", "cost": {"Scavenged Pelt": 1}, "allowed_classes": ["wizard", "cleric", "necromancer"]},
    "Medium Armor": {"slot": "armor", "cost": {"Scavenged Pelt": 1}, "allowed_classes": ["rogue", "ranger", "runecaster", "druid"]},
    "Heavy Armor": {"slot": "armor", "cost": {"Crag-Iron": 1}, "allowed_classes": ["warrior", "paladin"]},
}

# "grade" (1 or 2) AND the Gold price both come from the 2026-09-08 balance sweep in
# EQUIPMENT_SWEEP_RESULTS.md -- Gold is set proportional to each ingredient's measured
# cross-class average win-rate uplift (a rough "1 Gold per ~2.2 percentage points" conversion,
# floored at 1), not assigned by feel. Grade 2 ingredients also require a Tier-2 material
# (Sun-Copper/River-Mint/Bristle-Pelt) in place of their old Tier-1 material -- this is the
# actual enforcement of "Level 2 requires Level 2 materials" that EQUIPMENT_GUIDE.md described
# from the start but was never wired into a real recipe cost until now. Grade 1 ingredients keep
# their original Tier-1 material unchanged. A Base's own material (see BASES above) is NEVER
# tier-gated by the ingredient's grade -- the frame is always ordinary material regardless of
# what's attached to it.
INGREDIENTS = {
    # Weapons
    "Honed": {"rider": "honed", "grade": 1, "allowed_bases": ["1-Hander", "2-Hander", "Wand", "Staff"], "cost": {"Scavenged Pelt": 1, "Gold": 1}},
    # Reclassified Grade 2 -> 1 (was measuring at or below Honed's own value in every class
    # that had it -- not an underperforming Level 2 item, a correctly-performing Level 1 one
    # that was misfiled). Kept flat at -2 Block, not weight-scaled, to control its ceiling.
    "Pierce": {"rider": "pierce", "grade": 1, "allowed_bases": ["1-Hander", "Wand"], "cost": {"Crag-Iron": 1, "Gold": 1}},
    "Blessed": {"rider": "blessed", "grade": 1, "allowed_bases": ["Staff"], "cost": {"Snap-Root": 1, "Gold": 2}},
    # New Grade 2 companion to Blessed (+1 Heal) rather than just buffing Blessed itself --
    # splits what used to be a single overtuned +2 Heal item into a real two-step progression:
    # a modest Level 1 heal option, and a stronger, correctly-gated Level 2 one. The +2 Heal
    # number is unchanged from the old single-tier Blessed, just moved to its own gated entry.
    # Material is River-Mint (Tier 2 Herb) alone -- dropped the extra Crag-Iron from the earlier
    # draft so this isn't also the most materially-expensive item on top of costing more Gold.
    "Greater Blessed": {"rider": "greater_blessed", "grade": 2, "allowed_bases": ["Staff"], "cost": {"River-Mint": 1, "Gold": 4}},
    "Ruthless": {"rider": "ruthless", "grade": 2, "allowed_bases": ["2-Hander"], "cost": {"Sun-Copper": 1, "Gold": 4}},
    "Sunder": {"rider": "sunder", "grade": 2, "allowed_bases": ["2-Hander", "Staff"], "cost": {"Sun-Copper": 1, "Gold": 3}},

    # Armor
    "Reinforced": {"rider": "reinforced", "grade": 1, "allowed_bases": ["Light Armor", "Medium Armor", "Heavy Armor"], "cost": {"Crag-Iron": 1, "Gold": 3}},
    "Elusive": {"rider": "elusive", "grade": 2, "allowed_bases": ["Light Armor", "Medium Armor"], "cost": {"River-Mint": 1, "Gold": 5}},
    "Thorns": {"rider": "thorns", "grade": 2, "allowed_bases": ["Medium Armor", "Heavy Armor"], "cost": {"Sun-Copper": 1, "Gold": 3}},
    # Widened from Heavy-only to all 3 armor weights (rebuilt as an Echo -- see
    # equipment_mechanics.py's PERSISTENT_THIS_ROUND/PERSISTENT_NEXT_ROUND for the numbers).
    "Persistent": {"rider": "persistent", "grade": 2, "allowed_bases": ["Light Armor", "Medium Armor", "Heavy Armor"], "cost": {"Bristle-Pelt": 1, "Gold": 5}},
}

def get_recipes_for_class(class_name):
    recipes = []
    for base_name, base_data in BASES.items():
        if class_name not in base_data["allowed_classes"]: continue
        for ing_name, ing_data in INGREDIENTS.items():
            if base_name in ing_data["allowed_bases"]:
                # Combine costs
                cost = {"Gold": ing_data["cost"].get("Gold", 0)}
                for k, v in base_data["cost"].items(): cost[k] = cost.get(k, 0) + v
                for k, v in ing_data["cost"].items():
                    if k != "Gold": cost[k] = cost.get(k, 0) + v
                
                # Deduplicate cost entries that are 0
                cost = {k: v for k, v in cost.items() if v > 0}
                
                recipes.append({
                    "name": f"{ing_name} {base_name}",
                    "slot": base_data["slot"],
                    "rider": ing_data["rider"],
                    "base": base_name,
                    "ingredient": ing_name,
                    "cost": cost
                })
    return recipes