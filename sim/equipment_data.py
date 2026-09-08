# Equipment definitions for Base + Ingredient crafting system.

BASES = {
    "1-Hander": {"slot": "weapon", "cost": {"Crag-Iron": 1}, "allowed_classes": ["warrior", "paladin", "rogue", "ranger", "runecaster", "druid"]},
    "2-Hander": {"slot": "weapon", "cost": {"Crag-Iron": 2}, "allowed_classes": ["warrior", "paladin", "rogue", "ranger", "runecaster", "druid"]},
    "Wand": {"slot": "weapon", "cost": {"Crag-Iron": 1}, "allowed_classes": ["wizard", "cleric", "necromancer", "druid"]},
    "Staff": {"slot": "weapon", "cost": {"Crag-Iron": 2}, "allowed_classes": ["wizard", "cleric", "necromancer", "druid"]},
    "Light Armor": {"slot": "armor", "cost": {"Scavenged Pelt": 1}, "allowed_classes": ["wizard", "cleric", "necromancer"]},
    "Medium Armor": {"slot": "armor", "cost": {"Scavenged Pelt": 1}, "allowed_classes": ["rogue", "ranger", "runecaster", "druid"]},
    "Heavy Armor": {"slot": "armor", "cost": {"Scavenged Pelt": 1}, "allowed_classes": ["warrior", "paladin"]},
}

INGREDIENTS = {
    # Weapons
    "Honed": {"rider": "honed", "allowed_bases": ["1-Hander", "2-Hander", "Wand", "Staff"], "cost": {"Scavenged Pelt": 1, "Gold": 1}},
    "Pierce": {"rider": "pierce", "allowed_bases": ["1-Hander", "Wand"], "cost": {"Crag-Iron": 1, "Gold": 1}},
    "Blessed": {"rider": "blessed", "allowed_bases": ["Staff"], "cost": {"Snap-Root": 1, "Gold": 1}},
    "Ruthless": {"rider": "ruthless", "allowed_bases": ["2-Hander"], "cost": {"Crag-Iron": 1, "Gold": 1}},
    "Sunder": {"rider": "sunder", "allowed_bases": ["2-Hander", "Staff"], "cost": {"Crag-Iron": 1, "Gold": 1}},
    
    # Armor
    "Reinforced": {"rider": "reinforced", "allowed_bases": ["Light Armor", "Medium Armor", "Heavy Armor"], "cost": {"Crag-Iron": 1, "Gold": 1}},
    "Elusive": {"rider": "elusive", "allowed_bases": ["Light Armor", "Medium Armor"], "cost": {"Snap-Root": 1, "Gold": 1}},
    "Thorns": {"rider": "thorns", "allowed_bases": ["Medium Armor", "Heavy Armor"], "cost": {"Crag-Iron": 1, "Gold": 1}},
    "Persistent": {"rider": "persistent", "allowed_bases": ["Heavy Armor"], "cost": {"Scavenged Pelt": 1, "Gold": 1}},
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