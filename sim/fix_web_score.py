with open('playtest_board_web.py', 'r') as f:
    content = f.read()
    
content = content.replace(
    'i_score = i_dmg + i_hero.tokens\n    d_score = d_dmg + d_hero.tokens',
    'i_score = i_dmg + i_hero.max_hp + i_hero.tokens\n    d_score = d_dmg + d_hero.max_hp + d_hero.tokens'
)

with open('playtest_board_web.py', 'w') as f:
    f.write(content)
