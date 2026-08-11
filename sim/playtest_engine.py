"""
Interactive step-by-step engine for condensed combat, built for human play
(CLI and web front ends both call this, never each other).

condensed_warrior.py / condensed_wizard.py / condensed_cleric.py /
condensed_trip.py stay untouched and remain the single source of truth for
card numbers (CARDS, DECK, *_HP) and mob data (MOBS). This module imports
those directly so numbers can never drift, but reimplements the per-round
resolution as a fresh step-at-a-time function per class instead of reusing
the solvers' batch-enumeration internals (_sim_from / simulate loops) --
those are the balance-tested exhaustive search this whole project relies on,
and are deliberately left alone. See unified-sprouting-aurora.md for the
tradeoff this implies: a future *mechanic* change (not just a number tweak)
needs to be ported here too. best_line_for_hand() is reused directly (not
reimplemented) for the "reveal optimal line" feature, so that part can never
drift.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Optional

import condensed_cleric as C
import condensed_paladin as P
import condensed_trip as T
import condensed_warrior as W
import condensed_wizard as Z

CARD_SOURCE = {"warrior": W, "wizard": Z, "cleric": C, "paladin": P}
HP_ATTR = {"warrior": "WARRIOR_HP", "wizard": "WIZARD_HP", "cleric": "CLERIC_HP", "paladin": "PALADIN_HP"}
ROUNDS = 3


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

    # Warrior-only
    stance: Optional[str] = None
    sunder_stacks: int = 0
    prev_card_name: Optional[str] = None

    # Wizard-only
    weave_armed: bool = False

    # Paladin-only
    strikes_played: int = 0
    invocation_played: bool = False
    active_invocation: Optional[str] = None  # "sanctuary" / "grace" / None -- only ever set by the FIRST Invocation played this pull


def new_pull(class_name: str, mob_name: str, seed: int = None) -> PullState:
    rng = random.Random(seed)
    mod = CARD_SOURCE[class_name]
    hand = tuple(rng.sample(mod.DECK, 4))
    pattern, mob_hp = T.MOBS[mob_name][class_name]
    hero_hp = float(getattr(mod, HP_ATTR[class_name]))
    return PullState(
        class_name=class_name, hero_hp=hero_hp, hero_max_hp=hero_hp,
        mob_name=mob_name, mob_pattern=pattern, mob_hp_total=float(mob_hp),
        mob_hp_remaining=float(mob_hp), hand=hand,
    )


def _remaining_hand(state: PullState) -> list:
    return [c for c in state.hand if c not in state.played]


def _resolve_warrior_round(state: PullState, card_name: str, stance: str):
    card = W.CARDS[card_name]
    if card["execute_finisher"]:
        if state.mob_hp_remaining <= state.mob_hp_total * 0.5:
            dmg, block = 6, 0
        else:
            return None  # illegal: Execute requires mob <= 50% HP, either stance
    else:
        dmg, block = card[stance]

    if card["chain_stance"] == stance and state.prev_card_name == card["chain_requires"]:
        if card["chain_target"] == "block":
            block += card["chain_bonus"]
        else:
            dmg += card["chain_bonus"]

    eff_dmg = dmg + (W.SUNDER_BONUS * state.sunder_stacks if dmg > 0 else 0)
    new_sunder = state.sunder_stacks + (1 if card["sunder"] else 0)

    mob_atk, mob_block = state.mob_pattern[state.round_num]
    dmg_dealt = max(0.0, eff_dmg - mob_block)
    new_remaining = state.mob_hp_remaining - dmg_dealt

    if card_name == "Execute" and new_remaining <= 0:
        dmg_taken = 0.0
    else:
        dmg_taken = max(0.0, mob_atk - block)
    new_hp = state.hero_hp - dmg_taken

    return dict(dmg_dealt=dmg_dealt, dmg_taken=dmg_taken, new_hp=new_hp,
                new_remaining=new_remaining, new_sunder=new_sunder,
                raw_dmg=eff_dmg, block=block, heal=0)


def _resolve_wizard_round(state: PullState, card_name: str):
    card = Z.CARDS[card_name]
    use_boost = card["payoff"] and state.weave_armed
    dmg = card["dmg"][1] if use_boost else card["dmg"][0]
    block = card["block"]

    new_weave_armed = state.weave_armed
    if card["weave_source"]:
        new_weave_armed = True
    elif use_boost:
        new_weave_armed = False

    mob_atk, mob_block, mob_type = state.mob_pattern[state.round_num]
    dmg_dealt = max(0.0, dmg - mob_block)
    new_remaining = state.mob_hp_remaining - dmg_dealt

    if card["grants_range"] and mob_type == "melee":
        dmg_taken = 0.0
    else:
        dmg_taken = max(0.0, mob_atk - block)
    new_hp = state.hero_hp - dmg_taken

    return dict(dmg_dealt=dmg_dealt, dmg_taken=dmg_taken, new_hp=new_hp,
                new_remaining=new_remaining, new_weave_armed=new_weave_armed,
                used_boost=use_boost, raw_dmg=dmg, block=block, heal=0)


def _resolve_cleric_round(state: PullState, card_name: str):
    card = C.CARDS[card_name]
    dmg, heal, block = card["dmg"], card["heal"], card["block"]
    if card["sacred_balance"]:
        heal += C.SACRED_BALANCE_HEAL

    # Fiery Fortitude's max_hp_buff is pull-scoped: raises the cap for the
    # rest of THIS pull only, so the card's own heal (already a separate
    # field) isn't wasted near the old cap. It does NOT add a second,
    # separate instant-HP grant on top of heal -- "+2 Max HP" and "2 heal"
    # describe one rider, not two stacking ones. An earlier version double-
    # counted this (added max_hp_buff to hp a second time alongside heal)
    # and reopened Cleric's "cannot die" equilibrium bug on Grunt/Skirmisher;
    # see condensed_cleric.py for the traced fix.
    new_max_hp = state.hero_max_hp + card["max_hp_buff"]
    healed_hp = min(new_max_hp, state.hero_hp + heal)
    mob_atk, mob_block = state.mob_pattern[state.round_num]
    dmg_dealt = max(0.0, dmg - mob_block)
    new_remaining = state.mob_hp_remaining - dmg_dealt
    dmg_taken = max(0.0, mob_atk - block)
    new_hp = healed_hp - dmg_taken

    return dict(dmg_dealt=dmg_dealt, dmg_taken=dmg_taken, new_hp=new_hp,
                new_remaining=new_remaining, new_max_hp=new_max_hp,
                raw_dmg=dmg, block=block, heal=heal)


def _resolve_paladin_round(state: PullState, card_name: str):
    """No precedent in the other three classes -- this is a genuinely new
    mechanic shape, not a variant of stance/chain/weave/sacred-balance.
    Ported directly from condensed_paladin.simulate(), same care taken as
    every other resolver: the two Invocation cards are mutually exclusive
    with STRIKE cards (a card is never both), so checking state.active_
    invocation for the STRIKE bonus and card['invocation'] for the
    Invocation-card branch never collide within the same round."""
    card = P.CARDS[card_name]
    dmg, heal, block = card["dmg"], card["heal"], card["block"]

    new_strikes_played = state.strikes_played
    new_invocation_played = state.invocation_played
    new_active_invocation = state.active_invocation

    if card["invocation"] is not None:
        if not state.invocation_played:
            # First Invocation played this pull: retroactive bonus for
            # STRIKE cards already played, and becomes Active for the rest
            # of the pull (drives the forward-looking bonus below).
            new_invocation_played = True
            new_active_invocation = card["invocation"]
            if new_active_invocation == "sanctuary":
                dmg += state.strikes_played
            else:
                heal += state.strikes_played
        # else: second Invocation played this pull -- flat base dmg only,
        # no retroactive bonus, does not become (or change) Active.

    if card["strike"]:
        new_strikes_played = state.strikes_played + 1
        if state.active_invocation == "sanctuary":
            dmg += 1  # forward-looking bonus from an already-active Invocation of Sanctuary
        elif state.active_invocation == "grace":
            heal += 1  # forward-looking bonus from an already-active Invocation of Grace

    healed_hp = min(state.hero_max_hp, state.hero_hp + heal)
    mob_atk, mob_block = state.mob_pattern[state.round_num]
    dmg_dealt = max(0.0, dmg - mob_block)
    new_remaining = state.mob_hp_remaining - dmg_dealt
    dmg_taken = max(0.0, mob_atk - block)
    new_hp = healed_hp - dmg_taken

    return dict(dmg_dealt=dmg_dealt, dmg_taken=dmg_taken, new_hp=new_hp,
                new_remaining=new_remaining, raw_dmg=dmg, block=block, heal=heal,
                new_strikes_played=new_strikes_played, new_invocation_played=new_invocation_played,
                new_active_invocation=new_active_invocation)


def _legal_stances(state: PullState) -> list:
    """Mirrors condensed_warrior.stance_sequences(): stance is chosen once
    before round 1 and locked for the whole pull -- no flip, ever."""
    if state.round_num == 0:
        return ["G", "C"]
    return [state.stance]


def _card_tags(state: PullState, card_name: str, stance: str = None) -> list:
    """Short, human-readable labels for a card's mechanic role -- built
    straight from fields already in each class's CARDS dict, not new data.
    Tags that depend on current state (has the setup card already been
    played, is Spellweave currently armed) get a live '-- ACTIVE this round'
    suffix instead of just describing the card in the abstract, so the UI
    can show whether the payoff is actually live right now, not just that
    the card has one in general."""
    tags = []
    if state.class_name == "warrior":
        card = W.CARDS[card_name]
        if card["sunder"]:
            tags.append(f"Applies Sunder (+{W.SUNDER_BONUS} dmg after)")
        if card["execute_finisher"]:
            tags.append("Finisher -- mob must be ≤ 50% HP")
        if card["chain_requires"]:
            active = (state.prev_card_name == card["chain_requires"] and stance == card["chain_stance"])
            suffix = " -- ACTIVE this round" if active else ""
            tags.append(f"Combo payoff if played after {card['chain_requires']}{suffix}")
    elif state.class_name == "wizard":
        card = Z.CARDS[card_name]
        if card["weave_source"]:
            tags.append("Arms Spellweave")
        if card["payoff"]:
            suffix = " -- ACTIVE this round" if state.weave_armed else " (not armed)"
            tags.append(f"Spellweave payoff{suffix}")
        if card["grants_range"]:
            tags.append("Grants Range (evades melee)")
    elif state.class_name == "cleric":
        card = C.CARDS[card_name]
        if card["sacred_balance"]:
            tags.append(f"Sacred Balance: +{C.SACRED_BALANCE_HEAL} heal on play")
        if card["max_hp_buff"]:
            tags.append(f"+{card['max_hp_buff']} Max HP (this pull only)")
    else:  # paladin
        card = P.CARDS[card_name]
        if card["strike"]:
            tags.append("STRIKE")
            if state.active_invocation == "sanctuary":
                tags.append("+1 dmg -- Invocation of Sanctuary active")
            elif state.active_invocation == "grace":
                tags.append("+1 heal -- Invocation of Grace active")
        if card["invocation"] is not None:
            bonus_word = "dmg" if card["invocation"] == "sanctuary" else "heal"
            if not state.invocation_played:
                tags.append(f"First Invocation this pull: +{state.strikes_played} {bonus_word} now "
                             f"(from STRIKEs already played), +1 {bonus_word} per STRIKE played after")
            else:
                tags.append("Second Invocation this pull: flat dmg only, no bonus, does not become active")
    return tags


def legal_actions(state: PullState) -> list:
    """List of {card, stance, dmg_dealt, dmg_taken, resulting_hp,
    resulting_mob_hp, raw_dmg, block, heal, legal, tags} previews -- illegal
    entries are included (with legal=False, no preview numbers) so the
    player can see *why* an option is greyed out, not just that it's
    missing.

    raw_dmg/block/heal are the card's own output before the opponent's side
    of the math is applied (raw_dmg is pre-mob-block, block/heal are the
    card's stated values before the mob's attack or the hero's max-HP cap
    reduce their visible effect this round) -- shown *alongside*
    dmg_dealt/dmg_taken/resulting_hp so a card's intrinsic strength is
    never hidden behind one specific round's numbers. A high-block card
    against a weak attack and a low-block card against a weak attack can
    both show "take 0" in the contextual numbers; raw_dmg/block/heal is
    what tells them apart."""
    if state.outcome is not None:
        return []

    actions = []
    for card_name in _remaining_hand(state):
        if state.class_name == "warrior":
            for stance in _legal_stances(state):
                result = _resolve_warrior_round(state, card_name, stance)
                tags = _card_tags(state, card_name, stance)
                if result is None:
                    actions.append(dict(card=card_name, stance=stance, legal=False, tags=tags))
                else:
                    actions.append(dict(
                        card=card_name, stance=stance, legal=True, tags=tags,
                        dmg_dealt=result["dmg_dealt"], dmg_taken=result["dmg_taken"],
                        resulting_hp=result["new_hp"], resulting_mob_hp=result["new_remaining"],
                        raw_dmg=result["raw_dmg"], block=result["block"], heal=result["heal"],
                    ))
        else:
            resolver = {"wizard": _resolve_wizard_round, "cleric": _resolve_cleric_round,
                        "paladin": _resolve_paladin_round}[state.class_name]
            result = resolver(state, card_name)
            actions.append(dict(
                card=card_name, stance=None, legal=True, tags=_card_tags(state, card_name),
                dmg_dealt=result["dmg_dealt"], dmg_taken=result["dmg_taken"],
                resulting_hp=result["new_hp"], resulting_mob_hp=result["new_remaining"],
                raw_dmg=result["raw_dmg"], block=result["block"], heal=result["heal"],
            ))
    return actions


def apply_action(state: PullState, card_name: str, stance: str = None) -> PullState:
    if state.outcome is not None:
        raise ValueError("pull already resolved")
    if card_name not in _remaining_hand(state):
        raise ValueError(f"{card_name!r} not available to play")

    extra = {}
    if state.class_name == "warrior":
        if stance not in _legal_stances(state):
            raise ValueError(f"stance {stance!r} not legal this round")
        result = _resolve_warrior_round(state, card_name, stance)
        if result is None:
            raise ValueError(f"{card_name!r} illegal in stance {stance!r} this round")
        extra["sunder_stacks"] = result["new_sunder"]
        extra["prev_card_name"] = card_name
        extra["stance"] = stance
    elif state.class_name == "wizard":
        result = _resolve_wizard_round(state, card_name)
        extra["weave_armed"] = result["new_weave_armed"]
    elif state.class_name == "cleric":
        result = _resolve_cleric_round(state, card_name)
        extra["hero_max_hp"] = result["new_max_hp"]
    else:  # paladin
        result = _resolve_paladin_round(state, card_name)
        extra["strikes_played"] = result["new_strikes_played"]
        extra["invocation_played"] = result["new_invocation_played"]
        extra["active_invocation"] = result["new_active_invocation"]

    new_hp = result["new_hp"]
    new_remaining = result["new_remaining"]
    new_round = state.round_num + 1

    if new_remaining <= 0:
        outcome = "win"
    elif new_hp <= 0:
        outcome = "loss"
    elif new_round >= ROUNDS:
        outcome = "fled"
    else:
        outcome = None

    return replace(
        state,
        hero_hp=new_hp, mob_hp_remaining=new_remaining, round_num=new_round,
        played=state.played + [card_name], outcome=outcome, **extra,
    )


def best_line_reveal(state: PullState) -> dict:
    """Thin wrapper around each solver's own best_line_for_hand -- reused
    verbatim, not reimplemented, so this can never drift from the balance
    tooling's notion of 'optimal'."""
    mod = CARD_SOURCE[state.class_name]
    if state.class_name == "warrior":
        seq_cards, stance_seq, hp_left, rounds = mod.best_line_for_hand(
            state.hand, state.mob_pattern, state.mob_hp_total, starting_hp=state.hero_max_hp)
        win, final_hp, final_rounds = mod.simulate(
            seq_cards, stance_seq, state.mob_pattern, state.mob_hp_total, starting_hp=state.hero_max_hp)
        return dict(sequence=seq_cards, stance_sequence=stance_seq, hp_left=final_hp, win=win)
    else:
        seq_cards, hp_left, rounds = mod.best_line_for_hand(
            state.hand, state.mob_pattern, state.mob_hp_total, starting_hp=state.hero_max_hp)
        win, final_hp, final_rounds = mod.simulate(
            seq_cards, state.mob_pattern, state.mob_hp_total, starting_hp=state.hero_max_hp)
        return dict(sequence=seq_cards, stance_sequence=None, hp_left=final_hp, win=win)
