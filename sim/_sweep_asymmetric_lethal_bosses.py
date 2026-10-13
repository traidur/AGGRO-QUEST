"""
Sweep script to find 3 distinct, lethal, asymmetric boss profiles:
1. Low ending HP (1.0 - 3.0 HP average across roster)
2. Significant death threat (10% - 25% death rate)
3. Clear class distance (each boss is easier for a different subset of classes)
"""

import sys
sys.path.insert(0, 'sim')
import itertools
from collections import Counter
import macro_sim as M
import leveling_validation as LV
import _boss_phase_sim as B
import _boss_fast_sweep as BFS

CLASSES = list(M.CARD_SOURCE.keys())

# Define candidate type sequences
TYPE_OPTIONS = [
    ("Heavy Ranged", ('ranged', 'ranged', 'melee'), ('ranged', 'ranged', 'melee')),
    ("Heavy Melee", ('melee', 'melee', 'ranged'), ('melee', 'melee', 'ranged')),
    ("Alternating R-M", ('ranged', 'melee', 'ranged'), ('melee', 'ranged', 'melee')),
    ("Alternating M-R", ('melee', 'ranged', 'melee'), ('ranged', 'melee', 'ranged')),
    ("Pure Melee", ('melee', 'melee', 'melee'), ('melee', 'melee', 'melee')),
]

# Phase 1 patterns: (atk, blk)
P1_PATTERNS = [
    ("P1_Lethal1 (3,0)-(4,0)-(4,0)", ((3, 0), (4, 0), (4, 0)), 10),
    ("P1_Lethal2 (3,1)-(4,0)-(4,0)", ((3, 1), (4, 0), (4, 0)), 10),
    ("P1_Lethal3 (4,0)-(3,1)-(4,0)", ((4, 0), (3, 1), (4, 0)), 10),
    ("P1_Spike (2,1)-(5,0)-(4,0)", ((2, 1), (5, 0), (4, 0)), 10),
    ("P1_HeavyArmor (3,2)-(4,0)-(4,0)", ((3, 2), (4, 0), (4, 0)), 9),
    ("P1_Relentless (4,0)-(4,0)-(3,1)", ((4, 0), (4, 0), (3, 1)), 10),
]

# Phase 2 patterns: (atk, blk)
P2_PATTERNS = [
    ("P2_Lethal1 (4,0)-(5,0)-(4,0)", ((4, 0), (5, 0), (4, 0)), 10),
    ("P2_Lethal2 (4,0)-(4,0)-(5,0)", ((4, 0), (4, 0), (5, 0)), 10),
    ("P2_Lethal3 (5,0)-(4,0)-(4,0)", ((5, 0), (4, 0), (4, 0)), 10),
    ("P2_ShieldSpike (4,1)-(4,0)-(5,0)", ((4, 1), (4, 0), (5, 0)), 10),
    ("P2_Brutal (5,0)-(4,0)-(5,0)", ((5, 0), (4, 0), (5, 0)), 9),
    ("P2_Heavy (4,1)-(5,0)-(4,0)", ((4, 1), (5, 0), (4, 0)), 10),
]

def run_sweep():
    candidates = []
    
    for (t_name, t1, t2) in TYPE_OPTIONS:
        fmt1, fmt2 = BFS.make_formatter(t1, t2)
        for (p1_name, p1_pat, hp1) in P1_PATTERNS:
            for (p2_name, p2_pat, hp2) in P2_PATTERNS:
                res = BFS.eval_profile_fast(p1_pat, hp1, p2_pat, hp2, fmt1, fmt2)
                wins = {c: res[c]['win_rate'] for c in CLASSES}
                end_hps = {c: res[c]['avg_end_hp'] for c in CLASSES if res[c]['win_rate'] > 0}
                deaths = {c: res[c]['total_death'] for c in CLASSES}
                
                avg_win = sum(wins.values()) / len(wins)
                avg_hp = sum(end_hps.values()) / len(end_hps) if end_hps else 0
                avg_death = sum(deaths.values()) / len(deaths)
                spread = max(wins.values()) - min(wins.values())
                
                # We want:
                # - Overall avg win rate between 68% and 80%
                # - Average ending HP between 1.0 and 3.5 HP (low!)
                # - Death rate >= 10%
                # - Spread >= 20% (good distance between classes!)
                if 0.68 <= avg_win <= 0.80 and 1.0 <= avg_hp <= 3.5 and avg_death >= 0.08 and spread >= 0.20:
                    candidates.append({
                        'type_name': t_name,
                        't1': t1,
                        't2': t2,
                        'p1_name': p1_name,
                        'p1_pat': p1_pat,
                        'hp1': hp1,
                        'p2_name': p2_name,
                        'p2_pat': p2_pat,
                        'hp2': hp2,
                        'avg_win': avg_win,
                        'avg_hp': avg_hp,
                        'avg_death': avg_death,
                        'spread': spread,
                        'wins': wins,
                        'end_hps': end_hps,
                        'deaths': deaths,
                    })

    print(f"Found {len(candidates)} viable candidates satisfying all constraints.")
    return candidates

if __name__ == '__main__':
    candidates = run_sweep()
    # Sort candidates by spread descending
    candidates.sort(key=lambda c: c['spread'], reverse=True)
    
    print("\nTOP CANDIDATES:")
    for i, c in enumerate(candidates[:15]):
        print(f"\n--- Candidate #{i+1} ---")
        print(f"Profile: {c['type_name']} | P1: {c['p1_name']} ({c['hp1']} HP) | P2: {c['p2_name']} ({c['hp2']} HP)")
        print(f"Avg Win: {c['avg_win']*100:.1f}% | Avg End HP: {c['avg_hp']:.2f} HP | Avg Death: {c['avg_death']*100:.1f}% | Spread: {c['spread']*100:.1f}%")
        # Print top 3 easiest and top 3 hardest classes
        sorted_cls = sorted(c['wins'].items(), key=lambda x: x[1], reverse=True)
        top3 = ", ".join([f"{cls} ({w*100:.0f}%)" for cls, w in sorted_cls[:3]])
        bot3 = ", ".join([f"{cls} ({w*100:.0f}%)" for cls, w in sorted_cls[-3:]])
        print(f"  Easiest for: {top3}")
        print(f"  Hardest for: {bot3}")
