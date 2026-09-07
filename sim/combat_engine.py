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
import macro_sim as M
import itertools
from equipment_mechanics import apply_equipment_mechanics
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
    equipment: dict = field(default_factory=dict)
    equipment_used: set = field(default_factory=set)


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
    if state.class_name == "necromancer":
        mod = CARD_SOURCE["necromancer"]
        if mod.CARDS.get(hand_card_name, {}).get("blood_magic"):
            return [hand_card_name, f"{hand_card_name} (Boosted)"]

    return [hand_card_name]


def get_legal_actions(state: PullState) -> list:
    """List of {card, variant, stance, legal, equipment, ...preview fields} dicts"""
    if state.outcome is not None:
        return []
    mod = CARD_SOURCE[state.class_name]
    actions = []
    
    # We always need to apply lingering equipment mechanics (e.g. HoT, Persistent)
    # Even if NO equipment is activated this round, `apply_equipment_mechanics` handles that if equip_round=None.
    
    available_equipment = []
    if getattr(state, "equipment", None):
        for slot, name in state.equipment.items():
            if name and slot not in state.equipment_used:
                recipe = next((r for r in M.EQUIPMENT_RECIPES if r["name"] == name), None)
                if recipe:
                    available_equipment.append((slot, recipe["rider"]))
                    
    # Generate all subsets of available equipment
    eq_combos = []
    for r in range(len(available_equipment) + 1):
        for combo in itertools.combinations(available_equipment, r):
            eq_combos.append(combo)

    for hand_card in _remaining_hand(state):
        for variant in _card_variants(state, hand_card):
            for stance in _legal_stances(state):
                base_outcome = mod.resolve_round(
                    state.round_state, variant, stance, state.round_num,
                    state.mob_pattern, state.mob_hp_total, state.mob_hp_remaining,
                    state.hero_hp, state.hero_max_hp,
                )
                if base_outcome is None:
                    actions.append(dict(card=hand_card, variant=variant, stance=stance, equipment=(), legal=False))
                    continue
                    
                for combo in eq_combos:
                    outcome = base_outcome
                    for slot, rider in combo:
                        outcome = apply_equipment_mechanics(outcome, rider, state.round_num, state.round_num, state.mob_pattern)
                    
                    # Also apply any lingering effects by calling it with equip_round=None
                    # wait! if combo is empty, we still need to apply lingering effects!
                    if not combo:
                        outcome = apply_equipment_mechanics(outcome, "none", state.round_num, None, state.mob_pattern)
                        
                    actions.append(dict(
                        card=hand_card, variant=variant, stance=stance, equipment=tuple(s for s, _ in combo), legal=True,
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
    base_outcome = mod.resolve_round(
        state.round_state, action["variant"], action["stance"], state.round_num,
        state.mob_pattern, state.mob_hp_total, state.mob_hp_remaining,
        state.hero_hp, state.hero_max_hp,
    )
    if base_outcome is None:
        raise ValueError(f"{action['card']!r} illegal this round")
        
    outcome = base_outcome
    combo = action.get("equipment", ())
    if getattr(state, "equipment", None):
        for slot in combo:
            name = state.equipment[slot]
            recipe = next((r for r in M.EQUIPMENT_RECIPES if r["name"] == name), None)
            if recipe:
                outcome = apply_equipment_mechanics(outcome, recipe["rider"], state.round_num, state.round_num, state.mob_pattern)
                
    if not combo:
        outcome = apply_equipment_mechanics(outcome, "none", state.round_num, None, state.mob_pattern)

    new_round = state.round_num + 1
    if outcome.new_hp <= 0:
        result = "loss"
    elif outcome.new_mob_hp_remaining <= 0:
        result = "win"
    elif new_round >= 3:
        result = "fled"
    else:
        result = None
        
    new_equipment_used = set(state.equipment_used) if getattr(state, "equipment_used", None) else set()
    for slot in combo:
        new_equipment_used.add(slot)

    return replace(
        state,
        hero_hp=outcome.new_hp, hero_max_hp=outcome.new_hero_max_hp,
        mob_hp_remaining=outcome.new_mob_hp_remaining, round_num=new_round,
        played=state.played + [action["card"]], outcome=result,
        round_state=outcome.new_state,
        stance=action["stance"] if state.class_name == "warrior" else state.stance,
        equipment_used=new_equipment_used
    )


def best_line_reveal(state: PullState) -> dict:
    """Uses the same exhaustive search to show the UI the optimal line, including equipment!"""
    iq = QuestIntelligence()
    iq.decide_combat(state, []) # This primes the cache
    
    seq_cards = []
    stance_seq = []
    eq_seq = []
    for a in iq._cached_actions:
        seq_cards.append(a["card"])
        stance_seq.append(a.get("stance"))
        eq_seq.append(a.get("equipment", ()))
        
    s = state
    for a in iq._cached_actions:
        s = apply_action(s, a)
        
    return dict(
        sequence=seq_cards, 
        stance_sequence=stance_seq if any(stance_seq) else None, 
        equipment_sequence=eq_seq,
        hp_left=s.hero_hp, 
        win=(s.outcome == "win")
    )


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
        if not hasattr(self, "_cached_actions"):
            # Full recursive solver using the actual get_legal_actions/apply_action
            # This correctly branches over all equipment choices!
            def search(s):
                if s.outcome == "win": return (True, s.hero_hp, s.round_num, [])
                if s.outcome in ("loss", "fled"): return (False, s.hero_hp, s.round_num, [])
                
                best_res = (False, float('-inf'), 3, [])
                best_action = None
                
                for a in get_legal_actions(s):
                    if not a["legal"]: continue
                    ns = apply_action(s, a)
                    res = search(ns)
                    # We want to maximize (win, hp_left, -rounds)
                    key = (res[0], res[1], -res[2])
                    bkey = (best_res[0], best_res[1], -best_res[2])
                    if best_action is None or key > bkey:
                        best_res = res
                        best_action = a
                        
                return (best_res[0], best_res[1], best_res[2], [best_action] + best_res[3])
            
            res = search(state)
            self._cached_actions = res[3]
            
        action = self._cached_actions[state.round_num]
        return action


def new_pull_with_hp(class_name: str, mob_name: str, hand, pattern, mob_hp: float,
                     starting_hp: float, equipment=None, equipment_used=None) -> PullState:
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
        equipment=equipment or {}, equipment_used=equipment_used or set(),
    )
