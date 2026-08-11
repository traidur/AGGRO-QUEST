"""Monte Carlo balance sim for QUEST.

Usage:
    python simulate.py --class wizard --mob tier1_grunt --trials 5000
    python simulate.py --class warrior --sweep --trials 2000
    python simulate.py --class wizard --mob tier1_grunt --trials 2000 --rollout

See engine.py for the round-resolution model and its documented
simplifications.
"""

from __future__ import annotations

import argparse
import random
import statistics
from dataclasses import dataclass, field

from engine import CLASS_HP, Card, choose_play, enumerate_hand_plays, load_cards, load_mobs

MAX_ROUNDS = 6
ROLLOUT_TRIALS = 10
ROLLOUT_HORIZON = 3


@dataclass
class PullState:
    hero_hp: float
    max_hero_hp: float
    mob_hp: float
    mob_max_hp: float
    engaged: bool = False
    sunder_tokens: int = 0
    has_charge: bool = False
    pending_hot: float = 0.0
    draw_pile: list = field(default_factory=list)
    discard_pile: list = field(default_factory=list)

    def copy(self) -> "PullState":
        return PullState(
            hero_hp=self.hero_hp,
            max_hero_hp=self.max_hero_hp,
            mob_hp=self.mob_hp,
            mob_max_hp=self.mob_max_hp,
            engaged=self.engaged,
            sunder_tokens=self.sunder_tokens,
            has_charge=self.has_charge,
            pending_hot=self.pending_hot,
            draw_pile=list(self.draw_pile),
            discard_pile=list(self.discard_pile),
        )


@dataclass
class PullResult:
    outcome: str  # "win", "loss", "timeout"
    rounds: int
    hero_hp_remaining: float


def _load_deck(class_name: str, exclude_exhaust: bool) -> list:
    cards = load_cards(class_name)
    if exclude_exhaust:
        # The exhaust resource is already spent for this fight (used
        # earlier in the trip) — the card is still drawn normally and still
        # occupies a hand slot, it just has nothing legal to play. Same
        # treatment as a non-combat Power card, not removed from the deck.
        cards = [
            c if not any(m.is_exhaust for m in c.modes) else type(c)(name=c.name, class_name=c.class_name, modes=())
            for c in cards
        ]
    return cards


def _draw(state: PullState, rng: random.Random, n: int = 5) -> list:
    hand = []
    for _ in range(n):
        if not state.draw_pile:
            if not state.discard_pile:
                break
            state.draw_pile = list(state.discard_pile)
            state.discard_pile = []
            rng.shuffle(state.draw_pile)
        hand.append(state.draw_pile.pop())
    return hand


def begin_round(state: PullState, class_name: str, rng: random.Random) -> tuple[list, list[dict]]:
    """Applies start-of-round HOT, draws a hand, and enumerates legal plays.
    Returns (hand, plays); hand is [] if the deck couldn't produce 5 cards."""
    state.hero_hp = min(state.max_hero_hp, state.hero_hp + state.pending_hot)
    state.pending_hot = 0.0
    hand = _draw(state, rng)
    if not hand:
        return hand, []
    plays = enumerate_hand_plays(hand, class_name, state.engaged, state.mob_hp, state.mob_max_hp, state.sunder_tokens)
    return hand, plays


