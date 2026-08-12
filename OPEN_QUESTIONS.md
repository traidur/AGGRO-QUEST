# QUEST — Open Questions

Design tensions and undefined interactions flagged before prototyping starts. Move an item to `DESIGN_DOC.md` once it's actually settled — don't mark it resolved just because it's discussed.

## Unresolved

### 2. Rest vs. the Claim structure
Clearing Winded requires Resting (forfeiting a pull) + consuming Food/Water. Undefined: does Resting happen *instead of* claiming a target in Phase 2, or is it a separate action outside the 4-phase loop? If it competes with claiming, a low-priority player could get starved out of both combat and recovery in the same round.

### 3. Winded-trigger rule definition
Does Winded/OOM trigger per heavy-spell-cast (Cast-type card played) or per total Energy spent regardless of card type? This isn't just flavor — it determines whether healer classes (Cleric, and partially Paladin/Druid) structurally pollute their own deck faster than block-sustain classes (Warrior, Rogue), since their sustain tool is itself a Cast-type card. See `DESIGN_DOC.md`'s Class Archetypes section. Testable directly once the balance sim can run multi-pull trips.

### 4. Wizard outcome variance
The Opening Range rule (mob starts at range, Engagement applies the Cast Penalty from round two of a Slog on) means Wizard's outcomes split hard: clean OTK at zero risk, or a spiraling Slog that gets worse every round on top of already having ~0 Block. Thematically appropriate ("mage plays are all-or-nothing"), but the actual variance needs to be measured, not assumed survivable.

### 5. Ranged-mob-never-engages implication
If a mob is a ranged type and never Engages, does the Cast Penalty ever apply against it, even across a multi-round Slog? If not, that's a real matchup axis (hero archetype vs. mob range-type, not just hero archetype vs. mob HP/ATK) — worth deciding whether that's a feature to lean into or a wrinkle to dampen.

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

**Validated empirically that the underlying mechanic works, not yet that any specific content
is right.** Summing two mobs' stats directly (HP added, each round's atk/block added -- a
tabletop-executable rule, no new authoring) was tested through `condensed_party.py` against
every 2-Standard-mob combination and every Elite+Standard combination, for a representative
hero pair. Two Standard mobs alone couldn't reach a genuine coinflip even at the hardest
combo (best case 70.2% win rate) -- the Standard tier's max combined HP (20, from the
tankiest mob paired with itself) is below where a 2-hero coinflip plausibly needs to sit.
Elite+Standard combos did much better (best found: Bulwark+Grunt, HP=19, 52.4% win/23.0%
cost against one hero pair) -- but checked against all 15 possible hero pairs, that same combo
ranged 49.3%-75.6% win rate, not class-agnostic. This is the same structural finding already
locked from the original solo Elite derivation: no single mob (or, now, no single *multi-mob
combo*) is class-agnostically tight on its own -- pool-averaging across several combinations
is what actually closes the spread (got the solo trio down to ~11pp), and the same
pool-search methodology should transfer here once real derivation work starts.

**Still genuinely open, not decided:**
- **Trigger/frequency for multi-mob nodes** -- every co-op node, a subset of designated
  "hot" nodes always dealing multiple mobs, some probability, or something else. Not decided.
- **Elite mob content/stats for real party math** -- the existing solo-baseline Elite trio
  (Bulwark/Berserker/Warlord, HP=12) is confirmed too weak for 2-hero party math (100% win
  rate, near-zero cost, everywhere) and needs its own re-derivation; today's combining tests
  were exploratory system-validation, not a proposed final answer.
- **Mixed `mob_type` when multiple mobs share a node.** Every test so far flattened a
  multi-mob encounter into one combined pattern with a single hardcoded `mob_type` -- a real
  simplification, not a decision. If a node genuinely holds two separate mob cards (say a
  melee one and Scout, the one ranged Standard mob), the more faithful model is probably that
  each mob keeps its own type independently -- a `grants_range` hero could plausibly evade the
  melee one's damage while still eating the ranged one's. Not built or decided either way.
- **Loot/reward scaling for a multi-mob kill** -- not addressed at all yet.

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
