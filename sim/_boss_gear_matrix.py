"""
Comprehensive Matrix Simulation:
Evaluates 4 Upgrade Levels x 4 Gear States = 16 Loadouts per class
across all 3 Tier-Gate Bosses.

Upgrade Levels:
1. Level 2 Mandatory only (1 kit)
2. Level 2 Mandatory + 1 purchased skill (average over 3 choices)
3. Level 2 Mandatory + 2 purchased skills (average over 3 choices)
4. Level 2 Mandatory + all 3 purchased skills (1 kit)

Gear States:
- 0 Gear (Unequipped)
- 1 Weapon (Honed)
- 1 Armor (Reinforced)
- Both (Weapon + Armor)
"""

import sys
sys.path.insert(0, 'sim')
import itertools
from collections import defaultdict
import macro_sim as M
import leveling_validation as LV
import equipment_solver as ES
import _boss_fast_sweep as BFS

CLASSES = list(M.CARD_SOURCE.keys())

CLASS_BASES = {
    'warrior': ('2-Hander', 'Heavy Armor'),
    'paladin': ('1-Hander', 'Heavy Armor'),
    'rogue': ('1-Hander', 'Medium Armor'),
    'ranger': ('1-Hander', 'Medium Armor'),
    'runecaster': ('1-Hander', 'Medium Armor'),
    'druid': ('Staff', 'Medium Armor'),
    'wizard': ('Wand', 'Light Armor'),
    'cleric': ('Staff', 'Light Armor'),
    'necromancer': ('Wand', 'Light Armor'),
}

# 3 Boss Profiles
f1_b1, f2_b1 = BFS.make_formatter(('ranged', 'melee', 'ranged'), ('ranged', 'melee', 'ranged'))
p1_b1 = ((3, 0), (3, 2), (4, 0))
p2_b1 = ((4, 0), (4, 1), (4, 0))

f1_b2, f2_b2 = BFS.make_formatter(('melee', 'ranged', 'melee'), ('ranged', 'melee', 'ranged'))
p1_b2 = ((2, 1), (4, 0), (4, 0))
p2_b2 = ((4, 0), (4, 0), (5, 0))

f1_b3, f2_b3 = BFS.make_formatter(('ranged', 'melee', 'ranged'), ('melee', 'ranged', 'melee'))
p1_b3 = ((4, 0), (3, 2), (3, 0))
p2_b3 = ((4, 1), (4, 0), (4, 0))

BOSSES = [
    ('Boss 1 (Inquisitor)', p1_b1, 10, p2_b1, 10, f1_b1, f2_b1),
    ('Boss 2 (Colossus)', p1_b2, 11, p2_b2, 10, f1_b2, f2_b2),
    ('Boss 3 (Eclipse)', p1_b3, 10, p2_b3, 10, f1_b3, f2_b3),
]

def build_class_kits(class_name):
    mand = M.LEVEL2_MANDATORY[class_name]
    purch = M.LEVEL2_PURCHASED_ORDER[class_name]
    
    mand_swap = {mand[1]: (mand[2], mand[3])}
    
    # Tier 0: Mand only
    tier0 = [mand_swap]
    
    # Tier 1: Mand + 1
    tier1 = []
    for idx in range(3):
        p = purch[idx]
        swaps = dict(mand_swap)
        swaps[p[0]] = (p[1], p[2])
        tier1.append(swaps)
        
    # Tier 2: Mand + 2
    tier2 = []
    for combo in itertools.combinations(range(3), 2):
        swaps = dict(mand_swap)
        for idx in combo:
            p = purch[idx]
            swaps[p[0]] = (p[1], p[2])
        tier2.append(swaps)
        
    # Tier 3: Mand + 3
    swaps_all = dict(mand_swap)
    for p in purch:
        swaps_all[p[0]] = (p[1], p[2])
    tier3 = [swaps_all]
    
    return [
        ('Mandatory Only', tier0),
        ('Mand + 1 Skill', tier1),
        ('Mand + 2 Skills', tier2),
        ('Mand + 3 (All)', tier3),
    ]

