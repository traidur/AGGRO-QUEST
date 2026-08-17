"""
Multi-hero Party Pull combat resolution -- two separate engines living in one module, per
OPEN_QUESTIONS.md's "Co-op multi-hero vs. Elite/multi-mob nodes" entry.

**simulate_party() / best_line_for_party() -- the original pooled engine, Boss-tier only.**
Damage and Block both pool across the whole party against one shared mob HP; one Aggro-
decided hero eats any leftover. Fully built and validated (validate_party_of_one() is a
540-check regression proving it reproduces solo exactly). Reclassified mid-project: this is
NOT the general "single mob" rule -- it's specifically reserved for a future Boss tier (not
yet designed, zero Bosses exist) where the whole party defends as one unit against one shared
threat. It has no live use case today.

**simulate_party_multimob() -- the current primary co-op engine**, covering both real
multi-mob nodes and Elite fights (which just degenerate to the trivial M=1 case: only the
loudest hero is ever assigned the mob's attack, everyone else's own block goes unused that
round, since nothing pools outside a Boss fight). Mobs are tracked as fully separate
entities (own HP, own round-by-round atk/block/mob_type) -- no stat-merging, ever. See
gemini_prompt_multimob_coop.md for the full design write-up (sent for external review) and
OPEN_QUESTIONS.md for the locked rules this implements. Which engine governs a fight is fixed
by how the node *starts* and never changes mid-fight -- a multi-mob node that whittles down to
one surviving mob stays on simulate_party_multimob for its remaining rounds.

Layering discipline matches macro_sim.py: sits on top of the six class modules and
condensed_trip.py, never modifies their internals. Each class's per-round mechanic is
ported into a small `_..._round()` function below -- a faithful re-expression of that
class's own simulate()/`_sim_from`, read directly from the real file while porting, every
numeric value pulled from the real CARDS dict rather than hand-copied. Both engines share
these same per-class resolvers, ROUND_FN, _initial_state, and HP_ATTR -- a hero's own card
mechanics don't change based on which engine is resolving the fight, only how damage/block/
targeting flow between hero and mob(s) does.

validate_party_of_one() is the safety net proving each per-class port is correct: called
through simulate_party() with exactly one hero, must reproduce that class's own solo
best_line_for_hand/simulate exactly, or the port has a bug. Run it before trusting anything
else in this module.

## simulate_party() rules (Boss-tier engine, pooled)
- Party size 2-4, any class mix. Still 3 rounds, one card per hero per round.
- Damage pools into one shared mob HP (whittles across rounds, doesn't reset). Block pools
  to mitigate the mob's one attack that round. Leftover (if any) is assigned to whoever
  played the highest-Aggro card that round; ties broken by highest raw damage among the
  tied cards; a further tie is left to table agreement (the solver breaks it arbitrarily
  by hero index, flagged in _resolve_target -- not a real rule).
- grants_range only matters if the evading hero would have been the round's target: in that
  case the leftover is nullified for everyone (not redirected), otherwise the card does
  nothing that round. Melee-mob-only, same as solo.
- A killing-blow-tagged card (Warrior's Execute, Rogue's Cutthroat) played by ANY hero,
  combined with the party's pooled damage killing the mob that round, prevents the mob's
  attack for the whole party that round -- same semantics as solo, evaluated against the
  shared pool instead of one hero's own damage.
- If the targeted hero's HP can't absorb the leftover, they just die -- no spillover.
- Hero death mid-pull: survivors keep fighting. A dead hero contributes nothing and is never
  a valid Aggro target again. Win = mob hits 0 HP before every hero is dead. Loss = every
  hero hits 0 HP first. Flee = 3 rounds pass, mob alive, at least one hero still standing.

## simulate_party_multimob() rules (current primary co-op engine, no pooling)
- Mobs stay fully separate: own HP, own 3-round (atk, block, mob_type) pattern.
- No pooling and no splitting anywhere. Each hero's own card damage is independently pointed
  at exactly one mob (the caller supplies this choice via `damage_targets`, one target index
  per living hero per round -- this module does not yet search for the best assignment, see
  the module-level TODO below). Multiple heroes can target the same mob; their damage adds
  up naturally there, but no shared pooled number is ever computed.
- A mob killed by ordinary (non-killing-blow) damage still gets its attack in this round --
  matches solo's existing "a mob dying this round doesn't by itself skip its attack" rule.
  Killing-blow riders are scoped per-mob (a real change from the pooled engine's party-wide
  version): a killing-blow card only prevents an attack from the specific mob its own damage
  was pointed at, if that mob dies this round. No effect on any other mob.
- Enemy Phase, once Hero Phase damage has resolved: rank living heroes by this round's Aggro
  (loudest first, same tiebreak as the pooled engine). Rank acting mobs (alive at the start of
  this round, minus any killed by a killing blow aimed at them) by this round's printed ATK,
  highest first -- tiebreak not yet locked as a tabletop rule (OPEN_QUESTIONS.md flags this
  open); the solver breaks it by remaining HP then mob index, same "deterministic but not a
  real rule" spirit as the pooled engine's hero tiebreak.
- Round-robin assign: highest-ATK acting mob to loudest hero, next to next-loudest, ...,
  wrapping back to the loudest hero again if mobs outnumber heroes. Not capped at party size.
- grants_range: a hero stays in the round-robin assignment regardless of whether they're
  evading -- any of *their* assigned attacks from a melee-type mob are zeroed, first-assigned
  or wrapped-second alike. Ranged mobs unaffected.
- Block is personal only, never routed to an ally, never split. Applies automatically to the
  first NON-ZEROED assigned attack in a hero's list (largest real threat, not just
  structurally-first -- if grants_range zeroed the structurally-first attack, block moves to
  protect the next real one instead; this specific wrinkle wasn't discussed explicitly with
  the user and is a judgment call made while implementing, flagged here rather than silently
  assumed). Proven optimal among genuinely-incoming attacks in OPEN_QUESTIONS.md.
- Overflow and death: unblocked damage from each of a hero's assigned attacks comes only out
  of that hero's own HP, no spillover. A dead hero drops out of all future rounds' Aggro
  ranking, round-robin assignment, and damage targeting. Win = every mob dead before every
  hero. Loss = every hero dead first. Flee = 3 rounds pass with both sides still standing.

**TODO, not yet built:** a best-line search over `damage_targets` choices (mirrors
best_line_for_party but adds a per-hero-per-round target-mob choice on top of the existing
ordering/stance search space -- flagged as a real, separate combinatorics question before
trusting it for N=4, same caution best_line_for_party's own docstring already gives).
"""
import itertools

