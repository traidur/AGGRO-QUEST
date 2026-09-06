"""Win/loss/contested breakdown for the 9x9 PvP matchup grid, built on sim_pvp.py's true
baseline (not the rejected sim_final_pvp.py). The raw point-margin matrix (score_A - score_B,
averaged across hand pairs) is hard to read as "who actually wins" -- this reports actual
victory percentages instead.

For each hand pair, both sides have several sequence/stance choices and neither knows the
other's hand or pick. Two bounds on the resulting margin matrix M[r,c] (A's score minus B's
score when A plays row r, B plays column c):
  v_low  = max_r min_c M[r,c]   -- the best floor A can guarantee no matter what B does
  v_high = min_c max_r M[r,c]   -- the best floor B can force A down to no matter what A does
v_low <= v_high always. If v_low > 0, A wins this hand pair regardless of B's pick (dominant
win). If v_high < 0, B wins regardless of A's pick (dominant loss for A). Otherwise the hand
pair is genuinely contested -- reported as its own bucket rather than forced into a win or
loss, since collapsing it either way overstates how "solved" hidden-information PvP is.
"""
import numpy as np
from sim_pvp import CLASSES, get_sequences, resolve_duel

class_names = list(CLASSES.keys())


def matchup_breakdown(class_A, class_B):
    hands_A = CLASSES[class_A][3]
    hands_B = CLASSES[class_B][3]

    a_wins = b_wins = contested = 0
    total = 0

    cache = {}
    def cached_duel(s_A, s_B):
        k = (s_A, s_B)
        if k not in cache:
            dA, dB = resolve_duel(class_A, s_A, class_B, s_B)
            cache[k] = dA - dB
        return cache[k]

    for hand_A in hands_A:
        seqs_A = get_sequences(class_A, hand_A)
        for hand_B in hands_B:
            seqs_B = get_sequences(class_B, hand_B)
            matrix = np.zeros((len(seqs_A), len(seqs_B)))
            for r, sA in enumerate(seqs_A):
                for c, sB in enumerate(seqs_B):
                    matrix[r, c] = cached_duel(sA, sB)

            v_low = np.max(np.min(matrix, axis=1))
            v_high = np.min(np.max(matrix, axis=0))

            if v_low > 0:
                a_wins += 1
            elif v_high < 0:
                b_wins += 1
            else:
                contested += 1
            total += 1

    return a_wins / total * 100, b_wins / total * 100, contested / total * 100


if __name__ == "__main__":
    print(f"{'Attacker':<12}{'Defender':<12}{'A wins %':>10}{'B wins %':>10}{'Contested %':>13}")
    class_win_pct = {c: [] for c in class_names}
    for cA in class_names:
        for cB in class_names:
            if cA == cB:
                continue
            a_pct, b_pct, c_pct = matchup_breakdown(cA, cB)
            class_win_pct[cA].append(a_pct)
            print(f"{cA:<12}{cB:<12}{a_pct:10.1f}{b_pct:10.1f}{c_pct:13.1f}")

    print()
    print(f"{'Class':<12}{'Avg dominant-win % vs field':>30}")
    for c in class_names:
        print(f"{c:<12}{np.mean(class_win_pct[c]):30.1f}")