def resolve_round(state: PullState, mob: dict, hand: list, play: dict) -> str | None:
    """Applies a chosen play to state in place. Returns 'win'/'loss', or
    None if the pull continues."""
    # Held power cards (e.g. Blessed Fortitude) also leave the discard flow
    # here, same as exhausted cards -- the caller tracks them separately and
    # adds a "Held (...)" placeholder in their place. Missing this let the
    # real card fall back into normal discard/reshuffle *in addition to* the
    # placeholder, duplicating it every time it got drawn and played again.
    removed_from_hand = set(play["exhausted_indices"]) | set(play["held_indices"])
    state.discard_pile.extend(c for i, c in enumerate(hand) if i not in removed_from_hand)

    state.hero_hp = min(state.max_hero_hp, state.hero_hp + play["heal"])
    state.sunder_tokens = min(3, state.sunder_tokens + play["sunder_placed"])
    if play["banks_charge"]:
        state.has_charge = True

    if play["dmg"] >= state.mob_hp:
        return "win"

    state.mob_hp -= play["dmg"]

    # Confound is assumed sequenced last (same optimal-ordering convention as
    # Spellweaving and the Vanguard bonuses) — damage dealt earlier in the
    # same round doesn't break it, only damage after Incapacitate would.
    if play["incapacitate"]:
        dmg_taken = 0.0
        mob_engages = False
    elif play["evades_melee"] and mob["mob_type"] == "melee":
        # Stepped back out of range -- no hit, no engagement, same as
        # Incapacitate's full negation. Does nothing against a ranged mob,
        # which can already hit from any distance in the Zone.
        dmg_taken = 0.0
        mob_engages = False
    elif play["untargetable"]:
        dmg_taken = 0.0
        mob_engages = mob["mob_type"] == "melee"
    else:
        dmg_taken = max(0.0, mob["atk"] - play["block"])
        mob_engages = mob["mob_type"] == "melee"

    if dmg_taken > 0 and state.has_charge:
        state.has_charge = False
        state.mob_hp -= 3.0

    state.hero_hp -= dmg_taken
    state.pending_hot = play["hot"]

    # Teleport (disengage) only waived this round's Cast Penalty — no
    # bearing on whether the mob engages going into next round.
    if mob_engages:
        state.engaged = True

    state.mob_hp -= play["dot"]
    if state.mob_hp <= 0:
        return "loss" if state.hero_hp <= 0 else "win"
    if state.hero_hp <= 0:
        return "loss"
    return None


def _greedy_choose(state: PullState, mob: dict, plays: list[dict]) -> dict:
    return choose_play(plays, state.mob_hp, hero_hp=state.hero_hp, mob_atk=mob["atk"], mob_type=mob["mob_type"])


def _partial_value(state: PullState) -> float:
    """End-state evaluator for an unresolved rollout, matching AGGRO's v1
    spec ("hero HP totals... mob HP removed / kills") rather than only
    hero HP — an earlier version scored hero HP alone, which made every
    candidate tie whenever incoming damage was zero (or otherwise didn't
    move), since hero HP was the only thing changing in the comparison.
    Both terms are in [0, 1); strictly below WIN's fixed value and
    strictly above LOSS's, so a guaranteed win/loss always dominates an
    unresolved partial state."""
    hero_frac = max(0.0, min(1.0, state.hero_hp / state.max_hero_hp))
    mob_progress = max(0.0, min(1.0, (state.mob_max_hp - state.mob_hp) / state.mob_max_hp))
    return hero_frac + mob_progress


WIN_SPEED_BONUS = 0.01  # per round saved — see choose_play_rollout for why this exists


def _rollout_continue(state: PullState, class_name: str, mob: dict, rng: random.Random, horizon: int) -> float:
    """Continue a scratch state with the plain greedy policy for up to
    `horizon` more rounds. Returns ~2.0 for a win, -1.0 for a loss (both
    chosen to dominate any partial state), and _partial_value if the
    horizon runs out with the fight still going.

    A flat win score isn't enough: once several candidates all clear the
    win threshold within the horizon, they tie, and the tie breaks on
    arbitrary iteration order rather than which one is actually better —
    this is exactly what let a play that wasted a full round on Heal
    outscore free damage at zero risk, since "wastes a round but still
    wins eventually" and "deals damage and wins eventually" both just
    score "win." A small, strictly-decreasing bonus for winning with more
    of the horizon left breaks that tie correctly — and it's not just a
    technical fix, it's the right thing to reward anyway, since every
    extra round in the real game is a round closer to a real Slog."""
    for step in range(horizon):
        hand, plays = begin_round(state, class_name, rng)
        if not hand or not plays:
            if not hand:
                break
            continue
        play = _greedy_choose(state, mob, plays)
        outcome = resolve_round(state, mob, hand, play)
        if outcome == "win":
            rounds_remaining = horizon - step - 1
            return 2.0 + WIN_SPEED_BONUS * rounds_remaining
        if outcome == "loss":
            return -1.0
    return _partial_value(state)