import condensed_cleric as C
import condensed_paladin as P
import condensed_ranger as G
import condensed_rogue as R
import condensed_trip as T
import condensed_warrior as W
import condensed_wizard as Z

CARD_SOURCE = {"warrior": W, "wizard": Z, "cleric": C, "paladin": P, "rogue": R, "ranger": G}
# condensed_trip.py's own lookup tables are keyed by capitalized labels
# ("Warrior"); this module uses lowercase throughout to match MOBS's mob_key
# convention, so a local lowercase copy is needed rather than reusing
# T.HP_ATTR_BY_LABEL directly.
HP_ATTR = {"warrior": "WARRIOR_HP", "wizard": "WIZARD_HP", "cleric": "CLERIC_HP",
           "paladin": "PALADIN_HP", "rogue": "ROGUE_HP", "ranger": "RANGER_HP"}


# ---------------------------------------------------------------------------
# Per-class one-round resolvers. Each takes (card_name, round_idx (0-2),
# hero_state, mob_hp_remaining, mob_hp_total) and returns a dict:
#   dmg, block, heal, aggro, killing_blow_eligible, grants_range, max_hp_buff,
#   new_state, illegal (True only for a Warrior Execute played out of legality)
# mob_hp_remaining/mob_hp_total are the SHARED party pool -- the only two
# mechanics that ever need them are Warrior's Execute legality check and the
# killing-blow check (handled by the engine after pooling, not here).
# ---------------------------------------------------------------------------

