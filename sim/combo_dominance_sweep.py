"""
Roster-wide sweep for near-automatic 2-card combos -- every card pair, within every locked
class's own 6-card kit, checked with condensed_trip.combo_dominance_report. Kept as a
permanent, rerunnable tool (not a one-off script) since this answers a real, recurring design
question: "is there a pair of cards a player would learn to always play together, in the same
order, within a handful of real hands" -- first asked 2026-08-28 after Necromancer's
Blight + Death Blow turned out to be exactly that (94.4% co-played whenever both are dealt,
100% fixed order, found by the user just playing a half-dozen hands by hand). Re-run whenever a
class's kit changes -- a combo that isn't dominant today can become one after a card gets
tuned.

Flags a pair as worth a human look when BOTH: (a) it's dominant enough to matter -- co-played in
at least DOMINANCE_THRESHOLD of scored (non-tied) hand/mob pairs, and (b) it's not just
"usually good" but a single fixed pattern -- the two cards, whenever played together, always
resolve in the same round-order (one direction only, zero cases of the reverse). A pair that's
merely "strong when it comes up" but flips order depending on the mob, or that only reaches
moderate co-play rates, isn't what this is looking for -- those are ordinary good cards, not the
kind of "figure it out in six hands, then it's not really a decision anymore" pattern this
exists to catch.

Run: python combo_dominance_sweep.py (from sim/).
"""
import itertools

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

DOMINANCE_THRESHOLD = 0.80  # co-played in at least this fraction of scored hand/mob pairs


def sweep_class(cls_label, mod, has_stance, max_hp, mob_key):
    """Every unordered pair from this class's real 6-card DECK (never the virtual Boneguard's
    Offering (Boosted)-style variant, if any -- those live in CARDS but not DECK, exactly so a
    pairing sweep like this one doesn't need to special-case them out). Returns a list of
    (card_a, card_b, overall_pct, direction) for every pair, sorted by overall_pct descending --
    direction is 'a_then_b'/'b_then_a' if one-directional whenever co-played, else 'mixed'."""
    results = []
    for card_a, card_b in itertools.combinations(mod.DECK, 2):
        report = T.combo_dominance_report(mod, has_stance, mob_key, max_hp, card_a, card_b)
        total_together = sum(r["together"] for r in report["per_mob"].values())
        total_scored = sum(r["together"] + r["apart"] for r in report["per_mob"].values())
        if total_scored == 0:
            continue
        overall_pct = total_together / total_scored
        total_a_then_b = sum(r["a_then_b"] for r in report["per_mob"].values())
        total_b_then_a = sum(r["b_then_a"] for r in report["per_mob"].values())
        if total_a_then_b > 0 and total_b_then_a == 0:
            direction = "a_then_b"
        elif total_b_then_a > 0 and total_a_then_b == 0:
            direction = "b_then_a"
        else:
            direction = "mixed"
        results.append((card_a, card_b, overall_pct, direction, total_together, total_scored))
    results.sort(key=lambda r: -r[2])
    return results


def run_all(verbose=True):
    flagged = {}
    for cls_label, (mod, has_stance, max_hp, mob_key) in SPECS.items():
        results = sweep_class(cls_label, mod, has_stance, max_hp, mob_key)
        hits = [r for r in results if r[2] >= DOMINANCE_THRESHOLD and r[3] != "mixed"]
        flagged[cls_label] = hits
        if verbose:
            print(f"=== {cls_label} ===")
            if not hits:
                top = results[0] if results else None
                if top:
                    print(f"  no dominant fixed-order combo found "
                          f"(closest: {top[0]!r} + {top[1]!r} at {100*top[2]:.1f}%, direction={top[3]})")
                else:
                    print("  no card pairs to check")
            for card_a, card_b, pct, direction, together, scored in hits:
                order = f"{card_a} -> {card_b}" if direction == "a_then_b" else f"{card_b} -> {card_a}"
                print(f"  FLAGGED: {card_a!r} + {card_b!r}  {100*pct:.1f}% co-played "
                      f"({together}/{scored} scored pairs), always {order}")
            print()
    return flagged


if __name__ == "__main__":
    run_all()
