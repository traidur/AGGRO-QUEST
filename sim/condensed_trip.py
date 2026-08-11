"""
Chain condensed-combat pulls together with no recovery between them (no Food)
to see how many pulls a hero can string together before HP would hit 0.
HP carries forward pull to pull; each pull draws a fresh random hand (deck
resets every pull, per the condensed-combat design). Reuses the existing
solvers' best_line_for_hand, which already maximizes (win, hp_left) per
pull -- since more HP now is never worse for the future in this model,
that per-pull-optimal choice is also the multi-pull-optimal one, no extra
lookahead needed.
"""
import random

import condensed_warrior as W
import condensed_wizard as Z
import condensed_cleric as C
import condensed_paladin as P
import condensed_rogue as R

# Standard tier, locked. Entire prior roster (the original 8-mob draft plus
# Footman/Marauder/Brawler, added incrementally by hand across this
# project) was retired and replaced with this 5-mob set -- found by the
# brute-force stat-gauntlet + random-pool-search process
# (sim/stat_gauntlet.py, sim/pool_search.py), not hand-designed. It's the
# only pool of several candidates tested that held up on BOTH the chained
# pulls-survived spread (0.24, tightest found) AND the chained decay
# spread (13 points Nothing-tier, also tightest found) at once -- it was
# only ever searched for the first property, and turned out best on the
# second too, which is exactly why it's the one that got kept over a
# decay-specific search result that didn't hold up under full cross-checking.
# See CLASS_BALANCE_GUIDE.md's "Retired roster" section for the full
# history of what used to be here and why hand-designed mobs were
# abandoned as a methodology. Future mobs (a Spike tier, later zones) get
# derived the same way -- brute-force search against the real chained
# diagnostics, not hand-picked and hoped to average out.
_RAW_MOBS = {
    # Grunt and Ambusher are reused names from the retired roster -- both
    # are close shape-matches for what used to sit here (same HP, same
    # core identity: Grunt = escalating rise-then-plateau, Ambusher =
    # front-loaded then fading), not just relabeled. Skirmisher and
    # Footman didn't have a matching shape among these five and stayed
    # retired rather than force a fit.
    "Grunt":    ([(2, 0), (3, 2), (3, 0)], 7),
    "Bruiser":  ([(2, 0), (2, 0), (5, 0)], 10),
    "Enforcer": ([(5, 2), (3, 0), (4, 2)], 6),
    "Raider":   ([(3, 2), (4, 0), (5, 1)], 5),
    "Ambusher": ([(4, 1), (4, 0), (2, 0)], 8),
}
MOBS = {
    name: dict(
        warrior=(pattern, hp),
        wizard=([(a, b, "melee") for a, b in pattern], hp),
        cleric=(pattern, hp),
        paladin=(pattern, hp),
        rogue=([(a, b, "melee") for a, b in pattern], hp),
    )
    for name, (pattern, hp) in _RAW_MOBS.items()
}
MOB_NAMES = list(MOBS.keys())

# Spike tier deliberately empty -- the old one (Sentinel/Brute/Elite/
# Champion) was retired along with everything else. Derive it the same
# brute-force way, against a higher cost/lower win-rate target, whenever
# the Elite node actually gets built (still deferred).
MOB_TIERS = {
    "standard": ["Grunt", "Bruiser", "Enforcer", "Raider", "Ambusher"],
    "spike": [],
}

# Draw weights for MOB_TIERS["standard"], shared across every class (the
# mob table itself doesn't change who's fighting it -- only how often each
# mob comes up changes, matching the class-agnostic mob rule). Defaults to
# uniform (every mob equally likely) unless overridden here; keyed by mob
# name so a partial override (just the mobs that need adjusting) is valid
# -- any standard-tier mob missing from this dict gets weight 1.
MOB_TIER_WEIGHTS = {
    "standard": {},
}


def mob_pool_weights(tier):
    """Returns (pool, weights) for rng.choices() -- weight 1 for any mob
    not explicitly overridden in MOB_TIER_WEIGHTS."""
    pool = MOB_TIERS[tier]
    overrides = MOB_TIER_WEIGHTS.get(tier, {})
    weights = [overrides.get(mob, 1) for mob in pool]
    return pool, weights


def run_trip_warrior(rng, max_pulls=50, fixed_mob=None):
    hp = W.WARRIOR_HP
    pulls, wins = 0, 0
    while hp > 0 and pulls < max_pulls:
        mob_name = fixed_mob or rng.choice(MOB_NAMES)
        pattern, mob_hp = MOBS[mob_name]["warrior"]
        hand = rng.choice(W.ALL_HANDS)
        seq, stance, hp_left, rounds = W.best_line_for_hand(hand, pattern, mob_hp, starting_hp=hp)
        win, _, _ = W.simulate(seq, stance, pattern, mob_hp, starting_hp=hp)
        hp = hp_left
        pulls += 1
        wins += 1 if win else 0
        if hp <= 0:
            break
    return pulls, wins


