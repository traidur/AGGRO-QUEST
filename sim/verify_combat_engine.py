"""
Permanent regression tool: proves sim/combat_engine.py's turn-by-turn get_legal_actions/
apply_action/QuestIntelligence.decide_combat loop reproduces each class's own,
independently-tested best_line_for_hand()+simulate() bit-for-bit -- the single load-bearing
check named in unified-sprouting-aurora.md's Part 4. Exhaustive across every locked hand x
every Standard mob, for all 9 classes, at full HP AND at reduced starting HP (macro_sim.py's
real carried-over-HP-between-pulls case). Run this after ANY change to combat_engine.py or any
condensed_<class>.py's resolve_round -- a mismatch here means the turn-by-turn engine has
drifted from the balance-tested solver, which invalidates every locked number downstream.

The reduced-HP sweep exists because a full-HP-only check passed 810/810 while still hiding a
real bug: combat_engine.py originally seeded a fresh pull's healing cap (hero_max_hp) from
whatever starting_hp was passed in, rather than each class's own fixed HP constant the way
Cleric/Paladin/Runecaster/Druid/Necromancer's real simulate() always does (see
combat_engine.initial_max_hp()'s docstring). At full HP the two are numerically identical, so
every check here originally passed anyway -- the bug only showed up in macro_sim.py's chained
decay_stress_test, where HP genuinely carries over below max between pulls. Caught 2026-08-21
via that divergence, not via this tool -- this sweep exists so the next version of this bug
gets caught here instead."""
import combat_engine as E
import condensed_trip as T

REDUCED_HP_FRACTIONS = (1.0, 0.5, 0.25)


def _old_result(class_name, hand, pattern, mob_hp, starting_hp):
    mod = E.CARD_SOURCE[class_name]
    if class_name == "warrior":
        seq_cards, stance_seq, hp_left, rounds = mod.best_line_for_hand(
            hand, pattern, mob_hp, starting_hp=starting_hp)
        return mod.simulate(seq_cards, stance_seq, pattern, mob_hp, starting_hp=starting_hp)
    seq_cards, hp_left, rounds = mod.best_line_for_hand(hand, pattern, mob_hp, starting_hp=starting_hp)
    return mod.simulate(seq_cards, pattern, mob_hp, starting_hp=starting_hp)


def _new_result(class_name, hand, mob_name, pattern, mob_hp, starting_hp):
    state = E.new_pull_with_hp(class_name, mob_name, hand, pattern, mob_hp, starting_hp)
    ai = E.QuestIntelligence()
    while state.outcome is None:
        actions = E.get_legal_actions(state)
        action = ai.decide_combat(state, actions)
        state = E.apply_action(state, action)
    return state.outcome == "win", state.hero_hp


def verify_class(class_name, verbose=False):
    mod = E.CARD_SOURCE[class_name]
    full_hp = float(getattr(mod, E.HP_ATTR[class_name]))
    mismatches = []
    total = 0
    for hand in mod.ALL_HANDS:
        for mob_name in T.MOB_NAMES:
            pattern, mob_hp = T.MOBS[mob_name][class_name]
            for frac in REDUCED_HP_FRACTIONS:
                starting_hp = round(full_hp * frac, 1)
                total += 1
                old_win, old_hp, _ = _old_result(class_name, hand, pattern, mob_hp, starting_hp)
                new_win, new_hp = _new_result(class_name, hand, mob_name, pattern, mob_hp, starting_hp)

                if (old_win, old_hp) != (new_win, new_hp):
                    mismatches.append((hand, mob_name, starting_hp, (old_win, old_hp), (new_win, new_hp)))
                    if verbose:
                        print(f"MISMATCH {class_name} hand={hand} mob={mob_name} "
                              f"starting_hp={starting_hp}: old={(old_win, old_hp)} new={(new_win, new_hp)}")
    return total, mismatches


def verify_all(verbose=False):
    grand_total = 0
    grand_mismatches = 0
    for class_name in E.CARD_SOURCE:
        total, mismatches = verify_class(class_name, verbose=verbose)
        grand_total += total
        grand_mismatches += len(mismatches)
        status = "OK" if not mismatches else f"{len(mismatches)} MISMATCHES"
        print(f"{class_name:12s} {total:4d} combos  {status}")
    print(f"\nTotal: {grand_total} combos, {grand_mismatches} mismatches")
    return grand_mismatches == 0


if __name__ == "__main__":
    ok = verify_all(verbose=True)
    raise SystemExit(0 if ok else 1)
