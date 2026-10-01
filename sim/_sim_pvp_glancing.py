"""One-off test of a Glancing Blow PvP rule variant: if a melee card would be evaded by
grants_range, it deals ceil(raw_dmg / 2) instead of 0, rather than being fully evaded. Built as
an isolated variant of sim_pvp.py's real resolve_duel (does not modify sim_pvp.py itself, and
is NOT the same code as the deleted, rejected sim_final_pvp.py, which bundled Glancing Blow
with two other rejected rules -- universal Unlocked Execute and a max-HP score bonus -- making
it impossible to tell which one drove the old result). Reuses sim_pvp.py's CLASSES/
get_sequences so the two are apples-to-apples comparable. Answers: does Glancing Blow alone
narrow the roster's token spread, or does it just as easily help the strong classes as the
weak ones (their melee cards get partial credit too)?
"""
import math
import numpy as np
import random

from sim_pvp import CLASSES, get_sequences
from combat_round import RoundState

class_names = list(CLASSES.keys())


def resolve_duel_glancing(class_A, seq_A, class_B, seq_B):
    cards_A, res_func_A, hp_A, _, _ = CLASSES[class_A]
    cards_B, res_func_B, hp_B, _, _ = CLASSES[class_B]

    max_hp_A, max_hp_B = hp_A, hp_B
    state_A, state_B = RoundState(), RoundState()
    cards_list_A, stance_A = seq_A
    cards_list_B, stance_B = seq_B

    for rnd in range(3):
        card_name_A = cards_list_A[rnd]
        card_name_B = cards_list_B[rnd]

        dummy_pattern_2 = [(0, 0)] * 3
        dummy_pattern_3 = [(0, 0, "melee")] * 3

        try:
            out_A = res_func_A(state_A, card_name_A, stance_A, rnd, dummy_pattern_3, max_hp_B, hp_B, hp_A, max_hp_A)
        except ValueError:
            out_A = res_func_A(state_A, card_name_A, stance_A, rnd, dummy_pattern_2, max_hp_B, hp_B, hp_A, max_hp_A)

        try:
            out_B = res_func_B(state_B, card_name_B, stance_B, rnd, dummy_pattern_3, max_hp_A, hp_A, hp_B, max_hp_B)
        except ValueError:
            out_B = res_func_B(state_B, card_name_B, stance_B, rnd, dummy_pattern_2, max_hp_A, hp_A, hp_B, max_hp_B)

        if out_A is None:
            raw_dmg_A, block_A, heal_A = 0, 0, 0
        else:
            raw_dmg_A, block_A, heal_A, state_A = out_A.raw_dmg, out_A.block, out_A.heal, out_A.new_state

        if out_B is None:
            raw_dmg_B, block_B, heal_B = 0, 0, 0
        else:
            raw_dmg_B, block_B, heal_B, state_B = out_B.raw_dmg, out_B.block, out_B.heal, out_B.new_state

        card_data_A = cards_A[card_name_A]
        card_data_B = cards_B[card_name_B]

        type_A = card_data_A.get("combat_type", "melee")
        type_B = card_data_B.get("combat_type", "melee")

        evades_melee_A = card_data_A.get("grants_range", False)
        if hasattr(state_A, "prev_grants_range") and state_A.prev_grants_range:
            evades_melee_A = True

        # GLANCING BLOW: evaded melee damage is halved (rounded up), not zeroed.
        if evades_melee_A and type_B == "melee":
            raw_dmg_B = math.ceil(raw_dmg_B / 2)

        evades_melee_B = card_data_B.get("grants_range", False)
        if hasattr(state_B, "prev_grants_range") and state_B.prev_grants_range:
            evades_melee_B = True

        if evades_melee_B and type_A == "melee":
            raw_dmg_A = math.ceil(raw_dmg_A / 2)

        pierce_A = card_data_A.get("armor_pierce", False)
        pierce_B = card_data_B.get("armor_pierce", False)

        eff_dmg_A = raw_dmg_A if pierce_A else max(0, raw_dmg_A - block_B)
        eff_dmg_B = raw_dmg_B if pierce_B else max(0, raw_dmg_B - block_A)

        kb_A = card_data_A.get("killing_blow", False)
        kb_B = card_data_B.get("killing_blow", False)

        A_kills_B = (hp_B - eff_dmg_A <= 0)
        B_kills_A = (hp_A - eff_dmg_B <= 0)

        if kb_A and A_kills_B:
            eff_dmg_B = 0
        if kb_B and B_kills_A:
            eff_dmg_A = 0

        hp_A = min(max_hp_A, hp_A - eff_dmg_B + heal_A)
        hp_B = min(max_hp_B, hp_B - eff_dmg_A + heal_B)

        if hp_A <= 0 or hp_B <= 0:
            break

    dmg_done_by_A = max_hp_B - hp_B
    dmg_done_by_B = max_hp_A - hp_A
    return dmg_done_by_A, dmg_done_by_B


