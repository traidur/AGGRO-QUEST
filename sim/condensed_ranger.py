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
equilibrium clean.

**Beast Bond: Wolf's base block, 0 -> 1 (2026-08-19), fixing the macro-loop risk-gate
outlier.** Root cause (see CLASS_BALANCE_GUIDE.md's "Rogue and Ranger's macro-loop risk
outlier"): Ranger's defense floor cracks a full HP-tier earlier than most of the roster,
entirely because Scout (the one ranged mob) voids grants_range-based evasion, leaving real
Block as the only defense that still works against it. Traced precisely, this real-HP number
(not a % checkpoint) was the actual mechanism: across 1000 traced trips, Ranger was forced to
eat its one starting Food at HP=4.58 on average, a full HP earlier than Paladin's 3.40 --
small-looking, but decisive, since both classes need that Food in essentially every trip
(1000/1000), so the whole game comes down to whether a *second* scare arrives before the trip
would have finished anyway. Confirmed this real-HP gap (not the risk policy's tolerance
values) was the actual driver by forcing Ranger's risk-gate decisions to run against Paladin's
own defense-floor curve while leaving Ranger's real combat unchanged: Gold barely moved
(+1.4) but deaths/run exploded 8x (0.167 -> 1.297) -- proof the caution was correctly reading
real danger, not an overly conservative policy setting.

The fix targets Beast Bond: Wolf specifically because its Block doesn't depend on
grants_range at all, so it works against Scout same as any other mob -- unlike
Withdrawing Hip Shot/Crippling Shot's evasion, which Scout nullifies outright. +2 total Block
was tried first (a new base value of 2, stacking with the existing +1/round persistent bonus)
and overcorrected badly -- Ranger swung past Paladin on every metric (Gold 26.2 vs Paladin's
23.8, deaths/run to 0.000, quests/trip 2.30 vs 2.16), evidence the buff was too strong, not
just a directional confirmation. **Locked at +1 base** (2 total Block the round it's played,
1/round after, persistent bonus itself untouched): Gold 22.6, quests/trip 2.11, both landing
just under Paladin rather than past it. Validated the residual gap is genuine class-flavor
variance, not a structural one: 35.3% of Ranger's 300 trial runs now beat Paladin's own
median (was 0.0% before this fix), and 27.7% of Paladin's runs fall below Ranger's median.

Notably, this fix does **not** close the single worst-case hand (`Withdrawing Hip Shot,
Beast's Challenge, Sure Shot, Crippling Shot` at HP=8 vs. Scout, still exactly 1/90 lethal
hand-mob pairs, unchanged) -- Beast Bond: Wolf isn't even in that hand. The large aggregate
improvement comes entirely from the ~67% of hands where Beast Bond: Wolf *is* drawn, compounded
over a full trip the same way small heal buffs compounded explosively elsewhere in this
project (Cleric's Heal, Paladin's Sacred Light) -- not from eliminating the worst case, just
from making everything else meaningfully safer around it. One known hidden-domination flag remains (Withdrawing
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

**Level 2 leveling infrastructure (2026-08-20):** `simulate()` gained an opt-in
`beast_block_value_decayed` field on Beast Bond: Wolf, read only if present -- lets a leveled
kit's persistent Block bonus step down starting two rounds after Wolf is played instead of
staying flat forever. Defaults to `beast_block_value` itself when absent, so the base Level 1
card (which has no such field) is untouched -- verified no-op (L1 win rate unchanged at
95.6%). Also gained an opt-in `armor_pierce` field (ignores the mob's own block value entirely
for that card's damage), added during a cross-class exploration prompted by Wizard's Fire Blast
finding -- swept against every card in this kit (Bullseye, Deadeye/Point Blank Shot, Withdrawing
Hip Shot, Crippling Shot, Beast Bond: Wolf) but none were locked; kept in the solver as validated
data points, not removed. See LEVELING_GUIDE.md's "Fifth class worked example: Ranger" and
"Sixth class worked example: Wizard" (the armor-pierce retrospective) for the full leveling
derivation and locked Level 2 upgrades (kept out of this module's own CARDS,
matching every other class -- leveled kits live in LEVELING_GUIDE.md as documented `leveled_kit`
swaps, not baked into the base file).
"""
import itertools
from dataclasses import replace

from combat_round import RoundState, RoundOutcome

RANGER_HP = 15

# aggro: co-op Party Pull targeting value (0-4), locked via direct user
# review -- see OPEN_QUESTIONS.md's "Co-op multi-hero vs. one Elite" entry.
CARDS = {
    "Beast Bond: Wolf":         dict(dmg=4, block=1, grants_range=False, beast_bond=True, beast_block_value=1,
                                      payoff_prev_range=False, aggro=2),
    "Withdrawing Hip Shot":     dict(dmg=2, block=0, grants_range=True, beast_bond=False, payoff_prev_range=False, aggro=2),
    "Sniper/Point Blank Shot":  dict(dmg=None, block=0, grants_range=False, beast_bond=False, payoff_prev_range=True,
                                      dmg_if_prev_range=7, dmg_else=5, aggro=3),
    "Beast's Challenge":        dict(dmg=None, block=0, grants_range=False, beast_bond=False, payoff_prev_range=False,
                                      payoff_wolf=True, dmg_if_wolf=5, dmg_else=2, aggro=3),
    "Sure Shot":                dict(dmg=4, block=0, grants_range=False, beast_bond=False, payoff_prev_range=False, aggro=2),
    "Crippling Shot":           dict(dmg=2, block=1, grants_range=True, beast_bond=False, payoff_prev_range=False, aggro=3),
}
DECK = list(CARDS.keys())

ALL_HANDS = list(itertools.combinations(DECK, 4))


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def resolve_round(state, card_name, stance, round_num, mob_pattern, mob_hp_total,
                   mob_hp_remaining, hero_hp, hero_max_hp):
    """The one place Ranger's card-effect logic lives. Faithful port of the real, current
    simulate() below. stance is unused (Ranger has none). hero_max_hp threaded through
    unchanged (no Ranger card raises it)."""
    card = CARDS[card_name]

    if card["payoff_prev_range"]:
        dmg = card["dmg_if_prev_range"] if state.prev_grants_range else card["dmg_else"]
    elif card.get("payoff_wolf"):
        dmg = card["dmg_if_wolf"] if state.beast_active else card["dmg_else"]
    else:
        dmg = card["dmg"]

    new_beast_active = state.beast_active
    new_rounds_since_beast = state.rounds_since_beast
    if card["beast_bond"]:
        new_beast_active = True  # activates starting this same round
        new_rounds_since_beast = 0
    elif state.rounds_since_beast is not None:
        new_rounds_since_beast = state.rounds_since_beast + 1

    if new_beast_active:
        wolf_card = CARDS["Beast Bond: Wolf"]
        # beast_block_value_decayed: optional -- lets the persistent bonus step down
        # starting two rounds after Wolf is played. Defaults to beast_block_value
        # itself when absent, so the original flat-forever card is untouched.
        if new_rounds_since_beast >= 2:
            beast_bonus = wolf_card.get("beast_block_value_decayed", wolf_card["beast_block_value"])
        else:
            beast_bonus = wolf_card["beast_block_value"]
    else:
        beast_bonus = 0
    block = card["block"] + beast_bonus

    mob_atk, mob_block, mob_type = mob_pattern[round_num]
    if card.get("armor_pierce"):
        dmg_dealt = dmg
    else:
        dmg_dealt = max(0.0, dmg - mob_block)
    new_remaining = mob_hp_remaining - dmg_dealt

    if card["grants_range"] and mob_type == "melee":
        dmg_taken = 0.0
    else:
        dmg_taken = max(0.0, mob_atk - block)
    new_hp = hero_hp - dmg_taken

    new_state = replace(state, beast_active=new_beast_active,
                         rounds_since_beast=new_rounds_since_beast,
                         prev_grants_range=card["grants_range"])
    return RoundOutcome(new_hp=new_hp, new_mob_hp_remaining=new_remaining, new_hero_max_hp=hero_max_hp,
                         new_state=new_state, dmg_dealt=dmg_dealt, dmg_taken=dmg_taken,
                         raw_dmg=dmg, block=block, heal=0.0)


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=RANGER_HP):
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
