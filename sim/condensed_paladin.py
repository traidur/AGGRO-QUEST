"""
Exact solver for the condensed Paladin prototype -- first pass, v2 (folded
Invocation design), rebalanced 2026-08-30 to close a genuine 2-card shortcut
(see below and CLASS_BALANCE_GUIDE.md's Paladin section for the full
investigation).

Mechanic, locked through iteration with the user: two self-contained
"Invocation of X" cards replace the original three-card Virtue+shared-
Invocation structure from CONDENSED_COMBAT.md's original design note.
Each Invocation card is simultaneously a payoff for STRIKE cards already
played earlier in the pull AND a setup for STRIKE cards played after it:

  Invocation of Sanctuary: on play, deal 3 dmg + 2 dmg per STRIKE card
  already played earlier this pull. Every STRIKE card played afterward
  also generates +2 dmg when played.

  Invocation of Grace: on play, deal 4 dmg + heal 2 HP per STRIKE card
  already played earlier this pull. Every STRIKE card played afterward
  also heals +2 HP when played.

  (Per-STRIKE bonus raised from +1 to +2 as part of the 2026-08-30
  rebalance -- moves damage budget out of the two flat STRIKE cards
  and into a bonus that only pays off with the full 3-card investment,
  so the fast 2-card burst specifically loses value while a real
  Strike+Strike+Invocation line keeps its old total.)

Exclusive: only one of the two Invocation cards may be played per pull,
ever (confirmed explicitly, same "one lane, chosen once" restriction
CONDENSED_COMBAT.md's original Virtue design already established).

Might of the Aegis and Bastion's Hammer are the two STRIKE-tagged cards
(matches AGGRO's real STRIKE tag -- verified against StS_WoW_Sim/data/
cards.csv). Vigil of Light and Holy Fortress are plain support cards, not
STRIKE-tagged, so they don't feed the Invocation bonus chain either
direction. Holy Fortress is simplified from AGGRO's real charge/reactive-
damage sub-mechanic to a flat dmg+block card for this first pass.

**2026-08-30 rebalance, full record:** a roster-wide sweep (worst-pair
round-2-finish breadth, see CLASS_BALANCE_GUIDE.md) found Might of the
Aegis(4)+Bastion's Hammer(6)=10 raw damage cleared every Standard mob's HP
(ceiling 10) in two cards, no mechanic needed -- literally any two of the
kit's damage cards did it. Fixed via: Might of the Aegis dmg 4->3,
Bastion's Hammer dmg 6->4, Invocation's per-STRIKE bonus 1->2 (so a full
3-card kit still reaches its old damage total, just not in 2 cards), Holy
Fortress dmg 2->3, and Sacred Light renamed Vigil of Light with block=1
added (was the least-played card in the kit, 8/90 real hand/mob
appearances; needed to close a real win-rate gap the burst nerf opened
against Bruiser/Enforcer specifically). PALADIN_HP was tried at 18
(partially restoring the earlier Warrior-1 dial-back) mid-investigation
when the burst nerf alone had left the class weaker on chained-trip
metrics, but once Holy Fortress and Vigil of Light were also carrying
their share of the load, HP=17 (the original, pre-existing value) landed
cleaner -- pulls=5.94 sits inside the pack range at HP=17 vs. 6.23
(outside it) at HP=18 -- so the HP dial-back was never actually needed
and PALADIN_HP stays at its original 17. Worst-pair breadth went from 6/6
(every mob) to 3/6; full tuning_report validated clean afterward.

No stance system -- has_stance=False, same category as Wizard/Cleric.
"""
import itertools
from dataclasses import replace

from combat_round import RoundState, RoundOutcome

PALADIN_HP = 17  # locked: settled at Warrior-1 after the Sacred Light/HP dial-back pass.
                 # Tried at 18 mid-2026-08-30-rebalance (see note above) but landed worse
                 # than the original 17 once Holy Fortress/Vigil of Light were also in
                 # the mix -- stays at 17.

INVOCATION_PER_STRIKE_BONUS = 2  # 2026-08-30: raised from 1 -- see rebalance note above.

# grants_aura_block's Block bonus is deliberately its OWN constant, not
# INVOCATION_PER_STRIKE_BONUS -- found 2026-09-04: the 2026-08-30 rebalance doubled
# INVOCATION_PER_STRIKE_BONUS to compensate for spread-out damage numbers, with zero
# awareness that Level 2's grants_aura_block field (added in the leveling pass, a separate,
# later change) read the same constant for its Block bonus. That silently doubled the
# leveled mandatory upgrade's real strength (validated at 1, running at 2) without anyone
# touching or re-validating the leveling work at all -- see LEVELING_GUIDE.md's Paladin
# section for the full trail.
# Locked back at 1, its original validated value, independent of whatever the damage-side
# constant does in the future.
INVOCATION_AURA_BLOCK_BONUS = 1

