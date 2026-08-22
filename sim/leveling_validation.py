"""
Validation harness for the hero leveling curve (see LEVELING_GUIDE.md) -- the two checks that
guide requires before any proposed level-up numbers get locked: cost% (single-pull risk) and
pulls-before-death (multi-pull endurance), both computed against the *level-appropriate* mob
mix rather than a uniform draw.

Kept as a permanent, rerunnable tool because both checks need to be re-run every time a new
level's card/HP numbers are proposed, not just once -- same reason stat_gauntlet.py and
class_mob_matchup_chart.py are permanent rather than one-off scripts.

**Why a weighted pool instead of reusing condensed_trip.py's existing run_trip_<class>
functions directly:** those draw via `rng.choice(MOB_NAMES)`, uniform across the 6 Standard
mobs only -- Elites were never wired into that draw. That's implicitly a Level 1 number
already. This module builds the mob pool explicitly per level, matching the real locked deck
composition (OPEN_QUESTIONS.md's "Zone-node mob dealing" section): Level 1 = 6 Standard mobs
only; Level 2 = the same 6 Standard mobs plus the 3 Elites, weighted 3:1 by literally
duplicating each mob's (pattern, hp) entry in the pool the same number of times its card
appears in the real physical deck (3 copies each Standard, 1 copy each Elite) -- so a plain
`rng.choice(pool)` reproduces the real draw odds with no separate weights array needed.

**Known limitation, carried over from every other tool that touches Elites so far:** the Elite
trio's stats (Bulwark/Berserker/Warlord, HP=12 each) are the *solo* single-hero baseline --
CLASS_BALANCE_GUIDE.md's "Elite trio, derived" section is explicit this hasn't been
re-validated for the multi-hero Party Pull math yet. Any number here should be re-checked once
that re-derivation happens, not treated as permanently fixed.

**`leveled_kit`, the piece that lets a leveled deck use every existing tool unchanged.** A
leveled kit is never additive (LEVELING_GUIDE.md's "1-for-1 card swap or in-place numeric
bump" rule) -- it's still exactly 6 cards, just with one or more swapped for an upgraded
replacement. Every diagnostic in this codebase (damage_floor_ceiling, this module's own
cost_pct_for_level/win_rate_for_level/pulls_before_death, survivability_chart, etc.) reads a
class module's CARDS/DECK/ALL_HANDS fresh on every call and takes the module itself as an
argument -- so a leveled kit doesn't need its own parallel copy of any tool. It only needs a
safe way to make a real class module's globals *temporarily* reflect the swap, run whatever
existing tools against it, then restore the real Level 1 kit exactly -- a class's locked
kit must never come out of a test run altered, even if the test raises partway through.
"""
import contextlib
import itertools
import random
import condensed_trip as T


