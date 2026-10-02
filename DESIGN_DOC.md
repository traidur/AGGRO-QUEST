# QUEST — Design Doc (Core)

*Mirrors the organizational pattern of AGGRO's own `StS_x_WoW_Design_Doc_v7_4_Core.md`: current
rules stated cleanly up front, reasoning/derivation history kept in trailing sections of the
same document instead of scattered across files. QUEST is small enough right now to stay a
single doc rather than AGGRO's four (Core/Classes/Items/Mobs-Encounters-Acts) — that split can
happen later if the scope grows to justify it.*

*AI reading this cold: read `SOTG.md` first for QUEST-specific gotchas and anti-patterns before
engaging with any design question — this document states current rules, `SOTG.md` states the
mistakes AI models keep making about them. This document is authoritative for "what are the
current rules"; if anything here disagrees with an older doc or a docstring, this one wins —
flag the drift rather than silently trusting the older source.*

## What Is This Game?

A prequel/companion to AGGRO (a StS-x-WoW raid deckbuilder). AGGRO is the claustrophobic,
10-minute micro-puzzle of a raid boss. QUEST is the sprawling, push-your-luck macro-logistics of
MMO "leveling and farming." Genre: **logistical engine-builder**, not a raid encounter. Vibe:
greed, inventory management, exponential power scaling. Two layers: a fast, deterministic
**per-pull combat toll-check** (Section II) gates loot, and the **macro loop** (Section VI) —
Town, Bag, Quests, Gold, trip-chaining — is the actual game.

## I. Core Philosophy

1. **No Movement Tax.** Commuting across the map costs nothing. Movement is a tempo choice,
   never a resource tax.
2. **Carrots, Not Sticks.** No global Doom Track or "Game Over in N Turns" clock kills you. Instead, you are fighting **Economic Inefficiency**. 
3. **Determinism Over Dice.** Combat is a fully deterministic math puzzle — mob intent is
   printed and known in advance, round by round. The only randomness anywhere in a pull is
   which 4-of-6 cards you draw for your hand. You lose because your hand/sequence was
   insufficient, not because you rolled poorly.
4. **Shared DNA.** Reuses AGGRO's classes, card identities, and keyword vocabulary
   (STRIKE, AT RANGE, etc.) — condensed down to QUEST's much smaller per-pull format, not
   reinvented from scratch. See `DECK_CONDENSING_GUIDE.md` for exactly how that translation
   works.

### The Motivation Engine: Economic Efficiency
Most adventure games push heroes forward using a ticking global Doom Track. QUEST replaces the Doom Track with an **Economic Efficiency Puzzle**. You are pushing your luck not to survive, but to maximize your Gold-per-Trip. This is driven by three interlocking systems:

1. **Quest Decay is the Real Clock:** Every extra turn spent in the wilderness, or every extra "safe" trip taken back to Town, mathematically rots the value of your active quests. You don't die by playing it safe; you bleed your future buying power.
2. **Quest Exhaustion Forces Forward Motion:** The starter zones only have a finite amount of "easy" quests. Once the lower-tier quest decks run dry, the hero is forced to move into the harder zones. There is a strict, finite amount of Gold available in the game—any Gold lost to decay is gone forever. *(Anti-grind safeguard: Bare mob pulls without active quests are mathematically bounded by Food recovery costs—Food is priced so that wild farming without quest payouts is net-zero or net-negative, preventing players from stalling the End Boss. See MACRO_LOOP_GUIDE.md's "Anti-Grind Equilibrium").*
3. **The End Boss is an Economic Audit:** The final victory condition (the End Boss) is not just a combat check; it is a literal audit of the player's economic efficiency. If a hero bled too much Gold to quest decay in Zones 1 and 2, they will arrive at the End Boss lacking the buying power to afford their Level 3 Exhaustible abilities, highest-tier Equipment riders, or crucial Consumables. The game punishes playing it "too safe" by mathematically starving the player's endgame power.

### Balance philosophy (locked findings, not guesses)

- **A player always takes an achievable win.** Every diagnostic and every balance number in
  this project assumes a player who never voluntarily bails on a killable mob to preserve HP.
  Tested directly: a "maximize HP, don't chase costly kills" strategy survives *more pulls*
  but produces *fewer total wins*, because a voluntarily-survived pull with no kill pays
  roughly nothing. Under the current reward scheme, always-take-the-win is the mathematically
  correct baseline, not an assumption glossed over.
- **Mob variety, not card rebalancing, is the primary difficulty-smoothing lever.** Damage
  output against any single real mob is never a smooth curve — a mob's block pattern collapses
  a hand's damage into just a handful of discrete tiers (which specific big card a hand holds
  matters far more than fine-grained numeric tuning). Smoothing the overall experience comes
  from facing a *variety* of mob shapes over a session, not from sanding down individual card
  numbers to chase a single mob's curve.
- **Mob-dependent performance can be a feature, not a bug.** Warrior's Guardian/Champion split
  (Guardian favored against weak/low-HP mobs, Champion against strong/high-HP ones) was
  deliberately kept asymmetric rather than flattened toward artificial parity — confirmed
  empirically to add a genuine per-mob read, not just noise. Don't reflexively "fix" a
  mob-dependent curve without first asking whether it's adding real decision depth.
- **Difficulty (average performance) and balance (spread across classes) are separate,
  orthogonal knobs.** Scaling every mob in an already-balanced pool by a flat multiplier can
  push difficulty exactly as intended while blowing the cross-class spread wide open — classes
  don't respond to a uniform change proportionally. Retuning target difficulty needs a fresh
  search at the new range, not a multiply-everything-by-X shortcut.
- **Never report "average pulls survived" without decay/death rate next to it, no exceptions.**
  The two metrics don't correlate — a pool can look tightest on pulls-survived and not even
  place top-3 on decay. A class can look worse on raw death rate while actually completing
  quests faster (succeeding *because* it plays more aggressively, not despite dying more) —
  invisible unless both numbers are checked together.
- **Full-roster balance doesn't guarantee a subset's balance.** A class's kit tuned to parity
  across the full mob roster can still diverge sharply on a specific subset (e.g. one class's
  sustain compounding across a chain of easy mobs in a way flat mitigation can't replicate) —
  invisible in the full-roster average. Check the actual subset in play, don't assume it
  inherits the full roster's tuning.
- **HP is a valid balance lever, but only when it's the diagnosed problem, not a cover-up.**
  Wins-per-trip scale close to linearly with a class's max HP (~+0.25 wins per +1 HP across a
  swept 10-22 range, no diminishing returns found) — but that constant is roster- and
  kit-dependent, not a universal formula to reuse untested. Raising HP always makes the numbers
  look better, whether or not it's the real fix — check a class's damage-output variance and
  per-round economy first; only raise HP if those are already healthy and the class is still
  underperforming.

## II. Combat — The Pull

**Core structure.** Each class has a unique 6-card deck (no duplicates). A pull draws a 4-card
hand, sequences exactly 3 of those 4 across 3 rounds (one card per round — the 4th card is a
real, deliberate decision to leave unplayed), and resolves against one mob's fixed, fully known
3-round attack pattern. No Energy pool, no per-card cost — the entire decision is *which 3 of 4,
in what order*. The deck fully resets every pull; nothing carries over between pulls at the card
level.

**Win / Loss / Flee.** Win: the mob's HP reaches 0 at any point during the 3 rounds. Loss: the
hero's HP reaches 0. Flee: 3 rounds pass with the mob still alive — no reward, no further
attrition, the mob is left behind.

**The Slog.** An OTK (killing the mob in fewer than 3 rounds) isn't required. Damage dealt in a
failed round still whittles the mob's HP down — round 2 (or 3) is a smaller remaining check
against a fresh hand, not a repeated attempt at the original threshold.

**Mob still acts on the round it dies — no interrupt, a deliberately tested and kept rule.**
If a hero's damage this round brings the mob to 0 HP, the mob's own attack that round still
lands (unless a killing-blow card says otherwise, below). Tested the alternative directly:
single-pull win rate is identical either way, but multi-pull trip length explodes 3-5x under an
interrupt rule, because most of a class's real per-pull HP cost comes specifically from "the
mob's last hit still lands even as it dies." Kept the no-interrupt rule because mob intent is a
fixed, known script — making it conditional on the hero's own success mid-round breaks that
determinism, and it preserves a real decision ("do I have enough to finish this round, and is
the exposure worth it") instead of making "go for the kill" unconditionally correct.

**`grants_range` (evasion).** Some cards grant "At Range" for the round they're played — evades
a melee mob's attack entirely that round. Does nothing against a ranged mob (Scout is currently
the only ranged mob in the game — see Section IV). Not every mob is melee; don't assume it is.

**Killing-blow riders (Warrior's Execute, Rogue's Cutthroat).** A narrower, explicitly-tagged
exception to the no-interrupt rule above: if one of these specific cards' damage brings the mob
to 0 HP the round it's played, that mob's attack *is* prevented — a clean, decisive finish,
not a trade. Every other card, even ones that also happen to land a killing blow, follows the
normal "mob still acts" rule.

**Stance (Warrior only): locked for the whole pull, no flip.** Pick Guardian or Champion before
round 1; it holds for all 3 rounds. Because mob intent is visible in advance, this is a real
per-mob read (Guardian tends to win against low-HP mobs, Champion against high-HP ones) —
confirmed as a deliberate, mob-dependent puzzle axis, not noise to flatten out. Physical
implementation: every Warrior card prints its Guardian and Champion values as mirrored text on
opposite ends of the card — lay all three played cards the same way up for the whole pull, no
separate stance token needed.