def run_trip_wizard(rng, max_pulls=50, fixed_mob=None):
    hp = Z.WIZARD_HP
    pulls, wins = 0, 0
    while hp > 0 and pulls < max_pulls:
        mob_name = fixed_mob or rng.choice(MOB_NAMES)
        pattern, mob_hp = MOBS[mob_name]["wizard"]
        hand = rng.choice(Z.ALL_HANDS)
        seq, hp_left, rounds = Z.best_line_for_hand(hand, pattern, mob_hp, starting_hp=hp)
        win, _, _ = Z.simulate(seq, pattern, mob_hp, starting_hp=hp)
        hp = hp_left
        pulls += 1
        wins += 1 if win else 0
        if hp <= 0:
            break
    return pulls, wins


def run_trip_cleric(rng, max_pulls=50, fixed_mob=None):
    hp = C.CLERIC_HP
    pulls, wins = 0, 0
    while hp > 0 and pulls < max_pulls:
        mob_name = fixed_mob or rng.choice(MOB_NAMES)
        pattern, mob_hp = MOBS[mob_name]["cleric"]
        hand = rng.choice(C.ALL_HANDS)
        seq, hp_left, rounds = C.best_line_for_hand(hand, pattern, mob_hp, starting_hp=hp)
        win, _, _ = C.simulate(seq, pattern, mob_hp, starting_hp=hp)
        hp = hp_left
        pulls += 1
        wins += 1 if win else 0
        if hp <= 0:
            break
    return pulls, wins


def run_trip_paladin(rng, max_pulls=50, fixed_mob=None):
    hp = P.PALADIN_HP
    pulls, wins = 0, 0
    while hp > 0 and pulls < max_pulls:
        mob_name = fixed_mob or rng.choice(MOB_NAMES)
        pattern, mob_hp = MOBS[mob_name]["paladin"]
        hand = rng.choice(P.ALL_HANDS)
        seq, hp_left, rounds = P.best_line_for_hand(hand, pattern, mob_hp, starting_hp=hp)
        win, _, _ = P.simulate(seq, pattern, mob_hp, starting_hp=hp)
        hp = hp_left
        pulls += 1
        wins += 1 if win else 0
        if hp <= 0:
            break
    return pulls, wins


def run_trip_rogue(rng, max_pulls=50, fixed_mob=None):
    hp = R.ROGUE_HP
    pulls, wins = 0, 0
    while hp > 0 and pulls < max_pulls:
        mob_name = fixed_mob or rng.choice(MOB_NAMES)
        pattern, mob_hp = MOBS[mob_name]["rogue"]
        hand = rng.choice(R.ALL_HANDS)
        seq, hp_left, rounds = R.best_line_for_hand(hand, pattern, mob_hp, starting_hp=hp)
        win, _, _ = R.simulate(seq, pattern, mob_hp, starting_hp=hp)
        hp = hp_left
        pulls += 1
        wins += 1 if win else 0
        if hp <= 0:
            break
    return pulls, wins


CLASSES = [("Warrior", run_trip_warrior), ("Wizard", run_trip_wizard), ("Cleric", run_trip_cleric),
           ("Paladin", run_trip_paladin), ("Rogue", run_trip_rogue)]

# Shared per-class lookup tables -- used anywhere a diagnostic needs to
# treat all four classes uniformly (mobs are tuned class-agnostic, so any
# roster-level stat, like mob difficulty, should be averaged across all
# four rather than read off a single class).
HAS_STANCE_BY_LABEL = {"Warrior": True, "Wizard": False, "Cleric": False, "Paladin": False, "Rogue": False}
CARD_SOURCE_BY_LABEL = {"Warrior": W, "Wizard": Z, "Cleric": C, "Paladin": P, "Rogue": R}
HP_ATTR_BY_LABEL = {"Warrior": "WARRIOR_HP", "Wizard": "WIZARD_HP", "Cleric": "CLERIC_HP", "Paladin": "PALADIN_HP",
                     "Rogue": "ROGUE_HP"}
MOB_KEY_BY_LABEL = {"Warrior": "warrior", "Wizard": "wizard", "Cleric": "cleric", "Paladin": "paladin",
                     "Rogue": "rogue"}
WIN_RATE_FNS = {"Warrior": (W.win_rate, "warrior"), "Wizard": (Z.win_rate, "wizard"),
                 "Cleric": (C.win_rate, "cleric"), "Paladin": (P.win_rate, "paladin"),
                 "Rogue": (R.win_rate, "rogue")}


