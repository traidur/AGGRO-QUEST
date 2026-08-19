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

**Fixed the macro-loop risk-gate outlier (2026-08-19).** Root cause (see
CLASS_BALANCE_GUIDE.md's "Rogue and Ranger's macro-loop risk outlier"): only
Dodge/Backstab and Evasion carried any Block, and hand size is 4 -- meaning
the one hand holding all four of the other cards (Quick Slash, Ambush,
Cutthroat, Envenom) had zero Block anywhere, a real, confirmed-lethal gap
against Ambusher at HP=8. Same forced-curve validation used on Ranger
confirmed this was real danger, not policy over-caution: forcing Rogue's
risk-gate decisions onto Paladin's own defense-floor curve, while leaving
Rogue's real combat untouched, barely moved Gold (16.8 -> 18.0) but sent
deaths/run from 0.000 to 1.810.

Two fix attempts were tried and walked back before landing on the final
one -- both real overcorrections, not just directional confirmations, kept
here because the story matters:
1. Renamed Ambush -> "Ambush and Vanish," giving it grants_range (full
   evasion against melee mobs, reusing Wizard/Ranger's mechanic). Closed
   the exact worst-case hand outright (0/90 lethal at HP=8), but overshot
   badly in aggregate -- Gold hit 36.3 against Paladin's 23.8, because full
   evasion is a categorically stronger effect than incremental Block and
   the card was now played in 98.9% of hands where drawn. Reverted.
2. Gave Envenom the killing-blow rider too (previously Cutthroat-only).
   Also closed the worst-case hand (Envenom landing the kill on the
   problem hand prevents Ambusher's retaliation), still overshot (Gold
   31.2) but by less than the evasion attempt -- kept, since it's a real,
   validated, thematically strong addition (see below), just needed
   correcting elsewhere rather than reverting outright.

**Locked: Envenom gains the killing-blow rider (matching Cutthroat's,
Warrior's Execute pattern) -- Backstab and Dodge's Block 4 -> 2 -- ROGUE_HP
16 -> 15.** The Block and HP cuts are a genuinely different kind of lever
from the killing-blow fix: they operate on the chain/macro level (bringing
an already-overshooting aggregate back in line), not the single-pull level
the original defense-floor gap needed fixing on -- HP is not standing in
for an undiagnosed card problem here, the card problem was already found
and fixed; HP is correcting the resulting aggregate overshoot afterward,
a different question CLASS_BALANCE_GUIDE.md's "HP as a balance lever"
caveat doesn't actually forbid. Final numbers: Gold@24XP 23.1 (Paladin
23.8), quests/trip 2.09 (Paladin 2.16), deaths/run 0.000 across 300
trials -- landing just under Paladin rather than past it, the same
shape Ranger's own fix settled into.

Worth naming the real shape of this fix directly: Rogue ended up with
*less* raw Block and *less* HP than it started with, and still performs
better, because the entire net gain came from one mechanic change. That's
a good identity signal, not just a numeric coincidence -- both finishers
now carry "the target doesn't get to hit back if you finish it first"
instead of generic durability, which reads more like an assassin than
stacking Block ever did.
"""
import itertools

ROGUE_HP = 15

# aggro: co-op Party Pull targeting value (0-4), locked via direct user
# review -- see OPEN_QUESTIONS.md's "Co-op multi-hero vs. one Elite" entry.
CARDS = {
    "Backstab and Dodge": dict(kind="plain", dmg=4, block=2, strike=True, aggro=3),
    "Evasion":            dict(kind="plain", dmg=0, block=10, strike=False, aggro=1),
    "Quick Slash":        dict(kind="plain", dmg=3, block=0, strike=True, aggro=2),
    "Ambush":             dict(kind="opener", dmg=3, round1_dmg=5, block=0, strike=True, aggro=3),
    "Cutthroat":          dict(kind="finisher", curve={0: 2, 1: 3, 2: 6}, block=0, strike=False, killing_blow=True, aggro=4),
    "Envenom":            dict(kind="finisher", curve={0: 3, 1: 4, 2: 5}, block=0, strike=False, killing_blow=True, aggro=2),
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
