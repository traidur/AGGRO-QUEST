"""Throwaway sweep script for a co-op-only tough Elite candidate -- checks the solo-vs-N=2
gap agreed with the user: solo (N=1) should be near-unbeatable/extremely costly, N=2 should
land in a real, winnable-but-risky band, class-agnostic across all 36 distinct class pairs."""
import itertools
import condensed_party as CP
import condensed_trip as T

CLASSES = list(CP.CARD_SOURCE.keys())  # 9 classes


def solo_cost_win(label, pattern, mob_hp):
    mod = CP.CARD_SOURCE[label]
    max_hp = float(getattr(mod, CP.HP_ATTR[label]))
    # solo resolve_round wants a 2-tuple for non-range-tagged classes, 3-tuple otherwise --
    # party's engine always wants 3-tuples, so the caller passes 3-tuples in and this strips
    # down to 2 only for the classes that need it.
    pattern = pattern if label in T._RANGE_TAGGED_MOB_KEYS else [(a, b) for a, b, _ in pattern]
    costs, wins = [], []
    for hand in mod.ALL_HANDS:
        if label == "warrior":
            seq, stance, hp_left, rounds = T._best_line(mod, True, hand, pattern, mob_hp, max_hp)
            win, _, _ = T._simulate(mod, True, seq, stance, pattern, mob_hp, max_hp)
        else:
            seq, hp_left, rounds = mod.best_line_for_hand(hand, pattern, mob_hp, starting_hp=max_hp)
            win, _, _ = mod.simulate(seq, pattern, mob_hp, starting_hp=max_hp)
        costs.append(max_hp - hp_left)
        wins.append(win)
    cost_pct = 100 * (sum(costs) / len(costs)) / max_hp
    win_pct = 100 * sum(wins) / len(wins)
    return cost_pct, win_pct


def pair_cost_win(label_a, label_b, pattern, mob_hp):
    mod_a, mod_b = CP.CARD_SOURCE[label_a], CP.CARD_SOURCE[label_b]
    max_hp_a = float(getattr(mod_a, CP.HP_ATTR[label_a]))
    max_hp_b = float(getattr(mod_b, CP.HP_ATTR[label_b]))
    total_max = max_hp_a + max_hp_b
    normalized = [e if len(e) == 3 else (e[0], e[1], "melee") for e in pattern]
    mob_specs = [dict(pattern=normalized, hp=mob_hp)]
    damage_targets = [{0: 0, 1: 0} for _ in range(3)]

    costs, wins = [], []
    for hand_a in mod_a.ALL_HANDS:
        for hand_b in mod_b.ALL_HANDS:
            hero_specs, hp_left, rounds = CP.best_line_for_party_multimob_single(
                [label_a, label_b], [hand_a, hand_b], pattern, mob_hp,
                starting_hps=[max_hp_a, max_hp_b])
            win, hp_left2, rounds2, _ = CP.simulate_party_multimob(hero_specs, mob_specs, damage_targets)
            total_hp_left = sum(v for v in hp_left2.values() if v > -1e8)
            costs.append(total_max - total_hp_left)
            wins.append(win)
    cost_pct = 100 * (sum(costs) / len(costs)) / total_max
    win_pct = 100 * sum(wins) / len(wins)
    return cost_pct, win_pct


def sweep(label, pattern, mob_hp):
    print(f"=== Candidate: {label}  HP={mob_hp}  pattern={pattern} ===")
    print("--- Solo (N=1), all 9 classes ---")
    solo_costs, solo_wins = [], []
    for cls in CLASSES:
        cost, win = solo_cost_win(cls, pattern, mob_hp)
        solo_costs.append(cost)
        solo_wins.append(win)
        print(f"  {cls:12s} cost%={cost:6.1f}  win%={win:6.1f}")
    print(f"  solo range: cost% {min(solo_costs):.1f}-{max(solo_costs):.1f}  win% {min(solo_wins):.1f}-{max(solo_wins):.1f}")

    print("--- N=2, all 36 distinct class pairs ---")
    pair_costs, pair_wins = [], []
    for a, b in itertools.combinations(CLASSES, 2):
        cost, win = pair_cost_win(a, b, pattern, mob_hp)
        pair_costs.append(cost)
        pair_wins.append(win)
        print(f"  {a:12s}+{b:12s} cost%={cost:6.1f}  win%={win:6.1f}")
    print(f"  N=2 range: cost% {min(pair_costs):.1f}-{max(pair_costs):.1f}  win% {min(pair_wins):.1f}-{max(pair_wins):.1f}")


if __name__ == "__main__":
    sweep("candidate_1", [(4, 1, "melee"), (5, 0, "melee"), (6, 1, "melee")], 24)
