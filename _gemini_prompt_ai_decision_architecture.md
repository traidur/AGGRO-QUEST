# Second opinion wanted: AI decision-making architecture in a board game simulator

## Context

QUEST is a solo tabletop RPG board game (Python simulator used as the design tool). A
simulated "hero" plays itself through the game each turn: fight mobs, restock supplies, spend
Gold at a Class Trainer, travel between map Zones. The simulator's job is to model what a
*rational, but not omniscient* player would actually do, so we can measure pacing/economy
numbers against real gameplay, not hand-picked assumptions.

## The current state

The hero's spending/decision logic lives in one big per-turn loop (`_trip_chain` in
`macro_sim.py`). Right now it looks like this, roughly:

```python
mandatory_granted = False   # has the free "you just leveled up" card upgrade been picked up?
bag_upgraded = False        # has the one-time Bag capacity upgrade been bought?
started_level2_quests = False   # has the hero picked up their first Level-2-tier quest batch?
owned_upgrades = set()      # which optional paid upgrades (of a fixed list) have been bought

while True:  # one iteration per game turn
    # ... restock food/potions ...

    # 1. Quest pickup (only if the hero has zero active quests AND is standing in the
    #    right map Zone for their level)
    if not active_quests and current_position in valid_quest_zones:
        active_quests = draw_new_quest_batch()
        if <this batch was Level-2-tier>:
            started_level2_quests = True

    # 2. Bag Upgrade: buy ASAP once Level 2 quests have started, if affordable
    if started_level2_quests and not bag_upgraded and gold >= BAG_UPGRADE_COST:
        gold -= BAG_UPGRADE_COST
        bag_upgraded = True
        <grow bag by 1 slot>

    # 3. Class Trainer: receive the free mandatory upgrade (if not yet received),
    #    then buy the next paid upgrade in a FIXED priority list, if affordable
    if <standing at a Trainer location> and <hero is Level 2+>:
        if not mandatory_granted:
            mandatory_granted = True
        next_upgrade = <first item in a fixed ordered list not yet in owned_upgrades>
        if next_upgrade is not None and gold >= SKILL_COST:
            gold -= SKILL_COST
            owned_upgrades.add(next_upgrade)

    # ... then the hero decides where to travel / what to fight this turn ...
```

**The real problem:** the *order* these three things get decided in (quest pickup → Bag
Upgrade → Trainer/mandatory/skills) is entirely implicit — it's just whichever if-block happens
to be written first in the function body. There's no data structure anywhere that says "this is
the priority order"; you have to read the code layout to know it. This has already caused one
real bug this session (a piece of state needed to be computed earlier in the function than it
originally was, purely because a later block depended on it, and the fix required manually
re-ordering code blocks rather than changing a value).

It also doesn't scale: every new "thing the hero might spend Gold or make a milestone decision
about" requires (a) a new boolean flag, and (b) a new manually-placed if-block whose position in
the function determines its priority relative to everything else. The game currently only has 2
character levels built out of an eventual 6 — this pattern would mean copy-pasting this entire
block, renamed, for each new level.

## What's already been decided as the philosophy for *one* piece of this

For the "which paid upgrade to buy next" question specifically, the project already deliberately
chose a **fixed, explicit priority list** (`LEVEL2_PURCHASED_ORDER`, just an ordered Python list)
over any kind of scoring/utility system — reasoning being that a fixed list is simple, testable,
and *tabletop-legible*: a human reading the design could reconstruct the AI's exact behavior
from the list alone, whereas a scoring system with weights would be much harder to justify or
explain to a human player trying to understand why the AI does what it does. This project has a
hard constraint that **every mechanic must be tabletop-executable** — a flat printed rule a
human could follow at a table, never a hidden algorithm.

## The question

Given that existing, deliberately-chosen constraint (explicit fixed-order lists over hidden
scoring systems, tabletop-legible always), what's a better way to structure this than "a pile of
independent booleans + implicit ordering via code layout"? Two directions under consideration,
neither implemented yet:

1. **Unify the one-off booleans into a set** (mirroring `owned_upgrades`, which is already a set
   of acquired-upgrade IDs, not one bool per upgrade) — e.g. `acquired = {"mandatory",
   "bag_upgrade", "started_l2_quests"}`, checked with `in` instead of dedicated variables.

2. **Generalize the fixed-priority-list pattern to cover *all* spending decisions per level**, not
   just paid skills — one ordered list per level containing the free mandatory upgrade, the Bag
   Upgrade, and each paid skill in explicit priority order, walked top-to-bottom each turn: do/buy
   whichever's next in line and currently possible, matching the same "explicit list a human
   could read and predict" philosophy already locked in for skill purchases specifically.

Is this the right direction? Specifically:
- Are there real failure modes or edge cases this two-part approach would handle badly that a
  different pattern (e.g., a small state machine per level, or something else entirely) would
  handle better — while *still* respecting the "must be an explicit, human-reconstructable rule,
  never a hidden weighting" constraint?
- Is unifying disparate one-time-milestone booleans into a single set actually a readability win,
  or does splitting "quest-pickup state" from "spending state" from "upgrade-ownership state"
  into separate named collections (three sets instead of one) better preserve clarity, even
  though it's less unified?
- Any other architectural pattern worth considering for "sequenced, priority-ordered AI
  decisions in a simulator, where the decision logic itself must double as printable game rules"
  that isn't utility-scoring, isn't a state machine, and isn't just an ordered list?

Please give a genuine second opinion, not just validation of the two options above — push back
if there's a better answer neither of us considered.