def matchup_breakdown(class_A, class_B):
    hands_A = CLASSES[class_A][3]
    hands_B = CLASSES[class_B][3]

    a_wins = b_wins = contested = 0
    total = 0

    cache = {}
    def cached_duel(s_A, s_B):
        k = (s_A, s_B)
        if k not in cache:
            dA, dB = resolve_duel_glancing(class_A, s_A, class_B, s_B)
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


def token_bleed():
    ITERATIONS = 10000
    cache = {}
    def cached_margin(cA, sA, cB, sB):
        k = (cA, sA, cB, sB)
        if k not in cache:
            dA, dB = resolve_duel_glancing(cA, sA, cB, sB)
            cache[k] = dA - dB
        return cache[k]

    results = {}
    for cA in class_names:
        avg_tokens_against_all = []
        all_seqs_A = []
        for h in CLASSES[cA][3]:
            all_seqs_A.extend(get_sequences(cA, h))

        for cB in class_names:
            if cA == cB:
                continue
            all_seqs_B = []
            for h in CLASSES[cB][3]:
                all_seqs_B.extend(get_sequences(cB, h))

            tokens_A = tokens_B = 0
            history_A = []
            for _ in range(ITERATIONS):
                sA = random.choice(all_seqs_A)
                sB = random.choice(all_seqs_B)
                diff = cached_margin(cA, sA, cB, sB)
                final_diff = diff + tokens_A - tokens_B

                if final_diff > 0:
                    if tokens_A > 0: tokens_A -= 1
                    else: tokens_B += 1
                elif final_diff < 0:
                    if tokens_B > 0: tokens_B -= 1
                    else: tokens_A += 1
                else:
                    if random.choice([True, False]):
                        if tokens_A > 0: tokens_A -= 1
                        else: tokens_B += 1
                    else:
                        if tokens_B > 0: tokens_B -= 1
                        else: tokens_A += 1
                history_A.append(tokens_A)

            avg_tokens_against_all.append(np.mean(history_A))
        results[cA] = np.mean(avg_tokens_against_all)
    return results


if __name__ == "__main__":
    print("=== Glancing Blow variant: win/loss/contested per class ===")
    print(f"{'Class':<12}{'avg A-win%':>12}{'avg B-win%(loss)':>18}{'avg contested%':>16}")
    class_win_pct = {c: {"a": [], "b": [], "c": []} for c in class_names}
    for cA in class_names:
        for cB in class_names:
            if cA == cB:
                continue
            a, b, c = matchup_breakdown(cA, cB)
            class_win_pct[cA]["a"].append(a)
            class_win_pct[cA]["b"].append(b)
            class_win_pct[cA]["c"].append(c)
    for c in class_names:
        print(f"{c:<12}{np.mean(class_win_pct[c]['a']):12.1f}{np.mean(class_win_pct[c]['b']):18.1f}{np.mean(class_win_pct[c]['c']):16.1f}")

    print()
    print("=== Glancing Blow variant: steady-state token bleed ===")
    bleed = token_bleed()
    for c in class_names:
        print(f"{c:<12}{bleed[c]:.2f}")
