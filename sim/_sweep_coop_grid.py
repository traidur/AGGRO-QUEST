"""Coarse grid sweep for a co-op-only tough Elite candidate. HP in [20,25], flat ATK in
[5,10], flat Block in [0,3] (same value all 3 rounds) -- 144 combinations. Fast pass only:
solo (N=1) win% for all 9 classes (must stay near 0), plus two extreme N=2 pairs (Wizard+Rogue
as the ceiling test, Ranger+Runecaster as the floor test, using every-3rd-hand sampling for
speed, not the full 15x15). Candidates that look promising get a full, unsampled 36-pair sweep
via _sweep_coop_elite.py afterward -- this script is deliberately not that final check."""
import condensed_party as CP
import condensed_trip as T

CLASSES = list(CP.CARD_SOURCE.keys())


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


def grid_sweep():
    print(f"{'HP':>4s}{'ATK':>5s}{'Blk':>5s}{'solo_max%':>11s}{'ceil(Wiz+Rog)%':>16s}{'floor(Rgr+Rc)%':>16s}")
    results = []
    for hp in range(20, 26):
        for atk in range(5, 11):
            for block in range(0, 4):
                pattern = [(atk, block, "melee")] * 3
                solo = solo_max_win(pattern, hp)
                ceil_pct = pair_win_sampled("wizard", "rogue", pattern, hp)
                floor_pct = pair_win_sampled("ranger", "runecaster", pattern, hp)
                results.append((hp, atk, block, solo, ceil_pct, floor_pct))
                print(f"{hp:4d}{atk:5d}{block:5d}{solo:11.1f}{ceil_pct:16.1f}{floor_pct:16.1f}")
    return results


if __name__ == "__main__":
    grid_sweep()
