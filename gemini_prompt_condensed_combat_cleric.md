I'm designing a board game called QUEST — a prequel/companion to an existing project called AGGRO (a Slay-the-Spire-x-WoW card-based deckbuilder raid-boss game). QUEST reuses AGGRO's classes and card economy but is a logistical engine-builder simulating MMO questing/farming/looting, not raid combat. Design philosophy: no movement tax, carrots not sticks, determinism over dice (no RNG anywhere — enemy behavior is fully known in advance, the only randomness is which cards you draw), shared DNA with AGGRO.

## Why "condensed combat" exists

I originally translated AGGRO's real combat system 1:1 into QUEST — 10-card deck, 5-card hand, 3-Energy budget per turn, Cast/Instant card types, a Cast Penalty for being "Engaged" by a melee mob, an Exhaust mechanic (cards get spent and must be refreshed by consumable resources), and a "held/power card" mechanic for buffs that persist across multiple pulls until you rest. This required a lot of supporting machinery to work correctly: dummy placeholder cards for exhausted/held cards, refresh-policy tuning, and even a rollout AI (a forward-simulating decision engine) just to play the resulting decks well.

That complexity is appropriate for AGGRO, where the fight *is* the game. But in QUEST, combat is supposed to be a fast "toll check" gating access to loot — the real game is the logistics loop (trip planning, bag space, loot decay, how many pulls you can do before you need to head back to town). By the time I'd built and debugged the full Exhaust/held-card system, combat-level complexity was rivaling the macro loop's, which is backwards for what QUEST is trying to be.

So I started a parallel prototype: **condensed combat** — a much smaller, simpler combat model, built from scratch per-class, to see if it can replace the AGGRO-scale system entirely.

## Core structural rules (apply to every class)

- **Deck = 6 unique cards, hand = 4, 3 rounds per pull.** If the mob isn't dead by the end of round 3, it flees — no reward, fight ends.
- **One card played per round**, not a subset chosen within an Energy budget. Draw 4, choose and sequence 3 of them across the 3 rounds; the 4th is deliberately left unplayed. Which 3-of-4, and in what order, is the whole tactical decision.
- **No Energy pool, no card costs.** Pure sequencing/ordering puzzle, not a knapsack problem.
- **No dice, anywhere.** Mob "intent" — its attack value each round, and sometimes a Block value that reduces the hero's own damage output that round — is fixed and fully known in advance for the whole 3-round pull before the player commits to anything. The only randomness in the entire system is which 4-of-6 hand gets drawn each pull.
- **The deck fully resets every pull.** Nothing persists at the card level between pulls — this replaces AGGRO's Exhaust mechanic entirely. The working theory is that hand-draw variance (sometimes your best tools aren't in the 4 you drew) does the job Exhaust used to do, without any of the bookkeeping.
- **HP is the only thing that carries across pulls, and the only thing Food restores.** Testing "how many pulls can a hero string together before needing to stop and eat" is a first-class design question, not an afterthought.
- **Every card in a class's 6-card deck must be unique — no duplicate copies.** This turns out to matter a lot (see "card-only mechanics" below).
- **Mob rosters must be class-agnostic.** Any hero can conceivably fight any mob, so mob HP/attack patterns are never tuned differently per class. Class balance has to come from the hero kits themselves or from roster-wide changes that hit every class identically.

## The solver, not a simulator

Because the whole space is small (15 possible hands from a 6-choose-4 deck, a few dozen orderings, a handful of stance/mechanic branches), I built an **exact enumeration solver** per class instead of a Monte Carlo simulator — for every possible hand, it finds the provably optimal line (card order, plus any class-specific choices) rather than estimating a win rate from random trials. This is both cheaper and more precise than sampling at this scale, and it sidesteps needing anything like AGGRO's rollout AI.

## Things I tried and rejected (so you don't re-suggest them)

