import numpy as np
import condensed_warrior as warrior
import condensed_cleric as cleric
import condensed_wizard as wizard
import condensed_paladin as paladin
from combat_round import RoundState
from dataclasses import replace

CLASSES = {
    "Warrior": (warrior.CARDS, warrior.resolve_round, warrior.WARRIOR_HP, warrior.ALL_HANDS, warrior.orderings),
    "Cleric": (cleric.CARDS, cleric.resolve_round, cleric.CLERIC_HP, cleric.ALL_HANDS, cleric.orderings),
    "Wizard": (wizard.CARDS, wizard.resolve_round, wizard.WIZARD_HP, wizard.ALL_HANDS, wizard.orderings),
    "Paladin": (paladin.CARDS, paladin.resolve_round, paladin.PALADIN_HP, paladin.ALL_HANDS, paladin.orderings)
}

def get_sequences(class_name, hand):
    mod_orderings = CLASSES[class_name][4]
    if class_name == "Warrior":
        seqs = []
        for cards in mod_orderings(hand):
            seqs.append((cards, "G"))
            seqs.append((cards, "C"))
        return seqs
    return [(cards, None) for cards in mod_orderings(hand)]

def resolve_duel(class_A, seq_A, class_B, seq_B, unlock_execute=False):
    cards_A, res_func_A, hp_A, _, _ = CLASSES[class_A]
    cards_B, res_func_B, hp_B, _, _ = CLASSES[class_B]
    max_hp_A, max_hp_B = hp_A, hp_B
    state_A, state_B = RoundState(), RoundState()
    
    cards_list_A, stance_A = seq_A
    cards_list_B, stance_B = seq_B
    
    for rnd in range(3):
        c_A, c_B = cards_list_A[rnd], cards_list_B[rnd]
        dummy_3 = [(0,0,"melee")] * 3
        dummy_2 = [(0,0)] * 3
        
        # Unlocked execute bypass
        if unlock_execute and class_A == "Warrior" and c_A == "Execute":
            hp_temp = 0 # fake the 50% check
        else:
            hp_temp = hp_B
            
        if unlock_execute and class_B == "Warrior" and c_B == "Execute":
            hp_temp_B = 0
        else:
            hp_temp_B = hp_A

        try: out_A = res_func_A(state_A, c_A, stance_A, rnd, dummy_3, max_hp_B, hp_temp, hp_A, max_hp_A)
        except ValueError: out_A = res_func_A(state_A, c_A, stance_A, rnd, dummy_2, max_hp_B, hp_temp, hp_A, max_hp_A)
            
        try: out_B = res_func_B(state_B, c_B, stance_B, rnd, dummy_3, max_hp_A, hp_temp_B, hp_B, max_hp_B)
        except ValueError: out_B = res_func_B(state_B, c_B, stance_B, rnd, dummy_2, max_hp_A, hp_temp_B, hp_B, max_hp_B)
        
        raw_dmg_A = 0 if out_A is None else out_A.raw_dmg
        block_A = 0 if out_A is None else out_A.block
        heal_A = 0 if out_A is None else out_A.heal
        if out_A: state_A = out_A.new_state
            
        raw_dmg_B = 0 if out_B is None else out_B.raw_dmg
        block_B = 0 if out_B is None else out_B.block
        heal_B = 0 if out_B is None else out_B.heal
        if out_B: state_B = out_B.new_state
            
        card_data_A = cards_A[c_A]
        card_data_B = cards_B[c_B]
        
        evades_A = card_data_A.get("grants_range", False) or getattr(state_A, "prev_grants_range", False)
        evades_B = card_data_B.get("grants_range", False) or getattr(state_B, "prev_grants_range", False)
        
        if evades_A and card_data_B.get("combat_type", "melee") == "melee": raw_dmg_B = 0
        if evades_B and card_data_A.get("combat_type", "melee") == "melee": raw_dmg_A = 0
            
        eff_dmg_A = raw_dmg_A if card_data_A.get("armor_pierce") else max(0, raw_dmg_A - block_B)
        eff_dmg_B = raw_dmg_B if card_data_B.get("armor_pierce") else max(0, raw_dmg_B - block_A)
        
        if card_data_A.get("killing_blow") and (hp_B - eff_dmg_A <= 0): eff_dmg_B = 0
        if card_data_B.get("killing_blow") and (hp_A - eff_dmg_B <= 0): eff_dmg_A = 0
            
        hp_A = min(max_hp_A, hp_A - eff_dmg_B + heal_A)
        hp_B = min(max_hp_B, hp_B - eff_dmg_A + heal_B)
        
        if hp_A <= 0 or hp_B <= 0: break
            
    # DEATH = AUTO LOSS RULE
    if hp_A <= 0 and hp_B > 0:
        return -50 # A dies, B lives
    if hp_B <= 0 and hp_A > 0:
        return 50  # B dies, A lives
    if hp_A <= 0 and hp_B <= 0:
        return 0   # Tie
        
    # Otherwise, normal raw damage rule
    return (max_hp_B - hp_B) - (max_hp_A - hp_A)

def evaluate(class_A, class_B, unlock=False):
    hands_A = CLASSES[class_A][3]
    hands_B = CLASSES[class_B][3]
    
    seqs_A = [get_sequences(class_A, h) for h in hands_A]
    seqs_B = [get_sequences(class_B, h) for h in hands_B]
    
    cache = {}
    total_ev = 0
    count = 0
    death_count = 0
    
    for sA_list in seqs_A:
        for sB_list in seqs_B:
            matrix = np.zeros((len(sA_list), len(sB_list)))
            for r, sA in enumerate(sA_list):
                for c, sB in enumerate(sB_list):
                    k = (sA, sB)
                    if k not in cache:
                        cache[k] = resolve_duel(class_A, sA, class_B, sB, unlock)
                    matrix[r, c] = cache[k]
            
            row_mins = np.min(matrix, axis=1)
            col_maxs = np.max(matrix, axis=0)
            ev = (np.max(row_mins) + np.min(col_maxs)) / 2
            total_ev += ev
            count += 1
            if abs(ev) >= 25: # If EV is massive, it means Death was forced in equilibrium
                death_count += 1
                
    return total_ev / count, death_count, count

print("BASELINE (Locked Execute, Death=Loss)")
ev, dc, c = evaluate("Warrior", "Wizard", False)
print(f"Warrior vs Wizard EV: {ev:.2f} | Deaths forced in equilibrium: {dc}/{c}")

print("\nUNLOCKED EXECUTE (Death=Loss)")
ev2, dc2, c2 = evaluate("Warrior", "Wizard", True)
print(f"Warrior vs Wizard EV: {ev2:.2f} | Deaths forced in equilibrium: {dc2}/{c2}")

