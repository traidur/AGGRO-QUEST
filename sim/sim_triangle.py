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
ARCH_MAP = {
    'Warrior': 'Martial', 'Paladin': 'Martial', 'Cleric': 'Martial',
    'Wizard': 'Magic', 'Necromancer': 'Magic', 'Runecaster': 'Magic',
    'Rogue': 'Agility', 'Ranger': 'Agility', 'Druid': 'Agility'
}

# Thematic triangle:
# Martial beats Agility
# Agility beats Magic
# Magic beats Martial

wl = {k: 0 for k in classes}
for cA in classes:
    for cB in classes:
        if cA == cB: continue
        aA, aB = ARCH_MAP[cA], ARCH_MAP[cB]
        ev = MATRIX[cA][cB]
        
        # Add Triangle Advantage
        if aA == 'Martial' and aB == 'Agility': ev += 2
        elif aA == 'Agility' and aB == 'Magic': ev += 2
        elif aA == 'Magic' and aB == 'Martial': ev += 2
        
        # Subtract Triangle Disadvantage
        if aA == 'Agility' and aB == 'Martial': ev -= 2
        elif aA == 'Magic' and aB == 'Agility': ev -= 2
        elif aA == 'Martial' and aB == 'Magic': ev -= 2
        
        if ev > 0: wl[cA] += 1

print("--- WIN RATES (WITH 2D THEMATIC TRIANGLE, +2 Advantage) ---")
for c in classes: print(f"{c:12}: {wl[c]} W - {8 - wl[c]} L")
