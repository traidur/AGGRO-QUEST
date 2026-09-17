"""Verify a BoardState-based port of quest_cost_gauntlet.py's measure_cost() against the
original _trip_chain-based version before retiring the old mob-dealing/trip-chain machinery.

Old system's unit is "pulls" (simulator bookkeeping). New system (run_solo_chain) is
deliberately turn-denominated instead -- board_state.py's own docstring says pulls/trips were
never a real physical unit, turns are. So this isn't a bit-for-bit port (the units differ on
purpose), it's a check that the two systems tell the same *story*: does a bigger `required`
cost proportionally more, do death rates land in the same range, does completion rate/trip
hold up -- the actual question quest_cost_gauntlet.py exists to answer."""
import random

import macro_sim as M
import board_state as B
import board_engine as BE
import quest_cost_gauntlet as QCG
from board_state import HeroBoardState


def measure_cost_v2(required, trials_per_class=50, max_turns=800, seed=42, strategy="food_only",
                     classes=None, zone=4):
    """BoardState-driven equivalent of quest_cost_gauntlet.measure_cost -- same isolation
    trick (monkey-patch macro_sim.py's QUESTS/NODES/etc., since board_engine.py reads them
    live through its own `import macro_sim as M`), driven through run_solo_chain instead of
    _trip_chain. zone defaults to 4 (a real Trainer zone) since board_engine.py's
    BoardState.town_markets is hardcoded to zones {3, 4}, unlike the old tool's fully
    caller-configurable zone."""
    if classes is None:
        classes = QCG.CLASSES
    orig = dict(QUESTS=M.QUESTS, NODES=M.NODES, NODE_ZONE=M.NODE_ZONE,
                ACTIVE_QUEST_COUNT=M.ACTIVE_QUEST_COUNT, LEVEL2_QUESTS=M.LEVEL2_QUESTS,
                LEVEL2_XP_THRESHOLD=M.LEVEL2_XP_THRESHOLD, LEVEL1_QUEST_ZONES=M.LEVEL1_QUEST_ZONES,
                LEVEL2_QUEST_ZONES=M.LEVEL2_QUEST_ZONES, TRAINER_ZONES=M.TRAINER_ZONES)
    test_quest = {"Test Loot": dict(required=required, base_xp=required, gold_ladder=[0, 0, 0, 0],
                                     allow_duplicates=True)}
    M.QUESTS = test_quest
    M.LEVEL2_QUESTS = dict(test_quest)
    M.LEVEL2_XP_THRESHOLD = -1
    M.LEVEL1_QUEST_ZONES = M.LEVEL2_QUEST_ZONES = {zone}
    M.TRAINER_ZONES = {zone}
    M.NODES = {"test_node": ("standard", "Test Loot")}
    M.NODE_ZONE = {"test_node": zone}
    M.ACTIVE_QUEST_COUNT = 1
    try:
        total_turns = 0
        total_completions = 0
        total_deaths = 0
        total_cycles = 0
        for cls in classes:
            for t in range(trials_per_class):
                rng = random.Random(f"{seed}-{required}-{cls}-{t}")
                for alive, gold, xp, quests_completed, trainer_turn, turns in BE.run_solo_chain(
                        cls, strategy, rng, max_turns=max_turns):
                    total_cycles += 1
                    total_completions += quests_completed
                    if not alive:
                        total_deaths += 1
                total_turns += turns  # cumulative turns for this whole chain, last yield's value
        return dict(
            avg_turns_per_completion=total_turns / max(total_completions, 1),
            avg_completions_per_trial=total_completions / (len(classes) * trials_per_class),
            death_rate_per_cycle=total_deaths / max(total_cycles, 1),
            total_completions=total_completions,
        )
    finally:
        M.QUESTS, M.NODES, M.NODE_ZONE = orig["QUESTS"], orig["NODES"], orig["NODE_ZONE"]
        M.ACTIVE_QUEST_COUNT, M.LEVEL2_QUESTS = orig["ACTIVE_QUEST_COUNT"], orig["LEVEL2_QUESTS"]
        M.LEVEL2_XP_THRESHOLD = orig["LEVEL2_XP_THRESHOLD"]
        M.LEVEL1_QUEST_ZONES, M.LEVEL2_QUEST_ZONES = orig["LEVEL1_QUEST_ZONES"], orig["LEVEL2_QUEST_ZONES"]
        M.TRAINER_ZONES = orig["TRAINER_ZONES"]


