"""
Permanent regression tool, Layer 1 verification for board_engine.resolve_border_crossing --
same mocked-replay strategy as verify_board_engine.py's Node-pull check (see its own
docstring for why exact mob-sequence reproduction is impossible in general but isn't needed
here: resolve_border_crossing still sources its mob via the OLD _scouted_pull_mob, not the
real LevelDeck, by deliberate checkpoint -- see board_engine.py's own module docstring).

Scenario is forced to a Zone-1-to-Zone-2 crossing: all 3 active quests are drawn from Zone
2's own Nodes (current_position=1), so run_one_trip's routing has to cross border_1_2 on its
very first turn before it can pull anything. _scouted_pull_mob and _engine_pull are both
monkeypatched -- the former just to mark "the next _engine_pull call is a crossing, not a
node pull" (Border crossings are the ONLY caller of _scouted_pull_mob in the whole per-pull
path), the latter to capture the actual (mob_name, hand) pair used.
"""
import random

import board_engine as BE
import macro_sim as M
from board_state import HeroBoardState

_ZONE2_LOOT_NAMES = [loot for node, (tier, loot) in M.NODES.items() if M.NODE_ZONE[node] == 2]


class _ReplayRNG:
    def __init__(self, hands):
        self._hands = list(hands)
        self._i = 0

    def choice(self, seq):
        hand = self._hands[self._i]
        self._i += 1
        return hand


def _capture_crossing(class_name, active_quests, seed, risk_tolerance_base, risk_only_as_last_resort):
    """Runs run_one_trip once, forced into a border_1_2 crossing on its first turn, capturing
    the (mob_name, hand) the crossing actually used plus the trip's final result for
    comparison."""
    pending = {"active": False}
    trace = []
    orig_scouted = M._scouted_pull_mob
    orig_engine_pull = M._engine_pull

    def traced_scouted(class_name_, tier, rng_):
        result = orig_scouted(class_name_, tier, rng_)
        pending["active"] = True
        return result
    M._scouted_pull_mob = traced_scouted

    def traced_engine_pull(class_name_, mob_name, hand, pattern, mob_hp, starting_hp):
        result = orig_engine_pull(class_name_, mob_name, hand, pattern, mob_hp, starting_hp)
        if pending["active"]:
            win, final_hp, final_rounds = result
            # Isolate the crossing's OWN immediate outcome here -- run_one_trip keeps going
            # after a successful crossing (further node pulls in the destination Zone), so
            # its final returned result reflects the WHOLE trip, not just this one pull.
            trace.append(dict(mob_name=mob_name, hand=hand, win=win, hp_after=final_hp,
                               gold_after_crossing=(1 if win else 0)))
            pending["active"] = False
        return result
    M._engine_pull = traced_engine_pull

    try:
        rng = random.Random(seed)
        bag = [None, None]
        locked = [False, False]
        M.run_one_trip(class_name, "none", rng, bag=bag, locked=locked,
                        active_quests=list(active_quests), quest_pool=M.QUESTS,
                        current_position=1, mob_level=1, gold=0,
                        risk_tolerance=M.RISK_TOLERANCE, risk_tolerance_base=risk_tolerance_base,
                        risk_only_as_last_resort=risk_only_as_last_resort,
                        fallback_target_zones={1, 2})
    finally:
        M._scouted_pull_mob = orig_scouted
        M._engine_pull = orig_engine_pull
    assert len(trace) == 1, f"expected exactly one crossing, got {len(trace)}"
    return trace[0]


def verify_class(class_name, trials=30, verbose=False):
    mismatches = []
    for seed in range(trials):
        active_quests = random.Random(2000 + seed).sample(_ZONE2_LOOT_NAMES, 3)
        entry = _capture_crossing(class_name, active_quests, seed, M.RISK_TOLERANCE_BASE, True)

        mod = M.CARD_SOURCE[class_name]
        max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
        hero = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(1, None),
                               bag=[None, None], locked=[False, False])
        rng = _ReplayRNG([entry["hand"]])
        outcome = BE.resolve_border_crossing(hero, class_name, "border_1_2", 2, entry["mob_name"], rng,
                                              M.RISK_TOLERANCE_BASE, True)

        if entry["hp_after"] <= 0:
            expected = (0.0, 0, "border:border_1_2:1:2")
            actual = (hero.hp, hero.gold, outcome.get("death_marker"))
            if outcome["outcome"] != "died" or actual != expected:
                mismatches.append((seed, "died", expected, (outcome["outcome"], actual)))
        else:
            expected = (entry["hp_after"], entry["gold_after_crossing"], "border_1_2")
            actual = (hero.hp, hero.gold, hero.position[0])
            if actual != expected:
                mismatches.append((seed, "survived", expected, actual))

        if verbose and mismatches and mismatches[-1][0] == seed:
            print(f"MISMATCH {class_name} seed={seed}: {mismatches[-1]}")
    return trials, mismatches


def verify_all(trials=30, verbose=False):
    grand_total = 0
    grand_mismatches = 0
    for class_name in M.CARD_SOURCE:
        total, mismatches = verify_class(class_name, trials=trials, verbose=verbose)
        grand_total += total
        grand_mismatches += len(mismatches)
        status = "OK" if not mismatches else f"{len(mismatches)} MISMATCHES"
        print(f"{class_name:12s} {total:4d} scenarios  {status}")
    print(f"\nTotal: {grand_total} scenarios, {grand_mismatches} mismatches")
    return grand_mismatches == 0


if __name__ == "__main__":
    ok = verify_all(verbose=True)
    raise SystemExit(0 if ok else 1)
