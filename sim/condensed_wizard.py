"""
Exact solver for the condensed Wizard prototype.
Deck=6, hand=4, 3 rounds max -- same skeleton as condensed_warrior.py.
No stance system (Wizard never had one in the source kit). Two mechanics
instead: Positioning (At Range this round, evades a melee mob's attack,
does nothing vs ranged) and Weave (a single-use trigger: playing a Weave
card arms a bonus that the *next* eligible payoff card consumes -- it does
not stack or apply to a second payoff card).
"""
import itertools

WIZARD_HP = 14

# dmg = (base, weave_boosted). block flat. weave_source arms the trigger.
# payoff = eligible to consume an armed trigger for the boosted dmg.
#
# Ice Barricade made a weave_source (was False). Found via a targeted dig
# into Wizard's death/flee shortfall against the two tankiest Standard-tier
# mobs (Bruiser hp10, Ambusher hp8): fled hands were routinely spending 2-3
# of 3 rounds on Snap Freeze/Frozen Shot/Ice Barricade to survive, at a real
# damage cost -- most had enough raw damage in hand to win, just not enough
# tempo once survival ate the round budget. Ice Barricade's 0-damage round
# was pure loss before this; arming Weave means it now sets up a real bonus
# for whatever payoff card follows, partially recovering the tempo spent on
# defense instead of just eating it. Confirmed: reduced flee counts against
# Bruiser (7/15 -> 5/15) and Ambusher (2/15 -> 1/15) at low starting HP,
# left death counts completely unchanged (those were mathematically
# unavoidable regardless of ordering -- Wizard has exactly one full-block
# card, and some mobs deal enough damage across the other two rounds alone
# to kill from a low starting HP no matter which round gets blocked). At
# the macro-loop level: Wizard's food_only Nothing-tier decay dropped from
# 32.6% to 28.2% and death rate from 0.39 to 0.31 per 20-trip run, landing
# it next to Cleric instead of standing alone as the clear worst class.
CARDS = {
    "Fire Blast":    dict(dmg=(3, 3), block=0,  grants_range=False, weave_source=True,  payoff=False),
    "Arcane Volley": dict(dmg=(6, 8), block=0,  grants_range=False, weave_source=False, payoff=True),
    "Snap Freeze":   dict(dmg=(1, 1), block=0,  grants_range=True,  weave_source=True,  payoff=False),
    "Ice Barricade": dict(dmg=(0, 0), block=10, grants_range=False, weave_source=True,  payoff=False),
    "Fire Ball":     dict(dmg=(5, 7), block=0,  grants_range=False, weave_source=False, payoff=True),
    "Frozen Shot":   dict(dmg=(2, 4), block=0,  grants_range=True,  weave_source=False, payoff=True),
}
DECK = list(CARDS.keys())

ALL_HANDS = list(itertools.combinations(DECK, 4))


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=WIZARD_HP):
    hp = starting_hp
    remaining_mob_hp = mob_hp
    weave_armed = False

    for rnd in range(3):
        card_name = seq_cards[rnd]
        card = CARDS[card_name]

        use_boost = card["payoff"] and weave_armed
        dmg = card["dmg"][1] if use_boost else card["dmg"][0]
        block = card["block"]

        if card["weave_source"]:
            weave_armed = True
        elif use_boost:
            weave_armed = False  # consumed

        mob_atk, mob_block, mob_type = mob_pattern[rnd]
        dmg_dealt = max(0.0, dmg - mob_block)
        remaining_mob_hp -= dmg_dealt

        if card["grants_range"] and mob_type == "melee":
            dmg_taken = 0.0
        else:
            dmg_taken = max(0.0, mob_atk - block)
        hp -= dmg_taken

        if hp <= 0:
            return False, hp, rnd + 1
        if remaining_mob_hp <= 0:
            return True, hp, rnd + 1
    return False, hp, 3


def best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=WIZARD_HP):
    best = None
    for seq_cards in orderings(hand):
        win, hp_left, rounds = simulate(seq_cards, mob_pattern, mob_hp, starting_hp)
        key = (win, hp_left)
        if best is None or key > best[0]:
            best = (key, (seq_cards, hp_left, rounds))
    return best[1]


def win_rate(mob_pattern, mob_hp, verbose=False, starting_hp=None):
    # See condensed_warrior.win_rate for why this isn't a default *parameter*
    # value -- that would freeze at import time and ignore `Z.WIZARD_HP = X`.
    if starting_hp is None:
        starting_hp = WIZARD_HP
    wins = 0
    for hand in ALL_HANDS:
        seq_cards, hp_left, rounds = best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=starting_hp)
        win, _, _ = simulate(seq_cards, mob_pattern, mob_hp, starting_hp=starting_hp)
        if win:
            wins += 1
        elif verbose:
            print(f"  LOSS hand={hand} best_seq={seq_cards}")
    return wins / len(ALL_HANDS)


if __name__ == "__main__":
    # same patterns/HP already tuned for Warrior; melee assumed for all
    mobs = {
        "Standard Grunt":     ([(4, 0, "melee"), (4, 0, "melee"), (6, 0, "melee")], 9),
        "Defensive Brute":    ([(4, 0, "melee"), (4, 3, "melee"), (6, 0, "melee")], 8),
        "Turtle then Burst":  ([(3, 4, "melee"), (4, 2, "melee"), (8, 0, "melee")], 6),
        "Glass Cannon":       ([(7, 0, "melee"), (5, 0, "melee"), (3, 0, "melee")], 9),
        "Sustained Pressure": ([(5, 0, "melee"), (5, 0, "melee"), (5, 0, "melee")], 9),
    }
    for name, (pattern, hp) in mobs.items():
        rate = win_rate(pattern, hp)
        print(f"{name:22s} HP={hp:2d} -> Wizard win rate = {rate:.1%}  (Warrior was tuned to ~90% on this mob)")
