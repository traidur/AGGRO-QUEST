"""
Boss Phase Simulation:
6-round, 2-phase battle for Level 2 heroes (Mandatory + 2-of-3 purchased upgrades).
No resting or consumables between phases.
Evaluates all 3 combos of 2-of-3 upgrades x 15 hands P1 x 15 hands P2 = 675 hand-pairs per class.
"""

import sys
sys.path.insert(0, 'sim')
import itertools
import macro_sim as M
import leveling_validation as LV
import combat_engine as CE

CLASSES = list(M.CARD_SOURCE.keys())
RANGE_CLASSES = {"wizard", "rogue", "ranger", "runecaster", "necromancer"}

def format_pattern(raw_pattern, class_name):
    if class_name in RANGE_CLASSES:
        return [(atk, blk, "melee") for atk, blk in raw_pattern]
    return [(atk, blk) for atk, blk in raw_pattern]

def simulate_phase(mod, class_name, hand, pattern, mob_hp, current_hp):
    """
    Simulates one 3-round phase using best_line_for_hand.
    Returns (win, remaining_hero_hp, rounds_used).
    """
    if class_name == "warrior":
        seq_cards, stance_seq, hp_left, rounds = mod.best_line_for_hand(
            hand, pattern, mob_hp, starting_hp=current_hp
        )
        win, final_hp, final_rounds = mod.simulate(
            seq_cards, stance_seq, pattern, mob_hp, starting_hp=current_hp
        )
    else:
        seq_cards, hp_left, rounds = mod.best_line_for_hand(
            hand, pattern, mob_hp, starting_hp=current_hp
        )
        win, final_hp, final_rounds = mod.simulate(
            seq_cards, pattern, mob_hp, starting_hp=current_hp
        )
    return win, final_hp, final_rounds

def eval_boss(p1_pattern, p1_hp, p2_pattern, p2_hp):
    """
    Evaluates boss profile across all 9 classes.
    """
    results = {}
    for class_name in CLASSES:
        mod = M.CARD_SOURCE[class_name]
        start_hp = getattr(mod, M.HP_ATTR[class_name])
        mand = M.LEVEL2_MANDATORY[class_name]
        purch = M.LEVEL2_PURCHASED_ORDER[class_name]
        
        c_pat1 = format_pattern(p1_pattern, class_name)
        c_pat2 = format_pattern(p2_pattern, class_name)
        
        total_runs = 0
        wins = 0
        p1_death = 0
        p1_dmg_fail = 0
        p2_death = 0
        p2_dmg_fail = 0
        win_ending_hps = []
        
        combos = list(itertools.combinations(range(3), 2))
        for combo in combos:
            swaps = {}
            _, old_name, new_name, new_card = mand
            swaps[old_name] = (new_name, new_card)
            for idx in combo:
                old_name, new_name, new_card = purch[idx]
                swaps[old_name] = (new_name, new_card)
                
            with LV.leveled_kit(mod, swaps):
                hands = mod.ALL_HANDS
                # For each possible hand in Phase 1
                for h1 in hands:
                    win1, hp1, r1 = simulate_phase(mod, class_name, h1, c_pat1, p1_hp, start_hp)
                    if not win1:
                        # Phase 1 failed for all 15 Phase 2 hands
                        for _ in hands:
                            total_runs += 1
                            if hp1 <= 0:
                                p1_death += 1
                            else:
                                p1_dmg_fail += 1
                        continue
                    
                    # Phase 1 won! Hero moves to Phase 2 with hp1
                    for h2 in hands:
                        total_runs += 1
                        win2, hp2, r2 = simulate_phase(mod, class_name, h2, c_pat2, p2_hp, hp1)
                        if win2:
                            wins += 1
                            win_ending_hps.append(hp2)
                        else:
                            if hp2 <= 0:
                                p2_death += 1
                            else:
                                p2_dmg_fail += 1
                                
        win_rate = wins / total_runs
        avg_end_hp = sum(win_ending_hps) / len(win_ending_hps) if win_ending_hps else 0.0
        results[class_name] = {
            "win_rate": win_rate,
            "avg_end_hp": avg_end_hp,
            "start_hp": start_hp,
            "p1_death": p1_death / total_runs,
            "p1_dmg_fail": p1_dmg_fail / total_runs,
            "p2_death": p2_death / total_runs,
            "p2_dmg_fail": p2_dmg_fail / total_runs,
            "total_death": (p1_death + p2_death) / total_runs,
            "total_dmg_fail": (p1_dmg_fail + p2_dmg_fail) / total_runs,
        }
    return results

if __name__ == "__main__":
    # Test a baseline candidate
    # P1: Tactical Inquisitor form: 7 HP, [(3, 1), (3, 0), (3, 0)]
    # P2: Enraged Sun Form: 7 HP, [(4, 0), (3, 0), (4, 0)]
    p1_pat = [(3, 1), (3, 0), (3, 0)]
    p1_hp = 7
    p2_pat = [(4, 0), (3, 0), (4, 0)]
    p2_hp = 7
    
    print(f"Testing Candidate 1: P1={p1_hp} HP {p1_pat} | P2={p2_hp} HP {p2_pat}")
    res = eval_boss(p1_pat, p1_hp, p2_pat, p2_hp)
    avg_win = sum(r['win_rate'] for r in res.values()) / len(res)
    print(f"OVERALL AVERAGE WIN RATE: {avg_win*100:.1f}%\n")
    print(f"{'Class':12} {'Win%':7} {'End HP':8} {'Start':6} {'Death%':8} {'DmgFail%':9}")
    print("-" * 55)
    for c, r in res.items():
        print(f"{c:12} {r['win_rate']*100:6.1f}% {r['avg_end_hp']:7.1f}  {r['start_hp']:5}  {r['total_death']*100:7.1f}% {r['total_dmg_fail']*100:8.1f}%")
