"""
Bit-for-bit regression check: equipment_solver.best_line_with_equipment(..., equipment={})
must reproduce each class's own real, trusted best_line_for_hand()/simulate() exactly.

Exists because this check was skipped before equipment_solver.py's numbers were trusted for
real balance conclusions (see EQUIPMENT_HANDOFF.md) -- a bug (equipment_solver.py rebuilding
hand-ordering logic from itertools.permutations instead of calling each class's own
orderings()) silently dropped Necromancer's Death Pact variant from every equipped search,
and was only caught by chance via a manual spot-check, not a systematic one. This is the
systematic one: run it before trusting ANY new equipment_solver.py number, the same way
verify_combat_engine.py is run before trusting combat_engine.py's numbers.

Checked with the FULL hand space (mod.ALL_HANDS) x the full mob roster (condensed_trip.MOBS),
not a sample -- cheap here since equipment={} means best_line_with_equipment's equipment-usage
permutation loop degenerates to a single no-op pass, so this is the same cost as calling each
class's own solver twice.
"""
import condensed_trip as T
from combat_engine import CARD_SOURCE
from equipment_solver import best_line_with_equipment

CLASSES = ["warrior", "wizard", "cleric", "paladin", "rogue", "ranger", "runecaster", "druid", "necromancer"]
STANCE_CLASSES = {"warrior"}  # only Warrior has a real stance mechanic -- Paladin's
# best_line_for_hand/simulate never take or return one (checked directly in condensed_paladin.py)


def main():
    total_checked = 0
    total_mismatches = 0
    for cls in CLASSES:
        mod = CARD_SOURCE[cls]
        cls_mismatches = 0
        cls_checked = 0
        for mob_name in T.MOB_NAMES:
            pattern, mob_hp = T.MOBS[mob_name][cls]
            for hand in mod.ALL_HANDS:
                for starting_hp in (mob_hp, mob_hp / 2, 3):  # a few HP levels, not just one
                    cls_checked += 1
                    if cls in STANCE_CLASSES:
                        seq_ref, stance_ref, hp_ref, rounds_ref = mod.best_line_for_hand(
                            hand, pattern, mob_hp, starting_hp=starting_hp)
                        win_ref, hp_ref2, rounds_ref2 = mod.simulate(
                            seq_ref, stance_ref, pattern, mob_hp, starting_hp=starting_hp)
                    else:
                        seq_ref, hp_ref, rounds_ref = mod.best_line_for_hand(
                            hand, pattern, mob_hp, starting_hp=starting_hp)
                        stance_ref = None
                        win_ref, hp_ref2, rounds_ref2 = mod.simulate(
                            seq_ref, pattern, mob_hp, starting_hp=starting_hp)

                    win_eq, seq_eq, stance_eq, hp_eq, rounds_eq, usage_eq = best_line_with_equipment(
                        cls, hand, pattern, mob_hp, starting_hp, {})

                    # Compare the actual outcome (win, hp_left, rounds), not the raw sequence --
                    # two different orderings can be equally optimal (ties), so sequence
                    # equality is too strict a check and would false-positive on real ties.
                    if (win_eq, hp_eq, rounds_eq) != (win_ref, hp_ref2, rounds_ref2):
                        cls_mismatches += 1
                        total_mismatches += 1
                        if cls_mismatches <= 3:
                            print(f"MISMATCH {cls} mob={mob_name} hp0={starting_hp} hand={hand}")
                            print(f"  reference: seq={seq_ref} stance={stance_ref} -> hp={hp_ref2} rounds={rounds_ref2}")
                            print(f"  equipment_solver: seq={seq_eq} stance={stance_eq} -> hp={hp_eq} rounds={rounds_eq}")
        total_checked += cls_checked
        status = "OK" if cls_mismatches == 0 else f"{cls_mismatches} MISMATCHES"
        print(f"{cls:12s} {cls_checked:5d} checked  {status}")

    print(f"\nTotal: {total_checked} checked, {total_mismatches} mismatches")
    if total_mismatches == 0:
        print("equipment_solver.py's zero-equipment path is verified bit-for-bit against every class's real solver.")


if __name__ == "__main__":
    main()
