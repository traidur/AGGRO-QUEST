"""One-off diagnostic: run every 2-hero class pair against the existing Elite trio
(Bulwark/Berserker/Warlord, HP=12 each, the SOLO single-hero baseline from
CLASS_BALANCE_GUIDE.md) through the new condensed_party.py engine, to see empirically
how far off these need to be for real 2-hero party math, and whether Aggro targeting
looks reasonable in the process. Full 15x15 hand-pair sweep per pair per mob (~2-4s each,
measured), assuming optimal play throughout (best_line_for_party)."""
import itertools

import condensed_party as PT

ELITES = {
    "Bulwark":   ([(3, 1, "melee"), (4, 0, "melee"), (6, 0, "melee")], 12),
    "Berserker": ([(6, 0, "melee"), (6, 0, "melee"), (3, 0, "melee")], 12),
    "Warlord":   ([(5, 0, "melee"), (4, 0, "melee"), (5, 0, "melee")], 12),
}

CLASSES = ["warrior", "wizard", "cleric", "paladin", "rogue", "ranger"]
PAIRS = list(itertools.combinations(CLASSES, 2))


def run_pair(labels, pattern, mob_hp):
    mod0, mod1 = PT.CARD_SOURCE[labels[0]], PT.CARD_SOURCE[labels[1]]
    max_hp0 = float(getattr(mod0, PT.HP_ATTR[labels[0]]))
    max_hp1 = float(getattr(mod1, PT.HP_ATTR[labels[1]]))
    total_max_hp = max_hp0 + max_hp1

    wins = 0
    total_cost = 0.0
    total_rounds = 0
    total_hands = 0
    round1_kills = 0
    for hand0 in mod0.ALL_HANDS:
        for hand1 in mod1.ALL_HANDS:
            hero_specs, hp_left, rounds = PT.best_line_for_party(
                labels, [hand0, hand1], pattern, mob_hp, starting_hps=[max_hp0, max_hp1])
            win, hp_left2, rounds2, _ = PT.simulate_party(hero_specs, pattern, mob_hp)
            total_hands += 1
            if win:
                wins += 1
                if rounds2 == 1:
                    round1_kills += 1
            party_hp_left = sum(max(0.0, v) for v in hp_left2.values())
            total_cost += (total_max_hp - party_hp_left)
            total_rounds += rounds2
    return dict(
        win_rate=100 * wins / total_hands,
        avg_cost_pct=100 * (total_cost / total_hands) / total_max_hp,
        avg_rounds=total_rounds / total_hands,
        round1_kill_pct=100 * round1_kills / total_hands,
    )


def main():
    for mob_name, (pattern, mob_hp) in ELITES.items():
        print(f"\n=== {mob_name} (HP={mob_hp}, solo baseline) ===")
        for labels in PAIRS:
            r = run_pair(labels, pattern, mob_hp)
            print(f"  {labels[0]:8s}+{labels[1]:8s}  win={r['win_rate']:6.1f}%  "
                  f"cost={r['avg_cost_pct']:5.1f}%  avg_rounds={r['avg_rounds']:.2f}  "
                  f"R1-kill={r['round1_kill_pct']:5.1f}%")


if __name__ == "__main__":
    main()
