"""
Verification for board_engine.scouted_pull_from_deck / _best_scouted_candidate (the first
piece of the real-LevelDeck integration, checkpointed 2026-08-22 -- see run_solo_trip's own
docstring for why Border crossings went first).

Two parts, matching this project's established split once a real deck replaces independent
rng.choices sourcing:
1. Direct mechanical checks (deck draw/discard/Spice-skip behavior, correct-matchup
   selection) -- deterministic, hand-verifiable, no aggregate needed.
2. Aggregate-stats sanity check: run_solo_chain with the real deck wired into Border
   crossings, compared to the pre-swap baseline (decay_stress_test) -- NOT bit-for-bit
   (impossible once a real deck replaces rng.choices, same reasoning as every other
   real-deck swap this session), just confirming gold/deaths land in a similar ballpark,
   since Border crossings are a minority of a trip's total pulls.
"""
import random

import board_engine as BE
import board_state as B
import condensed_trip as T
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

    # 1. A deck with only Spice on top gets skipped until 2 real mobs are found.
    deck = B.LevelDeck(draw_pile=["Grunt", B.SPICE, B.SPICE, "Ambusher"])
    rng = random.Random(1)
    mob = BE.scouted_pull_from_deck("warrior", deck, rng)
    check("skips Spice, returns a real mob", mob in ("Grunt", "Ambusher"), mob)
    check("both Spice draws went to discard", deck.discard_pile.count(B.SPICE) == 2, deck.discard_pile)
    check("both real candidates went to discard too", set(deck.discard_pile) >= {"Grunt", "Ambusher"},
          deck.discard_pile)
    check("draw pile fully consumed", deck.draw_pile == [], deck.draw_pile)

    # 2. Picks the lower-cost% (easier) matchup between two genuinely different mobs.
    cache = M._scouted_pull_costpct_cache.setdefault("warrior", {})
    cache.clear()
    mod = M.CARD_SOURCE["warrior"]
    has_stance = M.HAS_STANCE["warrior"]
    max_hp = float(mod.WARRIOR_HP)
    costs = {}
    for name in T.MOB_NAMES:
        pattern, mob_hp = M._pattern_hp_for_mob("warrior", name)
        total = sum(max_hp - T._best_line(mod, has_stance, hand, pattern, mob_hp, max_hp)[2]
                    for hand in mod.ALL_HANDS)
        costs[name] = total / len(mod.ALL_HANDS)
    easiest = min(costs, key=costs.get)
    hardest = max(costs, key=costs.get)
    check("easiest != hardest (real spread exists)", easiest != hardest, costs)
    picked = BE._best_scouted_candidate("warrior", [easiest, hardest])
    check("picks the easier matchup", picked == easiest, (picked, easiest, hardest, costs))

    # 3. Reshuffle-on-empty still works when scouted through repeatedly.
    deck2 = B.LevelDeck.new(1, random.Random(5))
    rng2 = random.Random(5)
    seen = set()
    for _ in range(15):
        mob = BE.scouted_pull_from_deck("warrior", deck2, rng2)
        seen.add(mob)
    check("reshuffle-on-empty survives repeated scouted pulls", len(seen) > 0, seen)

    print(f"\n{len(failures)} failures" if failures else "\nAll direct checks passed")
    return not failures


def aggregate_sanity_check(class_name, strategy="food_only", trials=100, old_chain_trips=15, seed=7, verbose=True):
    """Compares run_solo_chain (real deck for Border crossings) against decay_stress_test
    (old rng-based crossings) using gold-PER-TURN, not gold-after-N-trips -- "trips" isn't a
    comparable unit (a trip's own length varies wildly by class and luck); decay_stress_test
    already computes its own gold_per_turn for exactly this reason (OPEN_QUESTIONS.md's "What
    a turn is," locked). run_solo_chain itself is turn-denominated (takes max_turns, not
    chain_trips) -- old_chain_trips only bounds the OLD _trip_chain-based baseline call, since
    that's still the old code's own API; the new side is driven for old["total_turns"] turns,
    the exact turn count the old side actually took, so both sides cover the same amount of
    real simulated playtime rather than merely a similar one. Expects the ratio in a similar
    ballpark, not exact."""
    old = M.decay_stress_test(class_name, strategy, random.Random(seed), max_turns=old_chain_trips)
    old_gold_per_turn = old["gold_per_turn"]
    max_turns = old["total_turns"]

    rng = random.Random(seed)
    total_gold_per_turn = 0.0
    deaths = 0
    for t in range(trials):
        final_gold, final_turns, died = 0, 0, False
        for alive, gold, xp, quests_completed, trainer_turn, turns in BE.run_solo_chain(
                class_name, strategy, rng, max_turns):
            final_gold, final_turns = gold, turns
            if not alive:
                died = True
        total_gold_per_turn += final_gold / final_turns if final_turns else 0.0
        if died:
            deaths += 1
    avg_gold_per_turn = total_gold_per_turn / trials

    if verbose:
        print(f"{class_name:12s} old: gold/turn={old_gold_per_turn:.3f} deaths={old['died_count']}   "
              f"new: avg_gold/turn={avg_gold_per_turn:.3f} deaths={deaths}/{trials}")
    return avg_gold_per_turn, deaths


if __name__ == "__main__":
    ok = run_direct_checks()
    print("\n=== Aggregate sanity check (single trial per class matching decay_stress_test's own shape) ===")
    for class_name in M.CARD_SOURCE:
        aggregate_sanity_check(class_name, trials=1, old_chain_trips=20, seed=1)
    raise SystemExit(0 if ok else 1)
