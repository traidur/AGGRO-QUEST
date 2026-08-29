import re
# Druid
with open('condensed_druid.py', 'r') as f:
    d_code = f.read()

def replacer_druid(match):
    name = match.group(1)
    combat_type = 'melee' if name in ['Shapeshift: Grizzly', 'Maul', 'Swipe', "Nature's Wildguard"] else 'ranged'
    return f'\"{name}\": dict(combat_type=\"{combat_type}\",'
d_code = re.sub(r'\"([^\"]+)\":\s*dict\(combat_type=\"[^\"]+\",', replacer_druid, d_code)

with open('condensed_druid.py', 'w') as f:
    f.write(d_code)

# Necro
with open('condensed_necromancer.py', 'r') as f:
    n_code = f.read()

def replacer_necro_str(match):
    name = match.group(1)
    combat_type = 'melee' if name in ['Reap', 'Death Blow'] else 'ranged'
    return f'\"{name}\": dict(combat_type=\"{combat_type}\",'
n_code = re.sub(r'\"([^\"]+)\":\s*dict\(combat_type=\"[^\"]+\",', replacer_necro_str, n_code)

def replacer_necro_var(match):
    name_or_var = match.group(1)
    return f'{name_or_var}: dict(combat_type=\"melee\",'
n_code = re.sub(r'(BONEGUARD_OFFERING):\s*dict\(combat_type=\"[^\"]+\",', replacer_necro_var, n_code)

with open('condensed_necromancer.py', 'w') as f:
    f.write(n_code)

from condensed_druid import CARDS as D_CARDS
from condensed_necromancer import CARDS as N_CARDS
print("DRUID:", [(k, v['combat_type']) for k, v in D_CARDS.items()])
print("NECRO:", [(k, v['combat_type']) for k, v in N_CARDS.items()])
