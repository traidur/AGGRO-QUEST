import random

def resolve_duel(p1, tokens1, p2, tokens2, ev_matrix):
    raw_adv = ev_matrix[p1][p2]
    score1 = tokens1 + raw_adv
    score2 = tokens2 
    variance = random.uniform(-2, 2)
    if score1 + variance > score2: return p1, p2
    elif score2 > score1 + variance: return p2, p1
    else: return random.choice([(p1, p2), (p2, p1)])

def run_short_sim():
    ev_matrix = {
        'A': {'A':0, 'B':3, 'C':0, 'D':-3},
        'B': {'A':-3, 'B':0, 'C':3, 'D':0},
        'C': {'A':0, 'B':-3, 'C':0, 'D':3},
        'D': {'A':3, 'B':0, 'C':-3, 'D':0},
    }
    players = ['A', 'B', 'C', 'D']
    
    max_tokens_seen = 0
    for _ in range(1000):
        tokens = {'A':0, 'B':0, 'C':0, 'D':0}
        for _ in range(10): # 10 duels in a game
            p1, p2 = random.sample(players, 2)
            winner, loser = resolve_duel(p1, tokens[p1], p2, tokens[p2], ev_matrix)
            
            # Double Bleed Rule
            tokens[winner] = max(0, tokens[winner] - 1)
            tokens[loser] += 1
            max_tokens_seen = max(max_tokens_seen, max(tokens.values()))
            
    print(f"Max tokens seen in a 10-duel game using Double Bleed: {max_tokens_seen}")

run_short_sim()
