import re

with open('playtest_board_web.py', 'r') as f:
    content = f.read()
    
func_str = '''
    def _fill_stances(class_name, plan):
        if class_name == "Warrior":
            return [("assault", "assault", "assault")]
        elif class_name == "Paladin":
            return [("holy", "holy", "holy")]
        return None

    i_dmg, d_dmg = PvP.resolve_duel(i_hero.class_name.title(), (i_plan, _fill_stances(i_hero.class_name.title(), i_plan)), d_hero.class_name.title(), (d_plan, _fill_stances(d_hero.class_name.title(), d_plan)))
'''

content = content.replace(
    'i_dmg, d_dmg = PvP.resolve_duel(i_hero.class_name.title(), (i_plan, None), d_hero.class_name.title(), (d_plan, None))',
    '''
    def _fill_stances(class_name):
        if class_name == "Warrior":
            return ("assault", "assault", "assault")
        elif class_name == "Paladin":
            return ("holy", "holy", "holy")
        return None
        
    i_dmg, d_dmg = PvP.resolve_duel(i_hero.class_name.title(), (i_plan, _fill_stances(i_hero.class_name.title())), d_hero.class_name.title(), (d_plan, _fill_stances(d_hero.class_name.title())))
'''
)

with open('playtest_board_web.py', 'w') as f:
    f.write(content)
