"""
Per-class survivability against constant, escalating attack -- how many of a class's 15
possible hands can survive all 3 rounds against a flat, fixed per-round ATK, swept upward,
against both a melee and a ranged dummy mob. Kept as a permanent, rerunnable tool (not a
one-off script) since it surfaces a real, structural asymmetry in the roster that no other
existing diagnostic checks: `damage_floor_ceiling` isolates pure damage output (ATK=0 dummy),
`defense_floor_sweep` checks survival against the real, locked mob roster (which currently
tops out at ATK=6, Elite's ceiling) -- neither one probes *beyond* the current game's actual
attack range, which is exactly where this matters. First run to answer a direct design
question: how much headroom is left before a future tier's mobs (if they lean on bigger flat
ATK numbers, the same way Elite already leans harder than Standard) start exposing a real gap
in the roster.

**The finding this tool exists to keep re-checkable, not just a one-off observation:** exactly
the 5 classes with any `grants_range` (At Range / evasion) card -- Wizard, Rogue, Ranger,
Runecaster, Necromancer -- show a real divergence between the melee and ranged charts, because
evasion negates a round's damage *entirely*, regardless of magnitude, while Block only
subtracts a flat amount whose relative value shrinks as ATK climbs. Warrior, Cleric, Paladin,
and Druid have zero evasion tools between them, so their two charts are always identical.
Necromancer is the sharpest case: 14/15 hands survive all 3 rounds at ATK=8 melee, but 0/15 at
the same ATK=8 ranged -- the roster's most exposed class against sustained ranged pressure
specifically, invisible unless ranged is checked separately from melee (see `OPEN_QUESTIONS.md`
and the hero-power-curve discussion this was built to support).

Run: python survivability_chart.py (from sim/).
"""
import condensed_trip as T


def _melee_pattern(mob_key, atk):
    return T._dummy_pattern(mob_key, atk=atk, block=0)


def _ranged_pattern(mob_key, atk):
    if mob_key in T._RANGE_TAGGED_MOB_KEYS:
        return [(atk, 0, "ranged")] * 3
    return [(atk, 0)] * 3  # no mob_type concept for these classes -- identical to the melee case


def _full_survivors(mod, has_stance, max_hp, pattern):
    """Count of hands (out of 15) whose best line survives all 3 rounds -- mob HP is set
    absurdly high (9999) so the mob is never actually killed; only the hero's own survival
    against the constant attack is being measured."""
    count = 0
    for hand in mod.ALL_HANDS:
        seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, pattern, 9999, max_hp)
        if rounds == 3:
            count += 1
    return count


def survivability_table(atk_levels=(2, 4, 6, 8, 10, 12, 14)):
    """Returns {"melee": {class_label: {atk: survivors_of_15}}, "ranged": {...}}."""
    table = {"melee": {}, "ranged": {}}
    for label, _ in T.CLASSES:
        mod = T.CARD_SOURCE_BY_LABEL[label]
        has_stance = T.HAS_STANCE_BY_LABEL[label]
        max_hp = float(getattr(mod, T.HP_ATTR_BY_LABEL[label]))
        mob_key = T.MOB_KEY_BY_LABEL[label]
        table["melee"][label] = {}
        table["ranged"][label] = {}
        for atk in atk_levels:
            table["melee"][label][atk] = _full_survivors(mod, has_stance, max_hp, _melee_pattern(mob_key, atk))
            table["ranged"][label][atk] = _full_survivors(mod, has_stance, max_hp, _ranged_pattern(mob_key, atk))
    return table


def print_chart(table, atk_levels=(2, 4, 6, 8, 10, 12, 14)):
    classes = [lbl for lbl, _ in T.CLASSES]
    for chart_name in ("melee", "ranged"):
        print(f"=== {chart_name.upper()} dummy -- hands (of 15) surviving all 3 rounds ===")
        header = f"{'ATK':>5s} | " + " | ".join(f"{c:>11s}" for c in classes)
        print(header)
        print("-" * len(header))
        for atk in atk_levels:
            row = f"{atk:5d} | "
            cells = [f"{table[chart_name][c][atk]}/15" for c in classes]
            row += " | ".join(f"{c:>11s}" for c in cells)
            print(row)
        print()


if __name__ == "__main__":
    print_chart(survivability_table())
