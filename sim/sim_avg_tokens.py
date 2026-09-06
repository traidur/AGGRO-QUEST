"""Steady-state Battle Hardened token simulator. Runs many randomized PvP duels per matchup
(via sim_pvp.py, the true PvP baseline) with the winner-discards/loser-gains pendulum applied
each duel, and reports each class's long-run average token count -- a proxy for how hard the
pendulum has to work to keep that class at parity. Used to re-derive starting Battle Hardened
Token counts after a card/kit change (see AI_HANDOFF.md's 2026-08-30 entry and DESIGN_DOC.md
Section X for the Necromancer re-derivation this tool produced)."""
import numpy as np
import random
import sim_pvp as PvP
from sim_pvp import CLASSES, get_sequences, evaluate_matchup

class_names = list(CLASSES.keys())
ITERATIONS = 10000

cache = {}
def cached_duel(cA, s_A, cB, s_B):
    k = (cA, s_A, cB, s_B)
    if k not in cache:
        dA, dB = PvP.resolve_duel(cA, s_A, cB, s_B)
        cache[k] = dA - dB
    return cache[k]

for cA in class_names:
    hands_A = CLASSES[cA][3]
    all_seqs_A = []
    for h in hands_A:
        all_seqs_A.extend(get_sequences(cA, h))
        
    avg_tokens_against_all = []
        
    for cB in class_names:
        if cA == cB: continue
        hands_B = CLASSES[cB][3]
        all_seqs_B = []
        for h in hands_B:
            all_seqs_B.extend(get_sequences(cB, h))
            
        tokens_A = 0
        tokens_B = 0
        history_A = []
        
        for _ in range(ITERATIONS):
            sA = random.choice(all_seqs_A)
            sB = random.choice(all_seqs_B)
            diff = cached_duel(cA, sA, cB, sB)
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
            
        avg_tokens = np.mean(history_A)
        avg_tokens_against_all.append(avg_tokens)
        
    print(f"{cA} Average Tokens Held: {np.mean(avg_tokens_against_all):.2f}")