@contextlib.contextmanager
def leveled_kit(mod, swaps):
    """swaps: {old_card_name: (new_card_name, new_card_dict)}. Removes old_card_name from
    mod.CARDS, inserts new_card_name with new_card_dict's values in its place, and rebuilds
    mod.DECK/mod.ALL_HANDS to match -- exactly the reskin+retune shape LEVELING_GUIDE.md
    calls for, never a bigger or smaller deck. Restores the original CARDS/DECK/ALL_HANDS on
    exit no matter what, including if the code inside the `with` block raises, so mod's real
    Level 1 kit is never left corrupted.

    Usage: with leveled_kit(W, {"Shield Block": ("Shield Bash", dict(G=(2, 5), C=(3, 2), ...))}):
               ceiling, floor = T.damage_floor_ceiling(W, True, "warrior", W.WARRIOR_HP)
           # W.CARDS is back to the real, locked Level 1 kit here

    DECK is rebuilt by substituting old_name -> new_name *in the original deck's own order and
    membership*, not by taking every key currently in mod.CARDS. Two real bugs this fixes,
    found together 2026-08-21 while building the Class Trainer:
    (1) Some classes' CARDS dict legitimately holds more entries than DECK (Necromancer's
        "Boneguard's Offering (Boosted)", an alternate-play variant its own custom orderings()
        reads directly, never a real 7th deck card). Rebuilding from list(mod.CARDS.keys())
        wholesale silently pulled that extra entry into DECK/ALL_HANDS even with an empty
        swaps dict -- caught on a real, first-ever call of leveled_kit on Necromancer (one of
        the 3 classes with no Level 2 slate yet, so never swept during any earlier leveling
        pass) -- gold dropped from a real ~92 to 3 and produced a genuine death, on an
        intended no-op.
    (2) `del mod.CARDS[old_name]; mod.CARDS[new_name] = new_card` always inserts new_name at
        the *end* of dict order (Python dict semantics), regardless of where old_name used to
        sit -- so list(mod.CARDS.keys()) silently moved every swapped card to the back of
        DECK/ALL_HANDS' combination order, for every class, on every real (non-empty) swap
        this whole project has ever run. Substituting in place instead keeps a swapped card
        exactly where it always sat."""
    old_cards = dict(mod.CARDS)
    old_deck = list(mod.DECK)
    old_hands = list(mod.ALL_HANDS)
    try:
        for old_name, (new_name, new_card) in swaps.items():
            del mod.CARDS[old_name]
            mod.CARDS[new_name] = new_card
        rename = {old_name: new_name for old_name, (new_name, _) in swaps.items()}
        mod.DECK[:] = [rename.get(name, name) for name in old_deck]
        mod.ALL_HANDS[:] = list(itertools.combinations(mod.DECK, 4))
        yield mod
    finally:
        mod.CARDS.clear()
        mod.CARDS.update(old_cards)
        mod.DECK[:] = old_deck
        mod.ALL_HANDS[:] = old_hands

def sweep_purchased_candidate(mod, has_stance, mob_key, max_hp, mandatory_swap,
                               candidate_old_name, candidate_variants,
                               L1_cost, L1_win, L1_pulls, level=2, trials=1500):
    """The one correct way to sweep a purchased-upgrade candidate's numbers, per
    LEVELING_GUIDE.md's Step 3 -- structurally enforces the mandatory-only baseline that's
    been violated four separate times already despite being written down in prose twice
    (Warrior's Dominate-vs-Heavy-Swing, Cleric's Void Storm/Void Mark, Rogue's Relentless
    Ambush AND Backstab and Dodge, all in this same project). Prose alone did not stop this
    from recurring -- this function exists to make the mistake structurally harder, not just
    better-explained.

    mandatory_swap must be EXACTLY the single already-locked mandatory upgrade's swap entry
    ({old_name: (new_name, new_card)}, len == 1). Raises ValueError otherwise -- so a swap
    dict that's grown to include a previously-locked *purchased* upgrade (the exact shape of
    every past incident: copy-pasting the last candidate's swap dict and adding the new one
    to it, instead of starting fresh from mandatory-only each time) fails loudly instead of
    silently producing contaminated numbers. Never build mandatory_swap by extending a
    previous candidate's swap dict -- always construct it fresh, containing only the
    mandatory upgrade, no matter how many purchased upgrades are already locked.

    candidate_variants: list of (label, card_dict) pairs to sweep for candidate_old_name
    (label is just a display string, e.g. "3/5" or "dmg=4"; card_dict's own "name" isn't
    read here -- pass the candidate's own new display name via candidate_old_name's paired
    swap if you want it renamed, same as any other leveled_kit swap).

    Prints a cost/win/pulls-margin table, one row per variant, and returns the raw numbers as
    a list of (label, cost_margin, win_margin, pulls_margin) tuples."""
    if len(mandatory_swap) != 1:
        raise ValueError(
            f"mandatory_swap must contain exactly the one locked mandatory upgrade, got "
            f"{len(mandatory_swap)} entries: {list(mandatory_swap.keys())}. This is exactly "
            f"the contamination bug LEVELING_GUIDE.md's Step 3 warns about -- every "
            f"purchased-upgrade candidate must be swept against mandatory-only, never a kit "
            f"that already includes another purchased upgrade, even one that's already "
            f"locked. Build mandatory_swap fresh, don't extend a previous candidate's dict.")
    results = []
    print(f"{'variant':>10s}{'cost_marg':>11s}{'win_marg':>10s}{'pulls_marg':>12s}")
    for label, card_dict in candidate_variants:
        swaps = dict(mandatory_swap)
        swaps[candidate_old_name] = (candidate_old_name, card_dict)
        with leveled_kit(mod, swaps) as leveled:
            cost = cost_pct_for_level(leveled, has_stance, max_hp, mob_key, level)
            win = win_rate_for_level(leveled, has_stance, max_hp, mob_key, level)
            pulls = pulls_before_death(leveled, has_stance, max_hp, mob_key, level, trials=trials)
        cost_m = L1_cost - cost
        win_m = win - L1_win
        pulls_m = pulls - L1_pulls
        results.append((label, cost_m, win_m, pulls_m))
        print(f"{label:>10s}{cost_m:11.1f}{win_m:10.1f}{pulls_m:12.2f}")
    return results


