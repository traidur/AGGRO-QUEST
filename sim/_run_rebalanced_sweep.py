import sys
sys.path.insert(0, 'sim')
import _boss_fast_sweep as BFS
import macro_sim as M

CLASSES = list(M.CARD_SOURCE.keys())

# Boss 1: High Inquisitor Malakor (Anti-Caster / Pure Ranged P1)
f1_inq, f2_inq = BFS.make_formatter(('ranged', 'ranged', 'ranged'), ('ranged', 'ranged', 'melee'))
p1_inq = ((4, 0), (3, 1), (4, 0))
p2_inq = ((4, 0), (4, 0), (5, 0))

# Boss 2: Citadel Colossus (Anti-Melee / Heavy Slams)
f1_col, f2_col = BFS.make_formatter(('melee', 'melee', 'ranged'), ('melee', 'melee', 'ranged'))
p1_col = ((3, 2), (5, 0), (4, 0))
p2_col = ((5, 0), (4, 1), (4, 0))

# Boss 3: Eclipse Sovereign (Twilight Guillotine / Anti-Attrition)
f1_ecl, f2_ecl = BFS.make_formatter(('melee', 'ranged', 'melee'), ('ranged', 'melee', 'melee'))
p1_ecl = ((4, 1), (4, 0), (5, 0))
p2_ecl = ((4, 0), (4, 1), (6, 0))

bosses = [
    ('Boss 1 (Inquisitor)', p1_inq, 10, p2_inq, 10, f1_inq, f2_inq),
    ('Boss 2 (Colossus)', p1_col, 10, p2_col, 10, f1_col, f2_col),
    ('Boss 3 (Eclipse)', p1_ecl, 10, p2_ecl, 9, f1_ecl, f2_ecl),
]

all_res = {}
for b_name, p1_pat, hp1, p2_pat, hp2, fmt1, fmt2 in bosses:
    all_res[b_name] = BFS.eval_profile_fast(p1_pat, hp1, p2_pat, hp2, fmt1, fmt2)

print('='*80)
print('REBALANCED CROSS-BOSS SPREAD MATRIX')
print('='*80)
print('%-12s | %-16s | %-16s | %-16s | %-8s' % ('Class', 'Boss 1 (Inquis)', 'Boss 2 (Colossus)', 'Boss 3 (Eclipse)', 'Spread'))
print('-'*80)
for c in CLASSES:
    w1 = all_res['Boss 1 (Inquisitor)'][c]['win_rate'] * 100
    w2 = all_res['Boss 2 (Colossus)'][c]['win_rate'] * 100
    w3 = all_res['Boss 3 (Eclipse)'][c]['win_rate'] * 100
    spread = max(w1, w2, w3) - min(w1, w2, w3)
    best = 'B1' if w1 >= max(w2, w3) else ('B2' if w2 >= w3 else 'B3')
    worst = 'B1' if w1 <= min(w2, w3) else ('B2' if w2 <= w3 else 'B3')
    print('%-12s | %5.1f%%          | %5.1f%%            | %5.1f%%           | %4.1f%% (Favors %s, Dreads %s)' % 
          (c, w1, w2, w3, spread, best, worst))

print('\n' + '='*80)
print('PALADIN & WIZARD & RANGER DEEP DIVE (WIN%, END HP, DEATH%)')
print('='*80)
for c in ['paladin', 'wizard', 'ranger', 'warrior', 'necromancer']:
    print(f'### {c.upper()}:')
    for b_name, _, _, _, _, _, _ in bosses:
        r = all_res[b_name][c]
        print("  %-20s: Win %5.1f%% | End HP %4.2f HP | Death %5.1f%% | Timeout %5.1f%%" % 
              (b_name, r['win_rate']*100, r['avg_end_hp'], r['total_death']*100, r['total_dmg_fail']*100))
