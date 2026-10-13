import sys
sys.path.insert(0, 'sim')
import random
import itertools
from collections import Counter, defaultdict
import board_engine as BE
import board_state as B
import macro_sim as M
import equipment_data as EQ
import equipment_solver as ES
import leveling_validation as LV
import _boss_fast_sweep as BFS

CLASSES = ["warrior", "wizard", "cleric", "paladin", "rogue", "ranger", "runecaster", "druid", "necromancer"]
MAT_NAMES = {'Snap-Root', 'Crag-Iron', 'Scavenged Pelt', 'River-Mint', 'Sun-Copper', 'Bristle-Pelt'}
VENDOR_VALUES = {'tarnished_silverware': 1, 'intact_pelt': 2, 'flawless_gemstone': 3}

CLASS_BASES = {
    'warrior': ('2-Hander', 'Heavy Armor'),
    'paladin': ('1-Hander', 'Heavy Armor'),
    'rogue': ('1-Hander', 'Medium Armor'),
    'ranger': ('1-Hander', 'Medium Armor'),
    'runecaster': ('1-Hander', 'Medium Armor'),
    'druid': ('Staff', 'Medium Armor'),
    'wizard': ('Wand', 'Light Armor'),
    'cleric': ('Staff', 'Light Armor'),
    'necromancer': ('Wand', 'Light Armor'),
}

# The 3 Locked Rebalanced Bosses (V2)
f1_inq, f2_inq = BFS.make_formatter(('ranged', 'ranged', 'ranged'), ('ranged', 'ranged', 'melee'))
p1_inq = ((4, 0), (3, 1), (4, 0))
p2_inq = ((4, 0), (4, 0), (5, 0))

f1_col, f2_col = BFS.make_formatter(('melee', 'melee', 'ranged'), ('melee', 'melee', 'ranged'))
p1_col = ((3, 2), (5, 0), (4, 0))
p2_col = ((5, 0), (4, 1), (4, 0))

f1_ecl, f2_ecl = BFS.make_formatter(('melee', 'ranged', 'melee'), ('ranged', 'melee', 'melee'))
p1_ecl = ((4, 1), (4, 0), (5, 0))
p2_ecl = ((4, 0), (4, 1), (6, 0))

BOSS_PROFILES = [
    ('Boss 1 (Inquisitor)', p1_inq, 10, p2_inq, 10, f1_inq, f2_inq),
    ('Boss 2 (Colossus)', p1_col, 10, p2_col, 10, f1_col, f2_col),
    ('Boss 3 (Eclipse)', p1_ecl, 10, p2_ecl, 9, f1_ecl, f2_ecl),
]

# Memoization cache for boss combat evaluations
# key: (class_name, swaps_tuple, gear_tuple, boss_idx) -> (win_rate, death_rate, dmg_fail_rate, avg_end_hp)
COMBAT_CACHE = {}

def get_kit_swaps(class_name, acquired_keys):
    mand = M.LEVEL2_MANDATORY[class_name]
    purch = M.LEVEL2_PURCHASED_ORDER[class_name]
    swaps = {}
    if 'mandatory' in acquired_keys:
        swaps[mand[1]] = (mand[2], mand[3])
    for idx, p in enumerate(purch):
        if f'skill_{idx}' in acquired_keys:
            swaps[p[0]] = (p[1], p[2])
    return swaps