- **Persistent "held/power card" buffs that survive across pulls** (AGGRO has these) — dropped. Doesn't fit "deck resets every pull." Where a card's flavor was "a lingering blessing," I rescoped it to a buff that lasts only the rest of the *current* pull instead.
- **Out-of-combat healing between pulls** — considered, then dropped for consistency: neither of the other two built classes (Warrior, Wizard) has any between-pulls mechanic, so giving Cleric one uniquely would break the shared skeleton.
- **Tuning mob HP/attack per class** to fix a Warrior/Wizard performance gap — explicitly rejected. Any hero can fight any mob; the roster has to be one shared set of numbers.
- **Letting a killing blow interrupt the mob's action that round** (i.e., mob doesn't get to hit you back the round it dies) — tested directly (see numbers below), rejected in favor of keeping the mob's action unconditional, for both thematic reasons (mob intent is a fixed script, shouldn't have a hero-dependent exception) and strategic reasons (removing it collapses a real risk/reward decision — "do I have enough to finish this round, and is it worth the exposure" — into an always-correct move).
- **"Stacking" mechanics needing physical tokens or counters** — turns out to be a non-issue as long as decks stay duplicate-free. If only one card in a 6-card unique deck carries a given tag, that mechanic can never exceed a single "stack" within one pull, so it's always just a binary "has this card been played yet" check, fully readable from the cards already on the table. No token needed for any of it. Same logic extended to a stance-declaration mechanic (see below) by printing stance values as mirrored text on opposite ends of the card — orienting the card physically *is* the state, no separate token at all.

## Warrior — built, tested

