import itertools
import functools
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

_warrior_resolve_round_pvp = functools.partial(warrior.resolve_round, execute_unlocked=True)
_necro_resolve_round_pvp = functools.partial(necro.resolve_round, death_pact_free=True)

CLASSES = {
    # PvP-only: Execute's 50%-HP gate is unlocked per DESIGN_DOC.md Section X ("Class-Specific
    # PvP Rules" #1). Every other class module's plain resolve_round is unchanged.
    "Warrior": (warrior.CARDS, _warrior_resolve_round_pvp, warrior.WARRIOR_HP, warrior.ALL_HANDS, warrior.orderings),
    "Cleric": (cleric.CARDS, cleric.resolve_round, cleric.CLERIC_HP, cleric.ALL_HANDS, cleric.orderings),
    "Wizard": (wizard.CARDS, wizard.resolve_round, wizard.WIZARD_HP, wizard.ALL_HANDS, wizard.orderings),
    "Paladin": (paladin.CARDS, paladin.resolve_round, paladin.PALADIN_HP, paladin.ALL_HANDS, paladin.orderings),
    "Rogue": (rogue.CARDS, rogue.resolve_round, rogue.ROGUE_HP, rogue.ALL_HANDS, rogue.orderings),
    "Ranger": (ranger.CARDS, ranger.resolve_round, ranger.RANGER_HP, ranger.ALL_HANDS, ranger.orderings),
    "Runecaster": (runecaster.CARDS, runecaster.resolve_round, runecaster.RUNECASTER_HP, runecaster.ALL_HANDS, runecaster.orderings),
    "Druid": (druid.CARDS, druid.resolve_round, druid.DRUID_HP, druid.ALL_HANDS, druid.orderings),
    # PvP-only: Death Pact's HP-cost rider is waived per DESIGN_DOC.md Section X
    # ("Class-Specific PvP Rules" #2) -- see condensed_necromancer.py's resolve_round docstring.
    "Necromancer": (necro.CARDS, _necro_resolve_round_pvp, necro.NECROMANCER_HP, necro.ALL_HANDS, necro.orderings),
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
    
    max_hp_A = hp_A
    max_hp_B = hp_B
    
    state_A = RoundState()
    state_B = RoundState()
    
    cards_list_A, stance_A = seq_A
    cards_list_B, stance_B = seq_B
    
    for rnd in range(3):
        card_name_A = cards_list_A[rnd]
        card_name_B = cards_list_B[rnd]
        
        dummy_pattern_2 = [(0,0)] * 3
        dummy_pattern_3 = [(0,0,"melee")] * 3
        
        try:
            out_A = res_func_A(state_A, card_name_A, stance_A, rnd, dummy_pattern_3, max_hp_B, hp_B, hp_A, max_hp_A)
        except ValueError:
            out_A = res_func_A(state_A, card_name_A, stance_A, rnd, dummy_pattern_2, max_hp_B, hp_B, hp_A, max_hp_A)
            
        try:
            out_B = res_func_B(state_B, card_name_B, stance_B, rnd, dummy_pattern_3, max_hp_A, hp_A, hp_B, max_hp_B)
        except ValueError:
            out_B = res_func_B(state_B, card_name_B, stance_B, rnd, dummy_pattern_2, max_hp_A, hp_A, hp_B, max_hp_B)
        
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
        if hasattr(state_A, "prev_grants_range") and state_A.prev_grants_range:
            evades_melee_A = True
            
        if evades_melee_A and type_B == "melee":
            raw_dmg_B = 0
            
        evades_melee_B = card_data_B.get("grants_range", False)
        if hasattr(state_B, "prev_grants_range") and state_B.prev_grants_range:
            evades_melee_B = True
            
        if evades_melee_B and type_A == "melee":
            raw_dmg_A = 0
            
        pierce_A = card_data_A.get("armor_pierce", False)
        pierce_B = card_data_B.get("armor_pierce", False)
        
        eff_dmg_A = raw_dmg_A if pierce_A else max(0, raw_dmg_A - block_B)
        eff_dmg_B = raw_dmg_B if pierce_B else max(0, raw_dmg_B - block_A)
        
        kb_A = card_data_A.get("killing_blow", False)
        kb_B = card_data_B.get("killing_blow", False)
        
        A_kills_B = (hp_B - eff_dmg_A <= 0)
        B_kills_A = (hp_A - eff_dmg_B <= 0)
        
        if kb_A and A_kills_B:
            eff_dmg_B = 0
        if kb_B and B_kills_A:
            eff_dmg_A = 0
            
        hp_A = min(max_hp_A, hp_A - eff_dmg_B + heal_A)
        hp_B = min(max_hp_B, hp_B - eff_dmg_A + heal_B)
        
        if hp_A <= 0 or hp_B <= 0:
            break
            
    dmg_done_by_A = max_hp_B - hp_B
    dmg_done_by_B = max_hp_A - hp_A

    return dmg_done_by_A, dmg_done_by_B

def evaluate_matchup(class_A, class_B):
    hands_A = CLASSES[class_A][3]
    hands_B = CLASSES[class_B][3]
    
    total_ev = 0
    count = 0
    
    seqs_A = [get_sequences(class_A, h) for h in hands_A]
    seqs_B = [get_sequences(class_B, h) for h in hands_B]
    
    cache = {}
    def cached_duel(s_A, s_B):
        k = (s_A, s_B)
        if k not in cache:
            dA, dB = resolve_duel(class_A, s_A, class_B, s_B)
            cache[k] = dA - dB
        return cache[k]
    
    for i, sA_list in enumerate(seqs_A):
        for j, sB_list in enumerate(seqs_B):
            matrix = np.zeros((len(sA_list), len(sB_list)))
            for r, sA in enumerate(sA_list):
                for c, sB in enumerate(sB_list):
                    matrix[r, c] = cached_duel(sA, sB)
            
            row_mins = np.min(matrix, axis=1)
            min_max = np.max(row_mins)
            
            col_maxs = np.max(matrix, axis=0)
            max_min = np.min(col_maxs)
            
            ev = (min_max + max_min) / 2
            total_ev += ev
            count += 1
            
    return total_ev / count

if __name__ == "__main__":
    class_names = list(CLASSES.keys())
    print('| Attacker \\ Defender | ' + ' | '.join(class_names) + ' |')
    print('|---' * (len(class_names) + 1) + '|')
    
    for cA in class_names:
        row = [f'**{cA}**']
        for cB in class_names:
            if cA == cB:
                row.append('0.00')
            else:
                ev = evaluate_matchup(cA, cB)
                row.append(f'{ev:+.2f}')
        print('| ' + ' | '.join(row) + ' |')