def evaluate_boss_combat(class_name, swaps, equipment, boss_idx):
    swaps_tuple = tuple(sorted(swaps.keys()))
    has_weapon = 'weapon' in equipment
    has_armor = 'armor' in equipment
    gear_tuple = (has_weapon, has_armor)
    cache_key = (class_name, swaps_tuple, gear_tuple, boss_idx)
    if cache_key in COMBAT_CACHE:
        return COMBAT_CACHE[cache_key]

    b_name, p1_pat, hp1, p2_pat, hp2, fmt1, fmt2 = BOSS_PROFILES[boss_idx]
    c1 = fmt1(p1_pat, class_name)
    c2 = fmt2(p2_pat, class_name)
    mod = M.CARD_SOURCE[class_name]
    start_hp = getattr(mod, M.HP_ATTR[class_name])
    w_base, a_base = CLASS_BASES[class_name]

    eq_weap = {'weapon': {'rider': 'honed', 'base': w_base}} if has_weapon else {}
    eq_arm = {'armor': {'rider': 'reinforced', 'base': a_base}} if has_armor else {}
    eq_both = {}
    if has_weapon: eq_both['weapon'] = eq_weap['weapon']
    if has_armor: eq_both['armor'] = eq_arm['armor']

    with LV.leveled_kit(mod, swaps):
        p1_cache = {}
        for h1 in mod.ALL_HANDS:
            w_raw, hp_raw, _ = BFS.B.simulate_phase(mod, class_name, h1, c1, hp1, start_hp)
            rw = ES.best_line_with_equipment(class_name, h1, c1, hp1, start_hp, eq_weap) if has_weapon else None
            ra = ES.best_line_with_equipment(class_name, h1, c1, hp1, start_hp, eq_arm) if has_armor else None
            rb = ES.best_line_with_equipment(class_name, h1, c1, hp1, start_hp, eq_both) if (has_weapon and has_armor) else None
            p1_cache[h1] = {
                'raw': (w_raw, hp_raw),
                'wep': (rw[0], rw[3], rw[5].get('weapon') is not None) if rw else None,
                'arm': (ra[0], ra[3], ra[5].get('armor') is not None) if ra else None,
                'both': (rb[0], rb[3], rb[5].get('weapon') is not None, rb[5].get('armor') is not None) if rb else None,
            }

        memo_eq = {}
        def get_best_eq(h, s_hp, eq):
            eq_k = tuple(sorted(eq.keys()))
            k = (h, s_hp, eq_k)
            if k not in memo_eq:
                memo_eq[k] = ES.best_line_with_equipment(class_name, h, c2, hp2, s_hp, eq)
            return memo_eq[k]

        memo_raw = {}
        def get_raw_phase(h, s_hp):
            k = (h, s_hp)
            if k not in memo_raw:
                memo_raw[k] = BFS.B.simulate_phase(mod, class_name, h, c2, hp2, s_hp)
            return memo_raw[k]

        runs = 0
        wins = 0
        deaths = 0
        dmg_fails = 0
        end_hps = []

        for h1 in mod.ALL_HANDS:
            p1 = p1_cache[h1]
            for h2 in mod.ALL_HANDS:
                runs += 1
                if not has_weapon and not has_armor:
                    # 0 Gear
                    if not p1['raw'][0]:
                        if p1['raw'][1] <= 0: deaths += 1
                        else: dmg_fails += 1
                    else:
                        w2, hp_end, _ = get_raw_phase(h2, p1['raw'][1])
                        if w2:
                            wins += 1
                            end_hps.append(hp_end)
                        elif hp_end <= 0: deaths += 1
                        else: dmg_fails += 1
                elif has_weapon and not has_armor:
                    # Weapon only
                    best_w = None
                    if p1['raw'][0]:
                        w2, _, _, hp_end, _, _ = get_best_eq(h2, p1['raw'][1], eq_weap)
                        best_w = (w2, hp_end)
                    if p1['wep'][0] and p1['wep'][2]:
                        w2, hp_end, _ = get_raw_phase(h2, p1['wep'][1])
                        if best_w is None or (w2 and not best_w[0]) or (w2 == best_w[0] and hp_end > best_w[1]):
                            best_w = (w2, hp_end)
                    if best_w is None:
                        if p1['raw'][1] <= 0: deaths += 1
                        else: dmg_fails += 1
                    elif best_w[0]:
                        wins += 1
                        end_hps.append(best_w[1])
                    elif best_w[1] <= 0: deaths += 1
                    else: dmg_fails += 1
                elif not has_weapon and has_armor:
                    # Armor only
                    best_a = None
                    if p1['raw'][0]:
                        w2, _, _, hp_end, _, _ = get_best_eq(h2, p1['raw'][1], eq_arm)
                        best_a = (w2, hp_end)
                    if p1['arm'][0] and p1['arm'][2]:
                        w2, hp_end, _ = get_raw_phase(h2, p1['arm'][1])
                        if best_a is None or (w2 and not best_a[0]) or (w2 == best_a[0] and hp_end > best_a[1]):
                            best_a = (w2, hp_end)
                    if best_a is None:
                        if p1['raw'][1] <= 0: deaths += 1
                        else: dmg_fails += 1
                    elif best_a[0]:
                        wins += 1
                        end_hps.append(best_a[1])
                    elif best_a[1] <= 0: deaths += 1
                    else: dmg_fails += 1
                else:
                    # Both Gear
                    best_b = None
                    if p1['raw'][0]:
                        w2, _, _, hp_end, _, _ = get_best_eq(h2, p1['raw'][1], eq_both)
                        best_b = (w2, hp_end)
                    if p1['arm'][0] and p1['arm'][2]:
                        w2, _, _, hp_end, _, _ = get_best_eq(h2, p1['arm'][1], eq_weap)
                        if best_b is None or (w2 and not best_b[0]) or (w2 == best_b[0] and hp_end > best_b[1]):
                            best_b = (w2, hp_end)
                    if p1['wep'][0] and p1['wep'][2]:
                        w2, _, _, hp_end, _, _ = get_best_eq(h2, p1['wep'][1], eq_arm)
                        if best_b is None or (w2 and not best_b[0]) or (w2 == best_b[0] and hp_end > best_b[1]):
                            best_b = (w2, hp_end)
                    if p1['both'][0]:
                        rem_gear = {}
                        if not p1['both'][2]: rem_gear['weapon'] = eq_weap['weapon']
                        if not p1['both'][3]: rem_gear['armor'] = eq_arm['armor']
                        if rem_gear:
                            w2, _, _, hp_end, _, _ = get_best_eq(h2, p1['both'][1], rem_gear)
                        else:
                            w2, hp_end, _ = get_raw_phase(h2, p1['both'][1])
                        if best_b is None or (w2 and not best_b[0]) or (w2 == best_b[0] and hp_end > best_b[1]):
                            best_b = (w2, hp_end)
                    if best_b is None:
                        if p1['raw'][1] <= 0: deaths += 1
                        else: dmg_fails += 1
                    elif best_b[0]:
                        wins += 1
                        end_hps.append(best_b[1])
                    elif best_b[1] <= 0: deaths += 1
                    else: dmg_fails += 1

    win_rate = wins / runs
    death_rate = deaths / runs
    dmg_fail_rate = dmg_fails / runs
    avg_end_hp = (sum(end_hps) / len(end_hps)) if end_hps else 0.0
    res = (win_rate, death_rate, dmg_fail_rate, avg_end_hp)
    COMBAT_CACHE[cache_key] = res
    return res

