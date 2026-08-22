"""
Shared per-round combat primitives -- the ONE place every condensed_<class>.py's
resolve_round() and simulate() (and, later, the turn-by-turn UI in combat_engine.py) agree
on state shape. Locked 2026-08-21, per the "player-facing decision architecture" plan
(unified-sprouting-aurora.md): promotes what used to be playtest_engine.py's own
per-class `_resolve_<class>_round` functions (a second, UI-side reimplementation of combat
logic, kept in sync with each class's real simulate() by hand) into the canonical
implementation, called by both the exhaustive-search solver and any future turn-by-turn caller.

Deliberately NOT a dependency on combat_engine.py (a UI-adjacent module) -- the class files
depend downward on this neutral shared primitive, never upward on anything UI-facing, matching
this project's existing layering discipline (macro_sim.py's own docstring: "Sits on top of
condensed_trip.py, doesn't modify it").

RoundState only carries per-class MECHANIC state that isn't already threaded as an ordinary
numeric loop variable by simulate() itself (hp, mob_hp_remaining, hero_max_hp are passed as
explicit resolve_round() parameters/RoundOutcome fields instead, the same way they were already
threaded through each class's old monolithic simulate() loop -- RoundState is only for things
like "which stance", "how many Sunder stacks", not raw HP numbers). A class that has no
persistent mechanic state at all (Cleric) simply never reads or writes any RoundState field.
"""
from dataclasses import dataclass, replace
from typing import Optional

__all__ = ["RoundState", "RoundOutcome"]


@dataclass
class RoundState:
    # Warrior-only
    stance: Optional[str] = None
    sunder_stacks: int = 0
    prev_card_name: Optional[str] = None

    # Wizard-only
    weave_armed: bool = False

    # Paladin-only
    strikes_played: int = 0
    invocation_played: bool = False
    active_invocation: Optional[str] = None  # "sanctuary" / "grace" / None
    active_grants_aura_block: bool = False  # set from the active Invocation's own
    # grants_aura_block field -- only ever True for a leveled-up card variant

    # Rogue-only
    strikes_played_rogue: int = 0  # separate field from Paladin's -- different card

    # Ranger-only
    beast_active: bool = False
    rounds_since_beast: Optional[int] = None
    prev_grants_range: bool = False

    # Runecaster-only
    rc_prev_card_name: Optional[str] = None
    pending_echo_dmg: float = 0.0
    pending_echo_heal: float = 0.0

    # Druid-only
    grizzly_played_before: bool = False
    shapeshift_played_before: int = 0
    eclipse_played_before: int = 0

    # Necromancer-only
    dot_played_before: int = 0
    nc_pending_echo_dmg: float = 0.0


@dataclass
class RoundOutcome:
    """Everything a round's resolution produces. new_state carries forward whichever
    per-class RoundState fields that class actually uses; new_hp/new_mob_hp_remaining/
    new_hero_max_hp are the ordinary numeric values simulate()'s own loop threads directly
    (mirroring how the pre-refactor monolithic simulate() loops already threaded them as
    plain local variables, not wrapped in a state object)."""
    new_hp: float
    new_mob_hp_remaining: float
    new_hero_max_hp: float
    new_state: RoundState
    dmg_dealt: float
    dmg_taken: float
    raw_dmg: float
    block: float
    heal: float