def kill_round_distribution(mod, has_stance, mob_key, max_hp):
    """For every hand, using the same always-take-the-win optimal play as
    everywhere else in this file, tallies which round the kill actually
    lands in (1/2/3), vs. no kill at all (survives to a round-3 flee, or
    dies trying). Per-mob and aggregate."""
    per_mob = {}
    totals = {"round1": 0, "round2": 0, "round3": 0, "no_kill_survived": 0, "no_kill_died": 0, "total": 0}
    for mob_name in MOB_NAMES:
        pattern, mob_hp = MOBS[mob_name][mob_key]
        counts = {"round1": 0, "round2": 0, "round3": 0, "no_kill_survived": 0, "no_kill_died": 0, "total": 0}
        for hand in mod.ALL_HANDS:
            seq, stance, hp_left, rounds = _best_line(mod, has_stance, hand, pattern, mob_hp, max_hp)
            win, final_hp, final_rounds = _simulate(mod, has_stance, seq, stance, pattern, mob_hp, max_hp)
            counts["total"] += 1
            if win:
                counts[f"round{final_rounds}"] += 1
            elif final_hp > 0:
                counts["no_kill_survived"] += 1
            else:
                counts["no_kill_died"] += 1
        per_mob[mob_name] = counts
        for k in totals:
            totals[k] += counts[k]
    return per_mob, totals


def kill_round_table(class_specs):
    """Prints the per-mob x per-class kill-round breakdown (round1/2/3 %,
    no-kill %), plus an aggregate row per class."""
    per_class = {label: kill_round_distribution(mod, has_stance, label.lower(), max_hp)
                 for label, mod, has_stance, max_hp in class_specs}
    labels = [spec[0] for spec in class_specs]

    def fmt(counts):
        t = counts["total"]
        return (f"R1 {100*counts['round1']/t:4.0f}%  R2 {100*counts['round2']/t:4.0f}%  "
                f"R3 {100*counts['round3']/t:4.0f}%  no-kill {100*(counts['no_kill_survived']+counts['no_kill_died'])/t:4.0f}%")

    for mob_name in MOB_NAMES:
        print(f"--- {mob_name} ---")
        for label in labels:
            per_mob, totals = per_class[label]
            print(f"  {label:8s} {fmt(per_mob[mob_name])}")
    print()
    print("=== AGGREGATE (all mobs pooled) ===")
    for label in labels:
        per_mob, totals = per_class[label]
        print(f"  {label:8s} {fmt(totals)}")
    return per_class


def unplayed_card_diagnostic(mod, has_stance, mob_key, max_hp):
    """
    The Unplayed Card diagnostic (Gemini's "agony of the unplayed card," standardized).
    Across every hand x mob combination, tallies which of the 4 drawn cards gets left
    out of the optimal 3-card line. A healthy kit shows real, sometimes-strong cards
    getting cut some of the time -- not just the same weakest card every time -- since
    that's evidence the 4-vs-3 choice is a genuine decision, not a foregone conclusion.
    """
    from collections import Counter
    left_out = Counter()
    total = 0
    for hand in mod.ALL_HANDS:
        for mob_name in MOB_NAMES:
            pattern, mob_hp = MOBS[mob_name][mob_key]
            if has_stance:
                seq, stance, hp_left, rounds = mod.best_line_for_hand(hand, pattern, mob_hp, starting_hp=max_hp)
            else:
                seq, hp_left, rounds = mod.best_line_for_hand(hand, pattern, mob_hp, starting_hp=max_hp)
            unplayed = [c for c in hand if c not in seq]
            if unplayed:
                left_out[unplayed[0]] += 1
                total += 1
    return left_out, total


# ---------------------------------------------------------------------------
# Standardized diagnostic suite. All of these are black-box: they only use
# each class's public ALL_HANDS/DECK/best_line_for_hand/simulate interface,
# never inspect a class's internal CARDS structure directly, so the same
# functions work for Warrior (has stance), Wizard, and Cleric (neither does)
# without per-class special-casing beyond the has_stance flag. Cheap enough
# (a few seconds per class) to run after any card or mob change.
# ---------------------------------------------------------------------------

def _best_line(mod, has_stance, hand, pattern, mob_hp, starting_hp):
    if has_stance:
        seq, stance, hp_left, rounds = mod.best_line_for_hand(hand, pattern, mob_hp, starting_hp=starting_hp)
    else:
        seq, hp_left, rounds = mod.best_line_for_hand(hand, pattern, mob_hp, starting_hp=starting_hp)
        stance = None
    return seq, stance, hp_left, rounds


def _simulate(mod, has_stance, seq, stance, pattern, mob_hp, starting_hp):
    if has_stance:
        return mod.simulate(seq, stance, pattern, mob_hp, starting_hp=starting_hp)
    return mod.simulate(seq, pattern, mob_hp, starting_hp=starting_hp)