def evaluate_kit_gear(mod, class_name, swaps, c1, b_hp1, c2, b_hp2, start_hp, eq_weap, eq_arm):
    """
    Evaluates all 15x15 hand pairs for a given kit across all 4 gear states.
    Correctly models Phase 1 & Phase 2 gear decisions and HP carryover.
    Returns dict: gear_state -> (wins, deaths, dmg_fails, total_runs)
    """
    gear_results = {
        '0 Gear': {'wins': 0, 'deaths': 0, 'dmg_fails': 0, 'runs': 0},
        '1 Weapon': {'wins': 0, 'deaths': 0, 'dmg_fails': 0, 'runs': 0},
        '1 Armor': {'wins': 0, 'deaths': 0, 'dmg_fails': 0, 'runs': 0},
        'Both Gear': {'wins': 0, 'deaths': 0, 'dmg_fails': 0, 'runs': 0},
    }
    eq_both = {'weapon': eq_weap['weapon'], 'armor': eq_arm['armor']}
    
    with LV.leveled_kit(mod, swaps):
        p1_cache = {}
        for h1 in mod.ALL_HANDS:
            w_raw, hp_raw, _ = BFS.B.simulate_phase(mod, class_name, h1, c1, b_hp1, start_hp)
            rw = ES.best_line_with_equipment(class_name, h1, c1, b_hp1, start_hp, eq_weap)
            ra = ES.best_line_with_equipment(class_name, h1, c1, b_hp1, start_hp, eq_arm)
            rb = ES.best_line_with_equipment(class_name, h1, c1, b_hp1, start_hp, eq_both)
            p1_cache[h1] = {
                'raw': (w_raw, hp_raw),
                'wep': (rw[0], rw[3], rw[5].get('weapon') is not None),
                'arm': (ra[0], ra[3], ra[5].get('armor') is not None),
                'both': (rb[0], rb[3], rb[5].get('weapon') is not None, rb[5].get('armor') is not None)
            }
            
        memo_eq = {}
        def get_best_eq(h, s_hp, eq):
            eq_k = tuple(sorted(eq.keys()))
            k = (h, s_hp, eq_k)
            if k not in memo_eq:
                memo_eq[k] = ES.best_line_with_equipment(class_name, h, c2, b_hp2, s_hp, eq)
            return memo_eq[k]

        memo_raw = {}
        def get_raw_phase(h, s_hp):
            k = (h, s_hp)
            if k not in memo_raw:
                memo_raw[k] = BFS.B.simulate_phase(mod, class_name, h, c2, b_hp2, s_hp)
            return memo_raw[k]

        for h1 in mod.ALL_HANDS:
            p1 = p1_cache[h1]
            for h2 in mod.ALL_HANDS:
                # --- 0 Gear ---
                st = gear_results['0 Gear']
                st['runs'] += 1
                if not p1['raw'][0]:
                    if p1['raw'][1] <= 0: st['deaths'] += 1
                    else: st['dmg_fails'] += 1
                else:
                    w2, hp2, _ = get_raw_phase(h2, p1['raw'][1])
                    if w2: st['wins'] += 1
                    elif hp2 <= 0: st['deaths'] += 1
                    else: st['dmg_fails'] += 1
                    
                # --- 1 Weapon ---
                st = gear_results['1 Weapon']
                st['runs'] += 1
                best_w = None
                if p1['raw'][0]:
                    w2, _, _, hp2, _, _ = get_best_eq(h2, p1['raw'][1], eq_weap)
                    best_w = (w2, hp2)
                if p1['wep'][0] and p1['wep'][2]:
                    w2, hp2, _ = get_raw_phase(h2, p1['wep'][1])
                    if best_w is None or (w2 and not best_w[0]) or (w2 == best_w[0] and hp2 > best_w[1]):
                        best_w = (w2, hp2)
                if best_w is None:
                    if p1['raw'][1] <= 0: st['deaths'] += 1
                    else: st['dmg_fails'] += 1
                elif best_w[0]:
                    st['wins'] += 1
                elif best_w[1] <= 0:
                    st['deaths'] += 1
                else:
                    st['dmg_fails'] += 1
                    
                # --- 1 Armor ---
                st = gear_results['1 Armor']
                st['runs'] += 1
                best_a = None
                if p1['raw'][0]:
                    w2, _, _, hp2, _, _ = get_best_eq(h2, p1['raw'][1], eq_arm)
                    best_a = (w2, hp2)
                if p1['arm'][0] and p1['arm'][2]:
                    w2, hp2, _ = get_raw_phase(h2, p1['arm'][1])
                    if best_a is None or (w2 and not best_a[0]) or (w2 == best_a[0] and hp2 > best_a[1]):
                        best_a = (w2, hp2)
                if best_a is None:
                    if p1['raw'][1] <= 0: st['deaths'] += 1
                    else: st['dmg_fails'] += 1
                elif best_a[0]:
                    st['wins'] += 1
                elif best_a[1] <= 0:
                    st['deaths'] += 1
                else:
                    st['dmg_fails'] += 1
                    
                # --- Both Gear ---
                st = gear_results['Both Gear']
                st['runs'] += 1
                best_b = None
                if p1['raw'][0]:
                    w2, _, _, hp2, _, _ = get_best_eq(h2, p1['raw'][1], eq_both)
                    best_b = (w2, hp2)
                if p1['arm'][0] and p1['arm'][2]:
                    w2, _, _, hp2, _, _ = get_best_eq(h2, p1['arm'][1], eq_weap)
                    if best_b is None or (w2 and not best_b[0]) or (w2 == best_b[0] and hp2 > best_b[1]):
                        best_b = (w2, hp2)
                if p1['wep'][0] and p1['wep'][2]:
                    w2, _, _, hp2, _, _ = get_best_eq(h2, p1['wep'][1], eq_arm)
                    if best_b is None or (w2 and not best_b[0]) or (w2 == best_b[0] and hp2 > best_b[1]):
                        best_b = (w2, hp2)
                if p1['both'][0]:
                    rem_gear = {}
                    if not p1['both'][2]: rem_gear['weapon'] = eq_weap['weapon']
                    if not p1['both'][3]: rem_gear['armor'] = eq_arm['armor']
                    if rem_gear:
                        w2, _, _, hp2, _, _ = get_best_eq(h2, p1['both'][1], rem_gear)
                    else:
                        w2, hp2, _ = get_raw_phase(h2, p1['both'][1])
                    if best_b is None or (w2 and not best_b[0]) or (w2 == best_b[0] and hp2 > best_b[1]):
                        best_b = (w2, hp2)
                if best_b is None:
                    if p1['raw'][1] <= 0: st['deaths'] += 1
                    else: st['dmg_fails'] += 1
                elif best_b[0]:
                    st['wins'] += 1
                elif best_b[1] <= 0:
                    st['deaths'] += 1
                else:
                    st['dmg_fails'] += 1

    return gear_results

