"""
Fast Memoized Sweep for Boss Gate Tuning:
Caches Phase 1 HP distributions and Phase 2 outcomes.
Runs 100x faster than raw nested loops.
"""
import sys
sys.path.insert(0, 'sim')
import itertools
from collections import Counter
import macro_sim as M
import leveling_validation as LV
import _boss_phase_sim as B

CLASSES = list(M.CARD_SOURCE.keys())

def make_formatter(type_seq1, type_seq2):
    def fmt1(raw_pat, cls):
        if cls in B.RANGE_CLASSES:
            return tuple((a, b, type_seq1[i]) for i, (a, b) in enumerate(raw_pat))
        return tuple((a, b) for a, b in raw_pat)
    def fmt2(raw_pat, cls):
        if cls in B.RANGE_CLASSES:
            return tuple((a, b, type_seq2[i]) for i, (a, b) in enumerate(raw_pat))
        return tuple((a, b) for a, b in raw_pat)
    return fmt1, fmt2

# Pre-extract kit swaps for each class
CLASS_KITS = {}
for class_name in CLASSES:
    mand = M.LEVEL2_MANDATORY[class_name]
    purch = M.LEVEL2_PURCHASED_ORDER[class_name]
    combos = list(itertools.combinations(range(3), 2))
    kits = []
    for combo in combos:
        swaps = {}
        _, old_name, new_name, new_card = mand
        swaps[old_name] = (new_name, new_card)
        for idx in combo:
            old_name, new_name, new_card = purch[idx]
            swaps[old_name] = (new_name, new_card)
        kits.append((combo, swaps))
    CLASS_KITS[class_name] = kits

# Caches
# p1_cache: (class_name, combo_idx, c_pat1, p1_hp) -> (p1_death_count, p1_dmg_fail_count, {hp1: count})
P1_CACHE = {}
# p2_cache: (class_name, combo_idx, c_pat2, p2_hp, hp1) -> (win_count, death_count, dmg_fail_count, sum_end_hp)
P2_CACHE = {}

def get_p1_dist(class_name, combo_idx, swaps, c_pat1, p1_hp):
    key = (class_name, combo_idx, c_pat1, p1_hp)
    if key in P1_CACHE:
        return P1_CACHE[key]
    
    mod = M.CARD_SOURCE[class_name]
    start_hp = getattr(mod, M.HP_ATTR[class_name])
    deaths = 0
    dmg_fails = 0
    survivors = Counter()
    
    with LV.leveled_kit(mod, swaps):
        for h1 in mod.ALL_HANDS:
            win1, hp1, _ = B.simulate_phase(mod, class_name, h1, c_pat1, p1_hp, start_hp)
            if not win1:
                if hp1 <= 0:
                    deaths += 1
                else:
                    dmg_fails += 1
            else:
                survivors[hp1] += 1
                
    res = (deaths, dmg_fails, dict(survivors))
    P1_CACHE[key] = res
    return res

def get_p2_outcome(class_name, combo_idx, swaps, c_pat2, p2_hp, hp1):
    key = (class_name, combo_idx, c_pat2, p2_hp, hp1)
    if key in P2_CACHE:
        return P2_CACHE[key]
    
    mod = M.CARD_SOURCE[class_name]
    wins = 0
    deaths = 0
    dmg_fails = 0
    end_hps = []
    
    with LV.leveled_kit(mod, swaps):
        for h2 in mod.ALL_HANDS:
            win2, hp2, _ = B.simulate_phase(mod, class_name, h2, c_pat2, p2_hp, hp1)
            if win2:
                wins += 1
                end_hps.append(hp2)
            else:
                if hp2 <= 0:
                    deaths += 1
                else:
                    dmg_fails += 1
                    
    res = (wins, deaths, dmg_fails, sum(end_hps))
    P2_CACHE[key] = res
    return res

def eval_profile_fast(p1_pat, p1_hp, p2_pat, p2_hp, fmt1, fmt2):
    results = {}
    for class_name in CLASSES:
        mod = M.CARD_SOURCE[class_name]
        start_hp = getattr(mod, M.HP_ATTR[class_name])
        c_pat1 = fmt1(p1_pat, class_name)
        c_pat2 = fmt2(p2_pat, class_name)
        
        total_runs = 0
        total_wins = 0
        total_death = 0
        total_dmg_fail = 0
        sum_win_hps = 0
        
        kits = CLASS_KITS[class_name]
        for combo_idx, (combo, swaps) in enumerate(kits):
            p1_deaths, p1_dmg_fails, survivors = get_p1_dist(class_name, combo_idx, swaps, c_pat1, p1_hp)
            # Each P1 fail applies across all 15 P2 hands
            total_runs += p1_deaths * 15
            total_death += p1_deaths * 15
            
            total_runs += p1_dmg_fails * 15
            total_dmg_fail += p1_dmg_fails * 15
            
            # For surviving P1 hands:
            for hp1, p1_count in survivors.items():
                w, d, df, h_sum = get_p2_outcome(class_name, combo_idx, swaps, c_pat2, p2_hp, hp1)
                total_runs += p1_count * 15
                total_wins += p1_count * w
                total_death += p1_count * d
                total_dmg_fail += p1_count * df
                sum_win_hps += p1_count * h_sum
                
        win_rate = total_wins / total_runs if total_runs else 0.0
        avg_end_hp = sum_win_hps / total_wins if total_wins else 0.0
        results[class_name] = {
            "win_rate": win_rate,
            "avg_end_hp": avg_end_hp,
            "start_hp": start_hp,
            "total_death": total_death / total_runs,
            "total_dmg_fail": total_dmg_fail / total_runs,
        }
    return results

