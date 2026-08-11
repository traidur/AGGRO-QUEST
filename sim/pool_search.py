"""Random pool search: sample random 4-mob combinations from the
Standard-tier-appropriate candidate set (+ the fixed Balanced Anchor),
test each as a whole pool against the chained no-recovery survivability
diagnostic, and keep whichever pools come out most even across all four
classes. Not per-class-assigned -- these are just varied shapes, tested
purely on their cumulative effect."""
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

ANCHOR = ('Anchor', (2, 0), (3, 2), (3, 0), 7)


def load_candidates():
    out = []
    with open('stat_gauntlet.csv') as f:
        reader = csv.DictReader(f)
        for row in reader:
            wins = [float(row[f'{c}_win']) for c in CLASSES]
            r1kills = [float(row[f'{c}_r1kill']) for c in CLASSES]
            if min(wins) < 93.0 or max(r1kills) > 0.0:
                continue
            costs = [float(row[f'{c}_cost']) for c in CLASSES]
            if not (15.0 <= min(costs) and max(costs) <= 32.0):
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
    # members: list of (pattern, hp)
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
    candidates = load_candidates()
    print(f'{len(candidates)} candidates available for random pool sampling')
    anchor_member = (list(ANCHOR[1:4]), ANCHOR[4])

    rng = random.Random(1)
    n_trials_search = 400
    best = []  # list of (spread, members, results)
    t0 = time.time()
    for i in range(n_trials_search):
        picks = rng.sample(candidates, 4)
        members = [anchor_member] + picks
        results = eval_pool(members, trials=300, seed=42)
        spread = max(results.values()) - min(results.values())
        best.append((spread, members, results))
        if (i + 1) % 50 == 0:
            print(f'{i+1}/{n_trials_search} pools tested, {time.time()-t0:.1f}s elapsed, '
                  f'best spread so far: {min(b[0] for b in best):.3f}')

    best.sort(key=lambda x: x[0])
    print()
    print('=== Top 10 most-even pools found ===')
    for spread, members, results in best[:10]:
        print(f'spread={spread:.3f}  {results}')
        for pattern, hp in members:
            print(f'    {pattern} hp={hp}')
        print()


if __name__ == '__main__':
    main()
