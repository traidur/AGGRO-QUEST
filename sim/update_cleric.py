import re
with open('condensed_cleric.py', 'r') as f:
    code = f.read()

def replacer(match):
    name = match.group(1)
    combat_type = 'melee' if 'Barrier' in name or 'Fortitude' in name else 'ranged'
    return f'\"{name}\": dict(combat_type=\"{combat_type}\",'

code = re.sub(r'\"([^\"]+)\":\s*dict\(', replacer, code)

with open('condensed_cleric.py', 'w') as f:
    f.write(code)

from condensed_cleric import CARDS
print([(k, v['combat_type']) for k, v in CARDS.items()])