def _warrior_round(card_name, rnd, state, mob_hp_remaining, mob_hp_total):
    stance = state["stance"]
    sunder_stacks = state["sunder_stacks"]
    prev_card_name = state["prev_card_name"]
    card = W.CARDS[card_name]

    if card["execute_finisher"]:
        if mob_hp_remaining > mob_hp_total * 0.5:
            return dict(illegal=True)
        dmg, block = 6, 0
    else:
        dmg, block = card[stance]

    if card["chain_stance"] == stance and prev_card_name == card["chain_requires"]:
        if card["chain_target"] == "block":
            block += card["chain_bonus"]
        else:
            dmg += card["chain_bonus"]

    eff_dmg = dmg + (W.SUNDER_BONUS * sunder_stacks if dmg > 0 else 0)
    new_sunder = sunder_stacks + (1 if card["sunder"] else 0)
    aggro = card["aggro"] if "aggro" in card else card[f"aggro_{stance}"]

    return dict(illegal=False, dmg=eff_dmg, block=block, heal=0, aggro=aggro,
                killing_blow_eligible=card.get("killing_blow", False), grants_range=False,
                max_hp_buff=0,
                new_state=dict(stance=stance, sunder_stacks=new_sunder, prev_card_name=card_name))


def _wizard_round(card_name, rnd, state, mob_hp_remaining, mob_hp_total):
    weave_armed = state["weave_armed"]
    card = Z.CARDS[card_name]
    use_boost = card["payoff"] and weave_armed
    dmg = card["dmg"][1] if use_boost else card["dmg"][0]

    if card["weave_source"]:
        new_weave_armed = True
    elif use_boost:
        new_weave_armed = False
    else:
        new_weave_armed = weave_armed

    return dict(illegal=False, dmg=dmg, block=card["block"], heal=0, aggro=card["aggro"],
                killing_blow_eligible=False, grants_range=card["grants_range"], max_hp_buff=0,
                new_state=dict(weave_armed=new_weave_armed))


def _cleric_round(card_name, rnd, state, mob_hp_remaining, mob_hp_total):
    card = C.CARDS[card_name]
    heal = card["heal"] + (C.SACRED_BALANCE_HEAL if card["sacred_balance"] else 0)
    return dict(illegal=False, dmg=card["dmg"], block=card["block"], heal=heal, aggro=card["aggro"],
                killing_blow_eligible=False, grants_range=False, max_hp_buff=card["max_hp_buff"],
                new_state=dict())


def _paladin_round(card_name, rnd, state, mob_hp_remaining, mob_hp_total):
    card = P.CARDS[card_name]
    dmg, heal = card["dmg"], card["heal"]
    strikes_played = state["strikes_played"]
    invocation_played = state["invocation_played"]
    active_invocation = state["active_invocation"]

    if card["invocation"] is not None and not invocation_played:
        invocation_played = True
        active_invocation = card["invocation"]
        if active_invocation == "sanctuary":
            dmg += strikes_played
        else:
            heal += strikes_played

    if card["strike"]:
        strikes_played += 1
        if active_invocation == "sanctuary":
            dmg += 1
        elif active_invocation == "grace":
            heal += 1

    return dict(illegal=False, dmg=dmg, block=card["block"], heal=heal, aggro=card["aggro"],
                killing_blow_eligible=False, grants_range=False, max_hp_buff=0,
                new_state=dict(strikes_played=strikes_played, invocation_played=invocation_played,
                                active_invocation=active_invocation))


def _rogue_round(card_name, rnd, state, mob_hp_remaining, mob_hp_total):
    card = R.CARDS[card_name]
    kind = card["kind"]
    strikes_played = state["strikes_played"]

    if kind == "finisher":
        dmg = card["curve"][min(strikes_played, 2)]
        strikes_played = 0
    elif kind == "opener":
        dmg = card["round1_dmg"] if rnd == 0 else card["dmg"]
    else:
        dmg = card["dmg"]

    if card["strike"]:
        strikes_played += 1

    killing_blow_eligible = kind == "finisher" and card.get("killing_blow", False)
    return dict(illegal=False, dmg=dmg, block=card["block"], heal=0, aggro=card["aggro"],
                killing_blow_eligible=killing_blow_eligible, grants_range=False, max_hp_buff=0,
                new_state=dict(strikes_played=strikes_played))


