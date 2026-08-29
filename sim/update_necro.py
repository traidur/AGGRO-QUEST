import re
with open('condensed_necromancer.py', 'r') as f:
    code = f.read()

def replacer(match):
    name_or_var = match.group(1)
    combat_type = 'melee' if 'Reap' in name_or_var or 'Death Blow' in name_or_var else 'ranged'
    return f'{name_or_var}: dict(combat_type=\"{combat_type}\",'

code = re.sub(r'(BONEGUARD_OFFERING):\s*dict\(', replacer, code)

with open('condensed_necromancer.py', 'w') as f:
    f.write(code)

from condensed_necromancer import CARDS
print("NECRO:", [(k, v['combat_type']) for k, v in CARDS.items()])
