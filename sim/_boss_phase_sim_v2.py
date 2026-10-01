"""
Boss Phase Simulation v2 -- fixes _boss_phase_sim.py's single bug: format_pattern tagged
EVERY round "melee" for the 5 classes whose simulate() needs a 3rd tuple element
(wizard/rogue/ranger/runecaster/necromancer -- rogue needs the 3-tuple shape to not crash its
unpack even though it has no grants_range field; the other 4 genuinely read mob_type for
grants_range). That made every boss round evadable by Wizard/Ranger/Necromancer/Runecaster's
grants_range cards (confirmed via direct grep of the 9 condensed_<class>.py files -- Rogue has
no grants_range card at all, so its RANGE_CLASSES membership is format-compatibility only, not
a design intent). This version takes the per-round TYPE as part of the pattern definition
itself, same way Scout (the one ranged Standard mob) already prints a type per round in the
real game -- nothing new mechanically, just varying it round-to-round on one card instead of
holding it fixed for all 3, which the existing mob_atk, mob_block, mob_type =
mob_pattern[round_num] unpack in every RANGE_CLASSES simulate() already supports natively.

eval_boss's own win/death/dmg_fail accounting is UNCHANGED from the original -- a Phase 1
loss (not dead by round 3) is already counted as a clean fail (not win2), same ruling as any
other mob flee in this game (no partial credit, no new rule). That's correct as originally
written; nothing to fix there.
"""

import sys
sys.path.insert(0, 'sim')
import itertools
import macro_sim as M
import leveling_validation as LV

CLASSES = list(M.CARD_SOURCE.keys())
NEEDS_3TUPLE = {"wizard", "rogue", "ranger", "runecaster", "necromancer"}


def format_pattern(raw_pattern, class_name):
    """raw_pattern: list of (atk, blk, type) tuples, one per round, type already specified
    per-round by the caller (e.g. [(3,0,"melee"), (3,1,"ranged"), (3,0,"ranged")]).
    Classes outside NEEDS_3TUPLE strictly unpack 2-tuples (mob_atk, mob_block = ...) and
    crash on a 3-tuple, so those get projected down; the 5 that need 3 elements keep the
    real, per-round type instead of always "melee"."""
    if class_name in NEEDS_3TUPLE:
        return [(atk, blk, typ) for atk, blk, typ in raw_pattern]
    return [(atk, blk) for atk, blk, typ in raw_pattern]


def simulate_phase(mod, class_name, hand, pattern, mob_hp, current_hp):
    if class_name == "warrior":
        seq_cards, stance_seq, hp_left, rounds = mod.best_line_for_hand(
            hand, pattern, mob_hp, starting_hp=current_hp
        )
        win, final_hp, final_rounds = mod.simulate(
            seq_cards, stance_seq, pattern, mob_hp, starting_hp=current_hp
        )
    else:
        seq_cards, hp_left, rounds = mod.best_line_for_hand(
            hand, pattern, mob_hp, starting_hp=current_hp
        )
        win, final_hp, final_rounds = mod.simulate(
            seq_cards, pattern, mob_hp, starting_hp=current_hp
        )
    return win, final_hp, final_rounds


