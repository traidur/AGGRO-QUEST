"""Per-round independent Block sweep for a co-op-only tough Elite candidate, ATK held to 4
representative shapes since the flat-pattern grid (_sweep_coop_grid.py) already showed ATK
doesn't affect win/loss in this HP range at all -- concentrating it differently per round is
the actual open question, not its magnitude. HP in [20,25], Block independently swept 0-3 per
round (64 shapes), 4 ATK shapes (flat/ascending/descending/spike-mid) -- 6*4*64=1536
combinations. Same fast/sampled two-pair coarse-pass methodology as _sweep_coop_grid.py;
whatever survives this gets the full, unsampled 36-pair check afterward."""
import condensed_party as CP
import condensed_trip as T

CLASSES = list(CP.CARD_SOURCE.keys())

ATK_SHAPES = {
    "flat":       (7, 7, 7),
    "ascending":  (5, 7, 10),
    "descending": (10, 7, 5),
    "spike_mid":  (5, 10, 5),
}


def solo_max_win(pattern, mob_hp):
    max_win = 0.0
    for cls in CLASSES:
        mod = CP.CARD_SOURCE[cls]
        max_hp = float(getattr(mod, CP.HP_ATTR[cls]))
        p = pattern if cls in T._RANGE_TAGGED_MOB_KEYS else [(a, b) for a, b, _ in pattern]
        wins = 0
        for hand in mod.ALL_HANDS:
            if cls == "warrior":
                seq, stance, hp_left, rounds = T._best_line(mod, True, hand, p, mob_hp, max_hp)
                win, _, _ = T._simulate(mod, True, seq, stance, p, mob_hp, max_hp)
            else:
                seq, hp_left, rounds = mod.best_line_for_hand(hand, p, mob_hp, starting_hp=max_hp)
                win, _, _ = mod.simulate(seq, p, mob_hp, starting_hp=max_hp)
            wins += 1 if win else 0
        win_pct = 100 * wins / len(mod.ALL_HANDS)
        max_win = max(max_win, win_pct)
    return max_win


def pair_win_sampled(label_a, label_b, pattern, mob_hp, sample_every=3):
    mod_a, mod_b = CP.CARD_SOURCE[label_a], CP.CARD_SOURCE[label_b]
    max_hp_a = float(getattr(mod_a, CP.HP_ATTR[label_a]))
    max_hp_b = float(getattr(mod_b, CP.HP_ATTR[label_b]))
    normalized = [e if len(e) == 3 else (e[0], e[1], "melee") for e in pattern]
    mob_specs = [dict(pattern=normalized, hp=mob_hp)]
    damage_targets = [{0: 0, 1: 0} for _ in range(3)]

    hands_a = [h for idx, h in enumerate(mod_a.ALL_HANDS) if idx % sample_every == 0]
    hands_b = [h for idx, h in enumerate(mod_b.ALL_HANDS) if idx % sample_every == 0]
    wins = 0
    total = 0
    for hand_a in hands_a:
        for hand_b in hands_b:
            hero_specs, hp_left, rounds = CP.best_line_for_party_multimob_single(
                [label_a, label_b], [hand_a, hand_b], pattern, mob_hp,
                starting_hps=[max_hp_a, max_hp_b])
            win, _, _, _ = CP.simulate_party_multimob(hero_specs, mob_specs, damage_targets)
            wins += 1 if win else 0
            total += 1
    return 100 * wins / total


def shape_sweep():
    print(f"{'HP':>4s}{'ATK_shape':>12s}{'B1':>4s}{'B2':>4s}{'B3':>4s}{'solo_max%':>11s}{'ceil%':>8s}{'floor%':>8s}")
    results = []
    for hp in range(20, 26):
        for atk_name, atk in ATK_SHAPES.items():
            for b1 in range(0, 4):
                for b2 in range(0, 4):
                    for b3 in range(0, 4):
                        pattern = [(atk[0], b1, "melee"), (atk[1], b2, "melee"), (atk[2], b3, "melee")]
                        solo = solo_max_win(pattern, hp)
                        ceil_pct = pair_win_sampled("wizard", "rogue", pattern, hp)
                        floor_pct = pair_win_sampled("ranger", "runecaster", pattern, hp)
                        results.append((hp, atk_name, b1, b2, b3, solo, ceil_pct, floor_pct))
                        # only print the interesting ones (solo still 0, floor nonzero, ceiling not maxed)
                        if solo == 0.0 and 0 < floor_pct < 100 and ceil_pct < 90:
                            print(f"{hp:4d}{atk_name:>12s}{b1:4d}{b2:4d}{b3:4d}{solo:11.1f}{ceil_pct:8.1f}{floor_pct:8.1f}")
    return results


if __name__ == "__main__":
    shape_sweep()
