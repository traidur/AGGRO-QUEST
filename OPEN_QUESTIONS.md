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

### 6. Co-op multi-hero vs. one Elite mob (a "Hogger battle")

Future idea, not yet decided, deliberately different from multi-hero-vs-multi-mob (considered
and set aside — doesn't seem like it'd work). The shape instead: multiple heroes (e.g. a
Warrior and a Cleric) all fight one shared Elite mob together, co-op only. Elite mobs would
live in their own pool, pulled out only in co-op mode — implies **deck/content composition
already varies by mode (solo/competitive/co-op)**, a broader principle worth noting on its
own, not just for Elites specifically.

Structure: still 3 rounds, still one card per hero per round, but each round every present
hero's card gets totaled together against the Elite's number that round — a pooled-party-
damage model, not parallel independent 1-on-1 fights the way every pull works today. If the
Elite's damage that round exceeds what the party's combined cards absorb, something has to
actually take the leftover as real HP loss. Two candidate ways to decide who:

1. **No splitting — the players choose who absorbs it all**, each round, by agreement. Zero
   extra bookkeeping, easy to teach, but risks being a solved, no-tension choice in practice
   (the obvious highest-HP/tankiest hero just always volunteers, same choice every round).
2. **A simplified Aggro number printed on every card** — whoever played the highest-Aggro
   card that round takes the leftover damage. Real tactical texture (do you play your best
   card even though it paints a target on you?), and ties the damage-distribution question to
   an actual play choice instead of pure negotiation. Real cost: a new number to track on
   every card, and it's a scoped reintroduction of something close to AGGRO's real Threat
   system — worth flagging directly, since "Threat is gone entirely, no aggro/targeting
   system exists in QUEST at all" has been a stated design pillar since the very first
   translation pass (`CLASSES.md`). If this direction is taken, it should be treated the same
   way the blind-refill exception was: a deliberate, narrow, called-out exception scoped to
   this one co-op mode, not a quiet reopening of the general rule.

Not decided which of the two (or something else) is right. Not yet built.

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
system reused — 3 copies each of the 5 locked Standard-tier mobs (Grunt/Bruiser/Enforcer/
Raider/Ambusher), 15 cards total. Reshuffles the discard back in whenever it runs dry
(possible mid-turn, since multiple heroes can pull multiple times before a turn ends) —
never actually stays empty.

**Node refill, decided:** replace, not stack. A node always holds exactly one current mob;
dealing a new one over an unclaimed mob simply replaces it. No node-congestion sub-system.

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

Not yet built — this is a real addition to the macro-loop engine (zone/node state, turn-based
dealing logic), sized more like a new subsystem than a parameter change. No task tracked for
the build yet.

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
