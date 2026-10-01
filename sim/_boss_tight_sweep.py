"""
Sweep script to find boss profiles with:
1. Average win rate ~75%
2. Minimal spread across all 9 classes (max_win - min_win as low as possible)
3. Both death failure and damage failure active
"""
import sys
sys.path.insert(0, 'sim')
import itertools
import macro_sim as M
import leveling_validation as LV
import _boss_phase_sim as B

CLASSES = list(M.CARD_SOURCE.keys())

def make_formatter(type_seq1, type_seq2):
    def fmt1(raw_pat, cls):
        if cls in B.RANGE_CLASSES:
            return [(a, b, type_seq1[i]) for i, (a, b) in enumerate(raw_pat)]
        return [(a, b) for a, b in raw_pat]
    def fmt2(raw_pat, cls):
        if cls in B.RANGE_CLASSES:
            return [(a, b, type_seq2[i]) for i, (a, b) in enumerate(raw_pat)]
        return [(a, b) for a, b in raw_pat]
    return fmt1, fmt2

def eval_profile(p1_pat, p1_hp, p2_pat, p2_hp, fmt1, fmt2):
    results = {}
    for class_name in CLASSES:
        mod = M.CARD_SOURCE[class_name]
        start_hp = getattr(mod, M.HP_ATTR[class_name])
        mand = M.LEVEL2_MANDATORY[class_name]
        purch = M.LEVEL2_PURCHASED_ORDER[class_name]
        
        c_pat1 = fmt1(p1_pat, class_name)
        c_pat2 = fmt2(p2_pat, class_name)
        
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
                for h1 in hands:
                    win1, hp1, r1 = B.simulate_phase(mod, class_name, h1, c_pat1, p1_hp, start_hp)
                    if not win1:
                        for _ in hands:
                            total_runs += 1
                            if hp1 <= 0:
                                p1_death += 1
                            else:
                                p1_dmg_fail += 1
                        continue
                    
                    for h2 in hands:
                        total_runs += 1
                        win2, hp2, r2 = B.simulate_phase(mod, class_name, h2, c_pat2, p2_hp, hp1)
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
            "total_death": (p1_death + p2_death) / total_runs,
            "total_dmg_fail": (p1_dmg_fail + p2_dmg_fail) / total_runs,
        }
    return results

# Sweep candidates
type_configs = [
    ("R-M-R / R-M-R", ('ranged', 'melee', 'ranged'), ('ranged', 'melee', 'ranged')),
    ("M-R-M / R-M-R", ('melee', 'ranged', 'melee'), ('ranged', 'melee', 'ranged')),
    ("R-M-M / M-R-R", ('ranged', 'melee', 'melee'), ('melee', 'ranged', 'ranged')),
    ("R-R-M / R-M-R", ('ranged', 'ranged', 'melee'), ('ranged', 'melee', 'ranged')),
]

p1_patterns = [
    ("Balanced P1 (3,1)-(3,0)-(3,0)", [(3, 1), (3, 0), (3, 0)]),
    ("Tempered P1 (3,1)-(4,0)-(3,0)", [(3, 1), (4, 0), (3, 0)]),
    ("Sturdy P1 (3,1)-(3,1)-(4,0)", [(3, 1), (3, 1), (4, 0)]),
    ("Rising P1 (2,1)-(3,0)-(4,0)", [(2, 1), (3, 0), (4, 0)]),
    ("Front P1 (4,1)-(3,0)-(3,0)", [(4, 1), (3, 0), (3, 0)]),
]

p2_patterns = [
    ("Furious P2 (4,0)-(4,0)-(4,0)", [(4, 0), (4, 0), (4, 0)]),
    ("Heavy P2 (3,0)-(4,0)-(4,0)", [(3, 0), (4, 0), (4, 0)]),
    ("Burst P2 (4,0)-(5,0)-(3,0)", [(4, 0), (5, 0), (3, 0)]),
    ("Ramping P2 (3,0)-(4,0)-(5,0)", [(3, 0), (4, 0), (5, 0)]),
    ("Shielded P2 (4,1)-(4,0)-(4,0)", [(4, 1), (4, 0), (4, 0)]),
]

hp_options = [
    (8, 9),
    (9, 8),
    (9, 9),
    (8, 10),
    (9, 10),
    (10, 8),
    (10, 9),
]

candidates = []

print("Starting sweep across type configurations, patterns, and HP...")
for type_label, t1, t2 in type_configs:
    fmt1, fmt2 = make_formatter(t1, t2)
    for p1_name, p1_pat in p1_patterns:
        for p2_name, p2_pat in p2_patterns:
            for hp1, hp2 in hp_options:
                res = eval_profile(p1_pat, hp1, p2_pat, hp2, fmt1, fmt2)
                wins = [r['win_rate'] for r in res.values()]
                avg_win = sum(wins) / len(wins)
                spread = max(wins) - min(wins)
                
                # We want avg_win between 68% and 82%, and spread < 0.25
                if 0.68 <= avg_win <= 0.82 and spread <= 0.25:
                    avg_end_hp = sum(r['avg_end_hp'] for r in res.values()) / len(res)
                    avg_death = sum(r['total_death'] for r in res.values()) / len(res)
                    avg_dmg = sum(r['total_dmg_fail'] for r in res.values()) / len(res)
                    candidates.append({
                        "types": type_label,
                        "p1_name": p1_name, "p1_pat": p1_pat, "hp1": hp1,
                        "p2_name": p2_name, "p2_pat": p2_pat, "hp2": hp2,
                        "avg_win": avg_win,
                        "spread": spread,
                        "min_win": min(wins),
                        "max_win": max(wins),
                        "end_hp": avg_end_hp,
                        "death": avg_death,
                        "dmg_fail": avg_dmg,
                        "res": res,
                    })

print(f"Sweep complete! Found {len(candidates)} candidates matching criteria.")
# Sort primarily by lowest spread, secondarily by proximity to 75%
candidates.sort(key=lambda x: (x['spread'], abs(x['avg_win'] - 0.75)))

for i, c in enumerate(candidates[:10]):
    print(f"\nRANK #{i+1} [Spread: {c['spread']*100:.1f}%, Avg Win: {c['avg_win']*100:.1f}%, Range: {c['min_win']*100:.1f}% - {c['max_win']*100:.1f}%]")
    print(f"  Types: {c['types']}")
    print(f"  P1: {c['p1_name']} | HP: {c['hp1']} | Pat: {c['p1_pat']}")
    print(f"  P2: {c['p2_name']} | HP: {c['hp2']} | Pat: {c['p2_pat']}")
    print(f"  Death Fail: {c['death']*100:.1f}% | Dmg Fail: {c['dmg_fail']*100:.1f}% | Avg End HP: {c['end_hp']:.1f}")
    print("  Class Breakdown:")
    for cls_name, r in c['res'].items():
        print(f"    {cls_name:12}: Win {r['win_rate']*100:5.1f}% | End HP {r['avg_end_hp']:4.1f} | Death {r['total_death']*100:4.1f}% | DmgFail {r['total_dmg_fail']*100:4.1f}%")
