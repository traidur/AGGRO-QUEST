"""
Exact solver for the condensed Necromancer prototype -- LOCKED, ninth class. Kit designed
directly by the user, card by card, checkpointed at every step (see
DECK_CONDENSING_GUIDE.md's checkpoint-discipline section), matching how Rogue/Ranger/
Runecaster/Druid were each built.

Source: AGGRO's real Level-1 Necromancer kit (StS_WoW_Sim/data/cards.csv, class_name=
necromancer, card_ids 801-811 minus 806/Death Coil, already cut at the source level --
confirmed via the rules doc's own note, not a data gap; cross-checked against
StS_x_WoW_Classes_v7_4.md's rules text). Necromancer is HP 10/10 in the source (the lowest of
any class pulled for this project), Role: Channeler, identity explicitly stated as three
pillars -- life drain (Soul Harvest), death afflictions that tick and accumulate (Sow, Blight),
and one bound Boneguard pet sustained by spending your own HP (Soul Offering).

**Cuts:**
- Grave Threat -- its only distinguishing clause ("drop all Threat... place 3 Threat tokens")
  is pure Threat-manipulation, the exact "no QUEST equivalent, cut not reworked" case
  DECK_CONDENSING_GUIDE.md's Step 2 describes. Stripped of that clause it's just a redundant,
  weaker Death Bolt.
- Dread (FEAR/mob-skips-its-turn) -- well-motivated as a card, but not one of the three
  stated identity pillars, and the one mechanic that would have needed genuinely new plumbing
  (nothing else in this codebase lets a card cancel a mob's attack as a standalone effect --
  Warrior's Execute and Rogue's killing-blow only prevent an attack as a side effect of
  already landing a killing blow). Its useful half (the evasion utility) survives anyway,
  folded into Sowing Dread below.
- Death Bolt -- the source's own note calls it "intentional thin filler" (the source's own
  Death Pact had a draw-acceleration effect that meant the real class cycled cards fast enough
  that a plain filler slot was deliberate); QUEST's own Death Pact no longer draws cards at
  all (see below), so that reasoning doesn't apply here, and the slot reads better spent
  elsewhere once Death Pact's HP-cost rider needed a home (see below).

**Collapses (Step 4):**
- **Summon Boneguard + Soul Offering -> Boneguard's Offering, one card.** Both source cards
  describe the same "Pet" template AGGRO's own Ranger Beast Bond: Wolf uses -- an HP-pool
  companion that redirects attacks, right down to sharing the source data's "standardized
  0-HP wording across all Pet cards" note. QUEST's own Wolf already discarded that literal
  mechanic once, replacing it with a flat persistent Block bonus instead -- there's no
  precedent here worth re-preserving. Since Wolf already owns "persistent, every round,
  recurring bonus," Boneguard's differentiation is duration, not mechanism: **Boneguard's
  Offering grants At Range for one round only** (reuses the existing grants_range mechanic,
  same move Runecaster's Call of the Glacier already made for its own flavor) -- a one-shot
  clutch save instead of Wolf's slow-build investment. A separate "top up the pet" action
  (what Soul Offering did in the source, over a much longer real encounter) isn't needed
  across a 3-round pull, so it didn't survive as its own card -- the slot went to Death
  Pact's HP-cost rider instead (see below).
- **Sow + Dread -> Sowing Dread, one card.** Sow's DOT half survives as flat, immediate
  damage (not a delayed tick -- confirmed directly with the user: the "(DOT)" tag exists
  purely so Reap can count it, it is not a second Echo-style split-timing card). Dread's
  evasion utility survives as the grants_range clause.
- **Reap reframed from "discard pending Affliction damage, deal it now" to a flat counter
  payoff** -- deals 3 DMG + 1 DMG per DOT-tagged card played in a strictly earlier round this
  pull (DOT-tagged cards: Sowing Dread, Blight). Same shape as Paladin's Invocation counting
  STRIKE cards, or Rogue's finisher curve -- much simpler to execute at the table than
  tracking per-card pending damage values, and confirmed there's no real mechanical conflict
  with Blight's Echo below: Blight's automatic next-round tick still fires on its own
  schedule regardless of whether Reap gets played too, since Reap only *counts* DOT cards
  now, it no longer *consumes* them.
- **Blight reframed as an Echo card** (Runecaster's Earth Strike Rune pattern, reused
  directly): 4 DMG the round it's played, +3 DMG automatically at the start of the *next*
  round, no card spent. Same boundary condition as Runecaster's Echo -- played in round 3,
  the echo simply never fires, nothing special to implement.
- **Death Blow's Exhaust clause dropped, replaced with a killing-blow rider** (Warrior's
  Execute / Rogue's Cutthroat pattern). AGGRO's "Exhaust" removes a card from the deck until
  an out-of-encounter reset -- QUEST's condensed combat has no persistent-across-pulls deck
  state at all (every pull redraws fresh), so there's no clean translation; dropping it
  outright and giving the card a different kind of payoff instead reads better than forcing
  a mechanic this format doesn't support.

**Death Pact, added as a rider rather than a new passive** -- deliberately NOT built as a
standalone ability outside the 6-card kit (no other class in this codebase has a passive, and
introducing one here would be inconsistent for no real gain). Lands on **Boneguard's
Offering** -- chosen over every other card specifically because it's the one card already
thematically about paying HP for the pact (Soul Offering's real source text was literally
"Spend 2 HP"), so a second HP-cost clause on the same card isn't a flavor stretch the way it
would be on Dread or Soul Harvest. Losing Boneguard's Offering's damage entirely to make room
for this also fixes something worth flagging directly: without this change the kit was 6-of-6
damage-capable, which would have been the first fully-offense kit in the roster (every other
locked class keeps at least one pure-support card) -- with the damage removed, it lands at
5-of-6, in line with Warrior/Wizard's ratio instead of being a new kind of outlier.

**Death Pact's mechanic, reworked once from the original draft -- see below for why.** The
name is unchanged throughout this class's whole history (deliberately kept -- see note below
on why "Life Tap" was rejected as a replacement name); only the rule under it changed. The
original draft: "before playing any card this pull, you may lose 2 HP to draw one of the two
undrawn deck cards into your hand, on the condition Boneguard's Offering gets played somewhere
this pull." That was the one mechanic in this entire codebase with genuine in-pull randomness
-- every other tool here (win_rate, damage_floor_ceiling, defense_floor_sweep, the whole
chained-trip machinery) depends on full-information, deterministic solving, so this original
draft required its own separate architecture entirely: `best_line_for_hand` correctly
excluded it (a coin-flip draw can't be part of a "certain" line), a dedicated
`draw_random_card` carried the real randomness inside the chained-trip Monte Carlo layer, and
a whole extra function (`effective_win_rate`) existed solely to show what raw `win_rate`
couldn't see. **Reworked directly at the user's request** -- raised independently as unwanted
complexity: "knowledge debt" (the one card in the game that worked on a fundamentally
different rule than every other card) and "simulation debt" (the one class needing its own
separate solver path, tooling, and doc caveats). The theme survives intact (a Necromancer
trading HP for power, still genuinely unique in this roster -- no other class has an optional,
in-the-moment, resource-for-effect trade with no setup or counter required); only the
mechanism changed. ("Life Tap" was used as a working name for this rework mid-session and is
retired -- it's AGGRO/WoW source terminology already spoken for elsewhere, not a fresh name
this project should claim. The card and its rider are both "Death Pact," full stop, before and
after the rework.)

**Current version: Boneguard's Offering may lose 4 HP to deal 3 extra damage, fully
deterministic, resolved the moment the card is played -- no draw, no hidden information, no
separate architecture.** Implemented as a second, virtual card variant
(`BONEGUARD_OFFERING_BOOSTED`) with the same block/grants_range as the base card but
different dmg/heal, added to `orderings()` alongside the base version whenever Boneguard's
Offering is in the hand -- exactly the same shape Warrior's Guardian/Champion stance duality
already uses. `best_line_for_hand` picks whichever variant is actually better automatically;
no special-casing needed anywhere else in this file or in `condensed_trip.py`.

**Numbers, derived directly rather than guessed:** a sweep of every (cost, bonus) pair from
(1,2) to (5,8) at full starting HP found the damage bonus is the only lever that matters for
single-pull win rate -- cost 1-5 all produced identical win rates for a given bonus, since
none of the class's two known-weak matchups (Bruiser, Enforcer) are HP-starved, only
damage-starved. Bonus=3 exactly reproduces the 93.3% the original draft's draw-adjusted rate
already landed on (the same validated target, not a step up in power); bonus=4 overshoots to
100%, stronger than the class was ever tuned to be. Cost was then found from the chained-trip
picture instead, where HP actually carries across pulls and compounds: cost 1-3 push every
chained-trip metric out of the pack's range (too strong across a full run), cost=5 sits with
comfortable margin under the pack's ceiling, cost=4 lands right at the pack's current maximum
(tied with Druid on pulls survived) with zero margin -- both are legitimately in-range, and
cost=4 was chosen deliberately over cost=5 for how it reads at the table (4-for-3 is a
cleaner, less punishing-looking trade than 5-for-3), accepting the tighter margin as the
tradeoff.

**Two things checked directly, not assumed, before locking this in:**
- **Does the boost let a fight end a round early (skip round 3 entirely), which would be a
  bigger effect than a simple win/loss flip?** No. Across every hand/mob pair where the
  normal, unboosted line already takes the full 3 rounds, the boost never lets the fight end
  in round 2 *and* come out ahead -- filtering to cases where the boosted card is actually
  played (not just sitting unused in a round-3 slot that never resolves because the fight
  already ended), every genuine case is strictly worse than playing the full 3 rounds, at
  both cost=4 and cost=5, with zero exceptions (0 better, 0 tied, 14 worse each). An earlier
  pass of this same check mistakenly reported some "tied" cases -- those turned out to be an
  artifact of the boosted card sitting in an unreached round-3 slot, contributing nothing,
  not genuine neutral trades; corrected before this was written down.
- **Does the boost get used meaningfully, not just decoratively or dominantly?** The solver
  picks the boosted variant in 3 of 60 hand/mob pairs containing Boneguard's Offering (at
  cost=4) -- a real, occasionally-decisive choice (it's what flips the previously-losing
  Death Blow hand into a win on Bruiser/Enforcer), not something that's either never worth
  taking or worth taking everywhere.

**Locked, validated:** `NECROMANCER_HP = 14`. Win rate 100% (Grunt, Raider, Ambusher,
Scout), 93.3% (Bruiser, Enforcer) -- one real number now, matching what the original draft's
draw-adjusted rate already achieved, no raw/adjusted split needed. Chained trip: pulls~5.68,
wins/trip~4.31, wins/pull~75.9%, all three inside the pack's range (5.13-5.68 / 3.84-4.33 /
74.1-78.3%), pulls sitting at the pack's current maximum by deliberate choice (see above).
macro_sim.py compatibility confirmed via `run_one_trip`.

**Not yet done:** Aggro values (all placeholder 0) -- assigned after balance lock per this
project's standard build order, not before.
"""
import itertools
from dataclasses import replace

