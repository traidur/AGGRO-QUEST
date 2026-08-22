"""
Permanent regression tool: the capstone check for BoardState's solo-mode driver
(board_engine.run_solo_chain) -- proves it reproduces macro_sim._trip_chain's exact
trip-by-trip (gold, xp, quests_completed, trainer_turn) sequence bit-for-bit, for the same
class/strategy/seed. This is the one true end-to-end bit-for-bit proof possible for the
driver, deliberately obtained BEFORE the real LevelDeck gets wired in (run_solo_trip still
uses the old rng-based tier-weighted mob draw, checkpointed 2026-08-21 specifically so this
comparison stays meaningful -- see run_solo_trip's own docstring). Once the real deck
replaces that sourcing, this exact bit-for-bit bar becomes unachievable for the same reason
verify_board_engine.py's Node-pull check couldn't use it either, and aggregate-statistics
verification takes over.

Comparison stops at the first death in EITHER chain -- run_solo_chain has no respawn/corpse-
recovery logic yet (a hero who dies simply stops, matching its own documented scope), while
_trip_chain keeps going (respawn, corpse lock, recovery pulls). Comparing past that point
would be comparing two deliberately different behaviors, not checking for a bug.
"""
import random

import board_engine as BE
import macro_sim as M


def verify_class(class_name, strategy="food_only", trials=30, chain_trips=15, verbose=False):
    mismatches = []
    scenarios_run = 0
    for seed in range(trials):
        old_log = []
        rng_old = random.Random(seed)
        for trip_num, result, gold, xp, decay_stage, corpse_node, quests_completed, trainer_turn in M._trip_chain(
                class_name, strategy, rng_old, purchase_policy="save", bag_queue_position=0):
            old_log.append((gold, xp, quests_completed, trainer_turn, result["died"]))
            if trip_num >= chain_trips or result["died"]:
                break

        rng_new = random.Random(seed)
        new_log = []
        for trip_num, alive, gold, xp, quests_completed, trainer_turn in BE.run_solo_chain(
                class_name, strategy, rng_new, chain_trips, purchase_policy="save", bag_queue_position=0):
            new_log.append((gold, xp, quests_completed, trainer_turn, not alive))
            if not alive:
                break

        scenarios_run += 1
        compare_len = min(len(old_log), len(new_log))
        for i in range(compare_len):
            if old_log[i] != new_log[i]:
                mismatches.append((seed, i, old_log[i], new_log[i]))
                if verbose:
                    print(f"MISMATCH {class_name} seed={seed} trip={i}: old={old_log[i]} new={new_log[i]}")
                break
        else:
            if len(old_log) != len(new_log):
                mismatches.append((seed, "length", len(old_log), len(new_log)))
                if verbose:
                    print(f"MISMATCH {class_name} seed={seed}: length old={len(old_log)} new={len(new_log)}")
    return scenarios_run, mismatches


def verify_all(strategy="food_only", trials=30, chain_trips=15, verbose=False):
    grand_scenarios = 0
    grand_mismatches = 0
    for class_name in M.CARD_SOURCE:
        scenarios_run, mismatches = verify_class(class_name, strategy=strategy, trials=trials,
                                                   chain_trips=chain_trips, verbose=verbose)
        grand_scenarios += scenarios_run
        grand_mismatches += len(mismatches)
        status = "OK" if not mismatches else f"{len(mismatches)} MISMATCHES"
        print(f"{class_name:12s} {scenarios_run:4d} scenarios  {status}")
    print(f"\nTotal: {grand_scenarios} scenarios, {grand_mismatches} mismatches")
    return grand_mismatches == 0


if __name__ == "__main__":
    ok = verify_all(verbose=True)
    raise SystemExit(0 if ok else 1)
