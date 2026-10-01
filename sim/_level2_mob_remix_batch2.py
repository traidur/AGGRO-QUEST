"""Quick individual footprint check (same lighter diagnostic as
_level2_mob_remix_search.py's search pass, not full_report()) for 4
user-specified candidate patterns -- these aren't found by permutation
search, they're hand-picked, so this just measures each one's disruption
individually before any combined verification happens."""
import random
import time

import condensed_trip as T

CANDIDATES = {
    "Scout": [(3, 0), (2, 0), (4, 0)],
    "Grunt": [(3, 0), (2, 2), (3, 0)],
    "Enforcer": [(5, 1), (3, 1), (4, 2)],
    "Raider": [(3, 0), (4, 2), (5, 1)],
}
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
    for mob_name, new_pattern in CANDIDATES.items():
        orig_pattern, hp = T._RAW_MOBS[mob_name]
        before = measure(mob_name)

        T._RAW_MOBS[mob_name] = (new_pattern, hp)
        rebuild_mobs()
        after = measure(mob_name)
        fp = footprint(before, after)
        print(f"{mob_name:10s} {orig_pattern} -> {new_pattern}  footprint={fp:.2f}")

        T._RAW_MOBS[mob_name] = (orig_pattern, hp)
        rebuild_mobs()
    print(f"TOTAL TIME: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
