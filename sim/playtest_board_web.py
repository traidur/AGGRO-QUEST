"""
Browser front end for the full human-playable game (solo + competitive) -- the web
counterpart to playtest_board_cli.py, built 2026-08-23 once combat_engine.py and
board_engine.py's Town/Travel/competitive seams were all complete and CLI-proven.

Architecture (checkpointed against AGGRO's own web.py, ui/StS_WoW_Sim/web.py, confirmed by
reading it directly): single global session state, plain server-rendered Jinja2, full-page-
reload forms -- no threads, no generators, no sessions. AGGRO's own engine is already
plain/synchronous (get_legal_actions/apply_action, no blocking calls anywhere); its web layer
just renders once per request and waits for the next one to supply the next action, using one
global GameState mutated in place. board_engine.py/combat_engine.py already have the identical
shape, so the same pattern applies directly.

The one real wrinkle solved here: combat itself doesn't need per-round requests. QUEST's mob
pattern (all 3 rounds' ATK/Block) is fully visible before any card is played -- there is no
hidden information across rounds, which is exactly why best_line_for_hand can brute-force the
whole ordering space. So a human can plan their full 3-card sequence (and Warrior stance) in
ONE page and submit it as ONE request; the server resolves the whole pull synchronously using
make_sequence_decide_fn below, which just replays the submitted order -- same cache-and-replay
shape as QuestIntelligence.decide_combat, fed from a form instead of the solver. This needed
one small additive backend change (board_engine.py's hand=None threading, task #75) so the web
route can draw the hand FIRST (to show it) and reuse that exact hand when resolving, rather
than the pull drawing a second, different hand internally.

Competitive mode's contested Nodes are the one place a human's target can change (blind
redraw) after they declare -- so a human's turn there is two page-loads instead of one:
declare the target, then (once the round's contested-node math resolves via
board_engine._resolve_contested_declarations, task #79) see the real final mob and submit the
combat plan. No hidden-information scheme between human players either, matching AGGRO's own
turn_order/active_hero_idx pattern -- players act in sequence on the same shared screen.

Run:
    python playtest_board_web.py
    python playtest_board_web.py --port 8080
"""
from __future__ import annotations


import json
import os



_CARDS_TEXT = {}
try:
    with open(os.path.join(os.path.dirname(__file__), "../pnp-tool/src/cards_text.json"), "r", encoding="utf-8") as f:
        _CARDS_TEXT = json.load(f)
except Exception as e:
    print(f"Warning: could not load cards_text.json: {e}")

# tier/type flavor only (e.g. "Standard"/"Elite", "melee"/"ranged") -- static and safe to read
# from this file since it's cosmetic and doesn't vary by class. ATK/BLK/HP numbers are NEVER
# read from here -- those come live from the real sim data passed into the template each time,
# the same lesson the matchup-table fix (2026-08-26) already established for this exact risk.
_MOBS_TEXT = {}
try:
    with open(os.path.join(os.path.dirname(__file__), "../pnp-tool/src/mobs_text.json"), "r", encoding="utf-8") as f:
        _MOBS_TEXT = {m["name"]: m for m in json.load(f)}
except Exception as e:
    print(f"Warning: could not load mobs_text.json: {e}")

import argparse
import random

from flask import Flask, redirect, render_template, request, url_for

import board_engine as BE
import board_state as B
import combat_engine as E
import macro_sim as M
import leveling_validation as LV
import sim_pvp as PvP
import class_mob_matchup_chart as MC
from board_state import HeroBoardState

app = Flask(__name__, template_folder="playtest_board_web_templates")

# Single-user global state -- deliberately not per-session (matches playtest_web.py's own
# "local single-player tool, no sessions needed" convention). _S holds everything needed to
# resume rendering the current page after any request; see reset_session() for the full shape.
_S = {}


def get_item_name(slot):
    if not slot: return None
    if isinstance(slot, str): return slot
    if isinstance(slot, dict) and "items" in slot:
        return list(slot["items"].keys())[0]
    return None

def get_item_count(slot):
    if not slot: return 0
    if isinstance(slot, str): return 1
    if isinstance(slot, dict) and "items" in slot:
        return list(slot["items"].values())[0]
    return 1


def _matchup_summary(per_mob):
    """per_mob: {mob_name: (cost_pct, win_pct)} for one class -- collapses to the
    best_1/best_2/worst_1/worst_2 shape the Class Guide modal renders."""
    by_cost = sorted(per_mob.items(), key=lambda kv: kv[1][0])
    (b1, (b1c, _)), (b2, (b2c, _)) = by_cost[0], by_cost[1]
    (w2, (w2c, _)), (w1, (w1c, _)) = by_cost[-2], by_cost[-1]
    return {"best_1": b1, "best_1_cost": round(b1c, 1), "best_2": b2, "best_2_cost": round(b2c, 1),
            "worst_1": w1, "worst_1_cost": round(w1c, 1), "worst_2": w2, "worst_2_cost": round(w2c, 1)}


# Computed once at import time (real solver output, not hand-typed -- checkpointed 2026-08-26,
# replacing a frozen, already-stale hardcoded block a prior pass had baked in directly here).
# See class_mob_matchup_chart.py's own docstring for why "fully upgraded kit" rather than any
# one hero's exact current deck, and why Level 1 vs Level 2 needs two separate tables at all.
_MATCHUP_BY_LEVEL = {
    level: {cls.lower(): _matchup_summary(per_mob) for cls, per_mob in MC.matchup_table(level=level).items()}
    for level in (1, 2)
}


def get_class_matchup(class_name, xp):
    level = 2 if xp >= M.LEVEL2_XP_THRESHOLD else 1
    return _MATCHUP_BY_LEVEL[level].get(class_name, {})


@app.context_processor
def inject_globals():
    return dict(
        quest_locations={v[1]: k.replace('_', ' ').title() for k, v in M.NODES.items()},
        get_class_matchup=get_class_matchup,
        get_mob_flavor=lambda mob_name: _MOBS_TEXT.get(mob_name, {}),
        get_item_name=get_item_name,
        get_item_count=get_item_count
    )



def reset_session():
    _S.clear()
    _S.update(dict(
        mode=None, board=None, class_names={}, controllers={}, purchase_queues={},
        rng=None, strategy="food_only", phase="setup", town_entered=False, trainer_entered=False,
        pending_kind=None, pending_action=None, pending_hand=None, pending_border=None,
        flash=[], active_hero_idx=0,
        # Competitive-only fields, see _cmp_begin_round's own docstring for the state machine.
        labels={}, human_count=0, round_num=0,
        cmp_town_pending=[], cmp_town_entered={}, cmp_trainer_entered={},
        cmp_field_idxs=[], cmp_quest_pools={}, cmp_claimed_this_round=set(), cmp_declare_order=[],
        cmp_declarations_resolved=None, cmp_resolve_order=[], cmp_results={}, cmp_touched_zones=set(),
    ))


