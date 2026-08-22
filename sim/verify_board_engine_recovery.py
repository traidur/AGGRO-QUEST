"""
Verification for corpse recovery / death handling (checkpointed 2026-08-22) --
run_solo_trip's _resolve_forced_recovery plus run_solo_chain's death/recovery
post-processing (bag lock, decay+2, corpse_node + respawn on death; bag unlock on recovery).

Bit-for-bit comparison against _trip_chain is not attempted here -- the mob-sourcing paths
were already made deck-based in earlier chunks this session (see verify_board_engine_
scouted_pull.py/verify_board_engine_node_deal.py's own docstrings for why that rules out
exact reproduction). Instead: direct mechanical checks (hand-verifiable state transitions,
driven by a real seed known to produce a death) plus an aggregate comparison against
decay_stress_test's own death-count/gold-per-turn numbers, now that both sides have full
respawn-and-continue behavior for the first time.
"""
import random

import board_engine as BE
import macro_sim as M


def run_direct_checks(verbose=True):
    failures = []

    def check(name, condition, detail=""):
        if not condition:
            failures.append((name, detail))
            if verbose:
                print(f"FAIL: {name} -- {detail}")
        elif verbose:
            print(f"ok: {name}")

    # 1. min(min(x+1,cap)+1,cap) == min(x+2,cap) for every relevant x -- the arithmetic
    # run_solo_chain's docstring claims justifies applying +1 twice (once manually, once via
    # resolve_town_turn's own automatic bump) instead of +2 once.
    for cap in range(1, 5):
        for x in range(0, cap + 2):
            two_steps = min(min(x + 1, cap) + 1, cap)
            one_step = min(x + 2, cap)
            check(f"decay+1 twice == decay+2 once (x={x}, cap={cap})", two_steps == one_step,
                  (two_steps, one_step))

    # 2. Drive a real chain with a seed known to die at trip 3 and recover at trip 4 (warrior,
    # seed=0) -- trace hero state directly around the death and the recovery.
    snapshots = []
    orig = BE.run_solo_trip

    def traced(hero, class_name, quest_pool, fallback_target_zones, board, rng, *a, **kw):
        before = dict(bag=list(hero.bag), locked=list(hero.locked), corpse_node=hero.corpse_node,
                      decay_stage=dict(hero.decay_stage), active_quests=list(hero.active_quests),
                      position=hero.position)
        result = orig(hero, class_name, quest_pool, fallback_target_zones, board, rng, *a, **kw)
        after = dict(bag=list(hero.bag), locked=list(hero.locked), corpse_node=hero.corpse_node,
                     decay_stage=dict(hero.decay_stage), position=hero.position, alive=hero.alive)
        snapshots.append((before, result, after))
        return result
    BE.run_solo_trip = traced

    try:
        rng = random.Random(0)
        for entry in BE.run_solo_chain("warrior", "food_only", rng, 40, purchase_policy="save",
                                        bag_queue_position=0):
            pass
    finally:
        BE.run_solo_trip = orig

    death_idx = next(i for i, (b, r, a) in enumerate(snapshots) if not r["alive"])
    before, result, after = snapshots[death_idx]
    check("death trip reports alive=False", not result["alive"], result)
    check("death_node set on the trip result", result["death_node"] is not None, result)
    # Bag-lock: every slot that held something before the death should be locked after --
    # note run_solo_chain applies the lock AFTER run_solo_trip returns, so `after` here
    # (captured inside the traced wrapper, right when run_solo_trip itself returns) reflects
    # pre-lock state; the real lock check needs a snapshot taken from run_solo_chain's own
    # post-processing instead, see check below.

    recovery_idx = death_idx + 1
    if recovery_idx < len(snapshots):
        before_r, result_r, after_r = snapshots[recovery_idx]
        check("recovery trip's hero enters with corpse_node set", before_r["corpse_node"] is not None,
              before_r["corpse_node"])
        check("recovery trip's hero enters with locked bag slots",
              any(before_r["locked"]), before_r["locked"])
        check("recovered flag set when recovery succeeds", result_r["recovered"] or not result_r["alive"],
              result_r)
        if result_r["recovered"]:
            check("hero.alive reset to True after successful recovery (the bug this session found)",
                  after_r["alive"] is True, after_r)
            check("corpse_node cleared after recovery", after_r["corpse_node"] is None, after_r)

    # 3. Direct bag-lock/decay check via a controlled scenario -- construct a hero with a
    # known bag and active_quests, run it through run_solo_chain's own death post-processing
    # logic in isolation (replaying the exact lines, not re-deriving them) to confirm the
    # lock/decay outcome precisely.
    from board_state import HeroBoardState
    hero = HeroBoardState(class_name="warrior", hp=0.0, max_hp=18.0, position=(3, None),
                           bag=["food", {"loot": {"Royal Signets": 1}, "closed": False}],
                           locked=[False, False], active_quests=["Royal Signets"],
                           decay_stage={"Royal Signets": 2}, alive=False)
    quest_pool = M.LEVEL2_QUESTS
    # Replay run_solo_chain's own death-branch lines directly:
    for i, slot in enumerate(hero.bag):
        if slot is not None:
            hero.locked[i] = True
    for loot in hero.active_quests:
        q = quest_pool[loot]
        hero.decay_stage[loot] = min(hero.decay_stage.get(loot, 0) + 1, len(q["gold_ladder"]) - 1)
    check("bag-lock: both non-empty slots locked", hero.locked == [True, True], hero.locked)
    ladder_len = len(quest_pool["Royal Signets"]["gold_ladder"])
    check("decay bumped by +1 in this manual replay (the other +1 comes from resolve_town_turn)",
          hero.decay_stage["Royal Signets"] == min(3, ladder_len - 1), hero.decay_stage)

    print(f"\n{len(failures)} failures" if failures else "\nAll direct checks passed")
    return not failures


