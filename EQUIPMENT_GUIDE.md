# QUEST — Equipment Guide

Process doc for the equipment/gear system (tasks #25 "design what drops besides quest loot"
and #26 "build weapons and armor system"). Mirrors `DECK_CONDENSING_GUIDE.md`'s role for a new
class and `MACRO_LOOP_GUIDE.md`'s role for the Town/Bag/Gold economy — this is where equipment
design decisions get made and their reasoning kept, not invented fresh each session.

**Status: core mechanic locked (2026-09-05), redemption mechanic's shape locked (2026-09-05),
ingredient menu and exact material list not yet locked.**

## Origin and constraint this system must satisfy

Drafted originally as a "Recipe System" (Base + Ingredient) proposal from an external session,
brought in for review rather than adopted wholesale. `OPEN_QUESTIONS.md`'s "Gathering items at
nodes" entry already locks that **Gathering Tokens (Herb/Ore/Skin) are physical game pieces
specifically meant to feed this system** — whatever gets built here needs a redemption path
from those tokens, not a Gold-purchase-only or found-loot-only model in isolation. That
redemption mechanic is explicitly still open (see below), not solved by this doc.

## Big-picture call, made before any content: equipment is a second modifier layer, kept simple by design

QUEST's combat identity is that a hero's entire ruleset lives on 6 physical cards in hand —
every other piece of transient state the game tracks (Sunder stacks, Weave-armed, stance,
dot-count) is revealed by reading the deck itself and resets at pull boundaries. Equipment
necessarily breaks that (a modifier living on a separate card, cross-referenced against
whatever base card triggers it) — the same shape Slay the Spire relics use, matching this
project's own stated combat ancestry, not a new pattern being introduced cold.

Given that, two decisions were made specifically to keep the *cost* of that added layer small
rather than let it compound:

1. **No new resource clock.** The original draft's per-item "Charges" count (1-Hander=2,
   2-Hander=1, Staff=1, etc.) was rejected before any numbers were touched — it introduced a
   *new* refresh rhythm independent of everything else in the game. Replaced with the
   Durability model below, which reuses Town as its reset point — the same checkpoint that
   already resets hero HP on `leave_town` (`board_engine.py`). One rhythm, not two.
2. **Equipment and Level 2 upgrades are kept structurally separate, not compounded.** A fully
   leveled, fully equipped hero runs base-kit x Level-2-upgrade x Equipment simultaneously —
   the validation surface is the *product* of all three axes, not the sum. Equipment is
   deliberately scoped to never touch a card's own printed number (that's what Level 2 upgrades
   already do) — it only ever adds a separate, bounded, single-use effect on top. Keeping the
   two mechanisms non-overlapping means a class's already-locked Level 1/Level 2 numbers never
   need re-deriving just because equipment exists.

## The Durability model (locked)

**Every equipped item has exactly one use, then is locked until the hero's next Town visit,
where it resets automatically — no cost, no repair check, no permanent breaking.** A hero can
equip at most 3 items at once (1 Weapon, 1 Armor, 1 Trinket). Using an item is a **declared
choice** the player makes when playing a card, not an automatic trigger — the same shape
Smoke Bomb and Scroll of Vanquishing already use, matching this project's existing consumable
pattern rather than inventing a new one. Effect is bounded to **a single round of a single
pull** — it cannot span rounds or carry into a later pull.

**Why this beats the original Charges draft, concretely:**
- Removes the entire per-base-type charge-count table as a design axis. Every item follows the
  identical rule (one use, resets at Town) — the only thing left to balance is *which effect*
  is on the item, not *how many times* it fires. A strictly smaller design space to validate.
- Reframes every ingredient as structurally equivalent to an already-locked, already-priced
  consumable (Scroll of Vanquishing, Smoke Bomb, Whetstone, Preserving Charm), not a permanent
  mechanic upgrade sitting on a class's best card forever. This directly changes the risk
  profile of several ingredients originally flagged as dangerous (see below) — a rare, one-shot
  event is a fundamentally smaller thing to get wrong than a repeatable one.
- Gear can never be lost or destroyed (explicit design call, WoW-style: gear needs "recharging,"
  not repairing or replacing). Keeps the acquisition economy simpler — a hero's equipment
  collection only ever grows, it's never a maintenance sink.