from combat_round import RoundState, RoundOutcome

NECROMANCER_HP = 14

BONEGUARD_OFFERING = "Boneguard's Offering"

# dmg/heal/block are flat base values. grants_range evades a melee mob's attack this round
# (mob_type read the same way Wizard/Rogue/Ranger/Runecaster already do it). dot=True marks
# a card Reap's dot_payoff counts. dot_payoff=True (Reap only) means +1 dmg per dot-tagged
# card played in a strictly earlier round this pull. echo_dmg fires automatically at the
# start of the next round, no card spent (Blight only). killing_blow prevents the mob's
# attack this round if this card's damage brings it to <=0 (Death Blow only).
# aggro: co-op Party Pull targeting value (0-4) -- NOT YET ASSIGNED, placeholder 0 throughout,
# matching every other class's actual build order (aggro comes after balance lock).
BONEGUARD_OFFERING_BOOSTED = "Boneguard's Offering (Boosted)"  # virtual variant, see module docstring

CARDS = {
    BONEGUARD_OFFERING: dict(dmg=0, heal=0, block=2, grants_range=True, dot=False,
                              dot_payoff=False, echo_dmg=0, killing_blow=False, aggro=0),
    "Soul Harvest":      dict(dmg=3, heal=2, block=0, grants_range=False, dot=False,
                               dot_payoff=False, echo_dmg=0, killing_blow=False, aggro=0),
    "Sowing Dread":      dict(dmg=2, heal=0, block=0, grants_range=True, dot=True,
                               dot_payoff=False, echo_dmg=0, killing_blow=False, aggro=0),
    "Reap":              dict(dmg=3, heal=0, block=0, grants_range=False, dot=False,
                               dot_payoff=True, echo_dmg=0, killing_blow=False, aggro=0),
    "Blight":            dict(dmg=3, heal=0, block=0, grants_range=False, dot=True,
                               dot_payoff=False, echo_dmg=3, killing_blow=False, aggro=0),
    "Death Blow":        dict(dmg=4, heal=0, block=0, grants_range=False, dot=False,
                               dot_payoff=False, echo_dmg=0, killing_blow=True, aggro=0),
}
DECK = list(CARDS.keys())
ALL_HANDS = list(itertools.combinations(DECK, 4))

