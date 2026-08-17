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
- Death Bolt -- the source's own note calls it "intentional thin filler" (Death Pact's draw
  acceleration meant the real class cycles cards fast enough that a plain filler slot was
  deliberate); with Death Pact itself not carrying over, that reasoning doesn't apply here,
  and the slot reads better spent elsewhere once Life Tap needed a home (see below).

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
  across a 3-round pull, so it didn't survive as its own card -- the slot went to Life Tap
  instead (see below).
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

**Life Tap, added as a rider rather than a new passive** -- deliberately NOT built as a
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

**Death Pact, the final mechanic (reworked once from an earlier draft -- see below for why):**
"Before playing any card this pull, you may lose 2 HP to draw one of the two cards not
currently in your hand into your hand. If you do, Boneguard's Offering must be one of the
three cards you play this pull (any round, any order)." The choice and the 2 HP cost both
happen up front, before round 1 -- not tied to when Boneguard's Offering itself gets played.
The only ongoing constraint from committing to it is that Boneguard's Offering has to be
among the three cards actually played that pull; everything else about sequencing (which
round it lands in, which round the drawn card lands in) is completely free.

**This is a genuinely new mechanic shape for this codebase, worth explaining precisely, and
it went through a real design correction mid-build.** Every existing tool here (win_rate,
damage_floor_ceiling, defense_floor_sweep, the whole chained-trip machinery) depends on
full-information, deterministic solving -- enumerate every possible hand, assume optimal
play, no dice anywhere except which 4-of-6 hand gets drawn. Drawing a card changes *what's
available to sequence*, not just a card's own dmg/heal/block values, which no other mechanic
in this codebase needed to do. The split adopted to handle this: `best_line_for_hand` (the
exact, deterministic solver every tool above is built on) never considers the draw at all --
correctly, since a coin-flip outcome can't be part of a "certain" line. The draw only exists
as genuine randomness inside the chained-trip Monte Carlo simulation (`draw_random_card`,
called from `run_trip_necromancer`), which already works by rolling real dice for hand/mob
draws, so this is the one place in-pull randomness can live without disturbing anything else.

**The first version of Death Pact tied the draw to playing Boneguard's Offering first, and
that turned out to be a real, measured mistake, not just a simplification.** It required
Boneguard's Offering to be played *before* the drawn card, which could then only fill a
*later* round. Measured directly: across the two hand/mob cases that first exposed a 0%
flip-to-win rate, drawing Blight could never rescue them under that rule -- but if Blight
were simply in the hand from the start (no draw involved), the winning line plays it
*first*, landing its own Echo tick in the same round as a second attacker's payoff. Freeing
the ordering entirely (any 3-of-5, Boneguard's Offering mandatory, no round restriction)
fixed this precisely: the same case that was previously unrescuable is now a clean win when
Blight comes up. Confirmed exhaustively for every hand this affects, not just the one case
that surfaced it -- see `effective_win_rate` below.

**The gamble policy also went through a real correction, not just the draw's shape.** An
earlier version gambled unconditionally whenever the deterministic line wasn't already
winning. Measured directly on 3000 chained trips: 65% of all gambles were being taken at
hero HP<=3, where the flat 2 HP cost alone is often close to fatal regardless of what gets
drawn, and the flip-to-win rate across ~2600 real gambles was under 1%. The fix: gamble only
if (1) the deterministic line doesn't win, AND (2) the WORSE of the two possible drawn
cards' full simulated outcome still keeps the hero alive. This alone raised the flip rate
from 0.8% to 2.0% and moved every chained-trip number closer to the rest of the roster,
before the ordering fix above closed the remaining gap.

**`effective_win_rate` exists specifically so this doesn't get lost as a one-off finding.**
Raw `win_rate` (used by every other diagnostic tool and printed first in every comparison)
is correctly blind to the draw, which makes Necromancer read as a real outlier below the
rest of the roster on Bruiser/Enforcer (86.7% vs. the pack-typical 93.3%) even though the
actual, played-out-at-the-table number already matches the pack exactly once the draw is
accounted for. `tuning_report`'s "win rate per mob" section now prints both numbers
automatically for any class exposing this function (see `condensed_trip.py`), so this
doesn't require a special script to rediscover every time the cards change.

**Known, accepted limitation:** neither `win_rate` nor any of the exact/deterministic tools
built on `best_line_for_hand` factor in the draw at all (by design -- see above). Only
`effective_win_rate` and the chained-trip numbers reflect it. Any future card change should
re-run `effective_win_rate` directly rather than assume the raw win_rate gap is the real
story, the same way it wasn't here.

**Locked, validated:** `NECROMANCER_HP = 14`. Damage floor/ceiling 9/14, matching the pack's
normal band on both ends. Win rate 100% (Grunt, Raider, Ambusher, Scout), 86.7% raw / 93.3%
draw-adjusted (Bruiser, Enforcer) -- the draw-adjusted number is what actually matches the
rest of the roster's pack-typical 93.3%. Defense floor strong across the board, best-in-
roster (0/90) at HP=6 and HP=7. Equilibrium clean. No hidden-domination flags. Chained trip:
pulls=5.56, wins/trip=4.21, wins/pull=75.7%, all three inside the pack's range (5.12-5.68 /
3.83-4.34 / 73.9-78.4%). macro_sim.py compatibility confirmed via `run_one_trip`.