**Not yet decided:** whether a hero can hold spare/unequipped items in the Bag (and if so, does
swapping equipment cost a turn/action), and how equipping something for the first time works
mechanically (found as loot mid-trip vs. only equippable in Town).

## The Base + Ingredient structure (kept from the original draft)

The separation itself is sound and matches how this project already isolates variables
elsewhere (Leveling Guide's mandatory-only baselines, the armor-pierce retrospective) — pricing
an item as Base (frame/slot type) + Ingredient (the actual mechanical hook) lets each be tuned
independently rather than hand-authoring every item's full stat block from scratch.

**Base** determines equipment slot (Weapon/Armor/Trinket) and, loosely, what kind of card it
makes sense to attach to (thematically — a Wand modifying only Ranged/Cast cards, a Staff
allowed to hold both offense and defense ingredients). Since Charges are gone, a Base no longer
needs its own numeric stat — it's now purely a slot-and-flavor classifier, not a balance lever.
This needs a fresh pass once the ingredient list is locked, since the original Base list was
built around the now-discarded Charges numbers.

**Ingredient** is the actual mechanical effect, and is where all the real balance work lives.

## Ingredient grades — what's kept, cut, or flagged, and why

**Named "grades," not "tiers"** — this project already uses "Tier" for mob difficulty
(Standard/Elite/Spike) and for grouping hero Levels (Tier 1 = Levels 1-2, etc.); a third meaning
in the same doc would recreate the exact ambiguity resolved earlier in this design pass.

### Grade 1 — kept close to the original draft, lowest risk
Flat, single-use, single-round bumps: **Honed** (+1 DMG), **Reinforced** (+1 Block), **Blessed**
(+1 Heal), **Swift** (resolves before the mob's own attack this round). These are the smallest
possible version of what a Level 2 upgrade already does, just single-use and equipment-sourced
instead of permanent and card-sourced. Same validation path as any other +1 grain-size change
this project has ever made — no new mechanism, just needs a sim pass once the redemption
economy exists to know what price point to test against.

### Grade 2/3 — re-evaluated under the single-use model, not cut wholesale the way they were under Charges

The original review of this draft (see conversation history, 2026-09-05) flagged four
ingredients as dangerous under the *Charges* (repeatable-per-trip) model. Single-use changes
the risk calculus for three of them substantially — they're no longer "cut," but they are not
cleared either. All four still need a dedicated simulator check before any are locked:

- **Ruthless** (killing blow, no damage taken if this kill lands) — under single-use, this is
  now structurally the same shape as an already-validated consumable, not a permanent mechanic
  upgrade on a class's best card. Real candidate. Needs a bounded check: does even one
  guaranteed damage-negation-on-kill per trip meaningfully move the defense-floor numbers
  `CLASS_BALANCE_GUIDE.md` already locked per class.
- **Elusive** (grants the Ranged tag / evades a Melee attack this round) — same reasoning,
  closer in spirit to Smoke Bomb's "escape unharmed" than a permanent evasion tool. Still
  touches a documented, deliberate design call directly: Rogue's own docstring states it has
  "no evasion tool... confirmed intentional, not revisited since." A single-use version is far
  less of an overturn than an unlimited one, but this still needs an explicit decision (not a
  default yes) on whether equipment is allowed to hand a class back a tool it was deliberately
  built without.
- **Mimicry** (counts as playing a specific tag — STRIKE/Eclipse/DOT/etc. — for combo purposes)
  — the one ingredient where single-use narrows the risk least. Rogue's finisher curve,
  Paladin's Invocation, and Necromancer's DOT-count payoff are all *exact* functions of how many
  qualifying cards were actually drawn and played — even one guaranteed extra count, once per
  trip, is a real, calculable shift in a scaling payoff's ceiling, not a vague power boost.
  Needs the most scrutiny of the four before it's allowed near a real item.
- **Persistent** (this round's Block carries into the next round) — the one ingredient where
  single-use narrows the risk the *least* in absolute terms, because the danger was never about
  repeatability, it was about the specific failure mode this project has already hit twice
  (Cleric, then Runecaster): a Block/Echo interaction quietly producing a "cannot die" result
  against a specific mob pattern. Even a single, once-per-trip application needs a direct
  equilibrium check (`condensed_trip.py`'s existing tooling) against the full mob roster before
  this is trusted, not just a sim of the isolated damage-margin math.

**Kept as lower-risk candidates, not yet checked:** Echo (duplicate a card's base effect) and
Smoke (force a Flee with no damage this round) — both single-purpose, bounded, and closer in
shape to existing mechanics (Blight/Earth Strike Rune's Echo tick, Smoke Bomb's existing Flee
consumable) than the four above.

## Redemption mechanic — shape locked (2026-09-05), exact materials/pricing not yet locked

**Crafting, not a direct token-to-item conversion: a hero brings specific Gathering Tokens plus
a Gold fee to Town and has a specific item crafted.** This is a Town-only action (matches every
other purchase-type action already in the game — Bag Upgrades, consumables, Class Trainer), and
the Gold fee follows the same flat-pricing philosophy `MACRO_LOOP_GUIDE.md` already established
for everything else. A recipe is not invented per finished item — it falls directly out of the
Base + Ingredient split already locked above: the Base consumes one token requirement, the
Ingredient consumes another (or a Gold-only fee), so learning "how do I get gear" and "what does
gear do" share the same mental model instead of being two separate systems to learn.

**Gathering Tokens gain Level-tiered subtypes within the existing 3 categories (Herb/Ore/Skin)
— not a fourth category, and not tiered by Zone.** `OPEN_QUESTIONS.md`'s own locked principle
for mob content — "the deck is curated per level, not per zone -- one shared deck for both
zones at that level" — applies here too: Zone and hero Level are independent axes in this game,
and equipment materials follow hero Level for the same reason mob content does, not the
player's physical map location. Concretely: a Level 1 node deals mostly the tier-1 subtype of
each category, a Level 2 node deals mostly the same plus a growing minority of the tier-2
subtype — the exact same weighted-pool shape `leveling_validation.mob_pool_for_level` already
implements for Standard-vs-Elite mob dealing, directly reusable here rather than requiring new
engineering.

**Subtype names locked 2026-09-05** (placeholder tier-1/tier-2 pair per category for now — full
6-tier naming ladder, drafted externally and checked for naming collisions against real WoW
terminology before locking, kept here for the remaining 4 slots as future material once more
than 2 hero Levels exist):

| Category | Tier 1 (Level 1) | Tier 2 (Level 2) | Future tiers (not yet needed) |
|---|---|---|---|
| Ore | Crag-Iron | Sun-Copper | Ember-Vein Ore, Glacier-Metal, Nether-Slag, Crown-Gold |
| Herb | Snap-Root | River-Mint | Scorch-Blossom, Lantern-Spore, Astral-Moss, Tyrant's-Crest |
| Skin | Scavenged Pelt | Bristle-Pelt | Ridge-Scale, Iron-Fleece, Phantom-Web, Behemoth Leather |

Checked directly against real WoW material names before locking (not assumed safe): the
original draft's third Herb slot, "Cinder-Bloom," was a near-exact match to Cinderbloom, an
actual gatherable herb in WoW: Cataclysm (Mount Hyjal, Deepholm, Uldum, Tol Barad, Twilight
Highlands) — replaced with Scorch-Blossom, verified clear. Two softer echoes were flagged and
kept anyway (a judgment call, not an oversight): Nether-Slag echoes WoW's real "Nether-" ore
naming convention (Nethercite Ore exists) without matching any specific item, and Behemoth
Leather echoes real WoW hide items ("Hide of the Behemoth," "Hide of the Abyssal Behemoth")
without being an exact material-name match — both are 4+ tiers out (not needed until Levels
3+ exist), so revisit before they're actually used if this becomes a real concern.

**Not yet locked:**
- Whether a recipe requiring a given subtype accepts only that exact subtype, or allows a
  higher-tier substitute (e.g., Sun-Copper usable anywhere Crag-Iron is required) — a real
  design choice affecting how forgiving crafting feels, not yet decided either way.
- The actual cost table (which Base/Ingredient needs which token type + how much Gold) — blocked
  on the ingredient menu itself being locked first.
- Whether unequipped spare materials/items sit in the Bag (competing with quest loot for space)
  or have their own separate storage.

## Open questions

Crafting is now settled as a Town-only action (see above), so the remaining open items are:

- **Base list needs re-deriving** now that Charges (the thing the original Base stats were
  built around) is gone — the six weapon/armor Bases from the original draft (1-Hander,
  2-Hander, Wand, Staff, Cloth/Leather/Mail/Plate) are flavor/slot placeholders only until this
  pass happens.
- **Whether swapping equipped gear costs a turn/action**, distinct from crafting it in the first
  place.
