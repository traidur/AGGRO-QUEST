import re

with open('verify_playtest_board_web.py', 'r') as f:
    content = f.read()

patch = '''            elif phase == "cmp_pvp_initiate":
                resp = client.post("/cmp/pvp/declare_peace", data={}, follow_redirects=True)
            elif phase == "cmp_pvp_plan":
                hero_idx = PW._S["active_hero_idx"]
                hand = PW._S[f"pvp_hand_{hero_idx}"]
                import random
                plan = random.sample(hand, 3)
                data = {f"card_{i}": c for i, c in enumerate(plan)}
                resp = client.post("/cmp/pvp/plan/submit", data=data, follow_redirects=True)
            elif phase == "cmp_round_result":'''

content = content.replace('            elif phase == "cmp_round_result":', patch)

with open('verify_playtest_board_web.py', 'w') as f:
    f.write(content)
