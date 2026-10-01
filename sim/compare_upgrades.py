import sim_pvp as PvP
import macro_sim as M

for class_name, upgrades in M.LEVEL2_PURCHASED_ORDER.items():
    print(f"\n### {class_name.capitalize()}")
    base_cards = PvP.CLASSES[class_name.capitalize()][0]
    
    if class_name in M.LEVEL2_MANDATORY:
        mod, old_name, new_name, new_dict = M.LEVEL2_MANDATORY[class_name]
        old_dict = base_cards.get(old_name, {})
        print(f"Mandatory: {old_name} -> {new_name}")
        for k, v in new_dict.items():
            old_v = old_dict.get(k)
            if old_v != v:
                print(f"  {k}: {old_v} -> {v}")
                
    for old_name, new_name, new_dict in upgrades:
        old_dict = base_cards.get(old_name, {})
        print(f"Purchased: {old_name} -> {new_name}")
        for k, v in new_dict.items():
            old_v = old_dict.get(k)
            if old_v != v:
                print(f"  {k}: {old_v} -> {v}")
