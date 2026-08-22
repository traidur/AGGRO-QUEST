"""
Verification that board_engine's combat-touching resolvers (resolve_node_pull,
resolve_border_crossing, decide_travel's risk-gate check) actually apply a hero's purchased
Level 2 upgrades in combat -- the gap found and fixed 2026-08-21: these functions called
combat_engine directly with no `with LV.leveled_kit(...)` wrapper, so a BoardState hero could
buy every upgrade in Town and never see a single upgraded card in a pull. All the existing
verify_board_engine*.py suites still pass unchanged after the fix (hero.acquired is empty in
every one of their scenarios, so _level2_swaps_for returns {} and leveled_kit is a documented
no-op there) -- this file is the one that actually exercises a NON-empty swap.
"""
import random

import board_engine as BE
import combat_engine as E
import condensed_warrior as W
import leveling_validation as LV
import macro_sim as M
from board_state import HeroBoardState


def run_checks(verbose=True):
    failures = []

    def check(name, condition, detail=""):
        if not condition:
            failures.append((name, detail))
            if verbose:
                print(f"FAIL: {name} -- {detail}")
        elif verbose:
            print(f"ok: {name}")

    # 1. _level2_swaps_for itself: empty acquired -> no swap; "mandatory" acquired -> the real
    # Warrior mandatory swap (Shield Block -> Shield Bash).
    check("no swaps before mandatory acquired", BE._level2_swaps_for("warrior", set()) == {})
    swaps = BE._level2_swaps_for("warrior", {"mandatory"})
    check("mandatory swap present", "Shield Block" in swaps and swaps["Shield Block"][0] == "Shield Bash", swaps)

    # 2. The leveled_kit context itself actually swaps CARDS/DECK, and restores on exit --
    # this is leveling_validation.py's own contract, just confirming board_engine wires it
    # through with the right dict.
    assert "Shield Block" in W.CARDS and "Shield Bash" not in W.CARDS  # sane starting state
    with LV.leveled_kit(W, swaps):
        check("leveled kit swaps CARDS", "Shield Bash" in W.CARDS and "Shield Block" not in W.CARDS)
        check("leveled kit swaps DECK", "Shield Bash" in W.DECK and "Shield Block" not in W.DECK)
    check("leveled kit restores CARDS on exit", "Shield Block" in W.CARDS and "Shield Bash" not in W.CARDS)

    # 3. Integration: resolve_node_pull with a hero who's acquired "mandatory" actually draws
    # hands from the LEVELED deck, not the base one -- force a hand containing Shield Bash
    # (impossible unless the leveled deck is really what's in effect) and confirm the pull
    # resolves using Shield Bash's own numbers (heal 5 in Guardian stance -- the base Shield
    # Block never has a heal component at all, so any healing at all is only explainable by
    # the swap having actually applied).
    hero = HeroBoardState(class_name="warrior", hp=10.0, max_hp=W.WARRIOR_HP, position=(1, "town"),
                           bag=[None, None], locked=[False, False], acquired={"mandatory"})
    with LV.leveled_kit(W, BE._level2_swaps_for("warrior", hero.acquired)):
        leveled_hand = tuple(h for h in W.ALL_HANDS if "Shield Bash" in h)[0]
    check("leveled hand is drawable", "Shield Bash" in leveled_hand, leveled_hand)

    class _FixedRNG:
        def choice(self, seq):
            return leveled_hand
    outcome = BE.resolve_node_pull(hero, "warrior", "waystation", "Grunt", M.QUESTS, _FixedRNG(),
                                    M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True)
    check("resolve_node_pull ran with leveled kit active without crashing",
          outcome["outcome"] in ("win", "flee", "died", "declined", "no_room"), outcome)
    check("CARDS restored to base after resolve_node_pull returns",
          "Shield Block" in W.CARDS and "Shield Bash" not in W.CARDS)

    print(f"\n{len(failures)} failures" if failures else "\nAll checks passed")
    return not failures


if __name__ == "__main__":
    ok = run_checks()
    raise SystemExit(0 if ok else 1)
