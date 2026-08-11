"""
Terminal front end for condensed combat -- calls playtest_engine directly,
same engine the web front end (playtest_web.py) uses. Exists as a fast
no-browser sanity check and to prove the engine has no web-specific coupling.

Usage:
    python playtest_cli.py --class warrior --mob Brute
    python playtest_cli.py --class wizard --mob Sentinel --seed 7
"""
from __future__ import annotations

import argparse

import condensed_trip as T
import playtest_engine as E


def _fmt_pattern(pattern, round_num):
    parts = []
    for i, rnd in enumerate(pattern):
        atk, block = rnd[0], rnd[1]
        marker = ">>" if i == round_num else "  "
        parts.append(f"{marker}R{i+1}: ATK {atk} / Block {block}")
    return "\n".join(parts)


def _fmt_action(i, a):
    if not a["legal"]:
        stance_str = f" [{a['stance']}]" if a["stance"] else ""
        return f"  {i}) {a['card']}{stance_str} -- ILLEGAL this round"
    stance_str = f" [{a['stance']}]" if a["stance"] else ""
    return (f"  {i}) {a['card']}{stance_str} -- "
            f"dmg {a['dmg_dealt']:.0f} to mob, take {a['dmg_taken']:.0f}  "
            f"(you: {a['resulting_hp']:.0f} HP, mob: {a['resulting_mob_hp']:.0f} HP left)")


def play(class_name: str, mob_name: str, seed: int = None):
    state = E.new_pull(class_name, mob_name, seed=seed)
    print(f"\n=== {class_name.title()} vs {mob_name} ===")
    print(f"Hand: {', '.join(state.hand)}")
    print(f"Mob HP: {state.mob_hp_total:.0f}\n{_fmt_pattern(state.mob_pattern, 0)}\n")

    while state.outcome is None:
        print(f"--- Round {state.round_num + 1} --- (you: {state.hero_hp:.0f} HP, "
              f"mob: {state.mob_hp_remaining:.0f} HP)")
        actions = E.legal_actions(state)
        for i, a in enumerate(actions):
            print(_fmt_action(i, a))
        choice = input("Play: ").strip()
        try:
            idx = int(choice)
            a = actions[idx]
        except (ValueError, IndexError):
            print("Invalid choice.")
            continue
        if not a["legal"]:
            print("That's not legal this round.")
            continue
        state = E.apply_action(state, a["card"], a["stance"])
        print()

    print(f"=== Result: {state.outcome.upper()} ===")
    print(f"Cards played: {', '.join(state.played)}")
    print(f"Final HP: {state.hero_hp:.0f}, mob HP remaining: {state.mob_hp_remaining:.0f}\n")

    reveal = E.best_line_reveal(state)
    stance_str = f" (stances: {reveal['stance_sequence']})" if reveal["stance_sequence"] else ""
    print(f"Solver's optimal line for this hand: {reveal['sequence']}{stance_str}")
    print(f"  -> {'WIN' if reveal['win'] else 'LOSS/TIMEOUT'}, HP left: {reveal['hp_left']:.0f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class", dest="class_name", required=True,
                         choices=["warrior", "wizard", "cleric"])
    parser.add_argument("--mob", required=True, choices=list(T.MOBS.keys()))
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    play(args.class_name, args.mob, seed=args.seed)


if __name__ == "__main__":
    main()
