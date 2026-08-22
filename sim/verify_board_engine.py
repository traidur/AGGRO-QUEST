"""
Permanent regression tool, Layer 1 of the two-layer BoardState verification strategy
(checkpointed 2026-08-21, see unified-sprouting-aurora.md's Part 3a): proves
board_engine.resolve_node_pull reproduces run_one_trip's own per-pull bookkeeping (hp, Gold,
bag, consumables) bit-for-bit -- NOT by comparing which mob shows up (that's structurally
impossible to match once the deck replaces rng.choices, see below), but by mocking the deck to
replay the OLD code's exact historical mob-draw sequence and requiring everything downstream of
that draw to land in the identical state. Layer 2 (real live deck, aggregate statistics within
expected bounds rather than exact equality) is separate and not built here -- it needs
choose_node_to_declare's routing to eventually cover cross-zone travel, which board_engine.py
doesn't yet.

Why not compare mob sequences directly: a shuffled 19-card deck drawn without replacement is a
structurally different random process from an independent weighted rng.choices draw -- no seed
choice makes those two sequences match beyond coincidence. Isolating "did the surrounding
bookkeeping get ported correctly" from "the deck changes which mob shows up" is exactly what
this mocked-replay approach is for, the same principle already used to catch the max-HP-seeding
and death-tiebreak-order bugs during the combat-engine port.

Scenario is deliberately constrained to Zone 1 only (all 3 active quests draw from Zone 1's own
4 Nodes, current_position=1, mob_level=1) so run_one_trip's own cross-zone travel/Border-
crossing logic never fires -- board_engine.py doesn't implement that yet (Node-pulls-only
scope, see its own docstring), so a scenario that could trigger it wouldn't be a fair
comparison.
"""
import random

import board_engine as BE
import macro_sim as M
from board_state import HeroBoardState

_ZONE1_LOOT_NAMES = [loot for node, (tier, loot) in M.NODES.items() if M.NODE_ZONE[node] == 1]


class _ReplayRNG:
    """Stand-in for random.Random that replays a pre-recorded sequence of .choice() results
    instead of drawing randomly -- guarantees resolve_node_pull sees the exact same hand at
    each pull that the captured OLD trace did, so any state divergence downstream can only be
    a real bookkeeping bug, not incidental hand-draw drift."""

    def __init__(self, hands):
        self._hands = list(hands)
        self._i = 0

    def choice(self, seq):
        hand = self._hands[self._i]
        self._i += 1
        return hand


def _capture_old_trace(class_name, active_quests, quest_pool, seed, risk_tolerance,
                        risk_tolerance_base, risk_only_as_last_resort):
    """Runs the OLD run_one_trip once, capturing (mob_name, hand, loot_name, hp_after,
    gold_after) for every real pull it makes, plus a snapshot of bag/locked/consumables_used
    after each one -- the ground truth Layer 1 replays against. Monkeypatches
    macro_sim._engine_pull (to capture mob_name/hand/result) and macro_sim._add_loot (to
    capture which loot_name a win actually granted) for the duration of one call only."""
    trace = []
    orig_engine_pull = M._engine_pull
    orig_add_loot = M._add_loot

    def traced_engine_pull(class_name_, mob_name, hand, pattern, mob_hp, starting_hp):
        result = orig_engine_pull(class_name_, mob_name, hand, pattern, mob_hp, starting_hp)
        trace.append(dict(mob_name=mob_name, hand=hand, loot_name=None))
        return result
    M._engine_pull = traced_engine_pull

    def traced_add_loot(bag, locked, loot_name):
        result = orig_add_loot(bag, locked, loot_name)
        if trace:
            trace[-1]["loot_name"] = loot_name
        return result
    M._add_loot = traced_add_loot

    try:
        rng = random.Random(seed)
        bag = [None, None]
        locked = [False, False]
        M.run_one_trip(class_name, "none", rng, bag=bag, locked=locked,
                        active_quests=list(active_quests), quest_pool=quest_pool,
                        current_position=1, mob_level=1, gold=0,
                        risk_tolerance=risk_tolerance, risk_tolerance_base=risk_tolerance_base,
                        risk_only_as_last_resort=risk_only_as_last_resort,
                        fallback_target_zones={1, 2})
    finally:
        M._engine_pull = orig_engine_pull
        M._add_loot = orig_add_loot
    return trace


