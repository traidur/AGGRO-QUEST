import condensed_trip as T
from equipment_solver import best_line_with_equipment
from equipment_data import get_recipes_for_class

def run_equipment_sweep(class_name, equipment_load):
    from combat_engine import CARD_SOURCE
    mod = CARD_SOURCE[class_name]
    max_hp_map = {"warrior": 14, "wizard": 10, "cleric": 13, "paladin": 17, "rogue": 11, "ranger": 12, "runecaster": 14, "druid": 13, "necromancer": 12}
    max_hp = max_hp_map[class_name]

    hp_survival = {}
    for hp in range(max_hp, 0, -1):
        dead_count = 0
        total = 0
        for mob_name in T.MOB_NAMES:
            pattern, mob_hp = T.MOBS[mob_name][class_name]
            for hand in mod.ALL_HANDS:
                total += 1
                res = best_line_with_equipment(class_name, hand, pattern, mob_hp, hp, equipment_load)
                if res is None or res[2] <= 0:
                    dead_count += 1
        hp_survival[hp] = (total - dead_count) / total
    return hp_survival

print("Running baseline vs equipment sweeps...")
for cls in ["warrior", "wizard", "paladin", "rogue"]:
    print(f"\\n--- {cls.upper()} ---")
    recipes = get_recipes_for_class(cls)
    
    armor_recipes = [r for r in recipes if r["slot"] == "armor"]
    weapon_recipes = [r for r in recipes if r["slot"] == "weapon"]
    
    honed = next((r for r in weapon_recipes if r["rider"] == "honed"), None)
    reinforced = next((r for r in armor_recipes if r["rider"] == "reinforced"), None)
    early_t1 = {}
    if honed: early_t1["weapon"] = honed
    if reinforced: early_t1["armor"] = reinforced
    
    sunder = next((r for r in weapon_recipes if r["rider"] == "sunder"), None)
    advanced_armor = next((r for r in armor_recipes if r["rider"] in ["persistent", "elusive"]), None)
    adv_t1 = {}
    if sunder: adv_t1["weapon"] = sunder
    elif honed: adv_t1["weapon"] = honed
    if advanced_armor: adv_t1["armor"] = advanced_armor
    
    print("Baseline:")
    res_base = run_equipment_sweep(cls, {})
    for hp in range(max(res_base.keys()), 0, -1):
        if res_base[hp] < 1.0:
            print(f"  Breaks survival at HP {hp} ({res_base[hp]*100:.1f}%)")
            break
            
    print("Early Tier 1 (Honed + Reinforced):")
    res_early = run_equipment_sweep(cls, early_t1)
    for hp in range(max(res_early.keys()), 0, -1):
        if res_early[hp] < 1.0:
            print(f"  Breaks survival at HP {hp} ({res_early[hp]*100:.1f}%)")
            break
            
    print("Advanced Tier 1 (Sunder + Persistent/Elusive):")
    res_adv = run_equipment_sweep(cls, adv_t1)
    for hp in range(max(res_adv.keys()), 0, -1):
        if res_adv[hp] < 1.0:
            print(f"  Breaks survival at HP {hp} ({res_adv[hp]*100:.1f}%)")
            break