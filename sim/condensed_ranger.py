"""
Exact solver for the condensed Ranger prototype -- LOCKED, designed by the
user directly, card by card, over a long iterative session (see
DECK_CONDENSING_GUIDE.md's checkpoint-discipline section for why that
matters here; a first solo-AI attempt at Ranger was never built -- Rogue's
solo-attempt incident happened first and set the working pattern before
Ranger's build ever started).

Source: AGGRO's real Level-1 Ranger kit (StS_WoW_Sim/data/cards.csv,
class_name=ranger, base card_ids 601-610, 10 cards -- an earlier pull of
this data filtered on the wrong CSV column and incorrectly reported only
8 cards; corrected before any design work started).

Two mechanics, both new to this codebase:

1. **Persistent Block (Beast Bond: Wolf).** Playing it deals 4 DMG once
   (the wolf's opening pounce) and activates Block *every round from then
   on, including the round it's played* (the wolf now on the field,
   redirecting hits) -- stacks with whatever Block that round's own card
   already grants. First multi-round-persistent effect in this codebase;
   every other class's Block clears each round. Deliberately NOT capped to
   a fixed window -- tested empirically instead of assumed: it's chased in
   76% of hands where drawn (not a hard lock, but a strong pull), and
   halving its per-round value (2 -> 1) was the single biggest lever in
   bringing Ranger's whole kit down from roughly double the rest of the
   roster's chained numbers to in-range.
2. **Positioning payoff (Sniper/Point Blank Shot).** Reads whether the
   *previous* round's card granted Range (Withdrawing Hip Shot or Crippling
   Shot): 7 DMG if so, 5 DMG otherwise. Reuses Warrior's existing
   previous-card-dependent chain-bonus pattern (Vanguard Blade/Shield),
   just keyed on a property (grants_range) instead of a specific card name.
   Does not itself grant Range for a future card to read.

Positioning itself reuses Wizard's exact mechanic: grants_range evades a
melee mob's attack entirely that round. Was permanently inert against an
all-melee roster (no mob it didn't work against); now real against Scout,
the Standard tier's 6th (ranged) mob -- see CLASS_BALANCE_GUIDE.md's
"Sixth Standard-tier mob" section.

**Tuning path, in order:** the original Beast's Challenge (flat 0 DMG / 5
Block) drove single-pull win rate to 100% on every mob with zero real
losses possible -- fixed by making its damage conditional on Beast Bond
having been played first (5 DMG if so, 2 otherwise) instead of flat block,
restoring a real floor. Chained numbers were then roughly double the rest
of the roster (Beast Bond's persistent block compounding across a chain,
the same shape Cleric's early healing overshoot took) -- Beast Bond's
per-round block value 2 -> 1 cut that gap in half; RANGER_HP briefly
dropped 15 -> 14 to close the remainder, then explicitly reverted (kept at
15 deliberately -- Ranger reads as Mail-armor tier by AGGRO's own design,
distinct from the Cloth-tier classes at 14, and that identity signal was
judged more important than a fully-closed integer gap); Sure Shot's flat
damage 5 -> 4 closed the same remaining gap without touching HP or the
already-correct defensive numbers, landing all three chained metrics
in-range at once. See CLASS_BALANCE_GUIDE.md's "Numeric tuning playbook"
for the generalized version of each of these levers.

Locked, validated at 5000-trial chained comparison against the rest of the
6-class roster (post-Scout): pulls-survived 5.11 (pack: 5.11-5.63), wins/
trip 3.83 (pack: 3.83-4.33), wins/pull 75.0% (pack: 73.9-78.5%). Damage
floor/ceiling 8/14, win rate 93.3-100% across all 6 Standard mobs,
equilibrium clean. One known hidden-domination flag remains (Withdrawing
Hip Shot vs. Crippling Shot, both deal 2 DMG and grant Range identically)
-- confirmed by a direct, out-of-aggregate check that the two cards DO
genuinely differ against Scout (Crippling Shot's +1 Block reduces a
Scout hit once evasion stops helping). The aggregate flag itself still
doesn't flip, for a structural reason, not because the fix is wrong: of
the 6 hands that draw both cards against Scout, half play both together
(not a one-vs-the-other case at all) and half land the differing card in
a round the fight never reaches -- exhausting every hand without ever
isolating the difference the way the checker's methodology requires. See
CLASS_BALANCE_GUIDE.md's "Sixth Standard-tier mob" section for the full
trace.

RANGER_HP = 15.
"""
import itertools

