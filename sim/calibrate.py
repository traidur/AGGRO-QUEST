"""Sweep mob HP at a fixed ATK to find where win rates diverge across classes.

Usage:
    python calibrate.py --atk 3 --mob-type melee --hp-min 6 --hp-max 18 --trials 3000
"""

from __future__ import annotations

import argparse

from simulate import run_trials


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atk", type=float, required=True)
    parser.add_argument("--mob-type", choices=["melee", "ranged"], required=True)
    parser.add_argument("--hp-min", type=float, required=True)
    parser.add_argument("--hp-max", type=float, required=True)
    parser.add_argument("--hp-step", type=float, default=1.0)
    parser.add_argument("--trials", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    classes = ["warrior", "cleric", "wizard"]
    print(f"ATK {args.atk:.0f}, {args.mob_type} — sweeping HP {args.hp_min:.0f} to {args.hp_max:.0f}\n")
    header = f"{'hp':>4}" + "".join(f"{c+' win%':>14}{c+' avgHP':>10}" for c in classes) + f"{'spread':>9}"
    print(header)

    hp = args.hp_min
    while hp <= args.hp_max + 1e-9:
        mob = {"name": f"calib_hp{hp:.0f}", "hp": hp, "atk": args.atk, "mob_type": args.mob_type}
        row = f"{hp:>4.0f}"
        win_rates = []
        for c in classes:
            stats = run_trials(c, mob, args.trials, args.seed)
            win_rates.append(stats["win_rate"])
            avg_hp = stats["avg_hero_hp_remaining_on_win"] or 0.0
            row += f"{stats['win_rate']*100:>13.1f}%{avg_hp:>10.2f}"
        spread = (max(win_rates) - min(win_rates)) * 100
        row += f"{spread:>8.1f}%"
        print(row)
        hp += args.hp_step


if __name__ == "__main__":
    main()