reset_session()


def make_sequence_decide_fn(sequence, stance_sequence=None):
    """Web-facing decide_fn -- replays a human's pre-submitted full card ordering (and Warrior
    stance choice) instead of computing anything live. Mirrors QuestIntelligence.decide_combat's
    cache-and-replay shape exactly, except the sequence comes from a submitted web form instead
    of the solver -- see this module's own docstring for why committing to a full ordering up
    front costs nothing in decision quality versus round-by-round play."""
    def decide_fn(state, actions):
        variant = sequence[state.round_num]
        stance = stance_sequence[state.round_num] if stance_sequence else None
        for action in actions:
            if action["variant"] == variant and action.get("stance") == stance and action.get("legal"):
                return action
        raise ValueError(f"submitted sequence illegal at round {state.round_num}: "
                          f"variant={variant!r} stance={stance!r}")
    return decide_fn


def _current_quest_pool(hero):
    return M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS



def _build_map_data(board, active_hero_idx=0):
    import macro_sim as M
    import leveling_validation as LV
    import sim_pvp as PvP
    zones = {}
    
    # All existing zones based on nodes
    all_zones = sorted(list(set(M.NODE_ZONE.values())))
    for z in all_zones:
        zones[z] = {"id": z, "name": f"Zone {z}", "nodes": [], "town_heroes": [], "trainer_heroes": [], "borders": []}
    
    # Place heroes
    for i, h in enumerate(board.heroes):
        z, n = h.position
        if isinstance(z, int) and n == "town":
            if z in zones:
                zones[z]["town_heroes"].append(i)
        elif isinstance(z, int) and n == "trainer":
            if z in zones:
                zones[z]["trainer_heroes"].append(i)
        elif isinstance(z, int):
            # In a node
            pass
            
    for node_name, z in M.NODE_ZONE.items():
        mob = board.zones[z].dealt.get(node_name) if z in board.zones else None
        heroes_here = [i for i, h in enumerate(board.heroes) if h.position == (z, node_name)]
        zones[z]["nodes"].append({"id": node_name, "mob": mob, "heroes": heroes_here})
        
    for border_name, z_set in M.BORDER_NODES.items():
        z_list = list(z_set)
        if len(z_list) == 2:
            z1, z2 = z_list
            heroes_here = [i for i, h in enumerate(board.heroes) if h.position[0] == border_name]
            if z1 in zones: zones[z1]["borders"].append({"id": border_name, "target": z2, "heroes": heroes_here})
            if z2 in zones: zones[z2]["borders"].append({"id": border_name, "target": z1, "heroes": heroes_here})

    return zones


def _build_action_dict(actions):
    """Maps a map-clickable key -> action index, for travel.html's map-pin onclick handlers.
    Node/Border/Zone-targeted actions key by their own node_name/border_name/target_zone;
    everything else (visit_trainer, return_to_town, use_food, etc. -- anything with none of
    those three fields) keys by its own action "type" string instead. Fixed 2026-08-24 -- the
    original version fell through all three .get()s to None for every type-only action, so
    return_to_town and visit_trainer's map pins (which look up action_dict.get('return_to_town')/
    action_dict.get('visit_trainer') by literal string) could never actually match anything and
    always rendered inactive, confirmed by reading both the Python and template sides together."""
    result = {}
    for i, a in enumerate(actions):
        key = a.get("node_name", a.get("border_name", a.get("target_zone")))
        if key is None:
            key = a["type"]
        result[key] = i
    return result


