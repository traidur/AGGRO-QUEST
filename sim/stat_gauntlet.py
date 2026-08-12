"""Brute-force mob-shape search: sweeps every (dmg, block) combination for
all 3 rounds jointly, for every mob HP in HP_RANGE, computing exact
single-pull cost%/win-rate%/round-1-kill-rate per class for each
combination and writing one row per combination to stat_gauntlet.csv.

Block is capped at 0-2, matching what the real hand-designed roster has
always used (nothing in it ever goes above block=2) -- an earlier,
unconstrained version of this sweep (block up to 5) found candidates that
looked great on paper but turned out to only "work" via a low-HP one-shot
loophole (see CLASS_BALANCE_GUIDE.md's stat-gauntlet section for the full
story). Round-1-kill rate is tracked directly so one-shot risk can be
filtered as a hard constraint, not checked after the fact.

Not part of the permanent simulation (macro_sim.py doesn't import this) --
a queryable data generator, regenerate as needed rather than treat as
sacred (~2.5 minutes for the full sweep). Query the resulting CSV with
csv.DictReader afterward rather than reading it directly; see
pool_search.py for the next step (searching whole mob-pool combinations
against the chained diagnostic using this CSV's output as candidates).

Covers all 6 classes now (Rogue and Ranger added when this predated their
build). stats() also takes an explicit mob_type ('melee' or 'ranged'),
applied only to classes in RANGE_TAGGED (currently Wizard and Ranger --
the only two with a grants_range-style mechanic that actually reads
mob_type). Every other class's numbers are provably identical regardless
of mob_type, since their simulate() never looks at it. The full CSV sweep
below is still melee-only by default (doubling it to cover both mob_types
would double the ~2.5-minute runtime for a dimension only 2 of 6 classes
care about) -- for a specific ranged-mob candidate, call stats() directly
with mob_type='ranged' rather than regenerating the whole sweep."""
import csv
import itertools
import time

import condensed_cleric as C
import condensed_paladin as P
import condensed_ranger as G
import condensed_rogue as R
import condensed_trip as T
import condensed_warrior as W
import condensed_wizard as Z

CARD_SOURCE = {'warrior': W, 'wizard': Z, 'cleric': C, 'paladin': P, 'rogue': R, 'ranger': G}
HP_ATTR = {'warrior': 'WARRIOR_HP', 'wizard': 'WIZARD_HP', 'cleric': 'CLERIC_HP', 'paladin': 'PALADIN_HP',
           'rogue': 'ROGUE_HP', 'ranger': 'RANGER_HP'}
HAS_STANCE = {'warrior': True, 'wizard': False, 'cleric': False, 'paladin': False, 'rogue': False, 'ranger': False}
CLASSES = ['warrior', 'wizard', 'cleric', 'paladin', 'rogue', 'ranger']

# Ranger isn't locked into condensed_trip.py's permanent structures yet, so
# its 3-tuple requirement wouldn't otherwise be registered -- do it here so
# this module works standalone regardless of what the caller already set up.
T.register_class_for_testing('ranger', needs_range_tag=True)

# Classes whose simulate() unpacks a 3-tuple (atk, block, mob_type) instead
# of the plain 2-tuple -- structurally required for Wizard/Rogue/Ranger
# (Rogue's simulate() still unpacks mob_type even though it never reads it,
# leftover from an earlier iteration with a grants_range mechanic). Reuses
# condensed_trip.py's own set directly rather than keeping a second,
# drift-prone copy in sync by hand.
RANGE_TAGGED = T._RANGE_TAGGED_MOB_KEYS

DMG_RANGE = range(0, 6)
BLOCK_RANGE = range(0, 3)  # capped at 2, matching the real roster's ceiling
HP_RANGE = range(4, 13)


def stats(pattern, mob_hp, mob_type='melee'):
    out = {}
    for cls in CLASSES:
        mod = CARD_SOURCE[cls]
        has_stance = HAS_STANCE[cls]
        max_hp = float(getattr(mod, HP_ATTR[cls]))
        p = pattern if cls not in RANGE_TAGGED else [(a, b, mob_type) for a, b in pattern]
        costs, wins, r1kills = [], [], 0
        for hand in mod.ALL_HANDS:
            seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, p, mob_hp, max_hp)
            win, final_hp, final_rounds = T._simulate(mod, has_stance, seq, stance, p, mob_hp, max_hp)
            costs.append(max_hp - hp_left)
            wins.append(win)
            if win and final_rounds == 1:
                r1kills += 1
        out[cls] = (100 * (sum(costs) / len(costs)) / max_hp, 100 * sum(wins) / len(wins),
                    100 * r1kills / len(mod.ALL_HANDS))
    return out


def main():
    round_combos = list(itertools.product(DMG_RANGE, BLOCK_RANGE))
    total = len(HP_RANGE) * len(round_combos) ** 3
    print(f'{len(round_combos)} combos/round, {len(round_combos)**3} combos/HP, '
          f'{len(list(HP_RANGE))} HP values -> {total} total rows')

    t0 = time.time()
    with open('stat_gauntlet.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['hp', 'r1_dmg', 'r1_block', 'r2_dmg', 'r2_block', 'r3_dmg', 'r3_block']
                         + [f'{cls}_cost' for cls in CLASSES] + [f'{cls}_win' for cls in CLASSES]
                         + [f'{cls}_r1kill' for cls in CLASSES])
        rows_written = 0
        for hp in HP_RANGE:
            hp_t0 = time.time()
            for r1 in round_combos:
                for r2 in round_combos:
                    for r3 in round_combos:
                        pattern = [r1, r2, r3]
                        s = stats(pattern, hp)
                        row = [hp, r1[0], r1[1], r2[0], r2[1], r3[0], r3[1]]
                        row += [s[cls][0] for cls in CLASSES]
                        row += [s[cls][1] for cls in CLASSES]
                        row += [s[cls][2] for cls in CLASSES]
                        writer.writerow(row)
                        rows_written += 1
            print(f'hp={hp} done in {time.time()-hp_t0:.1f}s -- {rows_written} rows so far, '
                  f'{time.time()-t0:.1f}s elapsed')
    print(f'TOTAL TIME: {time.time()-t0:.1f}s, {rows_written} rows written to stat_gauntlet.csv')


if __name__ == '__main__':
    main()
