"""
Exact solver for the condensed Warrior prototype (v3 -- AGGRO-aligned rework).
Deck=6, hand=4, 3 rounds max (mob flees after round 3).
No RNG needed for outcomes -- deterministic given hand+sequence+stance.
The only randomness is which 4-of-6 hand you draw; we enumerate all of them
and assume optimal play (best sequence+stance+choices) per hand, matching a
full-information, no-dice design.

v3 replaces Rally Blow/Brace with Vanguard Shield/Vanguard Blade, AGGRO's
real cards -- both carry an order-sensitive stance payoff ("if the previous
round's card dealt damage, deal bonus damage"), translating AGGRO's
within-turn "last card played this turn" rule into condensed combat's
cross-round structure, the same way Brace's reactive check already worked.
Deliberately phrased as "dealt damage" (checking the previous card's raw
dmg field), not "was an Attack" -- no Attack tag exists anywhere in this
system, and dmg>0 is exactly equivalent to AGGRO's own Attack tag for
every card in this kit.
"""
import itertools

WARRIOR_HP = 18

# name -> dict of stance-specific (dmg, block) pairs + tags.
# chain_stance: which stance gets the "previous round dealt damage" bonus,
# or None if the card doesn't have one. chain_bonus: how much bonus damage.
CARDS = {
    "Heavy Swing":     dict(G=(2, 0), C=(4, 0), sunder=False, execute_finisher=False,
                             chain_stance=None, chain_bonus=0, chain_target=None, chain_requires=None),
    "Sundering Blow":  dict(G=(1, 0), C=(1, 0), sunder=True,  execute_finisher=False,
                             chain_stance=None, chain_bonus=0, chain_target=None, chain_requires=None),
    # Execute: 6dmg, same in either stance, but only while the mob is at 50%
    # HP or lower -- illegal to play otherwise in Guardian or Champion (no
    # flat fallback value, this line is simply not a legal choice until the
    # mob is wounded). No stance asymmetry: G/C values unused, see
    # execute_finisher handling in _sim_from.
    "Execute":         dict(G=None, C=None,     sunder=False, execute_finisher=True,
                             chain_stance=None, chain_bonus=0, chain_target=None, chain_requires=None),
    # Same baseline in either stance now (2 DMG + 2 Block, trimmed from 3) --
    # stance only changes whether the bonus is reachable. Block trimmed
    # specifically because it was the real driver of multi-pull sustain
    # (confirmed: cutting it reduced trip length 10-23% depending on the
    # mob, while trimming Shield Block did nothing -- the solver routed
    # around a weaker Shield Block with zero net effect on trip outcomes).
    "Vanguard Shield": dict(G=(2, 2), C=(2, 2), sunder=False, execute_finisher=False,
                             chain_stance="G", chain_bonus=2, chain_target="block",
                             chain_requires="Vanguard Blade"),
    # Champion Shield Block is a confirmed false choice -- zeroing it never
    # changes an outcome, so it's zeroed for clarity: this card is a real,
    # honest Guardian-exclusive tool now, not a mediocre option in both.
    # Guardian value set to 5 specifically -- confirmed genuine 7/7/1
    # Guardian-vs-Champion parity (one hand is an exact numerical tie),
    # independent of Vanguard Shield's value.
    "Shield Block":    dict(G=(0, 5), C=(0, 0), sunder=False, execute_finisher=False,
                             chain_stance=None, chain_bonus=0, chain_target=None,
                             chain_requires=None),
    # Champion loses the 2 Block (3 DMG only there) -- Guardian keeps the
    # full 3 DMG + 2 Block baseline. Bonus stays +2 DMG in Champion only.
    "Vanguard Blade":  dict(G=(3, 2), C=(3, 0), sunder=False, execute_finisher=False,
                             chain_stance="C", chain_bonus=2, chain_target="dmg",
                             chain_requires="Vanguard Shield"),
}
DECK = list(CARDS.keys())
SUNDER_BONUS = 2  # Sundering Blow's persistent marker: +2 to all later damage, not +1

ALL_HANDS = list(itertools.combinations(DECK, 4))


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def stance_sequences():
    # Stance is chosen once at the start of a pull and locked for all 3
    # rounds -- no mid-pull flip.
    return [("G", "G", "G"), ("C", "C", "C")]


