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
2. **Carrots, Not Sticks.** No Doom Track, no "Game Over in N Turns" clock. Players are pulled
   forward by decaying loot bonuses (Section VI) and the hard math walls of harder content.
3. **Determinism Over Dice.** Combat is a fully deterministic math puzzle — mob intent is
   printed and known in advance, round by round. The only randomness anywhere in a pull is
   which 4-of-6 cards you draw for your hand. You lose because your hand/sequence was
   insufficient, not because you rolled poorly.
4. **Shared DNA.** Reuses AGGRO's classes, card identities, and keyword vocabulary
   (STRIKE, AT RANGE, etc.) — condensed down to QUEST's much smaller per-pull format, not
   reinvented from scratch. See `DECK_CONDENSING_GUIDE.md` for exactly how that translation
   works.

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

Multiple heroes (2-4, any class mix) fight a shared threat together, co-op only. Still 3
rounds, one card per hero per round.

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

**Starting map, locked (revised 2026-08-20): two Zones, one Border Node, a Town in each.**
Zone 1 (the starting zone) holds Town — Bag/Food/Potion purchases, quest turn-in, the Bag
Upgrade. Zone 2, reached via the single Border Node connecting them, holds **both** a second
Town and the **Class Trainer** — purchased (Level-2+) upgrade cards are bought at the Trainer
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

**Built in `sim/macro_sim.py`** (2026-08-20) — `NODES`/`NODE_ZONE`/`QUESTS` carry all 8 entries
across both Zones; Border Node crossing is a real Scouted Pull toll (`_scouted_pull_mob`/
`_cross_to`/`_best_case_mob` in `run_one_trip`), fully discretionary in both directions now
that both Zones have Town. Flight Path (Zone 2 <-> Zone 4, 2 Gold, no turn cost) is now also
built -- see the Flight Path entry above.

**Starting loadout:** 2-slot Bag, 1 Food occupying slot 1, 0 Gold, 0 XP.

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
a reskin of any existing copyrighted property -- see `OPEN_QUESTIONS.md` if this note needs
revisiting later for why that mattered here.

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