def choose_play_rollout(
    state: PullState,
    class_name: str,
    mob: dict,
    hand: list,
    plays: list[dict],
    rng: random.Random,
    n_trials: int = ROLLOUT_TRIALS,
    horizon: int = ROLLOUT_HORIZON,
) -> dict:
    """AGGRO's ROLLOUT_PLAN.md approach, scaled down to QUEST's much
    smaller state: don't score a play with a hand-tuned formula, simulate
    what actually happens after it (continuation = the plain greedy
    policy) and let the simulated win rate decide. Outright kills this
    round skip the rollout — no continuation needed to know a kill is
    good. Non-kill candidates are deduped by outcome signature (see
    below) rather than pruned by a scalar score, then each surviving
    candidate gets n_trials scratch continuations."""
    immediate_kill = [p for p in plays if p["dmg"] >= state.mob_hp]
    if immediate_kill:
        return max(immediate_kill, key=lambda p: p["block"])
    dot_kill = [p for p in plays if p["dmg"] + p["dot"] >= state.mob_hp]
    if dot_kill:
        return max(dot_kill, key=lambda p: p["block"])

    # Dedupe by outcome signature instead of truncating by a scalar score —
    # any such score is necessarily blind to some dimension (this one missed
    # Heal entirely, the same failure AGGRO's own rollout notes hit and fixed
    # by loosening pruning rather than trusting a biased pre-filter). Distinct
    # signatures top out around 50-60 even for Warrior's two-stance hands, so
    # deduping needs no truncation at QUEST's scale.
    seen = set()
    candidates = []
    for p in plays:
        sig = (p["dmg"], p["dot"], p["block"], p["heal"], p["hot"], p["cost"])
        if sig not in seen:
            seen.add(sig)
            candidates.append(p)

    # Common random numbers: the same n_trials seeds are reused across every
    # candidate, so trial #k sees an identical sequence of future draws for
    # every candidate being compared. Without this, two candidates that both
    # "probably win eventually" can score within noise of each other purely
    # because they happened to sample different future hands — which is
    # exactly what let a play that wastes a full-HP Heal outscore 5 free
    # damage at zero risk in testing. This isolates the effect of the
    # current round's choice instead of drowning it in unrelated variance.
    trial_seeds = [rng.random() for _ in range(n_trials)]

    best_play, best_score = None, float("-inf")
    for play in candidates:
        total = 0.0
        for seed in trial_seeds:
            trial_rng = random.Random(seed)
            scratch = state.copy()
            outcome = resolve_round(scratch, mob, hand, play)
            if outcome == "win":
                # Wins this round, before the continuation even starts —
                # strictly the fastest possible win, so it gets full credit
                # for "saving" the entire horizon (see _rollout_continue).
                total += 2.0 + WIN_SPEED_BONUS * horizon
            elif outcome == "loss":
                total += -1.0
            else:
                total += _rollout_continue(scratch, class_name, mob, trial_rng, horizon)
        score = total / n_trials
        if score > best_score:
            best_score, best_play = score, play
    return best_play


def run_pull(
    class_name: str,
    mob: dict,
    rng: random.Random,
    hp_override: float | None = None,
    exclude_exhaust: bool = False,
    use_rollout: bool = False,
) -> PullResult:
    max_hero_hp = float(hp_override if hp_override is not None else CLASS_HP[class_name])
    cards = _load_deck(class_name, exclude_exhaust)
    draw_pile = list(cards)
    rng.shuffle(draw_pile)
    state = PullState(
        hero_hp=max_hero_hp,
        max_hero_hp=max_hero_hp,
        mob_hp=mob["hp"],
        mob_max_hp=mob["hp"],
        draw_pile=draw_pile,
    )

    for round_num in range(1, MAX_ROUNDS + 1):
        hand, plays = begin_round(state, class_name, rng)
        if not hand:
            return PullResult("timeout", round_num, state.hero_hp)
        if not plays:
            state.discard_pile.extend(hand)
            continue

        play = (
            choose_play_rollout(state, class_name, mob, hand, plays, rng)
            if use_rollout
            else _greedy_choose(state, mob, plays)
        )
        outcome = resolve_round(state, mob, hand, play)
        if outcome is not None:
            return PullResult(outcome, round_num, state.hero_hp)

    return PullResult("timeout", MAX_ROUNDS, state.hero_hp)


