"""One-off diagnostic (2026-08-23): does per-hero Level-2 pacing penalty really shrink with
competitive group size, or is that noise? Directly instruments _blind_redraw (only called when
a Node is actually contested) to measure the real contention rate per group size, correlated
against turns-to-Level-2. Delete once the finding is written up."""
import random
import statistics

import board_engine as BE
import macro_sim as M

CLASSES = list(M.CARD_SOURCE.keys())
MAX_TURNS = 60
TRIALS = 120  # per group size, much larger than the first pass


def party_turns_and_contention(class_names_list, seed):
    rng = random.Random(seed)
    reached = {i: None for i in range(len(class_names_list))}
    contention_count = [0]
    declare_count = [0]

    orig_blind = BE._blind_redraw
    orig_advance = BE.advance_board

    def traced_blind(board, zone_id, level, rng_):
        contention_count[0] += 1
        return orig_blind(board, zone_id, level, rng_)

    def traced_advance(board, class_names, rng_, risk_tolerance_base, risk_only_as_last_resort):
        declare_count[0] += sum(1 for a in board.pending_declarations.values() if a["type"] == "declare_node")
        return orig_advance(board, class_names, rng_, risk_tolerance_base, risk_only_as_last_resort)

    BE._blind_redraw = traced_blind
    BE.advance_board = traced_advance
    try:
        for round_state in BE.run_competitive_chain(class_names_list, "food_only", rng, max_rounds=MAX_TURNS * 2):
            for i, (alive, gold, xp, position, turns) in round_state.items():
                if reached[i] is None and xp >= M.LEVEL2_XP_THRESHOLD:
                    reached[i] = turns
            if all(v is not None for v in reached.values()):
                break
    finally:
        BE._blind_redraw = orig_blind
        BE.advance_board = orig_advance
    return reached, contention_count[0], declare_count[0]


def run_group_size(size):
    all_turns = []
    total_contentions = 0
    total_declares = 0
    for trial in range(TRIALS):
        seed = trial + 9000 + size * 100000
        rng = random.Random(seed)
        comp = rng.sample(CLASSES, size)
        reached, contentions, declares = party_turns_and_contention(comp, seed)
        all_turns.extend(v for v in reached.values() if v is not None)
        total_contentions += contentions
        total_declares += declares
    mean = statistics.mean(all_turns)
    sem = statistics.stdev(all_turns) / (len(all_turns) ** 0.5)
    contention_rate = total_contentions / total_declares if total_declares else 0.0
    print(f"group={size}: turns mean={mean:.2f} +/- {sem:.2f} (SEM), n={len(all_turns)}  |  "
          f"contention rate={contention_rate:.1%} ({total_contentions}/{total_declares} declares)")
    return mean, sem, contention_rate


if __name__ == "__main__":
    print(f"=== {TRIALS} trials per group size, {MAX_TURNS*2}-round cap ===")
    for size in (2, 3, 4):
        run_group_size(size)