RANGER_HP = 15

CARDS = {
    "Beast Bond: Wolf":         dict(dmg=4, block=0, grants_range=False, beast_bond=True, beast_block_value=1,
                                      payoff_prev_range=False),
    "Withdrawing Hip Shot":     dict(dmg=2, block=0, grants_range=True, beast_bond=False, payoff_prev_range=False),
    "Sniper/Point Blank Shot":  dict(dmg=None, block=0, grants_range=False, beast_bond=False, payoff_prev_range=True,
                                      dmg_if_prev_range=7, dmg_else=5),
    "Beast's Challenge":        dict(dmg=None, block=0, grants_range=False, beast_bond=False, payoff_prev_range=False,
                                      payoff_wolf=True, dmg_if_wolf=5, dmg_else=2),
    "Sure Shot":                dict(dmg=4, block=0, grants_range=False, beast_bond=False, payoff_prev_range=False),
    "Crippling Shot":           dict(dmg=2, block=1, grants_range=True, beast_bond=False, payoff_prev_range=False),
}
DECK = list(CARDS.keys())

ALL_HANDS = list(itertools.combinations(DECK, 4))


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=RANGER_HP):
    hp = starting_hp
    remaining_mob_hp = mob_hp
    beast_active = False
    prev_grants_range = False

    for rnd in range(3):
        card_name = seq_cards[rnd]
        card = CARDS[card_name]

        if card["payoff_prev_range"]:
            dmg = card["dmg_if_prev_range"] if prev_grants_range else card["dmg_else"]
        elif card.get("payoff_wolf"):
            dmg = card["dmg_if_wolf"] if beast_active else card["dmg_else"]
        else:
            dmg = card["dmg"]

        if card["beast_bond"]:
            beast_active = True  # activates starting this same round
        block = card["block"] + (CARDS["Beast Bond: Wolf"]["beast_block_value"] if beast_active else 0)

        mob_atk, mob_block, mob_type = mob_pattern[rnd]
        dmg_dealt = max(0.0, dmg - mob_block)
        remaining_mob_hp -= dmg_dealt

        if card["grants_range"] and mob_type == "melee":
            dmg_taken = 0.0
        else:
            dmg_taken = max(0.0, mob_atk - block)
        hp -= dmg_taken

        prev_grants_range = card["grants_range"]

        if hp <= 0:
            return False, hp, rnd + 1
        if remaining_mob_hp <= 0:
            return True, hp, rnd + 1
    return False, hp, 3


def best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=RANGER_HP):
    best = None
    for seq_cards in orderings(hand):
        win, hp_left, rounds = simulate(seq_cards, mob_pattern, mob_hp, starting_hp)
        key = (win, hp_left)
        if best is None or key > best[0]:
            best = (key, (seq_cards, hp_left, rounds))
    return best[1]


def win_rate(mob_pattern, mob_hp, verbose=False, starting_hp=None):
    if starting_hp is None:
        starting_hp = RANGER_HP
    wins = 0
    for hand in ALL_HANDS:
        seq_cards, hp_left, rounds = best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=starting_hp)
        win, _, _ = simulate(seq_cards, mob_pattern, mob_hp, starting_hp=starting_hp)
        if win:
            wins += 1
        elif verbose:
            print(f"  LOSS hand={hand} best_seq={seq_cards}")
    return wins / len(ALL_HANDS)
