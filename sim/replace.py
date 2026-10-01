import re

with open('playtest_board_web.py', 'r') as f:
    content = f.read()

new_code = '''def _cmp_begin_resolve():
    board = _S["board"]
    rng = _S["rng"]
    
    # Check for PvP Contention
    node_claims = {}
    for hero_idx, action in board.pending_declarations.items():
        if action["type"] == "declare_node":
            node_claims.setdefault(action["node_name"], []).append(hero_idx)
            
    # Find nodes with 2+ claimants
    contested_nodes = {node: claims for node, claims in node_claims.items() if len(claims) > 1}
    
    if contested_nodes:
        # We only support one PvP contention at a time for the UI flow right now
        node = list(contested_nodes.keys())[0]
        claims = contested_nodes[node]
        # Sort by priority order
        order = BE._priority_order(board)
        claims_ordered = [h for h in order if h in claims]
        
        _S["pvp_contested_node"] = node
        _S["pvp_claimants"] = claims_ordered
        _S["pvp_current_chooser_idx"] = 0
        return _cmp_pvp_initiate_next()

    _S["cmp_declarations_resolved"] = BE._resolve_contested_declarations(board, rng)
    _S["cmp_resolve_order"] = list(_S["cmp_field_idxs"])
    _S["cmp_results"] = {}
    _S["cmp_touched_zones"] = set()
    return _cmp_process_resolve_queue()

def _cmp_pvp_initiate_next():
    claimants = _S["pvp_claimants"]
    idx = _S["pvp_current_chooser_idx"]
    if idx >= len(claimants):
        # Everyone declared peace!
        return _cmp_pvp_peace()
        
    hero_idx = claimants[idx]
    if _S["controllers"][hero_idx] == "ai":
        # AI logic: Declare War if token advantage >= 2 over any other claimant
        hero = _S["board"].heroes[hero_idx]
        declare_war = False
        for other_idx in claimants:
            if other_idx != hero_idx:
                other = _S["board"].heroes[other_idx]
                if hero.tokens >= other.tokens + 2:
                    declare_war = True
        
        if declare_war:
            return _cmp_pvp_war_declared(hero_idx)
        else:
            _S["pvp_current_chooser_idx"] += 1
            return _cmp_pvp_initiate_next()
            
    # Human
    _S["active_hero_idx"] = hero_idx
    return redirect(url_for("cmp_pvp_initiate"))

@app.route("/cmp/pvp/initiate")
def cmp_pvp_initiate():
    hero_idx = _S["active_hero_idx"]
    hero = _S["board"].heroes[hero_idx]
    node = _S["pvp_contested_node"]
    return render_template("pvp_initiate.html", board=_S["board"], hero=hero, flash=_pop_flash(), node=node)

@app.route("/cmp/pvp/declare_peace", methods=["POST"])
def cmp_pvp_declare_peace():
    _S["pvp_current_chooser_idx"] += 1
    return _cmp_pvp_initiate_next()

@app.route("/cmp/pvp/declare_war", methods=["POST"])
def cmp_pvp_declare_war():
    hero_idx = _S["active_hero_idx"]
    return _cmp_pvp_war_declared(hero_idx)

def _cmp_pvp_peace():
    board = _S["board"]
    rng = _S["rng"]
    _S["cmp_declarations_resolved"] = BE._resolve_contested_declarations(board, rng)
    _S["cmp_resolve_order"] = list(_S["cmp_field_idxs"])
    _S["cmp_results"] = {}
    _S["cmp_touched_zones"] = set()
    return _cmp_process_resolve_queue()

def _cmp_pvp_war_declared(initiator_idx):
    # For now, just pick the first other claimant as the defender
    claimants = _S["pvp_claimants"]
    defender_idx = next(c for c in claimants if c != initiator_idx)
    
    _S["pvp_initiator"] = initiator_idx
    _S["pvp_defender"] = defender_idx
    # Setup Hands
    board = _S["board"]
    rng = _S["rng"]
    
    for h_idx in (initiator_idx, defender_idx):
        hero = board.heroes[h_idx]
        mod = M.CARD_SOURCE[hero.class_name]
        with LV.leveled_kit(mod, BE._level2_swaps_for(hero.class_name, hero.acquired)):
            _S[f"pvp_hand_{h_idx}"] = rng.choice(mod.ALL_HANDS)
            
    _S["pvp_current_duelist"] = initiator_idx
    return _cmp_pvp_plan_next()
    
def _cmp_pvp_plan_next():
    h_idx = _S["pvp_current_duelist"]
    if h_idx is None:
        # Both planned, resolve!
        return _cmp_pvp_resolve()
        
    if _S["controllers"][h_idx] == "ai":
        # Bot picks 3 random cards
        hand = _S[f"pvp_hand_{h_idx}"]
        _S[f"pvp_plan_{h_idx}"] = _S["rng"].sample(hand, 3)
        _S["pvp_current_duelist"] = _S["pvp_defender"] if h_idx == _S["pvp_initiator"] else None
        return _cmp_pvp_plan_next()
        
    _S["active_hero_idx"] = h_idx
    return redirect(url_for("cmp_pvp_plan"))
    
@app.route("/cmp/pvp/plan")
def cmp_pvp_plan():
    hero_idx = _S["active_hero_idx"]
    hero = _S["board"].heroes[hero_idx]
    hand = _S[f"pvp_hand_{hero_idx}"]
    return render_template("pvp_plan.html", board=_S["board"], hero=hero, hand=hand, flash=_pop_flash())

@app.route("/cmp/pvp/plan/submit", methods=["POST"])
def cmp_pvp_plan_submit():
    hero_idx = _S["active_hero_idx"]
    hand = _S[f"pvp_hand_{hero_idx}"]
    plan = []
    for i in range(3):
        card_name = request.form.get(f"card_{i}")
        if card_name in hand:
            plan.append(card_name)
    if len(plan) != 3:
        _S["flash"].append("Must select exactly 3 cards.")
        return redirect(url_for("cmp_pvp_plan"))
        
    _S[f"pvp_plan_{hero_idx}"] = plan
    _S["pvp_current_duelist"] = _S["pvp_defender"] if hero_idx == _S["pvp_initiator"] else None
    return _cmp_pvp_plan_next()

def _cmp_pvp_resolve():
    import sim_pvp as PvP
    
    board = _S["board"]
    i_idx = _S["pvp_initiator"]
    d_idx = _S["pvp_defender"]
    
    i_hero = board.heroes[i_idx]
    d_hero = board.heroes[d_idx]
    
    i_plan = _S[f"pvp_plan_{i_idx}"]
    d_plan = _S[f"pvp_plan_{d_idx}"]
    
    i_score = PvP.run_pvp_combat(i_hero.class_name, d_hero.class_name, i_plan, d_plan) + i_hero.tokens
    d_score = PvP.run_pvp_combat(d_hero.class_name, i_hero.class_name, d_plan, i_plan) + d_hero.tokens
    
    if i_score >= d_score:
        winner_idx = i_idx
        loser_idx = d_idx
    else:
        winner_idx = d_idx
        loser_idx = i_idx
        
    winner = board.heroes[winner_idx]
    loser = board.heroes[loser_idx]
    
    winner.tokens = max(0, winner.tokens - 1)
    loser.tokens += 1
    
    winner.gold += 1
    if loser.gold > 0:
        loser.gold -= 1
        winner.gold += 1
        
    board.pending_declarations.pop(loser_idx)
    
    _S["flash"].append(f"PvP! {winner.class_name} defeated {loser.class_name}!")
    
    return _cmp_pvp_peace()
'''

content = re.sub(
    r'def _cmp_begin_resolve\(\):.*?return _cmp_process_resolve_queue\(\)',
    new_code,
    content,
    flags=re.DOTALL
)

with open('playtest_board_web.py', 'w') as f:
    f.write(content)
