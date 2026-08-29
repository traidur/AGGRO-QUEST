import random

# Abstract math simulation of the Token Economy in a 4-player FFA
# Classes: A, B, C, D
# Innate matchups (Raw EV differentials)
# A counters B (+3)
# B counters C (+3)
# C counters D (+3)
# D counters A (+3)
# All other matchups are 0 (even)

def resolve_duel(p1, tokens1, p2, tokens2, ev_matrix):
    # p1 vs p2
    raw_adv = ev_matrix[p1][p2]
    score1 = tokens1 + raw_adv
    score2 = tokens2 
    
    # Add small variance (simulating card draw)
    variance = random.uniform(-2, 2)
    
    if score1 + variance > score2:
        return p1, p2
    elif score2 > score1 + variance:
        return p2, p1
    else:
        return random.choice([(p1, p2), (p2, p1)])

def run_sim(rule_name, win_func, lose_func):
    ev_matrix = {
        'A': {'A':0, 'B':3, 'C':0, 'D':-3},
        'B': {'A':-3, 'B':0, 'C':3, 'D':0},
        'C': {'A':0, 'B':-3, 'C':0, 'D':3},
        'D': {'A':3, 'B':0, 'C':-3, 'D':0},
    }
    tokens = {'A':0, 'B':0, 'C':0, 'D':0}
    wins = {'A':0, 'B':0, 'C':0, 'D':0}
    
    players = ['A', 'B', 'C', 'D']
    
    for _ in range(10000):
        # Pick 2 random players
        p1, p2 = random.sample(players, 2)
        winner, loser = resolve_duel(p1, tokens[p1], p2, tokens[p2], ev_matrix)
        
        wins[winner] += 1
        
        # Apply rules
        w_tok = tokens[winner]
        l_tok = tokens[loser]
        
        tokens[winner] = win_func(w_tok, l_tok)
        tokens[loser] = lose_func(w_tok, l_tok)
        
    print(f"--- {rule_name} ---")
    for p in players:
        print(f"Player {p} Win Rate: {(wins[p]/10000)*2*100:.1f}% | Final Tokens: {tokens[p]}")
    print()

# Rule 1: Single Correction Bleed (Current Design Doc)
# Winner discards 1. If winner had 0, loser gains 1.
def scb_win(w, l): return max(0, w - 1)
def scb_lose(w, l): return l + 1 if w == 0 else l

# Rule 2: Double Bleed
# Winner discards 1. Loser gains 1. (Always)
def db_win(w, l): return max(0, w - 1)
def db_lose(w, l): return l + 1

# Rule 3: Zero-Sum Transfer
# Winner gives 1 token to Loser. (If winner has 0, loser just gains 1 from bank)
def zst_win(w, l): return max(0, w - 1)
def zst_lose(w, l): return l + 1

run_sim("Rule 1: Single Correction Bleed (Current)", scb_win, scb_lose)
run_sim("Rule 2: Double Bleed (Winner -1, Loser +1 ALWAYS)", db_win, db_lose)
