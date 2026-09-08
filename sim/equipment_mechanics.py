def apply_equipment_mechanics(outcome, rider, base, round_num, equip_round, mob_pattern, state_tracker=None):
    """
    outcome: RoundOutcome
    rider: str (e.g. "honed", "ruthless")
    base: str (e.g. "1-Hander", "Heavy Armor")
    round_num: int
    equip_round: int (when it was activated)
    state_tracker: dict for cross-round effects (sunder, persistent)
    """
    if state_tracker is None: state_tracker = {}
    
    new_dmg = outcome.raw_dmg
    block = outcome.block
    heal = outcome.heal
    pat = mob_pattern[round_num] if round_num < len(mob_pattern) else (0, 0, "melee")
    mob_atk, mob_block = pat[0], pat[1]
    mob_type = pat[2] if len(pat) > 2 else "melee"
    
    is_active_round = (round_num == equip_round)
    
    # 1. Apply Persistent from previous rounds
    if state_tracker.get("persistent_active", False) and state_tracker.get("carryover_block", 0) > 0:
        block += state_tracker["carryover_block"]
        state_tracker["carryover_block"] = 0
        
    # 2. Apply Sunder from previous or current rounds
    if state_tracker.get("sunder_active", False) or (is_active_round and rider == "sunder"):
        if is_active_round and rider == "sunder":
            state_tracker["sunder_active"] = True
        new_dmg += 1

    # Apply Active Round effects
    if is_active_round:
        if rider == "honed":
            new_dmg += 1 if base in ["1-Hander", "Wand"] else 2
        elif rider == "blessed":
            heal += 2
        elif rider == "reinforced":
            if "Light" in base: block += 2
            elif "Medium" in base: block += 3
            elif "Heavy" in base: block += 4
        elif rider == "persistent":
            state_tracker["persistent_active"] = True
            
    # Calculate new outcome
    dmg_dealt = max(0.0, new_dmg - mob_block)
    
    if is_active_round and rider == "pierce":
        reduced_block = max(0, mob_block - 2)
        dmg_dealt = max(0.0, new_dmg - reduced_block)
        
    new_rem = outcome.new_mob_hp_remaining + outcome.dmg_dealt - dmg_dealt
    
    dmg_taken = max(0.0, mob_atk - block)
    
    if is_active_round and rider == "elusive" and mob_type == "melee":
        dmg_taken = 0.0
    if is_active_round and rider == "ruthless" and new_rem <= 0:
        dmg_taken = 0.0
        
    if is_active_round and rider == "thorns" and dmg_taken > 0:
        thorns_dmg = 2 if "Medium" in base else 3
        new_rem -= thorns_dmg

    # Save carryover block for next round
    if state_tracker.get("persistent_active", False):
        state_tracker["carryover_block"] = max(0, block - mob_atk)

    new_hp = outcome.new_hp + outcome.dmg_taken - outcome.heal - dmg_taken + heal
    new_hp = min(new_hp, outcome.new_hero_max_hp)

    from dataclasses import replace
    return replace(outcome, new_hp=new_hp, new_mob_hp_remaining=new_rem, dmg_dealt=dmg_dealt, dmg_taken=dmg_taken, raw_dmg=new_dmg, block=block, heal=heal)