# dmg/heal/block are flat, unconditional base values. strike=True marks the
# two cards the Invocation bonus chain keys off. invocation={"sanctuary",
# "grace",None} marks the two Invocation cards.
# grants_aura_block: only ever True for the leveled-up "Invoking Aura of
# Sanctuary" swap-in (see LEVELING_GUIDE.md) -- False on every real, locked
# card here, pure schema addition, no-op against this file's own baseline.
# When the active (first-played) Invocation has this set, the existing
# per-STRIKE dmg bonus (retroactive on this card's own play, forward on
# every later STRIKE this pull) is mirrored 1:1 in Block -- even on a STRIKE
# card that doesn't normally have any Block of its own.
# aggro: co-op Party Pull targeting value (0-4), locked via direct user
# review -- see OPEN_QUESTIONS.md's "Co-op multi-hero vs. one Elite" entry.
# version: printed-card revision number, bumped only when a card's printed text/numbers
# change -- lets a physical deck owner tell which cards need reprinting. See
# CARD_REFERENCE.md's own note for the convention.
CARDS = {
    "Might of the Aegis": dict(combat_type="melee",dmg=3, heal=0, block=2, strike=True,  invocation=None, aggro=4, grants_aura_block=False, version=2),
    "Bastion's Hammer": dict(combat_type="melee",dmg=4, heal=0, block=0, strike=True,  invocation=None, aggro=2, grants_aura_block=False, version=2),
    "Vigil of Light": dict(combat_type="ranged",dmg=0, heal=3, block=1, strike=False, invocation=None, aggro=2, grants_aura_block=False, version=2),
    "Holy Fortress": dict(combat_type="melee",dmg=3, heal=0, block=4, strike=False, invocation=None, aggro=4, grants_aura_block=False, version=2),
    "Invocation of Sanctuary": dict(combat_type="ranged",dmg=3, heal=0, block=0, strike=False, invocation="sanctuary", aggro=3, grants_aura_block=False, version=2),
    "Invocation of Grace": dict(combat_type="ranged",dmg=4, heal=0, block=0, strike=False, invocation="grace", aggro=3, grants_aura_block=False, version=2),
}
DECK = list(CARDS.keys())

ALL_HANDS = list(itertools.combinations(DECK, 4))


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def resolve_round(state, card_name, stance, round_num, mob_pattern, mob_hp_total,
                   mob_hp_remaining, hero_hp, hero_max_hp):
    """The one place Paladin's card-effect logic lives. Faithful port of the real, current
    simulate() below (NOT playtest_engine.py's older _resolve_paladin_round, which predates
    the grants_aura_block leveled-card field added to CARDS since -- verified by direct
    comparison before porting). stance is unused (Paladin has none). hero_max_hp is threaded
    through unchanged every round (no Paladin card raises it, unlike Cleric)."""
    card = CARDS[card_name]
    dmg, heal, block = card["dmg"], card["heal"], card["block"]

    new_strikes_played = state.strikes_played
    new_invocation_played = state.invocation_played
    new_active_invocation = state.active_invocation
    new_active_grants_aura_block = state.active_grants_aura_block

    if card["invocation"] is not None:
        if state.invocation_played:
            pass  # second Invocation played this pull: flat base dmg only, no retroactive bonus, does not become Active
        else:
            new_invocation_played = True
            new_active_invocation = card["invocation"]
            new_active_grants_aura_block = card["grants_aura_block"]
            if new_active_invocation == "sanctuary":
                dmg += INVOCATION_PER_STRIKE_BONUS * state.strikes_played
                if new_active_grants_aura_block:
                    block += INVOCATION_AURA_BLOCK_BONUS * state.strikes_played
            else:
                heal += INVOCATION_PER_STRIKE_BONUS * state.strikes_played

    if card["strike"]:
        new_strikes_played = state.strikes_played + 1
        if state.active_invocation == "sanctuary":
            dmg += INVOCATION_PER_STRIKE_BONUS
            if state.active_grants_aura_block:
                block += INVOCATION_AURA_BLOCK_BONUS
        elif state.active_invocation == "grace":
            heal += INVOCATION_PER_STRIKE_BONUS

    healed_hp = min(hero_max_hp, hero_hp + heal)

    mob_atk, mob_block = mob_pattern[round_num]
    dmg_dealt = max(0.0, dmg - mob_block)
    new_remaining = mob_hp_remaining - dmg_dealt

    dmg_taken = max(0.0, mob_atk - block)
    new_hp = healed_hp - dmg_taken

    new_state = replace(state, strikes_played=new_strikes_played,
                         invocation_played=new_invocation_played,
                         active_invocation=new_active_invocation,
                         active_grants_aura_block=new_active_grants_aura_block)
    return RoundOutcome(new_hp=new_hp, new_mob_hp_remaining=new_remaining, new_hero_max_hp=hero_max_hp,
                         new_state=new_state, dmg_dealt=dmg_dealt, dmg_taken=dmg_taken,
                         raw_dmg=dmg, block=block, heal=heal)


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=PALADIN_HP):
    state = RoundState()
    hp, remaining, max_hp = starting_hp, mob_hp, PALADIN_HP
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
