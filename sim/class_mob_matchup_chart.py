"""
Per-class, per-mob matchup chart -- cost% and win% for every locked class against every
locked Standard-tier mob (Level 1) or Standard+Elite mob (Level 2), single-pull, full HP.
Kept as a permanent, rerunnable tool (not a one-off script) since this answers a real,
recurring design question: "which mobs favor which class," first asked when considering
whether to surface matchup info to players at class-select time to motivate node choice (see
OPEN_QUESTIONS.md) -- and, as of 2026-08-26, actually IS surfaced to players, via
playtest_board_web.py's "Class Guide" modal, which computes both tables once at app start
rather than the frozen, hand-typed numbers an earlier pass had baked in (a real bug -- see
LEVELING_GUIDE.md/this session's audit notes for why a static snapshot can't stay correct here).

As of 2026-10-12 this module is the SINGLE source for the Class Guide's Favored/Struggles lists
(DESIGN_DOC.md Section VI, "Class Guide: Favored and Struggles"): class_guide(level) is what both
pnp-tool/export_tracker_boards.py (printed hero boards) and playtest_board_web.py (live Class
Guide) call, so the two can no longer drift apart. See CLASS_BALANCE_GUIDE.md, "Favored and
Struggles derivation", for the reasoning and the audit that produced the rules below.

Why cost%, not win rate, is the metric that actually differentiates: win rate is a hard
binary cliff, quantized to multiples of 1/15 per class (only 15 possible hands) -- there's no
way to land at exactly 50%, and most classes already sit at 93.3-100% against most Standard
mobs by design (the roster was tuned to be broadly winnable everywhere, per the locked
"mobs must stay class-agnostic" rule). That leaves almost no signal to build a "shines here,
struggles there" mechanic on. Cost% is a continuous measure and was already found to be the
metric that actually differentiates cleanly in the Elite-derivation work (see
CLASS_BALANCE_GUIDE.md's "Elite trio, derived" section). Per hand: cost = max_hp - hp_left of the
class's best line, EXCEPT that a lost hand counts as 100% (2026-10-12 -- the old HP-loss-only
figure understated mobs a class sometimes loses to, by up to ~6.7 points per lost hand of 15).
cost% = 100 * mean(per-hand cost) / max_hp; tail = the worst single hand.

Level 2 uses each class's FULLY upgraded kit (mandatory + every purchased upgrade), via
board_engine._level2_swaps_for -- not a per-hero snapshot. A real hero's actual kit can differ
(Level 2 purchased-upgrade order is randomized per hero, locked 2026-08-23), so this is
deliberately "best available reference for this class at this level," not "this exact hero's
current deck" -- a reasonable simplification for a rough matchup guide, not a precision tool.
Level 2 Standard mobs use the REMIXED Level 2 stat blocks for Grunt/Enforcer/Ambusher
(leveling_validation.LEVEL2_STANDARD); an earlier version of this file used the Level 1 stat
blocks there by mistake.

Favored / Struggles (class_guide): per class and level, over the 6 Standard mobs only (Elites are
shown in the table but never ranked), Favored = the 2 lowest cost%, Struggles = the 2 highest.
Mobs within TIE_TOL points of the cutoff (the 2nd-ranked mob) are tied candidates; clearly better
or worse mobs are locked in. Ties break by (1) tail risk -- Favored prefers the lower worst-hand
cost, Struggles the higher, counted only when the gap exceeds TAIL_TOL; (2) diversity -- the
combination, found by exhaustive search (order-independent), that spreads mobs most evenly
across the nine classes (smallest sum of squared per-mob list counts, then smallest cost
deviation); (3) roster order. Entries carry the mob's flavor name from pnp-tool/src/mobs_text.json.

Run: python class_mob_matchup_chart.py (from sim/).
"""
import itertools
import json
import os

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

LOSS_COST_PCT = 100.0  # a lost hand costs the whole HP bar
TIE_TOL = 1.5          # cost% points around the cutoff mob that count as a tie
TAIL_TOL = 5.0         # worst-hand cost% points that still count as a tie
STANDARD_MOBS = list(T.MOB_NAMES)


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


