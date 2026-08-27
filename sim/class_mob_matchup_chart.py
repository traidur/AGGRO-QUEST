"""
Per-class, per-mob matchup chart -- cost% and win% for every locked class against every
locked Standard-tier mob (Level 1) or Standard+Elite mob (Level 2), single-pull, full HP.
Kept as a permanent, rerunnable tool (not a one-off script) since this answers a real,
recurring design question: "which mobs favor which class," first asked when considering
whether to surface matchup info to players at class-select time to motivate node choice (see
OPEN_QUESTIONS.md) -- and, as of 2026-08-26, actually IS surfaced to players, via
playtest_board_web.py's "Class Guide" modal, which computes both tables once at app start by
calling matchup_table(level=1) and matchup_table(level=2) directly rather than the frozen,
hand-typed numbers an earlier pass had baked in (a real bug -- see LEVELING_GUIDE.md/this
session's audit notes for why a static snapshot can't stay correct here).

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

Level 2 uses each class's FULLY upgraded kit (mandatory + every purchased upgrade), via
board_engine._level2_swaps_for -- not a per-hero snapshot. A real hero's actual kit can differ
(Level 2 purchased-upgrade order is randomized per hero, locked 2026-08-23), so this is
deliberately "best available reference for this class at this level," not "this exact hero's
current deck" -- a reasonable simplification for a rough matchup guide, not a precision tool.
Classes with no Level 2 kit built yet (Druid, Necromancer as of 2026-08-26) fall back to their
Level 1 numbers unchanged, rather than erroring.

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
import leveling_validation as LV
import macro_sim as M

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


def _full_upgrade_swaps(mob_key):
    """All purchased upgrades + mandatory, for whichever classes have Level 2 content built --
    a local import of board_engine (not a module-level one) since board_engine itself imports
    macro_sim and this file is imported by playtest_board_web.py alongside it; keeping the
    import inside the function avoids giving this a load-bearing import-order dependency on a
    much bigger module just for one helper call."""
    import board_engine as BE
    if mob_key not in M.LEVEL2_MANDATORY:
        return {}
    acquired = {"mandatory"} | {f"skill_{i}" for i in range(len(M.LEVEL2_PURCHASED_ORDER.get(mob_key, [])))}
    return BE._level2_swaps_for(mob_key, acquired)


def matchup_table(level=1):
    """Returns {class_label: {mob_name: (cost_pct, win_pct)}}. level=1: base kit vs the 6
    Standard mobs. level=2: fully-upgraded kit (see _full_upgrade_swaps) vs the same 6 Standard
    mobs plus the 3 Elites (Bulwark/Berserker/Warlord) -- see this module's own docstring for
    why "fully upgraded" rather than any one specific hero's actual current kit."""
    table = {}
    for cls, (mod, has_stance, max_hp, mob_key) in SPECS.items():
        table[cls] = {}
        swaps = _full_upgrade_swaps(mob_key) if level >= 2 else {}
        with LV.leveled_kit(mod, swaps):
            entries = [(mob_name, T.MOBS[mob_name][mob_key]) for mob_name in T.MOB_NAMES]
            if level >= 2:
                entries += [(name, (LV._elite_pattern(mob_key, name), LV.ELITE_HP))
                            for name in LV.ELITE_MELEE]
            for mob_name, (pattern, mob_hp) in entries:
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


def print_chart(table, label="Level 1"):
    # mob_names read from the table itself, not T.MOB_NAMES -- a Level 2 table also includes
    # the 3 Elites, which aren't in T.MOB_NAMES.
    mob_names = list(next(iter(table.values())).keys())
    print(f"### {label} ###")
    print("=== Cost% (avg HP spent per pull, win or lose) -- lower means the class finds that mob easier ===")
    header = "Class       | " + " | ".join(f"{m:9s}" for m in mob_names)
    print(header)
    print("-" * len(header))
    for cls in table:
        row = " | ".join(f"{table[cls][m][0]:8.1f}%" for m in mob_names)
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
    header = "Class       | " + " | ".join(f"{m:9s}" for m in mob_names)
    print(header)
    print("-" * len(header))
    for cls in table:
        row = " | ".join(f"{table[cls][m][1]:8.1f}%" for m in mob_names)
        print(f"{cls:11s} | {row}")


if __name__ == "__main__":
    print_chart(matchup_table(level=1), "Level 1")
    print()
    print_chart(matchup_table(level=2), "Level 2 (fully upgraded)")
