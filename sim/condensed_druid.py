"""
Exact solver for the condensed Druid prototype -- LOCKED. Kit designed directly by the user,
card by card, matching how Rogue/Ranger/Runecaster were each built (see
DECK_CONDENSING_GUIDE.md's checkpoint-discipline section).

Source: AGGRO's real Level-1 Druid kit (StS_WoW_Sim/data/cards.csv, class_name=druid, card_ids
701-709, cross-checked against StS_x_WoW_Classes_v7_4.md's rules text where the CSV's numeric
columns didn't capture an effect, e.g. Shapeshift: Grizzly's Block only appears in prose).
Druid is HP 14/14, Role: Striker in the source material, with two passives (Shapeshifting:
Forms, and Primal Attunement: guarantees a Form card in the opening hand) and a Weapon Lock
rule gating melee/staff equipment by Form.

**Cuts (Step 2 of DECK_CONDENSING_GUIDE.md):** Tanglevine (ROOT, no Zone/movement system to
apply it to); Primal Attunement (a hand-guarantee rule, no equivalent in this project's plain
draw-4-of-6); Weapon Lock (moot, no Equipment system yet, task #26); Bloom and the source's
separate Nature's Ward card (collapsed into Nature's Wildguard rather than cut, see below).

**The kit -- two mutually exclusive lines, by design:**
- **Shapeshift line** (Shapeshift: Grizzly, Maul, Swipe): Grizzly is 2 DMG/3 Block on its own
  and, if played in a **strictly earlier round** than Maul/Swipe this pull, gives them +1
  DMG/+1 Block. Order-dependent on purpose -- an earlier draft made this sequence-membership
  (order-irrelevant) and it created a "free lunch" line stacking Eclipse cards penalty-free
  before playing Grizzly last for its bonus anyway; corrected once traced directly.
- **Eclipse line** (Solar Flare, Moonbeam, Nature's Wildguard): Solar Flare and Moonbeam are
  5 DMG each, +1 DMG per *other* Eclipse-tagged card played in a strictly earlier round this
  pull (Nature's Wildguard counts toward this too, despite dealing no damage itself). Moonbeam
  also carries a flat +1 Heal. Nature's Wildguard (2 Heal/2 Block baseline) is itself
  Eclipse-tagged and gets +1 Heal per Eclipse card played before it, on top of its own
  contribution to that same count for cards after it.
- **The lines are mechanically exclusive, not just flavored differently: once Shapeshift:
  Grizzly has been played, any Eclipse-tagged card played in a later round gets zero
  Eclipse-stacking bonus** (`elif tag == "eclipse" and not grizzly_played_before` in
  `simulate()`). This was the fix for a real, measured problem -- see "What tuning found"
  below.

**HP settled at 15**, not the source's 14 -- explicit flavor call (user ruled out Druid reading
as caster-fragile-tier). Confirmed HP-independent numbers (win rate per mob, damage
floor/ceiling, flee-preference) hold identically regardless of which HP is chosen; only the
defense-floor table and chained-trip pacing are HP-sensitive, and both were re-validated at 15.

**What tuning found, worth generalizing:**
- **A card can be technically available and never actually get chosen — check play rate, not
  just presence.** The first full diagnostic pass found Shapeshift: Grizzly played in 60/60
  hand x mob pairs where it was drawn (100%), even after several rounds of buffing the Eclipse
  line's raw power. Buffing the *other* option doesn't create a decision if the buff is
  "blind" to which line it's helping -- Nature's Wildguard's heal-scaling helped Grizzly-
  inclusive hands exactly as much as Eclipse-only hands, since it only checks how many Eclipse
  cards came before it, not whether Grizzly is anywhere in the sequence. Making the lines
  mechanically exclusive (Grizzly cancels the Eclipse bonus for cards after it) was the lever
  that actually moved the number, from 60/60 down to 59/60 -- still not a large swing, but
  confirmed non-zero, and 3 further hand/mob pairs are exact (win, hp_left) ties resolved only
  by the solver's arbitrary first-found tie-break (`DECK` order puts Grizzly first, so
  Grizzly-inclusive sequences get enumerated before Grizzly-excluding ones) -- meaning the real
  count of genuine at-the-table decisions is closer to 4/60 than the raw stat suggests.
- **A shared card can't tip a comparison it appears on both sides of.** Two follow-up attempts
  to push the remaining ties toward the Eclipse line -- cutting Maul's Block further, buffing
  Moonbeam's Heal further -- both left the Grizzly/Eclipse split completely unchanged (still
  59/60) while damaging chained-trip pacing in opposite directions (Maul's cut pushed pulls/
  wins-per-pull below the pack floor; Moonbeam's buff pushed them above the ceiling and broke
  equilibrium outright on Grunt). Both cards appear in close-case sequences on *both* sides of
  the Grizzly/Eclipse comparison, so nudging either moves the whole kit's power level without
  changing the relative gap -- the same trap as the Wildguard buff above, just smaller in
  scale. Reverted both; not pursued further once this pattern repeated a second time.
- **Damage governs the full-HP win-rate ceiling; Block/Heal governs the low-HP defense floor
  -- confirmed via direct sensitivity sweep, not assumed.** At full HP, every card's -1 Block
  nudge tested flipped zero outcomes; every -1 DMG nudge flipped multiple pairs from win to
  timeout. At HP=1/2, the reverse: DMG nudges mostly produced more timeouts, while Block/Heal
  nudges (specifically Nature's Wildguard's) produced the most outright deaths. This directly
  shaped which lever got pulled for which problem -- Shapeshift: Grizzly's DMG (3->2) closed
  the Bruiser/Enforcer win-rate gap to the pack-typical 93.3%; its Block (4->3) pulled the
  best-in-roster low-HP defense floor back toward pack-normal without either one contaminating
  the other's fix.

**Validated at lock-in:** Win rate 93.3% (Bruiser, Enforcer) / 100% (Grunt, Raider, Ambusher,
Scout) -- same shape as most of the rest of the roster, no longer a 100%-everywhere outlier.
Damage floor/ceiling 9/14 (floor matches the pack's most common value exactly). Chained trip
(30,000-trial comparison): wins/trip 4.20 and wins/pull 74.7% both inside the pack range;
pulls-survived 5.62 vs. a pack ceiling of 5.60 -- a confirmed real but tiny 0.02-pull overshoot,
the smallest miss of any metric tested this session, left as-is rather than chased further.
Defense floor genuinely mid-pack across most HP values (still edges out the pack's best at
HP=2, no longer the extreme outlier of earlier passes). Equilibrium clean. Solar Flare/Moonbeam
no longer hidden-domination-flagged. Nature's Wildguard's unplayed rate 35.6%, down from a
42-56% range across earlier kit variants, though still the kit's most-skipped card.

**Not yet done:** Aggro values (placeholder 0 below except Grizzly's given 4) -- assigned per
this project's standard build order, after balance lock, not before.

**Fixed a real macro-loop underperformance, found via the same investigation that fixed
Rogue/Ranger (2026-08-19), but a genuinely different shape.** Druid sat dead last in the roster
on Gold-at-a-fixed-XP-checkpoint (18.5, vs. Paladin's 23.8). A forced-curve test (substituting
Paladin's own defense-floor lookup into Druid's risk-gate decisions while leaving its real
combat untouched) came back flat -- Gold was identical either way (18.5 exactly), while
deaths/run jumped 0.000 -> 0.700. That's a different signature from Rogue/Ranger's fix (which
both showed a small Gold gain alongside their death spike): it proves Druid's defense-floor
crack (HP=7 vs. Enforcer, both lethal hands missing Nature's Wildguard) is real and dangerous,
but is *not* the cause of the low Gold ranking -- the risk gate was never the bottleneck here.

Traced the real cause via segment-level tracing (pulls between Food-eats/town, matching the
same instrumentation built for Rogue/Ranger): Druid gets fewer pulls per segment than Paladin
(3.59 vs. 3.99) and wins slightly less often within them (96.5% vs. 97.3%) -- two modest gaps
compounding, not one sharp break. Traced further to the actual damage array: floor 9 (tied with
Paladin) but ceiling only 14 (vs. 15) and mean 11.60 (vs. 12.67) -- Druid's whole distribution
sits about a point lower across most hands, not just at the extremes. The specific driver: the
low-damage hand clusters (9/10/11) are dominated by three cards tied at 7-of-9 hands each
(Shapeshift: Grizzly, Maul, Swipe -- the entire Shapeshift line) plus Nature's Wildguard
(0 base damage, in 7-of-9) -- the Eclipse line (Solar Flare/Moonbeam, flat 5 base each) only
appears in 4-of-9. A genuine, structural power gap between the two lines, not one weak card.

**Locked: Shapeshift: Grizzly's bonus changed from a flat +1 DMG/+1 Block (triggered once
Grizzly has been played) to a stacking +1 DMG/+1 Block per Shapeshift-tagged card already
played this pull** (still gated on Grizzly having been played first, same as before -- only
the flat-vs-stacking shape changed). Verified via hand-trace: Grizzly -> Maul -> Swipe now
deals 2 + 3 + 5 = 10 total (was 2 + 3 + 4 = 9), since Swipe now benefits from *both* Grizzly and
Maul having gone before it, not just a fixed +1. Damage floor rose 9 -> 10, mean 11.60 -> 11.67,
stdev tightened 1.67 -> 1.58. Clean diagnostic throughout: equilibrium clear, no real
hidden-domination pairs. Gold-at-24XP 18.5 -> 20.6, quests/trip 1.91 -> 1.97, deaths/run held
at 0.000 -- climbed from dead last in the 9-class roster to 6th, ahead of Runecaster/Warrior/
Wizard, though still trailing Paladin/Rogue/Ranger/Necromancer/Cleric.

**Explicitly not fully closed, and correctly so** -- the defense-floor crack at HP=7 did not
move (still 3/90 lethal vs. Enforcer), because the new Block bonus only ever applies to
Shapeshift-tagged cards, and both lethal hands' actual death round lands on an Eclipse card
(Moonbeam or the missing Solar Flare), which never receives any Block from this mechanic by
design -- traced precisely: in `(Shapeshift: Grizzly, Swipe, Solar Flare, Moonbeam)` at HP=7
vs. Enforcer, the losing line's round-3 Moonbeam takes Enforcer's full 4 ATK unmitigated and
the hero dies the same instant the mob would have too (hero-death checked before mob-death in
`simulate()`, so an exact tie goes against the player). The fix closed the *offense* gap that
was actually driving Gold; the separate, still-open defense-floor gap was deliberately left
for a future pass rather than papered over with an unrelated lever.
"""
import itertools
from dataclasses import replace