def _load_map_coords():
    path = os.path.join(os.path.dirname(__file__), "static", "map_coords.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _flash(msg):
    _S["flash"].append(msg)


def _pop_flash():
    msgs = _S["flash"]
    _S["flash"] = []
    return msgs


def _hand_options(class_name, hand):
    """List of (hand_idx, card_name, variant, label, dict_json) for every selectable option in a hand --"""
    import condensed_necromancer as N
    import json
    options = []
    class_data = _CARDS_TEXT.get(class_name, {})
    for i, card_name in enumerate(hand):
        card_data = class_data.get(card_name, {})
        if class_name == "necromancer" and card_name == N.BONEGUARD_OFFERING:
            options.append((i, card_name, N.BONEGUARD_OFFERING, card_name, json.dumps(card_data)))
            options.append((i, card_name, N.BONEGUARD_OFFERING_BOOSTED, f"{card_name} (Boosted)", json.dumps(card_data)))
        else:
            options.append((i, card_name, card_name, card_name, json.dumps(card_data)))
    return options


def _parse_combat_plan(form, class_name, hand):
    """Parses the combat_plan form into (sequence, stance_sequence, error). Each round field is
    'hand_idx|variant'; validates the 3 rounds use 3 DIFFERENT hand slots (a hand card, once
    played, leaves the hand -- see combat_engine._remaining_hand) before ever touching
    combat_engine, so an invalid submission bounces back to the same page with a message
    instead of raising deep inside the resolution call."""
    used_idxs = set()
    sequence = []
    for round_num in range(3):
        raw = form.get(f"round_{round_num}", "")
        if "|" not in raw:
            return None, None, f"Round {round_num + 1} needs a card chosen."
        idx_s, variant = raw.split("|", 1)
        try:
            idx = int(idx_s)
        except ValueError:
            return None, None, f"Round {round_num + 1}: invalid submission."
        if idx in used_idxs or not (0 <= idx < len(hand)):
            return None, None, f"Round {round_num + 1}: each hand card can only be played once."
        used_idxs.add(idx)
        sequence.append(variant)
    stance_sequence = None
    if M.HAS_STANCE[class_name]:
        stance = form.get("stance")
        if stance not in ("G", "C"):
            return None, None, "Choose a stance (Guardian or Crusader)."
        stance_sequence = [stance] * 3
    return sequence, stance_sequence, None


def _validate_sequence(class_name, hand, mob_name, hero_hp, sequence, stance_sequence):
    """Dry-runs the submitted sequence through combat_engine directly (a throwaway PullState,
    never touching the real hero/board) before committing to it for real -- combat resolution
    is fully deterministic given hand+mob+sequence (no RNG anywhere in get_legal_actions/
    apply_action, the same property that lets best_line_for_hand brute-force it), so this is
    cheap and catches a conditionally-illegal card (e.g. Warrior's Execute, only legal below
    50% mob HP) before it wastes the player's real turn instead of crashing mid-resolution.
    Returns None if the whole sequence is legal round-by-round, else an error string."""
    pattern, mob_hp = M._pattern_hp_for_mob(class_name, mob_name)
    state = E.new_pull_with_hp(class_name, mob_name, hand, pattern, mob_hp, hero_hp)
    decide_fn = make_sequence_decide_fn(sequence, stance_sequence)
    try:
        while state.outcome is None:
            actions = E.get_legal_actions(state)
            action = decide_fn(state, actions)
            state = E.apply_action(state, action)
        return None
    except ValueError as e:
        return (f"That plan isn't legal: {e}. Some cards (like a Warrior's Execute) are only "
                f"playable once the mob is low enough -- try a different order.")


def _build_combat_log(class_name, hand, mob_name, hero_hp, sequence, stance_sequence):
    """Same dry-run shape as _validate_sequence (a throwaway PullState, never the real hero) --
    called only after _validate_sequence has already confirmed the plan is legal, so this one
    never raises. Reconstructs a round-by-round display log purely from combat_engine's own
    get_legal_actions/apply_action output (dmg_dealt, dmg_taken, block, heal, resulting_hp,
    resulting_mob_hp) -- never recomputes or approximates any of it. Safe to run as a SEPARATE
    pass from the real resolution that follows it (rather than trying to extract a log from
    that real call) because combat has zero RNG once hand+mob+sequence are fixed -- this dry
    run is guaranteed to produce numbers identical to the real one, the same determinism
    _validate_sequence already relies on. Returns (rows, final_outcome)."""
    pattern, mob_hp = M._pattern_hp_for_mob(class_name, mob_name)
    state = E.new_pull_with_hp(class_name, mob_name, hand, pattern, mob_hp, hero_hp)
    decide_fn = make_sequence_decide_fn(sequence, stance_sequence)
    rows = []
    while state.outcome is None:
        actions = E.get_legal_actions(state)
        action = decide_fn(state, actions)
        round_pattern = pattern[state.round_num]
        state = E.apply_action(state, action)
        rows.append(dict(
            round_num=state.round_num, card=action["card"],
            variant=action["variant"] if action["variant"] != action["card"] else None,
            stance=action.get("stance"),
            mob_atk=round_pattern[0], mob_blk=round_pattern[1],
            raw_dmg=action["raw_dmg"], block=action["block"], heal=action["heal"],
            dmg_dealt=action["dmg_dealt"], dmg_taken=action["dmg_taken"],
            hp_after=state.hero_hp, mob_hp_after=state.mob_hp_remaining,
        ))
    return rows, state.outcome


def _outcome_message(kind, result):
    outcome = result.get("outcome")
    mob = result.get("mob_name", "the foe")
    if outcome == "win":
        return f"Victory over {mob}! +1 Gold."
    if outcome == "flee":
        return f"Survived but didn't finish off {mob} -- no loot this time."
    if outcome == "no_room":
        return f"Won against {mob}, but your Bag has no room -- loot lost!"
    if outcome == "died":
        return f"You fell to {mob}..."
    return f"Outcome: {outcome}"


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    reset_session()
    return render_template("setup.html", classes=list(M.CARD_SOURCE.keys()))


def _new_hero(class_name, rng):
    mod = M.CARD_SOURCE[class_name]
    max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
    start_tokens = 0
    if class_name == "necromancer":
        start_tokens = 3
    elif class_name in ("rogue", "warrior"):
        start_tokens = 2
    elif class_name in ("ranger", "wizard", "cleric", "runecaster"):
        start_tokens = 1
        
    hero = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(1, "town"),
                           bag=[None] * M.BAG_SIZE, locked=[False] * M.BAG_SIZE, tokens=start_tokens)
    M._add_food(hero.bag, hero.locked)
    if class_name in M.LEVEL2_PURCHASED_ORDER:
        hero.skill_purchase_order = list(range(len(M.LEVEL2_PURCHASED_ORDER[class_name])))
        rng.shuffle(hero.skill_purchase_order)
    return hero


@app.route("/start", methods=["POST"])
def start():
    reset_session()
    class_name = request.form.get("class_name")
    seed_raw = request.form.get("seed", "").strip()
    seed = int(seed_raw) if seed_raw else None
    rng = random.Random(seed)

    hero = _new_hero(class_name, rng)
    purchase_queues = {0: M._build_purchase_queue(class_name, 0)}
    level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
    board = B.BoardState(mode="solo", heroes=[hero], zones={}, level_decks=level_decks)
    board.setup_quests(rng)

    _S.update(mode="solo", board=board, class_names={0: class_name}, controllers={0: "human"},
              purchase_queues=purchase_queues, rng=rng, phase="town", town_entered=False,
              active_hero_idx=0)
    return redirect(url_for("town"))


# ---------------------------------------------------------------------------
# Town
# ---------------------------------------------------------------------------

@app.route("/town")
def town():
    if _S["board"] is None:
        return redirect(url_for("index"))
    hero = _S["board"].heroes[0]
    class_name = _S["class_names"][0]
    if not _S["town_entered"]:
        setup = BE.enter_town(hero, class_name, _S["strategy"], _S["rng"], _S["board"])
        if setup["quests_completed"]:
            _flash(f"Turned in {setup['quests_completed']} quest(s).")
        _S["town_entered"] = True
    actions = BE.get_town_actions(hero, _S["purchase_queues"][0], _S["board"])
    return render_template("town.html", hero=hero, actions=list(enumerate(actions)), board=_S["board"],
                            flash=_pop_flash())


@app.route("/town/action", methods=["POST"])
def town_action():
    if _S["board"] is None:
        return redirect(url_for("index"))
    hero = _S["board"].heroes[0]
    actions = BE.get_town_actions(hero, _S["purchase_queues"][0], _S["board"])
    idx = int(request.form.get("idx", -1))
    if not (0 <= idx < len(actions)):
        return redirect(url_for("town"))
    action = actions[idx]
    still_in_town = BE.apply_town_action(hero, action, _S["purchase_queues"][0], _S["board"], _S["rng"])
    if not still_in_town:
        _S["town_entered"] = False
        if hero.corpse_node is not None:
            return redirect(url_for("recovery_intro"))
        _S["phase"] = "travel"
        return redirect(url_for("travel"))
    return redirect(url_for("town"))


# ---------------------------------------------------------------------------
# Class Trainer (checkpointed 2026-08-24: split from Town into its own turn-costing node
# type -- see board_engine.get_town_actions/_trainer_automatic_setup's own docstrings for the
# full finding. Mirrors the Town routes exactly, using the SAME get_town_actions/
# apply_town_action functions (filtered by hero.position's "trainer" marker) -- only
# enter_trainer/leave_trainer differ from Town's own enter_town/leave_town.)
# ---------------------------------------------------------------------------

