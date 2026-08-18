import sys
import os
import json
import importlib.util

sim_path = os.path.join(os.path.dirname(__file__), '..', 'sim')
sys.path.append(sim_path)

classes = ['cleric', 'paladin', 'ranger', 'rogue', 'warrior', 'wizard']
all_cards = {}

for cls in classes:
    mod_name = f'condensed_{cls}'
    try:
        mod_file = os.path.join(sim_path, f'{mod_name}.py')
        spec = importlib.util.spec_from_file_location(mod_name, mod_file)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        all_cards[cls] = mod.CARDS
    except Exception as e:
        print(f"Error loading {cls}: {e}")

output_path = os.path.join(os.path.dirname(__file__), 'src', 'cards.json')
with open(output_path, 'w') as f:
    json.dump(all_cards, f, indent=2)

print(f"Exported cards for {list(all_cards.keys())} classes to {output_path}")
