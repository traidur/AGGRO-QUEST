import re

# 1. Fix sim_pvp.py
with open('sim_pvp.py', 'r') as f:
    content = f.read()

idx = content.find('    return total_ev / count')
if idx != -1:
    content = content[:idx + len('    return total_ev / count')]
    
content += '''

if __name__ == "__main__":
    class_names = list(CLASSES.keys())
    print('| Attacker \\\\ Defender | ' + ' | '.join(class_names) + ' |')
    print('|---' * (len(class_names) + 1) + '|')
    
    for cA in class_names:
        row = [f'**{cA}**']
        for cB in class_names:
            if cA == cB:
                row.append('0.00')
            else:
                ev = evaluate_matchup(cA, cB)
                row.append(f'{ev:+.2f}')
        print('| ' + ' | '.join(row) + ' |')
'''

with open('sim_pvp.py', 'w') as f:
    f.write(content)

# 2. Fix verify_playtest_board_web.py UnboundLocalError
with open('verify_playtest_board_web.py', 'r') as f:
    v_content = f.read()

v_content = v_content.replace('''                import random
                plan = random.sample(hand, 3)''', '''                import random as rnd
                plan = rnd.sample(hand, 3)''')

with open('verify_playtest_board_web.py', 'w') as f:
    f.write(v_content)

