import re

with open('playtest_board_web.py', 'r') as f:
    content = f.read()

content = re.sub(
    r'PvP\.resolve_duel\(i_hero\.class_name, i_plan, d_hero\.class_name, d_plan\)',
    'PvP.resolve_duel(i_hero.class_name.title(), i_plan, d_hero.class_name.title(), d_plan)',
    content
)

with open('playtest_board_web.py', 'w') as f:
    f.write(content)