@dataclass
class TripPullLog:
    pull_num: int
    outcome: str
    rounds: int
    hero_hp_before: float
    hero_hp_after: float
    winded_added: int
    oom_added: int
    deck_size_after: int


BANDAGE_HEAL = 6.0
RESTORATIVE_CLEAR = 3  # Food/Water: trash cards cleared per item (legacy Winded/OOM path, inert)


def run_trip(
    class_name: str,
    mob: dict,
    rng: random.Random,
    use_rollout: bool = True,
    max_pulls: int = 100,
    exclude_exhaust: bool = False,
    bandages: int = 0,
    food: int = 0,
    water: int = 0,
) -> list[TripPullLog]:
    """Same mob, fought pull after pull, with HP and an accumulating deck
    (starting cards + trash) carried forward — no recovery between pulls,
    no Bag/Town/Rest, except what Food/Water buy back (see below).

    Two separate axes, two separate mechanisms — no overlap:
    - Winded: melee-only, purely card-triggered (mitigation cards for
      Warrior). No universal baseline; a Warrior who never blocks
      generates none.
    - OOM: caster-only, purely card-triggered (heal cards for Cleric,
      best-hitters for Wizard). Same — no universal baseline.

    (A third axis, Durability — a universal flat-per-pull escalating mob
    ATK bonus — was built, tested, and removed. It was solving the same
    problem that removing Cleric's Sacred Balance passive already solved
    directly, made it redundant, and its only remaining effect was an
    unconfirmed pacing preference. See OPEN_QUESTIONS.md for the full
    writeup before reviving anything like it.)

    Winded/OOM trash from a pull's card plays is generated during the
    pull but only merged into the deck (and reshuffled) once the pull
    ends — a pull's cost never affects itself, only the next one.

    Stops on a loss, a timeout (deck too polluted to function), or
    max_pulls.

    Exhaust model (current): the 8 mitigate/extend-field-time cards
    (Warrior's Shield Block/Vanguard Blade/Vanguard Shield, Cleric's Quick
    Mend/Blessed Recovery/Heal, Wizard's Wall of Ice/Confound) sideline
    themselves when played — the real card leaves the deck and a dummy
    placeholder (0 modes, same as a dead card) fills its spot in the
    discard pile, so deck SIZE stays constant but composition shifts.
    Sidelined cards persist across pulls (trip-level state, not
    per-pull) until refreshed. Refreshing is all-or-nothing: one use of
    the class's resource (Food for Warrior, Water for Cleric/Wizard)
    flips EVERY currently-sidelined card back to its real self at once —
    "clear all" is fine here (unlike the old Winded/OOM trash pile) since
    the sideline is bounded at 2-3 cards, not an unbounded accumulation,
    so there's no hoard-and-dump incentive to worry about.

    food/water: fixed starting counts for the whole trip (no Town, no
    restocking). Food heals BANDAGE_HEAL HP for every class if below max;
    for Warrior specifically it ALSO refreshes sidelined cards (Warrior's
    only resource does double duty, since melee doesn't carry Water).
    Water refreshes Cleric/Wizard's sidelined cards. bandages: legacy
    parameter, kept for backward compatibility, harmless if left at 0.

    Resource spending below uses the smarter (not purely greedy) policy —
    see the comments in the win-branch below for the actual thresholds."""
    max_hero_hp = float(CLASS_HP[class_name])
    hero_hp = max_hero_hp
    pool = _load_deck(class_name, exclude_exhaust=False)
    bandages_left, food_left, water_left = bandages, food, water
    sidelined: list[Card] = []
    held_power_cards: list[Card] = []
    active_max_hp_buff = 0.0
    refresh_resource = "food" if class_name == "warrior" else "water"
    log: list[TripPullLog] = []

    for pull_num in range(1, max_pulls + 1):
        draw_pile = list(pool)
        rng.shuffle(draw_pile)
        state = PullState(
            hero_hp=hero_hp,
            max_hero_hp=max_hero_hp,
            mob_hp=mob["hp"],
            mob_max_hp=mob["hp"],
            draw_pile=draw_pile,
        )
        pull_mob = mob

        # Winded/OOM are purely card-triggered (melee-only / caster-only
        # respectively). Both are currently inert (no card carries these
        # tags anymore, superseded by Exhaust), left in place rather than
        # ripped out.
        winded_added = 0
        oom_added = 0
        newly_sidelined: list[Card] = []
        newly_held: list[Card] = []
        outcome = "timeout"
        rounds_used = 0

        for round_num in range(1, MAX_ROUNDS + 1):
            hand, plays = begin_round(state, class_name, rng)
            if not hand:
                break
            if not plays:
                state.discard_pile.extend(hand)
                continue
            play = (
                choose_play_rollout(state, class_name, pull_mob, hand, plays, rng)
                if use_rollout
                else _greedy_choose(state, pull_mob, plays)
            )
            winded_added += play["winded_generated"]
            oom_added += play["oom_generated"]
            newly_sidelined.extend(hand[i] for i in play["exhausted_indices"])
            newly_held.extend(hand[i] for i in play["held_indices"])
            if play["max_hp_buff_gained"] > 0:
                # Raise the cap BEFORE resolve_round applies this play's own
                # heal, so "raise Max HP then heal to match" actually caps
                # against the new, higher max instead of the old one.
                state.max_hero_hp += play["max_hp_buff_gained"]
                active_max_hp_buff += play["max_hp_buff_gained"]
            o = resolve_round(state, pull_mob, hand, play)
            rounds_used = round_num
            if o is not None:
                outcome = o
                break

        max_hero_hp = state.max_hero_hp  # carry forward if a buff triggered this pull
        hero_hp_after = state.hero_hp
        pool = state.draw_pile + state.discard_pile
        pool += [Card(name="Winded", class_name=class_name, modes=()) for _ in range(winded_added)]
        pool += [Card(name="Out of Mana", class_name=class_name, modes=()) for _ in range(oom_added)]
        for real_card in newly_sidelined:
            pool.append(Card(name=f"Exhausted ({real_card.name})", class_name=class_name, modes=()))
        sidelined.extend(newly_sidelined)
        for real_card in newly_held:
            pool.append(Card(name=f"Held ({real_card.name})", class_name=class_name, modes=()))
        held_power_cards.extend(newly_held)

        if outcome == "win":
            food_before, water_before = food_left, water_left
            missing_hp = max_hero_hp - hero_hp_after
            # Don't burn a whole heal item topping off a scratch — only
            # worth it once missing HP is at least half a heal's value.
            if bandages_left > 0 and missing_hp >= BANDAGE_HEAL / 2:
                bandages_left -= 1
                hero_hp_after = min(max_hero_hp, hero_hp_after + BANDAGE_HEAL)
                missing_hp = max_hero_hp - hero_hp_after
            if food_left > 0 and missing_hp >= BANDAGE_HEAL / 2:
                food_left -= 1
                hero_hp_after = min(max_hero_hp, hero_hp_after + BANDAGE_HEAL)

            # Refresh is all-or-nothing per use, so spending it on a single
            # sidelined card wastes most of its value — wait for at least 2
            # unless this is the last charge (don't let it go to waste
            # entirely if the trip ends before hitting that threshold).
            resource_left = food_left if refresh_resource == "food" else water_left
            worth_using = len(sidelined) >= 2 or (resource_left == 1 and sidelined)
            if resource_left > 0 and worth_using:
                if refresh_resource == "food":
                    food_left -= 1
                else:
                    water_left -= 1
                num_to_restore = len(sidelined)
                removed = 0
                kept = []
                for c in pool:
                    if c.name.startswith("Exhausted (") and removed < num_to_restore:
                        removed += 1
                    else:
                        kept.append(c)
                pool = kept + sidelined
                sidelined = []

            # Power cards (e.g. Blessed Fortitude) are held, not exhausted —
            # ANY restorative use discards them (Food or Water, whichever),
            # not just the class's own refresh resource. Their Max HP buff
            # ends with them, and current HP is clamped down if it's now
            # above the reduced max.
            if held_power_cards and (food_left < food_before or water_left < water_before):
                num_to_return = len(held_power_cards)
                removed = 0
                kept = []
                for c in pool:
                    if c.name.startswith("Held (") and removed < num_to_return:
                        removed += 1
                    else:
                        kept.append(c)
                pool = kept + held_power_cards
                held_power_cards = []
                max_hero_hp -= active_max_hp_buff
                active_max_hp_buff = 0.0
                hero_hp_after = min(hero_hp_after, max_hero_hp)

        log.append(
            TripPullLog(
                pull_num, outcome, rounds_used, hero_hp, hero_hp_after,
                winded_added, oom_added, len(pool),
            )
        )
        hero_hp = hero_hp_after

        if outcome != "win":
            break

    return log


