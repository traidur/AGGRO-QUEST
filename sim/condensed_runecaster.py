"""
Exact solver for the condensed Runecaster prototype -- LOCKED, seventh class, numbers
given directly by the user (not an AI draft), tuning-tested and adjusted from there.

Source: AGGRO's real Level-1 Runecaster kit (StS_WoW_Sim/data/cards.csv, class_name=
runecaster, card_ids 901-911, 10 cards -- Windstep and Call of the Glacier's original
SLOW rider cut; SLOW is confirmed a pure Zone/movement-lock keyword ("Cannot change
Zones... Cannot be dragged", StS_x_WoW_Classes_v7_4.md's CC table) with zero functional
meaning in condensed combat's single-mob, no-movement format).

Two mechanics, one reused, one new to this codebase:

1. **Chain bonus (Lightning Bolt).** Reuses Warrior's Vanguard Blade/Shield
   previous-card-dependent pattern: Lightning Bolt deals 3 DMG normally, 4 if the
   previous round's card was Chain Lightning. Reframes AGGRO's "Lightning Bolt costs 0E
   this turn" clause (no Energy system in QUEST) into a damage payoff instead of a cost
   discount.

2. **Echo (Earth Strike Rune) -- new mechanic shape.** Deals 2 DMG + heals 2 HP the round
   it's played; automatically deals 1 more DMG + heals 1 more HP at the very start of the
   *next* round, before that round's own card resolves -- no card needs to be played or
   drawn for the echo to fire, and it stacks with whatever else happens that round. Folds
   AGGRO's two separate Rune cards (Windstriker Rune's STRIKE buff, Earth-Mender Rune's
   recurring Zone heal) into one card, and reuses Call of the Volcano's DOT-tick shape
   (damage automatically resolving on a later round) but bounded to exactly one echo
   round, and paired with a heal component. Boundary conditions, stated explicitly:
   played in round 3 (last round), the echo simply never fires -- there's no round 4,
   same structural boundary Rogue's Cutthroat curve already relies on (nothing special to
   implement). If the pull ends (win or loss) before the echo's round is reached, it never
   fires either -- again nothing special, the round loop already stops. The echo is
   reduced by the mob's Block that round exactly like any other damage source, no
   exception.

Call of the Glacier: SLOW dropped, repurposed as a positioning/evasion card instead
(grants_range=True, evades a melee mob's attack that round) -- reuses Wizard/Ranger's
existing grants_range mechanic rather than inventing a new one.

Windstrike's STRIKE tag dropped entirely (confirmed with the user) -- nothing in this
kit reads it, so it's not encoded as a flag at all, not even a vestigial no-op one.

No stance system -- has_stance=False, same category as Wizard/Cleric/Paladin/Rogue.
RUNECASTER_HP = 16 (Mail-tier, user-set -- Runecaster is not Cloth like Cleric/Wizard).

**Tuning path.** First numbers pass had Tidal Ward at (heal 3, block 3) and Earth Strike
Rune at (2 dmg + 2 heal this round, 1 dmg + 1 heal echo) -- broke equilibrium on Grunt and
Bruiser (a "cannot die" bug, the exact same failure mode Cleric hit originally) and blew
every chained-trip metric far outside the rest of the roster's range (9.14 pulls vs. the
pack's 5.12-5.64). Root cause: two separate heal sources plus the echo's "free" second
round of value (no card slot spent) added up to meaningfully more sustain than any other
class carries. Fix: Tidal Ward cut to (heal 2, block 2), Earth Strike Rune's first-round
heal cut from 2 to 1 (echo's 1/1 left untouched) -- closed both problems in one pass,
equilibrium ALL CLEAR, all three chained-trip metrics back in range (5.43 pulls, 4.14
wins/trip, 76.2% wins/pull vs. pack 5.12-5.64 / 3.83-4.34 / 73.9-78.4%).

**Locked, validated:** damage floor/ceiling 9/15 (matches Rogue's exact numbers). Waste
Index 1.98 dmg overkill / 0.27 HP overheal, both within the pack's range (1.10-2.85 dmg,
0.00-0.24 HP -- Runecaster's overheal sits right next to Cleric's, the only other real
healer). Elite trio (solo baseline, Bulwark/Berserker/Warlord): 50.6% cost / 64.4% win
aggregate, landing inside the locked 6-class spread (44.3-55.7% cost, 55.6-75.6% win) with
no single Elite an outlier. Chain Lightning vs. Call of the Glacier flagged `clean-thin`
by the hidden-domination check (only 2 real observations) -- dug in manually rather than
trusting the thin aggregate: 34 of 36 hand/mob combos play both cards *together* (they're
complementary, not competing for the same slot), and the 2 forced-swap comparisons that did
occur were both against Scout, the one ranged Standard mob, where Call of the Glacier's
`grants_range` is worthless by construction -- expected behavior, not domination. Echo
mechanic hand-traced directly (Earth Strike Rune -> Lightning Bolt -> Windstrike vs. Grunt)
to confirm it resolves correctly, not just that the aggregate looked fine -- confirmed,
including the echo's damage getting fully absorbed by Grunt's round-2 Block while its heal
still landed (heals aren't blocked). RUNECASTER_HP=16 was not swept against neighboring
values the way Ranger's HP got negotiated across three passes -- it landed in range on the
first try and was kept, not re-litigated once it worked.

**2026-08-30, redone:** a first worst-pair-round2-breadth rebalance pass (Chain Lightning
6->4, Call of the Glacier 3->4) was locked, then reverted when a real bug surfaced in
`resolve_round`'s mob-Block handling: Block was being applied as a flat reduction to Echo
damage AND this round's own card damage independently, instead of depleting as a single,
first-come-first-served pool the way the user's actual tabletop play (and QUEST's stated
ancestry, AGGRO and Slay the Spire) has always worked. See `resolve_round`'s own docstring
for the fix. Once corrected, the worst-pair-round2-breadth investigation was redone from
scratch against the fixed combat math -- landed on the *identical* numbers as the reverted
pass (Chain Lightning 6->4, Call of the Glacier 3->4), since neither card involves the Echo
mechanic at all, so their own math was never actually affected by the bug. Worst-pair breadth
4/6->2/6, clean against both the live pack and the frozen baseline, win rate 100% on all six
mobs, full combo-dominance sweep post-fix: nothing flagged. See CLASS_BALANCE_GUIDE.md's
"Fixing a worst-pair round-2 shortcut" recipe for the full methodology.
"""
import itertools
from dataclasses import replace