def _ranger_round(card_name, rnd, state, mob_hp_remaining, mob_hp_total):
    card = G.CARDS[card_name]
    beast_active = state["beast_active"] or card["beast_bond"]
    prev_grants_range = state["prev_grants_range"]

    if card["payoff_prev_range"]:
        dmg = card["dmg_if_prev_range"] if prev_grants_range else card["dmg_else"]
    elif card.get("payoff_wolf"):
        dmg = card["dmg_if_wolf"] if beast_active else card["dmg_else"]
    else:
        dmg = card["dmg"]

    block = card["block"] + (G.CARDS["Beast Bond: Wolf"]["beast_block_value"] if beast_active else 0)

    return dict(illegal=False, dmg=dmg, block=block, heal=0, aggro=card["aggro"],
                killing_blow_eligible=False, grants_range=card["grants_range"], max_hp_buff=0,
                new_state=dict(beast_active=beast_active, prev_grants_range=card["grants_range"]))


ROUND_FN = {"warrior": _warrior_round, "wizard": _wizard_round, "cleric": _cleric_round,
            "paladin": _paladin_round, "rogue": _rogue_round, "ranger": _ranger_round}


def _initial_state(class_label, stance=None):
    if class_label == "warrior":
        return dict(stance=stance, sunder_stacks=0, prev_card_name=None)
    if class_label == "wizard":
        return dict(weave_armed=False)
    if class_label == "cleric":
        return dict()
    if class_label == "paladin":
        return dict(strikes_played=0, invocation_played=False, active_invocation=None)
    if class_label == "rogue":
        return dict(strikes_played=0)
    if class_label == "ranger":
        return dict(beast_active=False, prev_grants_range=False)
    raise ValueError(class_label)


def _resolve_target(round_results, alive_indices):
    """Highest Aggro tanks the leftover; ties broken by highest raw damage among the tied
    cards; a still-remaining tie is left to table agreement in real play -- the solver picks
    the lowest hero index deterministically so it always returns a single answer, not a rule."""
    max_aggro = max(round_results[i]["aggro"] for i in alive_indices)
    tied = [i for i in alive_indices if round_results[i]["aggro"] == max_aggro]
    if len(tied) > 1:
        max_dmg = max(round_results[i]["dmg"] for i in tied)
        tied = [i for i in tied if round_results[i]["dmg"] == max_dmg]
    return tied[0]


