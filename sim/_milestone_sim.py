import sys
sys.path.insert(0, 'sim')
import random
from collections import Counter, defaultdict
import board_engine as BE
import board_state as B
import macro_sim as M
import equipment_data as EQ

CLASSES = ["warrior", "wizard", "cleric", "paladin", "rogue", "ranger", "runecaster", "druid", "necromancer"]
MAT_NAMES = {'Snap-Root', 'Crag-Iron', 'Scavenged Pelt', 'River-Mint', 'Sun-Copper', 'Bristle-Pelt'}
VENDOR_VALUES = {'tarnished_silverware': 1, 'intact_pelt': 2, 'flawless_gemstone': 3}

def simulate_hero_to_xp(class_name, target_xp, rng):
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

    while hero.xp < target_xp and hero.turns < 90:
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
            BE.apply_death_post_processing(hero, quest_pool, trip_result['death_node'])

        town_result = BE.resolve_town_turn(hero, class_name, 'food_only', purchase_queue, 'save', rng, board)

        # Move pending loot to bag
        while hero.pending_loot and M._bag_has_room(hero.bag, hero.locked):
            M._add_item(hero.bag, hero.locked, hero.pending_loot.pop(0))

        # Check crafting in Town
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

        # Vendor excess loot & excess materials if bag is crowded (< 3 empty slots)
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

    num_purchased_skills = sum(1 for k in hero.acquired if k.startswith('skill_'))
    has_mand = 'mandatory' in hero.acquired
    total_upgrades = num_purchased_skills + (1 if has_mand else 0)

    return {
        'class': class_name,
        'xp': hero.xp,
        'turns': hero.turns,
        'trips': trips,
        'gold': hero.gold,
        'total_upgrades': total_upgrades,
        'has_weapon': 'weapon' in hero.equipment,
        'has_armor': 'armor' in hero.equipment,
        'weapon_name': hero.equipment.get('weapon', {}).get('name'),
        'armor_name': hero.equipment.get('armor', {}).get('name'),
        'bag_upgrade': 'bag_upgrade' in hero.acquired
    }

def run_suite(seeds_per_class=50):
    for xp_target in [12, 14, 16]:
        print(f"\n========================================================")
        print(f"       SIMULATION: TARGET XP = {xp_target} (BOSS GATE MILESTONE)")
        print(f"========================================================")

        all_turns = []
        all_trips = []
        all_gold = []
        all_upgrades = Counter()
        all_gear = Counter()
        class_stats = {}

        for c in CLASSES:
            c_turns = []
            c_trips = []
            c_gold = []
            c_upgrades = Counter()
            c_gear = Counter()

            for s in range(seeds_per_class):
                rng = random.Random(s * 100 + 42)
                res = simulate_hero_to_xp(c, xp_target, rng)
                c_turns.append(res['turns'])
                c_trips.append(res['trips'])
                c_gold.append(res['gold'])
                c_upgrades[res['total_upgrades']] += 1

                if res['has_weapon'] and res['has_armor']:
                    gear_label = "both"
                elif res['has_weapon']:
                    gear_label = "weapon_only"
                elif res['has_armor']:
                    gear_label = "armor_only"
                else:
                    gear_label = "none"
                c_gear[gear_label] += 1

            all_turns.extend(c_turns)
            all_trips.extend(c_trips)
            all_gold.extend(c_gold)
            for k, v in c_upgrades.items():
                all_upgrades[k] += v
            for k, v in c_gear.items():
                all_gear[k] += v

            class_stats[c] = {
                'avg_turns': sum(c_turns) / len(c_turns),
                'avg_gold': sum(c_gold) / len(c_gold),
                'upgrades': dict(c_upgrades),
                'gear': dict(c_gear)
            }

        total_runs = len(CLASSES) * seeds_per_class
        avg_turns = sum(all_turns) / len(all_turns)
        avg_trips = sum(all_trips) / len(all_trips)
        avg_gold = sum(all_gold) / len(all_gold)

        print(f"\n[ROSTER AGGREGATE across {total_runs} runs]")
        print(f"• Pacing: {avg_turns:.1f} avg turns (range {min(all_turns)}-{max(all_turns)}), {avg_trips:.1f} avg trips")
        print(f"• Gold in purse: {avg_gold:.1f} gold")
        print(f"\n• Total Upgrades (1 Mandatory + 0-3 Purchased):")
        for upg in sorted(all_upgrades.keys()):
            pct = all_upgrades[upg] / total_runs * 100
            label = "Mandatory only" if upg == 1 else f"Mand + {upg-1} skills"
            print(f"    Tier {upg} ({label:18s}): {pct:5.1f}%")

        print(f"\n• Equipment Loadout Distribution:")
        for g in ["none", "weapon_only", "armor_only", "both"]:
            pct = all_gear[g] / total_runs * 100
            print(f"    {g:12s}: {pct:5.1f}%")

        print(f"\n• Per-Class Summary (Avg Turns | Avg Gold | Dominant Upgrades | Dominant Gear):")
        for c in CLASSES:
            st = class_stats[c]
            upg_str = ", ".join(f"T{k}:{v}" for k, v in sorted(st['upgrades'].items()))
            gear_str = ", ".join(f"{k}:{v}" for k, v in st['gear'].items())
            print(f"  {c:12s} | {st['avg_turns']:4.1f} turns | {st['avg_gold']:4.1f}g | {upg_str:16s} | {gear_str}")

if __name__ == '__main__':
    run_suite(seeds_per_class=50)