ELITE_MELEE = {
    "Bulwark":   [(3, 1), (4, 0), (6, 0)],
    "Berserker": [(6, 0), (6, 0), (3, 0)],
    "Warlord":   [(5, 0), (4, 0), (5, 0)],
}
ELITE_HP = 12


def _elite_pattern(mob_key, name):
    pat = ELITE_MELEE[name]
    if mob_key in T._RANGE_TAGGED_MOB_KEYS:
        return [(a, b, "melee") for a, b in pat]
    return pat


def mob_pool_for_level(mob_key, level):
    """Returns a flat list of (pattern, mob_hp) tuples, one entry per physical card copy --
    level 1: 3 copies each of the 6 Standard mobs (18 entries). level 2: the same 18, plus 1
    copy each of the 3 Elites (21 entries total). Matches OPEN_QUESTIONS.md's locked Tier 1
    deck composition exactly (Spice cards excluded -- not combat, irrelevant to this check)."""
    pool = []
    for mob_name in T.MOB_NAMES:
        pattern, mob_hp = T.MOBS[mob_name][mob_key]
        pool.extend([(pattern, mob_hp)] * 3)
    if level >= 2:
        for name in ELITE_MELEE:
            pool.append((_elite_pattern(mob_key, name), ELITE_HP))
    return pool


def cost_pct_for_level(mod, has_stance, max_hp, mob_key, level):
    """Average HP cost%, across every hand, weighted by the level's real mob pool -- matches
    class_mob_matchup_chart.py's per-mob cost% formula, just averaged across a weighted pool
    of mobs instead of a single one."""
    pool = mob_pool_for_level(mob_key, level)
    total_cost = 0.0
    for pattern, mob_hp in pool:
        for hand in mod.ALL_HANDS:
            seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, pattern, mob_hp, max_hp)
            total_cost += (max_hp - hp_left)
    n = len(pool) * len(mod.ALL_HANDS)
    return 100 * (total_cost / n) / max_hp


def win_rate_for_level(mod, has_stance, max_hp, mob_key, level):
    """Offensive output: every hand against every mob in the level's real, weighted pool
    (same pool cost_pct_for_level uses), counting the fraction that actually kill the mob
    within 3 rounds versus the fraction that don't (loss or flee) -- direct, real-content
    measure of "how often does this class actually finish the fight," not a synthetic-dummy
    proxy. This is the metric win rate is actually right for: cost% answers "how risky was
    this," win rate answers "how often did it succeed" -- two different, both real questions,
    neither one a stand-in for the other."""
    pool = mob_pool_for_level(mob_key, level)
    wins = 0
    for pattern, mob_hp in pool:
        for hand in mod.ALL_HANDS:
            seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, pattern, mob_hp, max_hp)
            win, _, _ = T._simulate(mod, has_stance, seq, stance, pattern, mob_hp, max_hp)
            if win:
                wins += 1
    n = len(pool) * len(mod.ALL_HANDS)
    return 100 * wins / n


