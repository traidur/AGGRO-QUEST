import re
with open('condensed_wizard.py', 'r') as f:
    code = f.read()

def replacer(match):
    name = match.group(1)
    combat_type = 'melee' if name in ['Snap Freeze', 'Ice Barricade'] else 'ranged'
    return f'\"{name}\": dict(combat_type=\"{combat_type}\",'

code = re.sub(r'\"([^\"]+)\":\s*dict\(combat_type=\"[^\"]+\",', replacer, code)

with open('condensed_wizard.py', 'w') as f:
    f.write(code)

from condensed_wizard import CARDS
print("WIZARD:", [(k, v['combat_type']) for k, v in CARDS.items()])