if __name__ == '__main__':
    print("Running 4x4 Gear and Skill Progression Matrix across all 9 classes and all 3 bosses...")
    
    # Store: boss_idx -> class -> skill_tier -> gear_state -> (win%, death%, timeout%)
    boss_summaries = {b[0]: defaultdict(lambda: defaultdict(dict)) for b in BOSSES}
    trio_summary = defaultdict(lambda: defaultdict(dict))
    
    for c in CLASSES:
        mod = M.CARD_SOURCE[c]
        start_hp = getattr(mod, M.HP_ATTR[c])
        w_base, a_base = CLASS_BASES[c]
        eq_weap = {'weapon': {'rider': 'honed', 'base': w_base}}
        eq_arm = {'armor': {'rider': 'reinforced', 'base': a_base}}
        skill_tiers = build_class_kits(c)
        
        for tier_name, kits in skill_tiers:
            trio_agg_gear = {
                '0 Gear': {'wins': 0, 'deaths': 0, 'dmg_fails': 0, 'runs': 0},
                '1 Weapon': {'wins': 0, 'deaths': 0, 'dmg_fails': 0, 'runs': 0},
                '1 Armor': {'wins': 0, 'deaths': 0, 'dmg_fails': 0, 'runs': 0},
                'Both Gear': {'wins': 0, 'deaths': 0, 'dmg_fails': 0, 'runs': 0},
            }
            
            for b_name, p1_pat, b_hp1, p2_pat, b_hp2, fmt1, fmt2 in BOSSES:
                c1 = fmt1(p1_pat, c)
                c2 = fmt2(p2_pat, c)
                boss_agg_gear = {
                    '0 Gear': {'wins': 0, 'deaths': 0, 'dmg_fails': 0, 'runs': 0},
                    '1 Weapon': {'wins': 0, 'deaths': 0, 'dmg_fails': 0, 'runs': 0},
                    '1 Armor': {'wins': 0, 'deaths': 0, 'dmg_fails': 0, 'runs': 0},
                    'Both Gear': {'wins': 0, 'deaths': 0, 'dmg_fails': 0, 'runs': 0},
                }
                for swaps in kits:
                    res = evaluate_kit_gear(mod, c, swaps, c1, b_hp1, c2, b_hp2, start_hp, eq_weap, eq_arm)
                    for g_state, counts in res.items():
                        for k in ['wins', 'deaths', 'dmg_fails', 'runs']:
                            boss_agg_gear[g_state][k] += counts[k]
                            trio_agg_gear[g_state][k] += counts[k]
                            
                for g_state, counts in boss_agg_gear.items():
                    r = counts['runs']
                    w = counts['wins'] / r * 100
                    d = counts['deaths'] / r * 100
                    df = counts['dmg_fails'] / r * 100
                    boss_summaries[b_name][c][tier_name][g_state] = (w, d, df)
                    
            for g_state, counts in trio_agg_gear.items():
                r = counts['runs']
                w = counts['wins'] / r * 100
                d = counts['deaths'] / r * 100
                df = counts['dmg_fails'] / r * 100
                trio_summary[c][tier_name][g_state] = (w, d, df)
                
        print(f"Completed class: {c}")

    def print_matrix(title, summary_data):
        print("\n" + "=" * 95)
        print(title)
        print("=" * 95)
        
        # Calculate roster averages for this boss/summary
        roster_avg = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0]))
        for c in CLASSES:
            for tier_name, _ in build_class_kits(c):
                for g_state in ['0 Gear', '1 Weapon', '1 Armor', 'Both Gear']:
                    w, d, df = summary_data[c][tier_name][g_state]
                    roster_avg[tier_name][g_state][0] += w / len(CLASSES)
                    roster_avg[tier_name][g_state][1] += d / len(CLASSES)
                    roster_avg[tier_name][g_state][2] += df / len(CLASSES)

        for c in CLASSES:
            print(f"\n### {c.upper()} (Base HP: {getattr(M.CARD_SOURCE[c], M.HP_ATTR[c])} | Weapon: {CLASS_BASES[c][0]} | Armor: {CLASS_BASES[c][1]})")
            print(f"{'Skill Progression':18} | {'0 Gear':12} | {'+1 Weapon':12} | {'+1 Armor':12} | {'Weapon + Armor':15}")
            print("-" * 75)
            for tier_name, _ in build_class_kits(c):
                row_str = f"{tier_name:18} | "
                for g_state in ['0 Gear', '1 Weapon', '1 Armor', 'Both Gear']:
                    w, d, df = summary_data[c][tier_name][g_state]
                    row_str += f"{w:5.1f}% (D{d:2.0f}%) | "
                print(row_str)

        print("\n" + "-" * 75)
        print("### ROSTER AVERAGE")
        print(f"{'Skill Progression':18} | {'0 Gear':12} | {'+1 Weapon':12} | {'+1 Armor':12} | {'Weapon + Armor':15}")
        print("-" * 75)
        for tier_name, _ in build_class_kits('warrior'):
            row_str = f"{tier_name:18} | "
            for g_state in ['0 Gear', '1 Weapon', '1 Armor', 'Both Gear']:
                w, d, df = roster_avg[tier_name][g_state]
                row_str += f"{w:5.1f}% (D{d:2.0f}%) | "
            print(row_str)

    # Print each boss
    for b in BOSSES:
        print_matrix(f"BOSS CANDIDATE: {b[0].upper()}", boss_summaries[b[0]])
        
    # Print trio summary
    print_matrix("TRIO-BOSS AGGREGATE AVERAGE", trio_summary)
