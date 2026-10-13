"""
Kill quests + the Level 1 Quest Draft -- simulator side of DESIGN_DOC.md Section VI ("Kill
Quests" and "Level 1 Quest Draft", both locked 2026-10-12).

What this module owns (data + rules only; the few hooks that call into it live in
board_engine.py, and the measurement driver is kill_quest_measure.py):
  - KILL card table (counts and the 2/1/0/0 ladder locked 2026-10-12 from kill_quest_measure.py;
    DESIGN_DOC pins XP 2 at Level 1).
  - Progress bookkeeping: hero.kill_progress[card] = filled count per clause. A kill is any
    outright win vs a roster mob; one kill fills ONE clause per card but advances EVERY
    qualifying quest at once. No Bag space, no token -- progress lives on the card.
  - The bot's solo draft (2 loot + 1 kill; display 2P+1 loot / P+1 kill -> 3 loot / 2 kill for
    solo) and its hunting policy switch.
  - enable(): a context manager that injects the kill cards into macro_sim.QUESTS and installs
    the engine hooks, so every existing quest-pool lookup (turn-in, decay, death) keeps working
    unchanged and OFF means the engine is bit-for-bit what it was.

Level 1 only for now: Favored/Struggles resolve through class_mob_matchup_chart.class_guide(1),
and Level 2 kill filters (faction, "any Elite") are not built (Level 2 mobs never match).
"""
import contextlib

import condensed_trip as T
import macro_sim as M

KILL_XP = 2
KILL_LADDER = [2, 1, 0, 0]   # loot quests keep 4/2/1/0; see OPEN_QUESTIONS.md "Level 1 kill quest counts"

# Locked counts (2026-10-12), derived with kill_quest_measure.py. Each card = list of (filter,
# count) clauses (max 2 clauses). Filters: ("role", <mob key>) | ("favored",) | ("struggles",).
# The dict keys are historical names; the values are the box counts.
DEFAULT_COUNTS = {"role": 3, "favored2": 5, "mixed": (1, 4), "struggles1": 5}

# Bot policy switches (module-level so the engine hooks read them without plumbing).
ENABLED = False
HUNT_POLICY = "border"   # "border": sit on/return to the Border Node when hunting; "stay": never
DRAFT_LOOT_PICK = "same_zone"   # or "random"
DRAFT_KILL_PICK = "fastest"     # or "random"

_GUIDE = {}


def _guide(class_name):
    """{'favored': {role,...}, 'struggles': {role,...}} for a class at Level 1, from the real
    Class Guide (class_mob_matchup_chart.class_guide) -- the same lists printed on the board."""
    if not _GUIDE:
        import class_mob_matchup_chart as MC
        for cls, g in MC.class_guide(level=1).items():
            _GUIDE[cls.lower()] = {k: {e["mob"] for e in g[k]} for k in ("favored", "struggles")}
    return _GUIDE[class_name.lower()]


def build_cards(counts=None):
    """{card name: quest dict} -- same shape as macro_sim.QUESTS entries plus kind/clauses."""
    c = dict(DEFAULT_COUNTS)
    c.update(counts or {})
    cards = {}

    ladder = list(c.get("ladder", KILL_LADDER))

    def add(name, clauses):
        cards[name] = dict(required=sum(n for _f, n in clauses), base_xp=KILL_XP,
                           gold_ladder=list(ladder), kind="kill", clauses=clauses)

    for role in T.MOB_NAMES:
        add(f"Kill {c['role']} {role}", [(("role", role), c["role"])])
    add(f"Kill {c['favored2']} Favored", [(("favored",), c["favored2"])])
    a, b = c["mixed"]
    add(f"Kill {a} Favored + {b} Struggles", [(("favored",), a), (("struggles",), b)])
    add(f"Kill {c['struggles1']} Struggles", [(("struggles",), c["struggles1"])])
    return cards


CARDS = build_cards()


def is_kill(q):
    return q.get("kind") == "kill"


