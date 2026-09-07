from combat_round import RoundOutcome, RoundState
from dataclasses import replace

def apply_equipment_mechanics(outcome: RoundOutcome, rider: str, round_num: int, equip_round: int, mob_pattern) -> RoundOutcome:
    """Applies a specific equipment mechanic to the outcome of a round.
    rider: e.g. 'honed', 'elusive', 'persistent'
    equip_round: which round the equipment was activated on (0, 1, 2)
    """
    if equip_round is None: return outcome

    state = outcome.new_state
    new_dmg = outcome.raw_dmg
    new_block = outcome.block
    new_heal = outcome.heal
    
    # Reconstruct the hero HP BEFORE this round's damage/heal hit it, 
    # so we can re-apply our modified dmg/heal.
    # outcome.new_hp = old_hp - dmg_taken + heal
    # old_hp = outcome.new_hp + dmg_taken - heal
    mod_hero_hp = outcome.new_hp + outcome.dmg_taken - outcome.heal
    
    # 1. Apply Persistent effects (from previous rounds)
    mod_block_bonus = state.eq_persistent_block
    state = replace(state, eq_persistent_block=0.0) # Reset it
    
    if state.eq_hot_active:
        mod_hero_hp = min(outcome.new_hero_max_hp, mod_hero_hp + 1)
        state = replace(state, eq_hot_active=False)

    # 2. Activate equipment THIS round
    active_this_round = (round_num == equip_round)
    if active_this_round:
        if rider == "death_pact":
            mod_hero_hp -= 2
        elif rider == "hot":
            mod_hero_hp = min(outcome.new_hero_max_hp, mod_hero_hp + 1)
            state = replace(state, eq_hot_active=True)
        elif rider == "sunder":
            state = replace(state, eq_sunder_active=True)

    # 3. Apply Sunder tracking
    if state.eq_sunder_active and new_dmg > 0:
        new_dmg += 1

    # 4. Apply standard buffs
    if active_this_round:
        if rider == "honed": new_dmg += 1
        elif rider == "reinforced": new_block += 3
        elif rider == "blessed": new_heal += 1
        elif rider == "death_pact": new_dmg += 3

    new_block += mod_block_bonus
    if active_this_round and rider == "persistent":
        state = replace(state, eq_persistent_block=new_block + 2) # +2 and carry over

    # 5. Re-calculate outcomes
    mob_atk, mob_block, *rest = mob_pattern[round_num]
    if active_this_round and rider == "armor_pierce":
        mob_block = max(0, mob_block - 2)
        
    dmg_dealt = max(0.0, new_dmg - mob_block)
    
    # new_rem = old_rem - dmg_dealt
    # old_rem = outcome.new_mob_hp_remaining + outcome.dmg_dealt
    old_rem = outcome.new_mob_hp_remaining + outcome.dmg_dealt
    new_rem = old_rem - dmg_dealt
    
    dmg_taken = max(0.0, mob_atk - new_block)
    if active_this_round and rider == "elusive" and (len(rest) == 0 or rest[0] == "melee"):
        dmg_taken = 0.0
        
    if active_this_round and rider == "ruthless" and new_rem <= 0:
        dmg_taken = 0.0
        
    if active_this_round and rider == "thorns" and dmg_taken > 0:
        new_rem -= 3 # Buffed thorns
        
    new_hero_hp = mod_hero_hp - dmg_taken + new_heal
    new_hero_hp = min(outcome.new_hero_max_hp, new_hero_hp)

    return replace(
        outcome,
        new_hp=new_hero_hp,
        new_mob_hp_remaining=new_rem,
        new_state=state,
        dmg_dealt=dmg_dealt,
        dmg_taken=dmg_taken,
        block=new_block,
        raw_dmg=new_dmg,
        heal=new_heal
    )