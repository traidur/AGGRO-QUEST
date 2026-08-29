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

best_mod = {
    'Warrior': {'Martial': 2, 'Magic': 0, 'Agility': 2},
    'Cleric': {'Martial': -1, 'Magic': 0, 'Agility': 0},
    'Wizard': {'Martial': 0, 'Magic': 0, 'Agility': 0},
    'Paladin': {'Martial': 0, 'Magic': 1, 'Agility': 0},
    'Rogue': {'Martial': 3, 'Magic': 0, 'Agility': 0},
    'Ranger': {'Martial': -1, 'Magic': 0, 'Agility': 0},
    'Runecaster': {'Martial': 0, 'Magic': 2, 'Agility': 0},
    'Druid': {'Martial': 0, 'Magic': 0, 'Agility': -2},
    'Necromancer': {'Martial': 3, 'Magic': 0, 'Agility': 0},
}
ARCH_MAP = {
    'Warrior': 'Martial', 'Paladin': 'Martial', 'Cleric': 'Martial',
    'Wizard': 'Magic', 'Necromancer': 'Magic', 'Runecaster': 'Magic',
    'Rogue': 'Agility', 'Ranger': 'Agility', 'Druid': 'Agility'
}
for cB in MATRIX['Warrior'].keys():
    ev = MATRIX['Warrior'][cB]
    archB = ARCH_MAP[cB]
    archA = ARCH_MAP['Warrior']
    shift = best_mod['Warrior'][archB] - best_mod[cB][archA]
    print(f"Warrior vs {cB:12} : Base {ev:+.2f}, Shift {shift:+.2f}, Net: {ev+shift:+.2f}")
