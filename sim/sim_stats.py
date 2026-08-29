import itertools
import numpy as np

import condensed_warrior as warrior
import condensed_cleric as cleric
import condensed_wizard as wizard
from combat_round import RoundState

CLASSES = {
    "Warrior": (warrior.CARDS, warrior.resolve_round, warrior.WARRIOR_HP, warrior.ALL_HANDS, warrior.orderings),
    "Cleric": (cleric.CARDS, cleric.resolve_round, cleric.CLERIC_HP, cleric.ALL_HANDS, cleric.orderings),
    "Wizard": (wizard.CARDS, wizard.resolve_round, wizard.WIZARD_HP, wizard.ALL_HANDS, wizard.orderings),
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

def resolve_duel_stats(class_A, seq_A, class_B, seq_B):
    cards_A, res_func_A, hp_A, _, _ = CLASSES[class_A]
    cards_B, res_func_B, hp_B, _, _ = CLASSES[class_B]
    
    max_hp_A = hp_A
    max_hp_B = hp_B
    state_A = RoundState()
    state_B = RoundState()
    
    cards_list_A, stance_A = seq_A
    cards_list_B, stance_B = seq_B
    
    total_raw_dmg_A = 0
    total_raw_dmg_B = 0
    total_block_A = 0
    total_block_B = 0
    total_heal_A = 0
    total_heal_B = 0
    
    for rnd in range(3):
        card_name_A = cards_list_A[rnd]
        card_name_B = cards_list_B[rnd]
        
        dummy_2 = [(0,0)] * 3
        dummy_3 = [(0,0,"melee")] * 3
        
        try: out_A = res_func_A(state_A, card_name_A, stance_A, rnd, dummy_3, max_hp_B, hp_B, hp_A, max_hp_A)
        except ValueError: out_A = res_func_A(state_A, card_name_A, stance_A, rnd, dummy_2, max_hp_B, hp_B, hp_A, max_hp_A)
            
        try: out_B = res_func_B(state_B, card_name_B, stance_B, rnd, dummy_3, max_hp_A, hp_A, hp_B, max_hp_B)
        except ValueError: out_B = res_func_B(state_B, card_name_B, stance_B, rnd, dummy_2, max_hp_A, hp_A, hp_B, max_hp_B)
        
        if out_A is None:
            raw_dmg_A, block_A, heal_A = 0, 0, 0
        else:
            raw_dmg_A, block_A, heal_A, state_A = out_A.raw_dmg, out_A.block, out_A.heal, out_A.new_state
            
        if out_B is None:
            raw_dmg_B, block_B, heal_B = 0, 0, 0
        else:
            raw_dmg_B, block_B, heal_B, state_B = out_B.raw_dmg, out_B.block, out_B.heal, out_B.new_state
            
        card_data_A = cards_A[card_name_A]
        card_data_B = cards_B[card_name_B]
        
        type_A = card_data_A.get("combat_type", "melee")
        type_B = card_data_B.get("combat_type", "melee")
        
        evades_melee_A = card_data_A.get("grants_range", False)
        if hasattr(state_A, "prev_grants_range") and state_A.prev_grants_range: evades_melee_A = True
        if evades_melee_A and type_B == "melee": raw_dmg_B = 0
            
        evades_melee_B = card_data_B.get("grants_range", False)
        if hasattr(state_B, "prev_grants_range") and state_B.prev_grants_range: evades_melee_B = True
        if evades_melee_B and type_A == "melee": raw_dmg_A = 0
            
        pierce_A = card_data_A.get("armor_pierce", False)
        pierce_B = card_data_B.get("armor_pierce", False)
        
        eff_dmg_A = raw_dmg_A if pierce_A else max(0, raw_dmg_A - block_B)
        eff_dmg_B = raw_dmg_B if pierce_B else max(0, raw_dmg_B - block_A)
        
        kb_A = card_data_A.get("killing_blow", False)
        kb_B = card_data_B.get("killing_blow", False)
        
        if kb_A and (hp_B - eff_dmg_A <= 0): eff_dmg_B = 0
        if kb_B and (hp_A - eff_dmg_B <= 0): eff_dmg_A = 0
            
        hp_A = min(max_hp_A, hp_A - eff_dmg_B + heal_A)
        hp_B = min(max_hp_B, hp_B - eff_dmg_A + heal_B)
        
        total_raw_dmg_A += raw_dmg_A
        total_raw_dmg_B += raw_dmg_B
        total_block_A += block_A
        total_block_B += block_B
        total_heal_A += heal_A
        total_heal_B += heal_B
        
        if hp_A <= 0 or hp_B <= 0:
            break
            
    dmg_done_by_A = max_hp_B - hp_B
    dmg_done_by_B = max_hp_A - hp_A
    
    return {
        "A_Net_Dmg": dmg_done_by_A,
        "B_Net_Dmg": dmg_done_by_B,
        "A_Raw_Dmg": total_raw_dmg_A,
        "B_Raw_Dmg": total_raw_dmg_B,
        "A_Block": total_block_A,
        "B_Block": total_block_B,
        "A_Heal": total_heal_A,
        "B_Heal": total_heal_B
    }

def evaluate_stats(class_A, class_B):
    hands_A = CLASSES[class_A][3]
    hands_B = CLASSES[class_B][3]
    
    seqs_A = [s for h in hands_A for s in get_sequences(class_A, h)]
    seqs_B = [s for h in hands_B for s in get_sequences(class_B, h)]
    
    totals = {
        "A_Net_Dmg": 0, "B_Net_Dmg": 0,
        "A_Raw_Dmg": 0, "B_Raw_Dmg": 0,
        "A_Block": 0, "B_Block": 0,
        "A_Heal": 0, "B_Heal": 0
    }
    count = 0
    
    # Just run a random subset to get a fast average
    import random
    random.seed(42)
    sample_A = random.sample(seqs_A, min(100, len(seqs_A)))
    sample_B = random.sample(seqs_B, min(100, len(seqs_B)))
    
    for sA in sample_A:
        for sB in sample_B:
            stats = resolve_duel_stats(class_A, sA, class_B, sB)
            for k in totals:
                totals[k] += stats[k]
            count += 1
            
    print(f"\n--- {class_A} vs {class_B} ---")
    for k in totals:
        print(f"{k}: {totals[k]/count:.2f}")

evaluate_stats("Warrior", "Cleric")
evaluate_stats("Warrior", "Wizard")
evaluate_stats("Rogue", "Wizard")