def _dummy_pattern(mob_key, atk=0, block=0):
    if mob_key in ("wizard", "rogue"):
        return [(atk, block, "melee")] * 3
    return [(atk, block)] * 3


def damage_floor_ceiling(mod, has_stance, mob_key, max_hp):
    """Best/worst hand's max raw 3-round damage output, found by bisecting a
    zero-ATK dummy mob's HP rather than reading card fields directly."""
    ceiling, floor, _ = damage_distribution(mod, has_stance, mob_key, max_hp)
    return ceiling, floor


def damage_distribution(mod, has_stance, mob_key, max_hp):
    """Same bisection as damage_floor_ceiling, but returns the full sorted
    per-hand distribution (all C(6,4)=15 hands) plus mean/stdev/range, not
    just the two endpoints. Floor and ceiling alone can look similar across
    two classes while hiding very different shapes underneath -- e.g.
    Warrior's spread (stdev ~1.1, tightest of the roster, every hand does
    roughly the same thing) vs Wizard's (stdev ~2.2, widest, the glass-
    cannon identity showing up directly in the distribution's shape, not
    just its average) are invisible from floor/ceiling alone. Promoted to a
    standing tool after being run ad hoc to check a Rogue design question --
    worth running on every new class, not just when something looks off."""
    import statistics as _stats
    per_hand = []
    dummy = _dummy_pattern(mob_key)
    for hand in mod.ALL_HANDS:
        best_kill = 0
        for test_hp in range(1, 30):
            seq, stance, hp_left, rounds = _best_line(mod, has_stance, hand, dummy, test_hp, max_hp)
            win, _, _ = _simulate(mod, has_stance, seq, stance, dummy, test_hp, max_hp)
            if win:
                best_kill = test_hp
        per_hand.append(best_kill)
    per_hand.sort()
    stats = dict(mean=_stats.mean(per_hand), stdev=_stats.pstdev(per_hand),
                 range=max(per_hand) - min(per_hand))
    return max(per_hand), min(per_hand), dict(per_hand=per_hand, **stats)


def healing_floor_ceiling(mod, has_stance, mob_key, max_hp):
    """Best/worst hand's max raw 3-round healing output: start near-empty,
    face a zero-ATK mob with unreachable HP (forces all 3 rounds to play out,
    win condition never triggers), read off net HP gained."""
    per_hand = []
    dummy = _dummy_pattern(mob_key)
    start_hp = 1
    for hand in mod.ALL_HANDS:
        seq, stance, hp_left, rounds = _best_line(mod, has_stance, hand, dummy, 9999, start_hp)
        per_hand.append(hp_left - start_hp)
    return max(per_hand), min(per_hand)