@app.route("/trainer")
def trainer():
    if _S["board"] is None:
        return redirect(url_for("index"))
    hero = _S["board"].heroes[0]
    class_name = _S["class_names"][0]
    if not _S["trainer_entered"]:
        setup = BE.enter_trainer(hero, class_name)
        if setup["mandatory_turn"]:
            _flash("You've been granted your mandatory Level 2 upgrade!")
        _S["trainer_entered"] = True
    actions = BE.get_town_actions(hero, _S["purchase_queues"][0], _S["board"])
    return render_template("town.html", hero=hero, actions=list(enumerate(actions)), board=_S["board"],
                            flash=_pop_flash(), action_url=url_for("trainer_action"))


@app.route("/trainer/action", methods=["POST"])
def trainer_action():
    if _S["board"] is None:
        return redirect(url_for("index"))
    hero = _S["board"].heroes[0]
    actions = BE.get_town_actions(hero, _S["purchase_queues"][0], _S["board"])
    idx = int(request.form.get("idx", -1))
    if not (0 <= idx < len(actions)):
        return redirect(url_for("trainer"))
    action = actions[idx]
    still_at_trainer = BE.apply_town_action(hero, action, _S["purchase_queues"][0], _S["board"], _S["rng"])
    if not still_at_trainer:
        _S["trainer_entered"] = False
        _S["phase"] = "travel"
        return redirect(url_for("travel"))
    return redirect(url_for("trainer"))


# ---------------------------------------------------------------------------
# Recovery (forced first action of a trip when hero.corpse_node is set)
# ---------------------------------------------------------------------------

@app.route("/recovery")
def recovery_intro():
    """Determines the forced recovery target and either goes straight to combat_plan (Node
    case -- mob's already known, no choice) or to scouted_pick (Border case -- gets the same
    reveal-2-pick-1 treatment an ordinary crossing does, rather than the AI-automatic path's
    auto-pick, since a human recovering their corpse is still a human making a real choice)."""
    hero = _S["board"].heroes[0]
    class_name = _S["class_names"][0]
    board = _S["board"]
    rng = _S["rng"]
    corpse = hero.corpse_node
    if corpse is None:
        return redirect(url_for("travel"))

    if corpse.startswith("border:"):
        _, border_name, _origin_zone, target_zone_s = corpse.split(":")
        target_zone = int(target_zone_s)
        level_deck = board.level_decks[BE.TIER_TO_LEVEL[M.ZONE_TIER[target_zone]]]
        candidates = BE.reveal_scouted_pull_candidates(level_deck, rng)
        _S["pending_kind"] = "recovery_border"
        _S["pending_border"] = dict(candidates=candidates, border_name=border_name, target_zone=target_zone)
        _S["phase"] = "scouted_pick"
        return redirect(url_for("scouted_pick"))

    node_name = corpse
    zone_id = M.NODE_ZONE[node_name]
    level = BE.TIER_TO_LEVEL[M.ZONE_TIER[zone_id]]
    node_names = BE._nodes_in_zone(zone_id)
    B.deal_zone(board, zone_id, level, node_names, rng)
    mob_name = board.zones[zone_id].dealt[node_name]
    mod = M.CARD_SOURCE[class_name]
    hand = rng.choice(mod.ALL_HANDS)
    _S["pending_kind"] = "recovery_node"
    _S["pending_action"] = {"node_name": node_name, "mob_name": mob_name}
    _S["pending_hand"] = hand
    _S["phase"] = "combat_plan"
    return redirect(url_for("combat_plan"))


# ---------------------------------------------------------------------------
# Travel
# ---------------------------------------------------------------------------

@app.route("/travel")
def travel():
    if _S["board"] is None:
        return redirect(url_for("index"))
    hero = _S["board"].heroes[0]
    actions = BE.get_travel_actions(hero, _S["board"], _S["rng"])
    return render_template("travel.html", board=_S["board"], hero=hero, actions=list(enumerate(actions)), flash=_pop_flash(),
                            map_data=_build_map_data(_S["board"], 0), action_dict=_build_action_dict(actions),
                            coords=_load_map_coords())


@app.route("/travel/action", methods=["POST"])
def travel_action():
    hero = _S["board"].heroes[0]
    class_name = _S["class_names"][0]
    board = _S["board"]
    rng = _S["rng"]
    actions = BE.get_travel_actions(hero, board, rng)
    idx = int(request.form.get("idx", -1))
    if not (0 <= idx < len(actions)):
        return redirect(url_for("travel"))
    action = actions[idx]

    if action["type"] == "declare_node":
        mod = M.CARD_SOURCE[class_name]
        hand = rng.choice(mod.ALL_HANDS)
        _S["pending_kind"] = "declare"
        _S["pending_action"] = action
        _S["pending_hand"] = hand
        _S["phase"] = "combat_plan"
        return redirect(url_for("combat_plan"))

    if action["type"] == "cross_border":
        result = BE.apply_travel_action(hero, action, class_name, board, rng,
                                         M.RISK_TOLERANCE_BASE, True)
        _S["pending_kind"] = "cross_border"
        _S["pending_border"] = dict(candidates=result["candidates"], border_name=result["border_name"],
                                     target_zone=result["target_zone"])
        _S["phase"] = "scouted_pick"
        return redirect(url_for("scouted_pick"))

    if action["type"] == "return_to_town":
        BE.apply_travel_action(hero, action, class_name, board, rng, M.RISK_TOLERANCE_BASE, True)
        _S["phase"] = "town"
        return redirect(url_for("town"))

    if action["type"] == "visit_trainer":
        # Checkpointed 2026-08-24: Class Trainer split from Town into its own turn-costing
        # node type -- falling through to the generic tail below (which just re-renders
        # /travel) would be wrong here, same as return_to_town needs its own explicit branch:
        # hero.position becomes (zone_id, "trainer"), which needs the Trainer's own route/menu,
        # not another Travel-menu render.
        BE.apply_travel_action(hero, action, class_name, board, rng, M.RISK_TOLERANCE_BASE, True)
        _S["phase"] = "trainer"
        return redirect(url_for("trainer"))

    # use_food / use_potion / use_scroll / use_smoke_bomb / flight_path / enter_zone --
    # no combat, resolves in one shot.
    result = BE.apply_travel_action(hero, action, class_name, board, rng, M.RISK_TOLERANCE_BASE, True)
    if result.get("outcome") in ("win", "flee", "no_room"):
        _flash(_outcome_message("instant", result))
    elif result.get("outcome") == "healed":
        _flash(f"HP now {hero.hp:.0f}/{hero.max_hp:.0f}.")
    return redirect(url_for("travel"))


