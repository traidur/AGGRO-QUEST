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
from dataclasses import replace

def warrior_resolve_round_unlocked(state, card_name, stance, round_num, mob_pattern, hero_max_hp, hero_hp, mob_hp_remaining, mob_hp_total):
    card = warrior.CARDS[card_name]
    if card["execute_finisher"]: dmg, block = 6, 0
    else:
        if stance == "G": dmg, block = card["G"]
        else: dmg, block = card["C"]
        if card["chain_requires"] == state.prev_card_name and card["chain_stance"] == stance:
            if card["chain_target"] == "block": block += card["chain_bonus"]
            else: dmg += card["chain_bonus"]
    eff_dmg = dmg + (warrior.SUNDER_BONUS * state.sunder_stacks if dmg > 0 else 0)
    new_sunder = state.sunder_stacks + (1 if card["sunder"] else 0)
    mob_atk, mob_block, mob_type = mob_pattern[round_num]
    dmg_dealt = max(0.0, eff_dmg - mob_block)
    if card.get("killing_blow") and (mob_hp_remaining - dmg_dealt) <= 0: dmg_taken = 0.0
    elif card.get("grants_range") and mob_type == "melee": dmg_taken = 0.0
    else: dmg_taken = max(0.0, mob_atk - block)
    new_hp = hero_hp - dmg_taken
    new_state = replace(state, stance=stance, sunder_stacks=new_sunder, prev_card_name=card_name)
    from combat_round import RoundOutcome
    return RoundOutcome(new_hp=new_hp, new_mob_hp_remaining=mob_hp_remaining-dmg_dealt, new_hero_max_hp=hero_max_hp, new_state=new_state, dmg_dealt=dmg_dealt, dmg_taken=dmg_taken, raw_dmg=eff_dmg, block=block, heal=0.0)

CLASSES = {
    "Warrior": (warrior.CARDS, warrior_resolve_round_unlocked, warrior.WARRIOR_HP, warrior.ALL_HANDS, warrior.orderings),
    "Cleric": (cleric.CARDS, cleric.resolve_round, cleric.CLERIC_HP, cleric.ALL_HANDS, cleric.orderings),
    "Wizard": (wizard.CARDS, wizard.resolve_round, wizard.WIZARD_HP, wizard.ALL_HANDS, wizard.orderings),
    "Paladin": (paladin.CARDS, paladin.resolve_round, paladin.PALADIN_HP, paladin.ALL_HANDS, paladin.orderings),
    "Rogue": (rogue.CARDS, rogue.resolve_round, rogue.ROGUE_HP, rogue.ALL_HANDS, rogue.orderings),
    "Ranger": (ranger.CARDS, ranger.resolve_round, ranger.RANGER_HP, ranger.ALL_HANDS, ranger.orderings),
    "Runecaster": (runecaster.CARDS, runecaster.resolve_round, runecaster.RUNECASTER_HP, runecaster.ALL_HANDS, runecaster.orderings),
    "Druid": (druid.CARDS, druid.resolve_round, druid.DRUID_HP, druid.ALL_HANDS, druid.orderings),
    "Necromancer": (necro.CARDS, necro.resolve_round, necro.NECROMANCER_HP, necro.ALL_HANDS, necro.orderings),
}

