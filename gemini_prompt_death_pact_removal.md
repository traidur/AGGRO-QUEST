Follow-up to an earlier prompt in this same project (QUEST, a board game — a prequel/
companion to another project called AGGRO). Context if this is a new conversation: QUEST is
built around a small, fully-enumerable combat model — 9 classes, each a unique fixed 6-card
deck, draw 4 of 6, play 3 of those 4 across exactly 3 rounds, one card deliberately unplayed.
The mob's full 3-round attack/block pattern is known and visible before sequencing — no
hidden information, no dice anywhere except which 4-of-6 hand gets drawn. The whole project's
balance methodology depends on this: every class is solved exhaustively by computer (every
possible hand against every mob, exact enumeration, no trials/sampling) and that solver's
output is the primary design tool, not a secondary check on playtesting.

Last time, a question came up about whether this format's full solvability was dangerous to
tabletop fun, whether a dedicated player memorizing "the correct play" would collapse the
game into rote execution. The conclusion reached (and independently checked with you) was no
— full-information solvability of a small tactical subcomponent isn't inherently a fun
problem (precedent: blackjack basic strategy, poker equity calculators, chess opening theory,
all solved/documented without being considered broken), and a player who brings a calculator
has opted out of the intended experience voluntarily. That conversation specifically named
one card as a good example of a *different* kind of design tool worth keeping on its own
merits, separate from the solvability question: Necromancer's Death Pact, the one card in the
entire 9-class roster with genuine in-pull randomness. Its mechanic: before playing any card
in a pull, you may lose HP to draw one of the two cards not currently in your hand into your
hand, on the condition a specific card gets played somewhere that pull. Every other card in
every other class resolves under full information — Death Pact was the single exception, a
real gamble with a real coin-flip outcome, thematically framed as a literal pact (spend life,
risk drawing power you can't predict).

Death Pact was fully built and validated by the time that conversation happened — designed
card-by-card by the project's lead designer (not AI-drafted), went through two real,
measured corrective passes (an early version of the mechanic's shape provably could never
rescue a losing hand; an early version of the AI's gamble-taking policy gambled irrationally
65% of the time at near-fatal HP for under a 1% payoff), and its final numbers matched the
rest of the roster cleanly on every metric the project tracks. Supporting it required real,
one-off engineering: since every other tool in the codebase (the exhaustive solver, damage-
floor sweeps, defense-floor sweeps, the whole multi-pull chained simulation) assumes full-
information deterministic play, Death Pact needed its own separate architecture — the exact
solver was built to correctly ignore the draw entirely (a coin-flip outcome can't be part of
a "certain" line), a separate function carried genuine randomness only inside the multi-pull
Monte Carlo layer, and a third function existed solely to show the real, draw-adjusted win
rate, since the solver's own number alone made the class look like a worse outlier than it
actually was in practice.

**What happened next, this session:** the designer decided to rework Death Pact into
something fully deterministic, keeping the same card name — not because anything about it
tested badly (no playtesting of this game has happened yet at all; every validation so far is
simulator-only) and not because the numbers were wrong. The stated reasons, given directly:
**"knowledge debt"** — Death Pact was the one card, out of an otherwise fully-consistent
9-class, 54-card roster, that worked on a fundamentally different *kind* of rule than every
other card in the game (every other card resolves under full information; this one had a
genuinely unknown outcome) — and **"simulation debt"** — it was the one class requiring its
own separate solver path, tooling, and doc caveats, in a project whose entire design
methodology is "the simulator solves everything exhaustively," making the one class that
broke that assumption a recurring, permanent maintenance cost rather than a one-time one.

The reworked version: the same card may now lose a flat 4 HP to deal 3 extra damage, fully
known on both sides of the trade, resolved the instant the card is played. It required zero
special-casing anywhere — implemented as a second, deterministic version of the same card
(the exact pattern another class's stance-choice mechanic already used), automatically
considered by the existing generic solver like any other choice. Its numbers were derived
directly (parameter sweeps, not guesses) to reproduce the exact same validated win rate the
original draft's draw-adjusted rate had already hit, and were checked specifically for a
subtler risk — whether the extra damage could let a fight end a round early in a way that
quietly outperforms the numbers on record — confirmed it can't, in every case checked. The
class's tuned numbers didn't change in any way that matters.

**One claim in an earlier draft of this same writeup turned out to be wrong, and the
correction matters for the actual question here.** The first framing was "the class lost its
one distinctive mechanic" — checked against the other 8 classes' actual mechanics and that
turned out false: no other class has an optional, resolved-in-the-moment, pay-a-resource-for-
an-effect trade with no setup or counter required, so the reworked card is still mechanically
unique in the roster, just along a different axis than before. What was actually lost is
narrower and more specific: the reworked version is deterministic, meaning **the roster now
has zero cards anywhere with a genuinely unknown-until-resolved outcome.** Death Pact's
original draft was the only place in the entire game where a player couldn't compute the
exact result of a choice in advance — every other card, in every class, resolves under full
information. That property is what's actually gone, not "distinctiveness" in general.

**The question:** given that reframe — is trading away the *only source of genuine hidden-
information/randomness in an otherwise fully-solved, exhaustively-enumerable game* a sound
call to make before a single real playtest session has happened, in exchange for consistency
of solver architecture and player-facing rule uniformity? Or is "this is more work for my
simulator and it's the odd one out" a risky reason to cut the one place unpredictability
could live, absent any actual evidence (from play, not from tooling) that it was a problem?
Genuinely curious whether you'd weigh consistency-of-methodology that heavily pre-playtest,
or whether you'd have pushed to keep that one outlier — specifically for what it contributed
structurally, not just as "a cool card" — until actual sessions said otherwise.
