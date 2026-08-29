# Raw EVs for Unlocked Execute (A vs B)
# We will just parse the baseline matrix and apply (Skirmish_A - Skirmish_B)
import numpy as np

# Copied from previous baseline + Unlocked Execute runs:
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

SKIRMISH = {
    'Rogue': 2, 'Necromancer': 2,
    'Warrior': 1, 'Runecaster': 1,
    'Paladin': 0,
    'Ranger': -1, 'Druid': -1,
    'Wizard': -2, 'Cleric': -2
}

win_loss = {k: {'W': 0, 'L': 0, 'T': 0} for k in SKIRMISH.keys()}

print("--- ACTUAL WIN RATES WITH INTEGER SKIRMISH RATINGS ---")
for cA in MATRIX.keys():
    for cB, base_ev in MATRIX[cA].items():
        # EV shifts exactly linearly in a zero-sum game when a constant is added to all payoffs
        new_ev = base_ev + (SKIRMISH[cA] - SKIRMISH[cB])
        if new_ev > 0.05:
            win_loss[cA]['W'] += 1
        elif new_ev < -0.05:
            win_loss[cA]['L'] += 1
        else:
            win_loss[cA]['T'] += 1
            
# Sort by Wins
sorted_wl = sorted(win_loss.items(), key=lambda item: item[1]['W'], reverse=True)
for c, wl in sorted_wl:
    print(f"{c:12}: {wl['W']} W - {wl['L']} L - {wl['T']} T   (Rating: {SKIRMISH[c]:+d})")
    
