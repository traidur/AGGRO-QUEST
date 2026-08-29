import re
with open('condensed_paladin.py', 'r') as f:
    code = f.read()

def replacer(match):
    name = match.group(1)
    combat_type = 'melee' if name in ['Might of the Aegis', "Bastion's Hammer", 'Holy Fortress'] else 'ranged'
    return f'\"{name}\": dict(combat_type=\"{combat_type}\",'

code = re.sub(r'\"([^\"]+)\":\s*dict\(', replacer, code)

with open('condensed_paladin.py', 'w') as f:
    f.write(code)

from condensed_paladin import CARDS
print("PALADIN:", [(k, v['combat_type']) for k, v in CARDS.items()])
