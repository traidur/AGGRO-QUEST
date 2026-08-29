import numpy as np
import random
MATRIX = {
    'Warrior': {'Cleric': -1.86, 'Wizard': -2.70, 'Paladin': -1.26, 'Rogue': 0.21, 'Ranger': -2.37, 'Runecaster': -1.23, 'Druid': -1.35, 'Necromancer': -1.23},
    'Cleric': {'Warrior': 1.86, 'Wizard': 0.79, 'Paladin': 0.51, 'Rogue': 2.46, 'Ranger': 1.13, 'Runecaster': 2.36, 'Druid': 0.27, 'Necromancer': 2.77},
    'Wizard': {'Warrior': 2.70, 'Cleric': -0.79, 'Paladin': 0.72, 'Rogue': 2.33, 'Ranger': 1.04, 'Runecaster': 1.98, 'Druid': -0.44, 'Necromancer': 2.45},
    'Paladin': {'Warrior': 1.26, 'Cleric': -0.51, 'Wizard': -0.72, 'Rogue': 1.69, 'Ranger': -0.59, 'Runecaster': 0.94, 'Druid': -0.37, 'Necromancer': 1.02},
    'Rogue': {'Warrior': -0.21, 'Cleric': -2.46, 'Wizard': -2.33, 'Paladin': -1.69, 'Ranger': -2.64, 'Runecaster': -1.37, 'Druid': -1.92, 'Necromancer': -1.47},
    'Ranger': {'Warrior': 2.37, 'Cleric': -1.13, 'Wizard': -1.04, 'Paladin': 0.59, 'Rogue': 2.64, 'Runecaster': 1.10, 'Druid': -0.94, 'Necromancer': 2.02},
    'Runecaster': {'Warrior': 1.23, 'Cleric': -2.36, 'Wizard': -1.98, 'Paladin': -0.94, 'Rogue': 1.37, 'Ranger': -1.10, 'Druid': -1.97, 'Necromancer': 0.76},
    'Druid': {'Warrior': 1.35, 'Cleric': -0.27, 'Wizard': 0.44, 'Paladin': 0.37, 'Rogue': 1.92, 'Ranger': 0.94, 'Runecaster': 1.97, 'Necromancer': 2.69},
    'Necromancer': {'Warrior': 1.23, 'Cleric': -2.77, 'Wizard': -2.45, 'Paladin': -1.02, 'Rogue': 1.47, 'Ranger': -2.02, 'Runecaster': -0.76, 'Druid': -2.69},
}
classes = list(MATRIX.keys())
ARCH_MAP = {
    'Warrior': 'Martial', 'Paladin': 'Martial', 'Cleric': 'Martial',
    'Wizard': 'Magic', 'Necromancer': 'Magic', 'Runecaster': 'Magic',
    'Rogue': 'Agility', 'Ranger': 'Agility', 'Druid': 'Agility'
}
archetypes = ['Martial', 'Magic', 'Agility']
def eval_assignment(mod_matrix):
    wl = {k: 0 for k in classes}
    for cA in classes:
        for cB in classes:
            if cA == cB: continue
            archB = ARCH_MAP[cB]
            archA = ARCH_MAP[cA]
            shift = mod_matrix[cA][archB] - mod_matrix[cB][archA]
            new_ev = MATRIX[cA][cB] + shift
            if new_ev > 0: wl[cA] += 1
            
    balance_score = sum(abs(wl[c] - 4) for c in classes) * 1000
    mag_score = sum(abs(mod_matrix[c][a]) for c in classes for a in archetypes)
    return balance_score + mag_score

best_score = 999999
best_mod = None
for _ in range(300):
    current = {c: {a: random.choice([-3, -2, -1, 0, 1, 2, 3]) for a in archetypes} for c in classes}
    curr_score = eval_assignment(current)
    improved = True
    while improved:
        improved = False
        for c in classes:
            for a in archetypes:
                for step in [-1, 1]:
                    neighbor = {c2: {a2: current[c2][a2] for a2 in archetypes} for c2 in classes}
                    neighbor[c][a] += step
                    if neighbor[c][a] < -3 or neighbor[c][a] > 3: continue
                    n_score = eval_assignment(neighbor)
                    if n_score < curr_score:
                        curr_score = n_score
                        current = neighbor
                        improved = True
    if curr_score < best_score:
        best_score = curr_score
        best_mod = current
        
print("BEST SCORE:", best_score)
for c in classes:
    print(f"**{c}**")
    print(f"* vs Martial: {best_mod[c]['Martial']:+d}")
    print(f"* vs Magic  : {best_mod[c]['Magic']:+d}")
    print(f"* vs Agility: {best_mod[c]['Agility']:+d}")
