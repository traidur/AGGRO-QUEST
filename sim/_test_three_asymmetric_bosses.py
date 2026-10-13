"""
Test script exploring the 3 Asymmetric & Lethal Boss archetypes:
Boss A (Inquisitor): Ranged Holy Prelate (R-M-R / R-M-R). High ranged damage. Tests armor/HP pools.
Boss B (Colossus): Heavy Melee Titan (M-M-R / M-M-R). High melee damage & melee block. Tests range evasion & magic.
Boss C (Eclipse): Hybrid Staccato Duelist (M-R-M / R-M-M). High spike turns & mixed pressure. Tests reactive kits.
"""

import sys
sys.path.insert(0, 'sim')
import _boss_fast_sweep as BFS
import macro_sim as M

CLASSES = list(M.CARD_SOURCE.keys())

# Define candidate profiles
PROFILES = [
    # ----------------------------------------------------
    # CANDIDATE A: The Inquisitor (Anti-Caster / Ranged Holy)
    # Heavy ranged magic attacks. Melee classes with shields & high HP thrive; ranged casters suffer.
    # ----------------------------------------------------
    {
        'id': 'Inquisitor_A1',
        'desc': 'Inquisitor A1: Ranged Holy Pressure (R-M-R / R-R-M)',
        't1': ('ranged', 'melee', 'ranged'),
        'p1_pat': ((4, 0), (3, 1), (4, 0)),
        'hp1': 10,
        't2': ('ranged', 'ranged', 'melee'),
        'p2_pat': ((4, 0), (4, 0), (4, 1)),
        'hp2': 10,
    },
    {
        'id': 'Inquisitor_A2',
        'desc': 'Inquisitor A2: Ranged Holy Burst (R-M-R / R-R-M, Higher ATK)',
        't1': ('ranged', 'melee', 'ranged'),
        'p1_pat': ((4, 0), (3, 2), (4, 0)),
        'hp1': 10,
        't2': ('ranged', 'ranged', 'melee'),
        'p2_pat': ((4, 0), (5, 0), (4, 0)),
        'hp2': 9,
    },
    {
        'id': 'Inquisitor_A3',
        'desc': 'Inquisitor A3: High Threat Ranged (R-M-R / R-R-M, 4-4-4 P1)',
        't1': ('ranged', 'melee', 'ranged'),
        'p1_pat': ((4, 0), (4, 0), (4, 0)),
        'hp1': 10,
        't2': ('ranged', 'ranged', 'melee'),
        'p2_pat': ((4, 0), (4, 0), (5, 0)),
        'hp2': 10,
    },
    
    # ----------------------------------------------------
    # CANDIDATE B: The Colossus (Anti-Tank / Heavy Melee)
    # Heavy melee strikes & melee blocks. Range evasion & magic pierce thrive; pure melee gets hammered.
    # ----------------------------------------------------
    {
        'id': 'Colossus_B1',
        'desc': 'Colossus B1: Melee Titan (M-M-R / M-M-R, Heavy Melee Atk)',
        't1': ('melee', 'melee', 'ranged'),
        'p1_pat': ((4, 1), (4, 0), (3, 0)),
        'hp1': 10,
        't2': ('melee', 'melee', 'ranged'),
        'p2_pat': ((5, 0), (4, 1), (4, 0)),
        'hp2': 10,
    },
    {
        'id': 'Colossus_B2',
        'desc': 'Colossus B2: Molten Core (M-M-R / M-R-M, 5 Atk P2)',
        't1': ('melee', 'melee', 'ranged'),
        'p1_pat': ((4, 2), (4, 0), (3, 0)),
        'hp1': 9,
        't2': ('melee', 'ranged', 'melee'),
        'p2_pat': ((5, 0), (4, 0), (5, 0)),
        'hp2': 9,
    },
    {
        'id': 'Colossus_B3',
        'desc': 'Colossus B3: Granite Sentinel (M-M-R / M-M-R, 3 Blk P1)',
        't1': ('melee', 'melee', 'ranged'),
        'p1_pat': ((3, 2), (4, 0), (4, 0)),
        'hp1': 10,
        't2': ('melee', 'melee', 'ranged'),
        'p2_pat': ((4, 0), (5, 0), (4, 0)),
        'hp2': 10,
    },

    # ----------------------------------------------------
    # CANDIDATE C: The Eclipse (Staccato Hybrid Duelist)
    # Alternating rhythms, sudden burst spikes, parries. Tests reactive kits (Druid, Rogue, Cleric).
    # ----------------------------------------------------
    {
        'id': 'Eclipse_C1',
        'desc': 'Eclipse C1: Dusk Parry & Spike (M-R-M / R-M-R)',
        't1': ('melee', 'ranged', 'melee'),
        'p1_pat': ((3, 1), (4, 0), (4, 0)),
        'hp1': 10,
        't2': ('ranged', 'melee', 'ranged'),
        'p2_pat': ((4, 0), (5, 0), (4, 1)),
        'hp2': 10,
    },
    {
        'id': 'Eclipse_C2',
        'desc': 'Eclipse C2: Twilight Burst (R-M-R / M-R-M, R2 Spike)',
        't1': ('ranged', 'melee', 'ranged'),
        'p1_pat': ((4, 0), (5, 0), (3, 1)),
        'hp1': 9,
        't2': ('melee', 'ranged', 'melee'),
        'p2_pat': ((4, 1), (4, 0), (5, 0)),
        'hp2': 10,
    },
    {
        'id': 'Eclipse_C3',
        'desc': 'Eclipse C3: Dual Rapier Flurry (M-M-R / R-M-M)',
        't1': ('melee', 'melee', 'ranged'),
        'p1_pat': ((3, 1), (4, 1), (4, 0)),
        'hp1': 10,
        't2': ('ranged', 'melee', 'melee'),
        'p2_pat': ((4, 0), (4, 1), (5, 0)),
        'hp2': 9,
    },
]

