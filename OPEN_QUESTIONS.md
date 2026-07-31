# QUEST — Open Questions

Design tensions and undefined interactions flagged before prototyping starts. Move an item to `DESIGN_DOC.md` once it's actually settled — don't mark it resolved just because it's discussed.

## Unresolved

### 1. The Claim phase's failure mode
One claim per node per round, priority passed clockwise via the First Player Token — good for drafting tension, but what happens to a player who's consistently last in turn order at a hot node? Does priority rotate (AGGRO uses threat-based targeting order for something structurally similar), or is turn order fixed, meaning the same player can get shut out repeatedly?

### 2. Rest vs. the Claim structure
Clearing Winded requires Resting (forfeiting a pull) + consuming Food/Water. Undefined: does Resting happen *instead of* claiming a target in Phase 2, or is it a separate action outside the 4-phase loop? If it competes with claiming, a low-priority player could get starved out of both combat and recovery in the same round.

### 3. Solved-hand risk in OTK combat
Static mob stat blocks + deterministic math means once a player finds the optimal 3-Energy line for a given HP/ATK threshold, the fight stops being a decision. AGGRO avoids this with multi-phase enemy AI and shifting threat; QUEST's only source of variance is which 5 cards you drew. Decide early whether that's sufficient, or whether mob stat blocks need structural variation (affixes, escalating tiers within a zone) to keep the math puzzle fresh over repeated pulls.

## Resolved

*(none yet)*