# ---------------------------------------------------------------------------
# Scouted Pull reveal-and-pick (ordinary crossing OR a Border-shaped recovery)
# ---------------------------------------------------------------------------

@app.route("/scouted_pick")
def scouted_pick():
    if _S["pending_border"] is None:
        return redirect(url_for("travel"))
    return render_template("scouted_pick.html", candidates=_S["pending_border"]["candidates"])


@app.route("/scouted_pick/choose", methods=["POST"])
def scouted_pick_choose():
    hero = _S["board"].heroes[0]
    class_name = _S["class_names"][0]
    pick = request.form.get("pick")
    candidates = _S["pending_border"]["candidates"]
    mob_name = candidates[0] if pick == "0" else candidates[1]

    mod = M.CARD_SOURCE[class_name]
    hand = _S["rng"].choice(mod.ALL_HANDS)
    _S["pending_action"] = dict(_S["pending_border"], mob_name=mob_name)
    _S["pending_hand"] = hand
    _S["phase"] = "combat_plan"
    return redirect(url_for("combat_plan"))


# ---------------------------------------------------------------------------
# Combat plan -- one page, whole-hand submission
# ---------------------------------------------------------------------------

@app.route("/combat_plan")
def combat_plan():
    hero = _S["board"].heroes[0]
    class_name = _S["class_names"][0]
    hand = _S["pending_hand"]
    mob_name = _S["pending_action"]["mob_name"]
    pattern, mob_hp = M._pattern_hp_for_mob(class_name, mob_name)
    return render_template(
        "combat_plan.html", class_name=class_name, mob_name=mob_name,
        pattern=list(enumerate(pattern)), mob_hp=mob_hp, hero=hero,
        hand_options=_hand_options(class_name, hand), has_stance=M.HAS_STANCE[class_name],
        pending_kind=_S["pending_kind"], flash=_pop_flash(),
    )


@app.route("/combat_plan/submit", methods=["POST"])
def combat_plan_submit():
    hero = _S["board"].heroes[0]
    class_name = _S["class_names"][0]
    board = _S["board"]
    rng = _S["rng"]
    hand = _S["pending_hand"]
    kind = _S["pending_kind"]
    pending = _S["pending_action"]

    sequence, stance_sequence, error = _parse_combat_plan(request.form, class_name, hand)
    if error is None:
        error = _validate_sequence(class_name, hand, pending["mob_name"], hero.hp, sequence, stance_sequence)
    if error:
        _flash(error)
        return redirect(url_for("combat_plan"))

    # Built BEFORE the real resolution below, from a separate throwaway dry run -- see
    # _build_combat_log's own docstring for why that's safe (zero RNG once the plan is fixed).
    log_rows, log_outcome = _build_combat_log(class_name, hand, pending["mob_name"], hero.hp,
                                               sequence, stance_sequence)
    decide_fn = make_sequence_decide_fn(sequence, stance_sequence)

    if kind == "declare":
        result = BE.apply_travel_action(hero, pending, class_name, board, rng,
                                         M.RISK_TOLERANCE_BASE, True, decide_fn=decide_fn, hand=hand)
    elif kind == "cross_border":
        result = BE.resolve_border_crossing(hero, class_name, pending["border_name"], pending["target_zone"],
                                             pending["mob_name"], rng, M.RISK_TOLERANCE_BASE, True,
                                             decide_fn=decide_fn, hand=hand)
    elif kind == "recovery_node":
        quest_pool = _current_quest_pool(hero)
        zone_id = M.NODE_ZONE[pending["node_name"]]
        level = BE.TIER_TO_LEVEL[M.ZONE_TIER[zone_id]]
        result = BE.resolve_node_pull(hero, class_name, pending["node_name"], pending["mob_name"], quest_pool,
                                       rng, M.RISK_TOLERANCE, M.RISK_TOLERANCE_BASE, True,
                                       suppress_loot=True, decide_fn=decide_fn, hand=hand)
        B.discard_zone(board, zone_id, level)
        if result.get("outcome") != "died":
            hero.corpse_node = None
    else:  # recovery_border
        result = BE.resolve_border_crossing(hero, class_name, pending["border_name"], pending["target_zone"],
                                             pending["mob_name"], rng, M.RISK_TOLERANCE_BASE, True,
                                             decide_fn=decide_fn, hand=hand)
        if result.get("outcome") != "died":
            hero.corpse_node = None

    _S["pending_kind"] = None
    _S["pending_action"] = None
    _S["pending_hand"] = None
    _S["pending_border"] = None

    next_flashes = []
    if result.get("outcome") == "died":
        death_node = result.get("death_marker", pending.get("node_name") if pending else None)
        BE.apply_death_post_processing(hero, _current_quest_pool(hero), death_node)
        next_flashes.append(_outcome_message(kind, result))
        _S["pending_next_phase"] = "town"
    else:
        if kind in ("recovery_node", "recovery_border"):
            hero.alive = True
            next_flashes.append("You've recovered your gear.")
        next_flashes.append(_outcome_message(kind, result))
        _S["pending_next_phase"] = "travel"
    _S["pending_next_flashes"] = next_flashes

    mob_pattern, mob_hp_total = M._pattern_hp_for_mob(class_name, pending["mob_name"])
    _S["phase"] = "combat_result"
    return render_template("combat_result.html", class_name=class_name, mob_name=pending["mob_name"],
                            rows=log_rows, outcome=log_outcome, hero=hero,
                            pattern=list(enumerate(mob_pattern)), mob_hp=mob_hp_total)


@app.route("/combat_plan/continue", methods=["POST"])
def combat_plan_continue():
    next_phase = _S.pop("pending_next_phase")
    for msg in _S.pop("pending_next_flashes", []):
        _flash(msg)
    _S["phase"] = next_phase
    return redirect(url_for(next_phase))


# ---------------------------------------------------------------------------
# Competitive mode -- N=2-4 heroes, any human/AI mix, sequential turns on one shared screen
# ---------------------------------------------------------------------------
#
# State machine (mirrors playtest_board_cli.py's play_competitive, but each "pause point" is
# its own page instead of a blocking input()):
#   cmp_town      -> per-hero Town visit for whichever human is next in cmp_town_pending
#   cmp_declare   -> per-hero Travel declaration for whichever human is next in cmp_declare_order
#   cmp_scouted_pick / cmp_combat_plan -> a human's resolve-time reveal/plan, keyed by whichever
#                     hero_idx is next in cmp_resolve_order
#   cmp_round_result -> summary once every hero has been resolved this round
# AI-controlled heroes never get a page -- every AI step resolves instantly inline wherever the
# state machine reaches it, exactly like the CLI's controllers[hero_idx] == "ai" branches.

