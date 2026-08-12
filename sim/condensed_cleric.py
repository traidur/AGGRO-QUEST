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
    "Void Mark":         dict(dmg=3, heal=0, block=0, sacred_balance=False, max_hp_buff=0, aggro=1),
    "Smite":             dict(dmg=5, heal=0, block=0, sacred_balance=True,  max_hp_buff=0, aggro=2),
    "Call of the Void":  dict(dmg=6, heal=0, block=0, sacred_balance=False, max_hp_buff=0, aggro=3),
    "Cleansing Barrier": dict(dmg=3, heal=0, block=5, sacred_balance=False, max_hp_buff=0, aggro=1),
    "Fiery Fortitude":   dict(dmg=3, heal=2, block=0, sacred_balance=False, max_hp_buff=2, aggro=2),
    "Heal":              dict(dmg=0, heal=3, block=0, sacred_balance=False, max_hp_buff=0, aggro=3),
}
DECK = list(CARDS.keys())

ALL_HANDS = list(itertools.combinations(DECK, 4))


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=CLERIC_HP):
    hp = starting_hp
    hp_cap = CLERIC_HP
    remaining_mob_hp = mob_hp

    for rnd in range(3):
        card = CARDS[seq_cards[rnd]]
        dmg, heal, block = card["dmg"], card["heal"], card["block"]
        if card["sacred_balance"]:
            heal += SACRED_BALANCE_HEAL

        hp_cap += card["max_hp_buff"]  # raises the ceiling only -- does not add its own separate HP on top of heal
        hp = min(hp_cap, hp + heal)  # heal resolves first, now capped at the (possibly raised) max HP

        mob_atk, mob_block = mob_pattern[rnd]
        dmg_dealt = max(0.0, dmg - mob_block)
        remaining_mob_hp -= dmg_dealt

        dmg_taken = max(0.0, mob_atk - block)
        hp -= dmg_taken

        if hp <= 0:
            return False, hp, rnd + 1
        if remaining_mob_hp <= 0:
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