STANCE_SEQS = stance_sequences()


def _sim_from(rnd, seq_cards, stance_seq, mob_pattern, mob_hp_total,
              hp, remaining_mob_hp, sunder_stacks, prev_card_name):
    if rnd == 3:
        return (remaining_mob_hp <= 0, hp, rnd), (seq_cards, stance_seq)

    card_name = seq_cards[rnd]
    card = CARDS[card_name]
    stance = stance_seq[rnd]

    if card["execute_finisher"]:
        if remaining_mob_hp <= mob_hp_total * 0.5:
            dmg, block = 6, 0
        else:
            return (False, float("-inf"), rnd), (seq_cards, stance_seq)  # illegal
    else:
        dmg, block = card[stance]

    # Chain bonus: the SETUP card can be played in either stance (no
    # requirement there), but the PAYOFF card must be played in its own
    # designated stance, and the previous round's card must be the specific
    # named partner card -- not just "anything that dealt damage."
    if (card["chain_stance"] == stance and prev_card_name == card["chain_requires"]):
        if card["chain_target"] == "block":
            block += card["chain_bonus"]
        else:
            dmg += card["chain_bonus"]

    eff_dmg = dmg + (SUNDER_BONUS * sunder_stacks if dmg > 0 else 0)
    new_sunder = sunder_stacks + (1 if card["sunder"] else 0)

    mob_atk, mob_block = mob_pattern[rnd]
    dmg_dealt = max(0.0, eff_dmg - mob_block)  # mob's own Block still reduces damage dealt, unchanged
    new_remaining = remaining_mob_hp - dmg_dealt

    # Execute's clean-kill rider: if Execute lands the killing blow this
    # round, the mob's attack is prevented entirely -- narrower than the
    # global "kill interrupts the mob" rule we rejected elsewhere, scoped
    # only to Execute specifically (a clean, decisive finish, not a trade).
    # Every other card still follows the normal "mob still acts" rule.
    if card_name == "Execute" and new_remaining <= 0:
        dmg_taken = 0.0
    else:
        dmg_taken = max(0.0, mob_atk - block)
    new_hp = hp - dmg_taken

    if new_hp <= 0:
        return (False, new_hp, rnd + 1), (seq_cards, stance_seq)
    if new_remaining <= 0:
        return (True, new_hp, rnd + 1), (seq_cards, stance_seq)
    return _sim_from(rnd + 1, seq_cards, stance_seq, mob_pattern, mob_hp_total,
                      new_hp, new_remaining, new_sunder, card_name)


def simulate(seq_cards, stance_seq, mob_pattern, mob_hp, starting_hp=WARRIOR_HP):
    (win, hp_left, rounds), _ = _sim_from(0, seq_cards, stance_seq, mob_pattern, mob_hp,
                                           starting_hp, mob_hp, 0, None)
    return win, hp_left, rounds


def best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=WARRIOR_HP):
    best = None
    for seq_cards in orderings(hand):
        for stance_seq in STANCE_SEQS:
            win, hp_left, rounds = simulate(seq_cards, stance_seq, mob_pattern, mob_hp, starting_hp)
            key = (win, hp_left)
            if best is None or key > best[0]:
                best = (key, (seq_cards, stance_seq, hp_left, rounds))
    return best[1]


def win_rate(mob_pattern, mob_hp, verbose=False, starting_hp=None):
    # starting_hp defaults to None (not WARRIOR_HP) deliberately: a default
    # *parameter value* is bound once at import time and would silently
    # ignore any later `W.WARRIOR_HP = X` lever-twist. Reading the bare name
    # here instead looks it up live in the module's globals at call time.
    if starting_hp is None:
        starting_hp = WARRIOR_HP
    wins = 0
    for hand in ALL_HANDS:
        seq_cards, stance_seq, hp_left, rounds = best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=starting_hp)
        win, _, _ = simulate(seq_cards, stance_seq, mob_pattern, mob_hp, starting_hp=starting_hp)
        if win:
            wins += 1
        elif verbose:
            print(f"  LOSS hand={hand} best_seq={seq_cards} stance={stance_seq}")
    return wins / len(ALL_HANDS)