def _cmp_label(hero_idx):
    return _S["labels"][hero_idx]


@app.route("/party")
def party_setup():
    reset_session()
    return render_template("party_setup.html", classes=list(M.CARD_SOURCE.keys()))


@app.route("/party/start", methods=["POST"])
def party_start():
    reset_session()
    specs = []
    for n in range(4):
        class_name = request.form.get(f"class_{n}", "")
        if not class_name:
            continue
        controller = request.form.get(f"controller_{n}", "ai")
        specs.append((class_name, controller))
    if not 2 <= len(specs) <= 4:
        return render_template("party_setup.html", classes=list(M.CARD_SOURCE.keys()),
                                error="Pick 2-4 heroes.")

    seed_raw = request.form.get("seed", "").strip()
    seed = int(seed_raw) if seed_raw else None
    rng = random.Random(seed)

    heroes = [_new_hero(class_name, rng) for class_name, _ctrl in specs]
    class_names = {i: c for i, (c, _ctrl) in enumerate(specs)}
    controllers = {i: ctrl for i, (_c, ctrl) in enumerate(specs)}
    labels = {i: f"Player {i + 1} ({c.title()}, {ctrl})" for i, (c, ctrl) in enumerate(specs)}
    purchase_queues = {i: M._build_purchase_queue(class_names[i], 0) for i in range(len(specs))}
    level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
    board = B.BoardState(mode="competitive", heroes=heroes, zones={}, level_decks=level_decks)
    board.setup_quests(rng)

    _S.update(mode="competitive", board=board, class_names=class_names, controllers=controllers,
              labels=labels, purchase_queues=purchase_queues, rng=rng,
              human_count=sum(1 for c in controllers.values() if c == "human"), round_num=0)
    return _cmp_begin_round()


def _cmp_begin_round():
    """Start-of-round: resolve every AI hero's Town/Trainer visit instantly, queue up humans
    still standing in either. Mirrors run_competitive_chain's own Town/Trainer-phase loop
    (per-hero, independent, never contested) but splits out human turns into real pages.
    Dispatches per-hero on hero.position's own "town"/"trainer" marker (checkpointed
    2026-08-24, Class Trainer split from Town into its own turn-costing node type) rather than
    assuming Town -- a hero can arrive at either from a previous round's declared
    return_to_town/visit_trainer."""
    _S["round_num"] += 1
    board = _S["board"]
    town_pending = []
    for hero_idx, hero in enumerate(board.heroes):
        at_trainer = hero.position[1] == "trainer"
        if hero.position[1] not in ("town", "trainer"):
            continue
        if _S["controllers"][hero_idx] == "ai":
            if at_trainer:
                BE.enter_trainer(hero, _S["class_names"][hero_idx])
            else:
                BE.enter_town(hero, _S["class_names"][hero_idx], _S["strategy"], _S["rng"], _S["board"])
            while True:
                actions = BE.get_town_actions(hero, _S["purchase_queues"][hero_idx], _S["board"])
                buyable = next((a for a in actions if a["type"] == "buy"), None)
                leave_type = "leave_trainer" if at_trainer else "leave_town"
                chosen = buyable if buyable else next(a for a in actions if a["type"] == leave_type)
                if not BE.apply_town_action(hero, chosen, _S["purchase_queues"][hero_idx], _S["board"], _S["rng"]):
                    break
        else:
            town_pending.append(hero_idx)
    _S["cmp_town_pending"] = town_pending
    _S["cmp_town_entered"] = {}
    _S["cmp_trainer_entered"] = {}
    return _cmp_after_town()


def _cmp_after_town():
    if _S["cmp_town_pending"]:
        hero_idx = _S["cmp_town_pending"][0]
        _S["active_hero_idx"] = hero_idx
        at_trainer = _S["board"].heroes[hero_idx].position[1] == "trainer"
        _S["phase"] = "cmp_trainer" if at_trainer else "cmp_town"
        return redirect(url_for("cmp_trainer" if at_trainer else "cmp_town"))
    return _cmp_begin_declare()


@app.route("/cmp/town")
def cmp_town():
    hero_idx = _S["active_hero_idx"]
    hero = _S["board"].heroes[hero_idx]
    if not _S["cmp_town_entered"].get(hero_idx):
        setup = BE.enter_town(hero, _S["class_names"][hero_idx], _S["strategy"], _S["rng"], _S["board"])
        if setup["quests_completed"]:
            _flash(f"Turned in {setup['quests_completed']} quest(s).")
        _S["cmp_town_entered"][hero_idx] = True
    actions = BE.get_town_actions(hero, _S["purchase_queues"][hero_idx], _S["board"])
    return render_template("town.html", hero=hero, actions=list(enumerate(actions)), board=_S["board"], flash=_pop_flash(),
                            turn_label=_cmp_label(hero_idx), action_url=url_for("cmp_town_action"))


@app.route("/cmp/town/action", methods=["POST"])
def cmp_town_action():
    hero_idx = _S["active_hero_idx"]
    hero = _S["board"].heroes[hero_idx]
    actions = BE.get_town_actions(hero, _S["purchase_queues"][hero_idx], _S["board"])
    idx = int(request.form.get("idx", -1))
    if not (0 <= idx < len(actions)):
        return redirect(url_for("cmp_town"))
    still_in_town = BE.apply_town_action(hero, actions[idx], _S["purchase_queues"][hero_idx], _S["board"], _S["rng"])
    if not still_in_town:
        _S["cmp_town_pending"].pop(0)
        return _cmp_after_town()
    return redirect(url_for("cmp_town"))


@app.route("/cmp/trainer")
def cmp_trainer():
    """Competitive counterpart to /cmp/town -- checkpointed 2026-08-24, Class Trainer split
    from Town into its own turn-costing node type. Same shape as /trainer (solo), keyed by
    _S["active_hero_idx"] instead of a fixed hero 0."""
    hero_idx = _S["active_hero_idx"]
    hero = _S["board"].heroes[hero_idx]
    if not _S["cmp_trainer_entered"].get(hero_idx):
        setup = BE.enter_trainer(hero, _S["class_names"][hero_idx])
        if setup["mandatory_turn"]:
            _flash("You've been granted your mandatory Level 2 upgrade!")
        _S["cmp_trainer_entered"][hero_idx] = True
    actions = BE.get_town_actions(hero, _S["purchase_queues"][hero_idx], _S["board"])
    return render_template("town.html", hero=hero, actions=list(enumerate(actions)), board=_S["board"], flash=_pop_flash(),
                            turn_label=_cmp_label(hero_idx), action_url=url_for("cmp_trainer_action"))


