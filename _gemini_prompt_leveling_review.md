# QUEST — Level 2 hero upgrades, 6 of 9 classes, for review

## What QUEST is

QUEST is a board game prequel to a game called AGGRO. Each hero class has a fixed 6-card
combat deck. In a "pull" (one combat encounter), the hero draws a 4-card hand from that deck,
picks 3 to play across 3 rounds against a mob, and the mob has its own fixed 3-round attack
pattern (damage + block value per round, sometimes a mob type of melee or ranged). Heroes deal
damage to reduce the mob's HP to 0 (a win); mobs deal damage to reduce the hero's HP to 0 (a
loss/death); if neither happens within 3 rounds it's a flee.

At Level 1, heroes fight a "Standard" tier of 6 mobs. At Level 2, the mob pool gets harder: the
same 6 Standard mobs, plus 3 new "Elite" mobs, weighted 3:1 (i.e. drawn 18:3, matching how many
physical copies of each mob's card exist in the deck).

This project is now giving each class a Level 2 upgrade slate: reaching Level 2 grants exactly
one **free (mandatory)** card upgrade, plus access to buy up to **3 additional (purchased)**
card upgrades at a trainer, using in-game gold. A card upgrade is always a same-shape swap — one
existing card in the 6-card kit gets its numbers (and sometimes a small mechanic) changed; the
deck size never grows.

## The methodology used to derive each upgrade

**Three metrics, three different questions**, all measured by running every possible hand
against the real, weighted mob pool for a given level:
- **cost%** = average % of max HP lost per pull (how risky is a single fight)
- **win%** = % of hands that actually kill the mob within 3 rounds (offensive output)
- **pulls-before-death** = Monte Carlo average of how many chained pulls (HP carrying forward
  pull-to-pull) a hero survives before dying, drawn from the level-appropriate mob pool

For each class, we compute a **margin** for each metric: `L1_baseline - L2_with_upgrades` for
cost (positive = good, means upgraded L2 performance is at least as safe as the original L1
kit was against easier content), and `L2_with_upgrades - L1_baseline` for win% and pulls
(positive = good, same direction convention).

**The core design rule:** the free mandatory upgrade must NOT by itself fully close both the
cost margin and the win margin — it should leave real, deliberate headroom so the paid,
purchased upgrades still have meaningful work to do. Every class's mandatory upgrade was
checked against this rule and deliberately kept short of fully closing both gaps alone.

**Diagnostic tool used to find upgrade candidates:** for every hand, find the single best-play
card ordering (maximizing win, then HP remaining). A card is "genuinely unplayed" for that
hand+mob pairing only if EVERY tied best ordering excludes it (ties are thrown out, not counted
as evidence of weakness). The card left out most often is the natural first candidate — usually
the mandatory upgrade target; runner-up candidates become purchased-upgrade targets, but always
diagnosed fresh against a kit that already includes the mandatory upgrade (and previously-locked
purchased upgrades), not the raw Level 1 kit.

**A few mechanic patterns emerged and were used repeatedly, worth noting explicitly:**
- Pure Block increases never move win% at all (Block doesn't affect whether the mob dies).
- Pure damage increases with no Block backing them can actually *worsen* cost%/pulls (faster
  but riskier).
- A new "armor pierce" mechanic was introduced this pass: a card with this flag ignores the
  mob's own block-stat entirely for its own damage. It matters most on *low*-damage cards,
  since the game's mob block values only ever run 0-2, so a small-damage card loses a much
  bigger fraction of its output to block than a big-damage card does.
- When choosing between the strongest legal value found in a sweep and a more conservative one,
  this project has consistently chosen to land *short* of the strongest value — the explicit
  design discipline is "leave real margin unclaimed," not "maximize every number available."

## The 6 classes' upgrades, base card -> Level 2 value

### 1. Warrior (Guardian/Champion dual-stance mechanic — every card has two numbers, one per stance)

| Card | Base (Guardian / Champion) | Level 2 (Guardian / Champion) | Slot |
|---|---|---|---|
| Shield Block -> **Shield Bash** | 0 dmg/5 block \| 0 dmg/0 block | 1 dmg/5 block \| 2 dmg/2 block | Mandatory |
| Sundering Blow -> **Dominate** | 1 dmg/0 block (applies a "Sunder" debuff mark) | 2 dmg/0 block (mark unchanged) | Purchased |
| Heavy Swing -> **Colossal Swing** | 2 dmg/0 block \| 4 dmg/0 block | 2 dmg/0 block (unchanged) \| 5 dmg/0 block | Purchased |
| Vanguard Blade -> **Vanguard Blade [Lv 2]** | 3 dmg/2 block \| 3 dmg/0 block (has a combo bonus with Vanguard Shield, unchanged) | 4 dmg/2 block \| 4 dmg/0 block | Purchased |

Untouched: Execute (killing-blow finisher, already near-always played), Vanguard Shield (its
own combo bonus was found to be a dead lever, not worth upgrading).

### 2. Cleric (heal/damage hybrid kit)

| Card | Base | Level 2 | Slot |
|---|---|---|---|
| Heal -> **Greater Heal** | 3 heal, 0 dmg | 4 heal | Mandatory |
| Fiery Fortitude -> **Holy Fiery Fortitude** | 3 dmg, 2 heal, +2 max HP | 4 dmg (heal/max HP unchanged) | Purchased |
| Call of the Void -> **Void Storm** | 6 dmg | 7 dmg | Purchased |
| Void Mark -> **Void Mark [Lv 2]** | 3 dmg, no DOT | 4 dmg, gains a 1-damage "echo" that automatically fires the following round (new DOT mechanic, ported from another class's existing pattern) | Purchased |

Untouched: Cleansing Barrier, Smite (both already near-always played).

### 3. Paladin (has an "Invocation" combo mechanic — bonus damage/Block tied to STRIKE-tagged cards)

| Card | Base | Level 2 | Slot |
|---|---|---|---|
| Invocation of Sanctuary -> **Invoking Aura of Sanctuary** | 3 dmg, 0 block, existing per-STRIKE damage combo bonus | 3 dmg, 1 block; the existing per-STRIKE damage bonus is now *also* mirrored 1:1 in Block (new mechanic — even STRIKE cards with no Block of their own gain some) | Mandatory |
| Sacred Light -> **Sanctified Light** | 3 heal | 4 heal | Purchased |
| Invocation of Grace -> **Invocation of Grace [Lv 2]** | 4 dmg | 5 dmg | Purchased |
| Bastion's Hammer -> **Bastion's Breaker** | 6 dmg | 7 dmg | Purchased |

Untouched: Might of the Aegis, Holy Fortress (already near-always played).

### 4. Rogue (STRIKE-tag/finisher-curve mechanic; also has an "armor pierce" mechanic added this pass)

| Card | Base | Level 2 | Slot |
|---|---|---|---|
| Evasion -> **Evasion and Riposte** | 0 dmg, 10 block | 2 dmg, 10 block (unchanged) | Mandatory |
| Quick Slash -> **Quicker Slash** | 3 dmg | 4 dmg | Purchased |
| Ambush -> **Relentless Ambush** | 3 dmg (5 dmg if played round 1) | Same numbers, but the round-1-only bonus window now also fires in round 2 (new mechanic, no number change) | Purchased |
| Backstab and Dodge -> **Backstab and Dodge [Lv 2]** | 4 dmg, 2 block | 4 dmg (unchanged), 2 block (unchanged), gains **armor pierce** | Purchased |

Untouched: Cutthroat, Envenom (both finisher cards, already strong/near-always played when
their curve condition is met).

### 5. Ranger (has a persistent-Block mechanic on one card, and conditional-damage cards keyed to combos)

| Card | Base | Level 2 | Slot |
|---|---|---|---|
| Beast's Challenge -> **Beast's Stand** | 2 dmg (5 if "Beast Bond: Wolf" was played earlier this pull), 0 block | Same damage (unchanged), gains 1 block | Mandatory |
| Sure Shot -> **Bullseye** | 4 dmg | 5 dmg | Purchased |
| Sniper/Point Blank Shot -> **Deadeye/Point Blank Shot** | 5 dmg (7 if previous round's card granted evasion) | 5 dmg unchanged, 8 if previous round granted evasion | Purchased |
| Crippling Shot -> **Crippling Shot [Lv 2]** | 2 dmg, 1 block, grants evasion | 2 dmg unchanged, 2 block, grants evasion (unchanged) | Purchased |

Untouched: Beast Bond: Wolf (a persistent, stacking-Block mechanic — every damage/block bump
tried for it was found to swing far too hard, an order of magnitude past anything else in the
game, so it was deliberately left alone), Withdrawing Hip Shot.

### 6. Wizard (has a "Weave" combo mechanic — some cards arm a one-time bonus, others consume it)

| Card | Base | Level 2 | Slot |
|---|---|---|---|
| Fire Blast | 3 dmg, 0 block | 4 dmg, gains **armor pierce**, block stays 0 | Mandatory |
| Fire Ball -> **Fire Ball [Lv 2]** | 5 dmg (7 if a Weave bonus was armed) | Flat 7 dmg always — the Weave dependency was dropped entirely, not just numerically bumped, since it was strictly weaker than a sibling card on both its damage faces | Purchased |
| Ice Barricade -> **Ice Palisade** | 0 dmg, 10 block | 1 dmg, 10 block (unchanged) | Purchased |
| Snap Freeze -> **Deep Freeze** | 1 dmg, 1 block, grants evasion | 2 dmg, 2 block, grants evasion (unchanged) | Purchased |

Untouched: Arcane Volley, Frozen Shot (both already strong).

**Known open issue on Wizard specifically:** the fully-stacked slate (mandatory + all 3
purchased together) overshoots the class's own win-margin target more than any other class in
this pass (+2.1 vs. a target more like 0 to -0.7) — every individual card looked conservative
when checked in isolation, but the combined total ran further than intended. This was left
as-is deliberately (explicit call: the class's remaining headroom was already thin enough that
further tuning felt like chasing noise), not overlooked.

## Combined result, all 6 classes, mandatory + all purchased upgrades applied at once, tested against the real Level 2 mob pool

| Class | L1 baseline (cost% / win% / pulls) | Fully-leveled L2 (cost% / win% / pulls) | cost margin | win margin | pulls margin |
|---|---|---|---|---|---|
| Warrior | 22.2 / 98.9 / 5.66 | 19.9 / 99.7 / 5.98 | +2.3 | +0.8 | +0.32 |
| Cleric | 23.3 / 97.8 / 5.58 | 24.8 / 99.4 / 5.70 | -1.6 | +1.6 | +0.12 |
| Paladin | 21.6 / 97.8 / 5.53 | 20.9 / 97.1 / 6.08 | +0.7 | -0.6 | +0.55 |
| Rogue | 18.4 / 97.8 / 6.05 | 18.9 / 97.1 / 6.18 | -0.5 | -0.6 | +0.12 |
| Ranger | 18.0 / 95.6 / 6.08 | 18.2 / 94.9 / 6.35 | -0.2 | -0.6 | +0.26 |
| Wizard | 21.0 / 96.7 / 5.31 | 21.0 / 98.7 / 5.56 | +0.0 | +2.1 | +0.25 |

Positive pulls margin across the board is the expected, desired shape (each class should be
able to sustain more chained pulls after leveling up than before, even against harder content).
Paladin/Rogue/Ranger cluster tightly on win margin (-0.6 to -0.7); Warrior's overshoot is mild
(+0.8); Cleric's (+1.6) and especially Wizard's (+2.1) are larger and worth a second opinion on
whether they're acceptable or need another look.

## What I'd like your take on

1. Does the overall methodology (mandatory/purchased split, the three-metric margin framework,
   "never close both margins in the free card") sound sound as a design discipline?
2. Any of the 6 classes' final upgrade choices look off to you, either in isolation or relative
   to the rest of the roster?
3. Specifically: is Wizard's +2.1 win-margin overshoot (and to a lesser extent Cleric's +1.6)
   something you'd flag as worth revisiting, or is the variance across a 6-class roster like
   this within a reasonable range to just accept?
