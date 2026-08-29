import numpy as np
import condensed_warrior as warrior
import condensed_cleric as cleric
import condensed_wizard as wizard
import condensed_paladin as paladin
import condensed_rogue as rogue
import condensed_ranger as ranger
import condensed_runecaster as runecaster
import condensed_druid as druid
import condensed_necromancer as necro
from combat_round import RoundState

CLASSES = {
    "Warrior": (warrior.CARDS, warrior.resolve_round, warrior.WARRIOR_HP, warrior.ALL_HANDS, warrior.orderings),
    "Cleric": (cleric.CARDS, cleric.resolve_round, cleric.CLERIC_HP, cleric.ALL_HANDS, cleric.orderings),
    "Wizard": (wizard.CARDS, wizard.resolve_round, wizard.WIZARD_HP, wizard.ALL_HANDS, wizard.orderings),
    "Paladin": (paladin.CARDS, paladin.resolve_round, paladin.PALADIN_HP, paladin.ALL_HANDS, paladin.orderings),
    "Rogue": (rogue.CARDS, rogue.resolve_round, rogue.ROGUE_HP, rogue.ALL_HANDS, rogue.orderings),
    "Ranger": (ranger.CARDS, ranger.resolve_round, ranger.RANGER_HP, ranger.ALL_HANDS, ranger.orderings),
    "Runecaster": (runecaster.CARDS, runecaster.resolve_round, runecaster.RUNECASTER_HP, runecaster.ALL_HANDS, runecaster.orderings),
    "Druid": (druid.CARDS, druid.resolve_round, druid.DRUID_HP, druid.ALL_HANDS, druid.orderings),
    "Necromancer": (necro.CARDS, necro.resolve_round, necro.NECROMANCER_HP, necro.ALL_HANDS, necro.orderings),
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

def resolve_duel(class_A, seq_A, class_B, seq_B):
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
        
        try: out_A = res_func_A(state_A, c_A, stance_A, rnd, dummy_3, max_hp_B, hp_B, hp_A, max_hp_A)
        except ValueError: out_A = res_func_A(state_A, c_A, stance_A, rnd, dummy_2, max_hp_B, hp_B, hp_A, max_hp_A)
            
        try: out_B = res_func_B(state_B, c_B, stance_B, rnd, dummy_3, max_hp_A, hp_A, hp_B, max_hp_B)
        except ValueError: out_B = res_func_B(state_B, c_B, stance_B, rnd, dummy_2, max_hp_A, hp_A, hp_B, max_hp_B)
        
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
            
    return (max_hp_B - hp_B) - (max_hp_A - hp_A)

def evaluate_random(class_A, class_B):
    hands_A = CLASSES[class_A][3]
    hands_B = CLASSES[class_B][3]
    
    total_ev = 0
    count = 0
    seqs_A = [get_sequences(class_A, h) for h in hands_A]
    seqs_B = [get_sequences(class_B, h) for h in hands_B]
    
    cache = {}
    def cached_duel(s_A, s_B):
        k = (s_A, s_B)
        if k not in cache: cache[k] = resolve_duel(class_A, s_A, class_B, s_B)
        return cache[k]
    
    for sA_list in seqs_A:
        for sB_list in seqs_B:
            matrix = np.zeros((len(sA_list), len(sB_list)))
            for r, sA in enumerate(sA_list):
                for c, sB in enumerate(sB_list):
                    matrix[r, c] = cached_duel(sA, sB)
            
            # PERFECTLY RANDOM PLAY: EV is just the mean of the entire matrix
            ev = np.mean(matrix)
            total_ev += ev
            count += 1
            
    return total_ev / count

print('--- WARRIOR (RANDOM PLAY) vs CLASSES ---')
for c in CLASSES.keys():
    if c != "Warrior":
        print(f"vs {c}: {evaluate_random('Warrior', c):+.2f}")
