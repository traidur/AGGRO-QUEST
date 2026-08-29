import itertools
import numpy as np

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
best_score = 9999
best_assignment = None

def get_win_rates(assignment):
    win_loss = {k: 0 for k in classes}
    for cA in classes:
        for cB in classes:
            if cA == cB: continue
            new_ev = MATRIX[cA][cB] + (assignment[cA] - assignment[cB])
            if new_ev > 0: win_loss[cA] += 1
    return win_loss

# We know roughly: Rogue, Necro need +, Wizard, Cleric need -
# Let's just try all combinations of [-2, -1, 0, 1, 2] for the 9 classes (actually, too many: 5^9 = 1.9M).
# But we can restrict it.
possibilities = {
    'Rogue': [1, 2],
    'Necromancer': [1, 2],
    'Warrior': [0, 1],
    'Runecaster': [0, 1],
    'Paladin': [0, -1],
    'Druid': [0, -1],
    'Ranger': [0, -1],
    'Wizard': [-1, -2],
    'Cleric': [-1, -2]
}

keys, values = zip(*possibilities.items())
for prod in itertools.product(*values):
    assignment = dict(zip(keys, prod))
    wl = get_win_rates(assignment)
    
    # We want all classes to have exactly 4 wins (so difference from 4 is minimized)
    score = sum(abs(wins - 4) for wins in wl.values())
    if score < best_score:
        best_score = score
        best_assignment = assignment
        
print("BEST ASSIGNMENT:")
print(best_assignment)
wl = get_win_rates(best_assignment)
print("WIN RATES:")
for c in classes:
    print(f"{c:12}: {wl[c]} W - {8 - wl[c]} L")
