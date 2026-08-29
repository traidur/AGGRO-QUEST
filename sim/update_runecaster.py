import re
with open('condensed_runecaster.py', 'r') as f:
    code = f.read()

def replacer(match):
    name = match.group(1)
    combat_type = 'melee' if name in ['Windstrike', 'Earth Strike Rune', 'Tidal Ward'] else 'ranged'
    return f'\"{name}\": dict(combat_type=\"{combat_type}\",'

code = re.sub(r'\"([^\"]+)\":\s*dict\(', replacer, code)

with open('condensed_runecaster.py', 'w') as f:
    f.write(code)

from condensed_runecaster import CARDS
print("RUNECASTER:", [(k, v['combat_type']) for k, v in CARDS.items()])
