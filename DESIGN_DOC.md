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

Necromancer and Druid are not built yet. **Full, exact card-by-card rules text (with keyword
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
zone being left, and how this reconciles with the zone-refresh rule). **Flight Paths** let a
player spend Gold in Town to bypass a Border Node's toll entirely, commuting straight to
another Zone instead — the Gold cost itself is still undecided. `sim/macro_sim.py`'s scope
note still correctly flags Border Toll travel as "not modeled at all" (not yet built, though
now fully specified). Not to be confused with the free intra-Zone movement above.

**Starting loadout:** 2-slot Bag, 1 Food occupying slot 1, 0 Gold, 0 XP.

**Loot chain, precisely (a common misread — this is not "one loot type per slot").** There is
at most one currently-*open* Bag slot at a time, and it accepts **any mix** of loot types while
open — winning three different loot cards in a row all pile into that same open slot together.
Closing a slot (via Food, below) locks in whatever mix it's holding and opens a fresh, empty
slot for future loot, up to the Bag's total slot count. Running out of slots (every slot
closed, locked, or holding an unused consumable) means no more loot can be collected at all
until a quest turn-in or sale frees one. **A normal Town visit (not a death respawn) reopens
every Food-closed slot** — its contents stay exactly as they were, but the slot becomes able to
collect new loot again, the same way it worked before it was closed. This does **not** touch
LOCKED (post-death) slots — those only ever unlock via corpse recovery, above, never just by
being in Town.

**Consumables — two different trade-offs on the same Bag-slot economy:**
- **Food (2 Gold):** heals to full HP, but **closes the active Bag slot** — subsequent loot
  opens a fresh slot. The real "push your luck" lever.
- **Potion (4 Gold):** heals a flat **8 HP**, but does **not** close the slot — preserves the
  loot chain at a steeper Gold cost.

**Risk policy (locked default): consumable-before-risk, always.** Exact constants:
`RISK_TOLERANCE = 0.15` (the fraction of hands allowed to be lethal *when this pull would
complete a quest* — a real player wouldn't refuse a pull just because one bad hand exists among
many) and `RISK_TOLERANCE_BASE = 0.0` (otherwise — effectively zero lethal-hand risk allowed).
The higher tolerance is only used as a genuine last resort, when no unused Food/Potion is
available in the Bag. Roughly halves average deaths per trip-chain versus the old "risk it
whenever a quest completes this turn" default, with no corresponding rise in worst-case decay.

**Death and corpse recovery (locked rule, not yet in this doc before now).** If a pull kills
the hero, a corpse marker is left at that node and the hero **respawns in Town at full Max
HP**; every Bag slot holding anything (loot or an unused consumable) **locks** — its contents
stop counting toward quests and can't be added to — and **every quest currently in the active
log takes an immediate 2-stage decay hit, with no exception for a quest that's already fully
collected and ready to turn in** (versus 1 stage for a normal incomplete return), still capped
at "nothing." The trip *after* a death is forced to spend its first pull back at the death node
(a fresh random mob from that node's tier, no loot either way) before any normal questing
resumes; the hero only needs to **survive** that pull — win or flee both count, killing the mob
is not required — to unlock every previously locked slot. Dying on the recovery pull triggers
the exact same handling again — a real spiral risk, not special-cased away. If the hero can't
safely attempt it (no consumable available to make the risk acceptable), the trip ends with the
corpse still unrecovered.

**Decaying Bounties.** Players hold exactly 3 Quests at all times. Decay is assessed at the
**end of each trip**, not on departure: any quest still incomplete once a trip concludes
downgrades one Gold-ladder tier (Gold → Silver → Bronze → nothing). **A quest's first trip can
never be decayed before or during that attempt** — this isn't a bolted-on grace period, it
falls directly out of the mechanism above: decay only ever applies to a quest that's *still*
incomplete once a trip is over, and a quest completed within its own first trip lands in the
turn-in branch instead of the decay branch, every time. This is why the "quicker half" of
completions land at full Gold-tier 100% of the time (see Designer's Notes) — without this,
finishing any quest at full Gold would be structurally impossible, not just unlikely. XP is
flat and doesn't decay (`base_xp = required`, 1 XP per loot item the quest asks for) — only the
Gold bonus erodes, so pushing your luck risks the bonus, never the guaranteed baseline progress.

**Quest table** (`sim/macro_sim.py`'s `QUESTS`), Gold ladder priced from measured trip cost, not
a hand-picked curve — see Designer's Notes for the derivation:

| Quest | Loot required | XP | Gold ladder (Gold/Silver/Bronze/nothing) |
|---|---|---|---|
| Pilfered Goods | 2 | 2 | 4 / 2 / 1 / 0 |
| Syndicate Ledger | 3 | 3 | 4 / 2 / 1 / 0 |
| Contraband Crates | 4 | 4 | 4 / 2 / 1 / 0 |
| Stolen Signet | 5 | 5 | 9 / 5 / 3 / 0 |

**Bag Upgrade:** 16 Gold, +1 Bag slot, back-solved (not guessed) by sweeping candidate prices
until the measured cost landed at ~4.5 trips / ~27 pulls / ~25 XP on average against the real
4-quest system. Priced to land 4-5 trips (~25-35 pulls) into a zone before the first upgrade, so
the 6-mob Standard roster gets enough repetition to master before moving on. Stale as of the 6th
mob (Scout) and 7th class (Runecaster) — should be re-swept, not assumed still exact.

## VII. Progression — NOT YET BUILT

**Nothing in this section is implemented or tested in the simulator** (`sim/macro_sim.py` has
no Level, no Cull, no Market Row purchase flow, no Final Boss check anywhere). Kept here as
stated design intent, not current rules:

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
  destroy) basic starter cards, thinning the deck so Market-bought upgrades draw more reliably.
- **Market Row:** spending Gold in Town adds tuned, tactical cards to a class's deck.
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
- **Bag:** physical slots (2 to start, upgradeable), tracking which loot type occupies each.
- **Quest log:** exactly 3 slots, each tracking its current decay tier (Gold/Silver/Bronze).
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
