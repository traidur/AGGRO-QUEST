"""Same random-pool-search method as pool_search.py, generalized to target
a specific average-pulls-per-trip magnitude (not just minimize spread at
whatever difficulty the candidate shortlist happens to produce). Pool size
itself is randomized too (4-6 mobs), not fixed."""
import csv
import random
import time

import condensed_cleric as C
import condensed_paladin as P
import condensed_trip as T
import condensed_warrior as W
import condensed_wizard as Z

CARD_SOURCE = {'warrior': W, 'wizard': Z, 'cleric': C, 'paladin': P}
HP_ATTR = {'warrior': 'WARRIOR_HP', 'wizard': 'WIZARD_HP', 'cleric': 'CLERIC_HP', 'paladin': 'PALADIN_HP'}
HAS_STANCE = {'warrior': True, 'wizard': False, 'cleric': False, 'paladin': False}
CLASSES = ['warrior', 'wizard', 'cleric', 'paladin']

TARGET_PULLS = 3.0
TARGET_TOLERANCE = 0.4  # accept mean pulls within +/- this of TARGET_PULLS


def load_candidates_filtered(min_cost, max_cost, min_win=93.0):
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


def run_trip_pool(class_name, rng, pool, mob_defs, max_pulls=50):
    mod = CARD_SOURCE[class_name]
    has_stance = HAS_STANCE[class_name]
    hp = float(getattr(mod, HP_ATTR[class_name]))
    pulls = 0
    while hp > 0 and pulls < max_pulls:
        mob_name = rng.choice(pool)
        pattern, mob_hp = mob_defs[mob_name][class_name]
        hand = rng.choice(mod.ALL_HANDS)
        seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, pattern, mob_hp, hp)
        win, final_hp, final_rounds = T._simulate(mod, has_stance, seq, stance, pattern, mob_hp, hp)
        hp = final_hp
        pulls += 1
        if hp <= 0:
            break
    return pulls


def eval_pool(members, trials=300, seed=42):
    mob_defs = {}
    pool = []
    for i, (pattern, hp) in enumerate(members):
        name = f'm{i}'
        mob_defs[name] = dict(
            warrior=(pattern, hp), wizard=([(a, b, 'melee') for a, b in pattern], hp),
            cleric=(pattern, hp), paladin=(pattern, hp),
        )
        pool.append(name)
    results = {}
    for cls in CLASSES:
        rng = random.Random(seed)
        total = sum(run_trip_pool(cls, rng, pool, mob_defs) for _ in range(trials))
        results[cls] = total / trials
    return results


def main():
    candidates = load_candidates_filtered(min_cost=25.0, max_cost=45.0)
    print(f'{len(candidates)} candidates in the 25-45% cost / 93%+ win / 0% one-shot band')

    rng = random.Random(1)
    n_trials_search = 500
    hits = []  # pools whose mean lands in the target window, sorted by spread
    t0 = time.time()
    for i in range(n_trials_search):
        pool_size = rng.choice([4, 5, 6])
        members = rng.sample(candidates, pool_size)
        results = eval_pool(members, trials=300, seed=42)
        mean_pulls = sum(results.values()) / 4
        spread = max(results.values()) - min(results.values())
        if abs(mean_pulls - TARGET_PULLS) <= TARGET_TOLERANCE:
            hits.append((spread, mean_pulls, members, results))
        if (i + 1) % 100 == 0:
            best_spread = min((h[0] for h in hits), default=float('nan'))
            print(f'{i+1}/{n_trials_search} pools tested, {time.time()-t0:.1f}s elapsed, '
                  f'{len(hits)} in target window, best spread so far: {best_spread}')

    hits.sort(key=lambda x: x[0])
    print()
    print(f'=== Top 10 pools with mean pulls in [{TARGET_PULLS-TARGET_TOLERANCE}, {TARGET_PULLS+TARGET_TOLERANCE}] ===')
    for spread, mean_pulls, members, results in hits[:10]:
        print(f'spread={spread:.3f}  mean={mean_pulls:.2f}  size={len(members)}  {results}')
        for pattern, hp in members:
            print(f'    {pattern} hp={hp}')
        print()


if __name__ == '__main__':
    main()
