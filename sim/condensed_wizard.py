"""
Exact solver for the condensed Wizard prototype.
Deck=6, hand=4, 3 rounds max -- same skeleton as condensed_warrior.py.
No stance system (Wizard never had one in the source kit). Two mechanics
instead: Positioning (At Range this round, evades a melee mob's attack,
does nothing vs ranged) and Weave (a single-use trigger: playing a Weave
card arms a bonus that the *next* eligible payoff card consumes -- it does
not stack or apply to a second payoff card).

**Level 2 leveling infrastructure (2026-08-20):** `simulate()` gained two opt-in fields, both
absent on every base card (verified no-op). `killing_blow` (Warrior's Execute pattern): if the
card's damage lands the kill this round, the mob's attack is prevented. Explored for Fire Blast
and rejected -- wildly overpowered for a mandatory slot (cost/pulls swings far exceeding entire
other classes' whole four-card stacked slates), kept in the solver as a validated dead end, not
removed. `armor_pierce` (new concept): the card's damage ignores the mob's own block value
entirely instead of `max(0, dmg - mob_block)`. Locked into Fire Blast's Level 2 upgrade (see
below). Leveled kits themselves live in LEVELING_GUIDE.md as documented `leveled_kit` swaps,
not baked into this module's own CARDS, matching every other class.

**Locked: Fire Blast, damage 3->4, gains `armor_pierce`, Block stays 0** (mandatory upgrade).
Kept purely offensive by explicit user call -- a Block bump doesn't fit a "blast" spell's
identity -- deferring cost/pulls recovery to a purchased upgrade on one of the kit's genuinely
defensive cards (Ice Barricade, Snap Freeze, Frozen Shot) instead.

**Locked: Fire Ball -> Fire Ball [Lv 2], damage flat 7 (was 5/7, weave-conditional), `payoff`
flipped to False** (first purchased upgrade). Was strictly dominated by Arcane Volley whenever
both were in hand (6/8 beats 5/7 on both faces), and only landed its own boosted value 30.4% of
the times it was actually played -- redesigned rather than bumped, dropping the Weave
dependency entirely instead of just raising its numbers. `payoff=False` (not True) specifically
so it no longer wastes an armed Weave bonus it doesn't need.

**Locked: Ice Barricade -> Ice Palisade, damage 0->1, Block unchanged at 10** (second purchased
upgrade). Block itself is a confirmed dead lever (max mob ATK anywhere is 6, already fully
absorbed by block=10, same finding as Rogue's Evasion) -- damage was the real lever, same
opportunity-cost shape as Evasion -> Evasion and Riposte. Chosen conservatively at dmg=1 over
dmg=2 (which flips win margin positive) to leave real headroom.

**Locked: Snap Freeze -> Deep Freeze, damage 1->2, Block 1->2** (third purchased upgrade). Block
alone turned out to be a weak, fast-saturating lever (only ever activates against Scout, same
reason it's near-dead on Ranger's Crippling Shot); damage was the real lever. Full rename since
both fields moved together, matching Ranger's Beast's Stand/Bullseye convention.

**Combined total (mandatory + all 3 purchased) overshoots Paladin's own final win-margin
reference (+2.1 vs. -0.7) -- left as-is by explicit user call, not re-tuned.** Every individual
card was conservative in isolation; the overshoot only appears once fully stacked. See
LEVELING_GUIDE.md's "Sixth class worked example: Wizard" for the full combined chart.

See LEVELING_GUIDE.md's "Sixth class worked example: Wizard" for the full diagnosis, mechanism
trace, and sweep data.

**2026-08-30 rebalance:** `worst_pair_round2_breadth` (see CLASS_BALANCE_GUIDE.md's "Fixing a
worst-pair round-2 shortcut" recipe) found Snap Freeze(weave_source)+Arcane Volley(payoff,
boosted dmg=8)=9 raw damage clearing 4 of 6 Standard mobs by round 2 -- Arcane Volley was the
common thread across the top 3 flagged pairs, since every one of the kit's three weave_source
cards (Fire Blast, Snap Freeze, Ice Barricade) can arm it. Unlike Paladin/Cleric/Ranger, this
wasn't a hidden interaction -- Weave is Wizard's real, signposted identity (`weave_source`/
`payoff` are named CARDS fields) -- so the fix specifically preserved the mechanic rather than
gutting it: only Arcane Volley's *boosted* value moved (8->7), its base damage (6) and every
weave_source card's own numbers stayed untouched (cutting the base value alone was tried first
and made things WORSE, not better -- it widened the gap the boost creates, making Snap
Freeze->Arcane Volley even more consistently correct). Worst-pair breadth 4/6->3/6.

That cut alone undershot the roster on chained-trip metrics -- caught by the newly-added
`FROZEN_BASELINE_2026_08_30` check specifically, not the live pack range (Wizard's own dip had
already become the live floor, so the live check trivially passed against itself). Every card
in this kit is either `weave_source` or `payoff` -- no card sits outside the mechanic the way
Paladin had Holy Fortress or Cleric had Sacred Light -- so the compensating buff went to Frozen
Shot's own boosted value (4->5) instead: the single losing hand (`Fire Blast, Snap Freeze, Ice
Barricade, Frozen Shot` -- three weave_source cards, only one payoff, wasting two of three arms)
had no Arcane Volley or Fire Ball at all, so buffing either of those couldn't have helped it.
Landed clean against both the live pack and the frozen baseline afterward; win rate actually
improved slightly over the original (Enforcer 93.3%->100%). Post-fix combo-dominance sweep
flags several weave_source->payoff pairs at high co-play -- expected and benign, they're all
explained directly by the shared `weave_source`/`payoff` fields, the same already-signposted
mechanic this whole fix was built around preserving.
"""
import itertools
from dataclasses import replace

