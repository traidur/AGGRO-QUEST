"""
Measures the kill-quest design (DESIGN_DOC.md Section VI, "Kill Quests" / "Level 1 Quest Draft",
locked 2026-10-12) against the real solo engine -- kept as a permanent tool because the kill
counts, filters and the bot hunting policy are all still tuning knobs (OPEN_QUESTIONS.md,
"Kill quests and the Level 1 Quest Draft").

Two experiments, both per class, both on board_engine.run_solo_chain with kill_quests.enable():

  card   -- ISOLATED CARD COST. The hero carries ONE quest (a kill card, or a single Level 1 loot
            quest as the reference) and the chain runs until it is turned in. Reports mean field
            turns to finish (hero.turns minus the opening and closing Town visits), the
            unfinished/death rate. This is the number that says whether a "Kill N <filter>" card
            costs about what a 2-loot quest does (all Level 1 quests pay 2 XP and a 4/2/1/0 Gold
            ladder, so equal turns == fair).

  start  -- STARTING HAND. Level 1 start-to-Level-2 (6 XP): today's random 3-of-8 loot draw vs the
            solo draft (2 loot + 1 kill). Reports mean turns to Level 2 and deaths.

--policy compares the bot's hunting rule: "border" (sit on / return to the Border Node so both
Zones are dealt) vs "stay" (never leave the current Zone's own deal).

--workers N splits the independent (class, card, policy) cells across N processes (default 1 =
serial). Each cell seeds its own RNG, so results are identical for any worker count.

Run:  py -3 -B kill_quest_measure.py card  [--n 60] [--classes warrior,rogue] [--policy border,stay] [--workers 4]
      py -3 -B kill_quest_measure.py start [--n 100] [--workers 4]
Counts are placeholders (kill_quests.DEFAULT_COUNTS); override with --role-count etc.
"""
import argparse
import contextlib
import multiprocessing as mp
import random
import statistics as st

import board_engine as BE
import kill_quests as KQ
import macro_sim as M

CLASSES = list(M.CARD_SOURCE)
MAX_TURNS = 120
OVERHEAD = 2   # the chain's opening Town visit + the closing Town turn-in visit


def _run_one(cls, seed, starter, xp_goal, policy, counts, loot_pick="same_zone"):
    """Runs one chain until xp_goal; returns (turns_to_goal or None, deaths)."""
    rng = random.Random(seed)
    deaths = 0
    with KQ.enable(counts=counts, hunt_policy=policy, starter=starter, loot_pick=loot_pick):
        for alive, _g, xp, _qc, _tr, turns in BE.run_solo_chain(cls, "food_only", rng, max_turns=MAX_TURNS):
            deaths += 0 if alive else 1
            if xp >= xp_goal:
                return turns, deaths
    return None, deaths


def _run_one_plain(cls, seed):
    """Baseline: the engine's own random 3-of-8 starter draw, kill mode off."""
    rng = random.Random(seed)
    deaths = 0
    for alive, _g, xp, _qc, _tr, turns in BE.run_solo_chain(cls, "food_only", rng, max_turns=MAX_TURNS):
        deaths += 0 if alive else 1
        if xp >= M.LEVEL2_XP_THRESHOLD:
            return turns, deaths
    return None, deaths


# ---- worker cells (module-level so Windows 'spawn' can pickle them) ----------------------------

def _cell_card(args):
    policy, name, cls, n, counts, base, goal = args
    turns, unfinished, deaths = [], 0, 0
    for s in range(n):
        t, d = _run_one(cls, 1000 * s + 17, lambda h, c, r, nm=name: list(base) + [nm], goal, policy, counts)
        deaths += d
        if t is None:
            unfinished += 1
        else:
            turns.append(t - OVERHEAD)
    return (policy, name, cls), (st.mean(turns) if turns else float("nan"), unfinished, deaths)


def _cell_start(args):
    kind, cls, n, counts, loot_pick = args           # kind: "rand" or a hunt policy name (draft)
    ts, deaths = [], 0
    for s in range(n):
        if kind == "rand":
            t, d = _run_one_plain(cls, 1000 * s + 17)
        else:
            t, d = _run_one(cls, 1000 * s + 17, True, M.LEVEL2_XP_THRESHOLD, kind, counts, loot_pick)
        deaths += d
        if t is not None:
            ts.append(t)
    return (kind, cls), (ts, deaths)