if __name__ == "__main__":
    type_configs = [
        ("R-M-R / R-M-R", ('ranged', 'melee', 'ranged'), ('ranged', 'melee', 'ranged')),
        ("M-R-M / R-M-R", ('melee', 'ranged', 'melee'), ('ranged', 'melee', 'ranged')),
        ("R-M-M / M-R-R", ('ranged', 'melee', 'melee'), ('melee', 'ranged', 'ranged')),
        ("R-R-M / R-M-R", ('ranged', 'ranged', 'melee'), ('ranged', 'melee', 'ranged')),
        ("R-M-R / M-R-M", ('ranged', 'melee', 'ranged'), ('melee', 'ranged', 'melee')),
    ]

    p1_patterns = [
        ("Balanced P1 (3,1)-(3,0)-(3,0)", ((3, 1), (3, 0), (3, 0))),
        ("Tempered P1 (3,1)-(4,0)-(3,0)", ((3, 1), (4, 0), (3, 0))),
        ("Sturdy P1 (3,1)-(3,1)-(4,0)", ((3, 1), (3, 1), (4, 0))),
        ("Rising P1 (2,1)-(3,0)-(4,0)", ((2, 1), (3, 0), (4, 0))),
        ("Front P1 (4,1)-(3,0)-(3,0)", ((4, 1), (3, 0), (3, 0))),
        ("Pervasive P1 (3,0)-(3,0)-(3,0)", ((3, 0), (3, 0), (3, 0))),
    ]

    p2_patterns = [
        ("Furious P2 (4,0)-(4,0)-(4,0)", ((4, 0), (4, 0), (4, 0))),
        ("Heavy P2 (3,0)-(4,0)-(4,0)", ((3, 0), (4, 0), (4, 0))),
        ("Burst P2 (4,0)-(5,0)-(3,0)", ((4, 0), (5, 0), (3, 0))),
        ("Ramping P2 (3,0)-(4,0)-(5,0)", ((3, 0), (4, 0), (5, 0))),
        ("Shielded P2 (4,1)-(4,0)-(4,0)", ((4, 1), (4, 0), (4, 0))),
        ("Equal P2 (3,0)-(3,0)-(4,0)", ((3, 0), (3, 0), (4, 0))),
    ]

    hp_options = [
        (8, 8),
        (8, 9),
        (9, 8),
        (9, 9),
        (8, 10),
        (9, 10),
        (10, 8),
        (10, 9),
    ]

    total_combos = len(type_configs) * len(p1_patterns) * len(p2_patterns) * len(hp_options)
    print(f"Total profiles to evaluate: {total_combos}", flush=True)

    candidates = []
    evaluated = 0

    for type_label, t1, t2 in type_configs:
        fmt1, fmt2 = make_formatter(t1, t2)
        for p1_name, p1_pat in p1_patterns:
            for p2_name, p2_pat in p2_patterns:
                for hp1, hp2 in hp_options:
                    evaluated += 1
                    res = eval_profile_fast(p1_pat, hp1, p2_pat, hp2, fmt1, fmt2)
                    wins = [r['win_rate'] for r in res.values()]
                    avg_win = sum(wins) / len(wins)
                    spread = max(wins) - min(wins)
                    
                    if evaluated % 200 == 0:
                        print(f"Progress: {evaluated}/{total_combos} profiles evaluated...", flush=True)
                    
                    if 0.68 <= avg_win <= 0.82 and spread <= 0.20:
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

    print(f"\nDone! Found {len(candidates)} profiles with spread <= 20% and avg_win 68-82%.", flush=True)
    # Sort primarily by lowest spread
    candidates.sort(key=lambda x: (x['spread'], abs(x['avg_win'] - 0.75)))

    for i, c in enumerate(candidates[:8]):
        print(f"\n=== RANK #{i+1} [Spread: {c['spread']*100:.1f}%, Avg Win: {c['avg_win']*100:.1f}%, Range: {c['min_win']*100:.1f}% - {c['max_win']*100:.1f}%] ===", flush=True)
        print(f"  Types: {c['types']}", flush=True)
        print(f"  P1: {c['p1_name']} | HP: {c['hp1']} | Pat: {c['p1_pat']}", flush=True)
        print(f"  P2: {c['p2_name']} | HP: {c['hp2']} | Pat: {c['p2_pat']}", flush=True)
        print(f"  Death Fail: {c['death']*100:.1f}% | Dmg Fail: {c['dmg_fail']*100:.1f}% | Avg End HP: {c['end_hp']:.1f}", flush=True)
        print("  Class Breakdown:", flush=True)
        for cls_name, r in c['res'].items():
            print(f"    {cls_name:12}: Win {r['win_rate']*100:5.1f}% | End HP {r['avg_end_hp']:4.1f} | Death {r['total_death']*100:4.1f}% | DmgFail {r['total_dmg_fail']*100:4.1f}%", flush=True)