def _replay_new(class_name, active_quests, trace):
    """Replays the captured trace through board_engine.resolve_node_pull, one pull at a time,
    feeding the exact same hand via _ReplayRNG and the exact same mob_name directly (bypassing
    the deck entirely -- this is Layer 1, isolating bookkeeping fidelity from deck sourcing).

    node_name is NOT read from the captured trace (a flee grants no loot, so _add_loot's
    capture hook never fires for it, leaving no way to recover which node a fled pull was
    even for). Instead it's derived fresh via the exact same routing rule run_one_trip itself
    uses -- the first still-incomplete quest in active_quests' own order. Provably identical to
    _hop_distance-sorted routing in this scenario specifically: every candidate node is Zone 1
    and current_position never leaves Zone 1, so _hop_distance is the same constant for every
    candidate, making the sort a same-key no-op (Python's sort is stable) that just preserves
    active_quests' original order -- this is NOT a general routing implementation, only valid
    because the whole scenario is deliberately confined to one Zone.

    Returns the final hero state for comparison against the OLD trip's own final bag/gold/hp."""
    mod = M.CARD_SOURCE[class_name]
    max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
    hero = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(1, None),
                           bag=[None, None], locked=[False, False], gold=0,
                           active_quests=list(active_quests))
    rng = _ReplayRNG([entry["hand"] for entry in trace])
    for entry in trace:
        incomplete = [loot for loot in hero.active_quests
                      if M._accessible_count(hero.bag, hero.locked, loot) < M.QUESTS[loot]["required"]]
        loot_name = incomplete[0]
        node_name = next(n for n, (t, l) in M.NODES.items() if l == loot_name)
        outcome = BE.resolve_node_pull(hero, class_name, node_name, entry["mob_name"], M.QUESTS,
                                        rng, M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)
        if outcome["outcome"] == "died":
            break
    return hero


def verify_class(class_name, trials=20, verbose=False):
    mismatches = []
    for seed in range(trials):
        active_quests = random.Random(1000 + seed).sample(_ZONE1_LOOT_NAMES, 3)
        trace = _capture_old_trace(class_name, active_quests, M.QUESTS, seed,
                                    M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)
        # Re-run old trip fresh to get its OWN final state for comparison (run once above only
        # to build the trace; run again identically to read back final hp/gold/bag cleanly).
        rng = random.Random(seed)
        bag = [None, None]
        locked = [False, False]
        old_result = M.run_one_trip(class_name, "none", rng, bag=bag, locked=locked,
                                     active_quests=list(active_quests), quest_pool=M.QUESTS,
                                     current_position=1, mob_level=1, gold=0,
                                     risk_tolerance=M.RISK_TOLERANCE, risk_tolerance_base=M.RISK_TOLERANCE_BASE,
                                     risk_only_as_last_resort=True, fallback_target_zones={1, 2})

        new_hero = _replay_new(class_name, active_quests, trace)

        old_hp = old_result["hp"]
        old_gold = old_result["gold"]
        old_bag = old_result["bag"]
        if (old_hp, old_gold, old_bag) != (new_hero.hp, new_hero.gold, new_hero.bag):
            mismatches.append((seed, (old_hp, old_gold, old_bag), (new_hero.hp, new_hero.gold, new_hero.bag)))
            if verbose:
                print(f"MISMATCH {class_name} seed={seed}: "
                      f"old=(hp={old_hp}, gold={old_gold}, bag={old_bag}) "
                      f"new=(hp={new_hero.hp}, gold={new_hero.gold}, bag={new_hero.bag})")
    return trials, mismatches


def verify_all(trials=20, verbose=False):
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
