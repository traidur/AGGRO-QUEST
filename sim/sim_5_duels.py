import numpy as np
import random
import condensed_warrior as warrior
import condensed_runecaster as runecaster
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
    "Runecaster": (runecaster.CARDS, runecaster.resolve_round, runecaster.RUNECASTER_HP, runecaster.ALL_HANDS, runecaster.orderings),
}

MODS_1D = {'Warrior': 1, 'Runecaster': 1}

def get_sequences(class_name, hand):
    mod_orderings = CLASSES[class_name][4]
    if class_name == "Warrior":
        seqs = []
        for cards in mod_orderings(hand):
            seqs.append((cards, "G"))
            seqs.append((cards, "C"))
        return seqs
    return [(cards, None) for cards in mod_orderings(hand)]

def resolve_duel_raw(class_A, seq_A, class_B, seq_B):
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
    return dmg_done_by_A, dmg_done_by_B

all_seqs_W = []
for h in CLASSES["Warrior"][3]:
    all_seqs_W.extend(get_sequences("Warrior", h))

all_seqs_R = []
for h in CLASSES["Runecaster"][3]:
    all_seqs_R.extend(get_sequences("Runecaster", h))

tokens_W = 0
tokens_R = 0

for i in range(1, 6):
    print(f"--- DUEL {i} ---")
    sW = random.choice(all_seqs_W)
    sR = random.choice(all_seqs_R)
    dmgW, dmgR = resolve_duel_raw("Warrior", sW, "Runecaster", sR)
    
    print(f"Pre-Duel State:")
    print(f"  Warrior:    Base Skirmish Rating = +1 | Battle Hardened Tokens = {tokens_W}")
    print(f"  Runecaster: Base Skirmish Rating = +1 | Battle Hardened Tokens = {tokens_R}")
    print()
    print(f"Combat Result:")
    print(f"  Warrior unblocked damage: {dmgW}")
    print(f"  Runecaster unblocked damage: {dmgR}")
    
    score_W = dmgW + MODS_1D["Warrior"] + tokens_W
    score_R = dmgR + MODS_1D["Runecaster"] + tokens_R
    
    print(f"Final Score Calculation:")
    print(f"  Warrior Score: {dmgW} (Dmg) + 1 (Base Rating) + {tokens_W} (Tokens) = {score_W}")
    print(f"  Runecaster Score: {dmgR} (Dmg) + 1 (Base Rating) + {tokens_R} (Tokens) = {score_R}")
    
    if score_W > score_R:
        print(f"Result: WARRIOR WINS (by {score_W - score_R} points)")
        tokens_W = 0
        tokens_R += 1
    elif score_R > score_W:
        print(f"Result: RUNECASTER WINS (by {score_R - score_W} points)")
        tokens_R = 0
        tokens_W += 1
    else:
        winner = random.choice(["Warrior", "Runecaster"])
        print(f"Result: TIE ({score_W} to {score_R}). {winner} wins Initiator Tiebreaker!")
        if winner == "Warrior":
            tokens_W = 0
            tokens_R += 1
        else:
            tokens_R = 0
            tokens_W += 1
            
    print(f"Post-Duel State:")
    print(f"  Warrior Battle Hardened Tokens: {tokens_W}")
    print(f"  Runecaster Battle Hardened Tokens: {tokens_R}")
    print()