def _clause_matches(flt, class_name, role):
    if flt[0] == "role":
        return role == flt[1]
    return role in _guide(class_name)[flt[0]]


def _role(mob_name):
    """Roster role key of a dealt/pulled mob, or None for a Level 2 / Elite / Spice card."""
    base = mob_name.replace("_loot", "")
    return base if base in T.MOB_NAMES else None


def _filled(hero, name, q):
    return hero.kill_progress.setdefault(name, [0] * len(q["clauses"]))


def progress(hero, name, q):
    """Kills banked on this card (0..required)."""
    return sum(_filled(hero, name, q))


def active_kill_cards(hero, pool):
    return [n for n in hero.active_quests if n in pool and is_kill(pool[n])]


def incomplete_kill_cards(hero, pool):
    return [n for n in active_kill_cards(hero, pool) if progress(hero, n, pool[n]) < pool[n]["required"]]


def _open_clause(hero, name, q, class_name, role):
    filled = _filled(hero, name, q)
    for i, (flt, need) in enumerate(q["clauses"]):
        if filled[i] < need and _clause_matches(flt, class_name, role):
            return i
    return None


def advances(hero, pool, class_name, mob_name):
    """Would a kill of mob_name advance any incomplete active kill quest right now?"""
    role = _role(mob_name)
    if role is None:
        return False
    return any(_open_clause(hero, n, pool[n], class_name, role) is not None
               for n in incomplete_kill_cards(hero, pool))


def record_kill(hero, mob_name):
    """A kill = any outright win vs a roster mob. One kill fills one clause per card, but every
    qualifying quest advances. Called from the engine's win paths; a no-op unless a kill quest
    is active, so non-kill runs are untouched."""
    if not ENABLED:
        return
    role = _role(mob_name)
    if role is None:
        return
    for name in incomplete_kill_cards(hero, M.QUESTS):
        i = _open_clause(hero, name, M.QUESTS[name], hero.class_name, role)
        if i is not None:
            _filled(hero, name, M.QUESTS[name])[i] += 1


def reset(hero, name):
    hero.kill_progress.pop(name, None)


def wants_token(hero, loot_name):
    """Kill-quest mode only: does the hero hold an open loot quest for this Node's token? (The
    rules hand out the Quest Token only when the Node matches an active quest.)"""
    q = M.QUESTS.get(loot_name) or M.LEVEL2_QUESTS.get(loot_name)
    return (q is not None and loot_name in hero.active_quests
            and M._accessible_count(hero.bag, hero.locked, loot_name) < q["required"])


def hunting(hero, pool):
    """Hunt state: some kill quest is still open and no loot quest is."""
    if not ENABLED or not incomplete_kill_cards(hero, pool):
        return False
    return not any(n in pool and not is_kill(pool[n]) and M._accessible_count(hero.bag, hero.locked, n) < pool[n]["required"]
                   for n in hero.active_quests)


# ---------------------------------------------------------------------------------- draft


_COST = {}


def _cost_table(class_name):
    """{role: cost%} for a class at Level 1 (lost hand = 100%), memoized -- it runs the solvers."""
    if not _COST:
        import class_mob_matchup_chart as MC
        for cls, row in MC.matchup_table(1).items():
            _COST[cls.lower()] = {mob: v[0] for mob, v in row.items()}
    return _COST[class_name.lower()]


def expected_pulls(card, class_name):
    """Bot heuristic: expected dealt-card pulls to finish a card if every pull were a random
    Level 1 card (each role is 1/6 of the deck). Used only to rank kill cards for the draft."""
    total = 0.0
    for flt, need in card["clauses"]:
        n_match = sum(1 for r in T.MOB_NAMES if _clause_matches(flt, class_name, r))
        total += need / (n_match / len(T.MOB_NAMES))
    return total


def _loot_zone(name):
    return next(M.NODE_ZONE[n] for n, (_t, l) in M.NODES.items() if l == name)


