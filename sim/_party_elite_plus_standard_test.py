"""One-off diagnostic: combine one Elite (Bulwark/Berserker/Warlord, HP=12 each, the solo
baseline) with one Standard-tier mob (sum HP, sum each round's (atk,block)) instead of two
Standard mobs -- checks whether pairing an already-tougher mob with a Standard one gets
closer to a genuine 2-hero coinflip than two Standard mobs alone did."""
import condensed_party as PT
import condensed_trip as T

ELITES = {
    "Bulwark":   ([(3, 1, "melee"), (4, 0, "melee"), (6, 0, "melee")], 12),
    "Berserker": ([(6, 0, "melee"), (6, 0, "melee"), (3, 0, "melee")], 12),
    "Warlord":   ([(5, 0, "melee"), (4, 0, "melee"), (5, 0, "melee")], 12),
}
STANDARD = ["Grunt", "Bruiser", "Enforcer", "Raider", "Ambusher", "Scout"]


def combine(elite_pattern, elite_hp, standard_name):
    pat_s, hp_s = T.MOBS[standard_name]["ranger"]
    combined_pattern = [(elite_pattern[r][0] + pat_s[r][0], elite_pattern[r][1] + pat_s[r][1], "melee")
                         for r in range(3)]
    return combined_pattern, elite_hp + hp_s


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
    labels = ["warrior", "cleric"]
    print(f"=== {labels[0]} + {labels[1]} vs every Elite+Standard combo ===")
    results = []
    for elite_name, (elite_pattern, elite_hp) in ELITES.items():
        for standard_name in STANDARD:
            pattern, mob_hp = combine(elite_pattern, elite_hp, standard_name)
            r = run_pair(labels, pattern, mob_hp)
            results.append((elite_name, standard_name, mob_hp, pattern, r))
            print(f"  {elite_name:10s}+{standard_name:10s}  HP={mob_hp:2.0f}  pattern={pattern}  "
                  f"win={r['win_rate']:6.1f}%  cost={r['avg_cost_pct']:5.1f}%  avg_rounds={r['avg_rounds']:.2f}")

    print()
    print("=== Closest to a genuine 50/50 (sorted by |win_rate-50|) ===")
    results.sort(key=lambda x: abs(x[4]["win_rate"] - 50))
    for elite_name, standard_name, hp, pattern, r in results[:8]:
        print(f"  {elite_name:10s}+{standard_name:10s}  HP={hp:2.0f}  win={r['win_rate']:6.1f}%  cost={r['avg_cost_pct']:5.1f}%")


if __name__ == "__main__":
    main()
