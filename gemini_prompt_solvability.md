Fresh question, different topic from the multi-mob co-op thread. Context if this is a new
conversation: QUEST is a board game (prequel to a project called AGGRO) built around a small,
fully-enumerable combat model — 9 classes, each with a unique fixed 6-card deck. Each combat
encounter ("a pull"): draw 4 of your 6 cards, choose 3 of those 4 to play in some order across
exactly 3 rounds, one card deliberately goes unplayed. The mob you're facing has a fixed,
fully-known attack/block pattern for all 3 rounds, printed and visible before you sequence your
hand — no hidden information, no dice anywhere except which 4-of-6 hand you happen to draw.
This is deliberate: the format is small enough that every hand-vs-mob matchup can be exactly,
exhaustively solved by a computer, and the whole project uses that solver as its primary
balance-testing tool (run every possible hand against every mob, confirm win rates/damage
floors/etc. land where intended) instead of relying on playtesting intuition.

Two questions came up in a row, and I want your independent take on both, not just a sanity
check of where we landed.

**Question 1: is this specific combination of mechanics something that already exists, and if
so, what's the closest real precedent?** The AI I was working with landed on: individual pieces
have real precedent (Gloomhaven's small fixed per-class ability-card kits with hand-select-
then-commit; Slay the Spire's per-class synergy-identity design and its "show the enemy's next
move" Intent mechanic), but the specific combination — especially revealing the mob's *entire*
3-round pattern up front rather than one round at a time, and being small enough for full
exhaustive brute-force solving used as the actual design/balance methodology — wasn't something
either of us could point to an exact match for. Curious whether that reads right to you, or if
there's a closer analog (tabletop, video game, or otherwise) neither of us thought of.

**Question 2, the one I actually want pushback on:** the AI I was working with then raised a
concern — since every hand-vs-mob pairing has a single objectively "correct" solved answer, and
the space is small (15 possible hands per class × 6 currently-live mobs = 90 hand/mob pairs per
class), a dedicated player or community could work out or memorize the correct play for common
situations, and once known, the in-the-moment tactical decision of a pull risks collapsing into
"did I memorize this" rather than a fresh decision. It went further into "how big would the
combinatorial space need to be before you'd call it unsolvable," concluded that scaling mob/
card-upgrade count doesn't actually fix this (any space small enough for the design team to
brute-force for balance testing is, by construction, small enough for a player to brute-force
live with a phone app — the real threat isn't memorization, it's the same live computation the
project's own tooling depends on), and started reasoning toward needing more mechanics with
genuine unresolvable-in-advance randomness (the one card in the whole 9-class roster that
already has this, Necromancer's "Death Pact" — spend HP to draw one of your two undrawn deck
cards, genuinely random which one — was framed as a model to replicate more of).

I pushed back: is full-information solvability of a small tactical subcomponent actually a real
danger to a tabletop game being fun, or is that importing a "solved game = bad" heuristic from a
context where it doesn't actually apply? My reasoning: blackjack has a complete, freely
published "basic strategy" chart and remains massively popular with players who never look at
it; poker hand equity against a fixed board is exactly computable and serious players use
equity calculators to study between sessions without it hurting the live game; chess opening
theory is documented dozens of moves deep and casual players never touch it and still love the
game. A player who brings a calculator to compute optimal play every round has opted out of the
intended experience voluntarily — that's not something I think a designer needs to defend
against. The AI conceded the point, reframed it as a playtesting question ("does resolving a
pull by feel, without a tool, feel satisfying to a normal player") rather than a combinatorics
or forced-randomness question, and walked back the idea that the game needs more Death-Pact-
style unresolvable mechanics to be safe.

Where do you actually land on this? Specifically: (a) do you think the solvability concern was
legitimate and the walk-back was premature, (b) do you think the walk-back was right and the
original concern was overthinking a non-issue, or (c) something else entirely — e.g. a
distinction between "solvable in principle" and "small enough to solve casually" that neither
of us drew cleanly. Also curious whether you'd treat "does it still feel fun without a tool" as
genuinely answerable only through playtesting, or whether there's a way to reason about it more
rigorously ahead of actually building and running sessions.