@app.route("/cmp/trainer/action", methods=["POST"])
def cmp_trainer_action():
    hero_idx = _S["active_hero_idx"]
    hero = _S["board"].heroes[hero_idx]
    actions = BE.get_town_actions(hero, _S["purchase_queues"][hero_idx], _S["board"])
    idx = int(request.form.get("idx", -1))
    if not (0 <= idx < len(actions)):
        return redirect(url_for("cmp_trainer"))
    still_at_trainer = BE.apply_town_action(hero, actions[idx], _S["purchase_queues"][hero_idx], _S["board"], _S["rng"])
    if not still_at_trainer:
        _S["cmp_town_pending"].pop(0)
        return _cmp_after_town()
    return redirect(url_for("cmp_trainer"))


def _cmp_begin_declare():
    """Every field hero (not in Town) submits one Travel declaration this round, in priority-
    token order -- AI resolves instantly via the SAME board_engine._choose_field_action the CLI
    and run_competitive_chain both already use; a human pauses on cmp_declare. Non-field heroes
    submit a harmless return_to_town no-op (matches advance_board's own contract: every hero in
    board.heroes needs an entry, not just field-active ones)."""
    board = _S["board"]
    field_idxs = [i for i, h in enumerate(board.heroes) if h.position[1] not in ("town", "trainer")]
    _S["cmp_field_idxs"] = field_idxs
    _S["cmp_quest_pools"] = {i: _current_quest_pool(board.heroes[i]) for i in field_idxs}
    _S["cmp_claimed_this_round"] = set()
    order = BE._priority_order(board)
    _S["cmp_declare_order"] = [i for i in order if i in field_idxs]
    for hero_idx in range(len(board.heroes)):
        if hero_idx not in field_idxs:
            still_town = board.heroes[hero_idx].position[1] == "town"
            BE.declare_for_hero(board, hero_idx,
                                 {"type": "return_to_town" if still_town else "visit_trainer"})
    return _cmp_process_declare_queue()


def _cmp_process_declare_queue():
    board = _S["board"]
    rng = _S["rng"]
    while _S["cmp_declare_order"]:
        hero_idx = _S["cmp_declare_order"][0]
        if _S["controllers"][hero_idx] == "ai":
            action = BE._choose_field_action(hero_idx, board, _S["class_names"], _S["cmp_quest_pools"],
                                              rng, _S["cmp_claimed_this_round"],
                                              purchase_queues=_S["purchase_queues"])
            if action["type"] == "declare_node":
                _S["cmp_claimed_this_round"].add(action["node_name"])
            BE.declare_for_hero(board, hero_idx, action)
            _S["cmp_declare_order"].pop(0)
            continue
        _S["active_hero_idx"] = hero_idx
        _S["phase"] = "cmp_declare"
        return redirect(url_for("cmp_declare"))
    return _cmp_begin_resolve()


@app.route("/cmp/declare")
def cmp_declare():
    hero_idx = _S["active_hero_idx"]
    hero = _S["board"].heroes[hero_idx]
    actions = BE.get_travel_actions(hero, _S["board"], _S["rng"])
    return render_template("travel.html", board=_S["board"], hero=hero, actions=list(enumerate(actions)), flash=_pop_flash(),
        turn_label=_cmp_label(hero_idx), action_url=url_for("cmp_declare_action"),
        declare_note="Declare your target for this round -- everyone's declarations resolve "
                     "together once all heroes have chosen.", map_data=_build_map_data(_S["board"], hero_idx),
        action_dict=_build_action_dict(actions), coords=_load_map_coords(),
    )


@app.route("/cmp/declare/action", methods=["POST"])
def cmp_declare_action():
    hero_idx = _S["active_hero_idx"]
    board = _S["board"]
    hero = board.heroes[hero_idx]
    actions = BE.get_travel_actions(hero, board, _S["rng"])
    idx = int(request.form.get("idx", -1))
    if not (0 <= idx < len(actions)):
        return redirect(url_for("cmp_declare"))
    action = actions[idx]
    if action["type"] == "declare_node":
        _S["cmp_claimed_this_round"].add(action["node_name"])
    BE.declare_for_hero(board, hero_idx, action)
    _S["cmp_declare_order"].pop(0)
    return _cmp_process_declare_queue()



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
    _S["cmp_resolve_order"] = [h for h in _S["cmp_field_idxs"] if h in _S["cmp_declarations_resolved"]]
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
    
    
    def _fill_stances(class_name):
        if class_name == "Warrior":
            return "G"
        return None
        
    i_dmg, d_dmg = PvP.resolve_duel(i_hero.class_name.title(), (i_plan, _fill_stances(i_hero.class_name.title())), d_hero.class_name.title(), (d_plan, _fill_stances(d_hero.class_name.title())))

    
    i_score = i_dmg + i_hero.max_hp + i_hero.tokens
    d_score = d_dmg + d_hero.max_hp + d_hero.tokens
    
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

    return _cmp_pvp_peace()

def _cmp_begin_resolve_OLD():
    """Once every hero has declared, resolve contested Nodes ONCE (BE._resolve_contested_
    declarations -- task #79, exactly so this doesn't redraw blind-redraw cards twice), then
    resolve each hero's action. AI resolves instantly; a human whose action needs combat
    (declare_node, or cross_border after its own reveal) pauses on cmp_scouted_pick/
    cmp_combat_plan with their FINAL (post-redraw) mob already known."""
    board = _S["board"]
    rng = _S["rng"]
    _S["cmp_declarations_resolved"] = BE._resolve_contested_declarations(board, rng)
    _S["cmp_resolve_order"] = [h for h in _S["cmp_field_idxs"] if h in _S["cmp_declarations_resolved"]]
    _S["cmp_results"] = {}
    _S["cmp_touched_zones"] = set()
    return _cmp_process_resolve_queue()


