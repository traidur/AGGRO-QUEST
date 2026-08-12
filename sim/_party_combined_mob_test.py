"""One-off diagnostic: instead of a hand-authored/searched Elite mob, test combining two
Standard-tier mobs' stats directly (sum HP, sum each round's (atk,block)) as the party-Elite
content source. Checks where the resulting 21 combos (15 distinct pairs + 6 same-mob-twice)
land for a representative 2-hero party, against the original Elite-derivation target: a
genuine, roughly 50/50 fight, not a foregone conclusion either way."""
import itertools

import condensed_party as PT
import condensed_trip as T

STANDARD = ["Grunt", "Bruiser", "Enforcer", "Raider", "Ambusher", "Scout"]


def combine(mob_a, mob_b):
    pat_a, hp_a = T.MOBS[mob_a]["ranger"]  # 3-tuple form, real dmg/block numbers
    pat_b, hp_b = T.MOBS[mob_b]["ranger"]
    combined_pattern = [(pat_a[r][0] + pat_b[r][0], pat_a[r][1] + pat_b[r][1], "melee") for r in range(3)]
    combined_hp = hp_a + hp_b
    return combined_pattern, combined_hp


def run_pair(labels, pattern, mob_hp):
    mod0, mod1 = PT.CARD_SOURCE[labels[0]], PT.CARD_SOURCE[labels[1]]
    max_hp0 = float(getattr(mod0, PT.HP_ATTR[labels[0]]))
    max_hp1 = float(getattr(mod1, PT.HP_ATTR[labels[1]]))
    total_max_hp = max_hp0 + max_hp1

    wins = 0
    total_cost = 0.0
    total_rounds = 0
    total_hands = 0
    for hand0 in mod0.ALL_HANDS:
        for hand1 in mod1.ALL_HANDS:
            hero_specs, hp_left, rounds = PT.best_line_for_party(
                labels, [hand0, hand1], pattern, mob_hp, starting_hps=[max_hp0, max_hp1])
            win, hp_left2, rounds2, _ = PT.simulate_party(hero_specs, pattern, mob_hp)
            total_hands += 1
            if win:
                wins += 1
            party_hp_left = sum(max(0.0, v) for v in hp_left2.values())
            total_cost += (total_max_hp - party_hp_left)
            total_rounds += rounds2
    return dict(win_rate=100 * wins / total_hands, avg_cost_pct=100 * (total_cost / total_hands) / total_max_hp,
                avg_rounds=total_rounds / total_hands)


def main():
    labels = ["warrior", "cleric"]  # representative pair, matches OPEN_QUESTIONS.md's own example
    combos = list(itertools.combinations(STANDARD, 2)) + [(m, m) for m in STANDARD]
    print(f"=== {labels[0]} + {labels[1]} vs every 2-Standard-mob combo ===")
    results = []
    for mob_a, mob_b in combos:
        pattern, mob_hp = combine(mob_a, mob_b)
        r = run_pair(labels, pattern, mob_hp)
        results.append((mob_a, mob_b, mob_hp, pattern, r))
        print(f"  {mob_a:10s}+{mob_b:10s}  HP={mob_hp:2.0f}  pattern={pattern}  "
              f"win={r['win_rate']:6.1f}%  cost={r['avg_cost_pct']:5.1f}%  avg_rounds={r['avg_rounds']:.2f}")

    print()
    print("=== Closest to a genuine 50/50 (sorted by |win_rate-50|) ===")
    results.sort(key=lambda x: abs(x[4]["win_rate"] - 50))
    for mob_a, mob_b, hp, pattern, r in results[:8]:
        print(f"  {mob_a:10s}+{mob_b:10s}  HP={hp:2.0f}  win={r['win_rate']:6.1f}%  cost={r['avg_cost_pct']:5.1f}%")


if __name__ == "__main__":
    main()