def run_trials(
    class_name: str,
    mob: dict,
    trials: int,
    seed: int = 0,
    hp_override: float | None = None,
    exclude_exhaust: bool = False,
    use_rollout: bool = False,
) -> dict:
    rng = random.Random(seed)
    results = [
        run_pull(class_name, mob, rng, hp_override=hp_override, exclude_exhaust=exclude_exhaust, use_rollout=use_rollout)
        for _ in range(trials)
    ]
    wins = [r for r in results if r.outcome == "win"]
    losses = [r for r in results if r.outcome == "loss"]
    timeouts = [r for r in results if r.outcome == "timeout"]
    return {
        "trials": trials,
        "win_rate": len(wins) / trials,
        "loss_rate": len(losses) / trials,
        "timeout_rate": len(timeouts) / trials,
        "avg_rounds_to_win": statistics.mean(r.rounds for r in wins) if wins else None,
        "avg_hero_hp_remaining_on_win": statistics.mean(r.hero_hp_remaining for r in wins) if wins else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class", dest="class_name", required=True, choices=["warrior", "cleric", "wizard"])
    parser.add_argument("--mob", dest="mob_id", help="mob_id from data/mobs.csv")
    parser.add_argument("--trials", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sweep", action="store_true", help="run against every mob in data/mobs.csv")
    parser.add_argument("--rollout", action="store_true", help="use the rollout chooser instead of plain greedy")
    args = parser.parse_args()

    mobs = load_mobs()

    if args.sweep:
        print(f"{'mob':<16}{'hp':>5}{'atk':>5}{'type':>8}  {'win%':>7}{'loss%':>7}{'t/o%':>7}{'avg_rd':>8}{'avg_hp':>8}")
        for mob_id, mob in mobs.items():
            stats = run_trials(args.class_name, mob, args.trials, args.seed, use_rollout=args.rollout)
            print(
                f"{mob_id:<16}{mob['hp']:>5.0f}{mob['atk']:>5.0f}{mob['mob_type']:>8}  "
                f"{stats['win_rate']*100:>6.1f}%{stats['loss_rate']*100:>6.1f}%{stats['timeout_rate']*100:>6.1f}%"
                f"{(stats['avg_rounds_to_win'] or 0):>8.2f}{(stats['avg_hero_hp_remaining_on_win'] or 0):>8.2f}"
            )
        return

    if not args.mob_id:
        parser.error("--mob is required unless --sweep is set")
    mob = mobs[args.mob_id]
    stats = run_trials(args.class_name, mob, args.trials, args.seed, use_rollout=args.rollout)
    print(f"{args.class_name} vs {mob['name']} (HP {mob['hp']:.0f}, ATK {mob['atk']:.0f}, {mob['mob_type']}) over {args.trials} trials:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
