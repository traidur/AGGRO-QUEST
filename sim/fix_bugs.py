with open('playtest_board_web.py', 'r') as f:
    content = f.read()

content = content.replace(
    'PvP.resolve_duel(i_hero.class_name, i_plan, d_hero.class_name, d_plan)',
    'PvP.resolve_duel(i_hero.class_name.title(), i_plan, d_hero.class_name.title(), d_plan)'
)

# And check why party_start returned None.
# If party_start returned None, _cmp_process_resolve_queue might be returning None!
