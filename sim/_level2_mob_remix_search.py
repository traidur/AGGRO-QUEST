"""One-off: for each of the 6 locked Standard mobs, try every round-order
permutation of its own (dmg, block) triples (same total damage/Block/HP,
just resequenced -- the safest kind of change) and measure roster-wide
disruption, matching the "total footprint across the whole roster"
methodology CLASS_BALANCE_GUIDE.md used for Scout's addition.

Deliberately NOT using condensed_trip.full_report() for the search pass --
timed at ~276s per call (trials=1500), which would make a ~30-candidate
sweep take hours. Swapping one mob's pattern leaves the other 5 mobs'
per-mob stats byte-identical (same seed, same inputs), so this only
recomputes the mixed-roster draw (all 9 classes) and the one varied mob's
own per-mob stats, at a lower trial count -- a rough ranking signal, not a
final number. The winning candidate gets a full-trial full_report()
re-verification afterward before anything is treated as locked.
"""
import itertools
import random
import time

import condensed_trip as T

MOB_NAMES = list(T._RAW_MOBS.keys())
SEARCH_TRIALS = 300


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


def measure(mob_name, trials=SEARCH_TRIALS, seed=42):
    """Returns {class_label: (mixed_pulls, mixed_wins, mob_pulls, mob_wins)}."""
    out = {}
    for lbl, fn in T.CLASSES:
        rng = random.Random(seed)
        mp, mw = [], []
        for _ in range(trials):
            p, w = fn(rng)
            mp.append(p)
            mw.append(w)
        rng = random.Random(seed)
        pp, pw = [], []
        for _ in range(trials):
            p, w = fn(rng, fixed_mob=mob_name)
            pp.append(p)
            pw.append(w)
        out[lbl] = (sum(mp) / trials, sum(mw) / trials, sum(pp) / trials, sum(pw) / trials)
    return out


def footprint(before, after):
    total = 0.0
    for lbl in before:
        bmp, bmw, bpp, bpw = before[lbl]
        amp, amw, app, apw = after[lbl]
        total += abs(amp - bmp) + abs(amw - bmw) + abs(apw - bpw)
    return total


def main():
    t0 = time.time()
    print("Baselines (per varied mob, since mixed-roster baseline also depends on which mob is being swapped)...")
    baselines = {mob_name: measure(mob_name) for mob_name in MOB_NAMES}
    print(f"  done in {time.time()-t0:.1f}s")
    print()

    results = []
    for mob_name in MOB_NAMES:
        orig_pattern, hp = T._RAW_MOBS[mob_name]
        seen = set()
        for perm in itertools.permutations(orig_pattern):
            if perm == tuple(orig_pattern) or perm in seen:
                continue
            seen.add(perm)

            t1 = time.time()
            T._RAW_MOBS[mob_name] = (list(perm), hp)
            rebuild_mobs()
            after = measure(mob_name)
            fp = footprint(baselines[mob_name], after)
            results.append((fp, mob_name, orig_pattern, list(perm), hp))
            print(f"{mob_name:10s} {orig_pattern} -> {list(perm)}  footprint={fp:.2f}  ({time.time()-t1:.1f}s)")

        T._RAW_MOBS[mob_name] = (orig_pattern, hp)
        rebuild_mobs()

    results.sort(key=lambda r: r[0])
    print()
    print(f"TOTAL TIME: {time.time()-t0:.1f}s")
    print("=== Ranked least-disruptive to most-disruptive ===")
    for fp, mob_name, orig, perm, hp in results:
        print(f"footprint={fp:6.2f}  {mob_name:10s} hp={hp}  {orig} -> {perm}")


if __name__ == "__main__":
    main()
