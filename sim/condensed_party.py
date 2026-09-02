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

**Real bug found and fixed 2026-09-01, present since this function was first built, roster-
wide (not scoped to any one class or to M=1) -- caught by validate_multimob_party_of_one(),
the first time this engine was ever actually validated against solo.** The Hero Phase used to
`return True` the instant every mob's HP hit 0, unconditionally -- skipping the Enemy Phase
entirely even when NO killing-blow card was involved. This directly violated the locked
"mob still acts on the round it dies -- no interrupt" rule (DESIGN_DOC.md Section II): any
fight that happened to end on an ordinary (non-killing-blow) kill silently gave the party a
free pass on that round's mob attack, roster-wide, for as long as this module has existed.
The correct logic (`acting_mobs`, right below) was already written and already correct --
it just never got a chance to run, because the premature early return exited first. Fix was
deleting the premature return, not adding a new check. Verified: 810/810 checks clean, full
(unsampled) validate_multimob_party_of_one() pass.

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
trusting it for N=4, same caution best_line_for_party's own docstring already gives). **Moot
for M=1 (a single co-op Elite)** -- with only one mob, every living hero's damage has exactly
one legal target every round, so `damage_targets` needs no search at all for that case.

**Class coverage: all 9 classes ported (2026-09-01).** Warrior/Wizard/Cleric/Paladin/Rogue/
Ranger were already here; Druid/Runecaster/Necromancer added this pass, in that order, each
verified individually before moving to the next -- see the three notes below for what each
one needed. `validate_party_of_one()`: 810 checks, 0 mismatches across the full roster.

**Druid (cleanest of the three -- no Echo, no evasion, no killing-blow card).** Direct copy
of condensed_druid.py's own resolve_round, not re-derived from memory. Caught and fixed a
real, unrelated, pre-existing bug in `_paladin_round` while verifying this port: it hardcoded
the Invocation per-strike bonus as `+1`, stale since Paladin's own rebalance locked
`INVOCATION_PER_STRIKE_BONUS = 2` -- `validate_party_of_one()` had never been re-run since
that rebalance landed, so the drift went uncaught.

**Runecaster and Necromancer both have an Echo mechanic** (a card's damage/heal partially
resolves at the START of the *next* round, stacking with that round's own card damage against
a single depleting Block pool -- see each class's own solo resolve_round docstring for the
real, locked mechanic, fixed 2026-08-30 after a roster-wide Block bug). This engine's
`_..._round()` shape returns one flat `dmg` per round with no notion of a pending cross-round
value. **Resolved by folding Echo directly into the same round's combined `dmg` number,
proven exactly equivalent to the real depleting-pool split for total damage dealt** (not an
approximation -- `min(block,a) + min(block-min(block,a),b) == min(block, a+b)` for any
non-negative a/b/block, confirmed over 200K random trials, zero mismatches, and neither
class's killing-blow check ever reads the intermediate per-source split, only the final
total). Necromancer's Boneguard's Offering (Boosted) also surfaced a real, separate,
pre-existing bug: `simulate_party`/`simulate_party_multimob` both gated heal application
behind `if r["heal"] > 0`, silently dropping the card's intentionally NEGATIVE heal (its
Death Pact HP cost) -- fixed to apply unconditionally in both engines. All three fixes
verified together: 810 checks, 0 mismatches.

