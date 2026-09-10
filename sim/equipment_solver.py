import itertools
from equipment_mechanics import apply_equipment_mechanics

def simulate_with_equipment(class_name, seq_cards, stance_seq, equipment, equip_usage, mob_pattern, mob_hp, starting_hp):
    from combat_engine import CARD_SOURCE, initial_max_hp
    mod = CARD_SOURCE[class_name]
    # max_hp must seed from each class's real heal ceiling (initial_max_hp, already built in
    # combat_engine.py for this exact problem), NOT from starting_hp directly -- classes with a
    # fixed healing ceiling independent of entering HP (Cleric/Paladin/Runecaster/Druid/
    # Necromancer) would otherwise have every Heal card silently clamped to whatever reduced HP
    # the pull started at. Confirmed via verify_equipment_solver.py: this alone produced wrong
    # hp_left/rounds for any Heal-using sequence whenever starting_hp < the class's real max.
    hp, remaining, max_hp = starting_hp, mob_hp, initial_max_hp(class_name, starting_hp)
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
        grants_range = mod.CARDS.get(seq_cards[rnd], {}).get("grants_range", False)
        for slot, recipe in equipment.items():
            activation_rnd = equip_usage.get(slot)
            if activation_rnd is not None:
                outcome = apply_equipment_mechanics(outcome, recipe["rider"], recipe["base"], rnd, activation_rnd, mob_pattern, state_tracker, grants_range=grants_range)
                
        hp, remaining, max_hp, state = outcome.new_hp, outcome.new_mob_hp_remaining, outcome.new_hero_max_hp, outcome.new_state
        if hp <= 0: return False, hp, rnd + 1
        if remaining <= 0: return True, hp, rnd + 1
        
    return False, hp, 3

def best_line_with_equipment(class_name, hand, mob_pattern, mob_hp, starting_hp, equipment):
    from combat_engine import CARD_SOURCE
    mod = CARD_SOURCE[class_name]
    best = None

    # Use the class's own orderings(hand) rather than a raw itertools.permutations rebuild --
    # identical to permutations for 8 of 9 classes, but Necromancer's orderings() additionally
    # expands Boneguard's Offering into its Death Pact "(Boosted)" variant, exactly like
    # best_line_for_hand's real search does. Reimplementing permutations here silently dropped
    # Death Pact as an option from every Necromancer equipment search (caught via a direct
    # anomaly: a "best" equipped line scored worse than the unequipped baseline's best line,
    # which should never happen since not using the item is always in the equipped search space).
    orderings = mod.orderings(hand)
    # Only Warrior actually has a stance mechanic -- Paladin's real resolve_round/simulate
    # always pass stance=None (checked directly: no STANCE_SEQS/stance_sequences() exists
    # anywhere in condensed_paladin.py). Inventing a "V"/"A" stance pair for Paladin was wrong;
    # every other class correctly gets stances=[None].
    if class_name == "warrior":
        stances = list(mod.STANCE_SEQS)
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
                # (win, hp_left) only -- matches every class's real best_line_for_hand ranking
                # key exactly. An added -rounds tiebreak here would pick a DIFFERENT tied
                # candidate than the reference solver on ties, which is exactly the kind of
                # silent divergence a second search implementation risks (see this project's
                # own EQUIPMENT_HANDOFF.md on why that's treated as a real bug, not a style nit).
                key = (win, hp_left)
                if best is None or key > best[0]:
                    best = (key, (win, seq_cards, stance_seq, hp_left, rounds, usage))

    return best[1]