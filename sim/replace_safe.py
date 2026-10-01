import re

with open('playtest_board_web.py', 'r') as f:
    content = f.read()

content = content.replace('import macro_sim as M', 'import macro_sim as M\nimport leveling_validation as LV\nimport sim_pvp as PvP')

content = content.replace(
'''    hero = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(1, "town"),
                           bag=[None] * M.BAG_SIZE, locked=[False] * M.BAG_SIZE)''',
'''    start_tokens = 0
    if class_name in ("rogue", "necromancer", "warrior", "runecaster"):
        start_tokens = 2
    elif class_name == "paladin":
        start_tokens = 1
        
    hero = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(1, "town"),
                           bag=[None] * M.BAG_SIZE, locked=[False] * M.BAG_SIZE, tokens=start_tokens)'''
)


pvp_funcs = '''
def _cmp_pvp_initiate_next():
    claimants = _S["pvp_claimants"]
    idx = _S["pvp_current_chooser_idx"]
    if idx >= len(claimants):
        return _cmp_pvp_peace()
        
    hero_idx = claimants[idx]
    if _S["controllers"][hero_idx] == "ai":
        hero = _S["board"].heroes[hero_idx]
        declare_war = False
        for other_idx in claimants:
            if other_idx != hero_idx:
                other = _S["board"].heroes[other_idx]
                if hero.tokens >= other.tokens + 2 or _S["rng"].random() < 0.25:
                    declare_war = True
        
        if declare_war:
            return _cmp_pvp_war_declared(hero_idx)
        else:
            _S["pvp_current_chooser_idx"] += 1
            return _cmp_pvp_initiate_next()
            
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
    claimants = _S["pvp_claimants"]
    defender_idx = next(c for c in claimants if c != initiator_idx)
    
    _S["pvp_initiator"] = initiator_idx
    _S["pvp_defender"] = defender_idx
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
        return _cmp_pvp_resolve()
        
    if _S["controllers"][h_idx] == "ai":
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
    board = _S["board"]
    i_idx = _S["pvp_initiator"]
    d_idx = _S["pvp_defender"]
    
    i_hero = board.heroes[i_idx]
    d_hero = board.heroes[d_idx]
    
    i_plan = _S[f"pvp_plan_{i_idx}"]
    d_plan = _S[f"pvp_plan_{d_idx}"]
    
    i_dmg, d_dmg = PvP.resolve_duel(i_hero.class_name, i_plan, d_hero.class_name, d_plan)
    
    i_score = i_dmg + i_hero.tokens
    d_score = d_dmg + d_hero.tokens
    
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
    
    _S["flash"].append(f"PvP! {winner.class_name} defeated {loser.class_name}! ({winner.class_name} dealt {i_dmg if winner_idx == i_idx else d_dmg} dmg, {loser.class_name} dealt {d_dmg if winner_idx == i_idx else i_dmg} dmg)")
    
    return _cmp_pvp_peace()

def _cmp_begin_resolve():
    board = _S["board"]
    rng = _S["rng"]
    
    node_claims = {}
    for hero_idx, action in board.pending_declarations.items():
        if action["type"] == "declare_node":
            node_claims.setdefault(action["node_name"], []).append(hero_idx)
            
    contested_nodes = {node: claims for node, claims in node_claims.items() if len(claims) > 1}
    
    if contested_nodes:
        node = list(contested_nodes.keys())[0]
        claims = contested_nodes[node]
        order = BE._priority_order(board)
        claims_ordered = [h for h in order if h in claims]
        
        _S["pvp_contested_node"] = node
        _S["pvp_claimants"] = claims_ordered
        _S["pvp_current_chooser_idx"] = 0
        return _cmp_pvp_initiate_next()

'''

content = re.sub(
    r'def _cmp_begin_resolve\(\):',
    pvp_funcs + 'def __OLD_cmp_begin_resolve():',
    content
)

content = content.replace('def __OLD_cmp_begin_resolve():', 'def _cmp_begin_resolve_OLD():')

with open('playtest_board_web.py', 'w') as f:
    f.write(content)
