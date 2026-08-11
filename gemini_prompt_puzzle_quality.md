I'm designing a board game called QUEST — a prequel/companion to an existing project called AGGRO (a Slay-the-Spire-x-WoW card-based deckbuilder raid-boss game). QUEST reuses AGGRO's classes and card economy but is a logistical engine-builder simulating MMO questing/farming/looting, not raid combat. Design philosophy: no movement tax, carrots not sticks, determinism over dice (no RNG anywhere except which cards you draw), shared DNA with AGGRO.

I want your honest, independent opinion on **puzzle quality specifically** — not "does the math work" (I've verified that extensively with an exact-enumeration solver), but "is this actually a good, interesting puzzle, or does it just look like one on paper." I'll give you the high-level shape first, then the real specifics, then my own prior self-assessment so you're reacting to and building on that rather than just repeating it.

## High-level shape

Combat in QUEST is meant to be a fast "toll check" gating access to loot — the real game is a logistics loop (trip planning, bag space, loot decay, how many fights you can complete before you need to head back to town). A direct translation of AGGRO's real combat system (10-card deck, 5-card hand, 3-Energy, Exhaust mechanic, a rollout AI just to play it well) got too complex relative to that role, so I built a much smaller parallel system from scratch: **6-card unique deck, 4-card hand, exactly 3 rounds per pull** (mob flees if not dead by round 3). One card played per round — draw 4, choose and sequence 3, one card is deliberately left unplayed each pull. No Energy costs. No dice anywhere: the mob's attack (and sometimes a Block value that reduces the hero's own damage output that round) is fixed and fully known for all 3 rounds before the player commits to anything. The only randomness in the whole system is which 4-of-6 hand gets drawn each pull, and the deck fully resets every pull (nothing persists at the card level — this replaces AGGRO's Exhaust mechanic).

Because the state space is small (15 possible hands from a 6-choose-4 deck, a few dozen orderings, a handful of mechanic branches per class), I built an exact solver instead of a Monte Carlo simulator — for every hand, it finds the provably optimal line rather than estimating from samples.

## The three classes, built and cross-tested

Each class gets DMG + a little Block/mitigation + one class-defining third axis, plus one signature mechanic. All three signature mechanics are deliberately **card-only** — no physical tokens or counters needed at the table, because every deck has zero duplicate cards, so any "stacking" mechanic tied to a single card's tag is automatically capped at a readable binary state (has this specific card been played yet, yes or no — visible just by looking at the play area).

**Warrior** — absorbs (DMG + Block). Signature: **Stance** (Guardian/Champion, declared once, may flip to the other exactly once across the 3 rounds) implemented with *zero physical components at all* — each card is printed with its two stance values as mirrored text on opposite ends, so physically orienting the card during placement *is* the declaration. Lay all three played cards the same way (no flip), or turn only the third one (flip before round 3), or the second and third together (flip before round 2) — the one-way rule is self-enforcing just by looking at the row. Also has **Sunder** (a card marks the mob; the next damaging card gets +1 — binary in practice, not a real stack, since only one card carries the tag).

| Card | Guardian | Champion |
|---|---|---|
| Heavy Strike | 2 DMG | 4 DMG |
| Sunder Strike | 2 DMG (stance-neutral) | 2 DMG — places Sunder marker |
| Execute | 3 DMG, unconditional | 6 DMG if mob HP ≤ 50%, else 3 |
| Rally Blow | 2 DMG / 4 Block | 4 DMG / 2 Block |
| Shield Wall | 6 Block | 3 Block |
| Brace | Reactive — no static value. Deals 4 DMG if the previous round's card was pure-Block; grants 4 Block if it was pure-DMG; player's choice if it was both; nothing if played first. |

**Wizard** — avoids (DMG + Positioning instead of Block). **Positioning**: a card can grant "At Range" for that one round — if the mob is melee-type, its attack doesn't land at all that round; no effect vs a ranged mob (directly reuses AGGRO's real `evades_melee` logic). **Spellweave** (repurposed from AGGRO's actual Spellweaving mechanic, relocated from within-round to cross-round since this system has no multi-card rounds): a card arms a single-use trigger, the next eligible card consumes it for bonus damage, doesn't stack.

| Card | Effect |
|---|---|
| Fire Blast | 3 DMG — Spellweave source |
| Arcane Volley | 6 DMG, 8 if consuming an armed Spellweave trigger |
| Snap Freeze | 1 DMG + grants At Range this round — source |
| Ice Barricade | 10 Block — no interaction with anything else |
| Fire Ball | 5 DMG, 7 with Spellweave |
| Frozen Shot | 2 DMG + grants At Range, 4 DMG with Spellweave |

**Cleric** — undoes (DMG + a little Block + Heal). Heal resolves before the mob acts each round (same timing as Block/Positioning), capped at max HP, not tied to a specific round's threat the way Block is — any "excess" just persists as a buffer. **Sacred Balance**: reworked from AGGRO's real passive of the same name into a binary ON/OFF state — Setup cards arm it, Payoff cards consume it for bonus damage *in addition to* their normal effect (not a trade-off).

| Card | Effect |
|---|---|
| Void Mark | 2 DMG. Setup — arms Sacred Balance. |
| Blessed Fortitude | +2 Max HP, Heal 2. Setup — arms Sacred Balance. |
| Heal | Heal 4. Payoff — if Sacred Balance ON, also deal 5 DMG, then turn it OFF. |
| Blessed Barrier | 4 Block. Payoff — same as Heal. |
| Smite | 3 DMG, 1 heal. No interaction. |
| Call of the Void | 5 DMG, 1 heal. No interaction. |

## Testing rigor so far (so you know what's already been checked)

- **Best-vs-worst-hand damage ceilings**, verified per class: Warrior 14 (ceiling) / 7 (floor), Wizard 16/8, Cleric 12/7 — deliberately balanced to a comparable range across classes after Cleric's first draft came in at a broken 10/2 (only 3 of 6 cards could deal any damage at all; fixed by making two support cards conditionally capable of damage instead of adding new dedicated attack cards).
- **Multi-pull chain testing** (draw a fresh hand each pull, HP carries forward, no recovery, stop at HP≤0) across a shared, class-agnostic 8-mob roster (never tuned differently per class — a hard rule) — currently lands around 4.5-4.6 pulls / ~2.0-2.2 wins per trip for all three classes, roughly comparable.
- **A real bug found and fixed via this testing**: Cleric's healing initially created a genuine "cannot die" equilibrium against several mobs (not just a slow decline — verified by checking net HP change across a *range* of starting HP values, since a high average-pulls number alone can't distinguish the two). Fixed with a distributed cut across three cards' heal values plus small ATK bumps on the affected mobs, re-verified with zero effect on Warrior/Wizard's numbers.
- **A/B tested whether raw damage or mitigation is the stronger lever** for completing more pulls: +25% DMG → +67% more wins-before-Food; +25% Block → only +4%, because most mob patterns escalate (hardest hit last), so killing faster skips the worst round entirely rather than just reducing exposure linearly.
- **Diagnosed a win-rate "cliff"** (jumps from 100% straight to 80% with nothing achievable near 90%) down to its root cause: only 15 possible hands means outcomes cluster into a small number of tiers determined by which 1-2 "key cards" a hand contains. Confirmed empirically that mob variety (giving mobs *some* Block/timing texture) smooths this far better than rebalancing card numbers would, without eroding the card identity differences already built.