from combat_round import RoundState, RoundOutcome

DRUID_HP = 15

# tag: "shapeshift" | "eclipse" | None. dmg/heal/block are flat base values before any
# Form-synergy modifier. aggro: co-op Party Pull targeting value -- NOT YET ASSIGNED except
# Shapeshift: Grizzly (given directly); every other card's 0 is a placeholder, not a real
# locked value, matching every other class's actual build order (aggro assigned after lock).
CARDS = {
    "Shapeshift: Grizzly": dict(combat_type="melee",dmg=2, heal=0, block=3, tag="shapeshift", aggro=4),
    "Maul": dict(combat_type="melee",dmg=2, heal=0, block=2, tag="shapeshift", aggro=0),
    "Swipe": dict(combat_type="melee",dmg=3, heal=0, block=0, tag="shapeshift", aggro=0),
    "Solar Flare": dict(combat_type="ranged",dmg=5, heal=0, block=0, tag="eclipse", aggro=0),
    "Moonbeam": dict(combat_type="ranged",dmg=5, heal=1, block=0, tag="eclipse", aggro=0),
    "Nature's Wildguard": dict(combat_type="melee",dmg=0, heal=2, block=2, tag="eclipse", aggro=0,
                                  heal_scales_with_eclipse=True),
}
DECK = list(CARDS.keys())

