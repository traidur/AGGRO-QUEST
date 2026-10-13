"""
One-off test: how do the locked Tier Gate Boss Trio numbers change if every hero carries
exactly one crafted weapon into the fight -- the single-use "Honed" rider (+1 raw dmg for
1-Hander/Wand, +2 for 2-Hander/Staff, Honed is allowed on all four weapon bases so every
class gets the same conceptual item) on their class-appropriate weapon base. No armor, no
consumables -- isolating the weapon slot alone.

Durability carries across phases correctly: if Honed gets activated in Phase 1, it's
exhausted (tapped) for Phase 2 too, since the boss fight explicitly allows "no resting...
between phases" and Exhaustion only refreshes on a Town visit (board_engine.py's own rule).
"""
import itertools
import macro_sim as M
import leveling_validation as LV
from equipment_solver import best_line_with_equipment
import _boss_phase_sim_v2 as B

CLASSES = list(M.CARD_SOURCE.keys())
MELEE_WEAPON_CLASSES = {"warrior", "paladin", "rogue", "ranger", "runecaster", "druid"}
# Druid qualifies for both lists (1-Hander AND Wand) -- picked 1-Hander by convention; Honed's
# bonus is identical either way (+1), so this choice has zero effect on the numbers.


def weapon_for(class_name):
    base = "1-Hander" if class_name in MELEE_WEAPON_CLASSES else "Wand"
    return {"weapon": {"rider": "honed", "base": base}}


def eval_boss_weapon(p1_pattern, p1_hp, p2_pattern, p2_hp, classes=None):
    classes = classes or CLASSES
    results = {}
    for class_name in classes:
        mod = M.CARD_SOURCE[class_name]
        start_hp = getattr(mod, M.HP_ATTR[class_name])
        mand = M.LEVEL2_MANDATORY[class_name]
        purch = M.LEVEL2_PURCHASED_ORDER[class_name]
        full_equipment = weapon_for(class_name)

        c_pat1 = B.format_pattern(p1_pattern, class_name)
        c_pat2 = B.format_pattern(p2_pattern, class_name)

        total_runs = 0
        wins = 0
        p1_death = 0
        p1_dmg_fail = 0
        p2_death = 0
        p2_dmg_fail = 0
        win_ending_hps = []

        combos = list(itertools.combinations(range(3), 2))
        for combo in combos:
            swaps = {}
            _, old_name, new_name, new_card = mand
            swaps[old_name] = (new_name, new_card)
            for idx in combo:
                old_name, new_name, new_card = purch[idx]
                swaps[old_name] = (new_name, new_card)

            with LV.leveled_kit(mod, swaps):
                hands = mod.ALL_HANDS
                for h1 in hands:
                    win1, seq1, stance1, hp1, r1, usage1 = best_line_with_equipment(
                        class_name, h1, c_pat1, p1_hp, start_hp, full_equipment)

                    if not win1:
                        for _ in hands:
                            total_runs += 1
                            if hp1 <= 0:
                                p1_death += 1
                            else:
                                p1_dmg_fail += 1
                        continue

                    # Durability: weapon used in P1 (usage1["weapon"] is not None) stays
                    # exhausted for P2 -- no Town visit between phases.
                    p2_equipment = full_equipment if usage1.get("weapon") is None else {}

                    for h2 in hands:
                        total_runs += 1
                        win2, seq2, stance2, hp2, r2, usage2 = best_line_with_equipment(
                            class_name, h2, c_pat2, p2_hp, hp1, p2_equipment)
                        if win2:
                            wins += 1
                            win_ending_hps.append(hp2)
                        else:
                            if hp2 <= 0:
                                p2_death += 1
                            else:
                                p2_dmg_fail += 1

        win_rate = wins / total_runs
        avg_end_hp = sum(win_ending_hps) / len(win_ending_hps) if win_ending_hps else 0.0
        results[class_name] = {
            "win_rate": win_rate, "avg_end_hp": avg_end_hp, "start_hp": start_hp,
            "p1_death": p1_death / total_runs, "p1_dmg_fail": p1_dmg_fail / total_runs,
            "p2_death": p2_death / total_runs, "p2_dmg_fail": p2_dmg_fail / total_runs,
            "total_death": (p1_death + p2_death) / total_runs,
            "total_dmg_fail": (p1_dmg_fail + p2_dmg_fail) / total_runs,
        }
    return results


def report(label, p1_pattern, p1_hp, p2_pattern, p2_hp):
    res = eval_boss_weapon(p1_pattern, p1_hp, p2_pattern, p2_hp)
    rates = [r["win_rate"] for r in res.values()]
    avg_win = sum(rates) / len(rates)
    spread = max(rates) - min(rates)
    print(f"=== {label} (ONE WEAPON: Honed) ===")
    print(f"OVERALL AVG WIN RATE: {avg_win*100:.1f}%   SPREAD: {spread*100:.1f}pp "
          f"(max {max(rates)*100:.1f}% / min {min(rates)*100:.1f}%)")
    print(f"{'Class':12} {'Win%':7} {'EndHP':7} {'Start':6} {'Death%':8} {'DmgFail%':9}")
    print("-" * 55)
    for c, r in sorted(res.items(), key=lambda kv: -kv[1]['win_rate']):
        print(f"{c:12} {r['win_rate']*100:6.1f}% {r['avg_end_hp']:6.1f}  {r['start_hp']:5}  "
              f"{r['total_death']*100:7.1f}% {r['total_dmg_fail']*100:8.1f}%")
    print()
    return avg_win, spread, res


if __name__ == "__main__":
    bosses = {
        "Boss1 Malakor": ([(3, 0, "ranged"), (3, 2, "melee"), (4, 0, "ranged")], 10,
                          [(4, 0, "ranged"), (4, 1, "melee"), (4, 0, "ranged")], 10),
        "Boss2 Aethelgard": ([(2, 1, "melee"), (4, 0, "ranged"), (4, 0, "melee")], 11,
                             [(4, 0, "ranged"), (4, 0, "melee"), (5, 0, "ranged")], 10),
        "Boss3 Cheryl": ([(4, 0, "ranged"), (3, 2, "melee"), (3, 0, "ranged")], 10,
                         [(4, 1, "melee"), (4, 0, "ranged"), (4, 0, "melee")], 10),
    }
    for name, (p1, p1hp, p2, p2hp) in bosses.items():
        report(name, p1, p1hp, p2, p2hp)
