"""
Exact solver for the condensed Rogue prototype -- LOCKED, designed by the
user directly through an iterative, checkpointed process (see
DECK_CONDENSING_GUIDE.md's checkpoint-discipline section, written after an
earlier solo AI attempt at this same class had to be fully reverted).

Mechanic: Cutthroat and Envenom are flat-base finishers with an explicit
lookup curve keyed by how many STRIKE-tagged cards were played since the
last finisher this pull (0, 1, or 2 -- 2 is the max reachable in a 3-round
pull with a finisher taking one of the three slots). Playing a finisher
resets the count to 0, matching AGGRO's real "Finisher: spend all CP" text
more faithfully than a hard one-finisher-per-pull ban (tested, not kept).
Cutthroat's curve (2 / 3 / 6) crosses over Envenom's flatter curve
(3 / 4 / 5): Envenom ahead at 0-1 strikes, Cutthroat ahead only once a hand
commits to building 2 strikes first.

Killing-blow rider (Warrior's Execute pattern: landing the kill prevents
the mob's attack that round) is on Cutthroat ONLY, a flavor call kept even
though the data showed putting it on Envenom instead got numerically
closer to the rest of the roster on flee-preference and wins/pull. That
gap was closed with HP instead (14 -> 16 across two passes) and a Block
buff on Dodge/Backstab (2 -> 4), not by moving the rider -- deliberately
separate levers so the flavor call didn't get silently re-litigated by the
numbers.

Ambush's bonus is keyed to round number instead of AGGRO's "if 0 CP"
condition (3 DMG normally, 5 if played in round 1) -- simpler, no resource
tracking needed for this card at all. Checked empirically: the bonus is
real (chased in 58.8% of played instances) but not chased blindly -- against
a mob with a heavy round-1 hit (Enforcer), hands with both Ambush and a
Block card correctly prioritize soaking that hit over cashing in the bonus.

Validated at lock-in (30,000-trial chained comparison against the other
four classes): pulls-survived 5.254 (tied with the pack, 5.266-5.767),
flee-preference 21.3% (in the pack's 20.0-38.7% range), wins/pull 76.78%
(pack: 72.96-75.80%, ~1pt over -- the one number that didn't fully close),
wins/trip 4.034 (dead center of the pack, 3.863-4.304 -- confirms the small
wins/pull overshoot isn't an outlier once combined with pulls-survived).
Damage floor/ceiling 9/15, win rate 93.3-100% across all 5 Standard mobs,
equilibrium clean, no hidden-domination.

Still open, not part of this lock-in: no evasion tool (dropped with Vanish
early in the design process, confirmed intentional, not revisited since).
"""
import itertools

ROGUE_HP = 16

CARDS = {
    "Dodge/Backstab": dict(kind="plain", dmg=4, block=4, strike=True),
    "Evasion":        dict(kind="plain", dmg=0, block=10, strike=False),
    "Quick Slash":    dict(kind="plain", dmg=3, block=0, strike=True),
    "Ambush":         dict(kind="opener", dmg=3, round1_dmg=5, block=0, strike=True),
    "Cutthroat":      dict(kind="finisher", curve={0: 2, 1: 3, 2: 6}, block=0, strike=False, killing_blow=True),
    "Envenom":        dict(kind="finisher", curve={0: 3, 1: 4, 2: 5}, block=0, strike=False, killing_blow=False),
}
DECK = list(CARDS.keys())

ALL_HANDS = list(itertools.combinations(DECK, 4))


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=ROGUE_HP):
    hp = starting_hp
    remaining_mob_hp = mob_hp
    strikes_played = 0

    for rnd in range(3):
        card_name = seq_cards[rnd]
        card = CARDS[card_name]
        kind = card["kind"]

        if kind == "finisher":
            dmg = card["curve"][min(strikes_played, 2)]
            strikes_played = 0  # Rule B: a finisher spends the count, doesn't just read it
        elif kind == "opener":
            dmg = card["round1_dmg"] if rnd == 0 else card["dmg"]
        else:
            dmg = card["dmg"]
        block = card["block"]

        if card["strike"]:
            strikes_played += 1

        mob_atk, mob_block, mob_type = mob_pattern[rnd]
        dmg_dealt = max(0.0, dmg - mob_block)
        remaining_mob_hp -= dmg_dealt

        # Killing-blow rider, same as Warrior's Execute: if a finisher with
        # the rider lands the kill this round, the mob's own attack is
        # prevented entirely -- a clean finish, not a trade. Cutthroat only
        # as of v8 (see module docstring); every other card, including
        # Envenom, still follows the normal "mob still acts" rule.
        if kind == "finisher" and card.get("killing_blow") and remaining_mob_hp <= 0:
            dmg_taken = 0.0
        else:
            dmg_taken = max(0.0, mob_atk - block)
        hp -= dmg_taken

        if hp <= 0:
            return False, hp, rnd + 1
        if remaining_mob_hp <= 0:
            return True, hp, rnd + 1
    return False, hp, 3


def best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=ROGUE_HP):
    best = None
    for seq_cards in orderings(hand):
        win, hp_left, rounds = simulate(seq_cards, mob_pattern, mob_hp, starting_hp)
        key = (win, hp_left)
        if best is None or key > best[0]:
            best = (key, (seq_cards, hp_left, rounds))
    return best[1]


def win_rate(mob_pattern, mob_hp, verbose=False, starting_hp=None):
    if starting_hp is None:
        starting_hp = ROGUE_HP
    wins = 0
    for hand in ALL_HANDS:
        seq_cards, hp_left, rounds = best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=starting_hp)
        win, _, _ = simulate(seq_cards, mob_pattern, mob_hp, starting_hp=starting_hp)
        if win:
            wins += 1
        elif verbose:
            print(f"  LOSS hand={hand} best_seq={seq_cards}")
    return wins / len(ALL_HANDS)