**Not yet done:** Aggro values (all placeholder 0) -- assigned after balance lock per this
project's standard build order, not before.
"""
import itertools

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


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=NECROMANCER_HP):
    hp = starting_hp
    remaining_mob_hp = mob_hp
    dot_played_before = 0
    pending_echo_dmg = 0

    for rnd in range(3):
        card_name = seq_cards[rnd]
        card = CARDS[card_name]
        mob_atk, mob_block, mob_type = mob_pattern[rnd]

        # Blight's echo from last round -- resolves before this round's own card, reduced
        # by this round's mob Block same as any other damage source.
        if pending_echo_dmg:
            remaining_mob_hp -= max(0.0, pending_echo_dmg - mob_block)
        pending_echo_dmg = 0

        dmg, heal, block = card["dmg"], card["heal"], card["block"]
        if card["dot_payoff"]:
            dmg += dot_played_before

        hp = min(NECROMANCER_HP, hp + heal)

        dmg_dealt = max(0.0, dmg - mob_block)
        remaining_mob_hp -= dmg_dealt

        if card["killing_blow"] and remaining_mob_hp <= 0:
            dmg_taken = 0.0
        elif card["grants_range"] and mob_type == "melee":
            dmg_taken = 0.0
        else:
            dmg_taken = max(0.0, mob_atk - block)
        hp -= dmg_taken

        if card["dot"]:
            dot_played_before += 1
        pending_echo_dmg = card["echo_dmg"]

        if hp <= 0:
            return False, hp, rnd + 1
        if remaining_mob_hp <= 0:
            return True, hp, rnd + 1
    return False, hp, 3


def best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=NECROMANCER_HP):
    """The exact, deterministic solver -- matches every other class's shape exactly, no RNG
    in outcomes. Does NOT consider Boneguard's Offering's draw option: since which of the 2
    non-hand cards comes up is genuinely random (see draw_random_card below), there is no
    single "certain best line" for a hand that uses it, so it's correctly excluded from every
    tool built on top of this function (win_rate, damage_distribution, flee_preference,
    defense_floor_sweep, equilibrium checks, etc.) -- those all answer "what can this hand
    achieve with certainty," and a coin-flip draw can't be part of a certain plan."""
    best = None
    for seq_cards in orderings(hand):
        win, hp_left, rounds = simulate(seq_cards, mob_pattern, mob_hp, starting_hp)
        key = (win, hp_left)
        if best is None or key > best[0]:
            best = (key, (seq_cards, hp_left, rounds))
    return best[1]


def _best_outcome_with_drawn_card(hand, drawn_card, mob_pattern, mob_hp, starting_hp):
    """Best (win, hp_left) achievable once a specific card has been drawn: a free choice of
    any 3 of the resulting 5-card pool (the original hand plus the drawn card), in any order,
    with the one constraint that Boneguard's Offering must be among the three played -- that
    is the entire cost of having committed to Death Pact, not a round restriction (see
    draw_random_card's docstring for why the mechanic was reworked away from "the drawn card
    can only fill a round after Boneguard's Offering"). The 2 HP cost itself isn't handled
    here at all -- the caller bakes it into starting_hp before calling, since it's paid the
    moment the draw is committed to, before any round resolves."""
    pool = list(hand) + [drawn_card]
    best = None
    for combo in itertools.combinations(pool, 3):
        if BONEGUARD_OFFERING not in combo:
            continue
        for seq_cards in itertools.permutations(combo, 3):
            win, hp_left, rounds = simulate(seq_cards, mob_pattern, mob_hp, starting_hp)
            key = (win, hp_left)
            if best is None or key > best[0]:
                best = (key, seq_cards)
    return best


