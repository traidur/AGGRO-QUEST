import sys
sys.path.insert(0, 'sim')
import random
import board_engine as BE
import board_state as B
import macro_sim as M

rng = random.Random(42)
mod = M.CARD_SOURCE['warrior']
max_hp = float(getattr(mod, M.HP_ATTR['warrior']))
hero = B.HeroBoardState(class_name='warrior', hp=max_hp, max_hp=max_hp, position=(4, 'town'),
                        bag=[None] * M.BAG_SIZE, locked=[False] * M.BAG_SIZE)
M._add_food(hero.bag, hero.locked)
level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
loot_decks = {1: B.LootDeck.new(1, rng), 2: B.LootDeck.new(2, rng)}
board = B.BoardState(mode='solo', heroes=[hero], zones={}, level_decks=level_decks, loot_decks=loot_decks)
board.town_markets = {3: [], 4: []}

hero.active_quests = ['Gilded Penance']
quest_pool = {'Gilded Penance': M.LEVEL2_QUESTS['Gilded Penance']}

print('Initial state: position=', hero.position, 'bag=', hero.bag, 'turns=', hero.turns)

for step in range(20):
    count = M._accessible_count(hero.bag, hero.locked, 'Gilded Penance')
    print(f"\n--- STEP {step} (turns={hero.turns}, hp={hero.hp}, tokens={count}/5) ---")
    action = BE.decide_travel(hero, 'warrior', quest_pool, {4}, M.RISK_TOLERANCE_BASE, True)
    print(f"decide_travel: {action}")
    if action['action'] == 'end_trip':
        hero.turns += 1
        print(f"End trip -> Town! Total turns now: {hero.turns}")
        if count >= 5:
            print(f"*** TURN IN GILDED PENANCE! Completed at turn {hero.turns}! ***")
            break
        hero.hp = hero.max_hp
        continue

    zone_id = action['zone_id']
    node_name = action['node_name']
    level = 2
    node_names = BE._nodes_in_zone(zone_id)
    B.deal_zone(board, zone_id, level, node_names, rng)
    mob_name = board.zones[zone_id].dealt[node_name]
    outcome = BE.resolve_node_pull(hero, 'warrior', node_name, mob_name, quest_pool, rng, M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)
    B.discard_zone(board, zone_id, level)
    print(f"Pull at {node_name} vs {mob_name}: outcome={outcome['outcome']}, new_hp={hero.hp}, turns={hero.turns}")
    if outcome['outcome'] in ('declined', 'died', 'no_room'):
        hero.turns += 1
        print(f"Trip ended due to {outcome['outcome']} -> Town! Total turns: {hero.turns}")
        hero.hp = hero.max_hp