def _cmp_process_resolve_queue():
    board = _S["board"]
    rng = _S["rng"]
    class_names = _S["class_names"]
    while _S["cmp_resolve_order"]:
        hero_idx = _S["cmp_resolve_order"][0]
        hero = board.heroes[hero_idx]
        action = _S["cmp_declarations_resolved"][hero_idx]
        zone_or_border, _node = hero.position
        if isinstance(zone_or_border, int) and action["type"] in ("declare_node", "use_scroll", "use_smoke_bomb"):
            _S["cmp_touched_zones"].add((zone_or_border, BE.TIER_TO_LEVEL[M.ZONE_TIER[zone_or_border]]))

        if _S["controllers"][hero_idx] == "ai" or action["type"] not in ("declare_node", "cross_border"):
            result = BE.apply_travel_action(hero, action, class_names[hero_idx], board, rng,
                                             M.RISK_TOLERANCE_BASE, True, defer_zone_discard=True)
            if result.get("outcome") == "scouted_pull_reveal":
                picked = rng.choice(result["candidates"])
                result = BE.resolve_border_crossing(hero, class_names[hero_idx], result["border_name"],
                                                      result["target_zone"], picked, rng,
                                                      M.RISK_TOLERANCE_BASE, True)
            if result.get("outcome") == "died":
                BE.apply_competitive_death_post_processing(hero, _S["cmp_quest_pools"][hero_idx])
            _S["cmp_results"][hero_idx] = result
            _S["cmp_resolve_order"].pop(0)
            continue

        # human, needs a page
        _S["active_hero_idx"] = hero_idx
        if action["type"] == "cross_border":
            level_deck = board.level_decks[BE.TIER_TO_LEVEL[M.ZONE_TIER[action["target_zone"]]]]
            candidates = BE.reveal_scouted_pull_candidates(level_deck, rng)
            _S["pending_kind"] = "cmp_cross_border"
            _S["pending_border"] = dict(candidates=candidates, border_name=action["border_name"],
                                         target_zone=action["target_zone"])
            _S["phase"] = "cmp_scouted_pick"
            return redirect(url_for("cmp_scouted_pick"))

        mod = M.CARD_SOURCE[class_names[hero_idx]]
        hand = rng.choice(mod.ALL_HANDS)
        _S["pending_kind"] = "cmp_declare_node"
        _S["pending_action"] = action
        _S["pending_hand"] = hand
        _S["phase"] = "cmp_combat_plan"
        return redirect(url_for("cmp_combat_plan"))
    return _cmp_round_done()


@app.route("/cmp/scouted_pick")
def cmp_scouted_pick():
    hero_idx = _S["active_hero_idx"]
    return render_template("scouted_pick.html", candidates=_S["pending_border"]["candidates"],
                            turn_label=_cmp_label(hero_idx), action_url=url_for("cmp_scouted_pick_choose"))


@app.route("/cmp/scouted_pick/choose", methods=["POST"])
def cmp_scouted_pick_choose():
    hero_idx = _S["active_hero_idx"]
    class_name = _S["class_names"][hero_idx]
    pick = request.form.get("pick")
    candidates = _S["pending_border"]["candidates"]
    mob_name = candidates[0] if pick == "0" else candidates[1]

    mod = M.CARD_SOURCE[class_name]
    hand = _S["rng"].choice(mod.ALL_HANDS)
    _S["pending_action"] = dict(_S["pending_border"], mob_name=mob_name)
    _S["pending_hand"] = hand
    _S["phase"] = "cmp_combat_plan"
    return redirect(url_for("cmp_combat_plan"))


@app.route("/cmp/combat_plan")
def cmp_combat_plan():
    hero_idx = _S["active_hero_idx"]
    hero = _S["board"].heroes[hero_idx]
    class_name = _S["class_names"][hero_idx]
    hand = _S["pending_hand"]
    mob_name = _S["pending_action"]["mob_name"]
    pattern, mob_hp = M._pattern_hp_for_mob(class_name, mob_name)
    return render_template(
        "combat_plan.html", class_name=class_name, mob_name=mob_name,
        pattern=list(enumerate(pattern)), mob_hp=mob_hp, hero=hero,
        hand_options=_hand_options(class_name, hand), has_stance=M.HAS_STANCE[class_name],
        pending_kind=_S["pending_kind"], flash=_pop_flash(),
        turn_label=_cmp_label(hero_idx), action_url=url_for("cmp_combat_plan_submit"),
    )


@app.route("/cmp/combat_plan/submit", methods=["POST"])
def cmp_combat_plan_submit():
    hero_idx = _S["active_hero_idx"]
    hero = _S["board"].heroes[hero_idx]
    class_name = _S["class_names"][hero_idx]
    board = _S["board"]
    rng = _S["rng"]
    hand = _S["pending_hand"]
    kind = _S["pending_kind"]
    pending = _S["pending_action"]

    sequence, stance_sequence, error = _parse_combat_plan(request.form, class_name, hand)
    if error is None:
        error = _validate_sequence(class_name, hand, pending["mob_name"], hero.hp, sequence, stance_sequence)
    if error:
        _flash(error)
        return redirect(url_for("cmp_combat_plan"))
    decide_fn = make_sequence_decide_fn(sequence, stance_sequence)

    if kind == "cmp_declare_node":
        result = BE.apply_travel_action(hero, pending, class_name, board, rng,
                                         M.RISK_TOLERANCE_BASE, True, defer_zone_discard=True,
                                         decide_fn=decide_fn, hand=hand)
    else:  # cmp_cross_border
        result = BE.resolve_border_crossing(hero, class_name, pending["border_name"], pending["target_zone"],
                                             pending["mob_name"], rng, M.RISK_TOLERANCE_BASE, True,
                                             decide_fn=decide_fn, hand=hand)

    if result.get("outcome") == "died":
        BE.apply_competitive_death_post_processing(hero, _S["cmp_quest_pools"][hero_idx])

    _S["pending_kind"] = None
    _S["pending_action"] = None
    _S["pending_hand"] = None
    _S["pending_border"] = None
    _S["cmp_results"][hero_idx] = result
    _S["cmp_resolve_order"].pop(0)
    return _cmp_process_resolve_queue()


def _cmp_round_done():
    board = _S["board"]
    for zone_id, level in _S["cmp_touched_zones"]:
        B.discard_zone(board, zone_id, level)
    board.priority_token_holder = (board.priority_token_holder + 1) % len(board.heroes)
    board.pending_declarations.clear()
    _S["phase"] = "cmp_round_result"
    return redirect(url_for("cmp_round_result"))


@app.route("/cmp/round_result")
def cmp_round_result():
    board = _S["board"]
    rows = []
    for hero_idx, hero in enumerate(board.heroes):
        result = _S["cmp_results"].get(hero_idx, {})
        rows.append(dict(
            label=_cmp_label(hero_idx), outcome=result.get("outcome", "-"),
            hp=f"{hero.hp:.0f}/{hero.max_hp:.0f}", gold=hero.gold, xp=hero.xp,
            position=hero.position[0],
        ))
    return render_template("cmp_round_result.html", round_num=_S["round_num"], rows=rows)


@app.route("/cmp/round_result/continue", methods=["POST"])
def cmp_round_result_continue():
    return _cmp_begin_round()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5152)
    parser.add_argument("--localhost", action="store_true", help="Bind to 127.0.0.1 only")
    args = parser.parse_args()
    host = "127.0.0.1" if args.localhost else "0.0.0.0"
    print(f"\n  QUEST board playtest\n  Open http://localhost:{args.port} in your browser\n")
    app.run(host=host, debug=False, port=args.port)


if __name__ == "__main__":
    main()