MATRIX = {
    'Warrior': {'Cleric': -1.86, 'Wizard': -2.70, 'Paladin': -1.26, 'Rogue': 0.21, 'Ranger': -2.37, 'Runecaster': -1.23, 'Druid': -1.35, 'Necromancer': -1.23},
    'Cleric': {'Warrior': 1.86, 'Wizard': 0.79, 'Paladin': 0.51, 'Rogue': 2.46, 'Ranger': 1.13, 'Runecaster': 2.36, 'Druid': 0.27, 'Necromancer': 2.77},
    'Wizard': {'Warrior': 2.70, 'Cleric': -0.79, 'Paladin': 0.72, 'Rogue': 2.33, 'Ranger': 1.04, 'Runecaster': 1.98, 'Druid': -0.44, 'Necromancer': 2.45},
    'Paladin': {'Warrior': 1.26, 'Cleric': -0.51, 'Wizard': -0.72, 'Rogue': 1.69, 'Ranger': -0.59, 'Runecaster': 0.94, 'Druid': -0.37, 'Necromancer': 1.02},
    'Rogue': {'Warrior': -0.21, 'Cleric': -2.46, 'Wizard': -2.33, 'Paladin': -1.69, 'Ranger': -2.64, 'Runecaster': -1.37, 'Druid': -1.92, 'Necromancer': -1.47},
    'Ranger': {'Warrior': 2.37, 'Cleric': -1.13, 'Wizard': -1.04, 'Paladin': 0.59, 'Rogue': 2.64, 'Runecaster': 1.10, 'Druid': -0.94, 'Necromancer': 2.02},
    'Runecaster': {'Warrior': 1.23, 'Cleric': -2.36, 'Wizard': -1.98, 'Paladin': -0.94, 'Rogue': 1.37, 'Ranger': -1.10, 'Druid': -1.97, 'Necromancer': 0.76},
    'Druid': {'Warrior': 1.35, 'Cleric': -0.27, 'Wizard': 0.44, 'Paladin': 0.37, 'Rogue': 1.92, 'Ranger': 0.94, 'Runecaster': 1.97, 'Necromancer': 2.69},
    'Necromancer': {'Warrior': 1.23, 'Cleric': -2.77, 'Wizard': -2.45, 'Paladin': -1.02, 'Rogue': 1.47, 'Ranger': -2.02, 'Runecaster': -0.76, 'Druid': -2.69},
}

def get_handicap(cA, cB):
    ev = MATRIX[cA][cB]
    if ev < -0.5: return round(abs(ev))
    return 0

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
        hp_temp_A = 0 if class_A == "Warrior" and c_A == "Execute" else hp_B
        hp_temp_B = 0 if class_B == "Warrior" and c_B == "Execute" else hp_A
        try: out_A = res_func_A(state_A, c_A, stance_A, rnd, dummy_3, max_hp_B, hp_temp_A, hp_A, max_hp_A)
        except ValueError: out_A = res_func_A(state_A, c_A, stance_A, rnd, dummy_2, max_hp_B, hp_temp_A, hp_A, max_hp_A)
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
    
    dmg_done_by_A = max_hp_B - hp_B
    dmg_done_by_B = max_hp_A - hp_A
    
    # EXACT HANDICAPS
    mod_A = get_handicap(class_A, class_B)
    mod_B = get_handicap(class_B, class_A)
    
    score_A = dmg_done_by_A + mod_A
    score_B = dmg_done_by_B + mod_B
    return score_A - score_B

class_names = list(CLASSES.keys())
cache = {}
def cached_duel(cA, s_A, cB, s_B):
    k = (cA, s_A, cB, s_B)
    if k not in cache: cache[k] = resolve_duel(cA, s_A, cB, s_B)
    return cache[k]

print("| Attacker \ Defender | " + " | ".join(class_names) + " |")
print("|---" * (len(class_names) + 1) + "|")
for cA in class_names:
    row = [f"**{cA}**"]
    for cB in class_names:
        if cA == cB:
            row.append("-")
            continue
            
        hands_A = CLASSES[cA][3]
        hands_B = CLASSES[cB][3]
        seqs_A = [get_sequences(cA, h) for h in hands_A]
        seqs_B = [get_sequences(cB, h) for h in hands_B]
        
        wins = 0
        total = 0
        
        for sA_list in seqs_A:
            for sB_list in seqs_B:
                matrix = np.zeros((len(sA_list), len(sB_list)))
                for r, sA in enumerate(sA_list):
                    for c, sB in enumerate(sB_list):
                        matrix[r, c] = cached_duel(cA, sA, cB, sB)
                row_mins = np.min(matrix, axis=1)
                col_maxs = np.max(matrix, axis=0)
                ev = (np.max(row_mins) + np.min(col_maxs)) / 2
                
                total += 1
                if ev > 0.05: wins += 1
                elif ev >= -0.05: wins += 0.5 
                
        wr = (wins / total) * 100
        row.append(f"{wr:.1f}%")
    print("| " + " | ".join(row) + " |")
