"""
Per-class, per-mob matchup chart -- cost% and win% for every locked class against every
locked Standard-tier mob, single-pull, full HP. Kept as a permanent, rerunnable tool (not a
one-off script) since this answers a real, recurring design question: "which mobs favor which
class," first asked when considering whether to surface matchup info to players at class-
select time to motivate node choice (see OPEN_QUESTIONS.md).

Why cost%, not win rate, is the metric that actually differentiates: win rate is a hard
binary cliff, quantized to multiples of 1/15 per class (only 15 possible hands) -- there's no
way to land at exactly 50%, and most classes already sit at 93.3-100% against most Standard
mobs by design (the roster was tuned to be broadly winnable everywhere, per the locked
"mobs must stay class-agnostic" rule). That leaves almost no signal to build a "shines here,
struggles there" mechanic on. Cost% (average HP spent per pull, win or lose, as a percentage
of max HP) is a continuous measure and was already found to be the metric that actually
differentiates cleanly in the Elite-derivation work (see CLASS_BALANCE_GUIDE.md's "Elite
trio, derived" section) -- same formula reused here directly: for the best line per hand,
cost = max_hp - hp_left, cost% = 100 * mean(cost) / max_hp.

Run: python class_mob_matchup_chart.py (from sim/).
"""
import condensed_trip as T
import condensed_warrior as W
import condensed_wizard as Z
import condensed_cleric as C
import condensed_paladin as P
import condensed_rogue as R
import condensed_ranger as G
import condensed_runecaster as N
import condensed_druid as Du
import condensed_necromancer as Nc

T.register_class_for_testing("necromancer", needs_range_tag=True)

SPECS = {
    "Warrior": (W, True, W.WARRIOR_HP, "warrior"),
    "Wizard": (Z, False, Z.WIZARD_HP, "wizard"),
    "Cleric": (C, False, C.CLERIC_HP, "cleric"),
    "Paladin": (P, False, P.PALADIN_HP, "paladin"),
    "Rogue": (R, False, R.ROGUE_HP, "rogue"),
    "Ranger": (G, False, G.RANGER_HP, "ranger"),
    "Runecaster": (N, False, N.RUNECASTER_HP, "runecaster"),
    "Druid": (Du, False, Du.DRUID_HP, "druid"),
    "Necromancer": (Nc, False, Nc.NECROMANCER_HP, "necromancer"),
}


def matchup_table():
    """Returns {class_label: {mob_name: (cost_pct, win_pct)}}."""
    table = {}
    for cls, (mod, has_stance, max_hp, mob_key) in SPECS.items():
        table[cls] = {}
        for mob_name in T.MOB_NAMES:
            pattern, mob_hp = T.MOBS[mob_name][mob_key]
            costs, wins = [], []
            for hand in mod.ALL_HANDS:
                seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, pattern, mob_hp, max_hp)
                win, final_hp, final_rounds = T._simulate(mod, has_stance, seq, stance, pattern, mob_hp, max_hp)
                costs.append(max_hp - hp_left)
                wins.append(win)
            cost_pct = 100 * (sum(costs) / len(costs)) / max_hp
            win_pct = 100 * sum(wins) / len(wins)
            table[cls][mob_name] = (cost_pct, win_pct)
    return table


def print_chart(table):
    print("=== Cost% (avg HP spent per pull, win or lose) -- lower means the class finds that mob easier ===")
    header = "Class       | " + " | ".join(f"{m:9s}" for m in T.MOB_NAMES)
    print(header)
    print("-" * len(header))
    for cls in table:
        row = " | ".join(f"{table[cls][m][0]:8.1f}%" for m in T.MOB_NAMES)
        print(f"{cls:11s} | {row}")

    print()
    print("=== Per-class: easiest and hardest mob by cost%, and the spread between them ===")
    for cls in table:
        by_cost = sorted(table[cls].items(), key=lambda kv: kv[1][0])
        easiest, hardest = by_cost[0], by_cost[-1]
        spread = hardest[1][0] - easiest[1][0]
        print(f"  {cls:11s} easiest={easiest[0]:10s}({easiest[1][0]:.1f}%)   "
              f"hardest={hardest[0]:10s}({hardest[1][0]:.1f}%)   spread={spread:.1f}pp")

    print()
    print("=== Win% for reference (mostly saturated near 93-100%, shown to confirm low differentiation) ===")
    header = "Class       | " + " | ".join(f"{m:9s}" for m in T.MOB_NAMES)
    print(header)
    print("-" * len(header))
    for cls in table:
        row = " | ".join(f"{table[cls][m][1]:8.1f}%" for m in T.MOB_NAMES)
        print(f"{cls:11s} | {row}")


if __name__ == "__main__":
    print_chart(matchup_table())