def run_trip_for_level(mod, has_stance, max_hp, mob_key, level, rng, max_pulls=50):
    """One chained trip: starts at max_hp, HP carries pull to pull, mob drawn from the
    level-appropriate weighted pool each time, stops at death or max_pulls. Returns
    (pulls, wins), same shape as condensed_trip.py's run_trip_<class> functions."""
    pool = mob_pool_for_level(mob_key, level)
    hp = max_hp
    pulls = wins = 0
    while hp > 0 and pulls < max_pulls:
        pattern, mob_hp = rng.choice(pool)
        hand = rng.choice(mod.ALL_HANDS)
        seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, pattern, mob_hp, hp)
        win, _, _ = T._simulate(mod, has_stance, seq, stance, pattern, mob_hp, hp)
        hp = hp_left
        pulls += 1
        wins += 1 if win else 0
        if hp <= 0:
            break
    return pulls, wins


def pulls_before_death(mod, has_stance, max_hp, mob_key, level, trials=3000, seed=1000):
    """Average pulls survived per trip (Monte Carlo, matching tuning_report's existing
    chained-trip methodology), against the level-appropriate weighted pool."""
    total_pulls = 0
    for i in range(trials):
        pulls, wins = run_trip_for_level(mod, has_stance, max_hp, mob_key, level, random.Random(seed + i))
        total_pulls += pulls
    return total_pulls / trials


def level_comparison_table(levels=(1, 2), trials=3000, seed=1000):
    """Returns {class_label: {level: (cost_pct, avg_pulls, win_pct)}} for every class in
    CLASSES. Three metrics, three different questions: cost% = how risky was a single pull,
    pulls = does the HP pool hold up across a real trip, win% = how often does the class
    actually finish the fight (offensive output, not a survivability stand-in -- see
    win_rate_for_level's docstring)."""
    table = {}
    for label, _ in T.CLASSES:
        mod = T.CARD_SOURCE_BY_LABEL[label]
        has_stance = T.HAS_STANCE_BY_LABEL[label]
        max_hp = float(getattr(mod, T.HP_ATTR_BY_LABEL[label]))
        mob_key = T.MOB_KEY_BY_LABEL[label]
        table[label] = {}
        for level in levels:
            cost = cost_pct_for_level(mod, has_stance, max_hp, mob_key, level)
            pulls = pulls_before_death(mod, has_stance, max_hp, mob_key, level, trials=trials, seed=seed)
            win = win_rate_for_level(mod, has_stance, max_hp, mob_key, level)
            table[label][level] = (cost, pulls, win)
    return table


def print_comparison(table, levels=(1, 2)):
    print(f"{'Class':12s}" + "".join(
        f"{'L'+str(l)+' cost%':>12s}{'L'+str(l)+' pulls':>11s}{'L'+str(l)+' win%':>10s}" for l in levels)
          + f"{'cost d':>9s}{'pulls d':>10s}{'win d':>9s}")
    for label, per_level in table.items():
        row = f"{label:12s}"
        for level in levels:
            cost, pulls, win = per_level[level]
            row += f"{cost:11.1f}%{pulls:11.2f}{win:9.1f}%"
        cost_delta = per_level[levels[-1]][0] - per_level[levels[0]][0]
        pulls_delta = per_level[levels[-1]][1] - per_level[levels[0]][1]
        win_delta = per_level[levels[-1]][2] - per_level[levels[0]][2]
        row += f"{cost_delta:+8.1f}pp{pulls_delta:+9.2f}{win_delta:+8.1f}pp"
        print(row)


if __name__ == "__main__":
    T.register_class_for_testing("necromancer", needs_range_tag=True)
    print_comparison(level_comparison_table())