def eval_boss(p1_pattern, p1_hp, p2_pattern, p2_hp, classes=None):
    """p1_pattern/p2_pattern: list of 3 (atk, blk, type) tuples, type per round explicit."""
    classes = classes or CLASSES
    results = {}
    for class_name in classes:
        mod = M.CARD_SOURCE[class_name]
        start_hp = getattr(mod, M.HP_ATTR[class_name])
        mand = M.LEVEL2_MANDATORY[class_name]
        purch = M.LEVEL2_PURCHASED_ORDER[class_name]

        c_pat1 = format_pattern(p1_pattern, class_name)
        c_pat2 = format_pattern(p2_pattern, class_name)

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
                    win1, hp1, r1 = simulate_phase(mod, class_name, h1, c_pat1, p1_hp, start_hp)
                    if not win1:
                        for _ in hands:
                            total_runs += 1
                            if hp1 <= 0:
                                p1_death += 1
                            else:
                                p1_dmg_fail += 1
                        continue

                    for h2 in hands:
                        total_runs += 1
                        win2, hp2, r2 = simulate_phase(mod, class_name, h2, c_pat2, p2_hp, hp1)
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
            "win_rate": win_rate,
            "avg_end_hp": avg_end_hp,
            "start_hp": start_hp,
            "p1_death": p1_death / total_runs,
            "p1_dmg_fail": p1_dmg_fail / total_runs,
            "p2_death": p2_death / total_runs,
            "p2_dmg_fail": p2_dmg_fail / total_runs,
            "total_death": (p1_death + p2_death) / total_runs,
            "total_dmg_fail": (p1_dmg_fail + p2_dmg_fail) / total_runs,
        }
    return results


