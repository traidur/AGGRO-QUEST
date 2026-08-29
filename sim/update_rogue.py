import re
with open('condensed_rogue.py', 'r') as f:
    code = f.read()

def replacer(match):
    name = match.group(1)
    combat_type = 'ranged' if name == 'Envenom' else 'melee'
    return f'\"{name}\": dict(combat_type=\"{combat_type}\",'

code = re.sub(r'\"([^\"]+)\":\s*dict\(', replacer, code)

with open('condensed_rogue.py', 'w') as f:
    f.write(code)

from condensed_rogue import CARDS
print("ROGUE:", [(k, v['combat_type']) for k, v in CARDS.items()])