from combat_round import RoundState, RoundOutcome

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
# left death counts completely unchanged. NOT because Wizard has only one
# way to fully answer a round -- grants_range (Snap Freeze, Frozen Shot)
# also zeroes a melee round entirely, same as Ice Barricade's block=10 does
# unconditionally, so the kit actually has three such cards. Re-checked
# directly (2026-08-20, separating genuine death (hp_left<=0 in the best
# available line) from flee (win=False but hp_left>0), since the two were
# being conflated): the real, much narrower mechanism is that a handful of
# specific hands draw only one of the three defensive-capable cards, and at
# very low starting HP (<=6, i.e. <=42.9% of WIZARD_HP) the other two
# exposed rounds' combined damage can still exceed it -- a hand-composition
# edge case, not a fixed one-card ceiling. Clears entirely by HP=7 (50%).
# Matches defense_floor_sweep's own documented 42.9% crack point exactly
# (CLASS_BALANCE_GUIDE.md), and that crack point is safer than Paladin's own
# locked 35.3% -- not a blocker for leveling or anything else. At
# the macro-loop level: Wizard's food_only Nothing-tier decay dropped from
# 32.6% to 28.2% and death rate from 0.39 to 0.31 per 20-trip run, landing
# it next to Cleric instead of standing alone as the clear worst class.
# aggro: co-op Party Pull targeting value (0-4), locked via direct user
# review -- see OPEN_QUESTIONS.md's "Co-op multi-hero vs. one Elite" entry.
# version: printed-card revision number, bumped only when a card's printed text/numbers
# change -- lets a physical deck owner tell which cards need reprinting. See
# CARD_REFERENCE.md's own note for the convention.
CARDS = {
    "Fire Blast": dict(combat_type="ranged",dmg=(3, 3), block=0,  grants_range=False, weave_source=True,  payoff=False, aggro=1, version=1),
    "Arcane Volley": dict(combat_type="ranged",dmg=(6, 7), block=0,  grants_range=False, weave_source=False, payoff=True, aggro=3, version=2),
    # Snap Freeze's block=1 (was 0) is deliberately silent against every
    # existing melee mob -- grants_range already zeroes melee damage
    # outright, so added block underneath it can never help there, and
    # every already-tuned melee number is unaffected by construction. It
    # only ever activates against a ranged mob, where grants_range
    # currently does nothing at all -- added specifically to give Wizard
    # partial recovery there without touching WIZARD_HP (explicitly ruled
    # out) or anything else already locked. See CLASS_BALANCE_GUIDE.md's
    # ranged-mob section for the before/after numbers.
    "Snap Freeze": dict(combat_type="melee",dmg=(1, 1), block=1,  grants_range=True,  weave_source=True,  payoff=False, aggro=3, version=1),
    "Ice Barricade": dict(combat_type="melee",dmg=(0, 0), block=10, grants_range=False, weave_source=True,  payoff=False, aggro=2, version=1),
    "Fire Ball": dict(combat_type="ranged",dmg=(5, 7), block=0,  grants_range=False, weave_source=False, payoff=True, aggro=3, version=1),
    "Frozen Shot": dict(combat_type="ranged",dmg=(2, 5), block=0,  grants_range=True,  weave_source=False, payoff=True, aggro=3, version=2),
}
DECK = list(CARDS.keys())

ALL_HANDS = list(itertools.combinations(DECK, 4))


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def resolve_round(state, card_name, stance, round_num, mob_pattern, mob_hp_total,
                   mob_hp_remaining, hero_hp, hero_max_hp):
    """The one place Wizard's card-effect logic lives. Faithful port of the real, current
    simulate() below (NOT playtest_engine.py's older _resolve_wizard_round, which predates the
    armor_pierce/killing_blow leveling fields added to CARDS since -- verified by direct
    comparison before porting, not assumed in sync). stance is unused (Wizard has none),
    kept for a uniform call signature across all 9 classes."""
    card = CARDS[card_name]

    use_boost = card["payoff"] and state.weave_armed
    dmg = card["dmg"][1] if use_boost else card["dmg"][0]
    block = card["block"]

    new_weave_armed = state.weave_armed
    if card["weave_source"]:
        new_weave_armed = True
    elif use_boost:
        new_weave_armed = False  # consumed

    mob_atk, mob_block, mob_type = mob_pattern[round_num]
    if card.get("armor_pierce"):
        dmg_dealt = dmg
    else:
        dmg_dealt = max(0.0, dmg - mob_block)
    new_remaining = mob_hp_remaining - dmg_dealt

    if card.get("killing_blow") and new_remaining <= 0:
        dmg_taken = 0.0
    elif card["grants_range"] and mob_type == "melee":
        dmg_taken = 0.0
    else:
        dmg_taken = max(0.0, mob_atk - block)
    new_hp = hero_hp - dmg_taken

    new_state = replace(state, weave_armed=new_weave_armed)
    return RoundOutcome(new_hp=new_hp, new_mob_hp_remaining=new_remaining, new_hero_max_hp=hero_max_hp,
                         new_state=new_state, dmg_dealt=dmg_dealt, dmg_taken=dmg_taken,
                         raw_dmg=dmg, block=block, heal=0.0)


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=WIZARD_HP):
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