Six cards, two extra mechanics: **Stance** (Guardian/Champion, declared once, may flip to the other exactly once across the 3-round sequence — implemented with zero physical components by printing each card's two stance values mirrored on opposite ends, so orienting the card *is* the declaration) and **Sunder** (a card marks the mob; the next damaging card gets +1 — binary in practice, not a real counter, since only one card in the deck carries the tag).

| Card | Guardian | Champion |
|---|---|---|
| Heavy Strike | 2 DMG | 4 DMG |
| Sunder Strike | 2 DMG (stance-neutral) | 2 DMG — places Sunder marker |
| Execute | 3 DMG, unconditional | 6 DMG if mob HP ≤ 50%, else 3 |
| Rally Blow | 2 DMG / 4 Block | 4 DMG / 2 Block |
| Shield Wall | 6 Block | 3 Block |
| Brace | Reactive — no static value. Deals 4 DMG if the previous round's card was pure-Block; grants 4 Block if it was pure-DMG; player's choice if it was both; nothing if played first. |

Diagnostics (verified, not estimated): no dead cards, usage spread 23-78% across the kit, and the stance flip is strictly necessary (changes the outcome, not just cosmetic) in 40.6% of winning lines.

Multi-pull chain-testing (draw a fresh hand each pull, HP carries forward, no recovery, stop when HP hits 0) against the current 5-mob roster: **averages ~2.9 total pulls survived, only ~1.0 of which are wins**, before HP runs out. Cost per win is close to Warrior's entire max HP (18).

A/B test isolating whether raw damage or mitigation is the better lever for completing more pulls: **+25% DMG raised wins-before-Food by +67%; +25% Block raised it by only +4%**, despite Block extending raw survival time slightly more. Reason: almost every mob pattern tested escalates (hardest hit is always the last round), so killing faster doesn't just reduce exposure linearly, it specifically skips the worst round — Block only ever saves a flat amount per round it's used.

## Wizard — built, tested

No stance system (that was always Warrior-specific). Instead: **Positioning** (a card can grant "At Range" for that round only — if the mob is melee-type, its attack that round doesn't land at all; no effect vs a ranged mob — directly reused from AGGRO's existing `evades_melee` logic) and **Spellweave** (a repurposing of AGGRO's real Spellweaving mechanic — since condensed combat has no within-round multi-card play, it was relocated to cross-round: playing a Spellweave-tagged card arms a single-use trigger; the next eligible "payoff" card consumes it for a bonus; doesn't stack).

| Card | Effect |
|---|---|
| Fire Blast | 3 DMG — Spellweave source |
| Arcane Volley | 6 DMG, 8 if consuming an armed Spellweave trigger |
| Snap Freeze | 1 DMG + grants At Range this round — Spellweave source |
| Ice Barricade | 10 Block — no Spellweave/positioning interaction |
| Fire Ball | 5 DMG, 7 with Spellweave |
| Frozen Shot | 2 DMG + grants At Range, 4 DMG with Spellweave |

Multi-pull chain-testing: **averages ~2.8 total pulls, ~1.3 of which are wins** — actually *ahead* of Warrior proportionally, despite having roughly half Warrior's max HP (10 vs 18). Cost per win as a fraction of max HP: Warrior ~103% of its pool (barely affords one win), Wizard ~78%. Wizard's kit is more efficient per card play because Snap Freeze/Frozen Shot bundle damage and defense into a single card slot, where Warrior's Block always costs a dedicated card.

## Mob roster (shared, class-agnostic, current draft)

Working "anchor" mobs derived by working backward from the target "~90% single-pull win rate, 3-5 pulls completed before Food" — the two independently-derived mobs for Warrior and Wizard landed close to each other:

| Mob | Pattern (ATK/mob-Block per round) | HP |
|---|---|---|
| Grunt (Warrior anchor) | 2/1, 2/1, 3/0 | 7 |
| Skirmisher (Wizard anchor) | 1/0, 2/1, 3/0 | 9 |

Both anchors are considerably weaker than what's in the wider draft roster (which includes harder "spike" mobs like Brute/Elite/Champion, sub-1.5 wins-before-Food, intentionally not meant to be pulled repeatedly). Even at baseline before this tuning pass, hitting "3-5 repeatable pulls" required roughly half the threat level of the original draft roster.

Also directly tested: interrupting the mob's action on the round it dies. Single-pull win rate doesn't change at all (the only losses at these anchor mobs are timeouts, not death-races), but multi-pull performance explodes 3-5x under the interrupt rule (Warrior 3.73 → 11.96 wins-before-Food; Wizard 3.81 → 18.99). Kept the no-interrupt rule anyway, for the thematic/strategic reasons above — but it's worth knowing that single rule is one of the most load-bearing pieces of the whole difficulty curve.

## Where Cleric is now, and the actual problem

Cleric's third axis (alongside DMG and a little Block, which Warrior and Wizard also have in some form) is **Heal** — restoring HP, resolved during the hero's own turn (before the mob acts that round, same timing slot as Block/Positioning), capped at max HP (no overhealing banked forward), and unlike Block/Positioning it isn't tied to a specific round's threat — any "excess" just persists as a real buffer for whatever round tests it next.

Also has its own version of the card-only stacking mechanic, currently named **Sacred Balance** (reusing Cleric's real AGGRO passive name, repurposed — Sacred Balance in AGGRO is "heal on playing a damage Cast card," but that's been demoted to plain baked-in card text with no mechanic name attached; the name was freed up for this new stacking resource instead, since "balance" fits a build-up-then-tip resource well and it's Cleric's most recognizable term). Two cards grant a Sacred Balance stack (no decay — persists the rest of the pull); two different cards (not just one) read the stack for a bonus.

Current draft kit:

| Card | Effect |
|---|---|
| Heal | Base 6, +1 per Sacred Balance stack |
| Smite | 3 DMG, 3 heal |
| Call of the Void | 5 DMG, 2 heal |
| Blessed Barrier | 4 Block, +1 per Sacred Balance stack |
| Blessed Fortitude | 1 heal, grants Sacred Balance |
| Void Mark | 2 DMG, grants Sacred Balance |

**The problem:** measuring the best possible 3-round damage output per hand (max over all 15 possible hands, and separately the *worst* hand's best-case ceiling), across all three classes:

| | Absolute max (best possible hand) | Smallest max (worst possible hand's ceiling) |
|---|---|---|
| Warrior | 12 | 6 |
| Wizard | 16 | 8 |
| Cleric | 10 | **2** |

Cleric's floor isn't just lower, it's a different category of problem — a bad draw can leave it dealing only 2 total damage across an entire pull. Root cause, checked directly: Warrior has 5 of its 6 cards capable of dealing some damage, Wizard has 5 of 6, but **Cleric only has 3 of 6** (Smite, Call of the Void, Void Mark — Heal, Blessed Barrier, and Blessed Fortitude are pure 0-damage support cards). Since there are only 3 non-damage cards in Cleric's deck and the hand size is 4, the worst possible draw is literally "all 3 support cards plus your weakest attack" — a real, unavoidable scenario, not an edge case, and when it happens the player is stuck with Void Mark's 2 damage for the entire pull.

Two options on the table, not yet decided between:
1. **Give more of the support cards a small secondary damage component** (e.g., Blessed Fortitude currently deals 0 damage at all — give it 1-2 DMG alongside its heal-and-stack effect, matching how Warrior's Rally Blow and Wizard's Snap Freeze are hybrids rather than pure specialists). Raises the floor directly, since even a "bad" hand would have something extra to swing with.
2. **Accept the 3-of-6 ratio as Cleric's deliberate identity** (the purest support class of the three) but compensate by making the few damage cards it has hit harder, especially Void Mark specifically, since it's the card most likely to be a player's only option in a bad hand.

Cleric's framing throughout this design process has been "a healer who fights when nobody's dying" (a real line from the source game's tutorial text) — a hybrid identity, not a pure healbot. Given that framing, does a genuinely damage-less bad hand undercut the identity, or is a hard floor an acceptable, even appropriate cost for being the most support-leaning of the three classes? What would you actually do here, and is there a third option neither of the two above considers?
