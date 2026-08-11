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

CLERIC_HP = 12
SACRED_BALANCE_HEAL = 1  # automatic heal on playing Smite or Call of the Void

# dmg/heal/block are flat, unconditional. sacred_balance=True means playing this card
# also heals SACRED_BALANCE_HEAL automatically, no state, no setup required.
CARDS = {
    "Void Mark":         dict(dmg=3, heal=0, block=0, sacred_balance=False),
    "Smite":             dict(dmg=5, heal=0, block=0, sacred_balance=True),
    "Call of the Void":  dict(dmg=6, heal=0, block=0, sacred_balance=False),
    "Cleansing Barrier": dict(dmg=2, heal=0, block=4, sacred_balance=False),
    "Fiery Fortitude":   dict(dmg=2, heal=2, block=0, sacred_balance=False),
    "Heal":              dict(dmg=0, heal=4, block=0, sacred_balance=False),
}
DECK = list(CARDS.keys())

ALL_HANDS = list(itertools.combinations(DECK, 4))


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=CLERIC_HP):
    hp = starting_hp
    remaining_mob_hp = mob_hp

    for rnd in range(3):
        card = CARDS[seq_cards[rnd]]
        dmg, heal, block = card["dmg"], card["heal"], card["block"]
        if card["sacred_balance"]:
            heal += SACRED_BALANCE_HEAL

        hp = min(CLERIC_HP, hp + heal)  # heal resolves first, capped at max HP

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


def win_rate(mob_pattern, mob_hp, verbose=False):
    wins = 0
    for hand in ALL_HANDS:
        seq_cards, hp_left, rounds = best_line_for_hand(hand, mob_pattern, mob_hp)
        win, _, _ = simulate(seq_cards, mob_pattern, mob_hp)
        if win:
            wins += 1
        elif verbose:
            print(f"  LOSS hand={hand} best_seq={seq_cards}")
    return wins / len(ALL_HANDS)
