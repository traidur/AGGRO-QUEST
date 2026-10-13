import sys
sys.path.insert(0, 'sim')
import macro_sim as M
import board_engine as BE
import board_state as B
import random

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
print('Initial active quests:', hero.active_quests)

for trip in range(15):
    valid_quest_zones = M.LEVEL2_QUEST_ZONES if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.LEVEL1_QUEST_ZONES
    fallback_target_zones = valid_quest_zones
    quest_pool = M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS
    res = BE.run_solo_trip(hero, 'warrior', quest_pool, fallback_target_zones, board, rng, M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)
    town = BE.resolve_town_turn(hero, 'warrior', 'rush', purchase_queue, 'save', rng, board)
    print(f'Trip {trip}: turns={hero.turns}, hp={hero.hp}, xp={hero.xp}, bag={hero.bag}, active={hero.active_quests}, completed={town["quests_completed"]}')