Town node (both Zones' Town is the same amenity, per "a town is a town is a town" above; The
Vanguard Camp is Zone 3/4's flavor name for it): **The Vanguard Camp** -- a fortified staging
ground outside the warzone where mercenaries and disgraced knights trade supplies.

Unused candidate loot names from the same brainstorm, kept for the record in case any fit
better once quest reward tuning starts: Sanctified Reliquary, Martyr's Toll, Zealot's Bounty,
Consecrated Ledger, Purged Confession.

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

**Still explicitly not done, real engineering work, not just data entry:**
- **XP/Gold-ladder values for all 8 new quests still need their own real balance derivation**
  (matching how `quest_cost_gauntlet.py` derived Zone 1/2's originally), not the placeholder
  numbers currently in `LEVEL2_QUESTS` -- those reuse the pre-compression Zone 1/2 formula
  wholesale (flat `[4,2,1,0]` for required 2-4, `[9,5,3,0]` at required 5) purely so the
  mechanic has *some* real numbers to run, explicitly flagged in-code as not the real derivation.

**Loot chain, revised — colored quest tokens, any mix per slot, capped at 3.** Each active
quest is assigned a color (printed on the quest card, or marked with a colored token on it).
Loot earned for that quest is represented by a token of the matching color, placed into any
slot with room — the color identifies which quest it belongs to; the slot itself is what
counts against Bag capacity, the same as a Food or Potion would. **A slot holds up to 3
tokens total, any mix of colors** — deliberately *not* restricted to one color per slot: a
same-color-only rule would tie which node a player can profitably pull at to their current
Bag state (each node maps to one quest's color), quietly punishing a player for chasing a
favorable mob matchup at a different node just because their Bag is already partway into a
different quest's color. Keeping colors freely mixable keeps node choice (about the mob
matchup) and Bag capacity (about token count) fully independent, the way they should be. The
cap of 3 itself is derived, not guessed — it's the smallest stacking limit under which every
quest in the current table (requiring 2, 3, 4, or 5 loot) is still completable inside a
2-slot Bag, while still forcing a real choice: the two smaller quests (Pilfered Goods,
Syndicate Ledger) comfortably coexist with a consumable in the other slot, while the two
bigger ones (Contraband Crates, Stolen Signet) force giving that consumable slot up entirely
to hold enough tokens. Running out of slots (every slot full, locked, or holding an unused
consumable) means no more loot of any kind can be collected until a quest turn-in or sale
frees space. This replaces the previous "one open slot accepts any mix of loot types, Food
closes it" model entirely — colored tokens don't need a "closed" state at all, since each
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

**Bag Upgrade:** 16 Gold, +1 Bag slot, back-solved (not guessed) by sweeping candidate prices
until the measured cost landed at ~4.5 trips / ~27 pulls / ~25 XP on average against the real
4-quest system. Priced to land 4-5 trips (~25-35 pulls) into a zone before the first upgrade, so
the 6-mob Standard roster gets enough repetition to master before moving on. Stale as of the 6th
mob (Scout) and 7th class (Runecaster) — should be re-swept, not assumed still exact.

## VII. Progression — NOT YET BUILT

**Nothing past Level 2 is implemented or tested in the simulator** (`sim/macro_sim.py` has no
Level 3-6, no Cull, no Final Boss check). Kept here as stated design intent, not current rules:

**Full-game pacing target, locked 2026-08-22:** a player should go from Level 1 to Level 6 and
defeat the Final Boss in **~90 turns or less** (turns as defined in `OPEN_QUESTIONS.md`'s "What
a turn is" — one pull, one Town visit, one Border crossing, etc., each exactly one turn,
regardless of business done). This is a real constraint on whatever Level 3-6/Cull/Final Boss
system eventually gets built, not just this section's existing prose — none of it should be
designed or tuned without checking it against this number. Not yet validated against anything:
the simulator currently only implements a two-tier Level 1/Level 2 stand-in
(`LEVEL2_XP_THRESHOLD`), not the real 6-level system, so there is no current tooling that can
measure whether any real design hits 90 turns — that tooling has to be built alongside Level
3-6 itself, not assumed to already exist.

**"Market Row," as a separate future system, is retired — it's stale as of the Class Trainer's
build (2026-08-21), corrected 2026-08-22.** Market Row's own one-line definition ("spending Gold
in Town adds tuned, tactical cards to a class's deck") is exactly what the Class Trainer already
does, live in the simulator, today (`SKILL_COST`, `LEVEL2_PURCHASED_ORDER`, buy any number of
upgrade cards in one Trainer-Zone visit — see Section VI/`MACRO_LOOP_GUIDE.md`). The Trainer just
hasn't been generalized past Level 2 yet; there is no second, distinct "Market Row" mechanism
left to build on top of it. Whenever Level 3-6 gets built, the same Trainer-purchase pattern is
expected to repeat at each level, not a separate system.

**Which purchased upgrade a hero gets 2nd/3rd/4th is randomized per hero, not fixed and not
player-selected (locked 2026-08-23).** The mandatory upgrade stays free/automatic/earned, but
beyond that, each hero draws from their own personally-shuffled order of the remaining upgrade
cards — a human never picks which one, only whether to spend the Gold on whichever is offered.
Deliberate, not an oversight: QUEST is a quick, one-shot, non-legacy game, and free selection
among a known upgrade set converges over repeated sessions (every table eventually just buys
whatever's mathematically strongest, in the same order, every time) — randomizing removes that
convergence. Safe because the balance methodology already validated each purchased upgrade
independently against the guaranteed-minimum kit, never against an order-dependent sequence —
see `LEVELING_GUIDE.md`'s "Purchased upgrade order" entry for the full reasoning.

- **The strict 6-card limit overrides the original vision below, wherever they conflict.**
  Combat's exact-solver architecture (Section II, "unique decks") depends on every class
  holding exactly 6 unique cards, always — the 15-hand enumeration every diagnostic in this
  project relies on doesn't exist at any other deck size. Any progression system, whenever it's
  built, has to work as a **1-for-1 card swap** (upgrading a base card into a purchased one),
  never additive growth. The paragraphs below describe the original, pre-condensed-combat
  vision (a larger starter deck thinned down via Cull) and are kept for the historical intent,
  not as a spec to build against — they need to be redesigned around the 1-for-1 constraint
  before any of this actually gets built.
- **Leveling (1-6):** turning in quests grants XP; leveling lets players **Cull** (permanently
  destroy) basic starter cards, thinning the deck so Trainer-bought upgrades draw more reliably.
- **Win condition — the Final Boss node:** a single, static, monstrous math check (co-op Party
  Pull) players build toward and attempt whenever ready.
- **Elite Spikes mixed into a zone's deck at known odds:** rather than a separately authored
  "Elite content" pool, a zone's actual mob deck would be its own authored recipe combining
  pools (e.g. an 18-card Standard deck with 2-3 Elite cards shuffled in) — with the exact
  composition printed and public on the zone card, so contesting a node with Elites mixed in is
  a calculable risk, not a blind draw. Decided in principle (`OPEN_QUESTIONS.md`), not built.

## VIII. Component & Physical Implementation

What an actual physical prototype needs, based on the current locked rules above:

- **Per-class deck:** 6 unique cards. Warrior's cards print Guardian/Champion values as
  mirrored text on opposite card ends (Section II) — no separate stance token needed.
- **Mob cards:** HP plus a 3-round `(ATK, Block)` pattern, printed and fully visible (no hidden
  mob info, ever). A melee/ranged type icon (Section IV).
- **HP trackers:** one per hero, plus a shared mob HP tracker per pull (or per active mob, in a
  co-op multi-mob fight — Section V).
- **Bag:** physical slots (2 to start, upgradeable — the exact target size is still open, see
  `OPEN_QUESTIONS.md`), each holding either one Food, up to 2 Potions, or up to 3 Quest Loot
  tokens in any mix of colors.
- **Quest Loot tokens:** one single generic component, not a distinct token per zone/quest —
  color-matched to whichever quest card is currently marked that color (a printed color, or a
  colored marker placed on the quest card at pickup).
- **Quest log:** exactly 3 slots, each tracking its current decay tier (Gold/Silver/Bronze),
  and now also its assigned color for token-matching.
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

## VIII. Competitive PvP (The Duel)

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
2. **Starting Battle Hardened Tokens:** To prevent a "rough patch" at the beginning of a campaign where naturally weaker PvP classes get stomped while waiting for the pity-timer to kick in, classes begin the game with an innate stack of Battle Hardened Tokens:
   * **2 Starting Tokens:** Rogue, Necromancer, Warrior, Runecaster
   * **1 Starting Token:** Paladin
   * **0 Starting Tokens:** Wizard, Cleric, Ranger, Druid
3. **The Pendulum Mechanic:** Each token adds **+1** to a player's final score for all future PvP duels. After a duel concludes, the **Winner discards exactly ONE** of their Battle Hardened Tokens, and the **Loser gains exactly ONE** Battle Hardened Token.

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