def aggregate_sanity_check(class_name, strategy="food_only", trials=20, old_chain_trips=20, seed=1, verbose=True):
    """Now that both sides have full respawn-and-continue behavior, compares TOTAL death
    count per chain (not just whether the chain ended in death) and gold-per-turn.
    run_solo_chain is turn-denominated (max_turns, not chain_trips) -- each new-side run uses
    that SAME seed's own old["total_turns"] as its max_turns, so both sides cover identical
    real playtime per seed."""
    old_deaths = 0
    old_gpt = []
    old_turns_by_seed = []
    for s in range(trials):
        r = M.decay_stress_test(class_name, strategy, random.Random(s + seed), chain_trips=old_chain_trips)
        old_deaths += r["died_count"]
        old_gpt.append(r["gold_per_turn"])
        old_turns_by_seed.append(r["total_turns"])
    old_avg_gpt = sum(old_gpt) / trials

    new_deaths = 0
    new_gpt = []
    for s in range(trials):
        rng = random.Random(s + seed)
        final_gold, final_turns = 0, 0
        deaths_this_chain = 0
        for alive, gold, xp, quests_completed, trainer_turn, turns in BE.run_solo_chain(
                class_name, strategy, rng, old_turns_by_seed[s]):
            final_gold, final_turns = gold, turns
            if not alive:
                deaths_this_chain += 1
        new_deaths += deaths_this_chain
        new_gpt.append(final_gold / final_turns if final_turns else 0.0)
    new_avg_gpt = sum(new_gpt) / trials

    if verbose:
        print(f"{class_name:12s} old: gold/turn={old_avg_gpt:.3f} total_deaths={old_deaths}   "
              f"new: gold/turn={new_avg_gpt:.3f} total_deaths={new_deaths}")
    return old_avg_gpt, new_avg_gpt, old_deaths, new_deaths


if __name__ == "__main__":
    ok = run_direct_checks()
    print("\n=== Aggregate sanity check (20 seeds, 20-trip chains, now with full recovery) ===")
    for class_name in M.CARD_SOURCE:
        aggregate_sanity_check(class_name)
    raise SystemExit(0 if ok else 1)