def _map(fn, tasks, workers):
    if workers <= 1:
        return [fn(t) for t in tasks]
    with mp.Pool(workers) as pool:
        return list(pool.imap_unordered(fn, tasks, chunksize=1))


PROFILE_BASE = ("Pilfered Goods", "Syndicate Ledger")   # two Zone 1 loot quests (the fixed pair)


def _cell_profile(args):
    """One (variant, class) cell of the profile experiment: per-chain checkpoints at 6 XP and at
    the mandatory Level 2 upgrade -- turns, Gold in hand right after turn-in, Food/Potions burned
    (the 'condition' proxy: HP resets every trip, so what a hero SPENT to stay alive is the
    honest measure), deaths."""
    variant, cls, n, counts, policy = args
    out = []
    for s in range(n):
        rng = random.Random(1000 * s + 17)
        cap = []
        if variant == "random3":
            saved = BE.STARTER_QUEST_HOOK
            BE.STARTER_QUEST_HOOK = lambda h, c, r: (cap.append(h), r.sample(list(M.QUESTS.keys()), 3))[1]
            ctx = contextlib.nullcontext()
        else:
            saved = None
            ctx = KQ.enable(counts=counts, hunt_policy=policy,
                            starter=lambda h, c, r, nm=variant: (cap.append(h), list(PROFILE_BASE) + [nm])[1])
        deaths, six, mand = 0, None, None
        try:
            with ctx:
                for alive, gold_in_hand, xp, _qc, _tr, turns in BE.run_solo_chain(
                        cls, "food_only", rng, max_turns=MAX_TURNS):
                    deaths += 0 if alive else 1
                    hero = cap[0]
                    used = sum(hero.consumables_used.values())
                    if six is None and xp >= M.LEVEL2_XP_THRESHOLD:
                        six = (turns, gold_in_hand, used, deaths)
                    if "mandatory" in hero.acquired:
                        mand = (turns, gold_in_hand, used, deaths)
                        break
        finally:
            if variant == "random3":
                BE.STARTER_QUEST_HOOK = saved
        out.append((six, mand))
    return (variant, cls), out


def profile_experiment(n, classes, policy, counts, workers):
    with KQ.enable(counts=counts) as cards:
        kill_names = list(cards)
    variants = ["random3", "Contraband Crates", "Smuggled Cargo"] + kill_names
    res = dict(_map(_cell_profile, [(v, c, n, counts, policy) for v in variants for c in classes], workers))
    print(f"PROFILE -- policy {policy}, n={n}/class, means over {len(classes)} classes\n"
          "random3 = today's random 3-of-8; the rest = Pilfered Goods + Syndicate Ledger + the named third card\n")
    print("third card".ljust(30) + "| at 6 XP:  turns  gold  used  deaths | at mandatory upgrade:  turns  gold  used  deaths  (reached)")
    for v in variants:
        runs = [r for c in classes for r in res[(v, c)]]
        six = [r[0] for r in runs if r[0]]
        mand = [r[1] for r in runs if r[1]]

        def m(rows, i):
            return st.mean(x[i] for x in rows) if rows else float("nan")
        print(v.ljust(30) + f"|        {m(six,0):6.1f} {m(six,1):5.1f} {m(six,2):5.1f} {m(six,3):7.2f} |"
              f"                      {m(mand,0):6.1f} {m(mand,1):5.1f} {m(mand,2):5.1f} {m(mand,3):7.2f}  ({len(mand)}/{len(runs)})")


def _cell_calib(args):
    """_cell_profile for one calibration variant, whose card exists only under its own counts.
    `label` keys the result so the same card can appear under several counts (e.g. ladders)."""
    label, variant, counts, cls, n, policy = args
    (_v, _c), out = _cell_profile((variant, cls, n, counts, policy))
    return (label, cls), out


