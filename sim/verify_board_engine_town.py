"""
Permanent regression tool, Layer 1 verification for board_engine.resolve_town_turn (same
two-layer strategy as verify_board_engine.py's Node-pull check, see its own docstring for why
exact reproduction is the right bar here even though it wasn't for the deck/mob-sourcing side).

**Why the ground truth isn't just chain_log[k] directly:** _trip_chain's own code SPLITS one
real Town visit across two places -- turn-in happens at the tail of one while-loop iteration
(using the field trip that just ended), and restock/Phase-1-pickup/Purchase-Queue happen at
the head of the NEXT iteration (preparing for the field trip after that). That's a coding
convenience, not two separate real Town turns -- a hero standing at Town does all of it in one
visit ("one turn total per Town visit," OPEN_QUESTIONS.md). resolve_town_turn bundles all of it
into one call to match that real semantics, which means the correct comparison stitches
together TWO of _trip_chain's yields: chain_log[k]'s gold/xp/quests_completed (trip k+1's own
turn-in) plus chain_log[k+1]'s trainer_turn (the shopping that happens right after, before trip
k+2) plus calls[k+1]'s incoming gold/active_quests (the state after that same shopping, right
when trip k+2 is about to start). An earlier version of this test compared resolve_town_turn's
output directly against chain_log[k] alone and found 159/159 "mismatches" that turned out to
be exactly this indexing mismatch, not a real bug in resolve_town_turn -- gold and trainer_turn
were the only two fields wrong, and always in the direction of the shadow hero shopping "one
Town visit too early" relative to how _trip_chain's own loop happens to be coded.

Death trips are excluded (any seed containing one, anywhere in the captured window, is skipped
entirely) -- death/corpse-recovery bookkeeping is run_one_trip/_trip_chain's death branch, not
a Town-turn action, and isn't in board_engine.py's scope yet (Border crossings aren't built).
"""
import copy
import random

import board_engine as BE
import macro_sim as M
from board_state import HeroBoardState


def _run_chain_with_calls(class_name, strategy, seed, num_calls):
    """Drives _trip_chain for real, capturing `num_calls` run_one_trip calls (both their
    incoming kwargs and outgoing result) plus the matching yielded chain_log entries."""
    calls = []
    orig_run_one_trip = M.run_one_trip

    def traced_run_one_trip(*args, **kwargs):
        result = orig_run_one_trip(*args, **kwargs)
        calls.append(dict(
            in_active_quests=list(kwargs["active_quests"]), in_gold=kwargs["gold"],
            in_current_position=kwargs["current_position"],
            out_bag=copy.deepcopy(result["bag"]), out_locked=list(result["locked"]),
            out_current_position=result["current_position"], out_died=result["died"],
            out_gold=result["gold"],  # the field trip's OWN Gold earnings (1 per won pull,
            # via _engine_pull) -- _trip_chain sets gold = result["gold"] BEFORE turn-in even
            # starts, so the shadow hero needs this seeded too, not left at its dataclass
            # default of 0.
        ))
        return result
    M.run_one_trip = traced_run_one_trip

    chain_log = []
    try:
        rng = random.Random(seed)
        for trip_num, result, gold, xp, decay_stage, corpse_node, quests_completed, trainer_turn in M._trip_chain(
                class_name, strategy, rng, purchase_policy="save", bag_queue_position=0):
            chain_log.append(dict(gold=gold, xp=xp, quests_completed=quests_completed, trainer_turn=trainer_turn))
            if len(calls) >= num_calls:
                break
    finally:
        M.run_one_trip = orig_run_one_trip
    return chain_log, calls


def verify_class(class_name, strategy="food_only", trials=20, num_calls=3, verbose=False):
    mismatches = []
    scenarios_run = 0
    for seed in range(trials):
        chain_log, calls = _run_chain_with_calls(class_name, strategy, seed, num_calls)
        if len(calls) < 2 or any(c["out_died"] for c in calls):
            continue  # need at least one "next call" to compare against; death out of scope
        scenarios_run += 1

        mod = M.CARD_SOURCE[class_name]
        max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
        purchase_queue = M._build_purchase_queue(class_name, 0)
        replay_rng = random.Random(seed + 10_000_000)  # independent -- only quest-bag refill
        # order depends on this, not part of what's being compared

        # ONE hero, persistent across the whole seed's k-loop -- xp/decay_stage/acquired/
        # quest_bag must carry forward call to call, same as a real hero's chain-long state
        # would. Only bag/locked/active_quests/gold/position get overwritten per-k from the
        # captured snapshot (the field-trip outcome that just happened); an earlier version of
        # this test rebuilt a fresh HeroBoardState every k, silently resetting xp back to 0
        # each time and producing a cascade of k=1+ mismatches that had nothing to do with
        # resolve_town_turn itself.
        hero = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp,
                               position=(1, "town"), bag=[], locked=[])

        for k in range(len(calls) - 1):
            hero.bag = copy.deepcopy(calls[k]["out_bag"])
            hero.locked = list(calls[k]["out_locked"])
            hero.active_quests = list(calls[k]["in_active_quests"])
            hero.gold = calls[k]["out_gold"]
            pos = calls[k]["out_current_position"]
            hero.position = (pos, "town") if isinstance(pos, int) else (pos, None)

            turn_result = BE.resolve_town_turn(hero, class_name, strategy, purchase_queue, "save", replay_rng)

            expected = (calls[k + 1]["in_gold"], chain_log[k]["xp"], chain_log[k]["quests_completed"],
                        chain_log[k + 1]["trainer_turn"])
            actual = (hero.gold, hero.xp, turn_result["quests_completed"], turn_result["trainer_turn"])
            if actual != expected:
                mismatches.append((seed, k, expected, actual))
                if verbose:
                    print(f"MISMATCH {class_name} seed={seed} k={k}: expected(gold,xp,qc,tt)={expected} actual={actual}")
                break
    return scenarios_run, mismatches


def verify_all(strategy="food_only", trials=20, num_calls=3, verbose=False):
    grand_scenarios = 0
    grand_mismatches = 0
    for class_name in M.CARD_SOURCE:
        scenarios_run, mismatches = verify_class(class_name, strategy=strategy, trials=trials,
                                                   num_calls=num_calls, verbose=verbose)
        grand_scenarios += scenarios_run
        grand_mismatches += len(mismatches)
        status = "OK" if not mismatches else f"{len(mismatches)} MISMATCHES"
        print(f"{class_name:12s} {scenarios_run:4d}/{trials} usable scenarios  {status}")
    print(f"\nTotal: {grand_scenarios} scenarios, {grand_mismatches} mismatches")
    return grand_mismatches == 0


if __name__ == "__main__":
    ok = verify_all(verbose=True)
    raise SystemExit(0 if ok else 1)
