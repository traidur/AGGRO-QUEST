import re

with open('playtest_board_web.py', 'r') as f:
    content = f.read()

content = re.sub(
    r'''    def _fill_stances\(class_name\):\n        if class_name == "Warrior":\n            return \("assault", "assault", "assault"\)\n        elif class_name == "Paladin":\n            return \("holy", "holy", "holy"\)\n        return None''',
    '''    def _fill_stances(class_name):
        if class_name == "Warrior":
            return "G"
        return None''',
    content
)

with open('playtest_board_web.py', 'w') as f:
    f.write(content)
