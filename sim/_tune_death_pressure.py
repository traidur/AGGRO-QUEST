"""
Targeted tuning to achieve:
1. Ending HP between 1.5 and 2.8 HP
2. Death rate between 15% and 25% (real threat!)
3. Clear 3-way distance:
   - Boss A (Inquisitor - Anti-Caster): Favors Tanks/Melee, punishing squishies.
   - Boss B (Colossus - Anti-Tank): Favors Ranged/Casters, punishing melee/tanks.
   - Boss C (Eclipse - Anti-Attrition): Favors Sustained Hybrids/Burst, punishing rigid kits.
"""

import sys
sys.path.insert(0, 'sim')
import _boss_fast_sweep as BFS
import macro_sim as M

CLASSES = list(M.CARD_SOURCE.keys())

# We will test variations of higher ATK and calibrated HP (9 HP / 9 HP or 10 HP / 9 HP)
CANDIDATES = [
    # ------------------------------------------------------------------
    # BOSS A: The Inquisitor (Anti-Caster Ranged Magic)
    # R-M-R / R-R-M. High ranged damage.
    # ------------------------------------------------------------------
    {
        'name': 'Inquisitor High Lethality V1',
        't1': ('ranged', 'melee', 'ranged'),
        'p1': ((4, 0), (4, 1), (4, 0)), 'hp1': 9,
        't2': ('ranged', 'ranged', 'melee'),
        'p2': ((4, 0), (5, 0), (5, 0)), 'hp2': 9,
    },
    {
        'name': 'Inquisitor High Lethality V2',
        't1': ('ranged', 'melee', 'ranged'),
        'p1': ((4, 0), (3, 1), (4, 0)), 'hp1': 9,
        't2': ('ranged', 'ranged', 'melee'),
        'p2': ((5, 0), (5, 0), (4, 0)), 'hp2': 9,
    },
    {
        'name': 'Inquisitor High Lethality V3',
        't1': ('ranged', 'melee', 'ranged'),
        'p1': ((4, 0), (4, 0), (4, 0)), 'hp1': 9,
        't2': ('ranged', 'ranged', 'melee'),
        'p2': ((4, 0), (5, 0), (4, 1)), 'hp2': 9,
    },

    # ------------------------------------------------------------------
    # BOSS B: The Colossus (Anti-Melee / Armor Titan)
    # M-M-R / M-M-R. Heavy melee slams & melee block.
    # ------------------------------------------------------------------
    {
        'name': 'Colossus High Lethality V1',
        't1': ('melee', 'melee', 'ranged'),
        'p1': ((4, 2), (5, 0), (3, 0)), 'hp1': 9,
        't2': ('melee', 'melee', 'ranged'),
        'p2': ((5, 0), (5, 0), (4, 0)), 'hp2': 9,
    },
    {
        'name': 'Colossus High Lethality V2',
        't1': ('melee', 'melee', 'ranged'),
        'p1': ((3, 2), (5, 0), (4, 0)), 'hp1': 9,
        't2': ('melee', 'melee', 'ranged'),
        'p2': ((5, 0), (4, 1), (5, 0)), 'hp2': 9,
    },
    {
        'name': 'Colossus High Lethality V3',
        't1': ('melee', 'melee', 'ranged'),
        'p1': ((4, 2), (4, 0), (4, 0)), 'hp1': 9,
        't2': ('melee', 'melee', 'ranged'),
        'p2': ((5, 0), (5, 0), (4, 1)), 'hp2': 9,
    },

    # ------------------------------------------------------------------
    # BOSS C: The Eclipse (Hybrid Staccato Duelist)
    # M-R-M / R-M-R. Sudden burst spikes & parries.
    # ------------------------------------------------------------------
    {
        'name': 'Eclipse High Lethality V1',
        't1': ('melee', 'ranged', 'melee'),
        'p1': ((3, 1), (5, 0), (4, 0)), 'hp1': 9,
        't2': ('ranged', 'melee', 'ranged'),
        'p2': ((5, 0), (4, 1), (5, 0)), 'hp2': 9,
    },
    {
        'name': 'Eclipse High Lethality V2',
        't1': ('melee', 'ranged', 'melee'),
        'p1': ((4, 1), (4, 0), (4, 0)), 'hp1': 9,
        't2': ('ranged', 'melee', 'ranged'),
        'p2': ((4, 0), (6, 0), (4, 1)), 'hp2': 9,
    },
    {
        'name': 'Eclipse High Lethality V3',
        't1': ('melee', 'ranged', 'melee'),
        'p1': ((4, 1), (5, 0), (3, 0)), 'hp1': 9,
        't2': ('ranged', 'melee', 'ranged'),
        'p2': ((5, 0), (5, 0), (4, 0)), 'hp2': 9,
    },
]

for cand in CANDIDATES:
    fmt1, fmt2 = BFS.make_formatter(cand['t1'], cand['t2'])
    res = BFS.eval_profile_fast(cand['p1'], cand['hp1'], cand['p2'], cand['hp2'], fmt1, fmt2)
    
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
    print(f"{cand['name']}")
    print(f"Overall Avg Win: {avg_win*100:.1f}% | Avg End HP: {avg_hp:.2f} HP | Death: {avg_death*100:.1f}% | Timeout: {avg_df*100:.1f}% | Spread: {spread*100:.1f}%")
    print("-" * 65)
    for c in sorted(CLASSES, key=lambda x: wins[x], reverse=True):
        print(f"  {c:12} | Win: {wins[c]*100:5.1f}% | End HP: {res[c]['avg_end_hp']:4.2f} HP | Death: {deaths[c]*100:5.1f}% | Timeout: {dmg_fails[c]*100:5.1f}%")