def run_tests():
    for p in PROFILES:
        fmt1, fmt2 = BFS.make_formatter(p['t1'], p['t2'])
        res = BFS.eval_profile_fast(p['p1_pat'], p['hp1'], p['p2_pat'], p['hp2'], fmt1, fmt2)
        
        wins = {c: res[c]['win_rate'] for c in CLASSES}
        end_hps = {c: res[c]['avg_end_hp'] for c in CLASSES if res[c]['win_rate'] > 0}
        deaths = {c: res[c]['total_death'] for c in CLASSES}
        dmg_fails = {c: res[c]['total_dmg_fail'] for c in CLASSES}
        
        avg_win = sum(wins.values()) / len(wins)
        avg_hp = sum(end_hps.values()) / len(end_hps) if end_hps else 0
        avg_death = sum(deaths.values()) / len(deaths)
        avg_df = sum(dmg_fails.values()) / len(dmg_fails)
        spread = max(wins.values()) - min(wins.values())
        
        print(f"\n=======================================================")
        print(f"PROFILE: {p['desc']}")
        print(f"Overall Avg Win: {avg_win*100:.1f}% | Avg End HP: {avg_hp:.2f} HP | Death Rate: {avg_death*100:.1f}% | Dmg Fail Rate: {avg_df*100:.1f}% | Spread: {spread*100:.1f}%")
        print("-------------------------------------------------------")
        print(f"{'Class':12} | {'Win%':7} | {'End HP':8} | {'Death%':8} | {'Timeout%':8}")
        print("-" * 55)
        for c in sorted(CLASSES, key=lambda x: wins[x], reverse=True):
            print(f"{c:12} | {wins[c]*100:5.1f}% | {res[c]['avg_end_hp']:5.2f} HP | {deaths[c]*100:6.1f}% | {dmg_fails[c]*100:6.1f}%")

if __name__ == '__main__':
    run_tests()