from combat_round import RoundState, RoundOutcome

RUNECASTER_HP = 16

# dmg/heal/block are flat, unconditional base values. grants_range evades a melee mob's
# attack this round (mob_type is read the same way Wizard/Rogue/Ranger already do it).
# chain_bonus_if_prev/chain_bonus_dmg: Lightning Bolt's payoff, keyed on the literal
# previous-round card name, same pattern as Warrior's Vanguard Blade/Shield.
# echo_dmg/echo_heal: Earth Strike Rune's automatic next-round tick.
# aggro: co-op Party Pull targeting value (0-4), locked via direct user
# review -- see OPEN_QUESTIONS.md's "Co-op multi-hero vs. one Elite" entry.
# version: printed-card revision number, bumped only when a card's printed text/numbers
# change -- lets a physical deck owner tell which cards need reprinting. See
# CARD_REFERENCE.md's own note for the convention.
CARDS = {
    "Chain Lightning": dict(combat_type="ranged",dmg=4, heal=0, block=0, grants_range=False,
                                chain_bonus_if_prev=None, chain_bonus_dmg=0,
                                echo_dmg=0, echo_heal=0, aggro=3, version=2),
    "Lightning Bolt": dict(combat_type="ranged",dmg=3, heal=0, block=0, grants_range=False,
                                chain_bonus_if_prev="Chain Lightning", chain_bonus_dmg=1,
                                echo_dmg=0, echo_heal=0, aggro=2, version=1),
    "Call of the Glacier": dict(combat_type="ranged",dmg=4, heal=0, block=0, grants_range=True,
                                 chain_bonus_if_prev=None, chain_bonus_dmg=0,
                                 echo_dmg=0, echo_heal=0, aggro=3, version=2),
    "Tidal Ward": dict(combat_type="melee",dmg=0, heal=2, block=2, grants_range=False,
                                chain_bonus_if_prev=None, chain_bonus_dmg=0,
                                echo_dmg=0, echo_heal=0, aggro=1, version=1),
    "Windstrike": dict(combat_type="melee",dmg=5, heal=0, block=0, grants_range=False,
                                chain_bonus_if_prev=None, chain_bonus_dmg=0,
                                echo_dmg=0, echo_heal=0, aggro=3, version=1),
    "Earth Strike Rune": dict(combat_type="melee",dmg=2, heal=1, block=0, grants_range=False,
                                chain_bonus_if_prev=None, chain_bonus_dmg=0,
                                echo_dmg=1, echo_heal=1, aggro=0, version=1),
}
DECK = list(CARDS.keys())