# Added after DECK/ALL_HANDS are built from the real 6 -- never itself drawable as a hand
# card. Deterministic rider on Boneguard's Offering: "may lose X HP to deal Y extra damage,"
# fully known on both sides of the trade, so it needs zero special-casing in the solver --
# it's just a second version of the same card with different dmg/heal, exactly like Warrior's
# stance duality already works. Locked: 4 HP for 3 damage -- see module docstring.
HP_FOR_DMG_COST = 4
HP_FOR_DMG_BONUS = 3
CARDS[BONEGUARD_OFFERING_BOOSTED] = dict(CARDS[BONEGUARD_OFFERING])
CARDS[BONEGUARD_OFFERING_BOOSTED]["dmg"] = HP_FOR_DMG_BONUS
CARDS[BONEGUARD_OFFERING_BOOSTED]["heal"] = -HP_FOR_DMG_COST


def orderings(hand):
    """All 3-card sequences for a hand -- if Boneguard's Offering is present, also includes
    every sequence with it swapped for its boosted variant, so best_line_for_hand picks
    whichever is actually better automatically, same as it already does for any other choice
    (e.g. Warrior's Guardian/Champion). No separate search path needed, unlike Death Pact's
    original draft."""
    base = list(itertools.permutations(hand, 3))
    if BONEGUARD_OFFERING not in hand:
        return base
    boosted = []
    for seq in base:
        if BONEGUARD_OFFERING in seq:
            idx = seq.index(BONEGUARD_OFFERING)
            boosted.append(seq[:idx] + (BONEGUARD_OFFERING_BOOSTED,) + seq[idx + 1:])
    return base + boosted