def simulate_party(hero_specs, mob_pattern, mob_hp):
    """hero_specs: list of 2-4 dicts, each {class_label, seq_cards (3 cards),
    starting_hp (optional, defaults to that class's max HP), stance (Warrior only)}.
    mob_pattern: 3 rounds of (atk, block) or (atk, block, mob_type) -- mob_type defaults
    to 'melee' if omitted. Returns (win, hp_left (dict: hero index -> float), rounds, log)."""
    n = len(hero_specs)
    # Real Party Pull play is 2-4 heroes; N=1 is allowed here purely so
    # validate_party_of_one() can use this exact engine to check against solo.
    assert 1 <= n <= 4, "party size must be 1-4 (1 is validation-only, not real play)"

    hero_hp, hero_hp_cap, hero_state, hero_alive = [], [], [], []
    for spec in hero_specs:
        lbl = spec["class_label"]
        mod = CARD_SOURCE[lbl]
        max_hp = float(getattr(mod, HP_ATTR[lbl]))
        hero_hp.append(spec.get("starting_hp", max_hp))
        hero_hp_cap.append(max_hp)
        hero_alive.append(True)
        hero_state.append(_initial_state(lbl, spec.get("stance")))

    remaining_mob_hp = float(mob_hp)
    mob_hp_total = float(mob_hp)
    log = []

    for rnd in range(3):
        entry = mob_pattern[rnd]
        mob_atk, mob_block, mob_type = entry if len(entry) == 3 else (entry[0], entry[1], "melee")

        round_results = [None] * n
        for i, spec in enumerate(hero_specs):
            if not hero_alive[i]:
                continue
            result = ROUND_FN[spec["class_label"]](spec["seq_cards"][rnd], rnd, hero_state[i],
                                                     remaining_mob_hp, mob_hp_total)
            if result.get("illegal"):
                return False, {i: float("-inf") for i in range(n)}, rnd, log
            hero_state[i] = result["new_state"]
            round_results[i] = result

        alive_indices = [i for i in range(n) if hero_alive[i]]

        for i in alive_indices:
            r = round_results[i]
            hero_hp_cap[i] += r["max_hp_buff"]
            if r["heal"] > 0:
                hero_hp[i] = min(hero_hp_cap[i], hero_hp[i] + r["heal"])

        total_dmg_dealt = sum(max(0.0, round_results[i]["dmg"] - mob_block) for i in alive_indices)
        total_block = sum(round_results[i]["block"] for i in alive_indices)
        any_killing_blow = any(round_results[i]["killing_blow_eligible"] for i in alive_indices)

        new_remaining = remaining_mob_hp - total_dmg_dealt
        mob_dies_this_round = new_remaining <= 0
        leftover = max(0.0, mob_atk - total_block)
        prevented = any_killing_blow and mob_dies_this_round
        target_idx = None

        if leftover > 0 and not prevented:
            target_idx = _resolve_target(round_results, alive_indices)
            target = round_results[target_idx]
            if target["grants_range"] and mob_type == "melee":
                pass  # evaded -- the designated target dodges, nobody else takes it
            else:
                hero_hp[target_idx] -= leftover
                if hero_hp[target_idx] <= 0:
                    hero_alive[target_idx] = False

        remaining_mob_hp = new_remaining
        log.append(dict(round=rnd + 1, dmg_dealt=total_dmg_dealt, block=total_block,
                         leftover=leftover, target=target_idx, mob_hp_after=remaining_mob_hp,
                         alive=list(hero_alive)))

        if not any(hero_alive):
            return False, {i: hero_hp[i] for i in range(n)}, rnd + 1, log
        if remaining_mob_hp <= 0:
            return True, {i: hero_hp[i] for i in range(n)}, rnd + 1, log

    return False, {i: hero_hp[i] for i in range(n)}, 3, log


def _hero_lines(class_label, hand):
    mod = CARD_SOURCE[class_label]
    orderings = mod.orderings(hand)
    if class_label == "warrior":
        return [(seq, stance) for seq in orderings for stance in ("G", "C")]
    return [(seq, None) for seq in orderings]


def best_line_for_party(class_labels, hero_hands, mob_pattern, mob_hp, starting_hps=None):
    """class_labels/hero_hands: matching lists, one entry per hero (2-4). Brute-force joint
    search across every hero's (ordering[, stance]) space -- product of each hero's ~90-line
    solo search space (N=2 ~8K, N=3 ~730K, N=4 ~65M; time N=4 before trusting it for repeated
    diagnostic use, per the plan's verification step). Ranks by (win, total party HP left),
    the natural sum-generalization of solo's single-hero (win, hp_left) key -- a judgment
    call, not a locked design decision, easy to change later if a different aggregate proves
    more useful. Returns (hero_specs, hp_left, rounds)."""
    n = len(class_labels)
    if starting_hps is None:
        starting_hps = [None] * n
    per_hero_lines = [_hero_lines(class_labels[i], hero_hands[i]) for i in range(n)]

    best = None
    for combo in itertools.product(*per_hero_lines):
        hero_specs = []
        for i in range(n):
            seq, stance = combo[i]
            spec = dict(class_label=class_labels[i], seq_cards=seq)
            if stance is not None:
                spec["stance"] = stance
            if starting_hps[i] is not None:
                spec["starting_hp"] = starting_hps[i]
            hero_specs.append(spec)
        win, hp_left, rounds, _ = simulate_party(hero_specs, mob_pattern, mob_hp)
        key = (win, sum(hp_left.values()))
        if best is None or key > best[0]:
            best = (key, (hero_specs, hp_left, rounds))
    return best[1]


