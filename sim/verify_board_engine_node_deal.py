"""
Verification for the Node-pull half of the real-LevelDeck integration (checkpointed
2026-08-22, see run_solo_trip's own docstring) -- full-reset-every-turn Dealing,
choose_node_to_declare reading the real dealt board, and the Spice-blocked-routing fallback
(trip ends cleanly rather than hanging or crashing when nothing declarable is dealt).

Same two-part split as verify_board_engine_scouted_pull.py: direct mechanical checks first
(deterministic, hand-verifiable), then an aggregate-stats sanity check against the
pre-integration baseline (bit-for-bit is impossible now that Node-pulls are deck-sourced too,
same reasoning as every other real-deck swap this session).
"""
import random

import board_engine as BE
import board_state as B
import macro_sim as M
from board_state import HeroBoardState


def run_direct_checks(verbose=True):
    failures = []

    def check(name, condition, detail=""):
        if not condition:
            failures.append((name, detail))
            if verbose:
                print(f"FAIL: {name} -- {detail}")
        elif verbose:
            print(f"ok: {name}")

    # 1. Full reset every turn: dealing the same Zone twice in a row (with intervening
    # discard) produces a FRESH set of cards, not a repeat of the same dealt state.
    rng = random.Random(3)
    level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
    board = B.BoardState(mode="solo", heroes=[], zones={}, level_decks=level_decks)
    node_names = BE._nodes_in_zone(1)
    B.deal_zone(board, 1, 1, node_names, rng)
    first_deal = dict(board.zones[1].dealt)
    B.discard_zone(board, 1, 1)
    check("discard clears dealt", board.zones[1].dealt == {}, board.zones[1].dealt)
    B.deal_zone(board, 1, 1, node_names, rng)
    second_deal = dict(board.zones[1].dealt)
    check("second deal produces a full dealt board again", set(second_deal.keys()) == set(node_names),
          second_deal)
    check("discarded cards from first deal are in the discard pile",
          all(card in level_decks[1].discard_pile for card in first_deal.values()), level_decks[1].discard_pile)

    # 2. choose_node_to_declare skips a Spice-dealt Node in favor of the next incomplete quest.
    zone_board = B.ZoneBoardState(dealt={"waystation": B.SPICE, "cove": "Grunt"})
    hero = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, "town"),
                           bag=[None, None], locked=[False, False],
                           active_quests=[M.NODES["waystation"][1], M.NODES["cove"][1]])
    node = BE.choose_node_to_declare(hero, zone_board, M.QUESTS)
    check("skips Spice-dealt node, picks the real one", node == "cove", node)

    # 3. If EVERY relevant Node is Spice-dealt, choose_node_to_declare returns None (nothing
    # declarable) -- run_solo_trip must end the trip cleanly in this case, not hang.
    zone_board2 = B.ZoneBoardState(dealt={"waystation": B.SPICE, "cove": B.SPICE})
    node2 = BE.choose_node_to_declare(hero, zone_board2, M.QUESTS)
    check("all-Spice board returns None", node2 is None, node2)

    # 4. run_solo_trip doesn't hang when the level deck is rigged to be nothing but Spice --
    # every Zone the hero ever visits comes up empty, so the trip should end quickly and
    # cleanly (alive=True, no pull ever resolved) rather than loop forever.
    rng2 = random.Random(4)
    all_spice_decks = {1: B.LevelDeck(draw_pile=[B.SPICE] * 200), 2: B.LevelDeck(draw_pile=[B.SPICE] * 200)}
    board2 = B.BoardState(mode="solo", heroes=[], zones={}, level_decks=all_spice_decks)
    hero2 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, "town"),
                            bag=[None, None], locked=[False, False],
                            active_quests=[M.NODES["waystation"][1]])
    import time
    t0 = time.time()
    alive = BE.run_solo_trip(hero2, "warrior", M.QUESTS, {1, 2}, board2, rng2,
                              M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)
    elapsed = time.time() - t0
    check("all-Spice trip ends quickly, no hang", elapsed < 5, elapsed)
    check("all-Spice trip ends alive (never fought)", alive is True, alive)

    print(f"\n{len(failures)} failures" if failures else "\nAll direct checks passed")
    return not failures


def aggregate_sanity_check(class_name, strategy="food_only", trials=20, chain_trips=20, seed=1, verbose=True):
    """gold-PER-TURN, not gold-after-N-trips -- "trips" isn't a comparable cross-run unit (a
    trip's own length varies wildly by class and luck); decay_stress_test already computes
    its own gold_per_turn for exactly this reason (OPEN_QUESTIONS.md's "What a turn is,"
    locked)."""
    old = []
    for s in range(trials):
        r = M.decay_stress_test(class_name, strategy, random.Random(s + seed), chain_trips=chain_trips)
        old.append((r["gold_per_turn"], r["died_count"] > 0))
    old_avg_gpt = sum(g for g, _ in old) / trials
    old_deaths = sum(1 for _, d in old if d)

    new_gpt = []
    new_deaths = 0
    for s in range(trials):
        rng = random.Random(s + seed)
        final_gold, final_turns = 0, 0
        died = False
        for trip_num, alive, gold, xp, quests_completed, trainer_turn, turns in BE.run_solo_chain(
                class_name, strategy, rng, chain_trips):
            final_gold, final_turns = gold, turns
            if not alive:
                died = True
        new_gpt.append(final_gold / final_turns if final_turns else 0.0)
        if died:
            new_deaths += 1
    new_avg_gpt = sum(new_gpt) / trials

    if verbose:
        print(f"{class_name:12s} old: gold/turn={old_avg_gpt:.3f} deaths={old_deaths}/{trials}   "
              f"new: gold/turn={new_avg_gpt:.3f} deaths={new_deaths}/{trials}")
    return old_avg_gpt, new_avg_gpt


if __name__ == "__main__":
    ok = run_direct_checks()
    print("\n=== Aggregate sanity check (20 seeds, 20-trip chains) ===")
    for class_name in M.CARD_SOURCE:
        aggregate_sanity_check(class_name)
    raise SystemExit(0 if ok else 1)