ALL_HANDS = list(itertools.combinations(DECK, 4))


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def resolve_round(state, card_name, stance, round_num, mob_pattern, mob_hp_total,
                   mob_hp_remaining, hero_hp, hero_max_hp):
    """The one place Runecaster's card-effect logic lives. Faithful port of the real,
    current simulate() below -- flagged as the hardest port in this project's own plan
    (unified-sprouting-aurora.md): Echo resolves at the START of this round, from whatever
    the PREVIOUS round's card set in state.pending_echo_dmg/heal, before this round's own
    card's own effects apply. Get this ordering exactly right -- verified byte-for-byte
    against the old recursive/loop version across all hands x mobs, not just spot-checked.
    stance is unused (Runecaster has none). hero_max_hp threaded unchanged (healing caps at
    the class's own RUNECASTER_HP constant here, same pattern as Paladin, not Cleric's
    dynamic ceiling).

    **Mob Block is a depleting pool for the round, not a flat reduction reapplied to every
    damage source separately (fixed 2026-08-30, confirmed against the user's actual tabletop
    play and QUEST's own stated ancestry -- AGGRO and Slay the Spire both work this way).**
    When Echo and this round's own card both deal damage in the same round, Block absorbs the
    Echo first (since it resolves first), and whatever's left over -- possibly nothing --
    reduces this round's own card damage. The two are NOT each independently reduced by the
    same printed Block number; every point of Block is single-use within the round, first hit
    served first. This is the only place in Runecaster's kit where it matters, since no other
    mechanic here deals two separate damage instances in one round."""
    card = CARDS[card_name]
    mob_atk, mob_block, mob_type = mob_pattern[round_num]
    remaining_block = mob_block  # depletes as it absorbs damage this round, first-come-first-served

    # Echo from an Earth Strike Rune played LAST round -- resolves before THIS round's own
    # card, stacks with it, no card slot consumed. Reads state.pending_echo_* (set by the
    # previous call), not this round's own card.
    hp = hero_hp
    new_remaining = mob_hp_remaining
    if state.pending_echo_heal:
        hp = min(hero_max_hp, hp + state.pending_echo_heal)
    if state.pending_echo_dmg:
        echo_dmg = state.pending_echo_dmg
        absorbed = min(remaining_block, echo_dmg)
        remaining_block -= absorbed
        new_remaining -= (echo_dmg - absorbed)

    dmg, heal, block = card["dmg"], card["heal"], card["block"]
    if card["chain_bonus_if_prev"] == state.rc_prev_card_name:
        dmg += card["chain_bonus_dmg"]

    hp = min(hero_max_hp, hp + heal)

    absorbed = min(remaining_block, dmg)
    remaining_block -= absorbed
    dmg_dealt = dmg - absorbed
    new_remaining -= dmg_dealt

    if card["grants_range"] and mob_type == "melee":
        dmg_taken = 0.0
    else:
        dmg_taken = max(0.0, mob_atk - block)
    new_hp = hp - dmg_taken

    new_state = replace(state, pending_echo_dmg=card["echo_dmg"], pending_echo_heal=card["echo_heal"],
                         rc_prev_card_name=card_name)
    return RoundOutcome(new_hp=new_hp, new_mob_hp_remaining=new_remaining, new_hero_max_hp=hero_max_hp,
                         new_state=new_state, dmg_dealt=dmg_dealt, dmg_taken=dmg_taken,
                         raw_dmg=dmg, block=block, heal=heal)


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=RUNECASTER_HP):
    state = RoundState()
    hp, remaining, max_hp = starting_hp, mob_hp, RUNECASTER_HP
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


def best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=RUNECASTER_HP):
    best = None
    for seq_cards in orderings(hand):
        win, hp_left, rounds = simulate(seq_cards, mob_pattern, mob_hp, starting_hp)
        key = (win, hp_left)
        if best is None or key > best[0]:
            best = (key, (seq_cards, hp_left, rounds))
    return best[1]


def win_rate(mob_pattern, mob_hp, verbose=False, starting_hp=None):
    if starting_hp is None:
        starting_hp = RUNECASTER_HP
    wins = 0
    for hand in ALL_HANDS:
        seq_cards, hp_left, rounds = best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=starting_hp)
        win, _, _ = simulate(seq_cards, mob_pattern, mob_hp, starting_hp=starting_hp)
        if win:
            wins += 1
        elif verbose:
            print(f"  LOSS hand={hand} best_seq={seq_cards}")
    return wins / len(ALL_HANDS)
