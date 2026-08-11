"""Random pool search scored directly on decay-spread (max-min of each
class's avg worst-decay-stage over a 20-trip chain), not on pulls-survived
spread. Built after finding the two aren't well correlated -- the
pulls-tightest pool wasn't even top-3 on decay. Reuses the same candidate
shortlist source as pool_search.py (stat_gauntlet.csv, Standard-tier cost
band) since this targets the same ~5-pulls difficulty level, just a
different, more expensive scoring function (decay_stress_test instead of
a simple reckless pull-chain, because decay only exists inside the full
quest/bag/food macro-loop machinery)."""
import csv
import random
import time

import condensed_trip as T
import macro_sim as M

CLASSES = ['warrior', 'wizard', 'cleric', 'paladin']
ANCHOR = ([(2, 0), (3, 2), (3, 0)], 7)


def load_candidates(min_cost=15.0, max_cost=32.0, min_win=93.0):
    out = []
    with open('stat_gauntlet.csv') as f:
        reader = csv.DictReader(f)
        for row in reader:
            wins = [float(row[f'{c}_win']) for c in CLASSES]
            r1kills = [float(row[f'{c}_r1kill']) for c in CLASSES]
            if min(wins) < min_win or max(r1kills) > 0.0:
                continue
            costs = [float(row[f'{c}_cost']) for c in CLASSES]
            if not (min_cost <= min(costs) and max(costs) <= max_cost):
                continue
            pattern = [(int(row['r1_dmg']), int(row['r1_block'])),
                       (int(row['r2_dmg']), int(row['r2_block'])),
                       (int(row['r3_dmg']), int(row['r3_block']))]
            out.append((pattern, int(row['hp'])))
    return out


def eval_pool_decay(members, trials, seed=42):
    pool_def = {}
    for i, (pattern, hp) in enumerate(members):
        pool_def[f'm{i}'] = (pattern, hp)
    for name, (pattern, hp) in pool_def.items():
        T.MOBS[name] = dict(warrior=(pattern, hp), wizard=([(a, b, 'melee') for a, b in pattern], hp),
                             cleric=(pattern, hp), paladin=(pattern, hp))
    T.MOB_TIERS['standard'] = list(pool_def.keys())

    results = {}
    for cls in CLASSES:
        rng = random.Random(seed)
        totals = [M.decay_stress_test(cls, 'food_only', rng, chain_trips=20)['worst_decay_stage']
                  for _ in range(trials)]
        results[cls] = sum(totals) / len(totals)
    return results


def main():
    candidates = load_candidates()
    print(f'{len(candidates)} candidates available')

    rng = random.Random(7)
    n_search = 120
    search_trials = 20
    best = []
    t0 = time.time()
    for i in range(n_search):
        picks = rng.sample(candidates, 4)
        members = [ANCHOR] + picks
        results = eval_pool_decay(members, trials=search_trials, seed=42)
        spread = max(results.values()) - min(results.values())
        best.append((spread, members, results))
        if (i + 1) % 20 == 0:
            print(f'{i+1}/{n_search} pools tested, {time.time()-t0:.1f}s elapsed, '
                  f'best spread so far: {min(b[0] for b in best):.3f}')

    best.sort(key=lambda x: x[0])
    print()
    print('=== Top 8 pools by decay-spread (search pass, low trial count) ===')
    for spread, members, results in best[:8]:
        print(f'decay_spread={spread:.3f}  {results}')
        for pattern, hp in members:
            print(f'    {pattern} hp={hp}')
        print()


if __name__ == '__main__':
    main()