**A second, more consequential Block bug found 2026-09-01 while sweeping a candidate co-op
mob, present since both engines were first built, in BOTH of them:** Block was being
subtracted independently from each hero's own damage, then summed, instead of pooling raw
damage first and subtracting Block ONCE as a shared, depleting resource -- the exact same "one
depleting pool per round" principle already locked for solo Echo (2026-08-30), just violated
here across heroes instead of across damage sources. Concretely: two heroes dealing 4 and 5
raw damage against Block=3 should deal (4+5)-3=6 total, not (4-3)+(5-3)=3. This wasn't caught
by `validate_party_of_one()`/`validate_multimob_party_of_one()` because both only ever call
with N=1 -- a single hero never triggers the multi-source sharing this bug lived in, so full
solo-agreement doesn't prove multi-hero correctness. Fixed in `simulate_party` (pool raw
damage across the whole party, subtract Block once, matching that engine's existing pooled-
damage identity) and in `simulate_party_multimob` (each mob's own Block pool depletes across
whichever heroes target it that round, in ascending hero-index order -- no tabletop rule locks
that specific ordering yet, same "deterministic but not a real rule" spirit already used for
this file's other tiebreaks). Also added: an explicit assert in both `simulate_party`/
`simulate_party_multimob` rejecting a party with a duplicate class label -- DESIGN_DOC.md's
Section V locks no duplicate classes in one co-op group (only one physical deck per class
exists), caught after an early test script used two Warriors without checking legality first.
"""
import itertools

import condensed_cleric as C
import condensed_druid as Du
import condensed_necromancer as Nc
import condensed_paladin as P
import condensed_ranger as G
import condensed_rogue as R
import condensed_runecaster as N
import condensed_trip as T
import condensed_warrior as W
import condensed_wizard as Z

CARD_SOURCE = {"warrior": W, "wizard": Z, "cleric": C, "paladin": P, "rogue": R, "ranger": G,
               "druid": Du, "runecaster": N, "necromancer": Nc}
# condensed_trip.py's own lookup tables are keyed by capitalized labels
# ("Warrior"); this module uses lowercase throughout to match MOBS's mob_key
# convention, so a local lowercase copy is needed rather than reusing
# T.HP_ATTR_BY_LABEL directly.
HP_ATTR = {"warrior": "WARRIOR_HP", "wizard": "WIZARD_HP", "cleric": "CLERIC_HP",
           "paladin": "PALADIN_HP", "rogue": "ROGUE_HP", "ranger": "RANGER_HP",
           "druid": "DRUID_HP", "runecaster": "RUNECASTER_HP", "necromancer": "NECROMANCER_HP"}


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
    """Bonus-per-strike reads P.INVOCATION_PER_STRIKE_BONUS (locked at 2, not the original 1)
    -- a prior version of this port hardcoded +1 and went stale when Paladin's own rebalance
    changed the real value, caught by validate_party_of_one() 2026-09-01 while porting Druid."""
    card = P.CARDS[card_name]
    dmg, heal = card["dmg"], card["heal"]
    bonus = P.INVOCATION_PER_STRIKE_BONUS
    strikes_played = state["strikes_played"]
    invocation_played = state["invocation_played"]
    active_invocation = state["active_invocation"]

    if card["invocation"] is not None and not invocation_played:
        invocation_played = True
        active_invocation = card["invocation"]
        if active_invocation == "sanctuary":
            dmg += bonus * strikes_played
        else:
            heal += bonus * strikes_played

    if card["strike"]:
        strikes_played += 1
        if active_invocation == "sanctuary":
            dmg += bonus
        elif active_invocation == "grace":
            heal += bonus

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


def _druid_round(card_name, rnd, state, mob_hp_remaining, mob_hp_total):
    """Ported by direct copy of condensed_druid.py's own resolve_round, not re-derived from
    memory -- that module's own docstring flags the two mutually-exclusive payoff branches
    (shapeshift bonus only once Grizzly's been played, eclipse bonus only while it HASN'T) as
    easy to invert by mistake. No Echo, no evasion, no killing-blow card -- the cleanest of
    the three classes ported into this engine 2026-09-01 (Runecaster/Necromancer's Echo
    mechanic needs the engine itself extended first, see the module docstring)."""
    card = Du.CARDS[card_name]
    dmg, heal, block = card["dmg"], card["heal"], card["block"]
    tag = card["tag"]
    grizzly_played = state["grizzly_played"]
    shapeshift_played = state["shapeshift_played"]
    eclipse_played = state["eclipse_played"]

    if tag == "shapeshift" and card_name != "Shapeshift: Grizzly" and grizzly_played:
        dmg += shapeshift_played
        block += shapeshift_played
    elif tag == "eclipse" and not grizzly_played:
        if card.get("heal_scales_with_eclipse"):
            heal += eclipse_played
        else:
            dmg += eclipse_played

    new_shapeshift_played = shapeshift_played + (1 if tag == "shapeshift" else 0)
    new_eclipse_played = eclipse_played + (1 if tag == "eclipse" else 0)
    new_grizzly_played = grizzly_played or (card_name == "Shapeshift: Grizzly")

    return dict(illegal=False, dmg=dmg, block=block, heal=heal, aggro=card["aggro"],
                killing_blow_eligible=False, grants_range=False, max_hp_buff=0,
                new_state=dict(shapeshift_played=new_shapeshift_played,
                                eclipse_played=new_eclipse_played,
                                grizzly_played=new_grizzly_played))


def _runecaster_round(card_name, rnd, state, mob_hp_remaining, mob_hp_total):
    """Echo (Earth Strike Rune's pending damage/heal from the PREVIOUS round) is folded
    directly into this round's own dmg/heal as one combined number, not resolved as a
    separate depleting-block step the way condensed_runecaster.py's own solo resolve_round
    does it. Proven exactly equivalent for total damage dealt (see this module's own
    docstring for the numeric proof -- min(block,a) + min(block-min(block,a),b) ==
    min(block, a+b) for any non-negative a/b/block, confirmed over 200K random trials, zero
    mismatches) since nothing here reads the intermediate per-source split: Runecaster has no
    killing-blow card, and heal has no absorption mechanic to split at all."""
    card = N.CARDS[card_name]
    pending_echo_dmg = state["pending_echo_dmg"]
    pending_echo_heal = state["pending_echo_heal"]
    prev_card_name = state["prev_card_name"]

    dmg, heal, block = card["dmg"], card["heal"], card["block"]
    if card["chain_bonus_if_prev"] == prev_card_name:
        dmg += card["chain_bonus_dmg"]

    dmg += pending_echo_dmg
    heal += pending_echo_heal

    return dict(illegal=False, dmg=dmg, block=block, heal=heal, aggro=card["aggro"],
                killing_blow_eligible=False, grants_range=card["grants_range"], max_hp_buff=0,
                new_state=dict(pending_echo_dmg=card["echo_dmg"], pending_echo_heal=card["echo_heal"],
                                prev_card_name=card_name))


def _necromancer_round(card_name, rnd, state, mob_hp_remaining, mob_hp_total):
    """Echo (Blight's pending damage from the PREVIOUS round) folded into this round's own dmg
    as one combined number -- same proven-equivalent simplification as Runecaster's port
    above; Necromancer's killing-blow check (Death Blow) only ever reads the FINAL total
    remaining mob HP after both sources, same as solo, so the combined number is exact, not
    an approximation. Boneguard's Offering's Blood Magic boosted variant is computed the same
    on-the-fly way condensed_necromancer.py's own resolve_round does it (never a separate
    CARDS mutation -- see that module's docstring for the regression this project already
    found and fixed once from getting that wrong)."""
    if "(Boosted)" in card_name and card_name not in Nc.CARDS:
        base_name = card_name.replace(" (Boosted)", "")
        base_card = Nc.CARDS[base_name]
        card = dict(base_card)
        card["dmg"] = base_card.get("boosted_dmg", Nc.HP_FOR_DMG_BONUS)
        card["heal"] = base_card.get("boosted_heal", -Nc.HP_FOR_DMG_COST)
        if "boosted_block" in base_card:
            card["block"] = base_card["boosted_block"]
    else:
        card = Nc.CARDS[card_name]

    pending_echo_dmg = state["pending_echo_dmg"]
    dot_played = state["dot_played"]

    dmg, heal, block = card["dmg"], card["heal"], card["block"]
    if card.get("dot_payoff"):
        dmg += dot_played * card.get("dot_multiplier", 1)
    dmg += pending_echo_dmg

    new_dot_played = dot_played + (1 if card.get("dot") else 0)

    return dict(illegal=False, dmg=dmg, block=block, heal=heal, aggro=card["aggro"],
                killing_blow_eligible=card.get("killing_blow", False),
                grants_range=card.get("grants_range", False), max_hp_buff=0,
                new_state=dict(pending_echo_dmg=card.get("echo_dmg", 0), dot_played=new_dot_played))


ROUND_FN = {"warrior": _warrior_round, "wizard": _wizard_round, "cleric": _cleric_round,
            "paladin": _paladin_round, "rogue": _rogue_round, "ranger": _ranger_round,
            "druid": _druid_round, "runecaster": _runecaster_round, "necromancer": _necromancer_round}


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
    if class_label == "druid":
        return dict(shapeshift_played=0, eclipse_played=0, grizzly_played=False)
    if class_label == "runecaster":
        return dict(pending_echo_dmg=0, pending_echo_heal=0, prev_card_name=None)
    if class_label == "necromancer":
        return dict(pending_echo_dmg=0, dot_played=0)
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
    labels = [spec["class_label"] for spec in hero_specs]
    assert len(labels) == len(set(labels)), (
        f"duplicate class in party: {labels} -- DESIGN_DOC.md's Section V locks no duplicate "
        f"classes in one co-op group (only one physical deck per class exists)")

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
            # Unconditional, not `if heal > 0` -- Necromancer's Death Pact (Boneguard's
            # Offering, Boosted) uses a NEGATIVE heal to represent its own HP cost. The old
            # `> 0` gate silently dropped that cost entirely (found 2026-09-01 while porting
            # Necromancer into this engine -- validate_party_of_one() caught a real 4-HP
            # discrepancy between solo and party for the exact same sequence).
            hero_hp[i] = min(hero_hp_cap[i], hero_hp[i] + r["heal"])

        # Block subtracted ONCE from the pooled raw total, not independently from each hero's
        # own damage then summed -- the same "one shared, depleting pool per round" principle
        # already locked for solo Echo (2026-08-30) and the multimob engine (2026-09-01, see
        # simulate_party_multimob below), found here 2026-09-01 while sweeping a candidate
        # co-op mob. This engine already conceptually pools damage (its whole identity), so
        # applying block per-hero-then-summing was a real, separate bug, not a design choice.
        total_raw_dmg = sum(round_results[i]["dmg"] for i in alive_indices)
        total_dmg_dealt = max(0.0, total_raw_dmg - mob_block)
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
    for label in ["warrior", "wizard", "cleric", "paladin", "rogue", "ranger", "druid",
                  "runecaster", "necromancer"]:
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
    Returns (win, hp_left (dict: hero index -> float), rounds, log).

    Real Party Pull play is 2-4 heroes; N=1 is allowed here purely so
    validate_multimob_party_of_one() can use this exact engine to check against solo -- same
    convention simulate_party's own docstring already establishes."""
    n = len(hero_specs)
    m = len(mob_specs)
    assert 1 <= n <= 4, "party size must be 1-4 (1 is validation-only, not real play)"
    labels = [spec["class_label"] for spec in hero_specs]
    assert len(labels) == len(set(labels)), (
        f"duplicate class in party: {labels} -- DESIGN_DOC.md's Section V locks no duplicate "
        f"classes in one co-op group (only one physical deck per class exists)")
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
            # Unconditional, not `if heal > 0` -- Necromancer's Death Pact (Boneguard's
            # Offering, Boosted) uses a NEGATIVE heal to represent its own HP cost. The old
            # `> 0` gate silently dropped that cost entirely (found 2026-09-01 while porting
            # Necromancer into this engine -- validate_party_of_one() caught a real 4-HP
            # discrepancy between solo and party for the exact same sequence).
            hero_hp[i] = min(hero_hp_cap[i], hero_hp[i] + r["heal"])

        starting_alive_mobs = [j for j in range(m) if mob_alive[j]]
        dmg_to_mob = {j: 0.0 for j in starting_alive_mobs}
        killing_blow_hit_mob = {j: False for j in starting_alive_mobs}
        # Each mob's own Block is ONE depleting pool for the round, shared by every hero
        # targeting it -- not reapplied in full to each attacking hero separately (found
        # 2026-09-01 while sweeping a candidate co-op mob; same "one shared, depleting pool"
        # principle already locked for solo Echo, 2026-08-30). Heroes are processed in
        # ascending index order (alive_indices is already sorted), giving a deterministic
        # first-come-first-served split when multiple heroes target the same mob -- no
        # tabletop rule for that ordering exists yet, same "deterministic but not a real
        # rule" spirit this file already uses for hero/mob tiebreaks elsewhere.
        remaining_block_for_mob = {j: mob_specs[j]["pattern"][rnd][1] for j in starting_alive_mobs}
        for i in alive_indices:
            r = round_results[i]
            j = r["target"]
            absorbed = min(remaining_block_for_mob[j], r["dmg"])
            remaining_block_for_mob[j] -= absorbed
            dmg_to_mob[j] += r["dmg"] - absorbed
            if r["killing_blow_eligible"]:
                killing_blow_hit_mob[j] = True

        mob_died_this_round = {}
        for j in starting_alive_mobs:
            mob_hp[j] -= dmg_to_mob[j]
            mob_died_this_round[j] = mob_hp[j] <= 0
            if mob_died_this_round[j]:
                mob_alive[j] = False

        # No early return here even if every mob is now dead -- a mob killed by ordinary
        # (non-killing-blow) damage still gets its attack in this round, matching solo's
        # "no interrupt" rule (DESIGN_DOC.md Section II). A premature `if not any(mob_alive):
        # return True` here (removed 2026-09-01, found while validating the M=1 best-line
        # search against solo) skipped the Enemy Phase unconditionally whenever the LAST mob
        # died, even without a killing-blow card -- silently dropping that round's mob attack
        # in every such case, not just the killing-blow-legitimate ones. The `acting_mobs`
        # filter just below already correctly excludes ONLY killing-blow kills; letting
        # control flow continue into it is the actual fix, not a new check.

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


def best_line_for_party_multimob_single(class_labels, hero_hands, mob_pattern, mob_hp, starting_hps=None):
    """The M=1 case of a best-line search over simulate_party_multimob -- built 2026-09-01
    specifically for a single tough co-op Elite, where the general `damage_targets` search
    the module docstring flags as an unbuilt TODO is moot: with only one mob, every living
    hero's damage has exactly one legal target every round, so there's nothing to search over
    beyond each hero's own (ordering[, stance]) space -- same shape best_line_for_party
    already searches, just resolved through the round-robin engine (correct for Elites)
    instead of the pooled one (Boss-tier only, wrong engine for this case). Ranks by (win,
    total party HP left), same convention as best_line_for_party. Returns
    (hero_specs, hp_left, rounds)."""
    n = len(class_labels)
    if starting_hps is None:
        starting_hps = [None] * n
    per_hero_lines = [_hero_lines(class_labels[i], hero_hands[i]) for i in range(n)]
    # simulate_party_multimob requires 3-tuples (unlike simulate_party, which has a 2-tuple
    # fallback) -- normalize here so callers can pass either shape, matching every class's
    # own T.MOBS entry regardless of whether that class is range-tagged.
    normalized_pattern = [entry if len(entry) == 3 else (entry[0], entry[1], "melee")
                           for entry in mob_pattern]
    mob_specs = [dict(pattern=normalized_pattern, hp=mob_hp)]
    # Every living hero targets the only mob, every round -- no search needed for this part.
    damage_targets = [{i: 0 for i in range(n)} for _ in range(3)]

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
        win, hp_left, rounds, _ = simulate_party_multimob(hero_specs, mob_specs, damage_targets)
        key = (win, sum(hp_left.values()))
        if best is None or key > best[0]:
            best = (key, (hero_specs, hp_left, rounds))
    return best[1]


def validate_multimob_party_of_one(sample_every=3):
    """Safety net for best_line_for_party_multimob_single, mirroring validate_party_of_one's
    shape: for every class, every real Standard-tier mob, and every Nth hand, confirms the M=1
    round-robin search reproduces that class's own solo best_line_for_hand/simulate exactly.
    Proves the M=1 degenerate case of the round-robin engine (single mob, trivial targeting)
    is a faithful match for solo, not just assumed from the module docstring's own claim that
    "Elite fights are simply the M=1 case of this same engine." sample_every=3 by default
    (not 1, unlike validate_party_of_one) purely for runtime -- this calls the full N=1
    multimob joint search per hand/mob, not the cheaper pooled-engine path."""
    mismatches = []
    checks = 0
    for label in ["warrior", "wizard", "cleric", "paladin", "rogue", "ranger", "druid",
                  "runecaster", "necromancer"]:
        mod = CARD_SOURCE[label]
        max_hp = float(getattr(mod, HP_ATTR[label]))
        for mob_name in T.MOB_NAMES:
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

                hero_specs, hp_left_party, rounds_party = best_line_for_party_multimob_single(
                    [label], [hand], pattern, mob_hp, starting_hps=[max_hp])
                normalized_pattern = [entry if len(entry) == 3 else (entry[0], entry[1], "melee")
                                       for entry in pattern]
                mob_specs = [dict(pattern=normalized_pattern, hp=mob_hp)]
                damage_targets = [{0: 0} for _ in range(3)]
                win_party, hp_left_party2, rounds_party2, _ = simulate_party_multimob(
                    hero_specs, mob_specs, damage_targets)

                solo_result = (win_solo, hp_left_solo, rounds_solo)
                party_result = (win_party, hp_left_party2[0], rounds_party2)
                if solo_result != party_result:
                    mismatches.append(dict(label=label, mob=mob_name, hand=hand,
                                            solo=solo_result, party=party_result,
                                            hero_specs=hero_specs))
    print(f"validate_multimob_party_of_one: {checks} checks, {len(mismatches)} mismatches")
    return mismatches


if __name__ == "__main__":
    mismatches = validate_party_of_one()
    if mismatches:
        for m in mismatches[:5]:
            print(m)
    else:
        print("Party-of-one reproduces solo exactly across every class/mob/hand checked.")

    mismatches2 = validate_multimob_party_of_one()
    if mismatches2:
        for m in mismatches2[:5]:
            print(m)
    else:
        print("Multimob-party-of-one (M=1) reproduces solo exactly across every class/mob/hand checked.")