def _mob_entries(mob_key, level):
    """[(mob_name, (pattern, mob_hp))] for this level: the 6 Standard mobs (Level 2 uses the
    remixed LEVEL2_STANDARD blocks for Grunt/Enforcer/Ambusher) plus, at Level 2, the 3 Elites."""
    entries = []
    for mob_name in T.MOB_NAMES:
        l2_name = f"{mob_name}_L2"
        if level >= 2 and l2_name in LV.LEVEL2_STANDARD:
            entries.append((mob_name, LV._level2_standard_pattern(mob_key, l2_name)))
        else:
            entries.append((mob_name, T.MOBS[mob_name][mob_key]))
    if level >= 2:
        entries += [(name, (LV._elite_pattern(mob_key, name), LV.ELITE_HP)) for name in LV.ELITE_MELEE]
    return entries


def matchup_table_full(level=1):
    """Returns {class_label: {mob_name: (cost_pct, win_pct, tail_pct)}}. level=1: base kit vs the
    6 Standard mobs. level=2: fully-upgraded kit (see _full_upgrade_swaps) vs the same 6 Standard
    mobs (remixed Level 2 blocks) plus the 3 Elites (Bulwark/Berserker/Warlord). A lost hand
    counts as LOSS_COST_PCT; tail_pct is the worst single hand."""
    table = {}
    for cls, (mod, has_stance, max_hp, mob_key) in SPECS.items():
        table[cls] = {}
        swaps = _full_upgrade_swaps(mob_key) if level >= 2 else {}
        with LV.leveled_kit(mod, swaps):
            for mob_name, (pattern, mob_hp) in _mob_entries(mob_key, level):
                per_hand, wins = [], []
                for hand in mod.ALL_HANDS:
                    seq, stance, hp_left, rounds = T._best_line(mod, has_stance, hand, pattern, mob_hp, max_hp)
                    win, final_hp, final_rounds = T._simulate(mod, has_stance, seq, stance, pattern, mob_hp, max_hp)
                    per_hand.append(100.0 * (max_hp - hp_left) / max_hp if win else LOSS_COST_PCT)
                    wins.append(win)
                table[cls][mob_name] = (sum(per_hand) / len(per_hand),
                                        100.0 * sum(wins) / len(wins),
                                        max(per_hand))
    return table


def matchup_table(level=1):
    """Returns {class_label: {mob_name: (cost_pct, win_pct)}} -- matchup_table_full without the
    tail, kept for callers that only want the two-number shape."""
    return {cls: {mob: (c, w) for mob, (c, w, _t) in row.items()} for cls, row in matchup_table_full(level).items()}


def _flavor_names():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pnp-tool", "src", "mobs_text.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {(m["mechanical_name"], m["level"]): m["name"] for m in json.load(f)}
    except (OSError, ValueError, KeyError):
        return {}


def mob_flavor_name(mob_name, level, _names=_flavor_names()):
    """The name printed on the card for this Standard mob at this level, falling back to the role."""
    l2_name = f"{mob_name}_L2"
    key = l2_name if level >= 2 and l2_name in LV.LEVEL2_STANDARD else mob_name
    return _names.get((key, level), mob_name)


def _resolve_slots(row, favored):
    """One class, one list. row: {mob: (cost, win, tail)} over the Standard mobs. Returns
    (settled, pending): settled = mobs already decided; pending = None, or (tied_mobs, k) meaning
    k more mobs must be picked from tied_mobs by the diversity step."""
    sign = 1 if favored else -1
    order = sorted(row, key=lambda m: (sign * row[m][0], STANDARD_MOBS.index(m)))
    cutoff = row[order[1]][0]
    locked = [m for m in order if sign * (row[m][0] - cutoff) < -TIE_TOL]
    cands = [m for m in order if abs(row[m][0] - cutoff) <= TIE_TOL]
    k = 2 - len(locked)
    if len(cands) <= k:
        return locked + cands, None
    by_tail = sorted(cands, key=lambda m: (sign * row[m][2], STANDARD_MOBS.index(m)))
    if abs(row[by_tail[k]][2] - row[by_tail[k - 1]][2]) > TAIL_TOL:
        return locked + by_tail[:k], None
    t_lo, t_hi = row[by_tail[k - 1]][2], row[by_tail[k]][2]
    tied = [m for m in by_tail if abs(row[m][2] - t_lo) <= TAIL_TOL or abs(row[m][2] - t_hi) <= TAIL_TOL]
    first = by_tail.index(tied[0])
    return locked + by_tail[:first], (tied, k - first)