**Unique decks.** Every class's 6 cards are unique — no duplicate copies. This means any
mechanic tied to "has card X been played yet this pull" is automatically capped at 0-or-1 and
needs no stacking token (e.g. Warrior's Sunder mark). Keep this constraint for every future
class too.

**Validation constraint every class's numbers must satisfy: net HP change stays negative at
every starting-HP level, not just on average ("the equilibrium check").** A class whose
best-case healing/sustain output can match or exceed a mob's damage at some starting HP
produces a structural "cannot die" bug — checked by testing net HP change at multiple starting
points (full, 2/3, 1/3, critically low), not just the average outcome, since a genuine slow
decline and a stable equilibrium can look identical on average alone. Found and fixed twice on
this project already (Cleric's original healing kit, Runecaster's first numbers pass) —
mandatory check before locking any healing-capable class.

## III. Class Kits

| Class | HP | Identity |
|---|---|---|
| Warrior | 18 | Guardian/Champion stance (Section II), Sunder stacks +2 damage on later cards, Vanguard Shield/Blade reward back-to-back play |
| Cleric | 14 | Sacred Balance — Smite auto-heals a flat amount; Cleansing Barrier/Fiery Fortitude carry incidental damage riders to keep a real floor |
| Wizard | 14 | Spellweave (arm a bonus on a Source card, consume it on a Payoff card) + Positioning (At Range evades melee) |
| Paladin | 17 | Invocation of Sanctuary/Grace — pick exactly one per pull, simultaneously a payoff for earlier STRIKE cards and a setup for later ones |
| Rogue | 16 | Cutthroat/Envenom — finishers scaling off STRIKE cards played since the last finisher; killing-blow rider on Cutthroat only |
| Ranger | 15 | Beast Bond: Wolf — persistent Block every round once played; Sniper/Point Blank Shot pays off having granted At Range the previous round |
| Runecaster | 16 | Lightning Bolt rewards playing right after Chain Lightning; Earth Strike Rune's damage/heal partially echoes automatically next round, no card spent |

All 9 classes are now built. **Full, exact card-by-card rules text (with keyword
tags) lives in `CARD_REFERENCE.md`, generated directly from each class's real `CARDS` dict —
don't duplicate card text here, it would drift.**

## IV. Mob Roster (Standard Tier)

Derived by brute-force search (`sim/stat_gauntlet.py`, `sim/pool_search.py`), not hand-designed.
**Mob stats are class-agnostic — never tuned per class.** Each entry is `(ATK, Block)` per
round, all three rounds shown in order:

| Mob | HP | Round 1 | Round 2 | Round 3 | Type |
|---|---|---|---|---|---|
| Grunt | 7 | 2 ATK / 0 Block | 3 ATK / 2 Block | 3 ATK / 0 Block | Melee |
| Bruiser | 10 | 2 ATK / 0 Block | 2 ATK / 0 Block | 5 ATK / 0 Block | Melee |
| Enforcer | 6 | 5 ATK / 2 Block | 3 ATK / 0 Block | 4 ATK / 2 Block | Melee |
| Raider | 5 | 3 ATK / 2 Block | 4 ATK / 0 Block | 5 ATK / 1 Block | Melee |
| Ambusher | 8 | 4 ATK / 1 Block | 4 ATK / 0 Block | 2 ATK / 0 Block | Melee |
| Scout | 8 | 2 ATK / 0 Block | 3 ATK / 0 Block | 4 ATK / 0 Block | Ranged |

Scout is currently the only ranged mob — `grants_range` cards do nothing against it. Spike and
Elite tiers exist as concepts (Elite trio: Bulwark/Berserker/Warlord, HP 12 each, solo-baseline
only — see Section V) but Spike tier is empty/deferred (task #20).

**Derivation methodology, precisely (applies to every future tier too).** Sweep every
`(dmg, block)` combination across all 3 rounds plus a target HP range, computing exact
single-pull cost/win-rate/round-1-kill-rate per class, then pool-search for the combination
that's simultaneously tightest on *both* pulls-survived spread and decay spread across every
class (never just one metric — see the Balance Philosophy section above). The current 6-mob
Standard tier was the only candidate pool found holding both at once.

**Block is hard-capped at 0-2 in the search itself — never swept higher.** An unconstrained
sweep found "great"-looking candidates at block 4-5, which turned out to be a trap: heavy block
caps the total damage any hand can deal in 3 rounds, so past a certain HP the mob becomes
literally unkillable, not just hard — a "fake win" that looks balanced on paper only because a
lucky hand can one-shot it before its brutal later rounds ever matter. Round-1-kill-rate is
tracked as a hard 0% requirement in the search, not a courtesy check after the fact.

**Every tier must contain at least one ranged mob, decided going forward.** Two classes
(Wizard, Ranger) have `grants_range` mechanics that are structurally inert against an all-melee
pool — Scout was added retroactively to Standard tier to fix this; any future tier (Spike,
Elite, etc.) needs a ranged candidate designed in from the start, not bolted on after the fact.
Scout itself was chosen for *least total disruption* to every class's existing numbers, not for
maximizing how differentiated the ranged tag reads — and deliberately carries **no Block**,
since Block represents durability against being hit (a melee-tank trait), while a ranged
attacker's identity is staying out of the fight entirely; giving it Block would stack a second,
redundant advantage on top of evasion-nullification for no real reason.

**Mixed-Type Mobs (Future Design Space):** Instead of a mob being exclusively Ranged or Melee for all 3 rounds, future mobs should explore mixed-round types (e.g., Round 1: Ranged, Round 2: Melee, Round 3: Melee). The combat engine already natively supports per-round types. This forces players to sequence their `grants_range` cards to counter the exact specific round where the mob closes to melee, massively increasing the depth of the sequencing puzzle without adding any new rules.

## V. Co-op — Aggro & the Party Pull

Multiple heroes (2-4, any distinct class) fight a shared threat together, co-op only. Still 3
rounds, one card per hero per round. **No duplicate classes in one group (locked 2026-09-01,
resolving "any class mix"'s prior ambiguity on this point)** — the physical components only
include one deck per class, so a group can never field two heroes of the same class at the
table; this isn't a game-balance rule, it's a hard physical-component constraint.

**Aggro.** Each card carries a flat, printed Aggro value (0-4), locked per card in every
class's own `CARDS` dict — this is a narrow, deliberate exception to "no aggro/targeting system
exists in QUEST," scoped only to this co-op mode.

**Two mechanically distinct fight shapes, decided by how the encounter starts (never
re-evaluated mid-fight):**

- **Elite and multi-mob nodes** (a node dealing 2+ simultaneous mobs is co-op-exclusive; a
  single Elite is available in every mode) resolve through the **round-robin engine**
  (`sim/condensed_party.py`'s `simulate_party_multimob`, built and validated this session):
  mobs stay fully separate (own HP, own pattern, own type), each hero's own damage is
  independently pointed at one mob (no pooling, no splitting), and each round's Enemy Phase
  ranks living heroes by Aggro and surviving mobs by that round's ATK, then round-robins the
  assignment — wrapping back to the loudest hero if mobs outnumber heroes. Block is personal
  only, auto-applied to a hero's first genuinely-incoming assigned attack (proven optimal, not
  a house rule). Killing-blow riders are scoped per-mob. Elite fights are simply the M=1 case
  of this same engine (only the loudest hero is ever assigned the attack).
- **A future, undesigned Boss tier** would use the older **pooled engine**
  (`simulate_party`, already built, validated via a 540-check regression against solo): the
  whole party's damage *and* Block pool together against one shared mob HP, with the
  single loudest hero taking any unabsorbed leftover. This is deliberately reserved for a
  Boss-fight feel (the party defending as one unit against one shared threat) and currently has
  no live use case — no Boss content exists yet.

**Full targeting/tiebreak rules, `grants_range` interaction, hero-death handling, and the
worked examples are in `OPEN_QUESTIONS.md`'s "Co-op multi-hero vs. Elite/multi-mob nodes"
entry — read that before touching this system.** Not yet built: a best-line search over which
mob each hero should target (the round resolver itself exists; the solver that finds optimal
play across targeting choices doesn't).

## VI. The Macro Loop — Town, Bag, Quests, Gold

**All 7 built classes are wired into the macro-loop simulator** (`sim/macro_sim.py`'s
`CARD_SOURCE`/`HP_ATTR`/`HAS_STANCE` — Rogue, Ranger, and Runecaster were missing until this
doc's audit caught it; fixed and re-swept against the current 6-mob roster). Re-measured
findings, not yet acted on:

- **Rogue dies roughly 3.4x as often as Warrior under the current default risk policy**
  (0.31 vs. 0.09 avg deaths per 20-trip chain, `food_only` strategy) and hits full bounty decay
  nearly 3x as often (30.7% vs. 11.7%). **Ranger and Rogue both take noticeably longer to
  afford the 16G Bag Upgrade** (5.07/5.41 avg trips) than the rest of the roster (3.83-4.45).
  **Root-caused, but two genuinely different mechanisms, not one shared cause:** Rogue and
  Ranger are the only two classes whose lethal-hand-fraction (fraction of hands with no
  survivable line) turns nonzero already at 50% HP — every other class holds a clean 0% floor
  down to 33% HP. The macro-loop risk policy runs at zero tolerance outside a quest-completing
  pull, so crossing that threshold a full HP-tier early means more forced consumable use
  (slower Gold/XP) and more exposure to the only risk the policy ever takes (more realized
  deaths) — that much is shared. But *why* each class crosses it differs: Rogue has a clean,
  generalizable card-count gap (exactly 4 of its 6 cards carry zero defensive value, at or
  above the 4-card hand size, so a hand containing none of its defense is mathematically
  possible). Ranger's cause is different — a defensive tool (`grants_range`) that's completely
  voided by mob type against Scout specifically, not a raw card-count shortfall. See
  `CLASS_BALANCE_GUIDE.md`'s "Rogue and Ranger's macro-loop risk outlier" section for the full
  trace of both. **Not yet decided: the fix** (kit rider, HP adjustment, risk-policy/pricing
  change, or accepted identity) — see that section's candidate list.

**Map model.** A Zone contains several Nodes, including Town itself; movement between any of
them is free (Golden Rule 1 — no movement tax). The actual cost of visiting Town is Decaying
Bounty quest decay (below), not distance. **Currently built (`sim/macro_sim.py`'s `NODES`):**
4 fixed Standard-tier nodes (waystation/cove/ridge/marsh), each tied to one specific quest's
loot — every pull at a node draws a random mob from the Standard pool (Section IV), so which
3-of-4 quests a given trip's log holds is cosmetic, not a different challenge. **Decided but
not yet built:** a richer version where each occupied node holds a visible, turn-based-dealt
mob card (a shuffled deck of 3 copies × N mobs, reshuffling on empty) instead of redrawing
blind every pull, plus a deliberate "blind refill" exception (a second hero landing on an
already-contested node draws fresh and blind, giving priority real stakes) and Elite mobs mixed
into a zone's deck at known, printed odds. See `OPEN_QUESTIONS.md`'s "Zone-node mob dealing"
entry for the full resolved design — don't confuse it with what's actually running today.

**Inter-Zone travel via Border Nodes, resolved.** Movement is free everywhere *within* a
Zone, but moving between distinct Zones requires crossing a Border Node, which acts as a
required combat toll — a **Scouted Pull** (draw 2 cards from the destination Zone's level
deck, both revealed, choose one to fight) rather than being free like internal movement.
Deliberately not a blind draw — see `OPEN_QUESTIONS.md`'s "Border Nodes and Scouted Pull"
entry for the full resolved mechanic (turn structure, why the destination deck and not the
zone being left, and how this reconciles with the zone-refresh rule). **Flight Path, locked and
built 2026-08-21**: a dedicated node present in Zone 2 and Zone 4 (not a Town purchase) that
lets a hero standing in one commute straight to the other for 2 Gold, bypassing the Border
Node toll (and its combat risk) entirely — only connects those two specific Zones, doesn't
shortcut any other journey. Costs no turn of its own, the same way ordinary intra-Zone movement
is free; a hero can fly and then immediately pull at a node in the destination Zone within that
same turn. A rational hero always takes it over the 2-hop Border Node route when it applies and
is affordable, since it strictly dominates (fewer turns, zero risk, small Gold cost). Border
Toll travel *is* also built and tested (`sim/macro_sim.py`, 2026-08-20) — see the "Starting map,
locked" note below for the two-Town map shape this was validated against and why an earlier
single-Town version got replaced. Not to be confused with the free intra-Zone movement above.

**Starting map, naming locked (2026-09-03): two Zones, one Border Node, a Town in each.**
**Zone 1 (The Gilded Coast)**, the starting zone, holds **The Smugglers' Roost** (Town) — Bag/Food/Potion purchases, quest turn-in, the Bag
Upgrade. **Zone 2 (The Syndicate Straits)**, reached via **Thorne's Toll** (the Border Node connecting them), holds **both** a second
Town (**Port Ironguard**) and the **Class Trainer** (**The Syndicate Master**) — purchased (Level-2+) upgrade cards are bought at the Trainer
specifically, not folded into Town's shopping list, but "a town is a town is a town": every
other amenity (turn-in, decay, Bag Upgrade, Food/Potion restock) works identically at either
Town, with no zone restriction on which quest's loot can be turned in where. A trip can end at
whichever Town the hero happens to be nearest, without any "must get home to Zone 1" pressure.

**Superseded design, kept for the record:** an earlier version of this section gave Zone 1 the
only Town and Zone 2 only the Trainer, forcing every Zone-2 excursion into a mandatory round
trip (cross out, cross back) before a trip could ever conclude. Built and tested directly in
`sim/macro_sim.py` — the round-trip requirement alone (independent of routing quality) drove
real, severe cost: trips-to-Level-2-plus-first-skill went from a ~2.1-2.4-trip baseline up to
6.8-56 trips depending on class, with real death rates appearing where the zone-less baseline
had a clean 0.000 across the board (up to 13.2 deaths/run for Wizard). Even after fixing the
routing policy to stop zigzagging between zones and to decline genuinely risky *outbound*
crossings, trips only came back down to 3.6-7.0 and deaths to 0.5-1.7 -- still well above
baseline, because the *return* leg stayed genuinely mandatory (Zone 1 was the only Town) no
matter how well the hero routed. Adding a Zone 2 Town removes that forced-return pressure
entirely, which is what actually explains the difference -- not smarter play, a different map.
Re-tested with two Towns and a fully discretionary crossing in both directions: trips dropped
to 2.33-2.71 and deaths to 0.000-0.020, both matching the original zone-less baseline almost
exactly, while the hero still genuinely works both Zones (roughly even Zone1/Zone2 pull splits
in testing, not "avoid Zone 2 entirely"). This 2-zone, 2-Town/1-Trainer shape was a
starting-slice artifact at the time it was written -- superseded below now that Zones 3/4's
hub shape is actually decided.

**Zone 2's nodes and quests, locked** — mirrors Zone 1's structure exactly (4 nodes, required
2/3/4/5, same coastal/pirate-plunder naming thread as Zone 1's waystation/cove/ridge/marsh and
Pilfered Goods/Syndicate Ledger/Contraband Crates/Stolen Signet):

| Node | Quest | Required | XP |
|---|---|---|---|
| shoal | Smuggled Cargo | 2 | 2 |
| lagoon | Forged Ledger | 3 | 3 |
| bluff | Plundered Chest | 4 | 4 |
| wreckage | Buried Treasure | 5 | 5 |

**Mob roster, flavor names locked (2026-09-16) -- not yet wired into the sim's actual display
names.** Level 1 only ever deals the 6 Standard-tier stat-blocks (see
`sim/leveling_validation.py`'s `mob_pool_for_level`) -- Elites are Level-2-exclusive content and
never appear at Level 1, so there is no Level 1 Elite naming to do. Flavor names lean on the
same Gilded Coast/Syndicate vocabulary as the quest names above:

| Mob (mechanical name) | Level 1 name |
|---|---|
| Grunt | Syndicate Deckhand |
| Enforcer | Syndicate Enforcer |
| Raider | The Cutthroat |
| Scout | Syndicate Gunner |
| Bruiser | The Powder Keg |
| Ambusher | The Wrecker |

**Built in `sim/macro_sim.py`** (2026-08-20) — `NODES`/`NODE_ZONE`/`QUESTS` carry all 8 entries
across both Zones; Border Node crossing is a real Scouted Pull toll (`_scouted_pull_mob`/
`_cross_to`/`_best_case_mob` in `run_one_trip`), fully discretionary in both directions now
that both Zones have Town. Flight Path (Zone 2 <-> Zone 4, 2 Gold, no turn cost) is now also
built -- see the Flight Path entry above.

**Starting loadout:** 3×3 Bag (9 slots total), 1 Food (a 2×2 tile occupying 4 slots, leaving 5 open 1×1 slots), 0 Gold, 0 XP.

**Zones 3 and 4, naming locked (2026-08-20), wired into real gameplay (2026-08-21).**
Map shape: Zone 1 (SW, starting Zone) -> Zone 2 (SE) -> Zone 3 (north of Zone 2) -> Zone 4
(west of Zone 3) -> back to Zone 1 (south of Zone 4), a 4-Zone loop connected by 4 Border
Nodes, all built (`border_1_2`, `border_2_3`, `border_3_4`, `border_4_1`, all in
`sim/macro_sim.py`'s `BORDER_NODES`). Zone 2 and Zone 4 mirror each other -- both get a full
Town **and** the Class Trainer, connected by a Flight Path (2 Gold, no turn cost, also built)
between them specifically, since they're diagonal on the loop rather than adjacent. Zone 3,
like Zone 1, is Town-only, no
Trainer.

Theme: **The Pale Wastes**, home to **The Sunsworn** -- a militant order that arose to purge
the corruption Zones 1/2's smuggler economy represents, and has curdled into something just as
bad: paranoid zealot-knights, "relics" that are really just looted goods laundered through
religious authority, confessions burned instead of heard. Deliberately an original setting, not
a reskin of any existing copyrighted property.

**The Sunsworn's origin story, locked (2026-09-15) -- their creed is "The Unyielding Dawn."**
Some past cataclysm ("the accident") blotted out the sun over this realm, turning the sky into
a permanent, suffocating twilight. The Sunsworn were the realm's own Knights before that
happened, and they didn't break when it did -- they doubled down. They believe the sun hasn't abandoned them, only that
it's testing them, and that purging every last shadow from the land is what will make it
return. Their corruption isn't demonic, it's the corruption of absolute, merciless zealotry:
the old chivalric codes twisted to an extreme where weakness, retreat, or compromise are worse
than death. They hoard holy relics, blessed oils, and sacred texts not out of greed but because
they believe these are the only weapons left against the apocalypse.

**The Tarnished Crusaders (aesthetic).** Heavy full-plate armor, tabards, greatswords, kite
shields -- but the armor is obsessively, almost maniacally maintained, polished with blessed
oils until it gleams blindingly bright by torchlight even waist-deep in a swamp of rotting
corpses. Weapons are anointed with holy fire; massive iron braziers burn with sacred, white-hot
flames along the parapets, and whole forests get burned just to keep the darkness at bay. High
stone castles and cathedrals, fortified for a siege that never ends.

**The Undead: the Risen Dead of the Long War.** Not an invading force -- the undead here are
the realm's *own* citizens and soldiers, the ones who fell in the earliest days of the
cataclysm. They're visually recognizable as what they once were: peasants, archers, fallen
knights still wearing rusted, broken versions of the kingdom's own armor. Light burns them and
also reminds them of the life they lost; holy magic makes their flesh smoke and blister, and
they recoil from the Sunsworn's polished armor and holy fire. They don't skitter in the
shadows -- they form endless shield-walls of the dead, battering against the cathedral doors
night after night in a grim parody of medieval siege warfare.

**The Three-Way Hostility.** The Sunsworn and the Undead are locked in a grinding, endless
meat-grinder -- for every corpse the Knights burn down, more rise from the mud. The Sunsworn
regard the player as "**The Unordained**": mercenaries, looters, and vagabonds trespassing in
their sacred warzone, tolerated at best. **Flavor only, not a built mechanic:** in fiction, if a
hero is caught carrying magical or holy items, the Sunsworn would demand they be surrendered
"for the war effort," and refusal would mean being declared a heretic and executed -- this
colors how the Sunsworn should read in any future flavor text or NPC dialogue, but it is not a
forced encounter, item-confiscation, or execution mechanic in the actual game. The Undead, for
their part, don't discriminate at all -- a hero is just living flesh caught in the middle of
someone else's war.

**Node/quest table, locked (2026-08-20):**

| Zone | Node | Quest (loot) | Required |
|---|---|---|---|
| 3 | Mud Trenches | Royal Signets | 2 |
| 3 | Ruined Abbey | Consecrated Ash | 3 |
| 3 | Pyre Fields | Ashen Vestments | 4 |
| 3 | Broken Bridge | Shattered Broadswords | 5 |
| 4 | Charred Village | Rusted Mail | 2 |
| 4 | Armory Gates | Tarnished Crests | 3 |
| 4 | Gleaming Citadel | Blessed Lamp Oil | 4 |
| 4 | Sunward Throne | Gilded Penance | 5 |

Ordering logic: each Zone escalates from an exposed outer position to the most defended/
innermost one -- Zone 3's Broken Bridge is the crossing that leads toward Zone 4, so it lands
last; Zone 4's Sunward Throne sits *inside* the Gleaming Citadel, so it's the final, hardest
node by construction, not just by assignment.

Town node (each Zone's Town is the same amenity, per "a town is a town is a town" above --
Zone 3 and Zone 4 each get their own distinct flavor name, locked 2026-09-15, matching Zone 1/2's
pattern of two distinct Town names rather than one shared one):
- **Zone 3: The Vanguard Camp** -- a fortified staging ground outside the warzone where
  mercenaries and disgraced knights trade supplies. Matches Zone 3's own nodes reading as the
  exposed frontline approaching the fight.
- **Zone 4: The Pyre-Lit Bastion** -- a fortress town lit by the same sacred braziers described
  in the Sunsworn's aesthetic above. Matches Zone 4 already holding the innermost, most-defended
  nodes (Gleaming Citadel, Sunward Throne).

Unused candidate loot names from the same brainstorm, kept for the record in case any fit
better once quest reward tuning starts: Sanctified Reliquary, Martyr's Toll, Zealot's Bounty,
Consecrated Ledger, Purged Confession.

**Mob roster, flavor names locked (2026-09-15) -- not yet wired into the sim's actual display
names.** Level 2 deals the same 6 Standard stat-blocks Level 1 uses (see Zone 1/2's own mob
roster table above) as its base, plus 3 Elite stat-blocks that are exclusive to Level 2 and
never appear at Level 1 at all (`sim/leveling_validation.py`'s `mob_pool_for_level`, weighted
3:1 Standard:Elite by physical deck composition) -- a Level 2-specific flavor skin split across
the Zone's two warring factions, roughly 2:1 Sunsworn:Undead since the Sunsworn are the zone's
entrenched, numerous holding force and the Undead are the rarer, more unsettling threat they're
fighting. **Three of the six Standard mobs also got a real stat remix for their Level 2
appearance** (locked 2026-09-16, see `CLASS_BALANCE_GUIDE.md`'s Level 2 mob remix section for
the full derivation and verification) -- same total damage/Block/HP as the Level 1 version,
just resequenced or redistributed across rounds 1-2, picked for the combination that kept the
9-class roster closest together rather than the combination with the least total movement. This
mechanical heritage (which flavor name is really which common mob, and what changed) is kept
here for design reference only -- PnP cards and the sim's own display never show the common
name or the remix, only the finished flavor name:

| Mob (mechanical name) | Tier | Faction | Level 2 name | Remix vs. Level 1 |
|---|---|---|---|---|
| Grunt | Standard | Sunsworn | Sunsworn Footman | `[(2,0),(3,2),(3,0)]` -> `[(3,0),(2,2),(3,0)]` (round 1/2 damage swapped, each round keeps its own Block) |
| Enforcer | Standard | Sunsworn | Sunsworn Inquisitor | `[(5,2),(3,0),(4,2)]` -> `[(5,1),(3,1),(4,2)]` (round 1 and round 2 Block both set to 1) |
| Raider | Standard | Sunsworn | Sunsworn Zealot | none -- identical to Level 1 |
| Scout | Standard | Sunsworn | Pyre Archer | none -- identical to Level 1 (a remix candidate was tested and rejected, see CLASS_BALANCE_GUIDE.md) |
| Bruiser | Standard | Undead | The Rotting Legion | none -- identical to Level 1 |
| Ambusher | Standard | Undead | Grave Lurker | `[(4,1),(4,0),(2,0)]` -> `[(4,0),(4,1),(2,0)]` (Block moved from round 1 to round 2) |
| Bulwark | Elite | Sunsworn | The Ashen Bulwark | n/a -- Level 2-exclusive, no Level 1 counterpart |
| Warlord | Elite | Sunsworn | The Unyielding | n/a -- Level 2-exclusive, no Level 1 counterpart |
| Berserker | Elite | Undead | The Grave Knight | n/a -- Level 2-exclusive, no Level 1 counterpart |

**Built, 2026-08-21 (`sim/macro_sim.py`):** the full 4-Zone loop is real and playable end to
end, not just designed on paper.
- `BORDER_NODES` now has all 4 crossings (`border_1_2`, `border_2_3`, `border_3_4`,
  `border_4_1`), and multi-hop routing (`_next_border_toward`/`_hop_distance`, built earlier
  this session) needed zero changes to handle them -- a pure data addition, as anticipated.
- `NODES`/`NODE_ZONE` carry all 8 real Zone 3/4 nodes, using the exact locked names/loot above.
  Each one's mob-difficulty tier (`LEVEL2_TIER`, the real 18-Standard+3-Elite pool) is set
  **natively on the node itself**, the same way Zone 1/2's nodes say `"standard"` -- mob
  difficulty is a property of the place, never the hero's XP or level. A same-session attempt
  to instead gate difficulty on `LEVEL2_XP_THRESHOLD` was caught and reverted before it shipped
  (would have made a Level 1 hero suddenly fight Elites the instant their quest log flipped
  over, still standing in the old Zone 1/2 nodes, and never come back down if they returned
  there later -- wrong on both counts). Verified directly: Level 1 heroes never wander into
  Zone 3/4 (0 violations across 300 trials), and all 3 real Elites (Bulwark, Berserker,
  Warlord) do turn up once a hero actually travels there.
- `TRAINER_ZONES` now includes Zone 4, matching the locked "Zone 2 and Zone 4 both get Town and
  the Class Trainer" rule.
- `LEVEL2_QUESTS` (the pool `_trip_chain` switches to once a hero passes `LEVEL2_XP_THRESHOLD`)
  now uses the real, locked loot names and `required` counts above, not a stand-in.

- **Level 2 Quest Gold Ladders (Locked 2026-10-01):** Derived to reward physical bag pressure and excursion wound risk with strictly monotonic Gold/turn efficiency scaling (clean tabletop: `2.00 -> 2.25 -> 2.60 -> 2.83` G/turn):
  * **2 tokens / 2 XP** (*Royal Signets*, *Rusted Mail*): `[4, 2, 1, 0]` (Total gross with mob kills: 6G)
  * **3 tokens / 3 XP** (*Consecrated Ash*, *Tarnished Crests*): `[6, 4, 2, 0]` (Total gross with mob kills: 9G)
  * **4 tokens / 4 XP** (*Ashen Vestments*, *Blessed Lamp Oil*): `[9, 5, 2, 0]` (Total gross with mob kills: 13G)
  * **5 tokens / 5 XP** (*Gilded Penance*, *Shattered Broadswords*): `[12, 7, 3, 0]` (Total gross with mob kills: 17G; carries ~28% silver decay risk on extended 2-trip excursions).

**Loot chain, revised - colored quest tokens, any mix.** Each active
quest is assigned a color (printed on the quest card, or marked with a colored token on it).
Loot earned for that quest is represented by a token of the matching color, placed into any
slot with room - the color identifies which quest it belongs to. **A slot holds exactly 1 
token/item** - there is no same-slot stacking (`ITEM_STACK_CAP = 1`). A
same-color-only rule would tie which node a player can profitably pull at to their current
Bag state (each node maps to one quest's color), quietly punishing a player for chasing a
favorable mob matchup at a different node just because their Bag is already partway into a
different quest's color. Keeping colors freely mixable keeps node choice (about the mob
matchup) and Bag capacity (about token count) fully independent, the way they should be.
Running out of slots (every slot full, locked, or holding an unused
consumable) means no more loot of any kind can be collected until a quest turn-in or sale
frees space. This replaces the previous "one open slot accepts any mix of loot types, Food
closes it" model entirely - colored tokens don't need a "closed" state at all, since each
quest's progress is now readable directly off the tokens' colors, regardless of which slot(s)
they end up sharing space in.

**Consumables — the price gap and the stacking exception are what create the real trade-off:**
- **Food (4 Gold):** heals to full HP. One uncapped, complete reset per slot — never stacks,
  one Food per slot maximum.
- **Potion (3 Gold):** heals a flat **8 HP**, cheaper than Food. For the same one slot, a
  player is choosing between one big guaranteed reset (Food) or a stack of smaller effects at a
  lower total Gold-per-slot (Potion and the other non-Food consumables below) — a real choice
  either way, not one strictly better than the other. (Food previously closed the active loot
  slot as its own separate trade-off; that clause is cut — traced through mechanically and
  found not to actually motivate anything a low HP/Food count wasn't already forcing on its
  own, see `MACRO_LOOP_GUIDE.md`'s Bag Tetris revision entry for the full reasoning.)

**Unified non-Food stacking rule (locked 2026-08-22): everything except Food stacks 3-to-a-slot,
any mix.** One rule instead of a separate cap per item type — the same rule Quest Loot tokens
already use ("a slot holds up to 3 tokens total, any mix," above), now extended to every
consumable so there's only one number to remember at the table, not one per item. This replaces
the old Potion-specific `POTION_STACK_SIZE = 2` cap with 3, and a single slot can hold any mix
of Potions, the new consumables below, and even Quest Loot tokens together. Deliberately not a
balance concern at the starting 2-slot Bag: a fresh hero doesn't have the Gold to buy enough of
this stuff to feel the crowding before their first Bag Upgrade anyway.

**New Bag-slot consumables (design intent, checkpointed 2026-08-22 — not yet built in the
simulator or wired into the Purchase Queue/Town seam).** Four Gold-purchasable items, stacking
3-to-a-slot under the rule above, none stackable with Food:

- **Scroll of Vanquishing (5 Gold):** used instead of pulling — the declared mob is defeated
  automatically, no cards played, hero takes 0 damage. Still grants the normal +1 Gold and the
  Node's loot (reuses the ordinary win path, not a separate one) and still costs the pull's one
  turn. **Standard-tier mobs only, never Elite/Boss** — a flat, printed restriction, not a
  hidden conditional, that keeps the exact-solver Elite/Boss fights meaningful rather than
  buyable-around. Priced low relative to an earlier draft (was 9 Gold) after checking real
  per-pull outcome rates directly: across all 9 classes, death is under 1% per attempted pull
  and flee is only 1.5-8.7% (measured via `board_engine._pull_and_resolve`, 120-turn runs, 8
  seeds/class) — most pulls a Scroll gets used on would have been won anyway, so it isn't the
  run-defining purchase a higher price implied.
- **Smoke Bomb (3 Gold):** used once a mob is revealed to guarantee a flee instead of resolving
  combat — 0 damage, 0 Gold, 0 loot, the pull/crossing just ends, still costs the turn. Its real
  value is on **Border crossings specifically**: unlike an ordinary Node (already free to just
  not declare), `resolve_border_crossing` has no decline path once the toll is committed to —
  this is a genuinely new lever there, not a reskin of something already free elsewhere.
- **Whetstone (4 Gold):** used before a pull, grants **+1 damage and +1 Block to every card
  played for that entire pull** (all 3 rounds), then consumed. One combined item rather than
  separate damage/Block versions, matching this project's preference for as few distinct
  at-the-table item types as the design actually needs.
- **Preserving Charm (5 Gold):** used at Town, resets one active quest's decay stage back to 0
  without needing to have collected its loot — doesn't cost the Town visit's one turn, folding
  into the visit the same way Food/Potion restock already does. The only one of the four not
  about combat risk at all; it protects quest Gold against the decay mechanic instead.

**Random-drop extension, stated intent only, deliberately unparameterized.** Beyond straight
Gold purchase, winning a pull (any pull, possibly at better odds for Elite/Boss-tier mobs)
should be able to drop one of the four items above for free. Exact drop rates, whether a drop
replaces or stacks on top of the existing +1 Gold win reward, and whether rates vary by mob
tier are all real open questions, not decided here — this needs its own pass (likely a
simulator sweep) once the Gold-purchase prices above are validated in play, not guessed
alongside them.

**Risk policy (locked default): consumable-before-risk, always.** Exact constants:
`RISK_TOLERANCE = 0.15` (the fraction of hands allowed to be lethal *when this pull would
complete a quest* — a real player wouldn't refuse a pull just because one bad hand exists among
many) and `RISK_TOLERANCE_BASE = 0.0` (otherwise — effectively zero lethal-hand risk allowed).
The higher tolerance is only used as a genuine last resort, when no unused Food/Potion is
available in the Bag. Roughly halves average deaths per trip-chain versus the old "risk it
whenever a quest completes this turn" default, with no corresponding rise in worst-case decay.

**Death and corpse recovery (locked rule, not yet in this doc before now).** If a pull kills
the hero, a corpse marker is left at that node and the hero **respawns at full Max HP in
whichever Town is closest** — clarified 2026-08-20 now that both Zones have Town: this means
the Town in the same Zone as the death node, not necessarily "Zone 1's Town" the way it would
have under the old single-Town map. Every Bag slot holding anything (loot or an unused
consumable) **locks** — its contents stop counting toward quests and can't be added to — and
**ALL currently equipped items break and flip face-down** (requiring Blacksmith repair in Town
for Gold equal to Item Level; see Section VIII.3 for durability rules) — and
**every quest currently in the active log takes an immediate 2-stage decay hit, with no
exception for a quest that's already fully collected and ready to turn in** (versus 1 stage for
a normal incomplete return), still capped at "nothing." Travel from the respawn Town back to
the death node is free (Golden Rule 1, same as any other intra-Zone movement) and costs no turn
on its own — the trip *after* a death is forced to spend its first pull back at the death node
(a fresh random mob from that node's tier, no loot either way) before any normal questing or
looting resumes; the hero only needs to **survive** that pull — win or flee both count, killing
the mob is not required — to unlock every previously locked slot. Dying on the recovery pull
triggers the exact same handling again — a real spiral risk, not special-cased away. If the hero
can't safely attempt it (no consumable available to make the risk acceptable), the trip ends
with the corpse still unrecovered.

**Decaying Bounties, and the "days passing" flavor now attached to it.** Players hold exactly
3 Quests at all times. Decay is assessed at the **end of each trip**, not on departure: any
quest still incomplete once a trip concludes downgrades one Gold-ladder tier
(Gold → Silver → Bronze → nothing). **Reframed as time passing, with zero numbers changed:**
each decay stage represents one day lost — a normal incomplete return costs the quest-giver's
patience one day (1-stage decay), a death costs two full days (the already-locked 2-stage
death decay, above) specifically because two days are spent getting back out to recover the
corpse before questing can resume. This is flavor only, not a new mechanic, but it gives the
existing "why does death decay twice as fast" rule a concrete, intuitive reason instead of an
abstract one. **A quest's first trip can never be decayed before or during that attempt** —
this isn't a bolted-on grace period, it falls directly out of the mechanism above: decay only
ever applies to a quest that's *still* incomplete once a trip is over, and a quest completed
within its own first trip lands in the turn-in branch instead of the decay branch, every time.
This is why the "quicker half" of completions land at full Gold-tier 100% of the time (see
Designer's Notes) — without this,
finishing any quest at full Gold would be structurally impossible, not just unlikely. XP is
flat and doesn't decay (`base_xp = required`, 1 XP per loot item the quest asks for) — only the
Gold bonus erodes, so pushing your luck risks the bonus, never the guaranteed baseline progress.

**Level 1 quest table (`sim/macro_sim.py`'s `QUESTS`), compressed and non-replenishing
(revised 2026-08-21).** All 8 Level 1 quests flattened to the same shape — every original
required=2/3/4 quest already shared the same Gold ladder, so this costs nothing in Gold, only
removes wasted turns; the two former required=5 quests lose their higher ladder too, a
deliberate choice to flatten everything uniformly:

| Quest | Loot required | XP | Gold ladder (Gold/Silver/Bronze/nothing) |
|---|---|---|---|
| Pilfered Goods | 2 | 2 | 4 / 2 / 1 / 0 |
| Syndicate Ledger | 2 | 2 | 4 / 2 / 1 / 0 |
| Contraband Crates | 2 | 2 | 4 / 2 / 1 / 0 |
| Stolen Signet | 2 | 2 | 4 / 2 / 1 / 0 |
| Smuggled Cargo | 2 | 2 | 4 / 2 / 1 / 0 |
| Forged Ledger | 2 | 2 | 4 / 2 / 1 / 0 |
| Plundered Chest | 2 | 2 | 4 / 2 / 1 / 0 |
| Buried Treasure | 2 | 2 | 4 / 2 / 1 / 0 |

A hero draws exactly 3 of these 8 at random as a starter batch and does **not** get a
replacement as each is turned in — "Players hold exactly 3 Quests at all times" (above) only
holds during this starter batch's own first quest-giving; the log shrinks toward 0 as quests
complete, unlike the old always-refilled system. Completing all 3 always nets exactly 6 XP
(3 x 2), which is deliberately identical to the Level 2 XP threshold (see below) — reaching 6
XP *is* reaching Level 2, by construction. Once exhausted, Zone 1/2 stops offering quests
permanently for that hero; Level 2 quests (Zone 3/4, still a placeholder pool pending real
balance — see the Zone 3/4 section) take over from that point on, with normal replenishment.

**+1 Gold per won pull, on top of quest loot if applicable (locked 2026-08-21).** Applies to
any pull that wins outright — a quest-node pull, a corpse-recovery pull, or a Border Node toll
crossing — never a flee, the same win-only standard across all three. Applies at both Level 1
and Level 2. Measured effect at the Level 2 checkpoint: Gold there rose from ~11-13 to ~17-18,
pooled and consistent across the roster — see `MACRO_LOOP_GUIDE.md`'s own entry for the full
derivation and the methodology note on why this was checked at a real, bounded checkpoint
rather than an arbitrary long trip-count average.

**Bag Upgrade:** 16 Gold, expands the Bag from a 3×3 grid (9 slots) to a 5×3 grid (15 slots, +6 slots total). Sized to comfortably hold both raw crafting materials and multiple active quest token turn-ins.

## VII. The Game Round

This is the definitive, chronological flow of a single Game Round.

### Phase 1: The Deal & Preparation
- **The Deal:** Only occupied Zones are dealt to. (If a hero is standing on a Border Node, *both* Zones connected to that border are dealt to).
  - Every Node in an occupied Zone is dealt 1 fresh Mob Card face-up.
  - If a Node does *not* currently have a Gathering Token, 1 fresh Gathering Token (Herb, Ore, Skin) is dealt to it.
- **Preparation:** Now that players can see the exact board state, they may use items from their bag (e.g., healing with Potions, buffing with a Whetstone) before deciding where to commit.

### Phase 2: Move & Declare
- **Movement is free.** Moving your pawn to any reachable node does not cost an Action.
- **Flight Paths:** Generic point-to-point travel between any two connected Flight Master nodes costs 2 Gold, but is still considered free movement.
- **The Action:** Players simultaneously move their pawn and declare exactly one Action for the Round:
  - **Quest Node:** Declare intent to fight the visible mob and claim its loot.
  - **Town:** Declare intent to conduct Town business.
  - **Class Trainer:** Declare intent to purchase upgrades.
  - **Border Node:** Declare intent to cross a border (the Action is a Scouted Pull toll).

> [!NOTE]
> **Simultaneous Play:** Everything from Phase 3 onward (Resolution, Combat, Rewards, Cleanup) happens completely simultaneously for all heroes. There is no turn order outside of the specific Priority checks for contested nodes.

### Phase 3: Resolution (Non-Combat & Initiation)
- **Town & Trainer Actions:** Players who declared Town or a Class Trainer resolve their business now (buy, sell, turn in quests, buy upgrades). Their action is now complete until Cleanup.
- **Uncontested Nodes:** If only one player declared a specific Quest Node, they lock in to fight the visible mob.
- **Contested Nodes:** If two or more players declare the exact same Quest Node, they enter the Initiation Flow:
  1. **Priority Order:** The player with the highest priority chooses Peace or War.
  2. **War (PvP):** The Initiator challenges a specific player. The PvP Duel initiates.
     - *Bystander Rule:* The PvE mob ignores the duelists. The highest-priority non-dueling player gets to fight the PvE mob.
  3. **Peace (PvE):** The highest priority player claims the visible mob. Everyone else who declared that node suffers a **Blind Pull** (draws a fresh mob from the deck with no preview).

### Phase 4: Combat
- **The Reaction Window (PvP Only):** Because PvP introduces sudden new information (a human opponent), duelists have a brief window to use non-Food consumables (e.g., Potions, Smoke Bombs) right before combat begins.
- Players resolve their PvE pulls (or PvP duels) simultaneously using the standard 3-round card combat system.

### Phase 5: The Post-Combat Reward Phase
For every player that won a PvE combat pull, resolve rewards in this exact order:
1. **The Base Payout:** Gain +1 Gold.
2. **The Quest Drop:** If the Node matches your active quest color, claim 1 Quest Token (occupies 1 Bag slot).
3. **The Board Drop (Gathering):** If you fought the visible mob, claim the Gathering Token sitting on that Node (occupies 1 Bag slot). *(Blind Pulls do not award gathering tokens).*
4. **The Mob Drop (Random Loot):** If the defeated Mob Card has a Loot Drop icon, draw 1 card from the Zone-appropriate Loot Deck. (Elite/Boss mobs have a Double Loot icon; draw 2 cards). These items occupy 1 Bag slot each.

### Phase 6: Cleanup
- All unbeaten Mob Cards in occupied zones are swept to the discard pile. (They do not persist).
- **Sticky Gathering:** Gathering Tokens are **not** swept. If no one claimed them, they remain on the board for the next Round.

## VIII. Progression Architecture & Tier Transitions

### 1. The Even-Numbered Tier Gate Rhythm
Progression across the 6 Zones is driven by the Quest Engine, moving through even-numbered gate zones:
* **Zone 2 Gate (Level 1 → Level 2 Transition):**
  - **Threshold:** Complete 3 Level 1 quests (6 XP). Zone 1 & 2 quest markets exhaust.
  - **Zone 2 Trainer (Port Ironguard):** Grants mandatory Level 2 skill upgrade + Rank 2 Guild Seal + issues the **Primer Quest: [Vanguard Dispatch]**.
  - **Arrival at Town 3/4:** Turning in the Dispatch awards +2 Gold travel stipend and unlocks the Level 2 Quest Market (Zones 3 & 4) via the Rank 2 Seal.
* **Zone 4 Gate (Level 2 → Level 3 Transition):**
  - **Threshold:** Complete Level 2 quests reaching Level 3 XP milestone (~12–14 total XP).
  - **Zone 4 Trainer (The Vanguard Camp):** Grants mandatory Level 3 skill upgrade + issues the **Capstone Boss Quest: [The Citadel Commission]**.
  - **The Landmark Encounter:** The hero confronts the Level 2 Boss at *The Gleaming Citadel* or *Sunward Throne*.
  - **Arrival at Town 5:** Resolving the landmark combat (Win or Fail-Forward) immediately delivers the hero to Town 5, unlocking the Level 3 Quest Market.
* **Zone 6 Gate (Level 3 → Endgame):** Final Boss confrontation.

### 2. Quest-Driven Gating (Open Map, No Chokepoints)
- **Map Freedom:** The map graph remains completely open, multi-routed, and interconnected (multiple border crossings, loops, and flight paths). The landmark is a destination, not a physical bottleneck.
- **Quest Enforcement:** Town 5’s Council strictly refuses to issue Level 3 contracts to unverified wanderers. The Level 3 Quest Market remains locked until the player turns in the completed *Citadel Commission*. Sequence-breaking is impossible.
- **Modularity:** In casual or speedrun variants where boss fights are omitted, the Trainer simply issues a standard courier dispatch to Town 5 instead of the boss quest.

### 3. Boss Gates: Triumph vs. Fail-Forward Resolution
Every player must initiate combat against the Gatekeeper when attempting the Capstone Quest (in solo, competitive, or co-op). Pacing never deadlocks, and all outcomes grant automatic express transit to Town 5 upon resolution.

Visiting Town automatically restores hero HP to full, and the Trainer purges the completed Capstone Quest from the log, rendering previous Town arrival HP and overland quest decay purely symbolic at this milestone. Instead, the real physical and economic differentiation between failure modes is governed by **Equipment Durability & Blacksmith Repair**:

| Outcome | Tabletop Narrative | Equipment State | Economic Impact | Rewards Claimed |
| :--- | :--- | :---: | :---: | :--- |
| **Triumph (Win)** | Citadel gate breached in victory | Refreshes to Ready | **+5 Gold** Bounty | • **The Level 3 Dungeon Key**<br>• **Boss Trophy** (+2 Bounty credits)<br>• **+5 Gold** Bounty |
| **Survival Timeout (Fail & Survive)** | Repelled by boss; tactical retreat | Refreshes to Ready | **0 Gold** (No repair fee) | • **Zero bonus spoils** (No Key, No Trophy, No Gold)<br>• Level 3 overland quests still unlock |
| **Death Failure (Crushed)** | Dragged from the rubble by scouts | **ALL Equipment Flipped (Broken)** | **−Gold repair fee at Town Forge** | • **Zero bonus spoils** (No Key, No Trophy, No Gold)<br>• Level 3 overland quests still unlock |

#### Equipment Durability & Repair Mechanics (Locked Default):
1. **Exhaustion (In the Field):** Using an equipment card's active trigger in combat rotates (taps) the card 90°. Visiting Town refreshes all exhausted equipment back to Ready (upright) for **free**.
2. **Broken on Death (Flipped Face-Down):** If a hero dies (HP $\le 0$) during any encounter (overland pull, dungeon room, or boss gate), **ALL currently equipped items are broken and flipped face-down**.
3. **The Blacksmith Forge:** Broken (face-down) equipment provides no stats or triggers. To restore a broken item upright, the hero must pay the Town Blacksmith a repair fee equal to the **item's level in Gold** (e.g. Level 1 item = 1 Gold, Level 2 item = 2 Gold). If a player has 0 Gold, equipment remains face-down until Gold is earned from overland combat (the 6-card hero deck still functions, preventing soft-locks).

> [!IMPORTANT]
> **Durability & Repair Balance Sweep (Documented for Future Empirical Testing):**
> Two specific levers are documented here for future simulation and playtest calibration:
> 1. **Break Scope:** Does death break **all** equipped items (current working rule), or should it only break the **single highest-level unbroken item** to soften the death penalty for gear-heavy heroes?
> 2. **Repair Cost Formula:** Is the optimal gold fee equal to the item's printed level ($\text{Fee} = \text{Level}$), or half rounded up ($\lceil \text{Level} / 2 \rceil$), or a flat fee?
> These levers will be formally evaluated in the macro-economy simulator once equipment progression and crafting curves are integrated into the full trip loop.

### 4. Zone 4 Tier Gate Boss Trio (Locked Specifications)
> [!NOTE]
> **Flavor / Lore Note:** Boss names, titles, and lore descriptions below are **placeholders** and will receive a dedicated narrative and thematic polish pass. The mechanical stats, action patterns, HP thresholds, and phase rules are **locked**.

When a Level 2 hero attempts the Capstone Quest (*The Citadel Commission*), they draw **1 of 3 Gatekeeper Bosses at random** (or draw 2 and pick 1 if spending a **Scout Token**). Under the locked V2 calibration, the bosses average **81.1% roster win rate**, create natural archetype divergence with **13%–40% class spreads**, demand razor-thin survival (**1.8–4.2 HP average ending health** on tough matchups), and restrict **Block exclusively to Melee rounds** (0 Block on all Ranged rounds).

#### Phase Rules & The Phase 1 Ruling:
1. **6 Rounds Continuous:** Combat is split into two 3-round bouts (Phase 1 = Rounds 1–3, Phase 2 = Rounds 4–6). The hero starts at full Max HP. Surviving Hero HP carries directly into Phase 2; no food, resting, or consumables are permitted between phases.
2. **Phase 1 Completion Requirement (The P1 Knockout Rule):**
   - The hero **must reduce Phase 1 HP to $\le 0$ within 3 rounds** to advance to Phase 2.
   - **If the hero fails to deal sufficient damage in Phase 1:** The hero **loses the entire encounter immediately on Round 3** (Damage Failure). The boss card does not flip, Phase 2 is not entered, and the hero suffers Fail-Forward express transit to Town 5 at 1 HP.
   - *Phase 1 Mortality:* Phase 1 incoming attack output is calibrated strictly for attrition; Hero death rate in Phase 1 is **0.0% across all 9 classes**.
   - *Phase 1 Damage Failure Frequency:* Across the roster, failing Phase 1 due to insufficient burst averages **~10%–12%** (ranging from 0%–4% for high-burst classes like Wizard/Necromancer, to 8%–9% for Warrior/Paladin/Cleric, up to 15%–20% on Rogue/Druid when drawing poor damage hands).
3. **Phase 2 Transition & Resolution:**
   - If Phase 1 is defeated, the player reshuffles their 6-card deck, draws a fresh 4-card hand, flips the boss card to its Phase 2 Unleashed form, and resolves Rounds 4–6.
   - **Triumph:** Boss Phase 2 HP reduced to $\le 0$ by Round 6 and Hero HP $> 0$.
   - **Survival Death:** Hero HP drops to $\le 0$ during Phase 2 (averages ~3%–6% roster-wide; up to 26%–34% on squishy casters facing their nemesis boss).
   - **Damage Timeout:** Boss Phase 2 HP $> 0$ after Round 6 (averages ~8%–14% roster-wide).

#### Boss Evolution: V1 Baseline vs. V2 Asymmetric Lethality
* **The Flaw in V1 (The Homogenous Baseline):** In early design passes, all three candidate bosses were tuned to hover at a uniform ~77.5% roster win rate with tight spreads. Under closer scrutiny, this created three critical problems:
  1. *Lack of Mechanical Identity:* Drawing Boss A vs. Boss B felt cosmetic because matchup spreads were muted.
  2. *Paladin/Warrior Invincibility:* Tanks crushed all three bosses with 86%–99% win rates, leaving them with zero challenging encounters.
  3. *Artificial Safety & High Ending HP:* Ending HP averaged 4.6 HP (and 6.5–7.8 HP on tanks), with Death accounting for only ~5% of failures. Phase 1 felt like a mindless DPS race rather than a life-or-death survival puzzle.
* **The V2 Design Philosophy (Asymmetric Distance & High Lethality):**
  1. *Archetype Polarization:* Each boss is tuned around QUEST's inherent mechanics (`grants_range` evasion vs. Melee, Melee Plating vs. Ranged magic, burst vs. attrition), creating a 13%–40% spread per class. Every hero has a favored boss (~80%–96%) and a dreaded nemesis (~40%–79%).
  2. *Skin-of-Your-Teeth Survival:* Attack pressure is front-loaded and intensified (Phase 1 hits for 11–13; Phase 2 hits for 13–14), pulling winning health down to **1.8–3.5 HP**.
  3. *Phase 1 Tension:* Because entering Phase 2 with under 6 HP is near-fatal, Phase 1 forces players to actively balance dealing damage with preserving health.

##### Side-by-Side Boss Evolution Table

| Boss Profile | V1 Pattern (Homogenous) | V1 Total Threat | V2 Pattern (Asymmetric & Lethal) | V2 Total Threat | Design Rationale & Mechanical Shift |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Boss 1 (Inquisitor)** | **P1:** (3,0)-(3,2)-(4,0) `R-M-R` [10 HP]<br>**P2:** (4,0)-(4,1)-(4,0) `R-M-R` [10 HP] | P1: 10 Atk, 2 Blk<br>P2: 12 Atk, 1 Blk | **P1:** (4,0)-(3,1)-(4,0) `R-R-R` [10 HP]<br>**P2:** (4,0)-(4,0)-(5,0) `R-R-M` [10 HP] | P1: 11 Atk, 1 Blk<br>P2: 13 Atk, 0 Blk | Converted P1 to **Pure Ranged (R-R-R)** to completely deny `grants_range` evasion. Added Atk 5 melee execute in R6. Directly punishes squishy casters (Necro win drops to 52.9% with 34% deaths; Wizard drops to 69.6% with 26% deaths) while heavy physical armor tanks (Paladin 96%, Warrior 94%) soak the rays. |
| **Boss 2 (Colossus)** | **P1:** (2,1)-(4,0)-(4,0) `M-R-M` [11 HP]<br>**P2:** (4,0)-(4,0)-(5,0) `R-M-R` [10 HP] | P1: 10 Atk, 1 Blk<br>P2: 13 Atk, 0 Blk | **P1:** (3,2)-(5,0)-(4,0) `M-M-R` [10 HP]<br>**P2:** (5,0)-(4,1)-(4,0) `M-M-R` [10 HP] | P1: 12 Atk, 2 Blk<br>P2: 13 Atk, 1 Blk | Shifted into the **Heavy Granite Titan**. Introduced R1 Block 2 Melee and dual 5-damage crushing melee slams (R2, R4). Punishes physical melee brawlers and low-burst attrition (Cleric 40.9%, Druid 53.0%, Rogue 61.0%, Ranger 69.8%, Paladin 79.6%). Highly vulnerable to ranged kiting and magic pierce (Wizard 85.5%, Necromancer 81.0%). |
| **Boss 3 (Eclipse)** | **P1:** (4,0)-(3,2)-(3,0) `R-M-R` [10 HP]<br>**P2:** (4,1)-(4,0)-(4,0) `M-R-M` [10 HP] | P1: 10 Atk, 2 Blk<br>P2: 12 Atk, 1 Blk | **P1:** (4,1)-(4,0)-(5,0) `M-R-M` [10 HP]<br>**P2:** (4,0)-(4,1)-(6,0) `R-M-M` [9 HP] | P1: 13 Atk, 1 Blk<br>P2: 14 Atk, 1 Blk | Tuned into the **Twilight Duelist**. Features dual melee parries (R1, R5) escalating into a devastating **Atk 6 Guillotine** in R6. Drops Phase 2 HP to 9 to allow burst victory. **Breaks Paladin invulnerability** (Paladin win rate drops from 95% down to 79.7% with 9.3% death rate). Favored by ranged burst (Wizard 90.2%, Necro 89.8%, Ranger 83.4%); punishes slow stalling (Cleric 50.8%, Runecaster 70.4%). |

#### Boss 1: High Inquisitor Malakor / The Sunward Archon *(The Holy Mage-Hunter)*
*Radiant prelate radiating continuous holy light. Heavy Ranged magic attacks deny distance evasion, directly challenging low-HP casters while physical armor and heavy shields soak the rays.*
* **Phase 1: The Radiant Bulwark [10 HP]**
  * Round 1: Atk 4, Blk 0 (`ranged` — *Holy Ray*)
  * Round 2: Atk 3, Blk 1 (`ranged` — *Consecrated Radiance*)
  * Round 3: Atk 4, Blk 0 (`ranged` — *Solar Flare*)
  * *P1 Total Threat:* 11 Raw Ranged Damage, 1 Block.
* **Phase 2: Unleashed Avatar of Light [10 HP]**
  * Round 4: Atk 4, Blk 0 (`ranged` — *Pillar of Radiance*)
  * Round 5: Atk 4, Blk 0 (`ranged` — *Sunward Searing*)
  * Round 6: Atk 5, Blk 0 (`melee` — *Avatar's Wrath*)
  * *P2 Total Threat:* 13 Raw Damage (8 Ranged, 5 Melee), 0 Block.
* **Performance:** **84.8% Roster Avg** | **4.5 Avg End HP** | **Favors: Paladin (96.0%), Warrior (94.4%), Druid (93.3%)** | **Dreaded by: Necromancer (52.9% — 34% Death), Wizard (69.6% — 26% Death)**

#### Boss 2: Aethelgard the Sun-Forged / Citadel Colossus *(The Granite Titan)*
*Ancient granite titan. Crushing 5-damage melee slams and heavy stone plating shatter close-combat brawlers, but slow movement leaves it vulnerable to ranged artillery and magic pierce.*
* **Phase 1: Granite Sentinel [10 HP]**
  * Round 1: Atk 3, Blk 2 (`melee` — *Heavy Stone Bracing*)
  * Round 2: Atk 5, Blk 0 (`melee` — *Crushing Fist Slam*)
  * Round 3: Atk 4, Blk 0 (`ranged` — *Prismatic Eye Beam*)
  * *P1 Total Threat:* 12 Raw Damage (8 Melee, 4 Ranged), 2 Melee Block.
* **Phase 2: Superheated Molten Core [10 HP]**
  * Round 4: Atk 5, Blk 0 (`melee` — *Molten Hammer*)
  * Round 5: Atk 4, Blk 1 (`melee` — *Core Reinforcement*)
  * Round 6: Atk 4, Blk 0 (`ranged` — *Thermal Steam Vent*)
  * *P2 Total Threat:* 13 Raw Damage (9 Melee, 4 Ranged), 1 Melee Block.
* **Performance:** **73.1% Roster Avg** | **4.2 Avg End HP** | **Favors: Wizard (85.5%), Necromancer (81.0%), Warrior (80.9%)** | **Dreaded by: Cleric (40.9%), Druid (53.0%), Rogue (61.0%), Ranger (69.8%), Paladin (79.6%)**

#### Boss 3: Cheryl the Sun-Dethroned / Eclipse Sovereign *(The Twilight Duelist)*
*Fallen solar monarch. Parries with dual eclipse rapiers in melee, dropping guard to unleash sweeping dark solar magic before executing stalling heroes with a Round 6 Guillotine.*
* **Phase 1: Dusk Rapier [10 HP]**
  * Round 1: Atk 4, Blk 1 (`melee` — *Twin Rapier Parry*)
  * Round 2: Atk 4, Blk 0 (`ranged` — *Eclipse Javelin*)
  * Round 3: Atk 5, Blk 0 (`melee` — *Shadowstep Thrust*)
  * *P1 Total Threat:* 13 Raw Damage (9 Melee, 4 Ranged), 1 Melee Block.
* **Phase 2: Twilight Ascendant [9 HP]**
  * Round 4: Atk 4, Blk 0 (`ranged` — *Black Sun Nova*)
  * Round 5: Atk 4, Blk 1 (`melee` — *Dusk Guard*)
  * Round 6: Atk 6, Blk 0 (`melee` — *Twilight Guillotine!*)
  * *P2 Total Threat:* 14 Raw Damage (10 Melee, 4 Ranged), 1 Melee Block.
* **Performance:** **85.4% Roster Avg** | **4.5 Avg End HP** | **Favors: Wizard (90.2%), Necromancer (89.8%), Warrior (85.8%), Ranger (83.4%)** | **Dreaded by: Cleric (50.8%), Runecaster (70.4%), Druid (70.4%), Paladin (79.7%)**

#### Rebalanced Cross-Boss Matchup Matrix (Level 2 + 2 Upgrades, Unequipped)

| Class | Boss 1 (Inquisitor) | Boss 2 (Colossus) | Boss 3 (Eclipse) | 3-Boss Average | Spread | Strategic Profile |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Warrior** | **94.4%** | 80.9% | 85.8% | **87.0%** | **13.5%** | **Favors B1**, Dreads B2 *(Colossus slams test physical armor)* |
| **Paladin** | **96.0%** | 79.6% | 79.7% | **85.1%** | **16.4%** | **Favors B1**, **Challenged by B2 & B3** *(Guillotine & Slams crack shields)* |
| **Wizard** | 69.6% | 85.5% | **90.2%** | **81.8%** | **20.6%** | **Favors B3**, **Dreads B1** *(Holy rays bypass range evasion)* |
| **Rogue** | **88.1%** | 61.0% | **88.1%** | **79.1%** | **27.1%** | **Favors B1 & B3**, **Dreads B2** *(Stone plating halts combo finishers)* |
| **Ranger** | 74.8% | 69.8% | **83.4%** | **76.0%** | **13.6%** | **Favors B3**, **Dreads B2** *(Colossus stone armor halts arrows)* |
| **Necromancer**| 52.9% | 81.0% | **89.8%** | **74.6%** | **36.9%** | **Favors B3**, **Dreads B1** *(Cannot evade ranged rays; dies 34%)* |
| **Druid** | **93.3%** | 53.0% | 70.4% | **72.2%** | **40.3%** | **Favors B1**, **Dreads B2** *(Nature damage struggles vs Colossus)* |
| **Runecaster** | 57.2% | 58.1% | **70.4%** | **61.9%** | **13.2%** | **Favors B3**, **Dreads B1 & B2** |
| **Cleric** | **77.8%** | 40.9% | 50.8% | **56.5%** | **36.9%** | **Favors B1**, **Dreads B2** *(Slow attrition gets overwhelmed)* |
| **ROSTER AVG**| **84.8%** | **73.1%** | **85.4%** | **81.1%** | **11.7%** | **Clear Archetype Distance & High Threat** |

*Superlatives:* Lowest Average: Cleric (56.5%); Highest Average: Warrior (87.0%); Lowest Absolute: Cleric on B2 (40.9%); Highest Absolute: Paladin on B1 (96.0%); Smallest Spread: Runecaster (13.2%); Widest Spread: Druid (40.3%).

#### Tier Gatekeeper Qualification & Encounter Rules (Locked 2026-10-01)
1. **The 6 XP $\rightarrow$ 14 XP Progression Curve:**
   - **Level 1 Clear (6 XP):** Reaching 6 XP unlocks Level 2 and awards the class's free Mandatory Level 2 skill swap.
   - **Level 2 Gate Qualification (14 XP):** A hero must earn **+8 XP in Level 2** (reaching **14 XP total**) before the Class Trainer offers the Tier Gatekeeper Boss Quest.
2. **Behavioral Archetypes (Speedrun vs. Completionist):**
   - *Speedrunner / Aggressive:* Upon reaching 14 XP, immediately pivots to Town, gears up, and challenges the Gatekeeper Boss.
   - *Completionist / Prepared:* Finishes their active Level 2 quest board to maximize Gold payouts on the `4 -> 6 -> 9 -> 12` ladder, craft full gear, and purchase remaining Trainer skills before facing the boss.
3. **The Anti-Grind Ceiling (No Infinite Level 2 Camping):**
   - A hero cannot stay in Level 2 soaking quests endlessly. Three interlocking tabletop rules enforce this:
     - *Economic Equilibrium:* Pulling bare mobs to grind gold costs more in Food consumption than mob loot pays out (`P_food >= Pulls * Income`, per `MACRO_LOOP_GUIDE.md`).
     - *Finite Quest Board:* Level 2 Town Quest markets do not refill indefinitely once the Gatekeeper Quest is unlocked. Once active Level 2 quests are turned in, the board directs the hero to the Boss Gate.
     - *XP Cap:* XP earned beyond 14 XP in Level 2 does not carry into Tier 2 until the Gatekeeper Boss is conquered.
4. **Scout Tokens (Pathfinder Intelligence):**
   - Tabletop reward tokens earned from specific tracking/recon quests or exploration landmarks.
   - *Effect:* A hero may spend a Scout Token when encountering a mob pull OR challenging the Tier Gatekeeper Boss to **draw 2 cards from the deck and choose 1**, giving players agency to seek their favored boss matchup or avoid their feared nemesis.

### 5. Key-Gated Dungeons (Level 3+)
- **Push-Your-Luck Gauntlet:** Dungeons are self-contained 3-room gauntlets (Room 1: Entry → Room 2: Depths → Room 3: Vault Boss) featuring cash-out decisions after each room. Wiping inside forfeits all unbanked dungeon spoils.
- **Strict Scarcity via Keys:** Dungeons require physical 1×1 **Dungeon Key tokens** to enter, primarily earned by conquering the Tier Gatekeeper Boss (with rare overland quest-chain alternatives).
- **Lateral Power, Not XP Bloat:** Dungeons do not award disproportionate XP. They grant **lateral capabilities** (Unique Legendary Relics, Tier 3 Crafting Materials, and dense Gold piles). This preserves **overland questing as the ~80% primary game loop** while keeping dungeons as high-stakes **~20% capstone expeditions**.

### 6. Technical Pacing Target
- **Full-Game Pacing Target (locked 2026-08-22):** Level 1 to Level 6 clear in **~90 turns or less**.
- **Deck Limit (locked):** Strict 6-card limit. Progression is always **1-for-1 card swap** (upgrading a base card into a purchased/trainer card), never additive growth.
- **Purchased Upgrade Randomization (locked 2026-08-23):** Beyond the free mandatory upgrade, remaining purchased upgrades draw from a randomized hero-specific order to prevent strategic convergence.

## IX. Component & Physical Implementation

What an actual physical prototype needs, based on the current locked rules above:

- **Per-class deck:** 6 unique cards. Warrior's cards print Guardian/Champion values as
  mirrored text on opposite card ends (Section II) — no separate stance token needed.
- **Mob cards:** HP plus a 3-round `(ATK, Block)` pattern, printed and fully visible (no hidden
  mob info, ever). A melee/ranged type icon (Section IV).
- **HP trackers:** one per hero, plus a shared mob HP tracker per pull (or per active mob, in a
  co-op multi-mob fight — Section V).
- **Bag:** 3×3 physical grid (9 slots to start, upgradeable to 5×3 / 15 slots). Food is a 2×2 tile physically occupying 4 slots, leaving 5 open 1×1 slots. Every other item (Potions, Quest Loot tokens, Gathering Materials, consumables) occupies exactly 1 slot. Nothing stacks.
- **Quest Loot tokens:** one single generic component per color (Red/Green/Blue), not a
  distinct token per zone/quest — locked 2026-09-01, resolving the earlier "printed color vs.
  colored marker" ambiguity: **the hero's tracker board (see below) has exactly 3 colored quest
  slots, and the physical quest card itself is what sits in a slot** — no separate token or
  marker on the card. Whichever slot a card occupies IS that quest's color for as long as it's
  active on that hero's board; a completed pull's loot token is just whichever color the
  satisfied quest's card currently sits in.
- **Hero tracker board:** one per player — HP dial, whatever else is personal to that hero (see
  `OPEN_QUESTIONS.md`'s "Per-class matchup info" entry), and **3 colored quest slots** (Red/
  Green/Blue), giving `ACTIVE_QUEST_COUNT = 3` a physical home at the table instead of being
  purely a simulator invariant. **Slot assignment, locked 2026-09-01:** free choice — when a
  hero picks up a new active quest, they place its card into any currently-empty slot. No fixed
  assignment order. A slot empties (and its color becomes available again) when that quest is
  turned in or dropped.
- **Gold and XP counters.**
- **Aggro reference (co-op only):** each card's printed Aggro value (0-4) is enough on its own —
  no extra token system needed beyond what's already printed on the card.

## Designer's Notes

This section points to where the reasoning/derivation history actually lives, rather than
duplicating it here — same split AGGRO's own Core doc uses between its numbered rules and its
"AI PRE-EMPTION LOG"/equipment "Open Questions" sections.

- **`SOTG.md`** — AI onboarding: mistakes repeatedly made and caught on this project, simulator
  gotchas, anti-patterns. Read this first, always.
- **`DECK_CONDENSING_GUIDE.md`** — how an AGGRO class's ~10-card kit becomes a legal 6-card
  QUEST kit (what gets cut, what gets reframed, checkpoint discipline).
- **`CLASS_BALANCE_GUIDE.md`** — per-class numeric tuning playbook and the full "locked" history
  for every built class (Warrior through Runecaster), including real bugs found and fixed
  (equilibrium/"cannot die" exploits, hidden domination, damage-floor collapses).
- **`MACRO_LOOP_GUIDE.md`** — how every macro-loop number above (risk policy, quest Gold
  formula, Bag Upgrade price) was actually derived and measured, not guessed.
- **`CARD_REFERENCE.md`** — generated, tabletop-facing card text for every locked class.
  Regenerate via `sim/generate_card_reference.py`, never hand-edit.
- **`CONDENSED_COMBAT.md`** — the original combat-design log (includes superseded drafts kept
  for history — treat this document, not that one, as authoritative for current rules).

**The diagnostic toolkit** (`sim/condensed_trip.py`, run on every locked class before it's
called done): damage floor/ceiling, healing floor/ceiling (forced against an unkillable
zero-ATK mob to isolate sustain), the equilibrium check (Section II), a hand-level
kill-feasibility check (how many of the 15 possible hands can mathematically kill a given mob
at all, regardless of play — caught that Paladin's damage floor of 8 masked 53% of hands unable
to kill certain mobs), a pairwise hidden-domination check (do two cards ever produce genuinely
different outcomes, reported with confidence tiers — `flagged`/`flagged-thin`/`clean`/
`clean-thin` — after an under-sampled "clean" verdict was found resting on only 3 real
observations), a Waste Index (average overkill damage and overheal HP thrown away in real
wins), and tie-density/permutation-variance checks (how many distinct lines share a hand's best
outcome, and how order-sensitive that outcome actually is) as decision-depth measurements.

**Selected war stories worth knowing before re-deriving a similar fix:**
- Wizard's Ice Barricade and Snap Freeze both received small, deliberately narrow compensating
  buffs (Ice Barricade became a Spellweave source; Snap Freeze gained 1 Block) — both provably
  silent against every melee mob (a card that already zeroes melee damage via `grants_range`
  can't be helped further by extra Block underneath it), only ever activating in the specific
  matchup they were meant to patch (low-HP survival tempo, and Scout specifically).
- Cleric's healing kit needed two separate, asymmetric fixes to escape one equilibrium bug:
  cutting Heal/Smite/Call of the Void's heal values broke a Grunt equilibrium but made Call of
  the Void strictly dominant over Smite, so the asymmetry was moved to Call of the Void's own
  damage/heal split instead of re-nerfing further; a second, smaller equilibrium leak against
  the very lowest-ATK mobs was closed with a small mob-side ATK increase instead of another
  card nerf, verified to have zero effect on any other class's win rate first.
- Ranger's Beast Bond persistent Block (Section III) was suspected to be a robotic
  always-play-round-1 card before real numbers existed — measured instead of assumed: chased
  round 1 in 76% of hands, round 2 in 18%, round 3 in 6%, confirming a real strategic pull, not
  a hard lock. Ranger's HP was deliberately kept at 15 over a numerically-tempting drop to 14
  specifically to preserve its Mail-armor identity signal (distinct from the Cloth-tier classes
  sitting at 14) — the remaining balance gap was closed on a card instead.
- Rogue's Cutthroat carries the killing-blow rider specifically as a flavor call, kept even
  after testing showed placing it on Envenom instead would have landed numerically closer to
  the rest of the roster — a deliberate identity choice over a marginal numeric win.
- Memorization risk in a 15-hands-per-class-per-mob combat puzzle was addressed by measuring,
  not assuming: the real (hand, mob) space is over a thousand combinations across the full
  roster, with each exact situation recurring only 2-4 times in a realistic 500-pull session —
  not enough for rote recall — and starting HP itself is a hidden variable that changes the
  optimal line for an otherwise-identical hand/mob pair, breaking simple memorization further.
- The "solved-hand" risk in deterministic OTK combat (once a hand's optimal line is found, does
  the puzzle go stale?) is de-risked for early-to-mid game by the player's own deck being the
  real moving target (a starter deck is small enough that a drawn hand is a large, mostly
  non-repeating fraction of it) rather than by adding mob-side randomness — reserve visible,
  no-hidden-info affixes for high-tier/Final Boss content specifically if this residual risk
  ever needs a direct fix once decks stabilize late-game.

## Open Design Questions

**Note on this section's provenance:** `OPEN_QUESTIONS.md`'s current "Unresolved" section
(items 2, 3, 4, 5) all reference a Winded/OOM + Cast Penalty + Engagement system that Section
III's own history shows was **cut entirely**, not deferred (see "Exhaust dropped entirely" in
`CONDENSED_COMBAT.md`). Those four items are stale and were deliberately **not** carried
forward here — flagging rather than silently dropping them; `OPEN_QUESTIONS.md` itself likely
needs a cleanup pass. The genuinely current open items, pulled from that same file's Resolved
entries where a sub-item is still explicitly marked open:

- **Trigger/frequency for multi-mob nodes** — every co-op node, a designated subset, some
  probability, or something else. Not decided.
- **Elite mob content/stats for real party math** — the solo-baseline Elite trio (HP 12) is
  confirmed too weak once run through the round-robin engine's M=1 case and needs its own
  re-derivation.
- **Tiebreak when two surviving mobs have identical this-round ATK** (round-robin engine,
  Section V) — no rule picked yet.
- **Mixed `mob_type` loot/reward scaling for a multi-mob kill** — not addressed at all.
- **Boss tier is entirely undesigned** — the pooled engine (Section V) has no live use case
  until this exists.
- **Player-chosen quest pool** — `active_quests` is currently randomly sampled by the sim, not
  actually chosen by the player from a curated set.
- **Node-difficulty as a second quest-variation axis** — blocked on Spike-tier mobs, which are
  still empty/deferred.
- **Potion pricing** — never tuned against the current quest economy above.
- **Rogue's death rate and Ranger/Rogue's Bag Upgrade timing (Section VI) are root-caused but
  not fixed** — both trace to a shared defense-floor gap (`CLASS_BALANCE_GUIDE.md`'s "Rogue and
  Ranger's macro-loop risk outlier"). Still open: which fix (kit rider, HP, risk-policy/pricing
  change, or accepted identity), and whether any other class is close to the same cliff without
  yet showing it — no diagnostic currently checks lethal-hand-fraction as a matter of course.
- **Out-of-combat healing** — proposed but not built: classes with a heal kit (currently just
  Cleric) getting a resource-free heal between pulls that doesn't cost a Bag slot or require a
  Town trip. Open question: Cleric-exclusive, or a smaller trickle for every class scaled by
  how much healing is in its own kit?
- **Exhaust/Pet-respawn boundary** — decided in principle (gone until a Town visit, not just
  until the next pull, matching AGGRO's original weight) but not implemented in the simulator.
  Flagged as possibly too punishing; a softer cooldown-token variant short of a full Town visit
  is on the table pending real trip-level data once it's actually built.
- **Loot decay by round count** — a *pull-level* decay idea (loot value drops in steps based on
  how many rounds a pull took to clear), decided in principle as distinct from Decaying
  Bounties (which is trip-level), but not implementable yet since no loot-tier system exists.
- **Durability's escalating-ATK trigger was tested and removed, but the concept isn't
  rejected** — the specific mechanism (a flat +1 stack per pull, universal mob-ATK buff) was
  found to be solving a problem a direct fix (Cleric's Sacred Balance heal cut) already handled,
  and caused real test-process bugs on top of that. The general idea (gear wear, Town-only
  repair) remains open if a new trigger is ever proposed — don't reuse the old one.


**The Tiered Loot Decks (Random Mob Drops)**
Random mob drops are handled via tiered decks of mini-cards (e.g., a Level 1 Loot Deck, a Level 2 Loot Deck), allowing the economy to scale natively as heroes progress to harder Zones. 
- **The Drop Rate:** Exactly 33% of Standard Mob cards (6 per 18-card deck) are printed with a "Loot Drop" icon. For pristine balance, exactly 1 copy of each of the 6 unique standard mobs gets the icon. This ensures that every draw from the Loot Deck is a guaranteed positive reward, rather than stuffing the deck with "Empty Pockets" cards.
- **Elite/Boss Scaling:** Elite and Boss mobs feature a "Double Loot" icon, granting 2 draws from the appropriate Loot Deck upon defeat.
- **Deck Depletion:** The physical Loot Decks should be printed with enough cards to comfortably supply 4 players. If a deck ever runs completely empty, simply reshuffle the discard pile (used Potions, sold items).

**Level 1 Loot Deck Composition (24 Cards) - Locked 2026-09-11**
*The Vendor Trash (Creates Bag Tetris Tension)*
- 3x **Tarnished Silverware** (Sell in Town for 1 Gold)
- 3x **Intact Pelt** (Sell in Town for 2 Gold)
- 2x **Flawless Gemstone** (Sell in Town for 3 Gold)

*The Consumables (The Trip Extenders)*
- 6x **Minor Healing Potion** (Drink for 8 HP)
- 4x **Smoke Bomb** (Free flee / PvP negate)
- 3x **Whetstone** (+1 DMG/Block for one pull)
- 2x **Preserving Charm** (Reset Quest decay)
- 1x **Scroll of Vanquishing** (Auto-win standard pull)

## X. Competitive PvP (The Duel)

**Locked 2026-08-28.** PvP is an opt-in mechanic that occurs strictly during the resolution of Contested Nodes in Competitive Mode. It resolves conflicts between players attempting to claim the same mob and loot.

**Initiation Flow (The Prisoner's Dilemma)**
When two or more players declare the same node simultaneously, resolution proceeds in Priority Order:
1. **Player 1 (Highest Priority) Choice:** Player 1 decides to declare Peace or War.
   - If **War**: PvP initiates. If 3+ players are present, Player 1 must explicitly challenge ONE specific player to a Duel. Player 1 is the Initiator.
   - If **Peace**: The choice passes to the next player.
2. **Subsequent Player Choice:** The next highest priority player decides to declare Peace or War.
   - If **War**: PvP initiates. (They must pick a specific target if 3+ players are present). They are the Initiator.
   - If **Peace**: The choice continues down the line. If all players declare Peace, the highest priority player fights the visible mob (standard priority claim). All other players are subjected to a Blind Pull (draws a fresh mob from the deck with no preview).

*Multi-Hero Bystander Rule:* If 3 or 4 players land on the same node and a Duel is initiated between two of them, the remaining players are NOT involved in the PvP. The PvE mob does NOT flee the node—it ignores the duelists! The highest priority non-dueling player claims the right to fight the visible PvE mob and claim the node's loot. The PvP winner still gets the stolen gold/bonus, but they forfeit the node's specific loot to the bystander.

*Balance Note:* Player 1 has a massive PvE advantage (priority access to the safe, known mob) and will generally decline PvP. Player 2 is disadvantaged in PvE (facing a blind pull) but gets the ultimate tactical choice to force PvP if their hand is strong enough to beat Player 1. This is a deliberate asymmetrical balance.

**The Duel Mechanics (Reveal & Resolve)**
If PvP is initiated (and it is only a 2-player contention), the mob at the node scatters (disappears).
1. **The "Oh Crap" Consumable Window:** Immediately after PvP is locked in, both combatants have a reaction window to use any non-Food consumables. (e.g., pop a Potion to heal 8 HP, use a Whetstone, or drop a Smoke Bomb to instantly flee and negate the duel).
2. Both players draw 4 cards from their unique decks.
3. Each player selects exactly 3 cards and places them face down in sequence (Round 1, Round 2, Round 3).
4. **Reveal & Resolve:** Players reveal their Round 1 card simultaneously and resolve damage. Then Round 2. Then Round 3.

**Melee vs. Ranged Keywords**
To support evasion mechanics in PvP, every damage-dealing class card carries a keyword tag: **[Melee]** or **[Ranged]**.
- If a player plays a card that grants_range, they take 0 damage from any **[Melee]** attack that round.
- **[Ranged]** attacks ignore the grants_range evasion and deal their full damage.

**Class-Specific PvP Rules**
To balance the mathematical disparity between PvE-tuned sustain tanks and burst classes in a 3-round sprint, PvP relies on the dynamic Battle Hardened token system:

1. **Unlocked Execute:** The Warrior's *Execute* card does not require the opponent to be <= 50% HP during a PvP duel. It is freely playable at any time for its baseline 6 damage.
2. **Death Pact costs no HP in duels:** The Necromancer's *Boneguard's Offering (Boosted)* "Death Pact" rider (normally: lose 4 HP to deal 3 extra damage) does not cost any HP during a PvP duel — it still deals its bonus damage for free. Reasoning: PvP score is a pure final-HP delta, so a self-inflicted HP loss was being credited to the *opponent* as damage dealt, making the card strictly worse than not playing it in every duel (see `PVP_BALANCE_GUIDE.md`).
3. **Starting Battle Hardened Tokens:** To prevent a "rough patch" at the beginning of a campaign where naturally weaker PvP classes get stomped while waiting for the pity-timer to kick in, classes begin the game with an innate stack of Battle Hardened Tokens:
   * **2 Starting Tokens:** Rogue, Warrior, Necromancer
   * **1 Starting Token:** Ranger, Runecaster
   * **0 Starting Tokens:** Wizard, Cleric, Paladin, Druid

   Re-derived 2026-09-04 via `sim/sim_avg_tokens.py` after locking the Death Pact PvP rule
   above — Necromancer `3→2` (its old 3-token count was sized for a 4.08 steady-state bleed
   that the Death Pact fix cut to 1.71, closer to Warrior/Rogue's own 1.78/1.85 than to its old
   tier) and Wizard/Cleric `1→0` (both measured at 0.36/0.16 steady-state, closer to Paladin/
   Druid's 0.20/0.19 than to Ranger/Runecaster's ~1). See `PVP_BALANCE_GUIDE.md` for the full
   before/after table.
4. **The Pendulum Mechanic:** Each token adds **+1** to a player's final score for all future PvP duels. After a duel concludes, the **Winner discards exactly ONE** of their Battle Hardened Tokens, and the **Loser gains exactly ONE** Battle Hardened Token.

> **[DESIGNER NOTE]: The Rubber-Banding Pendulum**
> Because the Winner and Loser are adjusted independently, the token economy acts as a mathematically perfect pendulum that forces players to "take turns" winning. A heavily countered underdog naturally hovers around a higher token count, slowly bleeding tokens when they win and instantly regaining them when they lose. This guarantees true, long-term 50/50 parity across all 72 class matchups, completely eliminating the need for complex static modifiers or 9x9 lookup tables.

**Resolution and Spoils**
The duel lasts exactly 3 rounds. The winner is determined by:
- **The Knockout:** If a player is reduced to 0 HP, they die. (They suffer the lighter PvP Death Penalty: Respawn in Town, quests decay only 1 stage, no locked bag slots).
- **The Score Tiebreaker:** If both players survive all 3 rounds, the players calculate their Final Score: `(Unblocked Damage Dealt) + (Battle Hardened Tokens)`. The highest score wins.
- **Initiator Tiebreaker:** If the Final Scores are exactly equal, the Initiator (whoever said 'War' first) wins.

**Edge-Case Rulings:**
- **Mutual Destruction:** If both players are reduced to 0 HP simultaneously, they *both* suffer a PvP Death. However, a "Winner" is still calculated purely via the normal Score Tiebreaker to resolve token math: the winner discards one token, and the loser gains one token.
- **The Smoke Bomb Flee:** If a player uses a Smoke Bomb in the consumable window, they instantly flee. The remaining player automatically wins by default and claims the node's Quest Loot freely (since the PvE mob scattered). The fleeing player does *not* receive a Battle Hardened token. 

**The Reward:**
- The Winner claims the Node's original Quest Loot Token.
- The Winner receives +1 Gold (standard combat victory reward).
- The Winner steals +1 Gold from the Loser (a PvP bonus).
- The Loser is forced to flee to an adjacent node (unless they died).

