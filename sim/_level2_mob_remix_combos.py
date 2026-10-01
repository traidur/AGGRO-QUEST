"""For the 5 pinned Level 2 mob candidates (Ambusher, Enforcer, Scout,
Grunt, Raider), test every one of the 2^5=32 subsets (which candidates to
apply together, including none and all) and rank by total roster-wide
footprint. A per-mob stat (fixed_mob=X) only depends on mob X's own
pattern, never on what any other mob is doing, so each candidate's
per-mob delta is computed exactly once and reused across every combo that
includes it -- only the mixed-roster stat (draws from all 6 mobs at once)
needs recomputing per combination."""
import itertools
import random
import time

import condensed_trip as T

CANDIDATES = {
    "Ambusher": [(4, 0), (4, 1), (2, 0)],
    "Enforcer": [(5, 1), (3, 1), (4, 2)],
    "Scout": [(3, 0), (2, 0), (4, 0)],
    "Grunt": [(3, 0), (2, 2), (3, 0)],
    "Raider": [(3, 0), (4, 2), (5, 1)],
}
ORIGINALS = {name: T._RAW_MOBS[name] for name in CANDIDATES}
MOB_NAMES = list(CANDIDATES.keys())
TRIALS = 300


def rebuild_mobs():
    T.MOBS = {
        name: dict(
            warrior=(pattern, hp),
            wizard=([(a, b, T._MOB_TYPES.get(name, "melee")) for a, b in pattern], hp),
            cleric=(pattern, hp),
            paladin=(pattern, hp),
            rogue=([(a, b, T._MOB_TYPES.get(name, "melee")) for a, b in pattern], hp),
            ranger=([(a, b, T._MOB_TYPES.get(name, "melee")) for a, b in pattern], hp),
            runecaster=([(a, b, T._MOB_TYPES.get(name, "melee")) for a, b in pattern], hp),
            druid=(pattern, hp),
            necromancer=([(a, b, T._MOB_TYPES.get(name, "melee")) for a, b in pattern], hp),
        )
        for name, (pattern, hp) in T._RAW_MOBS.items()
    }
    T.MOB_NAMES = list(T.MOBS.keys())


def set_combo(active_names):
    for name, (orig_pattern, hp) in ORIGINALS.items():
        T._RAW_MOBS[name] = (CANDIDATES[name] if name in active_names else orig_pattern, hp)
    rebuild_mobs()


def measure_mixed(trials=TRIALS, seed=42):
    out = {}
    for lbl, fn in T.CLASSES:
        rng = random.Random(seed)
        mp, mw = [], []
        for _ in range(trials):
            p, w = fn(rng)
            mp.append(p)
            mw.append(w)
        out[lbl] = (sum(mp) / trials, sum(mw) / trials)
    return out


def measure_per_mob(mob_name, trials=TRIALS, seed=42):
    out = {}
    for lbl, fn in T.CLASSES:
        rng = random.Random(seed)
        pp, pw = [], []
        for _ in range(trials):
            p, w = fn(rng, fixed_mob=mob_name)
            pp.append(p)
            pw.append(w)
        out[lbl] = (sum(pp) / trials, sum(pw) / trials)
    return out


def main():
    t0 = time.time()

    print("Baseline (all 6 mobs original)...")
    set_combo(set())
    baseline_mixed = measure_mixed()
    baseline_per_mob = {name: measure_per_mob(name) for name in MOB_NAMES}
    print(f"  done in {time.time()-t0:.1f}s")

    print("Precomputing each candidate's own per-mob delta (independent of other mobs)...")
    t1 = time.time()
    active_per_mob = {}
    per_mob_delta = {}
    for name in MOB_NAMES:
        set_combo({name})
        active_per_mob[name] = measure_per_mob(name)
        per_mob_delta[name] = sum(
            abs(active_per_mob[name][lbl][1] - baseline_per_mob[name][lbl][1])
            for lbl in active_per_mob[name]
        )
        print(f"  {name:10s} per-mob-wins footprint contribution = {per_mob_delta[name]:.2f}")
    print(f"  done in {time.time()-t1:.1f}s")
    print()

    print("Testing all 32 combinations (mixed-roster recompute per combo)...")
    t2 = time.time()
    results = []
    for k in range(0, len(MOB_NAMES) + 1):
        for combo in itertools.combinations(MOB_NAMES, k):
            combo_set = set(combo)
            set_combo(combo_set)
            mixed = measure_mixed()
            mixed_fp = sum(
                abs(mixed[lbl][0] - baseline_mixed[lbl][0]) + abs(mixed[lbl][1] - baseline_mixed[lbl][1])
                for lbl in mixed
            )
            total_fp = mixed_fp + sum(per_mob_delta[name] for name in combo_set)
            results.append((total_fp, combo, mixed_fp))
            label = "+".join(combo) if combo else "(none)"
            print(f"{label:40s} total_footprint={total_fp:7.2f}  (mixed={mixed_fp:.2f})")
    print(f"  done in {time.time()-t2:.1f}s")

    set_combo(set())  # restore originals in this process's module state
    results.sort(key=lambda r: r[0])
    print()
    print(f"TOTAL TIME: {time.time()-t0:.1f}s")
    print("=== Ranked least-disruptive to most-disruptive combination ===")
    for fp, combo, mixed_fp in results:
        label = "+".join(combo) if combo else "(none)"
        print(f"footprint={fp:7.2f}  (mixed={mixed_fp:6.2f})  {label}")


if __name__ == "__main__":
    main()