def validate_party_of_one(sample_every=1):
    """Safety net: for every class, every real Standard-tier mob, and every hand (or every
    Nth hand if sample_every>1, for a quick pass), confirms best_line_for_party called with
    exactly one hero reproduces that class's own best_line_for_hand/simulate exactly --
    proves _..._round() is a faithful port of the real, locked class files, not a silent
    drift. Returns a list of mismatches (empty means clean)."""
    mismatches = []
    checks = 0
    for label in ["warrior", "wizard", "cleric", "paladin", "rogue", "ranger"]:
        mod = CARD_SOURCE[label]
        max_hp = float(getattr(mod, HP_ATTR[label]))
        for mob_name in T.MOB_NAMES:
            # each class's own native pattern shape (2-tuple or 3-tuple) --
            # solo simulate() for a non-range-tagged class errors on a 3-tuple,
            # so this can't be a single shared shape across classes.
            pattern, mob_hp = T.MOBS[mob_name][label]
            for idx, hand in enumerate(mod.ALL_HANDS):
                if idx % sample_every != 0:
                    continue
                checks += 1
                if label == "warrior":
                    seq, stance, hp_left_solo, rounds_solo = T._best_line(mod, True, hand, pattern, mob_hp, max_hp)
                    win_solo, _, _ = T._simulate(mod, True, seq, stance, pattern, mob_hp, max_hp)
                else:
                    seq, hp_left_solo, rounds_solo = mod.best_line_for_hand(hand, pattern, mob_hp, starting_hp=max_hp)
                    win_solo, _, _ = mod.simulate(seq, pattern, mob_hp, starting_hp=max_hp)

                hero_specs, hp_left_party, rounds_party = best_line_for_party(
                    [label], [hand], pattern, mob_hp, starting_hps=[max_hp])
                win_party, hp_left_party2, rounds_party2, _ = simulate_party(hero_specs, pattern, mob_hp)

                solo_result = (win_solo, hp_left_solo, rounds_solo)
                party_result = (win_party, hp_left_party2[0], rounds_party2)
                if solo_result != party_result:
                    mismatches.append(dict(label=label, mob=mob_name, hand=hand,
                                            solo=solo_result, party=party_result,
                                            hero_specs=hero_specs))
    print(f"validate_party_of_one: {checks} checks, {len(mismatches)} mismatches")
    return mismatches


# ---------------------------------------------------------------------------
# Multi-mob engine (current primary co-op engine -- see module docstring).
# ---------------------------------------------------------------------------