def resolve_round(state, card_name, stance, round_num, mob_pattern, mob_hp_total,
                   mob_hp_remaining, hero_hp, hero_max_hp):
    """The one place Necromancer's card-effect logic lives. Faithful port of the real,
    current simulate() below -- Blight's echo resolves at the START of this round (from
    state.nc_pending_echo_dmg, set by the PREVIOUS round's card), before this round's own
    card's effects apply, same ordering Runecaster's echo already established. stance is
    unused (Necromancer has none). hero_max_hp threaded unchanged (healing caps at the
    class's own NECROMANCER_HP constant, same pattern as Paladin/Runecaster/Druid)."""
    card = CARDS[card_name]
    mob_atk, mob_block, mob_type = mob_pattern[round_num]

    new_remaining = mob_hp_remaining
    if state.nc_pending_echo_dmg:
        new_remaining -= max(0.0, state.nc_pending_echo_dmg - mob_block)

    dmg, heal, block = card["dmg"], card["heal"], card["block"]
    if card["dot_payoff"]:
        dmg += state.dot_played_before

    new_hp = min(hero_max_hp, hero_hp + heal)

    dmg_dealt = max(0.0, dmg - mob_block)
    new_remaining -= dmg_dealt

    if card["killing_blow"] and new_remaining <= 0:
        dmg_taken = 0.0
    elif card["grants_range"] and mob_type == "melee":
        dmg_taken = 0.0
    else:
        dmg_taken = max(0.0, mob_atk - block)
    new_hp -= dmg_taken

    new_dot_played = state.dot_played_before + (1 if card["dot"] else 0)
    new_state = replace(state, dot_played_before=new_dot_played,
                         nc_pending_echo_dmg=card["echo_dmg"])
    return RoundOutcome(new_hp=new_hp, new_mob_hp_remaining=new_remaining, new_hero_max_hp=hero_max_hp,
                         new_state=new_state, dmg_dealt=dmg_dealt, dmg_taken=dmg_taken,
                         raw_dmg=dmg, block=block, heal=heal)


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=NECROMANCER_HP):
    state = RoundState()
    hp, remaining, max_hp = starting_hp, mob_hp, NECROMANCER_HP
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


def best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=NECROMANCER_HP):
    """The exact, deterministic solver -- matches every other class's shape exactly, no RNG
    in outcomes, no special-casing needed. Boneguard's Offering's HP-for-damage rider is
    fully deterministic (see orderings()), so it's automatically considered here like any
    other choice -- no separate tool or excluded-mechanic caveat required."""
    best = None
    for seq_cards in orderings(hand):
        win, hp_left, rounds = simulate(seq_cards, mob_pattern, mob_hp, starting_hp)
        key = (win, hp_left)
        if best is None or key > best[0]:
            best = (key, (seq_cards, hp_left, rounds))
    return best[1]


def win_rate(mob_pattern, mob_hp, verbose=False, starting_hp=None):
    if starting_hp is None:
        starting_hp = NECROMANCER_HP
    wins = 0
    for hand in ALL_HANDS:
        seq_cards, hp_left, rounds = best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=starting_hp)
        win, _, _ = simulate(seq_cards, mob_pattern, mob_hp, starting_hp=starting_hp)
        if win:
            wins += 1
        elif verbose:
            print(f"  LOSS hand={hand} best_seq={seq_cards}")
    return wins / len(ALL_HANDS)