def ladder_experiment(n, classes, policy, workers):
    """Turn-matched kill cards under different kill Gold ladders (counts key 'ladder'), against
    the same loot reference as `calibrate`. Isolates how much of the Gold gap the ladder can close."""
    refs = ["Contraband Crates", "Smuggled Cargo"]
    cards = [("Kill 3 Grunt", {"role": 3}), ("Kill 3 Enforcer", {"role": 3}),
             ("Kill 5 Favored", {"favored2": 5}), ("Kill 5 Struggles", {"struggles1": 5}),
             ("Kill 1 Favored + 4 Struggles", {"mixed": (1, 4)})]
    ladders = [[4, 2, 1, 0], [2, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 0]]
    tasks = []
    for lad in ladders:
        for v, cn in cards:
            for cl in classes:
                tasks.append((f"{v}|{lad}", v, dict(cn, ladder=lad), cl, n, policy))
    for r in refs:
        for cl in classes:
            tasks.append((r, r, {}, cl, n, policy))
    res = dict(_map(_cell_calib, tasks, workers))

    def stats(label):
        runs = [r for cl in classes for r in res[(label, cl)]]
        six = [r[0] for r in runs if r[0]]
        mand = [r[1] for r in runs if r[1]]
        return [st.mean(x[i] for x in six) for i in (0, 1, 2)] + [st.mean(x[0] for x in mand)]

    print(f"LADDER SWEEP -- policy {policy}, n={n}/class, {len(classes)} classes\n")
    print("third card / kill ladder".ljust(46) + "turns6   gold   used  mand.turns")
    ref_rows = [stats(r) for r in refs]
    for r, s in zip(refs, ref_rows):
        print(r.ljust(46) + f"{s[0]:6.1f} {s[1]:6.1f} {s[2]:6.1f} {s[3]:9.1f}")
    s = [st.mean(x[i] for x in ref_rows) for i in range(4)]
    print("REFERENCE: average of the two".ljust(46) + f"{s[0]:6.1f} {s[1]:6.1f} {s[2]:6.1f} {s[3]:9.1f}")
    for lad in ladders:
        print("-" * 70 + f"\nkill ladder {lad}")
        for v, _cn in cards:
            s = stats(f"{v}|{lad}")
            print(("  " + v).ljust(46) + f"{s[0]:6.1f} {s[1]:6.1f} {s[2]:6.1f} {s[3]:9.1f}")


def calibrate_experiment(n, classes, policy, workers):
    """Sweeps counts per kill-card family against the reference 'third card = average of a Zone 1
    and a Zone 2 loot quest' (Contraband Crates / Smuggled Cargo) on turns to 6 XP, Gold in hand
    and Food/Potions used. Role cards are averaged over all six roles."""
    refs = ["Contraband Crates", "Smuggled Cargo"]
    fams = []   # (family label, [(variant name, counts)])
    for k in (3, 4, 5):
        c = {"role": k}
        with KQ.enable(counts=c) as cards:
            names = [nm for nm in cards if nm.startswith(f"Kill {k} ") and "Favored" not in nm and "Struggles" not in nm]
        fams.append((f"Kill {k} <role> (avg of 6)", [(nm, c) for nm in names]))
    for k in (3, 4, 5, 6, 7):
        fams.append((f"Kill {k} Favored", [(f"Kill {k} Favored", {"favored2": k})]))
        fams.append((f"Kill {k} Struggles", [(f"Kill {k} Struggles", {"struggles1": k})]))
    for a, b in ((1, 3), (2, 2), (2, 3), (1, 4), (2, 4)):
        fams.append((f"Kill {a} Favored + {b} Struggles", [(f"Kill {a} Favored + {b} Struggles", {"mixed": (a, b)})]))
    tasks = [(v, v, c, cl, n, policy) for _lab, vs in fams for v, c in vs for cl in classes]
    tasks += [(r, r, {}, cl, n, policy) for r in refs for cl in classes]
    res = dict(_map(_cell_calib, tasks, workers))

    def stats(variant):
        runs = [r for cl in classes for r in res[(variant, cl)]]
        six = [r[0] for r in runs if r[0]]
        mand = [r[1] for r in runs if r[1]]
        mean = lambda rows, i: st.mean(x[i] for x in rows)
        return (mean(six, 0), mean(six, 1), mean(six, 2), mean(six, 3), mean(mand, 0), len(mand) / len(runs))

    def show(label, rows):
        s = [sum(x[i] for x in rows) / len(rows) for i in range(6)]
        print(label.ljust(36) + f"{s[0]:7.1f} {s[1]:6.1f} {s[2]:6.1f} {s[3]:7.3f} {s[4]:9.1f}   {s[5]:.0%}")

    print(f"CALIBRATION -- policy {policy}, n={n}/class, {len(classes)} classes; third card on top of "
          "Pilfered Goods + Syndicate Ledger\n")
    print("third card".ljust(36) + "turns6   gold   used  deaths  mand.turns  reached")
    ref_rows = [stats(r) for r in refs]
    for r, row in zip(refs, ref_rows):
        show(r, [row])
    show("REFERENCE: average of the two", ref_rows)
    print("-" * 80)
    for lab, vs in fams:
        show(lab, [stats(v) for v, _c in vs])


