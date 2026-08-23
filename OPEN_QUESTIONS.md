# QUEST — Open Questions

Design tensions and undefined interactions flagged before prototyping starts. Move an item to `DESIGN_DOC.md` once it's actually settled — don't mark it resolved just because it's discussed.

## Unresolved

### Competitive AI: does a hero weigh contested-Node risk before declaring, and against what information?

Raised 2026-08-23, after building the Move-and-declare barrier (`declare_for_hero`/
`advance_board`, task #64). That barrier is pure resolution machinery — it settles a contest
once declarations exist, but nothing decides *whether* an AI hero should risk declaring a Node
that might turn out contested (blind redraw, unpreviewed mob) versus a different Node in the
same Zone. The existing single-hero AI (`decide_travel`) has zero concept that other heroes
exist at all, so this isn't a small addition to it — it's a new decision layer.

**What's actually known/computable, not guessed:** a hero's own class's cost%/win% against
every currently-dealt mob in their Zone (existing diagnostics), whether they hold the priority
token this round (not hidden — a hero knows this in advance), and which Zone each other hero is
currently standing in (physical position on a shared board — visible, unlike what they're about
to declare). What's genuinely uncertain: which specific Node each other present hero will
declare this round, since Move-and-declare is simultaneous and blind by design.

**Real open sub-questions, not decided here:**
- **Are other heroes' active quest logs public information at the table, or private to each
  hero?** This isn't settled anywhere in the docs. It matters a lot: if quest logs are public, a
  contest-risk model can reason "hero B is 1 loot away from finishing at Node X, they're likely
  to declare it"; if private, the model can only work off Zone occupancy and generic contest-
  probability, a much cruder signal.
- **What value function is being optimized** — expected gold/turn, this-pull win probability, a
  blend? The solo AI has established diagnostics for the deterministic case; nothing analogous
  exists yet for "expected value under contest uncertainty."
- **How is a blind redraw's expected value computed** — averaged over the level deck's full
  starting composition (a reasonable, tabletop-legible simplification) or its true remaining
  composition at that moment (more accurate, state-dependent, harder to reason about at a real
  table)?
- **Heuristic vs. genuine opponent modeling.** A flat rule ("if 2+ heroes share a Zone and more
  than one Node serves my active quest, prefer whichever has the better EV against a fixed
  assumed contest probability") fits this project's stated bias toward simple, tabletop-
  executable rules over hidden-conditional cleverness (`DESIGN_DOC.md`'s own repeated framing).
  A fuller Bayesian model of what other AI heroes are likely to do would be more accurate but is
  a different, much bigger build — needs a real decision, not an assumption either way.

**Blocked on task #65 (drive an actual competitive game through the barrier) existing first** —
there's nothing to validate a contest-risk heuristic against until multiple AI heroes are
actually being run through `declare_for_hero`/`advance_board` in a loop.

### Random-drop rates for the new Bag-slot consumables

Raised 2026-08-22, alongside locking the Gold prices for Scroll of Vanquishing, Smoke Bomb,
Whetstone, and Preserving Charm (see `DESIGN_DOC.md` Section VI). The stated intent is that
winning a pull should also be able to drop one of these four items for free, not just via Town
purchase, with better odds at Elite/Boss-tier mobs — but none of the actual numbers are decided:
- Exact drop rate per mob tier (Standard vs. Elite vs. Boss).
- Whether a drop replaces the existing +1 Gold win reward or stacks on top of it.
- Whether the odds are uniform across the 4 items or weighted (e.g. Scroll of Vanquishing rarer
  than Whetstone, matching its higher purchase price).

Deliberately deferred rather than guessed alongside the Gold prices — this needs its own pass,
likely a simulator sweep, once those base prices are validated in play.

### When does a hero deliberately travel to buy a purchased upgrade?

Raised 2026-08-21, right after building deliberate fallback travel for the *free* mandatory
upgrade and real quest pickup (both now require a real Trainer/quest-giver visit, not an
automatic grant on crossing an XP threshold — see `sim/macro_sim.py`'s `_trip_chain`). The
mandatory upgrade and quest pickup both got a real "travel there on purpose" rule;
**purchased (non-mandatory) upgrades did not** — buying one is still purely opportunistic: it
only happens if the hero already happens to be standing in a Trainer Zone (2 or 4) for some
other reason, with enough Gold and an unbought upgrade next in `LEVEL2_PURCHASED_ORDER`. There
is no mechanism making a hero deliberately travel to a Trainer Zone just to spend Gold on one.

Given Level 2 quests are now split across Zone 3 *and* Zone 4 while the Trainer only exists in
Zone 2 and 4, a hero whose quest log happens to route them through Zone 3 repeatedly could sit
on affordable Gold for a long stretch without a purchase happening, purely from quest-routing
luck, not because buying wasn't worth it.

**Decided for now: leave it opportunistic, do not build deliberate travel-to-buy logic yet.**
Explicitly flagged to revisit once Level 2 quests are fully wired in with real balance
numbers (not the current placeholder `LEVEL2_QUESTS` reward table) — test what the
opportunistic strategy actually produces first (how long Gold sits idle, how much later
purchases land compared to the mandatory-upgrade-driven travel), and only build a more
deliberate rule if that turns out to be a real problem, not preemptively.

### "Deterministic Spice" — node-variety ideas for task #28, not evaluated or decided

Raw brainstormed ideas, not discussed or checkpointed yet — recorded here so they aren't lost,
not because any of them are settled. All three lean on the same trick: since occupied nodes
are populated from a physical, shuffled deck (see "Zone-node mob dealing" below), variety
doesn't need new dice or hidden-info mechanics — it just needs non-mob cards shuffled into that
same deck.

- **Rare Spawns ("Loot Goblin").** A special mob card mixed into the zone deck: low HP, but
  Flees on round 2 instead of round 3. Drops Wildcard Loot or flat Gold if killed. Being dealt
  face-up is meant to create real priority contention and greed-driven routing changes.
- **Gathering Nodes.** A non-combat resource card in the same deck — no ATK/HP at all. Claiming
  it costs something instead of requiring a fight (e.g. "take 3 unmitigated damage, or discard
  a hand card with 3+ Block") and yields Potions, Gold, or specific loot with no combat-solver
  phase involved.
- **The Roaming Threat ("Fel Reaver").** A physical token, not a card — moves one node along a
  printed path every round, fully predictable (no hidden info), and overrides whatever's dealt
  at the node it lands on. Players have to route around it or get forced into a large pull.
  Interaction not thought through yet: what happens if it lands on a Border Node specifically.

None of this has been checked against anything the way the rest of this project's mechanics
are (no diagnostic run, no "does this actually fix task #28's repetition problem" check, no
discussion of whether it fits the game's existing texture). Treat as a starting point for that
conversation, not a queued build.

**Second brainstorm pass: 8 more Spice concepts, deliberately meant as rare rule-breakers, not
held to the usual validation bar.** Unlike a core mechanic that fires every node every turn,
these are meant to be occasional exceptions — user's stated intent is something like 1-3 of
them showing up total across Levels 1-2, which already lines up with the locked deck math (1
Spice slot at Level 1 + 2 at Level 2 = 3 total Spice appearances per tier) rather than fighting
it. That framing is why several of the concerns raised below were explicitly walked back from
"needs full derivation/validation before this can be trusted" to "fine as an intentional,
rarely-seen exception" — the stakes of an occasional table-level event being slightly
class-asymmetric are much lower than a repeated mob or card value being off. Still audited
directly rather than accepted at face value; real gaps found and either ruled on directly or
left open below.

- **The Insurance Broker (Death Protection).** Non-combat, pay 3 Gold, keep the card. If you
  hit 0 HP that trip: discard this card, respawn in Town, Bag does *not* lock, active quests
  take the normal 1-stage trip decay instead of the 2-stage death decay. **Ruled: the
  corpse-recovery forced pull is also skipped entirely** — since nothing locks, there's nothing
  to physically retrieve. The 3 Gold cost itself hasn't been checked against real death/decay
  rates the way every other economy lever in this project has (see `MACRO_LOOP_GUIDE.md`'s
  16-Gold quest-reward derivation for the standard this should eventually meet).
- **The Secret Tunnel (Toll Bypass).** Non-combat. Claiming this node lets you immediately
  resolve a pull at any node in an adjacent Zone, fully bypassing the Border Node's Scouted
  Pull toll; counts as your single pull for the turn. **Ruled: scoped to any zone, any node —
  not restricted to unoccupied destinations the way Scouted Pull itself is.** This means it can
  sometimes outperform a paid Flight Path outright (no toll, no travel turn, and if the
  neighboring zone is occupied, a free pick from its already-visible nodes). Accepted
  deliberately given rarity — Flight Path's value proposition is read as speed/convenience, not
  exclusive access, so occasional overlap is fine.
- **The Treasure Map (Specific Routing Reward).** Non-combat, keep the card on claim. Printed
  with a specific Zone/Node. Next successful combat pull there: discard for 1x Wildcard Loot.
  Flee or death there: keep the Map. **Ruled: does not occupy a Bag slot** — held state
  separate from loot, no competition with the existing 2-slot squeeze.
- **The Board Sweep (The Reset).** Non-combat. Claiming this node discards all face-up cards on
  the other 3 nodes in the Zone, deals 3 fresh cards from the Zone Deck, and lets you
  immediately claim and pull one of those fresh nodes. **Ruled: resolves before any pulls
  happen that turn, and any hero on a node affected by the sweep may change their already-
  declared target if they wish** — protects against Board Sweep silently invalidating another
  hero's locked-in choice with no recourse, given "move and declare" is normally simultaneous
  for everyone in a zone.
- **The "DPS Dummy" (The Armor Check).** Combat. 14 HP, 0 ATK all 3 rounds — a pure damage-race
  mob where Block/heal cards are dead draws. Fail to kill in 3 rounds: it flees *and* steals 1
  Gold or 1 Loot from the Bag. Kill it: premium loot. **Not yet checked: class symmetry** — do
  all 9 classes' 3 highest-damage cards actually clear 14 in 3 rounds. Deferred as a
  verification task, not a design decision, until this mob's real tier placement and final
  numbers exist (currently no numbers exist to check against, unlike Healing Spring below).
- **The "Modifier" Suite (Grafted Mechanics).** Not mobs — modifiers. **Ruled: when a Modifier
  card is drawn/dealt, the drawer learns immediately that whatever mob is drawn next belongs to
  that Modifier** (the Modifier is revealed before the mob underneath it, not paired secretly).
  **Ruled: no stacking** — if a second Modifier would land on an already-Modified node, discard
  it instead. Four variants: *Enrage* (+1 ATK every round, drops double loot on kill),
  *Fortified* (+3 HP, drops 1 Gold on kill), *Trap* (2 unmitigated DMG before Round 1 begins,
  drops 1 Gold on kill), *Bounty* (+2 XP on kill, no combat change at all — doesn't actually
  need the "deal an extra card" machinery the other three do, and probably reads better as its
  own simple card, closer in shape to Loot Goblin, than as a fourth Modifier variant).
- **The Shrine of Knowledge (Hand Sculpting).** Non-combat. Look at the top 3 cards of your
  6-card class deck, set 1 aside, shuffle the rest back in. Your next combat pull draws that
  set-aside card plus 3 random draws. This genuinely breaks the "deck fully resets every pull,
  15 equally-likely hands" invariant every exact-solver tool in this codebase depends on — but
  **deliberately not held to that bar, given how rarely this fires: a manual, table-level event,
  not a repeated system, so no dedicated solver mode is planned or needed for it.** Worth a
  quick hand-check per class if it ever gets built, but not permanent tooling investment.
- **The Healing Spring (The Gamble).** Non-combat, push-your-luck heal. Safe Play: flat Heal 2
  HP. Gamble: draw 4 of your 6-card deck; discard a card with the Heal or Block keyword to Heal
  4 HP (heal 0 if you can't), then shuffle. **Checked directly against every class's real
  `CARDS` dict, not assumed** (an earlier pass of this same check had a real bug — Warrior's
  block values live in per-stance `(G, C)` tuples, not a flat `block` key the way every other
  class stores them, which silently produced a false "Warrior 0%" result before being caught
  and corrected against the actual printed card text): success odds range from 66.7% (Ranger;
  also Warrior specifically while locked into Champion stance) to 100% (Cleric, Paladin, Druid,
  and Warrior while locked into Guardian stance) — a real spread, but nobody's mathematically
  locked out of the Gamble ever succeeding. **Two rulings still open, not yet decided:** (a)
  Warrior's own odds swing 33 points depending on which stance is locked that pull, since two
  of its three Block-bearing cards read 0 Block specifically in Champion stance — does "has the
  keyword" ignore current stance, or only count if the stance you're actually in shows a
  nonzero value; (b) three cards carry only a conditional or triggered Heal/Block rather than a
  flat guaranteed base value (Cleric's Smite, via its automatic Sacred Balance heal; Paladin's
  Invocation of Grace, whose heal scales off STRIKE cards already played; Ranger's Beast Bond:
  Wolf, which activates a *future* persistent Block rather than an immediate one) — does the
  keyword count if it's conditional, or only if it's guaranteed on that card regardless of
  circumstance.

*(Items 2-5 previously here — Rest vs. Claim structure, Winded-trigger rule, Wizard outcome
variance under the Cast Penalty, ranged-mob-never-engages — all referenced a Winded/OOM +
Cast Penalty + Engagement system that was cut entirely, not deferred, once condensed combat and
the macro loop replaced the original AGGRO-scale translation (see `CONDENSED_COMBAT.md`'s
"Exhaust dropped entirely"). Removed as stale rather than left to imply they're still live —
caught and flagged during the `DESIGN_DOC.md` rewrite/audit. If Wizard's actual current
all-or-nothing outcome variance under condensed combat's real rules ever needs its own
investigation, that's a fresh, unrelated question — see task #29.)*

### "Dungeon" node concept — forced multi-pull chain, not evaluated or decided

Raised 2026-08-22, inspired by how the WoW board game handles dungeons. Not yet scoped to a
level, Zone, or even confirmed as its own Node type versus some other delivery mechanism —
recorded here so the idea isn't lost, not because any of it is settled.

The core idea: a Dungeon node commits a hero to a chain of 3 pulls back-to-back, with
consumable use (Food/Potion) restricted somewhere across that chain rather than freely
available between each pull the way an ordinary Node visit works today. Two variants raised,
neither settled:
- No consumable use at all between any of the 3 pulls — full HP-management pressure across
  the whole chain, arrive with what you've got.
- Exactly one consumable use allowed, but only immediately before the third (final) pull, not
  between pulls 1 and 2.

Not discussed or checked against anything yet:
- What a Dungeon actually rewards for the added risk (bigger/guaranteed loot? something rarer
  than normal Node loot? a distinct reward track entirely?).
- Whether all 3 pulls draw from the same tier/deck or escalate in difficulty across the chain.
- Whether declining or retreating mid-chain is possible at all, or a hero is fully locked in
  once the first pull of the three is committed to.
- How this interacts with the already-locked "one turn = one pull" accounting (OPEN_QUESTIONS.
  md's "What a turn is") — does a 3-pull Dungeon cost 3 turns like 3 ordinary pulls would, or
  does committing to the whole chain read as something else turn-wise (e.g. one committed
  "turn" that resolves 3 rounds of combat internally).

### Per-class matchup info for the hero tracker boards, and how it interacts with blind-refill risk

**This information is meant to live on each hero's own tracker board** (the physical
dial/board each player uses to track their own HP and whatever else is personal to their
hero) — not a shared table reference, not printed once for the whole group.

Per-class "Comfortable against: X, Y / Struggles against: Z, W" matchup text (top 2 / bottom
2 mobs by cost%, uniform format for every class, leaves the middle 2 mobs deliberately
unlabeled — see `sim/class_mob_matchup_chart.py`'s own module docstring for the real numbers
and reasoning behind why cost%, not win rate, and why 2/2 rather than 3/3 or a
per-class-varying count). Real per-class content, e.g. Warrior favors Bruiser/Scout and
struggles with Enforcer/Ambusher; Wizard's struggle list is Raider/Scout instead, tracing
directly to its evasion tools doing nothing against Scout specifically. Re-confirmed live
against the current kits (2026-08-19, after that session's Ranger/Rogue/Druid fixes): Ranger
comfortable Bruiser/Grunt, struggles Scout/Enforcer; Rogue comfortable Grunt/Scout, struggles
Enforcer/Ambusher; Druid comfortable Grunt/Scout, struggles Ambusher/Enforcer.

**A real strategic wrinkle surfaced discussing it, not yet evaluated or decided:** this
interacts directly with the already-resolved blind-refill rule (see "Zone-node mob dealing"
below) — whoever's second or later to a contested node that same round draws a fresh mob
*blind*, losing the advance-information advantage that's this whole combat system's central
premise. Since a class's "Comfortable against" mobs are exactly the ones that class's
players most want to go fight, those are also the nodes most likely to attract contention —
meaning always chasing your favored matchup is a bet on winning a race, not a safe default.
The unlabeled *middle two* mobs may actually be the practically safer choice much of the
time: nobody's board is pointing there specifically, so there's a real chance of arriving
uncontested and keeping full information, traded against a merely-average matchup instead of
a great one.

Separately: since "struggles against" is far less differentiated across classes than
"comfortable against" (Ambusher and Enforcer are the hardest matchup for 7 of 9 classes
each, confirmed directly from the real cost% numbers), those specific nodes are probably
close to permanently uncontested — worth considering whether they deserve an explicit reward
bump, to make eating the worse matchup in exchange for guaranteed access and full
information a genuinely attractive trade rather than just a fallback.

Not evaluated: whether any of this changes the recommended board content itself, whether it
needs an explicit printed callout anywhere, or whether it's fine left as emergent strategy
for players to discover at the table without the game commenting on it directly.

## Resolved

### The Claim phase's failure mode (priority at a hot node)

Original concern: one claim per node per round, priority passed clockwise via the First
Player Token — what happens to a player consistently last in turn order at a hot node?

Resolved as part of the zone-node mob dealing system below: co-op groups self-organize turn
order by table agreement; competitive play uses a rotating "pass the box" priority so lead
position isn't fixed to one player every time. The mechanism also gives priority real
stakes beyond just "who acts first" — see the blind-refill rule below.

### Zone-node mob dealing, and node-based (not mob-based) loot sourcing

Replaces the current per-pull memoryless random mob draw (`macro_sim.py`'s `rng.choices`
against a tier's weighted pool, independent every single pull) with a visible, turn-based
board state. Each occupied Zone (only zones with a hero actually present need this tracked,
not every zone every turn) has a set of Nodes (e.g. a Tier 1 Zone: 4 farmable nodes + Town)
and a shared pile of mob cards drawn from that zone's tier. At the start of every turn, deal
the top card of the pile onto each node in order (A, B, C, D...) — this is what's actually
sitting at that node until it's dealt over again. Gives players real information to act on
(what's currently at each node, visible before committing to a pull) instead of a blind
random encounter every time — directly answers the still-open "brainstorm variety/anti-
repetition mechanics" task, and connects to `CONDENSED_COMBAT.md`'s existing "memorization
risk" reflection (a finite, visible pile changes the puzzle's texture differently than a
memoryless draw does).

**Deck composition, decided:** a literal finite deck, not the existing weighted-random
system reused — 3 copies each of the 6 locked Standard-tier mobs (Grunt/Bruiser/Enforcer/
Raider/Ambusher/Scout), 18 cards total (updated from an earlier 15-card/5-mob count, before
Scout existed). Reshuffles the discard back in whenever it runs dry — never actually stays
empty. See "Elite Spikes" below for how the deck extends past a pure Standard pull.

**Tier/level/zone structure, and the deck's actual scope, decided (this section originally
described the deck as scoped to a single zone — corrected here, not left contradictory):**
heroes progress through 3 tiers of 2 levels each (6 hero levels total). Tier 1 = Levels 1-2,
using the 6 Standard mobs and 3 Elite mobs already locked. Each tier has 4 zones — 2 built
for its lower level, 2 for its higher level. **No hard gate keeps a hero out of any zone at
any level** — the only things steering them toward the right ones are the content actually
being survivable and quests not sensibly pointing a low-level hero at high-level zones.
**The deck is curated per level, not per zone — one shared deck for both zones at that
level**, not four separate zone-specific decks per tier. This was a deliberate choice over
letting the two zones at a level differ in mob-composition leaning (which would have created
a genuine "which zone suits my class" pull, tying into the hero tracker board's Comfortable/
Struggles matchup info two sections below) — rejected specifically for the admin overhead of
authoring and maintaining 12 distinct deck recipes across the whole game (4 zones x 3 tiers)
instead of 6 (2 levels x 3 tiers). The zone-vs-zone pull this would have created is
considered adequately covered by loot already being sourced per-node instead (see below) —
zones can still differ in what they reward, just not in what they contain.

**Tier 1's actual two decks, worked example (ratios are the load-bearing number here, not
the raw counts — see `sim/class_mob_matchup_chart.py`'s docstring reasoning for why cost%,
not win rate, is what actually differentiates a class's real matchups):**
- **Level 1 deck:** 18 Standard (3 each of the 6) + 0 Elite + 1 Spice card = 19 cards.
  P(Spice on any single node-deal) = 1/19 (~5.3%). Zero Elites deliberately — Elites are
  meant to read as a real, close-to-coinflip risk (the locked target from the Elite
  derivation work), which doesn't belong in front of a hero still learning the base puzzle.
- **Level 2 deck:** 18 Standard + 3 Elite (1 each of Bulwark/Berserker/Warlord) + 2 Spice
  cards = 23 cards. P(Spice) = 2/23 (~8.7%), P(Elite) = 3/23 (~13.0%) per node-deal. Under
  the full-refresh-every-turn rule below, an occupied Level 2 zone deals its full 4 nodes
  fresh every turn, so expected Elite appearances per turn per occupied zone ≈ 4 x 3/23 ≈
  0.52 — roughly one Elite showing up somewhere on that zone's board every other turn. If
  both Level 2 zones happen to be occupied simultaneously, that's roughly one Elite per turn
  across the level as a whole.
- **"Deterministic Spice" is two different mechanisms, not one** (see that entry in
  Unresolved, above): Loot Goblin and Gathering Nodes are real cards that belong in this
  deck's card counts. The Roaming Threat ("Fel Reaver") is a separate physical token that
  overrides whatever's dealt at the node it lands on — it is not part of deck composition
  and doesn't factor into the ratios above.
- **Not yet decided:** whether this exact 3-category structure (Standard/Elite/Spice, same
  18-card Standard core, level-scoped deck) is meant to carry forward unchanged into Tier
  2/3, with only the specific mob pools and ratios re-derived once those tiers exist, or
  whether the structure itself should be revisited later. Treating the former as the working
  assumption unless something concrete argues otherwise.

**Turn phase order, decided:**
1. **Deal.** Only zones with a hero currently present get dealt to — an unoccupied zone's
   nodes aren't tracked or refreshed at all. Every node in an occupied zone gets a fresh
   card from that level's shared deck, unconditionally (see step 5 — this is a full refresh
   every turn, not a partial one).
2. **Move and declare.** Every hero moves and declares their target node simultaneously (this
   is also the resolution to the Claim-phase question above).
3. **Resolve contested nodes.** Priority (First Player / rotating token) only matters where
   two or more heroes land on the same node the same turn. Whoever's first sees the mob
   already dealt there; whoever's second or later at that same node draws a fresh
   replacement blind (see the blind-refill rule above).
4. **Resolve pulls.** Each hero plays out their combat pull(s) against whatever's now sitting
   at their declared node.
5. **End-of-turn cleanup.** Every mob card currently on the board in an occupied zone goes to
   discard — played or not, engaged or ignored. Nothing persists into next turn; a mob you
   didn't get to this turn is simply gone, replaced by a fresh deal at step 1 next turn, not
   held over. Discarded cards stay in discard until the deck runs dry and reshuffles, same as
   any other card removed from the active deck.

**Node refill, decided:** replace, not stack. A node always holds exactly one current mob;
dealing a new one over an unclaimed mob simply replaces it. No node-congestion sub-system.
**Exception, co-op only:** see "Multi-mob co-op nodes vs. single-Elite nodes" below -- in
co-op play specifically, a node can hold more than one simultaneous mob. Solo and competitive
play never see this; a node there always holds exactly one mob, no exception.

**Turn order for multiple heroes at the same zone, decided, and this is also the resolution
to Open Question #1 above (the Claim phase's failure mode):** turns are simultaneous —
every hero moves and declares their node at the same time. The token only breaks ties when
two or more heroes land on the *same* node the same round. Co-op groups self-organize who
goes in what order by table agreement. Competitive play uses a rotating "pass the buck"
Player-One token that shifts one seat to the left every round, giving a straight 1-2-3
priority count from whoever's holding it that round (not fixed to one player, and not a
sequential-turn-order system — it only matters for resolving an actual node conflict).
Whoever's first at a contested node sees the mob already dealt there (fully visible, same
as the normal per-turn deal) before committing. Whoever's second (etc.) at that *same* node
the *same* round draws a fresh replacement blind — no preview before committing.

**This blind-refill case is a deliberate, narrow exception to this project's otherwise
strict "no hidden information, no dice" combat pillar** (HP, mob intents, everything else
always visible everywhere else in the design) — not an oversight, and not a general
reintroduction of hidden information. It only applies to a same-turn re-deal at an
already-claimed node, and it does real design work: it gives the priority/turn-order
mechanic actual stakes (going first isn't just "you act first," it's "you get full
information and whoever pulls behind you at the same node doesn't"), which is a sharper
answer to Question #1 than a flat priority rule alone would have been.

**Loot is sourced from the Node, not the Mob** — deliberately, after considering and
rejecting mob-sourced loot as "randomness on top of randomness" (which mob shows up is
already random; making what it drops *also* random independently stacks two layers of
uncertainty with no decision in between). Instead, a quest card prints a fixed instruction
("Silver Trinkets drop from Node A or B") that never needs to reference which specific mob
is currently dealt there — matches the project's established bias toward flat, no-hidden-
conditional rules. When two active quests share an eligible node and a kill happens there,
the player chooses which quest's loot they receive — a real decision, and it interacts
usefully with the existing 2-slot Bag capacity squeeze (pick whichever you need more of).

**Elite Spikes, and level decks as an explicit recipe rather than a raw tier pull, decided:**
mob tiers are scoped by level (e.g. a "Tier 1 Standard" pool, eventually a "Tier 1 Elite"
pool once Spike-tier mobs exist, then Tier 2 versions of both later). A level's actual deck
is its own authored recipe built from those pools, not just "draw from one tier" -- see the
worked Tier 1 example above (18 Standard + 0/3 Elite + 1/2 Spice, level-scoped, shared by
that level's 2 zones) for the concrete numbers. This replaces treating `MOB_TIERS`'s two
pools as the only unit a node can draw from; the deck-building step itself becomes the
authored content, of which a pure-Standard deck is just the simplest case. **Deck
composition (how many of each mob, including how many Elites) is public knowledge** --
printed at the level, not hidden -- so contesting a node with Elites mixed in is a
calculable risk, not a blind unknown, matching how risk is handled everywhere else in this
project.

**Blind refills draw from the full level deck, Elites included -- no special-case
exception.** An earlier draft (from an external design pass) proposed Elites could never be
drawn on a blind refill, redirected to a held state instead -- rejected as unnecessary
complexity once traced through: it would have needed a new card-lifecycle state (where does
a skipped Elite go, is it visible before its deferred deal, does it override the node's
normal next-turn deal) with no clean answer to any of those questions. The simpler rule
needs none of that machinery: a blind refill is just a real draw from the whole deck, and
`macro_sim.py`'s existing `_pull_exceeds_risk` risk-tolerance check already covers the
consequence -- a player (or the simulated agent) who doesn't like the level's known Elite
odds simply declines to contest that node this turn, exactly like any other lethal-pull
decision already modeled. Nothing new to build here beyond not carving Elites out of the
pool.

**Blocked on task #20 (deriving Spike-tier mob stats) for real validation.** The whole
premise -- that facing an Elite on a blind pull is a real, playable-around gamble rather
than a disguised trap -- depends on Spike's actual numbers, which don't exist yet. Once they
do, the thing to check is a **survival rate** (not win rate) for a fresh, full-HP hero
against a Tier-1 Elite: what fraction of hands leave the hero above 0 HP, even if they can't
win outright. This is a direct extension of the existing hand-level kill-feasibility check
(`CLASS_BALANCE_GUIDE.md`'s tool inventory -- the same kind of check that found "8 of 15
hands can't kill Brute" for early Paladin), just reframed around survival instead of victory.
If most hands can survive (even while fleeing/losing the fight), "play defensively" is a
real lever and this design holds up. If a meaningful fraction of hands are simply
unsurvivable regardless of play, this reintroduces the exact unfair-trap problem the
rejected held-Elite exception was originally trying to prevent, and needs revisiting.

Not yet built — this is a real addition to the macro-loop engine (zone/node state, turn-based
dealing logic, deck-recipe authoring), sized more like a new subsystem than a parameter
change. The rules themselves are now specified in enough detail to build from (tier/level/
zone structure, deck composition and ratios for Tier 1, the full turn-phase sequence) — what
remains is implementation, not further design decisions, for everything except Tier 2/3's
actual numbers (blocked on those tiers' mob pools not existing yet) and Elite Spikes'
survival-rate validation (blocked on task #20). No task tracked for the build yet.

### Border Nodes and Scouted Pull

Resolves `DESIGN_DOC.md`'s previously-open "Inter-Zone travel via Border Nodes" note and
`sim/macro_sim.py`'s "Border Toll travel isn't modeled at all" scope gap. A Border Node is its
own physical position on the board, adjacent to (but not part of) each of the Zones it
connects — currently just one, between Zone 1 and Zone 2, but the model is built to support
more than one as the map grows (see "Registered as a named entity" below). Movement is free
everywhere *within* a Zone, and free *from* a Border Node into any Zone it connects, but moving
*onto* a Border Node from a Zone (or from a different Border Node) costs its toll.

**Turn structure, corrected twice now (2026-08-20) — the toll pull is the whole turn, and
it does not complete a crossing into the destination Zone.** Two earlier versions of this
entry were both wrong in the same direction (assuming the hero ends up "in" the new Zone once
the toll is paid): the first described crossing as two turns (toll, then a separate
continue-or-retreat turn); the correction after that collapsed it to one turn but still said
the crossing itself completed within it. Neither is right. **A Border Node is a destination
like any other node — surviving its toll pull just means the hero is now standing on the
Border Node itself, exactly the way winning a pull at a Standard node means the hero is
standing at that Standard node.** The following turn, the hero (still on the Border Node) can
freely choose any node in *either* Zone it connects — no second toll, since they never left
it — or, just as easily, immediately go back to a node in the Zone they came from. Nothing
forces the "obvious" continuation into the new Zone; it's simply the nearest option, same as
every other node choice. The toll is paid once, to occupy the Border Node itself, never
repeated just for lingering there.

**Registered as a named entity, not hardcoded as "the" crossing** (`sim/macro_sim.py`'s
`BORDER_NODES` dict, added 2026-08-20): each Border Node has a name and the set of Zones it
connects (currently `{"border_1_2": frozenset({1, 2})}`), so adding a second Border Node later
(e.g. connecting Zone 2 and a future Zone 3) is a data addition, not a rewrite of the crossing
logic.

**Flagged for later, not yet relevant since nothing targets a Zone yet:** any future card or
effect that says "targets a Zone" (an area effect, a Zone-wide bonus, whatever) will need to be
explicit about whether it includes the Border Node(s) attached to that Zone or not, since a
Border Node is its own position, not part of either Zone it connects. No such effect exists
yet, so this doesn't need resolving now — just flagged so it's not forgotten when one is
designed.

**Scouted Pull, the toll mechanic, decided — deliberately named and defined as the opposite
of the existing Blind Refill rule at contested nodes, not a variant of it.** Blind Refill
(whoever's second to a contested node this turn) stays exactly as it was: a true forced
single draw, zero preview, zero choice — that's what gives losing the priority race real
stakes, and diluting it into a multi-card choice would remove the entire reason the rule
exists. Scouted Pull is the opposite on purpose: draw 2 cards from the **destination** Zone's
level deck (not the Zone being left), reveal both face-up, the hero chooses which one to
fight. Fully visible, a real choice — not blind at all, hence the different name. The
unchosen card goes to discard, same as any other card leaving the active deck unplayed; it
does not go back into the deck to be reshuffled in immediately.

**Scouted Pull only happens if the destination Zone is currently unoccupied — precisely
stated, not just implied.** If the Zone a hero is crossing into already has another hero in
it, its 4 nodes are already dealt and visible for real, unrelated reasons (the normal
occupied-zone refresh) — the crossing hero just chooses from what's already sitting there,
no separate draw at all. Drawing a fresh Scouted Pull on top of an already-populated Zone
would be pure waste, generating new information when real information already exists.
Scouted Pull exists specifically to cover the case where there's nothing on the board yet to
choose from — it's the minimal mechanism for that one case, not a general rule that applies
to every border crossing regardless of Zone state.

**Multiplayer contention, decided — a hero arriving via a Border Node always resolves after
a Zone's existing residents, not alongside them as an equal:**
- **Destination Zone already occupied, real contention over its nodes that turn:** heroes
  already resident in that Zone declare and resolve their node choice first. A hero arriving
  fresh via the border that same turn picks only after all of them, from whatever's left
  over — in a 4-player game, if 3 of a Zone's 4 nodes are already claimed by residents'
  declarations, the border-arriving hero simply takes the 1 remaining node, no real choice
  left. Declaring itself still happens simultaneously for everyone (unchanged from the
  existing turn-order rule above) — this only changes the order contention actually
  *resolves* in, not when people announce their intent.
- **Multiple heroes arriving via the border at the same already-occupied Zone
  simultaneously:** among themselves (after residents have already resolved), they're
  ordered by the same First Player / rotating-token priority system used for any other node
  contention — not a separate border-specific mechanism.
- **Multiple heroes arriving via the border at the same currently-*unoccupied* Zone
  simultaneously:** no priority ordering needed at all. Each does their own independent
  Scouted Pull — there's nothing pre-existing to contend over, and Scouted Pull is a
  personal draw against the shared level deck, not a shared, contested pool. Two heroes
  drawing Scouted Pulls back to back off the same deck is just two ordinary sequential
  draws, nothing special needed beyond that.

**Why the destination Zone's deck, not the Zone being left:** a direct expression of this
project's "no hard gate, difficulty itself is the gate" philosophy (see the Tier/level/zone
structure above) — the toll uses a real sample of what's actually ahead, not a familiar fight
from where the hero already stands.

**Reconciling this with "a hero on a Border Node forces mob card refreshing on both zones"
(stated when the zone-dealing rules above were being written) — Scouted Pull is that
refresh for the destination Zone's side, not an addition on top of it.** Traced directly
against a solo-play sequence before landing here: if a hero alone crosses toward an
untouched Zone, and Scouted Pull's 2 cards were treated as separate from also fully
populating that Zone's real 4-node set, the destination Zone would get dealt a full 4 cards
immediately (discarded under the full-refresh rule) on top of Scouted Pull's own 2 -- up to 6
cards dealt and mostly discarded to support one crossing, all within the single turn the
crossing now costs (see the turn-structure correction above). Scouted Pull is the entire
mechanism for representing an unoccupied destination Zone while a hero is merely at the
border, not yet inside it — its real 4-node set doesn't get separately populated until the
hero actually commits to entering. Confirmed directly: this reconciliation is correct, not
just a plausible-sounding synthesis.

**Built and locked 2026-08-21.** Flight Path is a dedicated node present in Zone 2 and Zone 4
specifically (not a Town purchase) -- 2 Gold, no turn cost of its own (same as ordinary
intra-Zone movement), letting a hero standing in one commute straight to the other, bypassing
the Border Node toll and its combat risk entirely. Doesn't shortcut any other journey (e.g.
Zone 1 -> Zone 4 still needs a real Border Node crossing to reach Zone 2 or 4 first). Since it
costs no turn, a hero can use it and then immediately pull at a node in the destination Zone
within that same turn -- verified directly (real trip traces show `flight_paths_used=1`
alongside a normal, non-inflated pull count, not an extra turn). A rational hero always takes
it over the 2-hop Border Node route when it applies and is affordable, since it strictly
dominates (fewer turns, zero combat risk, for a small Gold cost).

### What a turn is (locked 2026-08-20)

Never stated as one canonical rule before this — the pieces existed scattered across the
Border Node entry and the simulator's own trip-chain logic, but nothing pulled them together
across every node type. A turn is a hero selecting a travel-appropriate node reachable from
where they currently stand, and executing that node's action — travel itself is free and
costs no separate turn (Golden Rule 1), so a turn is defined by the action, not the movement.
Per node type:

- **Quest node:** one pull is one turn. Matches the simulator's own `pulls` counter directly.
- **Town:** a hero may do as much business as they want in one visit — turn in any number of
  complete quests, sell loot, buy any number of consumables/Bag Upgrades — and declares their
  turn ended when they're done. One turn total per Town visit, no matter how much gets done
  there.
- **Border Node:** one turn, same as any other node — the Scouted Pull toll pull is the
  action taken there. Surviving it lands the hero *on* the Border Node itself, not across it
  into the destination Zone (see the Border Nodes entry above for why this was wrong twice
  before landing here) — the next turn is an ordinary, free node choice from that position,
  same as any other node-to-node move.
- **Class Trainer:** same structure as Town — buy as many upgrade cards as affordable in one
  visit, declare the turn ended when done. One turn total per visit.
- **Corpse recovery:** the forced first pull back at the death node (see "Death and corpse
  recovery" in DESIGN_DOC.md) is just an ordinary quest-node pull under this rule — one turn,
  nothing special about it turn-wise. Travel from the respawn Town to the death node is free,
  same as any other movement.
- **Elite node:** not a distinct node type, so it has no turn structure of its own. Elites
  don't have a real map node at all yet (see the "Co-op multi-hero vs. Elite/multi-mob nodes"
  entry below for where they actually live — inside a node's dealt mob pool, not a separate
  location). ("Market Row" used to be listed here too, on the assumption it would fold into a
  Town-visit turn if it was ever built separately — retired 2026-08-22, since the Class Trainer
  already IS Market Row under a different name; see DESIGN_DOC.md Section VII.)

**Why this matters beyond bookkeeping:** the simulator's existing "Gold after a fixed number
of trips" metric is not a fair unit for comparing classes, since a trip's real length (pulls,
Town visits, crossings) varies a lot per class and per run. Turns (as defined here) are the
actual comparable unit of play — a metric like Gold-per-turn is what should be used going
forward for any cross-class or cross-level comparison, not Gold-per-trip or Gold-per-fixed-
trip-count. Not yet built into `macro_sim.py`'s reporting -- currently only `pulls` is tracked
per trip; Town/Trainer/Border-crossing turns aren't counted as their own units anywhere in the
simulator yet.

### Co-op multi-hero vs. Elite/multi-mob nodes (a "Hogger battle")

Multiple heroes (e.g. a Warrior and a Cleric) fight a shared mob threat together, co-op only.
Each round, every present hero's card totals together against the mob's number that round --
a pooled-party-damage model, not parallel independent 1-on-1 fights the way every solo pull
works. **Combat resolution mechanic: locked and built**, see `sim/condensed_party.py`
(2-4 heroes, damage/Block pool into a shared mob HP that whittles across rounds same as solo,
validated via a 540-check regression proving it reproduces every existing solo result exactly
when run with one hero).

**Targeting, locked:** whoever played the highest-Aggro card that round takes the leftover
damage the party's pooled Block didn't absorb. Aggro is a dedicated, flat per-card number
(0-4, class-weighted, no cumulative tracking), replacing an earlier "derive it from
Damage/Block/Heal" idea that couldn't resolve real ties. **All 36 per-card values are
assigned and locked** (in each class's own `CARDS` dict, the `aggro` field -- the single
source of truth, not a separate table). Tie: highest raw damage among the tied cards tanks
it (checked directly -- damage narrows most ties but not all, e.g. three different classes'
Aggro=1 cards all deal exactly 3 damage). Still-tied: left to table agreement, no third
automatic number. `grants_range` only voids the leftover if the evading hero would have been
that round's target (otherwise irrelevant that round, not a broad party-wide negation).
Killing-blow riders (Warrior's Execute, Rogue's Cutthroat) prevent the mob's attack for the
whole party if played by anyone and the pooled damage kills that round. If the targeted hero
can't absorb the leftover, they die -- no spillover. A dead hero stops contributing and is no
longer a valid target; survivors keep fighting (win = mob dies before every hero does, loss =
every hero dies first). This *is* the scoped, called-out Aggro exception to "no
aggro/targeting system exists in QUEST" that was flagged as a risk when this was still an
open question -- confirmed narrow to this one co-op mode, not a quiet reopening of the
general rule.

**Multi-mob co-op nodes vs. single-Elite nodes, decided (mode-gated) -- reverses an earlier
call.** Previously this entry considered "multi-hero vs. multi-mob" and set it aside as
seeming unworkable, in favor of "multi-hero vs. one Elite" only. That's now reversed for
co-op specifically: **a single tougher Elite mob is available in every mode (solo,
competitive, co-op) and never changes node behavior -- a node still holds exactly one mob.
A node holding *more than one simultaneous mob* is a co-op-exclusive option** (some or all
co-op nodes, not yet decided which -- see open items below). This isn't arbitrary: a solo
hero facing two mobs' pooled stats would be facing an unwinnable wall by construction (mob HP
above ~15-16 was already found literally unwinnable against one hero's damage ceiling, see
`CLASS_BALANCE_GUIDE.md`'s "Elite trio, derived" section) -- multi-mob nodes are only ever
survivable with a party's pooled cards, so gating them to co-op isn't a restriction, it's the
only mode where the content is playable at all. Practically, this also means co-op difficulty
doesn't need a separately hand-authored "Elite" content pool -- the existing Standard (and
future Spike/Elite) mob rosters can be reused directly as raw material, with **how many mobs
get dealt to a node** becoming the real co-op-difficulty lever instead of bespoke stat design.
This is an amendment to "Zone-node mob dealing"'s already-resolved "a node always holds
exactly one current mob" rule (above) -- co-op is now a deliberate, narrow, called-out
exception to that rule, same treatment as the blind-refill exception gets.

**Multi-mob resolution mechanic superseded -- mobs stay separate, no stat-summing.**
The original approach (sum every simultaneous mob's HP and round-by-round atk/block into one
flattened pattern, resolved through the single-shared-mob `condensed_party.py` engine
described above) is retired for nodes holding more than one mob. It worked mechanically but
had two real problems, both raised externally (Gemini review) and confirmed here: real
arithmetic homework at the table before a round can even start, and no way to represent mixed
`mob_type` once two mobs' stats are merged into one pattern. This replacement applies to any
node that *starts* with 2+ simultaneous mobs, which only ever happens in co-op.

**The original pooled engine is reclassified as a Boss-tier-only mechanic, not a general
"single mob" rule -- correction from an earlier pass of this entry.** Pooling both damage
*and* Block across the whole party, with a single Aggro-decided hero taking the one leftover
attack, is a special treatment meant for a fight the whole party is ganging up on as one unit
-- that's a Boss-fight feel (no Boss tier exists yet, zero content designed), not the Elite
tier that's actually built and tested today. **Elite fights (single tougher mob, available in
every mode) use the new round-robin/atomic engine described below, same as multi-mob nodes --
they just degenerate to the trivial M=1 case:** only the loudest hero is ever assigned the
mob's attack each round, and every other present hero's own block goes unused that round
(nothing pools to bail them out, since pooling no longer exists outside a real Boss fight).
This is a real, accepted difference from a Boss fight, not an oversight -- being ganged-up-on
as a unit is specifically what should make a future Boss feel different from an Elite.

**Which mechanic governs a fight is fixed by how the node *starts*, and never changes
mid-fight.** A multi-mob node that whittles down to exactly one surviving mob by round 2 or 3
stays on the round-robin/atomic engine for its remaining rounds -- it does not switch over to
the pooled engine just because the live mob count happens to hit one. Only a node that is
itself designated a Boss encounter from the start (not yet designed) uses the pooled engine at
all.

**Locked, not yet built.** This is now the primary co-op engine -- it governs both multi-mob
nodes and Elite fights, per the reclassification above. The existing pooled engine in
`sim/condensed_party.py` isn't being deleted (it's still correctly validated code), but it has
no current use case until a Boss tier is actually designed -- it should be treated as
dormant/reserved, not as the thing Elite fights run through. Next step if picked up is a new
resolver function, likely `simulate_party_multimob` or similar, sitting alongside the existing
pooled path in the same file rather than replacing it outright:

- **Mobs are tracked as fully separate entities** -- own HP, own round-by-round atk/block/
  `mob_type` pattern, no merging at any point.
- **No pooling and no splitting, on either side.** Each hero's own card's damage is
  independently pointed by the party at exactly one surviving mob (heroes who happen to
  target the same mob still add up naturally, but no shared "pool" number is ever written
  down, and no single hero's own number is ever divided across two targets). Checked directly
  that this loses no reachable outcome a pooled-then-split model could reach, and that
  personal block (below) is strictly *more* expressive than a pooled Block would be, since two
  heroes can protect two different attacks in the same round, which one shared block value
  split to a single target structurally cannot do.
- **Enemy Phase, in order, once Hero Phase damage has resolved and any killed mobs have been
  removed:** rank surviving heroes by this round's Aggro (loudest first; tiebreak: highest raw
  damage among tied cards; still-tied: table agreement, unchanged from the single-mob rule).
  Rank surviving mobs by this round's printed ATK (highest first; **tiebreak not yet decided**,
  see open items). Round-robin assign highest-ATK mob to loudest hero, next to next-loudest,
  ..., **wrapping back to the loudest hero again if mobs outnumber heroes** (deliberately not
  capped at party size -- capping was considered and rejected specifically because it would
  remove "more mobs than heroes increases threat," which is the entire point of a multi-mob
  node existing).
- **`grants_range`:** an evading hero stays in the round-robin assignment (never drops out,
  never shifts anyone else's pairing) -- any of *their* assigned attacks that come from a
  melee-type mob are zeroed, whether it's their first or a wrapped-second assignment. Ranged
  mobs unaffected, matching solo behavior.
- **Block is personal only, never routed to an ally, never split.** If a hero is assigned two
  attacks (the wraparound case), their own block auto-applies to the first (larger, since mobs
  are ATK-sorted before distribution) of their two assigned attacks -- **proven, not just
  assumed, to never be the wrong choice**: for ordered attacks a >= b and a single block value
  k, applying k to a is provably never worse than applying it to b (identical when k<=b,
  strictly better when k>b). Safe to print as a flat, zero-decision rule.
- **Overflow and death:** unblocked damage from each of a hero's assigned attacks comes only
  out of that hero's own HP, no spillover to teammates. A dead hero stops contributing and
  drops out of Aggro ranking and round-robin assignment for remaining rounds; survivors keep
  fighting (same win/loss/flee framing as the single-mob rule above).
- **Killing-blow riders (Warrior's Execute, Rogue's Cutthroat) are scoped per-mob, not
  party-wide -- a real change from the single-mob wording above, made necessary by mobs no
  longer being one shared entity.** A killing-blow card only prevents an attack from the
  specific mob its own damage was pointed at, if that mob dies this round. It has no effect on
  any other surviving mob's attack that round.

**Earlier "sum two mobs' stats" testing (Elite+Standard, 2-Standard combos, the 49.3%-75.6%
spread finding) is now historical** -- it validated that a multi-mob node *can* be made
winnable at all, which is still true and useful context, but the specific stat-summing
approach it tested no longer reflects the locked mechanic and shouldn't be reused directly;
any future balance pass needs to test against the separate-mobs engine once it's built.

**Still genuinely open, not decided:**
- **Tiebreak when two surviving mobs have identical this-round ATK.** The hero-side tiebreak
  (highest raw damage among tied Aggro cards) doesn't have an obvious mob-side equivalent --
  not yet picked.
- **Trigger/frequency for multi-mob nodes** -- every co-op node, a subset of designated
  "hot" nodes always dealing multiple mobs, some probability, or something else. Not decided.
- **Elite mob content/stats for real party math** -- the existing solo-baseline Elite trio
  (Bulwark/Berserker/Warlord, HP=12) is confirmed too weak for 2-hero party math (100% win
  rate, near-zero cost, everywhere) and needs its own re-derivation. Per the reclassification
  above, this re-derivation now needs to run against the round-robin/atomic engine's M=1
  degenerate case (only the loudest hero ever takes the Elite's attack, others' block unused),
  not the pooled engine -- a materially different, likely harder matchup for the party than
  what the earlier pooled-engine combining tests explored.
- **Loot/reward scaling for a multi-mob kill** -- not addressed at all yet.
- **Boss tier itself is entirely undesigned.** The pooled `condensed_party.py` engine now has
  no live use case until this exists -- worth remembering it's reserved, not wasted, next time
  Boss content gets picked up.
- **The multi-mob engine itself is unbuilt.** Design is locked per above; `sim/condensed_party.py`
  only implements the single-shared-mob path today. See `gemini_prompt_multimob_coop.md` for
  the full write-up sent out for external review before implementation starts.

### Solved-hand risk in OTK combat
Original concern: static mob stat blocks + deterministic math means once a player finds the optimal 3-Energy line for a given HP/ATK threshold, the fight stops being a decision.

Resolution: de-risked for early-to-mid game, not by varying mob stats but because the *player's deck* is the actual moving target. Starter decks are small (~10-12 cards, AGGRO-scale), so a 5-card hand is a large, genuinely non-repeating fraction of the deck each pull. On top of that, deck pollution (Winded/Durability trash accumulating mid-session) and deck growth (Market buys, Cull) mean the same nominal mob gets harder or easier to solve over the course of a trip even though its stats never move. No mob-side variance needed to avoid staleness for most of a play session.

Residual risk: once a player has Culled and bought into a stable, near-final deck, round-to-round variance shrinks back to just draw order, and the collapse risk could reappear. Arguably correct for a Final Boss "exam" (it should test whether the deck was built right, not whether you can adapt on the fly). If mob-side variance is ever needed, reserve affixes (WoW Mythic+-style modifiers, visible at reveal, no hidden info) for high-tier zones / the Final Boss specifically, not as a general-purpose fix.

### Multi-round Slog persistence
Decided: multi-round mob battles **whittle the mob's HP down** across rounds — damage dealt in a failed OTK attempt carries over. A Slog round two is a smaller remaining check against a fresh hand, not a repeated fresh attempt at the original threshold. See `DESIGN_DOC.md` §2 (Combat as a Toll).

### Exhaust scope (Wall of Ice, Confound, and any future Exhaust-tagged card)
Original concern: AGGRO's "exhausted for the encounter" is a bounded, real cost because an AGGRO encounter is a long, rare, session-defining raid fight. QUEST's pulls are short and frequent by comparison — if exhaust mapped literally onto "the pull," a one-time panic button would come back almost immediately, undermining how precious these cards read in AGGRO.

Decided (for now): exhaust is scoped to **the trip** — an exhausted card is gone until a Town visit, not just until the next pull. Matches AGGRO's original weight.

Not yet implemented: the sim currently starts every pull from a fully fresh deck (no cross-pull memory at all), so it can only actually enforce "per pull" scope today. Trip-scoping needs the cross-pull trip simulator (same piece of infrastructure the Winded-pollution hypothesis has been waiting on) before it's real in the numbers, not just on paper.

Flagged for reconsideration: a pure trip-lock with no reset before Town might prove too punishing in practice. A softer variant — an exhaust cooldown (tokens, or a reset after some number of pulls rather than only at Town) — is worth testing once the trip simulator exists and can show whether trip-only-reset actually feels bad or not.

### Loot decay by round count (pull-level, distinct from Decaying Bounties)
Decided in principle: loot value drops in steps based on how many rounds a pull took to clear, not a single fixed round-count for every mob. The breakpoint for the top loot tier should be **mob-specific and simulation-derived** — set near the average/median rounds-to-clear across classes for that particular mob, not the fastest class's floor. That keeps the top tier consistently reachable for fast classes (Warrior, Wizard) while leaving it possible-but-unreliable for slow classes (Cleric) — a real chance via a good hand, not a hard wall that makes slowness an automatic loot penalty. Matches the existing "card draw is the only randomness" principle rather than turning class choice into a deterministic loot gate.

This is a different mechanic from Decaying Bounties (`DESIGN_DOC.md` §6) even though it reuses the same "decay" vocabulary on purpose — Bounties decay per Town-visit timing at the trip level, this decays per round-count at the single-pull level. Complementary, not the same system.

Not yet implementable — no loot-tier system exists in the design yet. This is the trigger/threshold rule to apply once one does; the actual round-count breakpoints need real simulation data per mob once mobs are calibrated.

### Pet respawn boundary (Ranger, Necromancer)
Same underlying issue as exhaust scope above, resolved the same way. AGGRO's rule ("Exhausted for the rest of the encounter... revives at full HP between encounters") is a bounded, real cost because an AGGRO encounter is long and rare; QUEST's pulls aren't.

Decided (for now): the pet is gone until a Town visit, not just until the hero's next pull. Not yet implemented — same cross-pull-state dependency as exhaust scope, and the same future softening (a cooldown/token reset short of a full Town visit) is worth revisiting once trip-level simulation exists and there's real data on whether losing the pet for a whole trip reads as too harsh, especially given how central the pet is to Ranger's and Necromancer's whole kit.

### Durability's escalating-ATK trigger — tested, and removed

**What it was.** A specific implementation of the Durability pillar, built to give the general "gear wears down, Town-only repair" concept in `DESIGN_DOC.md` §3 a concrete trigger: a flat +1 stack per pull, universal across all classes regardless of performance, adding a fixed bonus to the mob's effective ATK on every subsequent pull (`DURABILITY_ATK_PER_STACK`), living on the character board rather than the deck, uncleared anywhere in the field. This was one specific proposal for the pillar, not the only possible one.

**Why it was built.** Cleric could survive a field trip indefinitely with the trip simulator's original setup — its own in-combat sustain (Sacred Balance, an unconditional 2 HP heal on every Cast-type damage card, completely un-gated by Bag resources or Exhaust) kept pace with a flat, non-escalating mob ATK forever. Durability's escalating danger was the fix: no matter how well-provisioned or well-played, every pull got a little more dangerous, so a trip had to end eventually.

**Why it was removed.** Once the actual source of the infinite-sustain problem was found and fixed directly — Sacred Balance set to 0 (see the Sacred Balance heal-value entry, this file, and `engine.py`'s `SACRED_BALANCE_HEAL`) — Durability's original job was already done by something else. Verified directly: with Durability fully disabled, Cleric no longer runs away to 30+ pulls; all three classes land in a normal, bounded 5.5-6.3 pull range. Whatever Durability still did on top of that was just compressing trip length further (roughly 3.5-5.2 pulls with it on vs. 5.6-6.9 off) — a pacing preference nobody had actually confirmed wanting, not a mechanic anything else depended on.

On top of being redundant, it caused real, repeated harm to this session's own testing process: because it lived as a single mutable module-level global with a silent default, multiple test results got reported under the wrong condition without anyone (including the person running the tests) noticing until the numbers were compared and didn't add up. That's a bad sign for a mechanic meant to model a per-pull escalating cost in the real game too — if it's this easy to lose track of whether it's "on" in a controlled testing environment, it's not a mechanic with a clear, legible state at the table either.

**Decided:** removed from the sim entirely — not left dormant at a default value, the code itself is gone (`DURABILITY_ATK_PER_STACK`, `durability_stacks`, and the mob-ATK-boost logic in `run_trip`).

**What this does NOT settle:** the general Durability pillar concept in `DESIGN_DOC.md` §3 (gear wear, Town-only repair) is not rejected — only this specific trigger mechanism is. If a future need arises for something that forces a trip to end independent of Bag/Food/Water scarcity, Durability-the-concept is still on the table, but it needs a fresh, deliberately-chosen trigger rather than reviving this one by default. Bag/restorative scarcity is, for now, the sole mechanism bounding trip length — see the Food/Water sweep data (this session) for what that actually produces per class.