def measure_cost_v3(required, trials_per_class=50, max_turns=800, seed=42, strategy="food_only",
                     classes=None, zone=4):
    """Same isolation/monkey-patch as measure_cost_v2, but hand-inlines run_solo_chain's own
    loop (board_engine.py:1646) instead of calling it, purely so this function can keep a
    local `hero` reference and snapshot hero.decay_stage[loot] right before each
    resolve_town_turn call -- the same "decay-stage-at-turn-in" measurement
    quest_cost_gauntlet.measure_cost's stage_counts tracks, just read off BoardState's real
    hero.decay_stage dict instead of _trip_chain's loop-local one. Not calling run_solo_chain
    directly because it's a generator that yields (alive, gold, xp, quests_completed,
    trainer_turn, turns) only -- no hero handle, and this measurement needs one."""
    if classes is None:
        classes = QCG.CLASSES
    orig = dict(QUESTS=M.QUESTS, NODES=M.NODES, NODE_ZONE=M.NODE_ZONE,
                ACTIVE_QUEST_COUNT=M.ACTIVE_QUEST_COUNT, LEVEL2_QUESTS=M.LEVEL2_QUESTS,
                LEVEL2_XP_THRESHOLD=M.LEVEL2_XP_THRESHOLD, LEVEL1_QUEST_ZONES=M.LEVEL1_QUEST_ZONES,
                LEVEL2_QUEST_ZONES=M.LEVEL2_QUEST_ZONES, TRAINER_ZONES=M.TRAINER_ZONES)
    test_quest = {"Test Loot": dict(required=required, base_xp=required, gold_ladder=[0, 1, 2, 3],
                                     allow_duplicates=True)}
    M.QUESTS = test_quest
    M.LEVEL2_QUESTS = dict(test_quest)
    M.LEVEL2_XP_THRESHOLD = -1
    M.LEVEL1_QUEST_ZONES = M.LEVEL2_QUEST_ZONES = {zone}
    M.TRAINER_ZONES = {zone}
    M.NODES = {"test_node": ("standard", "Test Loot")}
    M.NODE_ZONE = {"test_node": zone}
    M.ACTIVE_QUEST_COUNT = 1
    try:
        total_turns = 0
        total_completions = 0
        total_deaths = 0
        total_cycles = 0
        total_trips_at_completion = 0  # sum of (trips since last completion), one term per completion
        stage_counts = [0, 0, 0, 0]  # Gold/Silver/Bronze/nothing, same indexing as gold_ladder above
        for cls in classes:
            for t in range(trials_per_class):
                rng = random.Random(f"{seed}-{required}-{cls}-{t}")
                mod = M.CARD_SOURCE[cls]
                max_hp = float(getattr(mod, M.HP_ATTR[cls]))
                hero = HeroBoardState(class_name=cls, hp=max_hp, max_hp=max_hp, position=(1, "town"),
                                       bag=[None] * M.BAG_SIZE, locked=[False] * M.BAG_SIZE)
                M._add_food(hero.bag, hero.locked)
                if cls in M.LEVEL2_PURCHASED_ORDER:
                    hero.skill_purchase_order = list(range(len(M.LEVEL2_PURCHASED_ORDER[cls])))
                    rng.shuffle(hero.skill_purchase_order)
                purchase_queue = M._build_purchase_queue(cls, 0)
                level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
                loot_decks = {1: B.LootDeck.new(1, rng), 2: B.LootDeck.new(2, rng)}
                board = B.BoardState(mode="solo", heroes=[hero], zones={}, level_decks=level_decks,
                                      loot_decks=loot_decks)
                board.setup_quests(rng)
                BE.resolve_town_turn(hero, cls, strategy, purchase_queue, "save", rng, board)
                trips_since_completion = 0
                while hero.turns < max_turns:
                    pending_mandatory = (cls in M.LEVEL2_MANDATORY and hero.xp >= M.LEVEL2_XP_THRESHOLD
                                          and "mandatory" not in hero.acquired)
                    valid_quest_zones = M.LEVEL2_QUEST_ZONES if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.LEVEL1_QUEST_ZONES
                    fallback_target_zones = M.TRAINER_ZONES if pending_mandatory else valid_quest_zones
                    quest_pool = M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS

                    trip_result = BE.run_solo_trip(hero, cls, quest_pool, fallback_target_zones, board, rng,
                                                    M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)
                    if trip_result["recovered"]:
                        BE.apply_recovery_post_processing(hero)
                    if not trip_result["alive"]:
                        BE.apply_death_post_processing(hero, quest_pool, trip_result["death_node"])

                    prev_stage = hero.decay_stage.get("Test Loot", 0)
                    town_result = BE.resolve_town_turn(hero, cls, strategy, purchase_queue, "save", rng, board)
                    total_cycles += 1
                    trips_since_completion += 1
                    qc = town_result["quests_completed"]
                    total_completions += qc
                    if qc:
                        stage_counts[prev_stage] += 1
                        total_trips_at_completion += trips_since_completion
                        trips_since_completion = 0
                    if not trip_result["alive"]:
                        total_deaths += 1
                total_turns += hero.turns
        return dict(
            avg_turns_per_completion=total_turns / max(total_completions, 1),
            avg_trips_per_completion=total_trips_at_completion / max(total_completions, 1),
            death_rate_per_cycle=total_deaths / max(total_cycles, 1),
            total_completions=total_completions,
            stage_pct=[100 * c / total_completions for c in stage_counts] if total_completions else [0, 0, 0, 0],
        )
    finally:
        M.QUESTS, M.NODES, M.NODE_ZONE = orig["QUESTS"], orig["NODES"], orig["NODE_ZONE"]
        M.ACTIVE_QUEST_COUNT, M.LEVEL2_QUESTS = orig["ACTIVE_QUEST_COUNT"], orig["LEVEL2_QUESTS"]
        M.LEVEL2_XP_THRESHOLD = orig["LEVEL2_XP_THRESHOLD"]
        M.LEVEL1_QUEST_ZONES, M.LEVEL2_QUEST_ZONES = orig["LEVEL1_QUEST_ZONES"], orig["LEVEL2_QUEST_ZONES"]
        M.TRAINER_ZONES = orig["TRAINER_ZONES"]


def main():
    for required in [2, 3, 4, 5]:
        old = QCG.measure_cost(required, trials_per_class=10, chain_trips=20, zone=4)
        new = measure_cost_v3(required, trials_per_class=10, max_turns=250)
        print(f"--- required={required} ---")
        print(f"  OLD (_trip_chain, trips-denominated):  trips/completion={old['trips_per_completion']:.2f}  "
              f"stage%={[round(x, 1) for x in old['stage_pct']]}")
        print(f"  NEW (run_solo_chain, turns-denominated): turns/completion={new['avg_turns_per_completion']:.2f}  "
              f"trips/completion={new['avg_trips_per_completion']:.2f}  "
              f"stage%={[round(x, 1) for x in new['stage_pct']]}")
        print(flush=True)


if __name__ == "__main__":
    main()