def perform_town_prep(hero, class_name, purchase_queue):
    # Move pending loot to bag
    while hero.pending_loot and M._bag_has_room(hero.bag, hero.locked):
        M._add_item(hero.bag, hero.locked, hero.pending_loot.pop(0))

    # Crafting
    recipes = EQ.get_recipes_for_class(class_name)
    bag_counts = {}
    for slot in hero.bag:
        if isinstance(slot, dict) and 'items' in slot:
            for k, v in slot['items'].items():
                bag_counts[k] = bag_counts.get(k, 0) + v
        elif isinstance(slot, str):
            bag_counts[slot] = bag_counts.get(slot, 0) + 1

    for r in recipes:
        slot = r['slot']
        curr_eq = hero.equipment.get(slot)
        if curr_eq and curr_eq.get('grade', 0) >= r.get('grade', 0):
            continue
        can_craft, to_consume = EQ.can_craft_recipe(r, hero.gold, bag_counts)
        if can_craft:
            BE.apply_town_action(hero, {'type': 'craft_equipment', 'recipe': r, 'consume': to_consume}, purchase_queue)
            bag_counts = {}
            for s in hero.bag:
                if isinstance(s, dict) and 'items' in s:
                    for k, v in s['items'].items():
                        bag_counts[k] = bag_counts.get(k, 0) + v
                elif isinstance(s, str):
                    bag_counts[s] = bag_counts.get(s, 0) + 1

    # Vendor items & materials
    empty_slots = sum(1 for s in hero.bag if s is None)
    for i in range(len(hero.bag)):
        s = hero.bag[i]
        if isinstance(s, str) and s in VENDOR_VALUES:
            hero.gold += VENDOR_VALUES[s]
            hero.bag[i] = None
        elif empty_slots < 3:
            if isinstance(s, dict) and 'items' in s:
                for k in list(s['items'].keys()):
                    if k in MAT_NAMES:
                        hero.gold += s['items'][k]
                        del s['items'][k]
                if not s['items']:
                    hero.bag[i] = None
                    empty_slots += 1
            elif isinstance(s, str) and s in MAT_NAMES:
                hero.gold += 1
                hero.bag[i] = None
                empty_slots += 1