ALL_HANDS = list(itertools.combinations(DECK, 4))


def orderings(hand):
    return list(itertools.permutations(hand, 3))


def resolve_round(state, card_name, stance, round_num, mob_pattern, mob_hp_total,
                   mob_hp_remaining, hero_hp, hero_max_hp):
    """The one place Druid's card-effect logic lives. Faithful port of the real, current
    simulate() below -- note the two mutually-exclusive payoff branches (shapeshift bonus
    only while Grizzly has been played, eclipse bonus only while it HASN'T), flagged in this
    project's own plan as easy to invert by mistake; ported by direct copy of the real
    condition, not re-derived from memory. stance is unused (Druid has none). hero_max_hp
    threaded unchanged (healing caps at the class's own DRUID_HP constant, same pattern as
    Paladin/Runecaster, not Cleric's dynamic ceiling)."""
    card = CARDS[card_name]
    dmg, heal, block = card["dmg"], card["heal"], card["block"]
    tag = card["tag"]

    if tag == "shapeshift" and card_name != "Shapeshift: Grizzly" and state.grizzly_played_before:
        dmg += state.shapeshift_played_before
        block += state.shapeshift_played_before
    elif tag == "eclipse" and not state.grizzly_played_before:
        if card.get("heal_scales_with_eclipse"):
            heal += state.eclipse_played_before
        else:
            dmg += state.eclipse_played_before

    new_hp = min(hero_max_hp, hero_hp + heal)

    mob_atk, mob_block = mob_pattern[round_num]
    dmg_dealt = max(0.0, dmg - mob_block)
    new_remaining = mob_hp_remaining - dmg_dealt

    dmg_taken = max(0.0, mob_atk - block)
    new_hp -= dmg_taken

    new_shapeshift_played = state.shapeshift_played_before + (1 if tag == "shapeshift" else 0)
    new_eclipse_played = state.eclipse_played_before + (1 if tag == "eclipse" else 0)
    new_grizzly_played = state.grizzly_played_before or (card_name == "Shapeshift: Grizzly")

    new_state = replace(state, shapeshift_played_before=new_shapeshift_played,
                         eclipse_played_before=new_eclipse_played,
                         grizzly_played_before=new_grizzly_played)
    return RoundOutcome(new_hp=new_hp, new_mob_hp_remaining=new_remaining, new_hero_max_hp=hero_max_hp,
                         new_state=new_state, dmg_dealt=dmg_dealt, dmg_taken=dmg_taken,
                         raw_dmg=dmg, block=block, heal=heal)


def simulate(seq_cards, mob_pattern, mob_hp, starting_hp=DRUID_HP):
    state = RoundState()
    hp, remaining, max_hp = starting_hp, mob_hp, DRUID_HP
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


def best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=DRUID_HP):
    best = None
    for seq_cards in orderings(hand):
        win, hp_left, rounds = simulate(seq_cards, mob_pattern, mob_hp, starting_hp)
        key = (win, hp_left)
        if best is None or key > best[0]:
            best = (key, (seq_cards, hp_left, rounds))
    return best[1]


def win_rate(mob_pattern, mob_hp, verbose=False, starting_hp=None):
    if starting_hp is None:
        starting_hp = DRUID_HP
    wins = 0
    for hand in ALL_HANDS:
        seq_cards, hp_left, rounds = best_line_for_hand(hand, mob_pattern, mob_hp, starting_hp=starting_hp)
        win, _, _ = simulate(seq_cards, mob_pattern, mob_hp, starting_hp=starting_hp)
        if win:
            wins += 1
        elif verbose:
            print(f"  LOSS hand={hand} best_seq={seq_cards}")
    return wins / len(ALL_HANDS)