def draft_starter(class_name, rng, cards=None, n_loot_shown=3, n_kill_shown=2):
    """Solo draft: display n_loot_shown loot + n_kill_shown kill cards (2P+1 / P+1 with P=1),
    pick loot, loot, kill. Loot pick favors two quests in the same Zone; kill pick takes the
    card with the fewest expected pulls (ties: lowest mean cost of the mobs it needs)."""
    cards = cards or CARDS
    loot_pool = [n for n, q in M.QUESTS.items() if not is_kill(q)]
    shown_loot = rng.sample(loot_pool, n_loot_shown)
    shown_kill = rng.sample(list(cards), n_kill_shown)

    if DRAFT_LOOT_PICK == "same_zone":
        by_zone = {}
        for n in shown_loot:
            by_zone.setdefault(_loot_zone(n), []).append(n)
        zone = max(by_zone, key=lambda z: len(by_zone[z]))
        picked_loot = by_zone[zone][:2]
        if len(picked_loot) < 2:
            picked_loot += [n for n in shown_loot if n not in picked_loot][:2 - len(picked_loot)]
    else:
        picked_loot = shown_loot[:2]

    if DRAFT_KILL_PICK == "fastest":
        costs = _cost_table(class_name)

        def key(n):
            c = cards[n]
            needed = [r for r in T.MOB_NAMES for flt, _k in c["clauses"] if _clause_matches(flt, class_name, r)]
            return (expected_pulls(c, class_name), sum(costs[r] for r in needed) / len(needed))
        picked_kill = min(shown_kill, key=key)
    else:
        picked_kill = shown_kill[0]
    return picked_loot + [picked_kill]


def choose_scouted(hero, pool, class_name, candidates):
    """Hunting-only override for a Border toll: prefer a candidate that advances a kill quest
    (lowest cost among those); None means 'no preference, use the normal cost pick'."""
    if not hunting(hero, pool):
        return None
    costs = _cost_table(class_name)
    good = [c for c in candidates if advances(hero, pool, class_name, c)]
    return min(good, key=lambda c: costs[_role(c)]) if good else None


# ------------------------------------------------------------------------------- switch


@contextlib.contextmanager
def enable(counts=None, hunt_policy="border", loot_pick="same_zone", kill_pick="fastest",
           starter=True):
    """Turns kill-quest mode on for the duration of the with-block: injects the kill cards into
    macro_sim.QUESTS (so turn-in/decay/death lookups just work), installs the starter-draft hook
    (starter=True; pass a callable (hero, class_name, rng) -> [names] to override, or False to
    leave the engine's own random draw alone), sets the bot policies. Restores everything."""
    import board_engine as BE
    global ENABLED, HUNT_POLICY, DRAFT_LOOT_PICK, DRAFT_KILL_PICK, CARDS
    saved = (ENABLED, HUNT_POLICY, DRAFT_LOOT_PICK, DRAFT_KILL_PICK, CARDS, BE.STARTER_QUEST_HOOK)
    CARDS = build_cards(counts)
    for name in list(CARDS):
        assert name not in M.QUESTS, f"kill card name collides: {name}"
    M.QUESTS.update(CARDS)
    ENABLED, HUNT_POLICY, DRAFT_LOOT_PICK, DRAFT_KILL_PICK = True, hunt_policy, loot_pick, kill_pick
    if callable(starter):
        BE.STARTER_QUEST_HOOK = starter
    elif starter:
        BE.STARTER_QUEST_HOOK = lambda hero, class_name, rng: draft_starter(class_name, rng)
    else:
        BE.STARTER_QUEST_HOOK = None
    try:
        yield CARDS
    finally:
        for name in CARDS:
            M.QUESTS.pop(name, None)
        (ENABLED, HUNT_POLICY, DRAFT_LOOT_PICK, DRAFT_KILL_PICK, CARDS, BE.STARTER_QUEST_HOOK) = saved
