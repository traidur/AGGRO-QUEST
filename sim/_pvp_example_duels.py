"""One-off: find and trace concrete Warrior-vs-Wizard duel examples -- worst beatings and
closest matches -- under the real current sim_pvp.py rules, using each side's security
(maximin) strategy for the dealt hand. Answers "what did the hands actually contain and what
did each side actually play" for specific cases, not just an aggregate percentage."""
import numpy as np
from sim_pvp import CLASSES, get_sequences
from combat_round import RoundState


def resolve_duel_trace(class_A, seq_A, class_B, seq_B):
    cards_A, res_func_A, hp_A, _, _ = CLASSES[class_A]
    cards_B, res_func_B, hp_B, _, _ = CLASSES[class_B]
    max_hp_A, max_hp_B = hp_A, hp_B
    state_A, state_B = RoundState(), RoundState()
    cards_list_A, stance_A = seq_A
    cards_list_B, stance_B = seq_B
    log = []

    for rnd in range(3):
        card_name_A = cards_list_A[rnd]
        card_name_B = cards_list_B[rnd]
        d2 = [(0, 0)] * 3
        d3 = [(0, 0, "melee")] * 3
        try:
            out_A = res_func_A(state_A, card_name_A, stance_A, rnd, d3, max_hp_B, hp_B, hp_A, max_hp_A)
        except ValueError:
            out_A = res_func_A(state_A, card_name_A, stance_A, rnd, d2, max_hp_B, hp_B, hp_A, max_hp_A)
        try:
            out_B = res_func_B(state_B, card_name_B, stance_B, rnd, d3, max_hp_A, hp_A, hp_B, max_hp_B)
        except ValueError:
            out_B = res_func_B(state_B, card_name_B, stance_B, rnd, d2, max_hp_A, hp_A, hp_B, max_hp_B)

        raw_dmg_A, block_A, heal_A = (0, 0, 0) if out_A is None else (out_A.raw_dmg, out_A.block, out_A.heal)
        if out_A: state_A = out_A.new_state
        raw_dmg_B, block_B, heal_B = (0, 0, 0) if out_B is None else (out_B.raw_dmg, out_B.block, out_B.heal)
        if out_B: state_B = out_B.new_state

        card_data_A = cards_A[card_name_A]
        card_data_B = cards_B[card_name_B]
        type_A = card_data_A.get("combat_type", "melee")
        type_B = card_data_B.get("combat_type", "melee")
        evades_A = card_data_A.get("grants_range", False) or getattr(state_A, "prev_grants_range", False)
        evades_B = card_data_B.get("grants_range", False) or getattr(state_B, "prev_grants_range", False)
        evaded_B_dmg = evades_A and type_B == "melee"
        evaded_A_dmg = evades_B and type_A == "melee"
        if evaded_B_dmg: raw_dmg_B = 0
        if evaded_A_dmg: raw_dmg_A = 0

        pierce_A = card_data_A.get("armor_pierce", False)
        pierce_B = card_data_B.get("armor_pierce", False)
        eff_dmg_A = raw_dmg_A if pierce_A else max(0, raw_dmg_A - block_B)
        eff_dmg_B = raw_dmg_B if pierce_B else max(0, raw_dmg_B - block_A)

        kb_A = card_data_A.get("killing_blow", False)
        kb_B = card_data_B.get("killing_blow", False)
        if kb_A and (hp_B - eff_dmg_A <= 0): eff_dmg_B = 0
        if kb_B and (hp_A - eff_dmg_B <= 0): eff_dmg_A = 0

        hp_A = min(max_hp_A, hp_A - eff_dmg_B + heal_A)
        hp_B = min(max_hp_B, hp_B - eff_dmg_A + heal_B)

        log.append(dict(rnd=rnd + 1, card_A=card_name_A, card_B=card_name_B,
                         dmg_to_B=eff_dmg_A, dmg_to_A=eff_dmg_B,
                         A_evaded=evaded_A_dmg, B_evaded=evaded_B_dmg,
                         hp_A_after=hp_A, hp_B_after=hp_B))
        if hp_A <= 0 or hp_B <= 0:
            break

    return log, max_hp_B - hp_B, max_hp_A - hp_A


def security_pick(class_A, hand_A, class_B, hand_B):
    """Each side's maximin (security-strategy) sequence for this specific hand pairing."""
    seqs_A = get_sequences(class_A, hand_A)
    seqs_B = get_sequences(class_B, hand_B)
    M = np.zeros((len(seqs_A), len(seqs_B)))
    for r, sA in enumerate(seqs_A):
        for c, sB in enumerate(seqs_B):
            dA, dB = resolve_duel_trace(class_A, sA, class_B, sB)[1:]
            M[r, c] = dA - dB
    row_mins = np.min(M, axis=1)
    col_maxs = np.max(M, axis=0)
    r_star = int(np.argmax(row_mins))
    c_star = int(np.argmin(col_maxs))
    return seqs_A[r_star], seqs_B[c_star], M[r_star, c_star]


def print_duel(hand_A, seq_A, hand_B, seq_B, margin, label):
    print(f"--- {label} (margin {margin:+.0f} favoring {'Warrior' if margin>0 else 'Wizard'}) ---")
    print(f"Warrior hand dealt: {hand_A}")
    print(f"Warrior plays: {seq_A[0]} (stance {seq_A[1]})")
    print(f"Wizard hand dealt:  {hand_B}")
    print(f"Wizard plays:  {seq_B[0]}")
    log, dA, dB = resolve_duel_trace("Warrior", seq_A, "Wizard", seq_B)
    for r in log:
        evade_note = ""
        if r["A_evaded"]: evade_note += " [Warrior's dmg EVADED by Wizard]"
        if r["B_evaded"]: evade_note += " [Wizard's dmg EVADED by Warrior]"
        print(f"  Round {r['rnd']}: Warrior plays {r['card_A']:<16} -> {r['dmg_to_B']:.0f} dmg to Wizard | "
              f"Wizard plays {r['card_B']:<16} -> {r['dmg_to_A']:.0f} dmg to Warrior{evade_note}")
    print(f"  Final: Warrior dealt {dA:.0f} total, Wizard dealt {dB:.0f} total")
    print()


if __name__ == "__main__":
    hands_A = CLASSES["Warrior"][3]
    hands_B = CLASSES["Wizard"][3]

    results = []
    for hand_A in hands_A:
        for hand_B in hands_B:
            seq_A, seq_B, margin = security_pick("Warrior", hand_A, "Wizard", hand_B)
            results.append((margin, hand_A, seq_A, hand_B, seq_B))

    results.sort(key=lambda x: x[0])  # most negative (worst for Warrior) first

    print("=========== WORST BEATINGS FOR WARRIOR ===========\n")
    for margin, hA, sA, hB, sB in results[:2]:
        print_duel(hA, sA, hB, sB, margin, "Worst case")

    print("=========== CLOSEST MATCHES ===========\n")
    closest = sorted(results, key=lambda x: abs(x[0]))
    for margin, hA, sA, hB, sB in closest[:2]:
        print_duel(hA, sA, hB, sB, margin, "Closest case")
