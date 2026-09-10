"""
Full cross-class, per-ingredient equipment balance sweep -- built to answer one question
directly: is equipment balanced across classes, across the Early/Advanced tier split, and
relative to what it costs?

Supersedes sweep_equipment.py's ad hoc 4-class/bundled-profile version: this tests all 9
classes, isolates each ingredient individually (never bundling weapon+armor together, so one
ingredient's contribution is never conflated with another's -- the same isolation discipline
CLASS_BALANCE_GUIDE.md/LEVELING_GUIDE.md require for card-level tuning), and reports each
recipe's Gold+material cost alongside its survival-floor effect so cost-efficiency across
classes is directly comparable.

"Crack point" = the highest starting HP where the class does not have a 100% guaranteed win
across the full mob roster x full hand space (T.MOB_NAMES x mod.ALL_HANDS) using the real
exact solver (best_line_with_equipment, which itself never departs from best_line_for_hand's
search -- see EQUIPMENT_HANDOFF.md Section 8/9 for why that matters). Reports the FULL
per-integer-HP curve, not just the break point, per this project's own defense-floor
convention (never resample to checkpoints).
"""
import time
import condensed_trip as T
from equipment_data import get_recipes_for_class

CLASSES = ["warrior", "wizard", "cleric", "paladin", "rogue", "ranger", "runecaster", "druid", "necromancer"]
MAX_HP = {"warrior": 14, "wizard": 10, "cleric": 13, "paladin": 17, "rogue": 11,
          "ranger": 12, "runecaster": 14, "druid": 13, "necromancer": 12}


def full_survival_curve(class_name, equipment_load):
    """Despite the name (kept for the rest of this module's existing vocabulary), this counts
    real WINS (mob actually killed), not mere survival -- matches every class's own established
    win_rate() convention (checked directly: condensed_necromancer.py's win_rate only counts
    simulate()'s win=True). The first version of this function used `hp_left > 0` as a survival
    proxy, which silently counted a hero who fled alive after 3 rounds with the mob still up as
    a "success" -- a real, different thing from winning that this project's own convention has
    never conflated."""
    from combat_engine import CARD_SOURCE
    from equipment_solver import best_line_with_equipment
    mod = CARD_SOURCE[class_name]
    max_hp = MAX_HP[class_name]
    curve = {}
    for hp in range(max_hp, 0, -1):
        wins, total = 0, 0
        for mob_name in T.MOB_NAMES:
            pattern, mob_hp = T.MOBS[mob_name][class_name]
            for hand in mod.ALL_HANDS:
                total += 1
                res = best_line_with_equipment(class_name, hand, pattern, mob_hp, hp, equipment_load)
                if res is not None and res[0]:
                    wins += 1
        curve[hp] = wins / total
    return curve


def crack_point(curve):
    """Highest HP where survival is NOT 100% -- None if 100% survival held all the way down
    to HP 1. Kept as a secondary stat only -- see curve_summary()'s docstring for why this
    number alone is misleading."""
    for hp in sorted(curve.keys(), reverse=True):
        if curve[hp] < 1.0:
            return hp, curve[hp]
    return None, 1.0


def curve_summary(base_curve, eq_curve):
    """Real fix for a bug this sweep's first version had: reporting only crack_point()
    silently hid any effect that doesn't move survival across the specific integer-HP
    threshold where the FIRST loss appears. Concretely: Warrior+Persistent broke at HP 7
    in both curves (so the old script reported "0 improvement"), but underneath that,
    HP 3 survival went 54.4% -> 65.6% and HP 2 went 25.6% -> 35.6% -- a large, real
    effect the crack-point number alone completely hid.

    Reports the mean win-rate uplift across every HP level actually swept (the true
    aggregate value an item delivers, not a single brittle threshold), plus the single
    biggest per-HP swing and where it happens, so a "0" here means something checked
    across the whole curve, not just the top of it."""
    diffs = {hp: eq_curve[hp] - base_curve[hp] for hp in base_curve}
    mean_uplift = sum(diffs.values()) / len(diffs)
    peak_hp = max(diffs, key=lambda hp: diffs[hp])
    return mean_uplift, peak_hp, diffs[peak_hp]


def recipe_cost_str(recipe):
    parts = [f"{v}{k}" for k, v in recipe["cost"].items()]
    return "+".join(parts)


def main():
    t0 = time.time()
    results = {}
    for cls in CLASSES:
        recipes = get_recipes_for_class(cls)
        # One representative recipe per (slot, rider) pair -- cheapest Base for that rider,
        # since we're isolating the ingredient's effect, not the Base's flavor.
        by_rider = {}
        for r in recipes:
            key = (r["slot"], r["rider"])
            if key not in by_rider or sum(v for k, v in r["cost"].items() if k != "Gold") < \
                    sum(v for k, v in by_rider[key]["cost"].items() if k != "Gold"):
                by_rider[key] = r

        base_curve = full_survival_curve(cls, {})
        base_break, base_pct = crack_point(base_curve)
        results[cls] = {"baseline": (base_curve, base_break, base_pct, None)}

        for (slot, rider), recipe in sorted(by_rider.items()):
            curve = full_survival_curve(cls, {slot: recipe})
            brk, pct = crack_point(curve)
            results[cls][f"{slot}:{rider}"] = (curve, brk, pct, recipe)
        print(f"-- {cls} done ({time.time()-t0:.0f}s elapsed) --", flush=True)

    print(f"\nTotal sweep time: {time.time()-t0:.0f}s\n")

    print("=" * 100)
    for cls, data in results.items():
        print(f"\n### {cls.upper()} (max HP {MAX_HP[cls]})")
        base_curve, base_brk, base_pct, _ = data["baseline"]
        base_str = f"HP {base_brk} ({base_pct*100:.1f}%)" if base_brk else "never breaks (immortal to HP 1)"
        print(f"  Baseline crack point: {base_str}")
        rows = []
        for key, (curve, brk, pct, recipe) in data.items():
            if key == "baseline":
                continue
            mean_uplift, peak_hp, peak_uplift = curve_summary(base_curve, curve)
            rows.append((mean_uplift, key, brk, pct, recipe, peak_hp, peak_uplift))
        rows.sort(reverse=True)
        for mean_uplift, key, brk, pct, recipe, peak_hp, peak_uplift in rows:
            brk_str = f"HP {brk} ({pct*100:.1f}%)" if brk else "never breaks"
            cost_str = recipe_cost_str(recipe)
            print(f"  {key:24s} cost={cost_str:20s} avg-uplift={mean_uplift*100:+5.1f}pp  "
                  f"peak=+{peak_uplift*100:.1f}pp@HP{peak_hp}  crack={brk_str}")


if __name__ == "__main__":
    main()
