"""
Interactive step-by-step engine for condensed combat, ALL 9 classes -- built for human play
(a future CLI/web front end calls this, never each other) AND for QuestIntelligence.decide_combat.

Promoted from the old playtest_engine.py (a 4-class prototype with its own per-class
_resolve_<class>_round reimplementations) per unified-sprouting-aurora.md's Part 2. That
promotion is already done: every condensed_<class>.py now owns its own resolve_round(), the
ONE place that class's card-effect logic lives -- this module never reimplements any of it,
it only drives each class's resolve_round() one round at a time via a single generic loop and
tracks the surrounding PullState (hand, played cards, outcome). best_line_for_hand() is reused
directly (never reimplemented) for best_line_reveal() and for QuestIntelligence.decide_combat's
cache-and-replay, so neither can ever drift from the balance-tested solver.

playtest_engine.py itself is untouched (still serves playtest_cli.py/playtest_web.py's existing
4-class UI) -- retiring it in favor of this module is out of scope here (Part 5 step 7, "Human
UI extension," explicitly sequenced last).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Optional

import condensed_cleric as C
import condensed_druid as D
import condensed_necromancer as N
import condensed_paladin as P
import condensed_ranger as Ra
import condensed_rogue as Ro
import condensed_runecaster as Rc
import condensed_trip as T
import condensed_warrior as W
import condensed_wizard as Z
from combat_round import RoundState

CARD_SOURCE = {
    "warrior": W, "wizard": Z, "cleric": C, "paladin": P, "rogue": Ro,
    "ranger": Ra, "runecaster": Rc, "druid": D, "necromancer": N,
}
HP_ATTR = {
    "warrior": "WARRIOR_HP", "wizard": "WIZARD_HP", "cleric": "CLERIC_HP",
    "paladin": "PALADIN_HP", "rogue": "ROGUE_HP", "ranger": "RANGER_HP",
    "runecaster": "RUNECASTER_HP", "druid": "DRUID_HP", "necromancer": "NECROMANCER_HP",
}
# Whether a pull's healing cap starts at the ENTERING hp (starting_hp, possibly carried over
# below the class's true max from a previous pull) or at the class's own fixed HP constant --
# mirrors each class's own simulate() seeding line exactly (`hp, remaining, max_hp =
# starting_hp, mob_hp, <X>`), read directly off every condensed_<class>.py rather than
# inferred. Only matters for classes with an actual heal card (Cleric/Paladin/Runecaster/
# Druid/Necromancer all seed to their fixed constant so healing isn't capped at a reduced
# carried-over ceiling); Warrior/Wizard/Rogue/Ranger have no heal mechanic at all, so it's a
# provably no-op there either way -- but getting this wrong for the other five silently
# undercounts healing across a chained multi-pull run without ever showing up in a single-pull
# check, which is exactly how this was first caught (see macro_sim.py's decay_stress_test
# diverging from the pre-refactor baseline for precisely these five classes, nothing else).
MAX_HP_SEED_IS_STARTING_HP = {
    "warrior": True, "wizard": True, "rogue": True, "ranger": True,
    "cleric": False, "paladin": False, "runecaster": False, "druid": False, "necromancer": False,
}
ROUNDS = 3


def initial_max_hp(class_name: str, starting_hp: float) -> float:
    if MAX_HP_SEED_IS_STARTING_HP[class_name]:
        return starting_hp
    return float(getattr(CARD_SOURCE[class_name], HP_ATTR[class_name]))


@dataclass
class PullState:
    class_name: str
    hero_hp: float
    hero_max_hp: float
    mob_name: str
    mob_pattern: list
    mob_hp_total: float
    mob_hp_remaining: float
    round_num: int = 0
    hand: tuple = ()
    played: list = field(default_factory=list)
    outcome: Optional[str] = None  # None / "win" / "loss" / "fled"
    round_state: RoundState = field(default_factory=RoundState)
    stance: Optional[str] = None  # Warrior only -- chosen at round 0, locked for the pull


def new_pull(class_name: str, mob_name: str, seed: int = None) -> PullState:
    rng = random.Random(seed)
    mod = CARD_SOURCE[class_name]
    hand = tuple(rng.sample(mod.DECK, 4))
    pattern, mob_hp = T.MOBS[mob_name][class_name]
    hero_hp = float(getattr(mod, HP_ATTR[class_name]))
    return PullState(
        class_name=class_name, hero_hp=hero_hp, hero_max_hp=initial_max_hp(class_name, hero_hp),
        mob_name=mob_name, mob_pattern=pattern, mob_hp_total=float(mob_hp),
        mob_hp_remaining=float(mob_hp), hand=hand,
    )


def _remaining_hand(state: PullState) -> list:
    return [c for c in state.hand if c not in state.played]


def _legal_stances(state: PullState) -> list:
    """Mirrors condensed_warrior.stance_sequences(): stance is chosen once before round 1
    and locked for the whole pull -- no flip, ever. Every other class has no stance at all,
    so this returns [None] uniformly for them (resolve_round's stance param is simply unused
    on those classes, same as it already is inside simulate())."""
    if state.class_name != "warrior":
        return [None]
    if state.round_num == 0:
        return ["G", "C"]
    return [state.stance]


def _card_variants(state: PullState, hand_card_name: str) -> list:
    """Almost always just [hand_card_name] -- the one real exception is Necromancer's
    Boneguard's Offering, which the solver already treats as two selectable lines (base vs.
    the boosted HP-for-damage virtual card, see condensed_necromancer.py's orderings()). Both
    variants come from the SAME hand card (the boosted one is never itself drawable), so this
    is the one place that duality needs exposing as two distinct legal actions."""
    if state.class_name == "necromancer" and hand_card_name == N.BONEGUARD_OFFERING:
        return [N.BONEGUARD_OFFERING, N.BONEGUARD_OFFERING_BOOSTED]
    return [hand_card_name]


def get_legal_actions(state: PullState) -> list:
    """List of {card, variant, stance, legal, ...preview fields} dicts -- illegal entries are
    included (legal=False, no preview numbers) so a caller can see *why* an option is
    unavailable, not just that it's missing (mirrors playtest_engine.py's old convention).
    `card` is the real hand card (what actually leaves the hand); `variant` is the exact
    card_name passed to resolve_round (differs from `card` only for Necromancer's boosted
    Boneguard's Offering)."""
    if state.outcome is not None:
        return []
    mod = CARD_SOURCE[state.class_name]
    actions = []
    for hand_card in _remaining_hand(state):
        for variant in _card_variants(state, hand_card):
            for stance in _legal_stances(state):
                outcome = mod.resolve_round(
                    state.round_state, variant, stance, state.round_num,
                    state.mob_pattern, state.mob_hp_total, state.mob_hp_remaining,
                    state.hero_hp, state.hero_max_hp,
                )
                if outcome is None:
                    actions.append(dict(card=hand_card, variant=variant, stance=stance, legal=False))
                else:
                    actions.append(dict(
                        card=hand_card, variant=variant, stance=stance, legal=True,
                        dmg_dealt=outcome.dmg_dealt, dmg_taken=outcome.dmg_taken,
                        resulting_hp=outcome.new_hp, resulting_mob_hp=outcome.new_mob_hp_remaining,
                        raw_dmg=outcome.raw_dmg, block=outcome.block, heal=outcome.heal,
                    ))
    return actions


def apply_action(state: PullState, action: dict) -> PullState:
    if state.outcome is not None:
        raise ValueError("pull already resolved")
    if action["card"] not in _remaining_hand(state):
        raise ValueError(f"{action['card']!r} not available to play")
    if not action.get("legal", False):
        raise ValueError(f"{action['card']!r} (variant={action.get('variant')}) illegal this round")

    mod = CARD_SOURCE[state.class_name]
    outcome = mod.resolve_round(
        state.round_state, action["variant"], action["stance"], state.round_num,
        state.mob_pattern, state.mob_hp_total, state.mob_hp_remaining,
        state.hero_hp, state.hero_max_hp,
    )
    if outcome is None:
        raise ValueError(f"{action['card']!r} illegal this round")

    # Hero death is checked BEFORE mob death, matching every class's own simulate() loop
    # exactly (`if hp <= 0: return False...` always precedes `if remaining <= 0: return
    # True...`) -- when a round's damage kills both simultaneously, the hero's own death
    # wins the tie, not the mob's. Reversing this order is a real, silent behavior change
    # (see verify_combat_engine.py's reduced-starting-hp sweep, which is what caught it).
    new_round = state.round_num + 1
    if outcome.new_hp <= 0:
        result = "loss"
    elif outcome.new_mob_hp_remaining <= 0:
        result = "win"
    elif new_round >= ROUNDS:
        result = "fled"
    else:
        result = None

    return replace(
        state,
        hero_hp=outcome.new_hp, hero_max_hp=outcome.new_hero_max_hp,
        mob_hp_remaining=outcome.new_mob_hp_remaining, round_num=new_round,
        played=state.played + [action["card"]], outcome=result,
        round_state=outcome.new_state,
        stance=action["stance"] if state.class_name == "warrior" else state.stance,
    )


def best_line_reveal(state: PullState) -> dict:
    """Thin wrapper around each class's own best_line_for_hand -- reused verbatim, not
    reimplemented, so this can never drift from the balance tooling's notion of 'optimal'."""
    mod = CARD_SOURCE[state.class_name]
    if state.class_name == "warrior":
        seq_cards, stance_seq, hp_left, rounds = mod.best_line_for_hand(
            state.hand, state.mob_pattern, state.mob_hp_total, starting_hp=state.hero_hp)
        win, final_hp, final_rounds = mod.simulate(
            seq_cards, stance_seq, state.mob_pattern, state.mob_hp_total, starting_hp=state.hero_hp)
        return dict(sequence=seq_cards, stance_sequence=stance_seq, hp_left=final_hp, win=win)
    else:
        seq_cards, hp_left, rounds = mod.best_line_for_hand(
            state.hand, state.mob_pattern, state.mob_hp_total, starting_hp=state.hero_hp)
        win, final_hp, final_rounds = mod.simulate(
            seq_cards, state.mob_pattern, state.mob_hp_total, starting_hp=state.hero_hp)
        return dict(sequence=seq_cards, stance_sequence=None, hp_left=final_hp, win=win)


class QuestIntelligence:
    """AI persona for both combat and macro decisions -- mirrors AGGRO's AggroIntelligence
    shape (one persona object, one method per decision layer; decide_macro lands here too once
    Part 3/3b's macro_engine.py exists). decide_combat is a thin cache-and-replay wrapper
    around each class's own best_line_for_hand, NEVER a reimplemented search -- per
    unified-sprouting-aurora.md's Part 2, a second lookahead search here would risk silently
    tie-breaking differently from the balance-tested solver, reopening the exact drift risk
    this whole combat-engine refactor closes. Calls the real solver once per pull (cached on
    first call, keyed on (class_name, hand, mob_name)), then just replays the cached sequence
    card-by-card -- byte-identical to the old batch-solved behavior by construction."""

    def __init__(self):
        self._cache_key = None
        self._cached_seq = None
        self._cached_stance_seq = None

    def decide_combat(self, state: PullState, actions: list) -> dict:
        mod = CARD_SOURCE[state.class_name]
        key = (state.class_name, state.hand, state.mob_name)
        if key != self._cache_key:
            if state.class_name == "warrior":
                seq_cards, stance_seq, hp_left, rounds = mod.best_line_for_hand(
                    state.hand, state.mob_pattern, state.mob_hp_total, starting_hp=state.hero_hp)
            else:
                seq_cards, hp_left, rounds = mod.best_line_for_hand(
                    state.hand, state.mob_pattern, state.mob_hp_total, starting_hp=state.hero_hp)
                stance_seq = None
            self._cached_seq, self._cached_stance_seq, self._cache_key = seq_cards, stance_seq, key

        variant = self._cached_seq[state.round_num]
        stance = self._cached_stance_seq[state.round_num] if self._cached_stance_seq else None
        for action in actions:
            if action["variant"] == variant and action.get("stance") == stance and action["legal"]:
                return action
        raise RuntimeError(f"cached best-line variant {variant!r} not found in legal actions")


def new_pull_with_hp(class_name: str, mob_name: str, hand, pattern, mob_hp: float,
                      starting_hp: float) -> PullState:
    """Like new_pull(), but for a hero who already has a specific hand/mob/HP in hand instead
    of drawing fresh -- the shape macro_sim.py's two real pull sites need (HP carries over
    between pulls, mob is already chosen by node/quest routing). Threads starting_hp through
    initial_max_hp() so classes with a fixed healing ceiling (Cleric/Paladin/Runecaster/Druid/
    Necromancer) don't get their heal cap silently clamped to a reduced entering HP -- see
    initial_max_hp()'s own docstring for why this specific seeding bit matters."""
    return PullState(
        class_name=class_name, hero_hp=starting_hp, hero_max_hp=initial_max_hp(class_name, starting_hp),
        mob_name=mob_name, mob_pattern=pattern, mob_hp_total=float(mob_hp),
        mob_hp_remaining=float(mob_hp), hand=tuple(hand),
    )
