import sys
sys.path.insert(0, 'sim')
import macro_sim as M
import board_engine as BE
import board_state as B
import random

# Fix 1: _remove_food
def fixed_remove_food(bag, index):
    cols = 3
    if bag[index] == 'food':
        bag[index] = None
        for offset in (1, cols, cols + 1):
            if index + offset < len(bag) and bag[index + offset] in ('food', 'food_filler'):
                bag[index + offset] = None
M._remove_food = fixed_remove_food
BE.M._remove_food = fixed_remove_food

# Fix 2: sell gathering items at Town
orig_town = BE.resolve_town_turn
def town_with_selling(hero, class_name, strategy, purchase_queue, purchase_policy, rng, board):
    raw_mats = {'Snap-Root', 'Crag-Iron', 'Scavenged Pelt', 'River-Mint', 'Sun-Copper', 'Bristle-Pelt'}
    for i, slot in enumerate(hero.bag):
        if slot and isinstance(slot, dict) and 'items' in slot:
            for item in list(slot['items'].keys()):
                if item in raw_mats:
                    count = slot['items'].pop(item)
                    hero.gold += count
            if not slot['items']:
                hero.bag[i] = None
    return orig_town(hero, class_name, strategy, purchase_queue, purchase_policy, rng, board)

BE.resolve_town_turn = town_with_selling

rng = random.Random(42)
mod = M.CARD_SOURCE['warrior']
max_hp = float(getattr(mod, M.HP_ATTR['warrior']))
hero = B.HeroBoardState(class_name='warrior', hp=max_hp, max_hp=max_hp, position=(1, 'town'),
                       bag=[None] * M.BAG_SIZE, locked=[False] * M.BAG_SIZE)
M._add_food(hero.bag, hero.locked)
board = B.BoardState(mode='solo', heroes=[hero], zones={}, level_decks={1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}, loot_decks={1: B.LootDeck.new(1, rng), 2: B.LootDeck.new(2, rng)})
board.setup_quests(rng)
purchase_queue = M._build_purchase_queue('warrior', 0)
BE.resolve_town_turn(hero, 'warrior', 'rush', purchase_queue, 'save', rng, board)

print("Starting simulation with fixes:")
for trip in range(12):
    valid_quest_zones = M.LEVEL2_QUEST_ZONES if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.LEVEL1_QUEST_ZONES
    fallback_target_zones = valid_quest_zones
    quest_pool = M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS
    res = BE.run_solo_trip(hero, 'warrior', quest_pool, fallback_target_zones, board, rng, M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)
    town = BE.resolve_town_turn(hero, 'warrior', 'rush', purchase_queue, 'save', rng, board)
    print(f"Trip {trip:2d}: turns={hero.turns:2d}, hp={hero.hp:4.1f}, xp={hero.xp:2d}, gold={hero.gold:2d}, active={hero.active_quests}, completed={town['quests_completed']}")
