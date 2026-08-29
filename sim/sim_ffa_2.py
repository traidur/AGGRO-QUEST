import random

def resolve_duel(p1, tokens1, p2, tokens2, ev_matrix):
    raw_adv = ev_matrix[p1][p2]
    score1 = tokens1 + raw_adv
    score2 = tokens2 
    variance = random.uniform(-2, 2)
    if score1 + variance > score2: return p1, p2
    elif score2 > score1 + variance: return p2, p1
    else: return random.choice([(p1, p2), (p2, p1)])

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
        p1, p2 = random.sample(players, 2)
        winner, loser = resolve_duel(p1, tokens[p1], p2, tokens[p2], ev_matrix)
        wins[winner] += 1
        
        w_tok, l_tok = tokens[winner], tokens[loser]
        tokens[winner] = win_func(w_tok, l_tok)
        tokens[loser] = lose_func(w_tok, l_tok)
        
    print(f"--- {rule_name} ---")
    for p in players:
        print(f"Player {p} Win Rate: {(wins[p]/10000)*2*100:.1f}% | Final Tokens: {tokens[p]}")
    print()

def zst_win(w, l): return max(0, w - 1)
def zst_lose(w, l): return l + 1

run_sim("Rule 3: The Transfer (Winner gives 1 to Loser, or Loser takes from bank)", zst_win, zst_lose)
