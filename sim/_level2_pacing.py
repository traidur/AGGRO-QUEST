"""One-off diagnostic (2026-08-23): how many real turns does it take to reach Level 2 (6 XP),
solo vs. in a party of 2/3/4 random classes? Measures each hero's own hero.turns at the moment
their xp first crosses LEVEL2_XP_THRESHOLD -- the real, comparable unit (OPEN_QUESTIONS.md's
"What a turn is"), not trips or rounds. Delete once the finding is written into a guide doc."""
import random
import statistics

import board_engine as BE
import macro_sim as M

CLASSES = list(M.CARD_SOURCE.keys())
SOLO_SEEDS = 40
PARTY_TRIALS = 40
MAX_TURNS = 60


def solo_turns_to_level2(class_name, seed):
    rng = random.Random(seed)
    for alive, gold, xp, quests_completed, trainer_turn, turns in BE.run_solo_chain(
            class_name, "food_only", rng, max_turns=MAX_TURNS):
        if xp >= M.LEVEL2_XP_THRESHOLD:
            return turns
    return None  # didn't reach it within MAX_TURNS


def party_turns_to_level2(class_names_list, seed):
    rng = random.Random(seed)
    reached = {i: None for i in range(len(class_names_list))}
    for round_state in BE.run_competitive_chain(class_names_list, "food_only", rng, max_rounds=MAX_TURNS * 2):
        for i, (alive, gold, xp, position, turns) in round_state.items():
            if reached[i] is None and xp >= M.LEVEL2_XP_THRESHOLD:
                reached[i] = turns
        if all(v is not None for v in reached.values()):
            break
    return reached


def summarize(label, values):
    real = [v for v in values if v is not None]
    missed = len(values) - len(real)
    if not real:
        print(f"{label:28s} no samples reached Level 2 within {MAX_TURNS} turns")
        return
    mean = statistics.mean(real)
    stdev = statistics.stdev(real) if len(real) > 1 else 0.0
    print(f"{label:28s} mean={mean:5.1f}  median={statistics.median(real):5.1f}  "
          f"stdev={stdev:4.1f}  min={min(real):3d}  max={max(real):3d}  n={len(real)}"
          + (f"  ({missed} never reached L2 in {MAX_TURNS} turns)" if missed else ""))


def run_solo():
    print(f"=== Solo: turns to Level 2, {SOLO_SEEDS} seeds/class ===")
    all_values = []
    for class_name in CLASSES:
        values = [solo_turns_to_level2(class_name, seed) for seed in range(SOLO_SEEDS)]
        all_values.extend(values)
        summarize(class_name, values)
    print()
    summarize("ALL CLASSES POOLED", all_values)
    print()


def run_parties(party_size):
    print(f"=== Party of {party_size}: turns to Level 2, {PARTY_TRIALS} random compositions ===")
    per_class_values = {c: [] for c in CLASSES}
    all_values = []
    for trial in range(PARTY_TRIALS):
        rng = random.Random(trial + 5000 + party_size * 100000)
        comp = rng.sample(CLASSES, party_size)
        reached = party_turns_to_level2(comp, trial + 5000 + party_size * 100000)
        for i, class_name in enumerate(comp):
            per_class_values[class_name].append(reached[i])
            all_values.append(reached[i])
    for class_name in CLASSES:
        if per_class_values[class_name]:
            summarize(class_name, per_class_values[class_name])
    print()
    summarize(f"ALL CLASSES POOLED (party={party_size})", all_values)
    print()


if __name__ == "__main__":
    run_solo()
    run_parties(2)
    run_parties(3)
    run_parties(4)