def equilibrium_check(mod, has_stance, mob_key, max_hp):
    """Per mob: does net HP change stay negative at every starting-HP level
    tested, or does the class hit a 'cannot die' equilibrium somewhere?"""
    results = {}
    for mob_name in MOB_NAMES:
        pattern, mob_hp = MOBS[mob_name][mob_key]
        ok = True
        for start_hp in [max_hp, max_hp * 2 // 3, max_hp // 3, 1]:
            if start_hp < 1:
                continue
            net_changes = []
            for hand in mod.ALL_HANDS:
                seq, stance, hp_left, rounds = _best_line(mod, has_stance, hand, pattern, mob_hp, start_hp)
                net_changes.append(hp_left - start_hp)
            if sum(net_changes) / len(net_changes) >= 0:
                ok = False
        results[mob_name] = ok
    return results


def pairwise_genuine_difference(mod, has_stance, mob_key, max_hp):
    """Generalizes the Smite/Call-of-the-Void check to every card pair in the
    deck automatically. For hands containing both cards of a pair, where the
    optimal line uses one but not the other, checks whether forcibly swapping
    produces a real (non-tied) outcome difference. A pair that's 100% ties
    whenever both are drawn is a hidden-domination red flag -- one card is
    dead weight the moment the other is available, same as the old Smite/CoV
    bug, just not yet noticed."""
    import itertools
    flagged = {}
    for card_a, card_b in itertools.combinations(mod.DECK, 2):
        genuine, tied = 0, 0
        for hand in mod.ALL_HANDS:
            if card_a not in hand or card_b not in hand:
                continue
            for mob_name in MOB_NAMES:
                pattern, mob_hp = MOBS[mob_name][mob_key]
                seq, stance, hp_left, rounds = _best_line(mod, has_stance, hand, pattern, mob_hp, max_hp)
                if card_a in seq and card_b not in seq:
                    other, mine = card_b, card_a
                elif card_b in seq and card_a not in seq:
                    other, mine = card_a, card_b
                else:
                    continue
                forced = tuple(other if c == mine else c for c in seq)
                win1, hp1, _ = _simulate(mod, has_stance, seq, stance, pattern, mob_hp, max_hp)
                win2, hp2, _ = _simulate(mod, has_stance, forced, stance, pattern, mob_hp, max_hp)
                if (win1, hp1) == (win2, hp2):
                    tied += 1
                else:
                    genuine += 1
        total = genuine + tied
        if total > 0 and genuine == 0:
            flagged[(card_a, card_b)] = total
    return flagged


def permutation_variance_rate(mod, has_stance, mob_key, max_hp):
    """Gemini's Commutativity check. For each hand's chosen 3-card SET (not
    just the one ordering the solver picked), enumerate all 6 permutations
    against the same mob and count how many tie the best (win, hp_left).
    6/6 tied means order genuinely doesn't matter for that hand+mob -- it's
    a drafting choice, not a sequencing puzzle. Returns the average tied
    fraction and the % of (hand, mob) cases with zero order-sensitivity."""
    import itertools
    all_fracs = []
    fully_order_independent = 0
    total = 0
    for hand in mod.ALL_HANDS:
        for mob_name in MOB_NAMES:
            pattern, mob_hp = MOBS[mob_name][mob_key]
            seq, stance, hp_left, rounds = _best_line(mod, has_stance, hand, pattern, mob_hp, max_hp)
            best_key = None
            outcomes = []
            for perm in itertools.permutations(seq):
                if has_stance:
                    win, hpl, r = _simulate(mod, has_stance, perm, stance, pattern, mob_hp, max_hp)
                else:
                    win, hpl, r = _simulate(mod, has_stance, perm, None, pattern, mob_hp, max_hp)
                key = (win, hpl)
                outcomes.append(key)
                if best_key is None or key > best_key:
                    best_key = key
            tied = sum(1 for k in outcomes if k == best_key)
            all_fracs.append(tied / len(outcomes))
            if tied == len(outcomes):
                fully_order_independent += 1
            total += 1
    avg_frac = sum(all_fracs) / len(all_fracs)
    return avg_frac, fully_order_independent / total


def tie_density(mod, has_stance, mob_key, max_hp):
    """Gemini's Solution Density check. Across ALL valid lines for a hand
    (every 3-of-4 card subset, every ordering, every stance variant), count
    how many distinct lines share the single best (win, hp_left) outcome.
    A hand with many tied-optimal lines means "every door leads to the
    exit" -- not much of a puzzle. Returns average tie count and the max
    seen."""
    import itertools
    stance_seqs = mod.STANCE_SEQS if has_stance else [None]
    tie_counts = []
    for hand in mod.ALL_HANDS:
        for mob_name in MOB_NAMES:
            pattern, mob_hp = MOBS[mob_name][mob_key]
            best_key = None
            outcomes = []
            for subset in itertools.permutations(hand, 3):
                for stance in stance_seqs:
                    win, hpl, r = _simulate(mod, has_stance, subset, stance, pattern, mob_hp, max_hp)
                    key = (win, hpl)
                    outcomes.append(key)
                    if best_key is None or key > best_key:
                        best_key = key
            tie_counts.append(sum(1 for k in outcomes if k == best_key))
    return sum(tie_counts) / len(tie_counts), max(tie_counts)


def _flee_preference_for_pattern(mod, has_stance, pattern, mob_hp, max_hp):
    """One mob's worth of the Coward's Gambit check -- shared by both
    flee_preference() (aggregate) and flee_preference_by_mob() (per-mob),
    so the two can never drift apart the way the ad-hoc stance-balance
    script did."""
    import itertools
    stance_seqs = mod.STANCE_SEQS if has_stance else [None]
    flee_better_count = 0
    flee_margins = []
    total = 0
    for hand in mod.ALL_HANDS:
        best_any_hp = None
        best_win_hp = None
        for subset in itertools.permutations(hand, 3):
            for stance in stance_seqs:
                win, hpl, r = _simulate(mod, has_stance, subset, stance, pattern, mob_hp, max_hp)
                if best_any_hp is None or hpl > best_any_hp:
                    best_any_hp = hpl
                if win and (best_win_hp is None or hpl > best_win_hp):
                    best_win_hp = hpl
        total += 1
        if best_win_hp is None:
            continue  # no winning line exists at all for this hand+mob
        if best_any_hp > best_win_hp:
            flee_better_count += 1
            flee_margins.append(best_any_hp - best_win_hp)
    rate = flee_better_count / total if total else 0.0
    avg_margin = sum(flee_margins) / len(flee_margins) if flee_margins else 0.0
    return rate, avg_margin, flee_better_count, total, flee_margins


def flee_preference(mod, has_stance, mob_key, max_hp):
    """Gemini's Coward's Gambit check, measurement only -- does NOT judge
    whether a high rate is good or bad, since that depends on the
    not-yet-decided loot-on-flee design. For each hand+mob, compares the
    best HP outcome requiring a kill against the best HP outcome allowing
    any result (including a timeout/flee). Reports how often letting the
    mob flee would preserve strictly more HP than winning does, and by how
    much on average in those cases -- i.e., how tempting a 'turtle and
    don't finish it' strategy would be if it had real value. Aggregated
    across the whole roster -- use flee_preference_by_mob() to see which
    specific mobs are driving the number."""
    total_better = 0
    total_hands = 0
    all_margins = []
    for mob_name in MOB_NAMES:
        pattern, mob_hp = MOBS[mob_name][mob_key]
        rate, avg_margin, better, total, margins = _flee_preference_for_pattern(mod, has_stance, pattern, mob_hp, max_hp)
        total_better += better
        total_hands += total
        all_margins.extend(margins)
    rate = total_better / total_hands if total_hands else 0.0
    avg_margin = sum(all_margins) / len(all_margins) if all_margins else 0.0
    return rate, avg_margin


def flee_preference_by_mob(mod, has_stance, mob_key, max_hp):
    """Same check as flee_preference(), broken out per mob instead of
    aggregated -- answers 'which mob is actually driving the number' in one
    call instead of a throwaway script."""
    results = {}
    for mob_name in MOB_NAMES:
        pattern, mob_hp = MOBS[mob_name][mob_key]
        rate, avg_margin, better, total, margins = _flee_preference_for_pattern(mod, has_stance, pattern, mob_hp, max_hp)
        results[mob_name] = dict(rate=rate, avg_margin=avg_margin, count=better, total=total)
    return results


def flee_preference_table(class_specs):
    """Prints the per-mob x per-class flee-preference table. class_specs is
    a list of (label, mod, has_stance, max_hp) tuples, e.g.:
        [("Warrior", W, True, W.WARRIOR_HP),
         ("Wizard", Z, False, Z.WIZARD_HP),
         ("Cleric", C, False, C.CLERIC_HP)]
    """
    per_class = {label: flee_preference_by_mob(mod, has_stance, label.lower(), max_hp)
                 for label, mod, has_stance, max_hp in class_specs}
    labels = [spec[0] for spec in class_specs]

    header = f"{'Mob':12s} |" + "".join(f" {l:>16s} |" for l in labels)
    print(header)
    print("-" * len(header))
    totals = {l: [0, 0] for l in labels}
    for mob_name in MOB_NAMES:
        row = f"{mob_name:12s} |"
        for label in labels:
            r = per_class[label][mob_name]
            totals[label][0] += r["count"]
            totals[label][1] += r["total"]
            row += f" {100*r['rate']:>5.1f}% {r['avg_margin']:>4.1f}hp |"
        print(row)
    print("-" * len(header))
    row = f"{'TOTAL':12s} |"
    for label in labels:
        c, t = totals[label]
        row += f" {100*c/t if t else 0:>5.1f}%        |"
    print(row)
    return per_class


def waste_index(mod, has_stance, mob_key, max_hp, max_hp_attr):
    """Gemini's Wasted Resource Index. Unlike the floor/ceiling checks
    (which deliberately use unkillable/zero-attack dummies to isolate raw
    output), this measures overkill and overheal against REAL mob HP
    breakpoints in actual optimal wins. Overkill: how much higher the same
    winning sequence+stance could have killed (via bisection), i.e. damage
    that did nothing. Overheal: replays the same line with the class's max
    HP temporarily patched very high, so healing is never capped, and
    compares -- the difference is healing that was thrown away by the cap."""
    overkills = []
    overheals = []
    for hand in mod.ALL_HANDS:
        for mob_name in MOB_NAMES:
            pattern, mob_hp = MOBS[mob_name][mob_key]
            seq, stance, hp_left, rounds = _best_line(mod, has_stance, hand, pattern, mob_hp, max_hp)
            win, _, _ = _simulate(mod, has_stance, seq, stance, pattern, mob_hp, max_hp)
            if not win:
                continue
            # overkill: bisect the max mob HP this exact seq+stance could still kill
            max_killable = mob_hp
            for test_hp in range(mob_hp, mob_hp + 30):
                w, _, _ = _simulate(mod, has_stance, seq, stance, pattern, test_hp, max_hp)
                if w:
                    max_killable = test_hp
            overkills.append(max_killable - mob_hp)
            # overheal: same line, cap patched very high
            orig = getattr(mod, max_hp_attr)
            setattr(mod, max_hp_attr, 999)
            win_u, hp_uncapped, _ = _simulate(mod, has_stance, seq, stance, pattern, mob_hp, max_hp)
            setattr(mod, max_hp_attr, orig)
            overheals.append(max(0.0, hp_uncapped - hp_left))
    avg_overkill = sum(overkills) / len(overkills) if overkills else 0.0
    avg_overheal = sum(overheals) / len(overheals) if overheals else 0.0
    return avg_overkill, avg_overheal


def full_diagnostic(label, mod, has_stance, mob_key, max_hp, max_hp_attr):
    print(f"===== FULL DIAGNOSTIC: {label} =====")
    dmg_ceil, dmg_floor, dmg_stats = damage_distribution(mod, has_stance, mob_key, max_hp)
    print(f"Damage floor/ceiling: {dmg_floor} / {dmg_ceil}")
    print(f"Damage distribution: {dmg_stats['per_hand']}")
    print(f"    mean={dmg_stats['mean']:.2f}  stdev={dmg_stats['stdev']:.2f}  range={dmg_stats['range']}")
    heal_ceil, heal_floor = healing_floor_ceiling(mod, has_stance, mob_key, max_hp)
    print(f"Healing floor/ceiling: {heal_floor} / {heal_ceil}")
    eq = equilibrium_check(mod, has_stance, mob_key, max_hp)
    broken = [m for m, ok in eq.items() if not ok]
    print(f"Equilibrium: {'ALL CLEAR' if not broken else 'BROKEN on ' + ', '.join(broken)}")
    left_out, total = unplayed_card_diagnostic(mod, has_stance, mob_key, max_hp)
    print("Unplayed Card diagnostic:")
    for card, count in left_out.most_common():
        print(f"    {card:20s} {count:4d}  ({count/total:.1%})")
    flagged = pairwise_genuine_difference(mod, has_stance, mob_key, max_hp)
    if flagged:
        print("Hidden-domination flags (100% tied whenever both drawn):")
        for (a, b), n in flagged.items():
            print(f"    {a} vs {b}  ({n} overlap cases, all tied)")
    else:
        print("No hidden-domination pairs found.")
    avg_frac, fully_indep_rate = permutation_variance_rate(mod, has_stance, mob_key, max_hp)
    print(f"Permutation Variance: avg {avg_frac:.1%} of orderings tie the best; "
          f"{fully_indep_rate:.1%} of hand/mob cases are fully order-independent")
    avg_ties, max_ties = tie_density(mod, has_stance, mob_key, max_hp)
    print(f"Tie Density: avg {avg_ties:.1f} distinct lines share the optimal outcome (max seen: {max_ties})")
    flee_rate, flee_margin = flee_preference(mod, has_stance, mob_key, max_hp)
    print(f"Flee Preference (measurement only, not a pass/fail): letting the mob flee beats "
          f"winning in {flee_rate:.1%} of cases, by {flee_margin:.2f} HP on average when it does")
    avg_overkill, avg_overheal = waste_index(mod, has_stance, mob_key, max_hp, max_hp_attr)
    print(f"Waste Index: avg overkill {avg_overkill:.2f} dmg, avg overheal {avg_overheal:.2f} HP per win")
    print()


def full_report(trials=3000, seed=42, label=None):
    """The complete three-section report (mixed roster, single-mob-repeated
    trip stats, single-pull win rate per mob) as a callable, reusable
    function instead of a hardcoded __main__ script -- so it can be run
    once as a baseline, then again after twisting a single lever (e.g.
    `W.WARRIOR_HP = 20` before the second call), and actually compared.
    Returns the raw numbers (not just prints them) so a caller can diff two
    runs programmatically instead of eyeballing two blocks of text.

    Reads current CARDS/HP/MOBS values live off the imported modules each
    call, so any module-level edit (temporary monkey-patch or a real file
    edit) is picked up automatically -- no need to re-import."""
    rng = random.Random(seed)
    if label:
        print(f"########## {label} ##########")

    results = {"mixed": {}, "per_mob": {}, "win_rate": {}}

    print("=== Mixed roster (random mob each pull, full 8-mob roster) ===")
    for lbl, fn in CLASSES:
        all_pulls, all_wins = [], []
        for _ in range(trials):
            p, w = fn(rng)
            all_pulls.append(p)
            all_wins.append(w)
        avg_p = sum(all_pulls) / trials
        avg_w = sum(all_wins) / trials
        results["mixed"][lbl] = (avg_p, avg_w)
        print(f"{lbl:8s} avg pulls before HP<=0: {avg_p:.2f}   avg wins in that span: {avg_w:.2f}"
              f"   wins/pull: {avg_w/avg_p:.1%}")

    print()
    print("=== Single mob repeated ===")
    for mob_name in MOB_NAMES:
        line = f"{mob_name:12s}"
        results["per_mob"][mob_name] = {}
        for lbl, fn in CLASSES:
            all_pulls, all_wins = [], []
            for _ in range(trials):
                p, w = fn(rng, fixed_mob=mob_name)
                all_pulls.append(p)
                all_wins.append(w)
            avg_p = sum(all_pulls) / trials
            avg_w = sum(all_wins) / trials
            results["per_mob"][mob_name][lbl] = (avg_p, avg_w)
            line += f"   {lbl}: {avg_p:5.2f}p/{avg_w:5.2f}w/{avg_w/avg_p:5.1%}"
        print(line)

    print()
    print("=== Single-pull win rate per mob ===")
    for mob_name in MOB_NAMES:
        rates = {}
        for lbl, _ in CLASSES:
            fn, mob_key = WIN_RATE_FNS[lbl]
            pattern, mob_hp = MOBS[mob_name][mob_key]
            rates[lbl] = fn(pattern, mob_hp)
        results["win_rate"][mob_name] = rates
        line = f"{mob_name:12s}"
        for lbl, _ in CLASSES:
            line += f"  {lbl} {rates[lbl]:6.1%}  "
        print(line)

    return results


def compare_reports(before, after, before_label="BEFORE", after_label="AFTER"):
    """Diffs two full_report() results side by side -- mixed-roster deltas
    and per-mob win deltas, so 'what did twisting this lever actually do'
    is a direct answer instead of two walls of text to eyeball."""
    print(f"=== Mixed roster: {before_label} -> {after_label} ===")
    for lbl, _ in CLASSES:
        bp, bw = before["mixed"][lbl]
        ap, aw = after["mixed"][lbl]
        br, ar = bw / bp, aw / ap
        print(f"{lbl:8s} pulls {bp:5.2f} -> {ap:5.2f} ({ap-bp:+.2f})   "
              f"wins {bw:5.2f} -> {aw:5.2f} ({aw-bw:+.2f})   "
              f"wins/pull {br:5.1%} -> {ar:5.1%} ({100*(ar-br):+.1f}pp)")

    print()
    print(f"=== Per-mob wins: {before_label} -> {after_label} ===")
    for mob_name in MOB_NAMES:
        line = f"{mob_name:12s}"
        for lbl, _ in CLASSES:
            _, bw = before["per_mob"][mob_name][lbl]
            _, aw = after["per_mob"][mob_name][lbl]
            line += f"   {lbl}: {bw:5.2f}->{aw:5.2f} ({aw-bw:+.2f})"
        print(line)


def mob_difficulty_ranking():
    """Ranks the current roster by difficulty using two exact,
    class-agnostic measures, each averaged across all four classes so no
    single class's kit quirks (e.g. Cleric's healing) can skew a mob's
    difficulty label -- mobs are tuned the same for every class (see
    MOBS), so their difficulty should be reported the same way.

    avg HP cost %: average, over every possible hand, of (max_hp -
    hp_left) from a full-HP single pull under optimal play, as a percent
    of that class's max HP -- how much of a health bar one pull against
    this mob typically costs. This is what actually separates a mob
    that's class-agnostically easy from one that just happens to be a
    great matchup for one class's kit -- a mob that's cheap for every
    class averages low here; a mob that's only cheap for one class still
    averages out closer to the pack.

    avg win rate: win_rate() per class, averaged the same way.

    Both are exact-enumeration numbers (no RNG, no trials argument)."""
    cost_by_mob = {}
    winrate_by_mob = {}
    for mob_name in MOB_NAMES:
        costs, winrates = [], []
        for lbl, _ in CLASSES:
            mod = CARD_SOURCE_BY_LABEL[lbl]
            has_stance = HAS_STANCE_BY_LABEL[lbl]
            max_hp = float(getattr(mod, HP_ATTR_BY_LABEL[lbl]))
            fn, mob_key = WIN_RATE_FNS[lbl]
            pattern, mob_hp = MOBS[mob_name][mob_key]

            per_hand_costs = [
                max_hp - _best_line(mod, has_stance, hand, pattern, mob_hp, max_hp)[2]
                for hand in mod.ALL_HANDS
            ]
            costs.append(100 * (sum(per_hand_costs) / len(per_hand_costs)) / max_hp)
            winrates.append(fn(pattern, mob_hp))

        cost_by_mob[mob_name] = sum(costs) / len(costs)
        winrate_by_mob[mob_name] = sum(winrates) / len(winrates)

    ranked = sorted(MOB_NAMES, key=lambda m: cost_by_mob[m])
    print("=== Mob difficulty ranking (avg HP cost % per pull, avg win rate -- both averaged across all 4 classes) ===")
    for mob_name in ranked:
        print(f"{mob_name:12s} avg cost {cost_by_mob[mob_name]:5.1f}%   avg win rate {winrate_by_mob[mob_name]:6.1%}")

    return dict(cost=cost_by_mob, win_rate=winrate_by_mob, ranked=ranked)


if __name__ == "__main__":
    full_report()
