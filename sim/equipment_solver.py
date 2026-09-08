import itertools
from equipment_mechanics import apply_equipment_mechanics

def simulate_with_equipment(class_name, seq_cards, stance_seq, equipment, equip_usage, mob_pattern, mob_hp, starting_hp):
    from combat_engine import CARD_SOURCE
    mod = CARD_SOURCE[class_name]
    hp, remaining, max_hp = starting_hp, mob_hp, starting_hp
    state = getattr(mod, "RoundState", lambda: None)()
    state_tracker = {}
    
    for rnd in range(3):
        stance = stance_seq[rnd] if stance_seq else None
        
        # Determine if execute is unlocked (PvP only, default false here)
        if hasattr(mod, "resolve_round") and "execute_unlocked" in mod.resolve_round.__code__.co_varnames:
            base_outcome = mod.resolve_round(state, seq_cards[rnd], stance, rnd, mob_pattern, mob_hp, remaining, hp, max_hp, execute_unlocked=False)
        else:
            base_outcome = mod.resolve_round(state, seq_cards[rnd], stance, rnd, mob_pattern, mob_hp, remaining, hp, max_hp)
            
        if base_outcome is None: return False, float('-inf'), rnd
        
        outcome = base_outcome
        for slot, recipe in equipment.items():
            activation_rnd = equip_usage.get(slot)
            if activation_rnd is not None:
                outcome = apply_equipment_mechanics(outcome, recipe["rider"], recipe["base"], rnd, activation_rnd, mob_pattern, state_tracker)
                
        hp, remaining, max_hp, state = outcome.new_hp, outcome.new_mob_hp_remaining, outcome.new_hero_max_hp, outcome.new_state
        if hp <= 0: return False, hp, rnd + 1
        if remaining <= 0: return True, hp, rnd + 1
        
    return False, hp, 3

def best_line_with_equipment(class_name, hand, mob_pattern, mob_hp, starting_hp, equipment):
    from combat_engine import CARD_SOURCE
    mod = CARD_SOURCE[class_name]
    best = None
    
    orderings = list(itertools.permutations(hand, 3))
    if class_name in ["warrior", "paladin"]:
        stances = [("G","G","G"), ("C","C","C")] if class_name == "warrior" else [("V","V","V"), ("A","A","A")]
    else:
        stances = [None]
        
    slots = list(equipment.keys())
    usage_perms = []
    for rnds in itertools.product([0, 1, 2, None], repeat=len(slots)):
        usage_perms.append(dict(zip(slots, rnds)))
        
    for seq_cards in orderings:
        for stance_seq in stances:
            for usage in usage_perms:
                win, hp_left, rounds = simulate_with_equipment(class_name, seq_cards, stance_seq, equipment, usage, mob_pattern, mob_hp, starting_hp)
                key = (win, hp_left, -rounds)
                if best is None or key > best[0]:
                    best = (key, (seq_cards, stance_seq, hp_left, rounds, usage))
                    
    return best[1]