"""
Sweep across boss parameter space to find profiles with ~75% overall win rate
and close-to-death ending HP.
"""

import sys
sys.path.insert(0, 'sim')
import itertools
import macro_sim as M
import leveling_validation as LV
from _boss_phase_sim import eval_boss, CLASSES

p1_patterns = [
    ("Shielded Cleave", [(3, 2), (4, 0), (4, 0)]),
    ("Inquisitor Strike", [(4, 1), (4, 0), (5, 0)]),
    ("Heavy Ramp", [(3, 1), (4, 1), (5, 0)]),
]

p2_patterns = [
    ("Enraged Assault", [(5, 0), (4, 0), (5, 0)]),
    ("Unleashed Fury", [(5, 0), (5, 0), (5, 0)]),
    ("Executioner", [(4, 0), (5, 0), (6, 0)]),
]

hp_pairs = [
    (8, 8),
    (9, 8),
    (8, 9),
    (9, 9),
    (10, 8),
    (9, 10),
    (10, 9),
    (10, 10),
]

candidates = []

print("Running parameter sweep across all 9 classes...")
for (name1, pat1) in p1_patterns:
    for (name2, pat2) in p2_patterns:
        for (hp1, hp2) in hp_pairs:
            res = eval_boss(pat1, hp1, pat2, hp2)
            avg_win = sum(r['win_rate'] for r in res.values()) / len(res)
            avg_end_hp = sum(r['avg_end_hp'] for r in res.values()) / len(res)
            avg_death = sum(r['total_death'] for r in res.values()) / len(res)
            avg_dmg_fail = sum(r['total_dmg_fail'] for r in res.values()) / len(res)
            
            # We want win rate between 70% and 80%, with low end HP
            candidates.append({
                "name": f"{name1} ({hp1}HP) -> {name2} ({hp2}HP)",
                "p1_pat": pat1, "hp1": hp1,
                "p2_pat": pat2, "hp2": hp2,
                "win": avg_win,
                "end_hp": avg_end_hp,
                "death": avg_death,
                "dmg_fail": avg_dmg_fail,
                "res": res
            })

# Sort by proximity to 75% win rate
candidates.sort(key=lambda x: abs(x['win'] - 0.75))

print("\nTOP CANDIDATES NEAR 75% WIN RATE:")
print("=" * 80)
for c in candidates[:8]:
    print(f"Profile: {c['name']}")
    print(f"  P1 Pattern: {c['p1_pat']} (HP {c['hp1']})")
    print(f"  P2 Pattern: {c['p2_pat']} (HP {c['hp2']})")
    print(f"  Overall Win Rate: {c['win']*100:.1f}% | Avg End HP: {c['end_hp']:.1f}")
    print(f"  Total Death Fail: {c['death']*100:.1f}% | Total Dmg Fail: {c['dmg_fail']*100:.1f}%")
    print("  Per-Class Breakdown:")
    for cls_name, r in c['res'].items():
        print(f"    {cls_name:12}: Win {r['win_rate']*100:5.1f}% | End HP {r['avg_end_hp']:4.1f} | Death {r['total_death']*100:4.1f}% | DmgFail {r['total_dmg_fail']*100:4.1f}%")
    print("-" * 80)