def draw_random_card(hand, seq_cards, win, hp_left, mob_pattern, mob_hp, starting_hp, rng):
    """Chained-trip-only: the genuinely random counterpart to Boneguard's Offering's Death
    Pact option, using that trip's own rng rather than exhaustive enumeration -- this is the
    one place in this class in-pull randomness actually lives (see best_line_for_hand's
    docstring).

    Mechanic (reworked from an earlier version -- see CLASS_BALANCE_GUIDE.md's Necromancer
    tuning notes): committing to the draw is a pre-round decision, not tied to playing
    Boneguard's Offering first. The 2 HP cost is paid immediately, the moment the draw is
    committed to, before any round resolves. The only ongoing constraint is that Boneguard's
    Offering must end up among the 3 cards actually played this pull -- which round, and
    which round the drawn card lands in, are both completely free. The original version tied
    the draw to playing Boneguard's Offering *first* and only let the drawn card fill a round
    *after* it, which meant a card like Blight (whose Echo wants to land early so its
    automatic next-round tick has somewhere useful to land) could never reach its own best
    line even when drawn -- confirmed directly: the exact hand/mob case that first exposed
    the 0% flip rate becomes a clean win once Blight is free to lead the sequence instead of
    being forced into round 2 or later.

    Policy: gamble only if (1) the deterministic line doesn't already win, AND (2) the WORSE
    of the two possible drawn cards' full simulated outcome (at starting_hp - 2, matching the
    flat upfront cost) still keeps the hero alive. Never gamble a HP total the worse draw
    would kill outright.
    """
    if win or BONEGUARD_OFFERING not in hand:
        return win, hp_left
    if starting_hp - 2 <= 0:
        return win, hp_left  # can't even survive the flat cost -- don't bother

    non_hand = [c for c in DECK if c not in hand]
    gambled_hp = starting_hp - 2

    worst_of_both = None
    for candidate_card in non_hand:
        (candidate_win, candidate_hp_left), _ = _best_outcome_with_drawn_card(
            hand, candidate_card, mob_pattern, mob_hp, gambled_hp)
        key = (candidate_win, candidate_hp_left)
        if worst_of_both is None or key < worst_of_both:
            worst_of_both = key
    if worst_of_both[1] <= 0:
        return win, hp_left  # even the worse possible draw would kill -- don't gamble

    drawn_card = rng.choice(non_hand)
    (result_win, result_hp_left), _ = _best_outcome_with_drawn_card(
        hand, drawn_card, mob_pattern, mob_hp, gambled_hp)
    return result_win, result_hp_left


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


def effective_win_rate(mob_pattern, mob_hp, starting_hp=None):
    """win_rate's real-play counterpart -- accounts for Boneguard's Offering's Death Pact
    option, deliberately excluded from win_rate/best_line_for_hand since a random draw can't
    be part of a "certain" line (see best_line_for_hand's docstring). Exists specifically so
    this doesn't get lost as a one-off finding: raw win_rate alone made Necromancer read as a
    real outlier below the rest of the roster (86.7% on Bruiser/Enforcer vs. the pack-typical
    93.3%), when the actual, played-out-at-the-table number already matches the pack exactly
    once the draw is accounted for -- both of Bruiser's and both of Enforcer's losing hands
    turn out to be rescued by a real 50% chance of drawing Blight, landing at 14/15 = 93.3%
    for both. See tuning_report's "win rate per mob" output, which prints this alongside the
    raw number automatically for any class exposing this function.

    For each hand: a deterministic win counts as a full 1.0. A deterministic loss with
    Boneguard's Offering in hand counts as the fraction of the 2 possible draws that would
    turn it into a win (0.0, 0.5, or 1.0) -- matching draw_random_card's real mechanic exactly
    (the 2 HP cost baked into starting_hp before checking, any 3-of-5 combo including
    Boneguard's Offering, in any order). A deterministic loss without Boneguard's Offering in
    hand has no draw option available at all and counts as 0.0, same as raw win_rate."""
    if starting_hp is None:
        starting_hp = NECROMANCER_HP
    total = 0.0
    for hand in ALL_HANDS:
        seq_cards, hp_left, rounds = best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=starting_hp)
        win, _, _ = simulate(seq_cards, mob_pattern, mob_hp, starting_hp=starting_hp)
        if win:
            total += 1.0
            continue
        if BONEGUARD_OFFERING not in hand or starting_hp - 2 <= 0:
            continue  # no draw available, or can't survive the flat cost -- stays a loss
        non_hand = [c for c in DECK if c not in hand]
        gambled_hp = starting_hp - 2
        wins_among_draws = 0
        for candidate_card in non_hand:
            (candidate_win, _), _ = _best_outcome_with_drawn_card(
                hand, candidate_card, mob_pattern, mob_hp, gambled_hp)
            if candidate_win:
                wins_among_draws += 1
        total += wins_among_draws / len(non_hand)
    return total / len(ALL_HANDS)