def run_campaign_to_boss(class_name, mode, rng):
    """
    mode: 'speedrunner' (pivot to boss at 14 XP) or 'completionist' (finish L2 active quests first)
    """
    mod = M.CARD_SOURCE[class_name]
    max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
    hero = B.HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(1, 'town'),
                            bag=[None] * M.BAG_SIZE, locked=[False] * M.BAG_SIZE)
    M._add_food(hero.bag, hero.locked)
    if class_name in M.LEVEL2_PURCHASED_ORDER:
        hero.skill_purchase_order = list(range(len(M.LEVEL2_PURCHASED_ORDER[class_name])))
        rng.shuffle(hero.skill_purchase_order)
    purchase_queue = M._build_purchase_queue(class_name, 0)
    level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
    loot_decks = {1: B.LootDeck.new(1, rng), 2: B.LootDeck.new(2, rng)}
    board = B.BoardState(mode='solo', heroes=[hero], zones={}, level_decks=level_decks, loot_decks=loot_decks)
    board.setup_quests(rng)

    BE.resolve_town_turn(hero, class_name, 'food_only', purchase_queue, 'save', rng, board)

    trips = 0
    deaths = 0

    # Phase A: Progress to 14 XP
    while hero.xp < 14 and hero.turns < 90:
        trips += 1
        pending_mandatory = (class_name in M.LEVEL2_MANDATORY and hero.xp >= M.LEVEL2_XP_THRESHOLD
                              and 'mandatory' not in hero.acquired)
        valid_quest_zones = M.LEVEL2_QUEST_ZONES if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.LEVEL1_QUEST_ZONES
        fallback_target_zones = M.TRAINER_ZONES if pending_mandatory else valid_quest_zones
        quest_pool = M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS

        trip_result = BE.run_solo_trip(hero, class_name, quest_pool, fallback_target_zones, board, rng,
                                       M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)

        if trip_result['recovered']:
            BE.apply_recovery_post_processing(hero)
        if not trip_result['alive']:
            deaths += 1
            BE.apply_death_post_processing(hero, quest_pool, trip_result['death_node'])

        BE.resolve_town_turn(hero, class_name, 'food_only', purchase_queue, 'save', rng, board)
        perform_town_prep(hero, class_name, purchase_queue)

    # Phase B: Completionist extra trips (finish remaining active quests)
    if mode == 'completionist':
        # Engine natively stops refilling Level 2 quests once hero.xp >= 14
        while hero.active_quests and hero.turns < 80:
            trips += 1
            quest_pool = M.LEVEL2_QUESTS
            trip_result = BE.run_solo_trip(hero, class_name, quest_pool, M.LEVEL2_QUEST_ZONES, board, rng,
                                           M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)
            if trip_result['recovered']:
                BE.apply_recovery_post_processing(hero)
            if not trip_result['alive']:
                deaths += 1
                BE.apply_death_post_processing(hero, quest_pool, trip_result['death_node'])

            BE.resolve_town_turn(hero, class_name, 'food_only', purchase_queue, 'save', rng, board)
            perform_town_prep(hero, class_name, purchase_queue)

    # Final visit to Trainer (Zone 4) if hero has money for more skills
    if hero.gold >= 8:
        hero.position = (4, 'trainer')
        BE.resolve_town_turn(hero, class_name, 'food_only', purchase_queue, 'save', rng, board)
        perform_town_prep(hero, class_name, purchase_queue)

    swaps = get_kit_swaps(class_name, hero.acquired)
    num_purchased = sum(1 for k in hero.acquired if k.startswith('skill_'))
    has_mand = 'mandatory' in hero.acquired

    # Active equipment: broken gear grants no combat benefit
    active_equipment = {k: v for k, v in hero.equipment.items() if k not in hero.equipment_broken}

    return {
        'class': class_name,
        'mode': mode,
        'turns': hero.turns,
        'trips': trips,
        'gold': hero.gold,
        'xp': hero.xp,
        'deaths': deaths,
        'skills': num_purchased + (1 if has_mand else 0),
        'has_weapon': 'weapon' in active_equipment,
        'has_armor': 'armor' in active_equipment,
        'swaps': swaps,
        'equipment': active_equipment,
        'all_equipment': hero.equipment,
        'broken_count': len(hero.equipment_broken),
        'repair_gold_spent': getattr(hero, 'repair_gold_spent', 0),
    }