## Our own prior self-assessment (react to this, don't just restate it)

We already asked ourselves whether this is a "true, interesting puzzle" and concluded: yes, with real evidence — 13 of 15 hands need a distinct optimal line depending on which mob they face, Warrior's stance flip is strictly necessary (not just cosmetic) in ~40% of winning lines, no card sits fully dead in any kit. We also concluded it does **not** feel like visceral "combat" — it reads as a tight tactical puzzle wearing combat's skin, which we decided is probably *correct* given the stated design goal (a fast, legible toll-check, not the emotional centerpiece — that's supposed to be the macro trip-planning loop). We flagged a real, unresolved risk: because the system is small and fully deterministic, a player who repeatedly faces the same mob could eventually approach rote memorization of the "answer" rather than genuine puzzle-solving, though we estimated this risk is lower than it first appears once you account for mob variety and multiple classes diluting real repeat-exposure per exact situation.

## What I actually want from you

Genuinely critique the puzzle quality, not the math. Specific angles I'd value your take on:
1. Do the three signature mechanics (Stance-timing, Spellweave, Sacred Balance) feel meaningfully distinct as *puzzles*, or are they three skins on the same underlying "sequence a setup before a payoff" idea? Is that actually a problem if so?
2. Is 3 rounds / 4-card hand / 6-card deck the right size, or does it feel too thin to sustain real tactical interest over repeated play, regardless of the memorization-risk math we ran?
3. We leaned hard on "mob variety creates the puzzle, not card complexity." Is that actually sufficient, or does real depth require something we haven't built yet?
4. Any blind spot in how we've been testing that would let a genuinely bad puzzle (solved once, boring forever, or effectively random-feeling despite being deterministic) slip through undetected the way the Cleric equilibrium bug did?
5. Bottom line: if you were a player who'd just solved a handful of these pulls, would you want to keep pulling, or would it start to feel like a solved chore?
