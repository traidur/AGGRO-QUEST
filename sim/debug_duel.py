import condensed_warrior as warrior
import condensed_wizard as wizard
from combat_round import RoundState

def test_duel():
    warrior_cards = warrior.CARDS
    wizard_cards = wizard.CARDS
    
    seq_W = (["Vanguard Shield", "Vanguard Blade", "Heavy Swing"], "G")
    seq_Z = (["Snap Freeze", "Fire Blast", "Arcane Volley"], None)
    
    hp_W = 18
    hp_Z = 14
    max_hp_W = 18
    max_hp_Z = 14
    
    state_W = RoundState()
    state_Z = RoundState()
    
    print(f"--- START DUEL ---")
    print(f"Warrior HP: {hp_W} | Wizard HP: {hp_Z}\n")
    
    cards_W = seq_W[0]
    stance_W = seq_W[1]
    cards_Z = seq_Z[0]
    stance_Z = seq_Z[1]
    
    for rnd in range(3):
        print(f"ROUND {rnd+1}:")
        cW = cards_W[rnd]
        cZ = cards_Z[rnd]
        print(f"  Warrior plays: {cW} [Melee]")
        print(f"  Wizard plays:  {cZ} [{wizard_cards[cZ]['combat_type'].capitalize()}]")
        
        dummy_pattern_2 = [(0,0)] * 3
        dummy_pattern_3 = [(0,0,"melee")] * 3
        
        out_W = warrior.resolve_round(state_W, cW, stance_W, rnd, dummy_pattern_2, max_hp_Z, hp_Z, hp_W, max_hp_W)
        out_Z = wizard.resolve_round(state_Z, cZ, stance_Z, rnd, dummy_pattern_3, max_hp_W, hp_W, hp_Z, max_hp_Z)
        
        raw_dmg_W, block_W, heal_W, state_W = out_W.raw_dmg, out_W.block, out_W.heal, out_W.new_state
        raw_dmg_Z, block_Z, heal_Z, state_Z = out_Z.raw_dmg, out_Z.block, out_Z.heal, out_Z.new_state
        
        type_W = warrior_cards[cW].get("combat_type", "melee")
        type_Z = wizard_cards[cZ].get("combat_type", "melee")
        
        evades_W = warrior_cards[cW].get("grants_range", False)
        evades_Z = wizard_cards[cZ].get("grants_range", False)
        
        print(f"    Warrior generates: {raw_dmg_W} Dmg, {block_W} Block")
        print(f"    Wizard generates:  {raw_dmg_Z} Dmg, {block_Z} Block" + (" (Grants Range!)" if evades_Z else ""))
        
        if evades_Z and type_W == "melee":
            print(f"    -> Wizard evades Warrior's melee attack! (Warrior dmg reduced to 0)")
            raw_dmg_W = 0
            
        eff_dmg_W = max(0, raw_dmg_W - block_Z)
        eff_dmg_Z = max(0, raw_dmg_Z - block_W)
        
        print(f"    Warrior takes {eff_dmg_Z} damage (Blocked {min(raw_dmg_Z, block_W)}).")
        print(f"    Wizard takes {eff_dmg_W} damage (Blocked {min(raw_dmg_W, block_Z)}).")
        
        hp_W = min(max_hp_W, hp_W - eff_dmg_Z + heal_W)
        hp_Z = min(max_hp_Z, hp_Z - eff_dmg_W + heal_Z)
        
        print(f"    End of Round -> Warrior HP: {hp_W}/{max_hp_W} | Wizard HP: {hp_Z}/{max_hp_Z}\n")
        
        if hp_W <= 0 or hp_Z <= 0:
            print("DUEL ENDED BY DEATH")
            break
            
    print(f"FINAL NET DIFFERENTIAL: Warrior took {18 - hp_W} dmg, Wizard took {14 - hp_Z} dmg")
    print(f"WINNER: {'Wizard' if (18 - hp_W) > (14 - hp_Z) else 'Warrior'}")

test_duel()
