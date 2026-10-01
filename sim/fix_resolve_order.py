import re

with open('playtest_board_web.py', 'r') as f:
    content = f.read()

content = content.replace(
    '_S["cmp_resolve_order"] = list(_S["cmp_field_idxs"])',
    '_S["cmp_resolve_order"] = [h for h in _S["cmp_field_idxs"] if h in _S["cmp_declarations_resolved"]]'
)

with open('playtest_board_web.py', 'w') as f:
    f.write(content)
