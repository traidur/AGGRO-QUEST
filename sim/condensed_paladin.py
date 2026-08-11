"""
Exact solver for the condensed Paladin prototype -- first pass, v2 (folded
Invocation design).

Mechanic, locked through iteration with the user: two self-contained
"Invocation of X" cards replace the original three-card Virtue+shared-
Invocation structure from CONDENSED_COMBAT.md's original design note.
Each Invocation card is simultaneously a payoff for STRIKE cards already
played earlier in the pull AND a setup for STRIKE cards played after it:

  Invocation of Sanctuary: on play, deal 3 dmg + 1 dmg per STRIKE card
  already played earlier this pull. Every STRIKE card played afterward
  also generates +1 dmg when played.

  Invocation of Grace: on play, deal 3 dmg + heal 1 HP per STRIKE card
  already played earlier this pull. Every STRIKE card played afterward
  also heals +1 HP when played.

Exclusive: only one of the two Invocation cards may be played per pull,
ever (confirmed explicitly, same "one lane, chosen once" restriction
CONDENSED_COMBAT.md's original Virtue design already established).

Might of the Aegis and Bastion's Hammer are the two STRIKE-tagged cards
(matches AGGRO's real STRIKE tag -- verified against StS_WoW_Sim/data/
cards.csv). Sacred Light and Holy Fortress are plain support cards, not
STRIKE-tagged, so they don't feed the Invocation bonus chain either
direction. Holy Fortress is simplified from AGGRO's real charge/reactive-
damage sub-mechanic to a flat dmg+block card for this first pass.

No stance system -- has_stance=False, same category as Wizard/Cleric.
"""
import itertools

PALADIN_HP = 17  # locked: settled at Warrior-1 after the Sacred Light/HP dial-back pass

# dmg/heal/block are flat, unconditional base values. strike=True marks the
# two cards the Invocation bonus chain keys off. invocation={"sanctuary",
# "grace",None} marks the two Invocation cards.
CARDS = {
    "Might of the Aegis":     dict(dmg=4, heal=0, block=2, strike=True,  invocation=None),
    "Bastion's Hammer":       dict(dmg=6, heal=0, block=0, strike=True,  invocation=None),
    "Sacred Light":           dict(dmg=0, heal=3, block=0, strike=False, invocation=None),
    "Holy Fortress":          dict(dmg=2, heal=0, block=4, strike=False, invocation=None),
    "Invocation of Sanctuary": dict(dmg=3, heal=0, block=0, strike=False, invocation="sanctuary"),
    "Invocation of Grace":     dict(dmg=4, heal=0, block=0, strike=False, invocation="grace"),
}
DECK = list(CARDS.keys())

ALL_HANDS = list(itertools.combinations(DECK, 4))


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=PALADIN_HP):
    hp = starting_hp
    remaining_mob_hp = mob_hp
    strikes_played = 0  # count of STRIKE cards played so far this pull
    invocation_played = False  # True once EITHER Invocation card has been played
    active_invocation = None  # "sanctuary" / "grace" / None -- only ever set by the FIRST Invocation played; drives the forward-looking bonus on later STRIKE cards

    for rnd in range(3):
        card_name = seq_cards[rnd]
        card = CARDS[card_name]
        dmg, heal, block = card["dmg"], card["heal"], card["block"]

        if card["invocation"] is not None:
            if invocation_played:
                pass  # second Invocation played this pull: flat base dmg only, no retroactive bonus, does not become Active
            else:
                invocation_played = True
                active_invocation = card["invocation"]
                if active_invocation == "sanctuary":
                    dmg += strikes_played  # +1 dmg per STRIKE already played -- only for the first Invocation played
                else:
                    heal += strikes_played  # +1 heal per STRIKE already played -- only for the first Invocation played

        if card["strike"]:
            strikes_played += 1
            if active_invocation == "sanctuary":
                dmg += 1  # forward-looking bonus from an already-active Invocation of Sanctuary
            elif active_invocation == "grace":
                heal += 1  # forward-looking bonus from an already-active Invocation of Grace

        hp = min(PALADIN_HP, hp + heal)  # heal resolves first, capped at max HP

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


def best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=PALADIN_HP):
    best = None
    for seq_cards in orderings(hand):
        win, hp_left, rounds = simulate(seq_cards, mob_pattern, mob_hp, starting_hp)
        key = (win, hp_left)
        if best is None or key > best[0]:
            best = (key, (seq_cards, hp_left, rounds))
    return best[1]


def win_rate(mob_pattern, mob_hp, verbose=False, starting_hp=None):
    if starting_hp is None:
        starting_hp = PALADIN_HP
    wins = 0
    for hand in ALL_HANDS:
        seq_cards, hp_left, rounds = best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=starting_hp)
        win, _, _ = simulate(seq_cards, mob_pattern, mob_hp, starting_hp=starting_hp)
        if win:
            wins += 1
        elif verbose:
            print(f"  LOSS hand={hand} best_seq={seq_cards}")
    return wins / len(ALL_HANDS)
