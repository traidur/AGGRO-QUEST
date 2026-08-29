import re
with open('condensed_ranger.py', 'r') as f:
    code = f.read()

def replacer(match):
    name = match.group(1)
    combat_type = 'melee' if 'Beast' in name else 'ranged'
    return f'\"{name}\": dict(combat_type=\"{combat_type}\",'

code = re.sub(r'\"([^\"]+)\":\s*dict\(', replacer, code)

with open('condensed_ranger.py', 'w') as f:
    f.write(code)

from condensed_ranger import CARDS
print("RANGER:", [(k, v['combat_type']) for k, v in CARDS.items()])
