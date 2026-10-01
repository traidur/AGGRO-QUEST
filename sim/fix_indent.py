with open('playtest_board_web.py', 'r') as f:
    lines = f.readlines()
    
for i, line in enumerate(lines):
    if line == 'import leveling_validation as LV\n':
        if lines[i-1] == '    import macro_sim as M\n':
            lines[i] = '    import leveling_validation as LV\n'
            lines[i+1] = '    import sim_pvp as PvP\n'

with open('playtest_board_web.py', 'w') as f:
    f.writelines(lines)