def simulate_party_multimob(hero_specs, mob_specs, damage_targets):
    """hero_specs: same shape as simulate_party (2-4 dicts: class_label, seq_cards,
    starting_hp, stance). mob_specs: list of 1+ dicts {pattern: [(atk, block, mob_type)] x3,
    hp}. damage_targets: 3 rounds, each a dict {hero_index: mob_index} naming which mob that
    hero's damage is aimed at this round (only living heroes need an entry; the caller picks
    a legal, currently-alive mob -- this function doesn't search for the best assignment).
    Returns (win, hp_left (dict: hero index -> float), rounds, log)."""
    n = len(hero_specs)
    m = len(mob_specs)
    assert 2 <= n <= 4, "party size must be 2-4"
    assert m >= 1, "at least one mob required"

    hero_hp, hero_hp_cap, hero_state, hero_alive = [], [], [], []
    for spec in hero_specs:
        lbl = spec["class_label"]
        mod = CARD_SOURCE[lbl]
        max_hp = float(getattr(mod, HP_ATTR[lbl]))
        hero_hp.append(spec.get("starting_hp", max_hp))
        hero_hp_cap.append(max_hp)
        hero_alive.append(True)
        hero_state.append(_initial_state(lbl, spec.get("stance")))

    mob_hp = [float(spec["hp"]) for spec in mob_specs]
    mob_hp_total = [float(spec["hp"]) for spec in mob_specs]
    mob_alive = [True] * m
    log = []

    for rnd in range(3):
        alive_indices = [i for i in range(n) if hero_alive[i]]
        targets_this_round = damage_targets[rnd]

        # ---- Hero Phase: each living hero's card resolves against their chosen target ----
        round_results = {}
        for i in alive_indices:
            spec = hero_specs[i]
            tgt = targets_this_round[i]
            assert mob_alive[tgt], f"round {rnd+1}: hero {i} targeted dead mob {tgt}"
            result = ROUND_FN[spec["class_label"]](spec["seq_cards"][rnd], rnd, hero_state[i],
                                                     mob_hp[tgt], mob_hp_total[tgt])
            if result.get("illegal"):
                return False, {i: float("-inf") for i in range(n)}, rnd, log
            hero_state[i] = result["new_state"]
            result["target"] = tgt
            round_results[i] = result

        for i in alive_indices:
            r = round_results[i]
            hero_hp_cap[i] += r["max_hp_buff"]
            if r["heal"] > 0:
                hero_hp[i] = min(hero_hp_cap[i], hero_hp[i] + r["heal"])

        starting_alive_mobs = [j for j in range(m) if mob_alive[j]]
        dmg_to_mob = {j: 0.0 for j in starting_alive_mobs}
        killing_blow_hit_mob = {j: False for j in starting_alive_mobs}
        for i in alive_indices:
            r = round_results[i]
            j = r["target"]
            mob_atk_j, mob_block_j, mob_type_j = mob_specs[j]["pattern"][rnd]
            dmg_to_mob[j] += max(0.0, r["dmg"] - mob_block_j)
            if r["killing_blow_eligible"]:
                killing_blow_hit_mob[j] = True

        mob_died_this_round = {}
        for j in starting_alive_mobs:
            mob_hp[j] -= dmg_to_mob[j]
            mob_died_this_round[j] = mob_hp[j] <= 0
            if mob_died_this_round[j]:
                mob_alive[j] = False

        if not any(mob_alive):
            log.append(dict(round=rnd + 1, phase="hero_only", dmg_to_mob=dict(dmg_to_mob),
                             mob_hp_after=list(mob_hp)))
            return True, {i: hero_hp[i] for i in range(n)}, rnd + 1, log

        # ---- Enemy Phase ----
        # A mob killed this round still gets its attack in UNLESS a killing-blow card was
        # specifically aimed at it (matches solo: ordinary lethal damage doesn't skip the
        # mob's own attack that round).
        acting_mobs = [j for j in starting_alive_mobs
                       if not (mob_died_this_round[j] and killing_blow_hit_mob[j])]

        hero_rank = sorted(alive_indices,
                            key=lambda i: (-round_results[i]["aggro"], -round_results[i]["dmg"], i))
        mob_rank = sorted(acting_mobs,
                           key=lambda j: (-mob_specs[j]["pattern"][rnd][0], -mob_hp[j], j))

        assigned = {i: [] for i in hero_rank}
        n_heroes = len(hero_rank)
        for p, j in enumerate(mob_rank):
            assigned[hero_rank[p % n_heroes]].append(j)

        round_leftover = {}
        for i in alive_indices:
            attacks = []
            for j in assigned[i]:
                mob_atk_j, mob_block_j, mob_type_j = mob_specs[j]["pattern"][rnd]
                evaded = round_results[i]["grants_range"] and mob_type_j == "melee"
                attacks.append(0.0 if evaded else mob_atk_j)

            hero_block = round_results[i]["block"]
            # Own block auto-applies to the first genuinely-incoming (non-evaded) attack --
            # never the structurally-first slot if that one was zeroed by grants_range.
            for idx, val in enumerate(attacks):
                if val > 0:
                    attacks[idx] = max(0.0, val - hero_block)
                    break

            total_taken = sum(attacks)
            round_leftover[i] = total_taken
            if total_taken > 0:
                hero_hp[i] -= total_taken
                if hero_hp[i] <= 0:
                    hero_alive[i] = False

        log.append(dict(round=rnd + 1, dmg_to_mob=dict(dmg_to_mob), assigned=dict(assigned),
                         leftover=round_leftover, mob_hp_after=list(mob_hp),
                         alive=list(hero_alive)))

        if not any(hero_alive):
            return False, {i: hero_hp[i] for i in range(n)}, rnd + 1, log
        if not any(mob_alive):
            return True, {i: hero_hp[i] for i in range(n)}, rnd + 1, log

    return False, {i: hero_hp[i] for i in range(n)}, 3, log


if __name__ == "__main__":
    mismatches = validate_party_of_one()
    if mismatches:
        for m in mismatches[:5]:
            print(m)
    else:
        print("Party-of-one reproduces solo exactly across every class/mob/hand checked.")
