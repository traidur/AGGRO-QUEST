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

**Level 2 leveling infrastructure (2026-08-20):** `simulate()` gained an opt-in `armor_pierce`
field -- a card with this set ignores the mob's own block value entirely for its damage this
round, instead of the usual `max(0, dmg - mob_block)`. Absent on every base card, so the base
Level 1 kit is untouched (verified no-op). Used on the locked Level 2 Backstab and Dodge [Lv 2]
(damage held at 4, gains armor_pierce, rather than the flat +1 damage first considered) -- see
LEVELING_GUIDE.md's "Fourth class worked example: Rogue" for the full derivation. Leveled kits
themselves live in LEVELING_GUIDE.md as documented `leveled_kit` swaps, not baked into this
module's own CARDS, matching every other class.
"""
import itertools
from dataclasses import replace

from combat_round import RoundState, RoundOutcome

ROGUE_HP = 15

# aggro: co-op Party Pull targeting value (0-4), locked via direct user
# review -- see OPEN_QUESTIONS.md's "Co-op multi-hero vs. one Elite" entry.
# version: printed-card revision number, bumped only when a card's printed text/numbers
# change -- lets a physical deck owner tell which cards need reprinting. See
# CARD_REFERENCE.md's own note for the convention.
CARDS = {
    "Backstab and Dodge": dict(combat_type="melee",kind="plain", dmg=4, block=2, strike=True, aggro=3, version=1),
    "Evasion": dict(combat_type="melee",kind="plain", dmg=0, block=10, strike=False, aggro=1, version=1),
    "Quick Slash": dict(combat_type="melee",kind="plain", dmg=3, block=0, strike=True, aggro=2, version=1),
    "Ambush": dict(combat_type="ranged",kind="opener", dmg=3, round1_dmg=5, block=0, strike=True, aggro=3, version=2),
    "Cutthroat": dict(combat_type="melee",kind="finisher", curve={0: 2, 1: 3, 2: 6}, block=0, strike=False, killing_blow=True, aggro=4, version=1),
    "Envenom": dict(combat_type="ranged",kind="finisher", curve={0: 3, 1: 4, 2: 5}, block=0, strike=False, killing_blow=True, aggro=2, version=1),
}
DECK = list(CARDS.keys())

ALL_HANDS = list(itertools.combinations(DECK, 4))


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def resolve_round(state, card_name, stance, round_num, mob_pattern, mob_hp_total,
                   mob_hp_remaining, hero_hp, hero_max_hp):
    """The one place Rogue's card-effect logic lives. Faithful port of the real, current
    simulate() below. stance is unused (Rogue has none). hero_max_hp threaded through
    unchanged (no Rogue card raises it)."""
    card = CARDS[card_name]
    kind = card["kind"]
    new_strikes_played = state.strikes_played_rogue

    if kind == "finisher":
        dmg = card["curve"][min(state.strikes_played_rogue, 2)]
        new_strikes_played = 0  # Rule B: a finisher spends the count, doesn't just read it
    elif kind == "opener":
        dmg = card["round1_dmg"] if round_num in card.get("bonus_rounds", (0,)) else card["dmg"]
    else:
        dmg = card["dmg"]
    block = card["block"]

    if card["strike"]:
        new_strikes_played = state.strikes_played_rogue + 1

    mob_atk, mob_block, mob_type = mob_pattern[round_num]
    if card.get("armor_pierce"):
        dmg_dealt = dmg
    else:
        dmg_dealt = max(0.0, dmg - mob_block)
    new_remaining = mob_hp_remaining - dmg_dealt

    if kind == "finisher" and card.get("killing_blow") and new_remaining <= 0:
        dmg_taken = 0.0
    else:
        dmg_taken = max(0.0, mob_atk - block)
    new_hp = hero_hp - dmg_taken

    new_state = replace(state, strikes_played_rogue=new_strikes_played)
    return RoundOutcome(new_hp=new_hp, new_mob_hp_remaining=new_remaining, new_hero_max_hp=hero_max_hp,
                         new_state=new_state, dmg_dealt=dmg_dealt, dmg_taken=dmg_taken,
                         raw_dmg=dmg, block=block, heal=0.0)


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=ROGUE_HP):
    state = RoundState()
    hp, remaining, max_hp = starting_hp, mob_hp, starting_hp
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
