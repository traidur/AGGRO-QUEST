"""
Exact solver for the condensed Cleric prototype (v2 -- identity-first redesign).
Deck=6, hand=4, 3 rounds max -- same skeleton as condensed_warrior.py / condensed_wizard.py.
No stance, no positioning, no arm/consume combo system. Sacred Balance restored to its
real AGGRO shape: playing Smite or Call of the Void (the class's real "Cast damage
spells") automatically heals a small flat amount -- no setup, no wasted charges, no
cross-round dependency at all. Void Mark deliberately does NOT trigger it, matching its
source identity as the one card that doesn't. Cleansing Barrier and Fiery Fortitude carry
a small flat, unconditional damage rider (fixes the damage floor independently of Sacred
Balance) but do not interact with Sacred Balance either -- they're support cards with
incidental damage, not attack spells.

Every card's effect is fully self-contained: order only matters relative to the mob's
known pattern, never relative to another card in hand. Deliberately different in kind
from Warrior (Stance/Sunder) and Wizard (Positioning/Spellweave), both of which have real
card-to-card dependencies independent of the mob.
"""
import itertools
from dataclasses import replace

from combat_round import RoundState, RoundOutcome

CLERIC_HP = 14
SACRED_BALANCE_HEAL = 1  # automatic heal on playing Smite

# dmg/heal/block are flat, unconditional. sacred_balance=True means playing this card
# also heals SACRED_BALANCE_HEAL automatically, no state, no setup required.
# max_hp_buff: pull-scoped only (deliberate -- deck and pull-local effects
# fully reset every pull per the condensed-combat rules; only raw HP itself
# carries across pulls in a trip). Raises the HP ceiling for the rest of
# THIS pull ONLY -- does NOT grant any instant current-HP on its own, only
# lets subsequent healing (this card's own heal included) actually land
# instead of being wasted to the old cap. Tested and confirmed: an earlier
# version that also added the buff directly to current HP (standard
# "Fortitude" semantics in most games) reopened Cleric's previously-fixed
# "cannot die" equilibrium bug on Grunt/Skirmisher -- traced to the extra
# instant HP, not the raised ceiling itself (a controlled ceiling-only
# variant stays clean at every starting-HP level). Ceiling-only it is.
# aggro: co-op Party Pull targeting value (0-4), locked via direct user
# review -- see OPEN_QUESTIONS.md's "Co-op multi-hero vs. one Elite" entry.
CARDS = {
    "Void Mark": dict(combat_type="ranged",dmg=3, heal=0, block=0, sacred_balance=False, max_hp_buff=0, echo_dmg=0, aggro=1),
    "Smite": dict(combat_type="ranged",dmg=5, heal=0, block=0, sacred_balance=True,  max_hp_buff=0, echo_dmg=0, aggro=2),
    "Call of the Void": dict(combat_type="ranged",dmg=6, heal=0, block=0, sacred_balance=False, max_hp_buff=0, echo_dmg=0, aggro=3),
    "Cleansing Barrier": dict(combat_type="melee",dmg=3, heal=0, block=5, sacred_balance=False, max_hp_buff=0, echo_dmg=0, aggro=1),
    "Fiery Fortitude": dict(combat_type="melee",dmg=3, heal=2, block=0, sacred_balance=False, max_hp_buff=2, echo_dmg=0, aggro=2),
    "Heal": dict(combat_type="ranged",dmg=0, heal=3, block=0, sacred_balance=False, max_hp_buff=0, echo_dmg=0, aggro=3),
}
DECK = list(CARDS.keys())

ALL_HANDS = list(itertools.combinations(DECK, 4))


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def resolve_round(state, card_name, stance, round_num, mob_pattern, mob_hp_total,
                   mob_hp_remaining, hero_hp, hero_max_hp):
    """The one place Cleric's card-effect logic lives. Faithful port of the real, current
    simulate() below (NOT playtest_engine.py's older _resolve_cleric_round, which predates the
    echo_dmg/pending_echo_dmg DOT-carryover field added to CARDS since -- verified by direct
    comparison before porting). stance is unused (Cleric has none). hero_max_hp here is the
    per-pull HP ceiling (starts at CLERIC_HP, not necessarily starting_hp -- see simulate()'s
    own seeding below), raised by max_hp_buff cards; state.pending_echo_dmg carries the DOT
    tick from the previous round's card, resolved before this round's own card, shared field
    shape with Runecaster/Necromancer's own echo mechanics."""
    card = CARDS[card_name]
    mob_atk, mob_block = mob_pattern[round_num]

    new_remaining = mob_hp_remaining
    if state.pending_echo_dmg:
        new_remaining -= max(0.0, state.pending_echo_dmg - mob_block)

    dmg, heal, block = card["dmg"], card["heal"], card["block"]
    if card["sacred_balance"]:
        heal += SACRED_BALANCE_HEAL

    new_max_hp = hero_max_hp + card["max_hp_buff"]
    healed_hp = min(new_max_hp, hero_hp + heal)

    dmg_dealt = max(0.0, dmg - mob_block)
    new_remaining -= dmg_dealt

    dmg_taken = max(0.0, mob_atk - block)
    new_hp = healed_hp - dmg_taken

    new_state = replace(state, pending_echo_dmg=card["echo_dmg"])
    return RoundOutcome(new_hp=new_hp, new_mob_hp_remaining=new_remaining, new_hero_max_hp=new_max_hp,
                         new_state=new_state, dmg_dealt=dmg_dealt, dmg_taken=dmg_taken,
                         raw_dmg=dmg, block=block, heal=heal)


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=CLERIC_HP):
    state = RoundState()
    hp, remaining, max_hp = starting_hp, mob_hp, CLERIC_HP  # hp_cap starts at the class's
    # base HP constant, NOT starting_hp -- matches the original loop's `hp_cap = CLERIC_HP`
    # seeding exactly (a hero starting a pull at reduced HP still has the full class ceiling).
    for rnd in range(3):
        outcome = resolve_round(state, seq_cards[rnd], None, rnd, mob_pattern, mob_hp,
                                 remaining, hp, max_hp)
        hp, remaining, max_hp, state = (outcome.new_hp, outcome.new_mob_hp_remaining,
                                         outcome.new_hero_max_hp, outcome.new_state)
        if hp <= 0:
            return False, hp, rnd + 1
        if remaining <= 0:
            return True, hp, rnd + 1
    return False, hp, 3


def best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=CLERIC_HP):
    best = None
    for seq_cards in orderings(hand):
        win, hp_left, rounds = simulate(seq_cards, mob_pattern, mob_hp, starting_hp)
        key = (win, hp_left)
        if best is None or key > best[0]:
            best = (key, (seq_cards, hp_left, rounds))
    return best[1]


def win_rate(mob_pattern, mob_hp, verbose=False, starting_hp=None):
    # See condensed_warrior.win_rate for why this isn't a default *parameter*
    # value -- that would freeze at import time and ignore `C.CLERIC_HP = X`.
    if starting_hp is None:
        starting_hp = CLERIC_HP
    wins = 0
    for hand in ALL_HANDS:
        seq_cards, hp_left, rounds = best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=starting_hp)
        win, _, _ = simulate(seq_cards, mob_pattern, mob_hp, starting_hp=starting_hp)
        if win:
            wins += 1
        elif verbose:
            print(f"  LOSS hand={hand} best_seq={seq_cards}")
    return wins / len(ALL_HANDS)
