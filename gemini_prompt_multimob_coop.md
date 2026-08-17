Following up on your "Kill Pool & The Aggro Draw" proposal. Quick context if this is a fresh
conversation: QUEST is a board game (prequel to a project called AGGRO) prototyping a small
combat model — 6-card unique deck, 4-card hand, exactly 3 rounds per pull, exact-enumeration
solver, no RNG except which hand you draw. Solo combat is one hero vs. one mob. We'd already
locked and built a co-op extension (2-4 heroes) where the party's combined damage and Block
pool against a single shared mob HP total, with a per-card "Aggro" number (0-4, flat, printed)
deciding who eats any leftover damage the pooled Block didn't absorb. You flagged the real UX
problem with extending that to *multiple simultaneous mobs*: our only tested approach summed
every mob's stats into one flattened "Super Mob" pattern before play even started, which is
real arithmetic homework at the table and also can't represent mixed mob types (a melee mob
and a ranged mob merged together stop being individually meaningful).

Your proposed fix — keep mobs as separate tracked entities, pool only damage into an
assignable "Kill Pool," and resolve the Enemy Phase by ranking players by loudness and mobs by
HP, pairing them off (loudest takes the highest-HP survivor's attack, etc.) — was the right
core insight and we kept it. But working through it in detail surfaced real gaps and one
genuine complexity regression, and we want your read on where we landed.

## What we changed from your original pitch, and why

**1. No pooling, no splitting, anywhere — replaced with atomic per-hero assignment.**
Your Kill Pool summed all heroes' damage into one number, then (implicitly) needed to split
that number across mobs to reflect "we focus-fired the weak one and chipped the tough one."
We checked whether pooling-then-splitting actually bought any outcome atomic assignment
couldn't reach, and it doesn't: if each hero's own card damage is independently pointed at
whichever mob the party chooses (no addition step, no shared number ever written down),
every outcome the pool could reach is still reachable — heroes who happen to target the same
mob still add up naturally — and outcomes requiring genuine splitting were never actually
needed. Same finding on the defense side, except sharper: personal, unsplit block is *more*
expressive than a pooled Block would be, since two heroes can each protect a different
attack simultaneously, which one pooled-then-split-to-one-target block value structurally
can't do. So the fix wasn't "add a Block Pool to mirror the Kill Pool" (we tried that
framing first) — it was to drop pooling as a concept entirely on both sides.

**2. Ranking mobs by this round's printed ATK, not remaining HP.**
Your version ranked survivors by remaining HP. We're leaning toward this round's ATK instead
— it's the value that actually determines the hit, both values are fully revealed to players
already (no hidden-information cost either way), and HP-ranking can let a mob having a quiet
round outrank one about to spike. Genuinely a judgment call, not an obvious correction — want
your take on which reads better in practice.

**3. Your model never defined mobs ≠ heroes; we do, via wraparound.**
Real gap in the original pitch: the loudest/highest-HP 1:1 pairing only works cleanly when
mob count equals party count. We generalized to round-robin: rank surviving mobs by ATK
(highest first) and heroes by Aggro (loudest first) each round, then assign mob 1 to hero 1,
mob 2 to hero 2, ... wrapping back to hero 1 if mobs outnumber heroes. This makes "loudest"
mean something concrete when outnumbered — you draw the most simultaneous attention, not just
the single worst hit. We explicitly chose *not* to cap mob count at party size (the simpler
fix that would remove wraparound entirely) because losing "more mobs than heroes actually
increases threat" undercuts the entire point of a multi-mob node existing.

**4. Self-block on multiple assigned attacks resolves to a flat, no-choice rule, and we can
prove it's never wrong.**
Wraparound means a hero can face two attacks in one round. We first assumed this created a
real decision (which of my two attacks does my own block protect?), then proved it doesn't:
since mobs are globally ATK-sorted before round-robin distribution, a hero's first-assigned
attack is always >= their wrapped second attack. For any single block value k against ordered
attacks a >= b, applying k to a is provably never worse than applying it to b (equal when
k<=b, strictly better than applying to b when k>b) — a short case check across the three
ranges of k confirms it. So "always apply your block to your first-assigned attack" is safe
to print as a flat, zero-decision rule, not a "usually correct" default.

**5. `grants_range` interaction, stated explicitly:** an evading hero stays in the round-robin
assignment (doesn't drop out, doesn't shift anyone else's pairing) — whichever of their
assigned attacks come from a melee-type mob is simply zeroed, first-assigned or wrapped-second
alike. Ranged mobs are unaffected, same as it's always been solo.

## Where we landed, in full

**Hero Phase (resolves first, in order):**
1. Every present, living hero reveals their card for the round.
2. Each hero's own damage value is independently assigned by the party to exactly one
   surviving mob (no splitting one hero's number across two mobs, no adding two heroes'
   numbers into a shared figure first — though if two heroes independently choose the same
   mob, their damage naturally adds up against that mob's HP).
3. Any mob whose remaining HP reaches <=0 dies immediately and takes no further part in the
   round, including the Enemy Phase below.

**Enemy Phase:**
4. Rank living heroes by this round's Aggro (loudest first; tie broken by highest raw damage
   among the tied cards; still-tied is left to table agreement, no third automatic number —
   already-established behavior, unchanged).
5. Rank surviving mobs by this round's printed ATK (highest first) — tiebreak here not yet
   decided, flagged below.
6. Round-robin assign: highest-ATK mob to loudest hero, next to next-loudest, ... wrapping
   back to the loudest hero if mobs outnumber heroes.
7. `grants_range`: any attack in a hero's assignment from a melee-type mob is zeroed
   entirely. Ranged mobs unaffected.
8. Each hero's own block (from their own played card, never an ally's) auto-applies to the
   first (largest) of their assigned attacks, per the proof above — no player choice needed.
9. Unblocked damage from each of a hero's assigned attacks comes only out of that hero's own
   HP — no spillover to teammates. If they can't absorb it, they die.
10. A dead hero contributes no further damage/block and drops out of Aggro ranking and
    round-robin assignment for all remaining rounds. Survivors keep fighting. Win = every mob
    dead before every hero is; loss = every hero dead first; flee/timeout = 3 rounds pass with
    both sides still standing.

**Killing-blow riders (Warrior's Execute, Rogue's Cutthroat) — a real scoping question we
had to resolve given separate mobs, flagging since it's an actual change from the original
single-shared-mob wording:** in the old single-mob model, any killing-blow card played by
anyone, if the party's pooled damage killed the mob that round, spared the *whole party* from
that mob's one attack (there was only ever one). With mobs separate, we think this has to
become per-mob: a killing-blow card only prevents an attack from the *specific mob its own
damage was pointed at*, if that mob dies this round. It says nothing about any other mob. This
follows logically from mobs no longer being one shared entity, but we want it stated plainly
rather than silently inherited, since it's a real behavior change from what was previously
locked.

## Worked example

2 heroes: Thorn (Warrior, plays a card: Aggro 3, dmg 4, block 2) and Faye (Cleric, plays a
card: Aggro 1, dmg 2, heal 2, block 0). 3 mobs alive at the start of the round: Mob A (ATK 4,
HP 6), Mob B (ATK 3, HP 8), Mob C (ATK 5, HP 3).

Hero Phase: party points Thorn's 4 damage at Mob C (HP 3) — Mob C dies, 1 overkill wasted.
Faye's 2 damage goes to Mob A (HP 6 -> 4).

Enemy Phase: survivors are Mob A (ATK 4) and Mob B (ATK 3) — Mob C is gone, takes no action.
Heroes ranked: Thorn (Aggro 3) > Faye (Aggro 1). Mobs ranked: A (ATK 4) > B (ATK 3).
Round-robin: A -> Thorn, B -> Faye. Both mobs are melee and neither hero played a
`grants_range` card, so both attacks apply in full. Thorn's own block (2) auto-applies to his
one assigned attack: takes 4-2=2. Faye has no block, takes the full 3.

## One more scoping change since drafting the above

Originally we treated the pooled single-shared-mob engine (damage+Block pooled, one Aggro-
decided hero takes the leftover) as the default for any single-mob node, and figured this new
round-robin engine only kicks in once a node deals 2+ mobs. On reflection that pooled
treatment -- the whole party defending as one unit against one shared threat -- is really a
**Boss-tier** mechanic (no Boss tier is designed yet), not a general "single mob" rule. Elite
(the tougher single mob that's actually built and available in every mode today) now also
runs through this new round-robin engine, just degenerating to the trivial case where there's
only one target: the loudest hero is the only one ever assigned the attack, and everyone
else's own block goes unused that round, since nothing pools to bail them out outside an
actual Boss fight. And whichever mechanic applies is fixed by how the encounter *starts* --
a multi-mob fight that whittles down to one surviving mob mid-fight keeps resolving through
this engine for its remaining rounds; it doesn't switch over to the pooled one just because
the count happens to hit one. So this write-up is no longer a narrow multi-mob-only proposal,
it's the primary co-op resolution engine, with the old pooled model held in reserve
specifically for a future Boss.

## What we want your read on

1. **Is this still simple enough at the table, or did fixing the gaps in your original pitch
   overcorrect into something heavier than the problem justified?** We think we landed on
   something with zero arithmetic-splitting and zero cross-hero coordination for block, with
   exactly one real player decision per hero per round (where does my damage go) — but we've
   been close to this for a while and want an outside read on whether it still *feels* like
   the streamlined fix you were originally going for.
2. **HP-ranking vs. ATK-ranking for the mob side of the Enemy Phase pairing** — genuine
   open call, see point 2 above.
3. **Tiebreak when two surviving mobs have identical this-round ATK** — not yet decided.
   Our hero-side tiebreak (highest raw damage among tied cards) doesn't have an obvious mob-side
   equivalent; open to a suggestion here rather than us just picking something arbitrary.
4. Anything structurally missing that a fresh read would catch that we'd miss after having
   iterated on this for so long.
