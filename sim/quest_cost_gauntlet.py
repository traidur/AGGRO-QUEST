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


def measure_cost(required, trials_per_class=50, chain_trips=50, seed=42, strategy="food_only",
                  tier="standard", classes=None, zone=1):
    """Runs an isolated single-quest-type chain per class and returns the
    average pulls and trips actually spent per completed quest, plus flee/
    death overhead, pooled across the given classes (design must stay
    class-agnostic, so the number we tune the formula against is the
    cross-class average, not any one class's number).

    tier: the isolated test node's tier -- "standard" (default, Level 1 content) or
    M.LEVEL2_TIER (the real 18-Standard:3-Elite pool, for deriving Zone 3/4's rewards).
    classes: which classes to pool across -- defaults to the original 4-class CLASSES subset;
    pass M.LEVEL2_CLASSES for Level 2 derivation (only classes with a real locked slate).
    zone: which Zone the isolated test node belongs to -- matters because _trip_chain now
    handles real, dynamic Level 2 leveling on its own (mandatory grants automatically at
    Level 2 XP, purchased upgrades get bought at the Trainer as Gold allows) -- Zone 2 is a
    Trainer zone, Zone 1 isn't, so this needs to be 2 for a Level 2 derivation to actually let
    the hero buy anything, not just receive the free mandatory upgrade. Defaults to 1,
    matching this tool's original behavior exactly when tier/classes/zone are all left at
    their defaults -- verified no-op for the existing Level 1 derivation."""
    if classes is None:
        classes = CLASSES
    orig_quests, orig_nodes, orig_count = M.QUESTS, M.NODES, M.ACTIVE_QUEST_COUNT
    orig_node_zone = M.NODE_ZONE
    orig_level2_stub, orig_threshold = M.LEVEL2_QUESTS, M.LEVEL2_XP_THRESHOLD
    test_quest = {"Test Loot": dict(required=required, base_xp=required, gold_ladder=[0, 0, 0, 0])}
    M.QUESTS = test_quest
    # _trip_chain's Level 1 starter batch (2026-08-21) is deliberately non-replenishing, but
    # this tool needs the same "Test Loot" quest redrawn every completion to gather repeated
    # trials in one chain -- patching LEVEL2_QUESTS to an equal-content dict AND dropping
    # LEVEL2_XP_THRESHOLD below 0 forces _trip_chain to always pick the (replenishing)
    # LEVEL2_QUESTS branch, sidestepping the starter-batch mechanic entirely, which isn't
    # what this isolated per-quest-size measurement is testing. Deliberately a SEPARATE dict
    # object (dict(test_quest), not test_quest itself) -- _trip_chain's `pool is QUESTS` branch
    # check is an identity check, and patching both names to literally the same object made it
    # always true regardless of which pool was actually selected, silently forcing the
    # never-replenish branch and leaving active_quests empty forever after the first completion
    # (a real regression caught 2026-08-21 once the "zero quests -> travel toward a real Zone"
    # fallback logic made that state actually consequential instead of silently harmless).
    M.LEVEL2_QUESTS = dict(test_quest)
    M.LEVEL2_XP_THRESHOLD = -1
    # Isolation also requires the pickup/fallback-travel Zone sets to match this test's single
    # synthetic Zone -- otherwise a hero with an empty log (a real, expected state between
    # completions before this fix) tries to travel toward the real Zone 3/4 map chasing
    # LEVEL2_QUEST_ZONES, burning pulls on real Border Node crossings unrelated to what this
    # tool measures.
    orig_l1_zones, orig_l2_zones = M.LEVEL1_QUEST_ZONES, M.LEVEL2_QUEST_ZONES
    M.LEVEL1_QUEST_ZONES = M.LEVEL2_QUEST_ZONES = {zone}
    # Same reasoning for TRAINER_ZONES: if a mandatory-upgrade class hasn't picked one up yet
    # mid-test (plausible, since LEVEL2_XP_THRESHOLD is forced negative above), the empty-quest
    # fallback would otherwise prioritize traveling toward the real Zone 2/4 Trainer instead of
    # this test's synthetic Zone -- belt-and-suspenders, even though the fix above should mean
    # active_quests never actually goes empty in practice.
    orig_trainer_zones = M.TRAINER_ZONES
    M.TRAINER_ZONES = {zone}
    M.NODES = {"test_node": (tier, "Test Loot")}
    M.NODE_ZONE = {"test_node": zone}  # a single Zone, no Border Node crossing possible or
    # needed for a genuinely isolated single-node test -- pre-existing gap (not patched at all
    # before 2026-08-20) surfaced once run_one_trip's routing started reading NODE_ZONE directly.
    M.ACTIVE_QUEST_COUNT = 1
    try:
        total_pulls = 0
        total_completions = 0
        total_deaths = 0
        total_trips = 0
        stage_counts = [0, 0, 0, 0]  # completions paid out at Gold/Silver/Bronze/nothing
        instances = []  # (trip_span, stage_at_payout) for every completed instance
        for cls in classes:
            for t in range(trials_per_class):
                rng = random.Random(f"{seed}-{required}-{cls}-{t}")
                pulls_this_chain = 0
                completions_this_chain = 0
                deaths_this_chain = 0
                prev_decay_stage = 0
                instance_trip_count = 0
                for trip_num, result, gold, xp, decay_stage, corpse_node, quests_completed, trainer_turn in M._trip_chain(
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
        M.NODE_ZONE = orig_node_zone
        M.LEVEL2_QUESTS, M.LEVEL2_XP_THRESHOLD = orig_level2_stub, orig_threshold
        M.LEVEL1_QUEST_ZONES, M.LEVEL2_QUEST_ZONES = orig_l1_zones, orig_l2_zones
        M.TRAINER_ZONES = orig_trainer_zones

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