def report(label, p1_pattern, p1_hp, p2_pattern, p2_hp):
    res = eval_boss(p1_pattern, p1_hp, p2_pattern, p2_hp)
    rates = [r["win_rate"] for r in res.values()]
    avg_win = sum(rates) / len(rates)
    spread = max(rates) - min(rates)
    print(f"=== {label} ===")
    print(f"P1: {p1_hp} HP {p1_pattern}")
    print(f"P2: {p2_hp} HP {p2_pattern}")
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
    # Candidate A: round 1 melee, rounds 2-3 ranged, per phase -- user's original damage
    # budget (~8-9 P1, ~9-10 P2), low/no Block matching the Elite-tier convention
    # (ELITE_MELEE: Bulwark/Berserker/Warlord all sit at 0-1 Block per round, never higher).
    report(
        "Candidate A",
        [(3, 1, "melee"), (3, 0, "ranged"), (3, 0, "ranged")], 8,
        [(4, 0, "melee"), (3, 0, "ranged"), (3, 0, "ranged")], 8,
    )

    # Candidate B: same type pattern, HP and damage both pushed up substantially
    report(
        "Candidate B",
        [(5, 1, "melee"), (5, 0, "ranged"), (5, 0, "ranged")], 11,
        [(6, 0, "melee"), (5, 0, "ranged"), (6, 0, "ranged")], 11,
    )

    # Candidate C: midpoint between A (too easy) and B (too hard)
    report(
        "Candidate C",
        [(4, 1, "melee"), (4, 0, "ranged"), (3, 0, "ranged")], 9,
        [(4, 0, "melee"), (4, 0, "ranged"), (4, 0, "ranged")], 9,
    )

    # Candidate D: push further from C toward B
    report(
        "Candidate D",
        [(4, 1, "melee"), (5, 0, "ranged"), (4, 0, "ranged")], 10,
        [(5, 0, "melee"), (4, 0, "ranged"), (5, 0, "ranged")], 10,
    )

    # Candidate E: slightly lower damage, more HP (longer fight) to let sustain classes catch up
    report(
        "Candidate E",
        [(4, 1, "melee"), (4, 0, "ranged"), (4, 0, "ranged")], 11,
        [(4, 0, "melee"), (4, 0, "ranged"), (4, 0, "ranged")], 11,
    )

    # Candidate F: same as D but zero Block everywhere (isolate Block's own contribution)
    report(
        "Candidate F (D, zero Block)",
        [(4, 0, "melee"), (5, 0, "ranged"), (4, 0, "ranged")], 10,
        [(5, 0, "melee"), (4, 0, "ranged"), (5, 0, "ranged")], 10,
    )

    # User candidate: "The Sunward Archon / Inquisitor"
    report(
        "Sunward Archon/Inquisitor",
        [(3, 1, "ranged"), (3, 1, "melee"), (4, 0, "ranged")], 10,
        [(4, 1, "ranged"), (4, 0, "melee"), (4, 0, "ranged")], 10,
    )

    # Boss 2: "The Hollow Commander" -- Risen Dead champion of the Long War
    report(
        "The Hollow Commander",
        [(4, 0, "ranged"), (3, 1, "melee"), (3, 1, "ranged")], 9,
        [(4, 1, "ranged"), (4, 0, "melee"), (5, 0, "ranged")], 10,
    )

    # Boss 3: "The Pyre Warden" -- zealot guardian of the Consuming Pyre
    report(
        "The Pyre Warden",
        [(4, 1, "melee"), (3, 0, "ranged"), (4, 1, "ranged")], 11,
        [(4, 0, "ranged"), (3, 1, "melee"), (5, 0, "ranged")], 9,
    )

    # Boss 2 v2: nudge damage up slightly to pull average down toward target
    report(
        "The Hollow Commander v2",
        [(4, 0, "ranged"), (4, 1, "melee"), (3, 1, "ranged")], 9,
        [(4, 1, "ranged"), (4, 0, "melee"), (5, 0, "ranged")], 10,
    )

    # Boss 3 v2: ease P2's finisher hit, raise P2 HP slightly for a gentler ramp
    report(
        "The Pyre Warden v2",
        [(4, 1, "melee"), (3, 0, "ranged"), (4, 1, "ranged")], 11,
        [(4, 0, "ranged"), (3, 1, "melee"), (4, 0, "ranged")], 10,
    )

    # Boss 3 v3: cut P1 HP, drop to one Block round total in P1 (was two) to ease kill-speed bottleneck
    report(
        "The Pyre Warden v3",
        [(4, 1, "melee"), (3, 0, "ranged"), (4, 0, "ranged")], 9,
        [(4, 0, "ranged"), (3, 1, "melee"), (4, 0, "ranged")], 10,
    )

    # Boss 3 v4: keep the single-Block-round structure, raise raw damage to bring average down
    report(
        "The Pyre Warden v4",
        [(5, 1, "melee"), (4, 0, "ranged"), (4, 0, "ranged")], 10,
        [(5, 0, "ranged"), (4, 1, "melee"), (5, 0, "ranged")], 10,
    )

    # Boss 3 v5: midpoint between v3 (too easy) and v4 (too hard)
    report(
        "The Pyre Warden v5",
        [(4, 1, "melee"), (4, 0, "ranged"), (4, 0, "ranged")], 10,
        [(4, 0, "ranged"), (4, 1, "melee"), (4, 0, "ranged")], 10,
    )

    # Boss 3 v6: P1 unchanged from v3 (good spread), only P2 pushed harder
    report(
        "The Pyre Warden v6",
        [(4, 1, "melee"), (3, 0, "ranged"), (4, 0, "ranged")], 9,
        [(5, 0, "ranged"), (4, 1, "melee"), (4, 0, "ranged")], 10,
    )

    # Boss 3 v7: small further nudge to P2's last round
    report(
        "The Pyre Warden v7",
        [(4, 1, "melee"), (3, 0, "ranged"), (4, 0, "ranged")], 9,
        [(5, 0, "ranged"), (4, 1, "melee"), (5, 0, "ranged")], 10,
    )

    # Double-check: Gemini's latest 3 bosses, claimed 77.1/77.9/77.6% win, 17.9/22.7/16.1% spread
    report(
        "Boss 1: High Inquisitor Malakor",
        [(3, 0, "ranged"), (3, 2, "melee"), (4, 0, "ranged")], 10,
        [(4, 0, "ranged"), (4, 1, "melee"), (4, 0, "ranged")], 10,
    )
    report(
        "Boss 2: Aethelgard the Sun-Forged",
        [(2, 1, "melee"), (4, 0, "ranged"), (4, 0, "melee")], 11,
        [(4, 0, "ranged"), (4, 0, "melee"), (5, 0, "ranged")], 10,
    )
    report(
        "Boss 3: Cheryl the Sun-Dethroned",
        [(4, 0, "ranged"), (3, 2, "melee"), (3, 0, "ranged")], 10,
        [(4, 1, "melee"), (4, 0, "ranged"), (4, 0, "melee")], 10,
    )
