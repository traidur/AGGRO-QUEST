"""
Measures the real opportunity cost of a quest's `required` loot count, in
actual pulls and trips spent, isolated from any other quest competing for
bag room or turns. Answers "how much does asking for N loot instead of 3
actually cost the player" empirically, instead of assuming pulls scale
1-for-1 with `required` (they don't: flees, deaths/corpse-recovery pulls,
and food-driven bag-deadlock evictions all add overhead on top of the N
winning pulls actually needed).

Isolation method: monkey-patches macro_sim.QUESTS/NODES/ACTIVE_QUEST_COUNT
to a single quest of the given `required`, so nothing else is competing for
the bag or the trip's turn budget -- this measures the pure per-quest-size
cost curve, the input the reward formula should be built from. (Multi-quest
competition, i.e. how one big quest slows down others sharing the log, is a
separate question layered on top of this baseline, not what this measures.)

Kept as a permanent, rerunnable tool (same convention as stat_gauntlet.py /
pool_search.py) -- future quest curation should re-derive against this
whenever `required` options or the mob roster change, not eyeball a formula.
"""
import random
import macro_sim as M

CLASSES = ["warrior", "cleric", "wizard", "paladin"]


def measure_cost(required, trials_per_class=50, chain_trips=50, seed=42, strategy="food_only"):
    """Runs an isolated single-quest-type chain per class and returns the
    average pulls and trips actually spent per completed quest, plus flee/
    death overhead, pooled across all four classes (design must stay
    class-agnostic, so the number we tune the formula against is the
    cross-class average, not any one class's number)."""
    orig_quests, orig_nodes, orig_count = M.QUESTS, M.NODES, M.ACTIVE_QUEST_COUNT
    M.QUESTS = {"Test Loot": dict(required=required, base_xp=required, gold_ladder=[0, 0, 0, 0])}
    M.NODES = {"test_node": ("standard", "Test Loot")}
    M.ACTIVE_QUEST_COUNT = 1
    try:
        total_pulls = 0
        total_completions = 0
        total_deaths = 0
        total_trips = 0
        stage_counts = [0, 0, 0, 0]  # completions paid out at Gold/Silver/Bronze/nothing
        instances = []  # (trip_span, stage_at_payout) for every completed instance
        for cls in CLASSES:
            for t in range(trials_per_class):
                rng = random.Random(f"{seed}-{required}-{cls}-{t}")
                pulls_this_chain = 0
                completions_this_chain = 0
                deaths_this_chain = 0
                prev_decay_stage = 0
                instance_trip_count = 0
                for trip_num, result, gold, xp, decay_stage, corpse_node, quests_completed in M._trip_chain(
                        cls, strategy, rng):
                    pulls_this_chain += result["pulls"]
                    completions_this_chain += quests_completed
                    if result["died"]:
                        deaths_this_chain += 1
                    instance_trip_count += 1
                    if quests_completed:
                        stage_counts[prev_decay_stage] += 1
                        instances.append((instance_trip_count, prev_decay_stage))
                        instance_trip_count = 0
                    prev_decay_stage = decay_stage["Test Loot"]
                    if trip_num >= chain_trips:
                        break
                total_pulls += pulls_this_chain
                total_completions += completions_this_chain
                total_deaths += deaths_this_chain
                total_trips += chain_trips
    finally:
        M.QUESTS, M.NODES, M.ACTIVE_QUEST_COUNT = orig_quests, orig_nodes, orig_count

    instances.sort(key=lambda pair: pair[0])
    half = len(instances) // 2
    fast_half = instances[:half] if half else instances
    fast_stage_counts = [0, 0, 0, 0]
    for _, stage in fast_half:
        fast_stage_counts[stage] += 1

    return dict(
        required=required,
        pulls_per_completion=total_pulls / total_completions if total_completions else float("inf"),
        completions_per_trip=total_completions / total_trips,
        trips_per_completion=total_trips / total_completions if total_completions else float("inf"),
        deaths_per_1000_trips=1000 * total_deaths / total_trips,
        stage_pct=[100 * c / total_completions for c in stage_counts] if total_completions else [0, 0, 0, 0],
        fast_half_trip_span=sum(t for t, _ in fast_half) / len(fast_half) if fast_half else float("nan"),
        fast_half_stage_pct=[100 * c / len(fast_half) for c in fast_stage_counts] if fast_half else [0, 0, 0, 0],
    )


if __name__ == "__main__":
    print(f"=== Quest cost gauntlet: pulls actually spent per completed quest, by required count ===")
    print(f"{'required':>8s} {'pulls/completion':>17s} {'trips/completion':>17s} {'deaths/1000 trips':>18s}")
    rows = []
    for required in [2, 3, 4, 5]:
        r = measure_cost(required)
        rows.append(r)
        print(f"{r['required']:8d} {r['pulls_per_completion']:17.2f} {r['trips_per_completion']:17.2f} {r['deaths_per_1000_trips']:18.2f}")

    print()
    print("=== overhead beyond the raw N winning pulls ===")
    for r in rows:
        overhead = r["pulls_per_completion"] - r["required"]
        pct = 100 * overhead / r["required"]
        print(f"  required={r['required']}: {r['pulls_per_completion']:.2f} actual pulls "
              f"({overhead:+.2f}, {pct:+.1f}% over the {r['required']} raw wins needed)")

    print()
    print("=== what decay stage the quest's OWN reward has already reached by the time it's turned in ===")
    print(f"{'required':>8s} {'Gold':>7s} {'Silver':>7s} {'Bronze':>7s} {'nothing':>8s}")
    for r in rows:
        g, s, b, n = r["stage_pct"]
        print(f"{r['required']:8d} {g:6.1f}% {s:6.1f}% {b:6.1f}% {n:7.1f}%")

    print()
    print("=== the FASTER HALF of completions only (by trips spent on that instance) ===")
    print(f"{'required':>8s} {'avg trips (fast half)':>22s} {'Gold':>7s} {'Silver':>7s} {'Bronze':>7s} {'nothing':>8s}")
    for r in rows:
        g, s, b, n = r["fast_half_stage_pct"]
        print(f"{r['required']:8d} {r['fast_half_trip_span']:22.2f} {g:6.1f}% {s:6.1f}% {b:6.1f}% {n:7.1f}%")