def _choose_lists(std_table, favored):
    """{class: [2 mobs]} for one list type, running the tie ladder across all classes at once."""
    settled, pending = {}, {}
    cutoffs = {}
    for cls, row in std_table.items():
        s, p = _resolve_slots(row, favored)
        settled[cls] = s
        costs = sorted(v[0] for v in row.values())
        cutoffs[cls] = costs[1] if favored else costs[-2]
        if p:
            pending[cls] = p
    base = {}
    for lst in settled.values():
        for m in lst:
            base[m] = base.get(m, 0) + 1
    pend = list(pending)
    options = [list(itertools.combinations(pending[c][0], pending[c][1])) for c in pend]
    best = None
    for pick in itertools.product(*options):
        counts = dict(base)
        dev = 0.0
        for cls, chosen in zip(pend, pick):
            for m in chosen:
                counts[m] = counts.get(m, 0) + 1
                dev += abs(std_table[cls][m][0] - cutoffs[cls])
        key = (sum(v * v for v in counts.values()), round(dev, 6),
               [STANDARD_MOBS.index(m) for chosen in pick for m in chosen])
        if best is None or key < best[0]:
            best = (key, pick)
    result = {cls: list(s) for cls, s in settled.items()}
    for cls, chosen in zip(pend, best[1]):
        result[cls] = list(settled[cls]) + list(chosen)
    for cls in result:
        assert len(result[cls]) == 2, (cls, result[cls])
        result[cls].sort(key=lambda m: ((1 if favored else -1) * std_table[cls][m][0], STANDARD_MOBS.index(m)))
    return result


def class_guide(level=1, table=None):
    """{class_label: {"favored": [entry, entry], "struggles": [entry, entry]}} where entry is
    {"mob": role, "name": flavor name, "cost": cost% rounded to 1 decimal}. Best/worst first.
    Pass `table` (a matchup_table_full result) to avoid recomputing it."""
    table = table if table is not None else matchup_table_full(level)
    std = {cls: {m: row[m] for m in STANDARD_MOBS} for cls, row in table.items()}
    fav, stg = _choose_lists(std, True), _choose_lists(std, False)
    guide = {}
    for cls in table:
        assert not (set(fav[cls]) & set(stg[cls])), (cls, fav[cls], stg[cls])
        guide[cls] = {
            "favored": [{"mob": m, "name": mob_flavor_name(m, level), "cost": round(std[cls][m][0], 1)} for m in fav[cls]],
            "struggles": [{"mob": m, "name": mob_flavor_name(m, level), "cost": round(std[cls][m][0], 1)} for m in stg[cls]],
        }
    return guide


def print_chart(table, label="Level 1"):
    # mob_names read from the table itself, not T.MOB_NAMES -- a Level 2 table also includes
    # the 3 Elites, which aren't in T.MOB_NAMES.
    mob_names = list(next(iter(table.values())).keys())
    print(f"### {label} ###")
    print("=== Cost% (avg HP spent per pull, a lost hand counts as 100%) -- lower means the class finds that mob easier ===")
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


def print_guide(guide, label="Level 1"):
    print(f"=== Class Guide, {label} (Favored / Struggles, by flavor name) ===")
    for cls, g in guide.items():
        fav = ", ".join(f"{e['name']} ({e['cost']}%)" for e in g["favored"])
        stg = ", ".join(f"{e['name']} ({e['cost']}%)" for e in g["struggles"])
        print(f"  {cls:11s} Favored: {fav}   |   Struggles: {stg}")


if __name__ == "__main__":
    for lvl, lbl in ((1, "Level 1"), (2, "Level 2 (fully upgraded)")):
        tbl = matchup_table_full(lvl)
        print_chart({c: {m: (v[0], v[1]) for m, v in row.items()} for c, row in tbl.items()}, lbl)
        print()
        print_guide(class_guide(lvl, table=tbl), lbl)
        print()