def run_suite(seeds_per_class=30):
    print("=" * 80, flush=True)
    print("END-TO-END MACRO CAMPAIGN SIMULATION (LEVEL 1 -> LEVEL 2 -> BOSS GATE)", flush=True)
    print(f"Sampling {seeds_per_class} runs per class ({seeds_per_class * len(CLASSES)} campaigns per strategy)", flush=True)
    print("Comparing: Speedrunner (Immediate 14 XP Boss) vs Completionist (Clear L2 Quests)", flush=True)
    print("Boss Modes: Blind Draw (1 of 3) vs Scout Token (Draw 2, Choose Best)", flush=True)
    print("=" * 80, flush=True)

    for mode in ['speedrunner', 'completionist']:
        print(f"\n>>>>>>>>>>>> STRATEGY: {mode.upper()} <<<<<<<<<<<<", flush=True)
        all_turns = []
        all_gold = []
        all_repairs = []
        all_broken = []
        all_skills = Counter()
        all_gear = Counter()

        blind_wins = []
        scout_wins = []
        blind_deaths = []
        scout_deaths = []

        class_metrics = {}

        for c in CLASSES:
            print(f"  Simulating {c:12s} ({seeds_per_class} runs)... ", end="", flush=True)
            c_turns = []
            c_gold = []
            c_repairs = []
            c_broken = []
            c_skills = Counter()
            c_gear = Counter()
            c_blind_wins = []
            c_scout_wins = []
            c_blind_deaths = []
            c_scout_deaths = []

            for s in range(seeds_per_class):
                rng = random.Random(s * 1000 + 42)
                res = run_campaign_to_boss(c, mode, rng)

                c_turns.append(res['turns'])
                c_gold.append(res['gold'])
                c_repairs.append(res['repair_gold_spent'])
                c_broken.append(res['broken_count'])
                c_skills[res['skills']] += 1

                if res['has_weapon'] and res['has_armor']:
                    g_lbl = 'both'
                elif res['has_weapon']:
                    g_lbl = 'weapon_only'
                elif res['has_armor']:
                    g_lbl = 'armor_only'
                else:
                    g_lbl = 'none'
                c_gear[g_lbl] += 1

                # Boss Combat Evaluations:
                # 1. Blind Draw: Draw 1 random boss from 0, 1, 2
                draw_rng = random.Random(s * 777 + 13)
                blind_b_idx = draw_rng.randint(0, 2)
                b_win, b_death, b_to, b_hp = evaluate_boss_combat(c, res['swaps'], res['equipment'], blind_b_idx)
                c_blind_wins.append(b_win)
                c_blind_deaths.append(b_death)

                # 2. Scout Token: Draw 2 distinct bosses, pick the one with higher win rate
                scout_pool = draw_rng.sample([0, 1, 2], 2)
                cand0 = evaluate_boss_combat(c, res['swaps'], res['equipment'], scout_pool[0])
                cand1 = evaluate_boss_combat(c, res['swaps'], res['equipment'], scout_pool[1])
                best_cand = cand0 if cand0[0] >= cand1[0] else cand1
                c_scout_wins.append(best_cand[0])
                c_scout_deaths.append(best_cand[1])

            all_turns.extend(c_turns)
            all_gold.extend(c_gold)
            all_repairs.extend(c_repairs)
            all_broken.extend(c_broken)
            for k, v in c_skills.items(): all_skills[k] += v
            for k, v in c_gear.items(): all_gear[k] += v
            blind_wins.extend(c_blind_wins)
            scout_wins.extend(c_scout_wins)
            blind_deaths.extend(c_blind_deaths)
            scout_deaths.extend(c_scout_deaths)

            class_metrics[c] = {
                'turns': sum(c_turns) / len(c_turns),
                'gold': sum(c_gold) / len(c_gold),
                'repairs': sum(c_repairs) / len(c_repairs),
                'broken_pct': (sum(1 for b in c_broken if b > 0) / len(c_broken)) * 100,
                'skills': dict(c_skills),
                'gear': dict(c_gear),
                'blind_win': sum(c_blind_wins) / len(c_blind_wins) * 100,
                'scout_win': sum(c_scout_wins) / len(c_scout_wins) * 100,
                'blind_death': sum(c_blind_deaths) / len(c_blind_deaths) * 100,
                'scout_death': sum(c_scout_deaths) / len(c_scout_deaths) * 100,
            }
            print(f"done. (Blind: {class_metrics[c]['blind_win']:.1f}%, Scout: {class_metrics[c]['scout_win']:.1f}%)", flush=True)

        total_campaigns = len(CLASSES) * seeds_per_class
        avg_turns = sum(all_turns) / len(all_turns)
        avg_gold = sum(all_gold) / len(all_gold)
        avg_repairs = sum(all_repairs) / len(all_repairs)
        tot_broken_pct = (sum(1 for b in all_broken if b > 0) / len(all_broken)) * 100
        tot_blind_win = sum(blind_wins) / len(blind_wins) * 100
        tot_scout_win = sum(scout_wins) / len(scout_wins) * 100
        tot_blind_death = sum(blind_deaths) / len(blind_deaths) * 100
        tot_scout_death = sum(scout_deaths) / len(scout_deaths) * 100

        print(f"\n--- ROSTER AGGREGATE SUMMARY ({total_campaigns} runs) ---")
        print(f"• Campaign Duration: {avg_turns:.1f} avg turns to reach Boss Gate")
        print(f"• Gold in Purse at Gate: {avg_gold:.1f}g (Avg Forge Repairs Paid: {avg_repairs:.2f}g)")
        print(f"• Broken Equipment at Gate: {tot_broken_pct:.1f}% campaigns arrived with broken gear")
        print(f"• Skill Upgrades: " + ", ".join(f"T{k}: {v/total_campaigns*100:.1f}%" for k, v in sorted(all_skills.items())))
        print(f"• Gear Loadouts: " + ", ".join(f"{k}: {v/total_campaigns*100:.1f}%" for k, v in sorted(all_gear.items())))
        print(f"• BLIND BOSS DRAW:  Win Rate = {tot_blind_win:5.1f}% | Hero Death Rate = {tot_blind_death:5.1f}%")
        print(f"• SCOUT TOKEN DRAW: Win Rate = {tot_scout_win:5.1f}% | Hero Death Rate = {tot_scout_death:5.1f}%")
        print(f"• Scout Token Uplift: +{tot_scout_win - tot_blind_win:.1f}% Win Rate | -{tot_blind_death - tot_scout_death:.1f}% Deaths")

        print(f"\n--- PER-CLASS BREAKDOWN ---")
        print(f"%-12s | %-10s | %-6s | %-8s | %-8s | %-15s | %-10s | %-10s | %-6s" % 
              ('Class', 'Avg Turns', 'Gold', 'Repairs', 'Broken%', 'Dominant Gear', 'Blind Win%', 'Scout Win%', 'Uplift'))
        print("-" * 105)
        for c in CLASSES:
            m = class_metrics[c]
            dom_gear = max(m['gear'].items(), key=lambda x: x[1])[0]
            uplift = m['scout_win'] - m['blind_win']
            print("%-12s | %4.1f turns | %4.1fg | %4.2fg   | %5.1f%%  | %-15s | %5.1f%%    | %5.1f%%    | +%4.1f%%" %
                  (c, m['turns'], m['gold'], m['repairs'], m['broken_pct'], dom_gear, m['blind_win'], m['scout_win'], uplift))

if __name__ == '__main__':
    run_suite(seeds_per_class=20)

