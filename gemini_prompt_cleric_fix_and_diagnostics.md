Following up on the earlier "condensed combat" puzzle-quality review. Quick context if this is a fresh conversation: QUEST is a board game (prequel to a project called AGGRO) where I'm prototyping a much smaller combat model — 6-card unique deck, 4-card hand, exactly 3 rounds per pull, no dice anywhere except which hand you draw, an exact-enumeration solver instead of Monte Carlo. Three classes exist so far: Warrior (Stance + Sunder), Wizard (Positioning + Spellweave), Cleric (Heal + Sacred Balance). You previously critiqued puzzle quality across all three and flagged that the three signature mechanics risked feeling like "three skins on setup/payoff."

## What we actually did to "fix" the Cleric

This went through several real, sequential problems, not one clean pass:

**1. Identity had eroded into pure numbers-optimization.** Cards like Smite and Call of the Void had drifted into being distinguished only by an arbitrary heal-amount axis that was invented to avoid a damage-floor bug, not because it meant anything thematically. We did a full research sweep of the source game's actual Cleric (originally "Priest") design — every version of its docs, cut cards, and design-rationale notes — and found:
- The real "Sacred Balance" passive (originally "Atonement") is dead simple: playing a damage-dealing spell heals a small flat amount, automatically, no setup or resource-tracking at all. We had invented an entire arm/consume combo system and just put that name on it.
- "Void" isn't generic flavor — it's specifically the class's Shadow-magic half (opposite "Sacred/Blessed" Holy magic), a direct remap of WoW's Shadow Priest spells. Void Mark = Shadow Word: Pain, and its real defining trait is that it's the *one* card that deliberately does NOT trigger the passive — we had it backwards, using it as a passive-arming card.
- Call of the Void's real tradeoff was a higher Energy cost, which doesn't exist in this condensed system at all — explaining why we'd been inventing awkward substitute tradeoffs.

**2. Restoring the real mechanic reopened an old bug.** Simplifying Sacred Balance back to "automatic small heal on certain damage cards" and dropping the arm/consume system meant Heal and Blessed Barrier lost the conditional bonus damage that had been the fix for an earlier problem: only 3 of 6 cards could deal any damage at all, giving a worst-case hand a damage floor of just 2 (compared to ~7-8 for the other two classes). We separated this into two independent fixes instead of one entangled mechanism: kept Sacred Balance clean and automatic (identity), and gave two support cards a small flat, unconditional damage rider, completely decoupled from Sacred Balance (floor).

**3. The flat damage riders reopened a "cannot die" equilibrium bug** (found earlier in this same class, now recurring for a different reason): checking net HP change across a range of starting HP values, not just the total, revealed Cleric had enough healing throughput to trend positive at low HP against some mobs — not a slow decline toward death, a structural inability to die. Diagnosed the root cause precisely: one specific mob (nicknamed "Grunt") had a total 3-round attack of only 7, exactly tied with Cleric's own healing ceiling of 7 — any mob whose total damage doesn't clearly exceed the healer's best-case healing total is mathematically guaranteed to be survivable forever by a good hand. Fixed by giving that one mob a modest attack increase (verified zero effect on the other two classes' win rates) rather than repeatedly nerfing Cleric's cards — reasoning that this is a one-time roster-level fix that benefits every future healing class instead of a recurring tax on each one.

**4. A raw-damage pass to fix a separate problem (Cleric losing badly on high-HP mobs, timeouts not deaths) silently reintroduced strict domination** between Smite and Call of the Void — bumping both cards' damage without re-checking whether they were still meaningfully different broke the earlier fix. Caught this via a standardized check (below), not by inspection.

**5. Before accepting "no domination" as the goal, we tested whether it even mattered.** Pushback worth including: is strict domination actually bad if the two cards aren't always drawn together, and could a future, not-yet-built mob shape make the "dominated" card's marginal properties matter in ways a static stat comparison can't see (e.g., 1 extra point of damage being the difference between finishing a fight before or after an escalating final round)? We tested this empirically rather than debating it abstractly: forced substitution of one card for the other across every hand/mob combination and checked whether outcomes were genuinely different or just tied. Result: in the *old*, truly-dominated version, every apparent instance of the "weaker" card being used was 100% tie-break noise (identical outcome either way) — confirming domination was real. In the *current*, differentiated version, 75% of the same comparison cases showed a genuine, non-tied difference (the "weaker" card actually preserving more HP in real scenarios) — confirming the fix produced real value, not just theoretical distinctness.

## Cleric's current, final card list

| Card | Effect |
|---|---|
| Void Mark | 3 DMG. Does not trigger Sacred Balance (deliberately, matching its source identity). |
| Smite | 5 DMG. Triggers Sacred Balance — playing it also heals 1 HP automatically. |
| Call of the Void | 6 DMG. Does NOT trigger Sacred Balance (this is the "premium cost" tradeoff, replacing the lost Energy-cost mechanic — bigger hit, no passive sustain). |
| Cleansing Barrier | 4 Block, 2 DMG flat (unconditional, no Sacred Balance interaction — this is the damage-floor fix, kept fully separate from the passive). |
| Fiery Fortitude | +2 Max HP, 2 heal, 2 DMG flat (same floor-fix role as above). |
| Heal | 4 heal flat. No Sacred Balance interaction. |

Cleric HP: 12. Sacred Balance's automatic heal amount: 1. Every card in the deck is unique (no duplicates) — this matters mechanically, see below.

## Our standardized diagnostic suite (just built, want your read on it)

Every one of these is black-box — implemented once as shared functions that only call each class's public solver interface (never inspect internal card-data structures directly), so the exact same code runs for all three classes without special-casing:

1. **Damage floor/ceiling** — for every possible hand, find the max 3-round damage output (via bisecting a zero-attack dummy mob's HP and checking win/lose, not by summing card fields directly). Report the best hand's max and the worst hand's max.
2. **Healing floor/ceiling** — same idea, but start the hero near-empty against an unkillable zero-attack dummy (forces all 3 rounds to play out, healing accumulates, win condition never fires) and read off net HP gained.
3. **Equilibrium check** — across every mob in the roster, verify net HP change stays negative at multiple starting-HP levels (full, 2/3, 1/3, critically low). Catches the specific "cannot die" bug class described above — a high average survival number alone can't distinguish a genuine slow decline from a stable equilibrium, only checking the sign at multiple starting points can.
4. **Unplayed Card diagnostic** (this is what we've been calling your "agony of the unplayed card" point, standardized) — across every hand × mob combination, tally which of the 4 drawn cards gets left out of the optimal 3-card line. A healthy kit shows real, sometimes-strong cards getting cut sometimes, not the same weakest card every time.
5. **Pairwise hidden-domination check** — generalizes the Smite/Call-of-the-Void incident to scan *every* card pair in a deck automatically. For hands containing both cards of a pair, where the optimal line uses one but not the other, force-substitutes and checks whether the outcome is genuinely different or just tied. A pair that's 100% tied whenever both are drawn is flagged as dead weight — this is exactly the check that would have caught the Smite/Call-of-the-Void regression the moment it happened, instead of us finding it by accident days later.

All five ran clean on the current build: Warrior 8/14 damage floor/ceiling, Wizard 8/16, Cleric 7/14 with a 1/7 healing floor/ceiling; equilibrium clean on all three; zero hidden-domination pairs found anywhere.

**The actual question:** given everything above — the specific bug classes we've hit (identity erosion, floor collapse, equilibrium exploits, hidden domination, and the "does domination even matter without real testing" nuance — is there a category of problem this five-check suite still can't see? What would you add?
