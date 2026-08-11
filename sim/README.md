# QUEST Balance Sim

Monte Carlo tool for calibrating mob HP/ATK against hero decks. Card data is translated from AGGRO — see `../CLASSES.md` for the translation and every deliberate change from the source cards.

## Run it

```bash
cd sim
python simulate.py --class wizard --mob tier1_grunt --trials 5000
python simulate.py --class warrior --sweep --trials 2000
```

`--sweep` runs the chosen class against every mob in `data/mobs.csv` and prints win/loss/timeout rates, average rounds to clear, and average hero HP remaining on a win.

## What's modeled

- A full pull, round by round: mob HP whittles on a failed OTK (not a reset), matching the decided rule in `DESIGN_DOC.md` §2.
- Engagement/Cast Penalty: a melee mob Engages after round one if the OTK failed; Cast-type cards cost +1 Energy from then on. Ranged mobs never Engage.
- DOT cards resolve *after* the mob's strike in the same round (a mob at low HP still gets to act before dying to a DOT tick), matching AGGRO's Mob Afflictions step ordering.
- Execute's real condition (mob HP ≤ 50% of max) is checked live each round, not pre-baked into an average.
- Class passives: Warrior Stance (re-chosen each round, solver tries both and keeps the better one), Cleric Sacred Balance (free self-heal on Cast-type damage cards), Wizard Spellweaving (Instant-before-Cast Energy discount, assumed optimally sequenced).
- Deck shuffle/discard/reshuffle exactly as AGGRO does it: discard the whole hand at round end, reshuffle discard into the draw pile when it runs dry mid-draw.

## What's NOT modeled yet (by scope, not oversight)

- **Cross-pull deck pollution.** Winded/Durability cards accumulating over a multi-pull trip — this is the mechanism `OPEN_QUESTIONS.md` (resolved item on solved-hand risk) leans on, and it isn't built yet. Next real step once single-pull numbers look sane.
- **Bag Tetris, Town, Market, Decaying Bounties** — none of the macro-loop systems. This tool only answers "can this deck clear this mob," not the logistics layer around it.
- **Co-op / Party Pulls.** Single hero only. Cleric's Sacred Balance and Blessed Barrier are modeled self-only per `CLASSES.md`.
- **Card-granted draw effects** (Shoot Wand, Void's Veil) are tracked in the output but don't let you play the newly drawn card the same round.
- Rogue, Paladin, Ranger, Necromancer, Druid, Runecaster aren't translated yet — only Warrior, Cleric, Wizard have card data in `data/cards.csv`.

## Mob data

`data/mobs.csv` is a first-guess spread across three tiers, not calibrated numbers — it exists so `--sweep` has something to run against. Finding the actual HP/ATK values that produce a sane win-rate curve per class/tier is the point of running this tool, not an input to it.
