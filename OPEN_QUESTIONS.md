# QUEST — Open Questions

Design tensions and undefined interactions flagged before prototyping starts. Move an item to `DESIGN_DOC.md` once it's actually settled — don't mark it resolved just because it's discussed.

## Unresolved

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

*(Items 2-5 previously here — Rest vs. Claim structure, Winded-trigger rule, Wizard outcome
variance under the Cast Penalty, ranged-mob-never-engages — all referenced a Winded/OOM +
Cast Penalty + Engagement system that was cut entirely, not deferred, once condensed combat and
the macro loop replaced the original AGGRO-scale translation (see `CONDENSED_COMBAT.md`'s
"Exhaust dropped entirely"). Removed as stale rather than left to imply they're still live —
caught and flagged during the `DESIGN_DOC.md` rewrite/audit. If Wizard's actual current
all-or-nothing outcome variance under condensed combat's real rules ever needs its own
investigation, that's a fresh, unrelated question — see task #29.)*

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
Scout existed). Reshuffles the discard back in whenever it runs dry (possible mid-turn,
since multiple heroes can pull multiple times before a turn ends) — never actually stays
empty. See "Elite Spikes" below for how a zone's deck can extend past a pure single-tier
pull.

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

**Elite Spikes, and zone decks as an explicit recipe rather than a raw tier pull, decided:**
mob tiers are scoped by level (e.g. a "Tier 1 Standard" pool, eventually a "Tier 1 Elite"
pool once Spike-tier mobs exist, then Tier 2 versions of both later). A zone's actual deck
is its own authored recipe built from those pools, not just "draw from one tier" -- e.g. a
Tier 1 zone's deck could be "18-card Tier 1 Standard + 2-3 Tier 1 Elite" shuffled together,
rather than pure Standard. This replaces treating `MOB_TIERS`'s two pools as the only unit a
node can draw from; the deck-building step itself becomes the authored content, of which a
pure-Standard deck is just the simplest case. **Zone deck composition (how many of each
mob, including how many Elites) is public knowledge** -- printed on the zone, not hidden --
so contesting a node with Elites mixed in is a calculable risk, not a blind unknown, matching
how risk is handled everywhere else in this project.

**Blind refills draw from the full zone deck, Elites included -- no special-case exception.**
An earlier draft (from an external design pass) proposed Elites could never be drawn on a
blind refill, redirected to a held state instead -- rejected as unnecessary complexity once
traced through: it would have needed a new card-lifecycle state (where does a skipped Elite
go, is it visible before its deferred deal, does it override the node's normal next-turn
deal) with no clean answer to any of those questions. The simpler rule needs none of that
machinery: a blind refill is just a real draw from the whole deck, and `macro_sim.py`'s
existing `_pull_exceeds_risk` risk-tolerance check already covers the consequence -- a
player (or the simulated agent) who doesn't like the zone's known Elite odds simply declines
to contest that node this turn, exactly like any other lethal-pull decision already modeled.
Nothing new to build here beyond not carving Elites out of the pool.

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
change. No task tracked for the build yet; Elite Spikes specifically are additionally
blocked on task #20.

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
