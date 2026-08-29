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
from dataclasses import replace

from combat_round import RoundState, RoundOutcome

PALADIN_HP = 17  # locked: settled at Warrior-1 after the Sacred Light/HP dial-back pass

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
CARDS = {
    "Might of the Aegis": dict(combat_type="melee",dmg=4, heal=0, block=2, strike=True,  invocation=None, aggro=4, grants_aura_block=False),
    "Bastion's Hammer": dict(combat_type="melee",dmg=6, heal=0, block=0, strike=True,  invocation=None, aggro=2, grants_aura_block=False),
    "Sacred Light": dict(combat_type="ranged",dmg=0, heal=3, block=0, strike=False, invocation=None, aggro=2, grants_aura_block=False),
    "Holy Fortress": dict(combat_type="melee",dmg=2, heal=0, block=4, strike=False, invocation=None, aggro=4, grants_aura_block=False),
    "Invocation of Sanctuary": dict(combat_type="ranged",dmg=3, heal=0, block=0, strike=False, invocation="sanctuary", aggro=3, grants_aura_block=False),
    "Invocation of Grace": dict(combat_type="ranged",dmg=4, heal=0, block=0, strike=False, invocation="grace", aggro=3, grants_aura_block=False),
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
                dmg += state.strikes_played
                if new_active_grants_aura_block:
                    block += state.strikes_played
            else:
                heal += state.strikes_played

    if card["strike"]:
        new_strikes_played = state.strikes_played + 1
        if state.active_invocation == "sanctuary":
            dmg += 1
            if state.active_grants_aura_block:
                block += 1
        elif state.active_invocation == "grace":
            heal += 1

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
