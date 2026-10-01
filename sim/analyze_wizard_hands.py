import condensed_trip as T
import leveling_validation as L
import macro_sim as M
from condensed_wizard import WIZARD_HP, CARDS, DECK, ALL_HANDS
import itertools

def evaluate_hands():
    W = __import__("condensed_wizard")
    max_hp = float(WIZARD_HP)
    
    # Apply Level 2 swaps
    swaps = {}
    mod, old, new, d = M.LEVEL2_MANDATORY["wizard"]
    swaps[old] = (new, d)
    for old, new, d in M.LEVEL2_PURCHASED_ORDER["wizard"]:
        swaps[old] = (new, d)
        
    print("Level 2 Wizard Hands against Brute (Standard):")
    brute_pattern = T.MOBS["Bruiser"]["wizard"][0]
    brute_hp = T.MOBS["Bruiser"]["wizard"][1]
    
    with L.leveled_kit(W, swaps) as leveled:
        for i, hand in enumerate(leveled.ALL_HANDS):
            seq, stance, hp_left, rounds = T._best_line(leveled, False, hand, brute_pattern, brute_hp, max_hp)
            cost = max_hp - hp_left
            cost_pct = (cost / max_hp) * 100
            print(f"Hand {i+1}: {', '.join(hand)}")
            print(f"  Best Sequence: {', '.join(seq)} (Rounds: {rounds})")
            print(f"  HP Cost: {cost} ({cost_pct:.1f}%)")
            print()

if __name__ == "__main__":
    evaluate_hands()