# ---- experiments --------------------------------------------------------------------------------

def card_experiment(n, classes, policies, counts, workers, base=(), goal=2):
    loot_names = [q for q in list(M.QUESTS) if not KQ.is_kill(M.QUESTS[q])]
    with KQ.enable(counts=counts) as cards:
        kill_names = list(cards)
    tasks = [(p, nm, c, n, counts, base, goal) for p in policies for nm in loot_names + kill_names for c in classes]
    res = dict(_map(_cell_card, tasks, workers))
    what = "ISOLATED CARD COST -- one card alone" if not base else "MARGINAL CARD COST -- " + " + ".join(base) + f" + card, to {goal} XP"
    print(f"{what}: mean field turns (n={n}/class/cell)\n")
    for policy in policies:
        print(f"== hunt policy: {policy} ==")
        print("card".ljust(30) + "".join(c[:5].rjust(7) for c in classes) + "   mean  unfin deaths")
        for nm in loot_names + kill_names:
            cells = [res[(policy, nm, c)] for c in classes]
            vals = [v[0] for v in cells]
            tag = "(loot ref)" if nm in loot_names else ""
            print(nm.ljust(30) + "".join(f"{v:7.1f}" for v in vals)
                  + f"  {st.mean(vals):5.1f}  {sum(v[1] for v in cells):4d}  {sum(v[2] for v in cells):5d} {tag}")
        ref = st.mean(res[(policy, nm, c)][0] for nm in loot_names for c in classes)
        print(f"\nloot-quest reference mean: {ref:.2f} field turns\n")


def start_experiment(n, classes, policies, counts, workers, loot_pick="same_zone"):
    kinds = ["rand"] + list(policies)
    res = dict(_map(_cell_start, [(k, c, n, counts, loot_pick) for k in kinds for c in classes], workers))
    print(f"STARTING HAND -- mean turns to 6 XP (Level 2), n={n}/class\n")
    print("class".ljust(12) + "random 3-of-8".rjust(15) + "".join(f"draft/{p}".rjust(15) for p in policies)
          + "   deaths(rand/draft...)")
    for c in classes:
        print(c.ljust(12) + "".join(f"{st.mean(res[(k, c)][0]):15.1f}" for k in kinds)
              + "   " + "/".join(str(res[(k, c)][1]) for k in kinds))
    print("ALL".ljust(12) + "".join(f"{st.mean([t for c in classes for t in res[(k, c)][0]]):15.1f}" for k in kinds))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("experiment", choices=["card", "marginal", "start", "profile", "calibrate", "ladder"])
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--classes", default=",".join(CLASSES))
    ap.add_argument("--policy", default="border,stay")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--loot-pick", default="same_zone", choices=["same_zone", "random"])
    ap.add_argument("--role-count", type=int)
    ap.add_argument("--favored2", type=int)
    ap.add_argument("--struggles1", type=int)
    ap.add_argument("--mixed", help="A,B  (Kill A Favored + B Struggles)")
    a = ap.parse_args()
    counts = {k: v for k, v in (("role", a.role_count), ("favored2", a.favored2),
                                ("struggles1", a.struggles1)) if v is not None}
    if a.mixed:
        counts["mixed"] = tuple(int(x) for x in a.mixed.split(","))
    if a.experiment == "card":
        card_experiment(a.n, a.classes.split(","), a.policy.split(","), counts, a.workers)
    elif a.experiment == "marginal":
        card_experiment(a.n, a.classes.split(","), a.policy.split(","), counts, a.workers,
                        base=("Pilfered Goods", "Syndicate Ledger"), goal=6)
    elif a.experiment == "ladder":
        ladder_experiment(a.n, a.classes.split(","), a.policy.split(",")[0], a.workers)
    elif a.experiment == "calibrate":
        calibrate_experiment(a.n, a.classes.split(","), a.policy.split(",")[0], a.workers)
    elif a.experiment == "profile":
        profile_experiment(a.n, a.classes.split(","), a.policy.split(",")[0], counts, a.workers)
    else:
        start_experiment(a.n, a.classes.split(","), a.policy.split(","), counts, a.workers, a.loot_pick)
