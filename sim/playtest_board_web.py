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
# Keyed by (mechanical_name, level), not by flavor name -- Bruiser/Raider/Scout aren't
# remixed at Level 2, so they keep the SAME mechanical_name across both levels while still
# needing different flavor text (pirate vs. Sunsworn) -- mechanical_name alone would collide
# and silently drop one level's entry. Grunt/Enforcer/Ambusher's Level 2 entries carry their
# real dealt name (Grunt_L2 etc, see leveling_validation.LEVEL2_STANDARD) as mechanical_name,
# so this scheme handles both remixed and non-remixed mobs the same way.
_MOBS_TEXT = {}
try:
    with open(os.path.join(os.path.dirname(__file__), "../pnp-tool/src/mobs_text.json"), "r", encoding="utf-8") as f:
        _MOBS_TEXT = {(m["mechanical_name"], m["level"]): m for m in json.load(f)}
except Exception as e:
    print(f"Warning: could not load mobs_text.json: {e}")

import argparse
import random
import pickle

SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "savegame.pkl")

from flask import Flask, redirect, render_template, request, url_for

import board_engine as BE
import board_state as B
import combat_engine as E
import macro_sim as M
import leveling_validation as LV
import sim_pvp as PvP
import class_mob_matchup_chart as MC
import equipment_data as EQ
import spice_data as SD
from board_state import HeroBoardState

app = Flask(__name__, template_folder="playtest_board_web_templates")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True

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

def _get_equip_text(recipe):
    base = recipe["base"]
    rider = recipe["rider"]
    if rider == "honed": return "+2 DMG" if "2-Hander" in base or "Staff" in base else "+1 DMG"
    elif rider == "pierce": return "Ignore up to 2 enemy block."
    elif rider == "blessed": return "+1 Heal."
    elif rider == "greater_blessed": return "+2 Heal."
    elif rider == "ruthless": return "If this attack is lethal, prevent all damage taken this round."
    elif rider == "sunder": return "+1 DMG this round and all subsequent rounds of this pull."
    elif rider == "reinforced": return "+3 Block." if "Heavy" in base else ("+2 Block." if "Medium" in base else "+1 Block.")
    elif rider == "elusive": return "Evade one melee attack this round."
    elif rider == "thorns": return f"Deal {3 if 'Heavy' in base else 2} DMG, unless At Range this round."
    elif rider == "persistent":
        blk = 3 if "Heavy" in base else (2 if "Medium" in base else 1)
        return f"+{blk} Block this round, and +{blk} Block next round."
    return ""

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


_ROLE_ICONS = {
    'grunt': '🛡️',
    'bruiser': '⏳',
    'enforcer': '💥',
    'raider': '⚔️',
    'ambusher': '🗡️',
    'scout': '🎯',
    'bulwark': '🏰',
    'berserker': '🩸',
    'warlord': '👑',
}


def get_role_icon(role_name):
    if not role_name:
        return ''
    key = str(role_name).replace('_loot', '').replace('_l2', '').replace('_L2', '').lower()
    return _ROLE_ICONS.get(key, '⚔️')


def get_quest_progress(hero, quest):
    pool = M.LEVEL2_QUESTS if hero.xp >= M.LEVEL2_XP_THRESHOLD else M.QUESTS
    if quest not in pool:
        if quest in M.LEVEL2_QUESTS: pool = M.LEVEL2_QUESTS
        elif quest in M.QUESTS: pool = M.QUESTS
        else: return ""
    count = M._accessible_count(hero.bag, hero.locked, quest)
    req = pool[quest]["required"]
    return f" ({count}/{req} Collected)"


def get_item_icon(item_name):
    icons = {
        "red_quest": "🔴", "green_quest": "🟢", "blue_quest": "🔵",
        "Snap-Root": "🌿", "Crag-Iron": "🪨", "Scavenged Pelt": "🦡",
        "River-Mint": "🌿", "Sun-Copper": "🪨", "Bristle-Pelt": "🦡",
        "food": "🍖", "potion": "🧪", "smoke_bomb": "💨",
        "whetstone": "🪨", "preserving_charm": "🧿", "scroll_of_vanquishing": "📜",
        "tarnished_silverware": "🍴", "intact_pelt": "🦊", "flawless_gemstone": "💎"
    }
    return icons.get(item_name, "📦")

ITEMS_WITH_ART = {"food", "potion", "preserving_charm", "scroll_of_vanquishing", "smoke_bomb"}

def has_item_art(item_name):
    return (item_name or "").lower() in ITEMS_WITH_ART

def get_hero_upgrades(hero):
    if not hero:
        return []
    class_name = hero.class_name
    upgrades = []
    class_cards = _CARDS_TEXT.get(class_name, {})
    if class_name in M.LEVEL2_MANDATORY and ("mandatory" in hero.acquired or hero.xp >= 6):
        _, old_name, new_name, new_card = M.LEVEL2_MANDATORY[class_name]
        cdata = class_cards.get(new_name, {})
        upgrades.append({
            "tier": "Level 2 Trait",
            "old_name": old_name,
            "new_name": new_name,
            "text": cdata.get("text", ""),
            "badges": cdata.get("badges", {}),
            "card_data": cdata
        })
    if class_name in M.LEVEL2_PURCHASED_ORDER:
        for i, (old_name, new_name, new_card) in enumerate(M.LEVEL2_PURCHASED_ORDER[class_name]):
            if f"skill_{i}" in hero.acquired:
                cdata = class_cards.get(new_name, {})
                upgrades.append({
                    "tier": f"Talent {i+1}",
                    "old_name": old_name,
                    "new_name": new_name,
                    "text": cdata.get("text", ""),
                    "badges": cdata.get("badges", {}),
                    "card_data": cdata
                })
    return upgrades

def get_hero_deck(hero):
    if not hero:
        return []
    class_name = hero.class_name
    mod = M.CARD_SOURCE.get(class_name)
    if not mod or not hasattr(mod, "DECK"):
        return []
    swaps = BE._level2_swaps_for(class_name, hero.acquired)
    class_cards = _CARDS_TEXT.get(class_name, {})
    deck = []
    for c in mod.DECK:
        if c in swaps:
            new_name, _ = swaps[c]
            cdata = class_cards.get(new_name, {})
            deck.append({
                "name": new_name,
                "is_upgraded": True,
                "replaces": c,
                "text": cdata.get("text", ""),
                "badges": cdata.get("badges", {}),
                "data": cdata
            })
        else:
            cdata = class_cards.get(c, {})
            deck.append({
                "name": c,
                "is_upgraded": False,
                "replaces": None,
                "text": cdata.get("text", ""),
                "badges": cdata.get("badges", {}),
                "data": cdata
            })
    return deck

@app.context_processor
def inject_globals():
    return dict(
        quest_locations={v[1]: k.replace('_', ' ').title() for k, v in M.NODES.items()},
        town_names={
            1: "The Smugglers' Roost",
            2: "Port Ironguard",
            3: "The Vanguard Camp",
            4: "The Vanguard Camp"
        },
        get_class_matchup=get_class_matchup,
        get_mob_flavor=lambda mob_name, level: (
            {"name": SD.get_spice_display_name(mob_name), "tier": "Spice Combat" if SD.is_spice_combat(mob_name) else "Spice Event", "type": "melee"}
            if SD.is_spice(mob_name) else _MOBS_TEXT.get((mob_name.replace("_loot", ""), level), {})
        ),
        get_item_name=get_item_name,
        get_item_count=get_item_count,
        get_item_icon=get_item_icon,
        has_item_art=has_item_art,
        get_quest_progress=get_quest_progress,
        get_recipes=EQ.get_recipes_for_class,
        get_equip_text=_get_equip_text,
        get_hero_upgrades=get_hero_upgrades,
        get_hero_deck=get_hero_deck,
        get_role_icon=get_role_icon
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


def make_sequence_decide_fn(sequence, stance_sequence=None, equipment_sequence=None):
    """Web-facing decide_fn -- replays a human's pre-submitted full card ordering, Warrior
    stance choice, and equipment activation choices instead of computing anything live."""
    def decide_fn(state, actions):
        variant = sequence[state.round_num]
        stance = stance_sequence[state.round_num] if stance_sequence else None
        target_eq = equipment_sequence[state.round_num] if equipment_sequence else []

        # 1. Look for legal action matching variant, stance, and exact equipment activations
        for action in actions:
            if (action["variant"] == variant and 
                action.get("stance") == stance and 
                action.get("legal") and 
                sorted(action.get("equipment", [])) == sorted(target_eq)):
                return action

        # 2. Fallback if specific equipment was unavailable or omitted
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
        if isinstance(z, int) and (n == "town" or n is None):
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
        gathering_item = board.zones[z].gathering_tokens.get(node_name) if z in board.zones else None
        heroes_here = [i for i, h in enumerate(board.heroes) if h.position == (z, node_name)]
        zones[z]["nodes"].append({"id": node_name, "mob": mob, "gathering_item": gathering_item, "heroes": heroes_here})
        
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


def _hand_options(class_name, hand, hero=None):
    """List of (hand_idx, card_name, variant, label, dict_json) for every selectable option in a hand --"""
    import condensed_necromancer as N
    import json
    options = []
    class_data = _CARDS_TEXT.get(class_name, {})
    swaps = BE._level2_swaps_for(class_name, hero.acquired) if hero else {}
    for i, card_name in enumerate(hand):
        card_data = dict(class_data.get(card_name, {}))
        for old_c, (new_c, _) in swaps.items():
            if new_c == card_name:
                card_data["is_upgraded"] = True
                card_data["replaces"] = old_c
                break
        if class_name == "necromancer" and card_name == N.BONEGUARD_OFFERING:
            options.append((i, card_name, N.BONEGUARD_OFFERING, card_name, json.dumps(card_data)))
            options.append((i, card_name, N.BONEGUARD_OFFERING_BOOSTED, f"{card_name} (Boosted)", json.dumps(card_data)))
        else:
            options.append((i, card_name, card_name, card_name, json.dumps(card_data)))
    return options


def _parse_combat_plan(form, class_name, hand, hero=None):
    """Parses the combat_plan form into (sequence, stance_sequence, equipment_sequence, error). Each round field is
    'hand_idx|variant'; validates the 3 rounds use 3 DIFFERENT hand slots (a hand card, once
    played, leaves the hand -- see combat_engine._remaining_hand) before ever touching
    combat_engine, so an invalid submission bounces back to the same page with a message
    instead of raising deep inside the resolution call."""
    used_idxs = set()
    sequence = []
    for round_num in range(3):
        raw = form.get(f"round_{round_num}", "")
        if "|" not in raw:
            return None, None, None, f"Round {round_num + 1} needs a card chosen."
        idx_s, variant = raw.split("|", 1)
        try:
            idx = int(idx_s)
        except ValueError:
            return None, None, None, f"Round {round_num + 1}: invalid submission."
        if idx in used_idxs or not (0 <= idx < len(hand)):
            return None, None, None, f"Round {round_num + 1}: each hand card can only be played once."
        used_idxs.add(idx)
        sequence.append(variant)
    stance_sequence = None
    if M.HAS_STANCE[class_name]:
        stance = form.get("stance")
        if stance not in ("G", "C"):
            return None, None, None, "Choose a stance (Guardian or Crusader)."
        stance_sequence = [stance] * 3

    equipment_sequence = [[], [], []]
    if hero and hero.equipment:
        for slot in hero.equipment.keys():
            if slot in hero.equipment_used:
                continue
            choice = form.get(f"equip_{slot}", "none")
            if choice in ("0", "1", "2"):
                equipment_sequence[int(choice)].append(slot)

    return sequence, stance_sequence, equipment_sequence, None


def _normalize_hand(hand, class_name, acquired):
    """If hero has acquired Level 2 upgrades, replaces any old Level 1 cards in hand with their
    upgraded names so planning and execution match."""
    if not hand:
        return hand
    swaps = BE._level2_swaps_for(class_name, acquired)
    if not swaps:
        return hand
    return tuple(swaps[c][0] if c in swaps else c for c in hand)


def _draw_hero_hand(hero, class_name, rng):
    """Draws a random hand for the hero from their current deck (respecting Level 2 upgrades)."""
    mod = M.CARD_SOURCE[class_name]
    swaps = BE._level2_swaps_for(class_name, hero.acquired)
    with LV.leveled_kit(mod, swaps):
        hand = rng.choice(mod.ALL_HANDS)
    if getattr(hero, "reserved_card", None):
        reserved = hero.reserved_card
        hero.reserved_card = None
        if reserved not in hand:
            hand_list = list(hand)
            hand_list[0] = reserved
            hand = tuple(hand_list)
    return hand


def _validate_sequence(class_name, hand, mob_name, hero_hp, sequence, stance_sequence, equipment_sequence=None, hero=None):
    """Dry-runs the submitted sequence through combat_engine directly (a throwaway PullState,
    never touching the real hero/board) before committing to it for real -- combat resolution
    is fully deterministic given hand+mob+sequence (no RNG anywhere in get_legal_actions/
    apply_action, the same property that lets best_line_for_hand brute-force it), so this is
    cheap and catches a conditionally-illegal card (e.g. Warrior's Execute, only legal below
    50% mob HP) before it wastes the player's real turn instead of crashing mid-resolution.
    Returns None if the whole sequence is legal round-by-round, else an error string."""
    mod = M.CARD_SOURCE[class_name]
    swaps = BE._level2_swaps_for(class_name, hero.acquired) if hero else {}
    with LV.leveled_kit(mod, swaps):
        pattern, mob_hp = M._pattern_hp_for_mob(class_name, mob_name)
        state = E.new_pull_with_hp(class_name, mob_name, hand, pattern, mob_hp, hero_hp,
                                   equipment=hero.equipment if hero else None,
                                   equipment_used=set(hero.equipment_used) if hero else None)
        decide_fn = make_sequence_decide_fn(sequence, stance_sequence, equipment_sequence)
        try:
            while state.outcome is None:
                actions = E.get_legal_actions(state)
                action = decide_fn(state, actions)
                state = E.apply_action(state, action)
            return None
        except ValueError as e:
            return (f"That plan isn't legal: {e}. Some cards (like a Warrior's Execute) are only "
                    f"playable once the mob is low enough -- try a different order.")


def _build_combat_log(class_name, hand, mob_name, hero_hp, sequence, stance_sequence, equipment_sequence=None, hero=None):
    """Same dry-run shape as _validate_sequence (a throwaway PullState, never the real hero) --
    called only after _validate_sequence has already confirmed the plan is legal, so this one
    never raises. Reconstructs a round-by-round display log purely from combat_engine's own
    get_legal_actions/apply_action output (dmg_dealt, dmg_taken, block, heal, resulting_hp,
    resulting_mob_hp) -- never recomputes or approximates any of it. Safe to run as a SEPARATE
    pass from the real resolution that follows it (rather than trying to extract a log from
    that real call) because combat has zero RNG once hand+mob+sequence are fixed -- this dry
    run is guaranteed to produce numbers identical to the real one, the same determinism
    _validate_sequence already relies on. Returns (rows, final_outcome)."""
    mod = M.CARD_SOURCE[class_name]
    swaps = BE._level2_swaps_for(class_name, hero.acquired) if hero else {}
    with LV.leveled_kit(mod, swaps):
        pattern, mob_hp = M._pattern_hp_for_mob(class_name, mob_name)
        state = E.new_pull_with_hp(class_name, mob_name, hand, pattern, mob_hp, hero_hp,
                                   equipment=hero.equipment if hero else None,
                                   equipment_used=set(hero.equipment_used) if hero else None)
        decide_fn = make_sequence_decide_fn(sequence, stance_sequence, equipment_sequence)
        rows = []
        while state.outcome is None:
            actions = E.get_legal_actions(state)
            action = decide_fn(state, actions)
            round_pattern = pattern[state.round_num]
            state = E.apply_action(state, action)
            eq_names = []
            for s in action.get("equipment", []):
                if hero and hero.equipment and s in hero.equipment and isinstance(hero.equipment[s], dict):
                    eq_names.append(hero.equipment[s].get("name", s))
                else:
                    eq_names.append(s.title())
            rows.append(dict(
                round_num=state.round_num, card=action["card"],
                variant=action["variant"] if action["variant"] != action["card"] else None,
                stance=action.get("stance"),
                equipment=eq_names,
                mob_atk=round_pattern[0], mob_blk=round_pattern[1],
                raw_dmg=action["raw_dmg"], block=action["block"], heal=action["heal"],
                dmg_dealt=action["dmg_dealt"], dmg_taken=action["dmg_taken"],
                hp_after=state.hero_hp, mob_hp_after=state.mob_hp_remaining,
            ))
        return rows, state.outcome


def _mob_level_for_pending(pending):
    """Which Level (1 or 2) the dealt mob in `pending` belongs to, for get_mob_flavor's
    (mechanical_name, level) lookup -- a Node-declared/recovery mob's Zone comes from
    NODE_ZONE, a Border-crossing/Scouted-Pull mob's from its own target_zone (no node_name
    exists for those, see get_travel_actions' cross_border action shape)."""
    zone_id = M.NODE_ZONE[pending["node_name"]] if "node_name" in pending else pending["target_zone"]
    return BE.TIER_TO_LEVEL[M.ZONE_TIER[zone_id]]


def _outcome_message(kind, result, mob_level=None):
    outcome = result.get("outcome")
    mob = result.get("mob_name", "the foe").replace("_loot", "")
    if SD.is_spice(mob):
        mob = SD.get_spice_display_name(mob)
    elif mob_level is not None:
        mob = _MOBS_TEXT.get((mob, mob_level), {}).get("name", mob)

    msg = f"Outcome: {outcome}"
    if outcome == "win":
        if result.get("is_spice"):
            msg = f"Victory at {mob}!"
        else:
            msg = f"Victory over {mob}! +1 Gold."
    elif outcome == "flee":
        msg = f"Survived but didn't finish off {mob} -- no loot this time."
    elif outcome == "no_room":
        msg = f"Won against {mob}, but your Bag had no room for its Quest Loot!"
    elif outcome == "died":
        msg = f"You fell to {mob}..."
        
    if "gathering_item" in result:
        msg += f" Gathered {result['gathering_item']}."
    if "gathering_item_pending" in result:
        msg += f" Bag full! {result['gathering_item_pending']} is waiting for you to make room."
        
    if "mob_drops" in result:
        drops = [d.replace('_', ' ').title() for d in result['mob_drops']]
        msg += f" Looted {', '.join(drops)}!"
    if "mob_drops_pending" in result:
        drops = [d.replace('_', ' ').title() for d in result['mob_drops_pending']]
        msg += f" Bag full! {', '.join(drops)} waiting for you to make room."
        
    return msg


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    reset_session()
    has_save = os.path.exists(SAVE_FILE)
    return render_template("setup.html", classes=list(M.CARD_SOURCE.keys()), has_save=has_save)


def _new_hero(class_name, rng):
    mod = M.CARD_SOURCE[class_name]
    max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
    start_tokens = 0
    if class_name in ("rogue", "warrior", "necromancer"):
        start_tokens = 2
    elif class_name in ("ranger", "runecaster"):
        start_tokens = 1
        
    hero = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(1, "town"),
                           bag=[None] * M.BAG_SIZE, locked=[False] * M.BAG_SIZE, tokens=start_tokens)
    M._add_food(hero.bag, hero.locked)
    if class_name in M.LEVEL2_PURCHASED_ORDER:
        hero.skill_purchase_order = list(range(len(M.LEVEL2_PURCHASED_ORDER[class_name])))
        rng.shuffle(hero.skill_purchase_order)
    return hero


@app.route("/bag/discard/<int:idx>", methods=["POST"])
def discard_bag_item(idx):
    if not _S.get("board") or not _S["board"].heroes:
        return redirect(url_for("index"))
    hero = _S["board"].heroes[_S["active_hero_idx"]] if _S["mode"] == "solo" else _S["board"].heroes[_S["cmp_declare_order"][0] if _S.get("cmp_declare_order") else 0]
    if 0 <= idx < len(hero.bag) and not hero.locked[idx]:
        if hero.bag[idx] in ("food", "food_filler"):
            M._remove_food(hero.bag, idx)
        else:
            hero.bag[idx] = None
    return redirect(request.referrer or url_for("travel"))

@app.route("/bag/organize", methods=["POST"])
def organize_bag():
    if not _S.get("board") or not _S["board"].heroes:
        return redirect(url_for("index"))
    hero = _S["board"].heroes[_S["active_hero_idx"]] if _S["mode"] == "solo" else _S["board"].heroes[_S["cmp_declare_order"][0] if _S.get("cmp_declare_order") else 0]
    M._organize_bag(hero.bag, hero.locked)
    return redirect(request.referrer or url_for("travel"))

@app.route("/bag/swap", methods=["POST"])
def swap_bag():
    if not _S.get("board") or not _S["board"].heroes:
        return redirect(url_for("index"))
    hero = _S["board"].heroes[_S["active_hero_idx"]] if _S["mode"] == "solo" else _S["board"].heroes[_S["cmp_declare_order"][0] if _S.get("cmp_declare_order") else 0]
    try:
        from_idx = int(request.form.get("from_idx", -1))
        to_idx = int(request.form.get("to_idx", -1))
        M._swap_bag_slots(hero.bag, hero.locked, from_idx, to_idx)
    except Exception as e:
        app.logger.warning(f"Failed to swap bag slots: {e}")
    return redirect(request.referrer or url_for("travel"))

@app.route("/bag/discard_pending/<int:idx>", methods=["POST"])
def discard_pending_item(idx):
    if not _S.get("board") or not _S["board"].heroes:
        return redirect(url_for("index"))
    hero = _S["board"].heroes[_S["active_hero_idx"]] if _S["mode"] == "solo" else _S["board"].heroes[_S["cmp_declare_order"][0] if _S.get("cmp_declare_order") else 0]
    if 0 <= idx < len(hero.pending_loot):
        hero.pending_loot.pop(idx)
    return redirect(request.referrer or url_for("travel"))

@app.route("/bag/claim_pending", methods=["POST"])
def claim_pending_items():
    if not _S.get("board") or not _S["board"].heroes:
        return redirect(url_for("index"))
    hero = _S["board"].heroes[_S["active_hero_idx"]] if _S["mode"] == "solo" else _S["board"].heroes[_S["cmp_declare_order"][0] if _S.get("cmp_declare_order") else 0]
    leftover = []
    for item in hero.pending_loot:
        if M._bag_has_room(hero.bag, hero.locked):
            M._add_item(hero.bag, hero.locked, item)
        else:
            leftover.append(item)
    hero.pending_loot = leftover
    if leftover:
        _flash("Not enough room in bag for all pending items.")
    return redirect(request.referrer or url_for("travel"))


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
    loot_decks = {1: B.LootDeck.new(1, rng), 2: B.LootDeck.new(2, rng)}
    board = B.BoardState(mode="solo", heroes=[hero], zones={}, level_decks=level_decks, loot_decks=loot_decks)
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
        satchel_count = M._accessible_count(hero.bag, hero.locked, "couriers_satchel")
        if satchel_count > 0:
            zone_id = hero.position[0] if isinstance(hero.position, tuple) else 1
            gain = (4 + SD.zone_level_for_zone(zone_id)) * satchel_count
            hero.gold += gain
            hero.tokens += satchel_count
            M._remove_loot(hero.bag, hero.locked, "couriers_satchel", satchel_count)
            _flash(f"Delivered {satchel_count} Courier's Satchel: +{gain} Gold, +{satchel_count} Bounty Credit!")
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
    if SD.is_spice_event(mob_name):
        _S["pending_kind"] = "recovery_spice_event"
        _S["pending_action"] = {"node_name": node_name, "mob_name": mob_name}
        _S["phase"] = "event_resolve"
        return redirect(url_for("event_resolve"))
    hand = _draw_hero_hand(hero, class_name, rng)
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
        mob_name = action.get("mob_name")
        if SD.is_spice_event(mob_name):
            _S["pending_kind"] = "spice_event"
            _S["pending_action"] = action
            _S["phase"] = "event_resolve"
            return redirect(url_for("event_resolve"))
        hand = _draw_hero_hand(hero, class_name, rng)
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
        _flash(_outcome_message("instant", result, mob_level=_mob_level_for_pending(action)))
    elif result.get("outcome") == "healed":
        _flash(f"HP now {hero.hp:.0f}/{hero.max_hp:.0f}.")
    return redirect(url_for("travel"))


# ---------------------------------------------------------------------------
# Spice Event Resolution
# ---------------------------------------------------------------------------

@app.route("/event/resolve")
def event_resolve():
    if _S.get("board") is None or not _S.get("pending_action"):
        return redirect(url_for("travel"))
    board = _S["board"]
    is_cmp = (board.mode == "competitive")
    hero_idx = _S.get("active_hero_idx", 0) if is_cmp else 0
    hero = board.heroes[hero_idx]
    action = _S["pending_action"]
    mob_name = action["mob_name"].replace("_loot", "")
    zone_id = hero.position[0] if isinstance(hero.position, tuple) else 1
    zone_lvl = SD.zone_level_for_zone(zone_id)
    display_name = SD.get_spice_display_name(mob_name)
    level = BE.TIER_TO_LEVEL[M.ZONE_TIER.get(zone_id, "tier_1")]
    level_consumable = "Whetstone" if level == 1 else "Preserving Charm"

    flavor = ""
    badge = "Wilderness Encounter"
    choices = []

    if mob_name == "sacred_well":
        badge = "Ancient Shrine"
        flavor = "Crystal-clear water pools inside moss-covered flagstones, humming with celestial resonance."
        choices = [
            {"key": "well_safe", "title": "Drink Deep", "desc": "Safely restore 2 HP immediately.", "tag": "Safe (+2 HP)"},
            {"key": "well_gamble", "title": "Commune with the Depths", "desc": "Reveal 4 class cards. If any contain Heal or Block, restore 4 HP. Otherwise, 0 HP.", "tag": "Gamble (+4 HP or 0)"},
        ]
    elif mob_name == "forgotten_passage":
        badge = "Secret Route"
        flavor = "An overgrown stone archway cuts beneath the mountain spine, bypassing patrolled borders."
        target_zone = 2 if zone_id == 1 else (1 if zone_id == 2 else (4 if zone_id == 3 else 3))
        choices = [
            {"key": f"passage_{target_zone}", "title": f"Bypass to Zone {target_zone}", "desc": f"Slip through the tunnel directly into Zone {target_zone} with no border toll or mob encounter.", "tag": f"Free Travel -> Zone {target_zone}"},
        ]
    elif mob_name == "dead_scouts_map":
        badge = "Relic Discovery"
        flavor = "Clutched in the gauntlet of a fallen surveyor lies a parchment charting hidden monster caches."
        choices = [
            {"key": "take_map", "title": "Take the Map", "desc": "Hold the map. Your next combat win grants 1 bonus Level Loot card.", "tag": "Bonus Loot on Win"},
        ]
    elif mob_name == "ruined_watchtower":
        badge = "Vantage Point"
        flavor = "From this broken battlement, the valley stretches out, revealing roaming monsters and shifting threats."
        choices = [
            {"key": "scout_horizon", "title": "Survey the Valley", "desc": "Discard all other cards in this zone and deal 3 fresh cards from the zone deck.", "tag": "Redeal Zone"},
        ]
    elif mob_name == "wandering_hermit":
        badge = "Enigmatic Mystic"
        flavor = "An ascetic sage sits beside a stone cairn, carving protective bone runes against doom."
        cost = 2 + zone_lvl
        choices = [
            {"key": "hermit_ward", "title": "Purchase Bone Ward", "desc": f"Pay {cost} Gold. On your next death, Bag does not lock, no corpse retrieval needed, 1-stage quest decay.", "tag": f"-{cost} Gold (Ward)"},
            {"key": "hermit_pass", "title": "Politely Decline", "desc": "Bow respectfully and continue your journey without buying the ward.", "tag": "Free"},
        ]
    elif mob_name == "runic_monolith":
        badge = "Arcane Wonder"
        flavor = "Ancient glyphs pulse with crimson light along an obsidian slab, sharpening your martial reflexes."
        choices = [
            {"key": "attune_rune", "title": "Attune with the Monolith", "desc": "Look into your martial arts and reserve 1 card face-up for your next combat hand.", "tag": "Guaranteed Card"},
        ]
    elif mob_name == "abandoned_hearth":
        badge = "Sheltered Campsite"
        flavor = "Cold embers lie in an alcove sheltered from wind and beasts. A rest here will knit deep wounds."
        choices = [
            {"key": "field_rest", "title": "Make Camp & Rest", "desc": "Restore HP to full in the wilderness without trip decay or returning to Town.", "tag": "Full HP Restore"},
        ]
    elif mob_name == "masters_forge":
        badge = "Field Smithing"
        flavor = "A master smith's anvil and roaring bellows sit untended, ready to shape steel without a workshop fee."
        choices = [
            {"key": "field_smith", "title": "Field Smithing", "desc": "Craft 1 equipment recipe from materials in your bag with 0 forge fee (or salvage +1 Crag-Iron).", "tag": "0 Gold Forge Fee"},
        ]
    elif mob_name == "wandering_peddler":
        badge = "Wilderness Merchant"
        flavor = "A heavily laden merchant packs sundries and elixirs, eager to barter far from Town taxes."
        choices = [
            {"key": "peddler_potion", "title": "Buy Healing Potion", "desc": "Purchase 1 Healing Potion for 3 Gold.", "tag": "3 Gold"},
            {"key": "peddler_food", "title": "Buy Field Ration", "desc": "Purchase 1 Food Ration for 2 Gold.", "tag": "2 Gold"},
            {"key": "peddler_sell", "title": "Sell Gathering Materials", "desc": "Sell all raw gathering materials in your bag for 1 Gold each.", "tag": "1 Gold Each"},
        ]
    elif mob_name == "trappers_cache":
        badge = "Hidden Stash"
        flavor = "Concealed beneath hollowed boughs lies an oiled leather pack left behind by an old frontier trapper."
        choices = [
            {"key": "cache_kit_a", "title": "Cache Kit A: Elusive Scout", "desc": "Take 1 Smoke Bomb and 1 Food Ration.", "tag": "Smoke Bomb + Food"},
            {"key": "cache_kit_b", "title": "Cache Kit B: Seasoned Veteran", "desc": f"Take 1 {level_consumable} and 1 Food Ration.", "tag": f"{level_consumable} + Food"},
        ]
    elif mob_name == "alchemists_alembic":
        badge = "Strange Apparatus"
        flavor = "A brass distillation apparatus bubbles gently over a blue spirit flame, extracting potent essences."
        choices = [
            {"key": "alembic_brew", "title": "Distill Field Tincture", "desc": "Transmute 1 Herb from your bag into 2 Healing Potions.", "tag": "1 Herb -> 2 Potions"},
            {"key": "alembic_salvage", "title": "Salvage Scrap Metal", "desc": "Dismantle parts of the apparatus to obtain 1 Crag-Iron ore.", "tag": "+1 Crag-Iron"},
        ]
    elif mob_name == "couriers_satchel":
        badge = "Abandoned Pack"
        flavor = "An embossed leather satchel lies beside the trail, sealed with wax and addressed to the Town magistrate."
        choices = [
            {"key": "satchel_instant", "title": "Pocket Contents Now", "desc": f"Break the seal and pocket the travel stipend immediately for {2 + zone_lvl} Gold.", "tag": f"+{2 + zone_lvl} Gold"},
            {"key": "satchel_deliver", "title": "Deliver Sealed Satchel", "desc": f"Take the 1x1 Courier's Satchel. Deliver it to Town to claim {4 + zone_lvl} Gold and +1 Bounty credit.", "tag": "1x1 Bag Token"},
        ]

    return render_template(
        "event_resolve.html",
        hero=hero,
        board=board,
        event_display_name=display_name,
        event_badge=badge,
        event_flavor=flavor,
        choices=choices,
        flash=_pop_flash(),
    )


@app.route("/event/choose", methods=["POST"])
def event_choose():
    if _S.get("board") is None or not _S.get("pending_action"):
        return redirect(url_for("travel"))

    board = _S["board"]
    is_cmp = (board.mode == "competitive")
    hero_idx = _S.get("active_hero_idx", 0) if is_cmp else 0
    hero = board.heroes[hero_idx]
    class_name = _S["class_names"][hero_idx]
    rng = _S["rng"]
    pending = _S["pending_action"]
    node_name = pending["node_name"]
    zone_id = hero.position[0] if isinstance(hero.position, tuple) else 1
    zone_lvl = SD.zone_level_for_zone(zone_id)
    level = BE.TIER_TO_LEVEL[M.ZONE_TIER.get(zone_id, "tier_1")]
    choice_key = request.form.get("choice_key", "")

    if choice_key == "well_safe":
        hero.hp = min(hero.max_hp, hero.hp + 2)
        _flash("You drank deep from the Sacred Well and restored 2 HP.")
    elif choice_key == "well_gamble":
        mod = M.CARD_SOURCE[class_name]
        swaps = BE._level2_swaps_for(class_name, hero.acquired)
        with LV.leveled_kit(mod, swaps):
            sample_hands = rng.sample(mod.ALL_HANDS, min(4, len(mod.ALL_HANDS)))
            all_cards = [c for h in sample_hands for c in h]
            has_defense = any("Block" in c or "Heal" in c or "Shield" in c or "Ward" in c for c in all_cards)
        if has_defense:
            hero.hp = min(hero.max_hp, hero.hp + 4)
            _flash("The Sacred Well resonated with your restorative essence! Restored 4 HP.")
        else:
            _flash("The Sacred Well remained silent. 0 HP restored.")
    elif choice_key.startswith("passage_"):
        target_z = int(choice_key.split("_")[1])
        hero.position = (target_z, None)
        _flash(f"You slipped through the Forgotten Passage into Zone {target_z}!")
    elif choice_key == "take_map":
        hero.acquired.add("dead_scouts_map")
        _flash("You took the Dead Scout's Map. Your next combat win will yield 1 bonus Level Loot card.")
    elif choice_key == "scout_horizon":
        B.discard_zone(board, zone_id, level)
        B.deal_zone(board, zone_id, level, rng)
        _flash("You surveyed the horizon from the watchtower. Fresh cards have been dealt across the zone.")
    elif choice_key == "hermit_ward":
        cost = 2 + zone_lvl
        if hero.gold >= cost:
            hero.gold -= cost
            hero.bone_ward = True
            _flash(f"You paid {cost} Gold. The Hermit granted you the Bone Ward!")
        else:
            _flash("You cannot afford the Hermit's Bone Ward.")
    elif choice_key == "hermit_pass":
        _flash("You bowed to the Hermit and continued on your journey.")
    elif choice_key == "attune_rune":
        mod = M.CARD_SOURCE[class_name]
        swaps = BE._level2_swaps_for(class_name, hero.acquired)
        with LV.leveled_kit(mod, swaps):
            sample = rng.choice(mod.ALL_HANDS)
            hero.reserved_card = sample[0]
            _flash(f"You attuned to the Monolith. '{sample[0]}' is reserved for your next combat hand!")
    elif choice_key == "field_rest":
        hero.hp = hero.max_hp
        _flash(f"You rested at the Abandoned Hearth. HP restored to {hero.max_hp:.0f}/{hero.max_hp:.0f}!")
    elif choice_key == "field_smith":
        recipes = EQ.get_recipes_for_class(hero.class_name)
        crafted = False
        bag_counts = {}
        for slot in hero.bag:
            if isinstance(slot, dict) and "items" in slot:
                for k, v in slot["items"].items():
                    bag_counts[k] = bag_counts.get(k, 0) + v
            elif isinstance(slot, str):
                bag_counts[slot] = bag_counts.get(slot, 0) + 1
        for recipe in recipes:
            if hero.equipment.get(recipe["slot"]) == recipe:
                continue
            can_afford, to_consume = EQ.can_craft_recipe(recipe, 9999, bag_counts)
            if can_afford:
                for mat, amt in to_consume.items():
                    M._remove_item(hero.bag, hero.locked, mat, amt)
                hero.equipment[recipe["slot"]] = recipe
                _flash(f"Field Smithing crafted {recipe['base']} ({recipe['rider']}) with 0 forge fee!")
                crafted = True
                break
        if not crafted:
            if M._bag_has_room(hero.bag, hero.locked):
                M._add_item(hero.bag, hero.locked, "Crag-Iron")
            else:
                hero.pending_loot.append("Crag-Iron")
            _flash("No equipment craftable from current materials. Salvaged +1 Crag-Iron from the forge!")
    elif choice_key == "peddler_potion":
        if hero.gold >= 3 and M._bag_has_room(hero.bag, hero.locked):
            hero.gold -= 3
            M._add_item(hero.bag, hero.locked, "potion")
            _flash("Purchased 1 Potion from the Peddler for 3 Gold.")
        else:
            _flash("Cannot afford Potion or bag is full.")
    elif choice_key == "peddler_food":
        if hero.gold >= 2 and M._bag_has_room(hero.bag, hero.locked):
            hero.gold -= 2
            M._add_food(hero.bag, hero.locked)
            _flash("Purchased 1 Food Ration from the Peddler for 2 Gold.")
        else:
            _flash("Cannot afford Food or bag is full.")
    elif choice_key == "peddler_sell":
        sell_tokens = [slot for slot in hero.bag if slot in SD.HERB_TOKENS or slot in SD.ORE_TOKENS or slot in {"Scavenged Pelt", "Bristle-Pelt"}]
        count = len(sell_tokens)
        for t in sell_tokens:
            M._remove_item(hero.bag, hero.locked, t, 1)
        hero.gold += count
        _flash(f"Sold {count} gathering materials to the Peddler for {count} Gold.")
    elif choice_key == "cache_kit_a":
        if M._bag_has_room(hero.bag, hero.locked):
            M._add_item(hero.bag, hero.locked, "smoke_bomb")
        else:
            hero.pending_loot.append("smoke_bomb")
        if M._bag_has_room(hero.bag, hero.locked):
            M._add_food(hero.bag, hero.locked)
        else:
            hero.pending_loot.append("food")
        _flash("Claimed Kit A: 1 Smoke Bomb and 1 Food Ration!")
    elif choice_key == "cache_kit_b":
        cons = "whetstone" if level == 1 else "preserving_charm"
        if M._bag_has_room(hero.bag, hero.locked):
            M._add_item(hero.bag, hero.locked, cons)
        else:
            hero.pending_loot.append(cons)
        if M._bag_has_room(hero.bag, hero.locked):
            M._add_food(hero.bag, hero.locked)
        else:
            hero.pending_loot.append("food")
        _flash(f"Claimed Kit B: 1 {cons.replace('_', ' ').title()} and 1 Food Ration!")
    elif choice_key == "alembic_brew":
        herbs = [s for s in hero.bag if s in SD.HERB_TOKENS]
        if herbs:
            M._remove_item(hero.bag, hero.locked, herbs[0], 1)
            for _ in range(2):
                if M._bag_has_room(hero.bag, hero.locked):
                    M._add_item(hero.bag, hero.locked, "potion")
                else:
                    hero.pending_loot.append("potion")
            _flash(f"Transmuted 1 {herbs[0]} into 2 Healing Potions!")
        else:
            _flash("No herbs in Bag to distill.")
    elif choice_key == "alembic_salvage":
        ore = "Crag-Iron" if level == 1 else "Sun-Copper"
        if M._bag_has_room(hero.bag, hero.locked):
            M._add_item(hero.bag, hero.locked, ore)
        else:
            hero.pending_loot.append(ore)
        _flash(f"Salvaged +1 {ore} from the alembic!")
    elif choice_key == "clutch_snatch":
        hero.hp = max(1.0, hero.hp - 2)
        if M._bag_has_room(hero.bag, hero.locked):
            M._add_item(hero.bag, hero.locked, "beast_egg")
        else:
            hero.pending_loot.append("beast_egg")
        _flash("Snatched the Beast Egg and took 2 damage!")
    elif choice_key == "satchel_instant":
        gain = 2 + zone_lvl
        hero.gold += gain
        _flash(f"Pocketed {gain} Gold from the Courier's Satchel.")
    elif choice_key == "satchel_deliver":
        if M._bag_has_room(hero.bag, hero.locked):
            M._add_item(hero.bag, hero.locked, "couriers_satchel")
        else:
            hero.pending_loot.append("couriers_satchel")
        _flash("Took the Courier's Satchel. Deliver it to Town for reward + Bounty credit!")

    if _S.get("pending_kind") == "recovery_spice_event":
        hero.corpse_node = None
        hero.alive = True
        BE.apply_recovery_post_processing(hero)
        _flash("You've recovered your gear.")

    hero.turns += 1
    if zone_id in board.zones:
        gathering_item = board.zones[zone_id].gathering_tokens.pop(node_name, None)
        if gathering_item:
            if M._bag_has_room(hero.bag, hero.locked):
                M._add_item(hero.bag, hero.locked, gathering_item)
                _flash(f"Gathered {gathering_item} from the node.")
            else:
                hero.pending_loot.append(gathering_item)
                _flash(f"Gathered {gathering_item} (Bag Full).")

    if choice_key != "scout_horizon":
        B.discard_zone(board, zone_id, level)

    _S["pending_kind"] = None
    _S["pending_action"] = None
    _S["pending_hand"] = None
    _S["pending_border"] = None

    if is_cmp:
        _S["cmp_resolve_order"].pop(0)
        return _cmp_process_resolve_queue()

    _S["phase"] = "travel"
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

    if SD.is_spice_event(mob_name):
        _S["pending_action"] = dict(_S["pending_border"], mob_name=mob_name, node_name=_S["pending_border"].get("border_name"))
        _S["phase"] = "event_resolve"
        return redirect(url_for("event_resolve"))

    hand = _draw_hero_hand(hero, class_name, _S["rng"])
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
    _S["pending_hand"] = _normalize_hand(_S["pending_hand"], class_name, hero.acquired)
    hand = _S["pending_hand"]
    mob_name = _S["pending_action"]["mob_name"]
    pattern, mob_hp = M._pattern_hp_for_mob(class_name, mob_name)
    available_equipment = {
        slot: recipe for slot, recipe in hero.equipment.items()
        if slot not in hero.equipment_used
    }
    return render_template(
        "combat_plan.html", class_name=class_name, mob_name=mob_name.replace("_loot", ""),
        mob_level=_mob_level_for_pending(_S["pending_action"]),
        pattern=list(enumerate(pattern)), mob_hp=mob_hp, hero=hero,
        available_equipment=available_equipment,
        hand_options=_hand_options(class_name, hand, hero=hero), has_stance=M.HAS_STANCE[class_name],
        pending_kind=_S["pending_kind"], flash=_pop_flash(),
        nest_raid_url=url_for("combat_plan_nest_raid"),
    )


@app.route("/combat_plan/nest_raid", methods=["POST"])
def combat_plan_nest_raid():
    board = _S.get("board")
    if board is None or not _S.get("pending_action"):
        return redirect(url_for("travel"))
    hero = board.heroes[0]
    hero.hp = max(1.0, hero.hp - 2)
    hero.turns += 1
    if M._bag_has_room(hero.bag, hero.locked):
        M._add_item(hero.bag, hero.locked, "beast_egg")
        _flash("You raided the nest, suffered 2 unpreventable Damage, and fled with the Beast Egg!")
    else:
        hero.pending_loot.append("beast_egg")
        _flash("You raided the nest and suffered 2 damage! Bag full — Beast Egg is pending.")

    pending = _S.get("pending_action", {})
    node_name = pending.get("node_name")
    if node_name:
        zone_id = hero.position[0] if isinstance(hero.position, tuple) else 1
        zone = board.zones.get(zone_id)
        if zone and node_name in zone.nodes:
            zone.nodes[node_name].card = None

    _S["pending_action"] = None
    _S["pending_hand"] = None
    _S["phase"] = "travel"
    return redirect(url_for("travel"))


@app.route("/combat_plan/submit", methods=["POST"])
def combat_plan_submit():
    hero = _S["board"].heroes[0]
    class_name = _S["class_names"][0]
    board = _S["board"]
    rng = _S["rng"]
    _S["pending_hand"] = _normalize_hand(_S["pending_hand"], class_name, hero.acquired)
    hand = _S["pending_hand"]
    kind = _S["pending_kind"]
    pending = _S["pending_action"]

    sequence, stance_sequence, equipment_sequence, error = _parse_combat_plan(request.form, class_name, hand, hero=hero)
    if error is None:
        error = _validate_sequence(class_name, hand, pending["mob_name"], hero.hp, sequence, stance_sequence, equipment_sequence=equipment_sequence, hero=hero)
    if error:
        _flash(error)
        return redirect(url_for("combat_plan"))

    # Built BEFORE the real resolution below, from a separate throwaway dry run -- see
    # _build_combat_log's own docstring for why that's safe (zero RNG once the plan is fixed).
    log_rows, log_outcome = _build_combat_log(class_name, hand, pending["mob_name"], hero.hp,
                                               sequence, stance_sequence, equipment_sequence=equipment_sequence, hero=hero)
    decide_fn = make_sequence_decide_fn(sequence, stance_sequence, equipment_sequence)

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
        next_flashes.append(_outcome_message(kind, result, mob_level=_mob_level_for_pending(pending)))
        _S["pending_next_phase"] = "town"
    else:
        if kind in ("recovery_node", "recovery_border"):
            hero.alive = True
            next_flashes.append("You've recovered your gear.")
        if result.get("outcome") == "win" and "dead_scouts_map" in hero.acquired:
            hero.acquired.remove("dead_scouts_map")
            zone_id = hero.position[0] if isinstance(hero.position, tuple) else 1
            level = BE.TIER_TO_LEVEL[M.ZONE_TIER.get(zone_id, "tier_1")]
            deck = board.loot_decks.get(level)
            if deck:
                bonus_card = deck.draw(rng)
                if bonus_card:
                    if M._bag_has_room(hero.bag, hero.locked):
                        M._add_item(hero.bag, hero.locked, bonus_card)
                        next_flashes.append(f"The Dead Scout's Map guided you to bonus loot: {bonus_card.replace('_', ' ').title()}!")
                    else:
                        hero.pending_loot.append(bonus_card)
                        next_flashes.append(f"The Dead Scout's Map guided you to bonus loot (Bag Full): {bonus_card.replace('_', ' ').title()}!")
        next_flashes.append(_outcome_message(kind, result, mob_level=_mob_level_for_pending(pending)))
        _S["pending_next_phase"] = "travel"
    _S["pending_next_flashes"] = next_flashes

    mob_pattern, mob_hp_total = M._pattern_hp_for_mob(class_name, pending["mob_name"])
    _S["phase"] = "combat_result"
    return render_template("combat_result.html", class_name=class_name, mob_name=pending["mob_name"].replace("_loot", ""),
                            mob_level=_mob_level_for_pending(pending),
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
    loot_decks = {1: B.LootDeck.new(1, rng), 2: B.LootDeck.new(2, rng)}
    board = B.BoardState(mode="competitive", heroes=heroes, zones={}, level_decks=level_decks, loot_decks=loot_decks)
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
    if _S["cmp_declare_order"]:
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


@app.route("/cmp/pvp/use_consumable", methods=["POST"])
def cmp_pvp_use_consumable():
    hero_idx = _S["active_hero_idx"]
    hero = _S["board"].heroes[hero_idx]
    item = request.form.get("item")
    if item == "food":
        _S["flash"].append("Cannot use Food during the PvP Reaction Window.")
    elif M._accessible_count(hero.bag, hero.locked, item) > 0:
        M._remove_item(hero.bag, hero.locked, item, 1)
        if item == "potion":
            hero.hp = min(hero.max_hp, hero.hp + 8)
            hero.consumables_used["potion"] += 1
            _S["flash"].append("Drank Potion: +8 HP.")
        elif item == "whetstone":
            hero.pvp_whetstone_active = True
            _S["flash"].append("Used Whetstone: +1 DMG / +1 BLK for this duel.")
        elif item == "smoke_bomb":
            _S["flash"].append("Used Smoke Bomb! Fleeing the duel!")
            # Fleeing instantly resolves the duel!
            board = _S["board"]
            _S["pvp_smoke_bomber"] = hero_idx
            return _cmp_pvp_resolve()
    return redirect(url_for("cmp_pvp_plan"))

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
    

    # Handle Smoke Bomb Flee (if any)
    smoke_bomber = _S.get("pvp_smoke_bomber")
    if smoke_bomber is not None:
        loser_idx = smoke_bomber
        winner_idx = d_idx if i_idx == loser_idx else i_idx
        winner = board.heroes[winner_idx]
        loser = board.heroes[loser_idx]
        _S["flash"].append(f"PvP! {loser.class_name} used a Smoke Bomb to flee! {winner.class_name} wins by default.")
        _S.pop("pvp_smoke_bomber", None)
    else:
        winner.tokens = max(0, winner.tokens - 1)
        loser.tokens += 1
        _S["flash"].append(f"PvP! {winner.class_name} defeated {loser.class_name}! ({winner.class_name} dealt {i_dmg if winner_idx == i_idx else d_dmg} dmg, {loser.class_name} dealt {d_dmg if winner_idx == i_idx else i_dmg} dmg)")

    winner.gold += 1
    if loser.gold > 0:
        loser.gold -= 1
        winner.gold += 1
        
    # Bystander Rule!
    node_name = _S["pvp_contested_node"]
    has_bystander = len(_S["pvp_claimants"]) > 2
    
    board.pending_declarations.pop(loser_idx, None)
    
    if has_bystander:
        board.pending_declarations.pop(winner_idx, None)
        _S["flash"].append(f"Bystander Rule: {winner.class_name} gets the PvP Gold, but the PvE mob remains for the bystanders to fight!")
    else:
        board.pending_declarations.pop(winner_idx, None)
        _tier, loot_name = M.NODES[node_name]
        if M._add_loot(winner.bag, winner.locked, loot_name):
            _S["flash"].append(f"{winner.class_name} claimed the node's {loot_name}!")
        else:
            _S["flash"].append(f"{winner.class_name} had no room for {loot_name}!")
            
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

        hero = board.heroes[hero_idx]
        mob_name = action.get("mob_name")
        if SD.is_spice_event(mob_name):
            _S["pending_kind"] = "cmp_spice_event"
            _S["pending_action"] = action
            _S["phase"] = "event_resolve"
            return redirect(url_for("event_resolve"))
        hand = _draw_hero_hand(hero, class_names[hero_idx], rng)
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
    hero = _S["board"].heroes[hero_idx]
    class_name = _S["class_names"][hero_idx]
    pick = request.form.get("pick")
    candidates = _S["pending_border"]["candidates"]
    mob_name = candidates[0] if pick == "0" else candidates[1]

    if SD.is_spice_event(mob_name):
        _S["pending_kind"] = "cmp_spice_event"
        _S["pending_action"] = dict(_S["pending_border"], mob_name=mob_name, node_name=_S["pending_border"].get("border_name"))
        _S["phase"] = "event_resolve"
        return redirect(url_for("event_resolve"))

    hand = _draw_hero_hand(hero, class_name, _S["rng"])
    _S["pending_action"] = dict(_S["pending_border"], mob_name=mob_name)
    _S["pending_hand"] = hand
    _S["phase"] = "cmp_combat_plan"
    return redirect(url_for("cmp_combat_plan"))


@app.route("/cmp/combat_plan")
def cmp_combat_plan():
    hero_idx = _S["active_hero_idx"]
    hero = _S["board"].heroes[hero_idx]
    class_name = _S["class_names"][hero_idx]
    _S["pending_hand"] = _normalize_hand(_S["pending_hand"], class_name, hero.acquired)
    hand = _S["pending_hand"]
    mob_name = _S["pending_action"]["mob_name"]
    pattern, mob_hp = M._pattern_hp_for_mob(class_name, mob_name)
    available_equipment = {
        slot: recipe for slot, recipe in hero.equipment.items()
        if slot not in hero.equipment_used
    }
    return render_template(
        "combat_plan.html", class_name=class_name, mob_name=mob_name.replace("_loot", ""),
        mob_level=_mob_level_for_pending(_S["pending_action"]),
        pattern=list(enumerate(pattern)), mob_hp=mob_hp, hero=hero,
        available_equipment=available_equipment,
        hand_options=_hand_options(class_name, hand, hero=hero), has_stance=M.HAS_STANCE[class_name],
        pending_kind=_S["pending_kind"], flash=_pop_flash(),
        turn_label=_cmp_label(hero_idx), action_url=url_for("cmp_combat_plan_submit"),
        nest_raid_url=url_for("cmp_combat_plan_nest_raid"),
    )


@app.route("/cmp/combat_plan/nest_raid", methods=["POST"])
def cmp_combat_plan_nest_raid():
    board = _S.get("board")
    if board is None or not _S.get("pending_action"):
        return redirect(url_for("cmp_travel"))
    hero_idx = _S["active_hero_idx"]
    hero = board.heroes[hero_idx]
    hero.hp = max(1.0, hero.hp - 2)
    hero.turns += 1
    if M._bag_has_room(hero.bag, hero.locked):
        M._add_item(hero.bag, hero.locked, "beast_egg")
        _flash("You raided the nest, suffered 2 unpreventable Damage, and fled with the Beast Egg!")
    else:
        hero.pending_loot.append("beast_egg")
        _flash("You raided the nest and suffered 2 damage! Bag full — Beast Egg is pending.")

    pending = _S.get("pending_action", {})
    node_name = pending.get("node_name")
    if node_name:
        zone_id = hero.position[0] if isinstance(hero.position, tuple) else 1
        zone = board.zones.get(zone_id)
        if zone and node_name in zone.nodes:
            zone.nodes[node_name].card = None

    _S["pending_action"] = None
    _S["pending_hand"] = None
    return _cmp_process_resolve_queue()


@app.route("/cmp/combat_plan/submit", methods=["POST"])
def cmp_combat_plan_submit():
    hero_idx = _S["active_hero_idx"]
    hero = _S["board"].heroes[hero_idx]
    class_name = _S["class_names"][hero_idx]
    board = _S["board"]
    rng = _S["rng"]
    _S["pending_hand"] = _normalize_hand(_S["pending_hand"], class_name, hero.acquired)
    hand = _S["pending_hand"]
    kind = _S["pending_kind"]
    pending = _S["pending_action"]

    sequence, stance_sequence, equipment_sequence, error = _parse_combat_plan(request.form, class_name, hand, hero=hero)
    if error is None:
        error = _validate_sequence(class_name, hand, pending["mob_name"], hero.hp, sequence, stance_sequence, equipment_sequence=equipment_sequence, hero=hero)
    if error:
        _flash(error)
        return redirect(url_for("cmp_combat_plan"))
    decide_fn = make_sequence_decide_fn(sequence, stance_sequence, equipment_sequence)

    if kind == "cmp_declare_node":
        result = BE.apply_travel_action(hero, pending, class_name, board, rng,
                                         M.RISK_TOLERANCE_BASE, True, defer_zone_discard=True,
                                         decide_fn=decide_fn, hand=hand)
    else:  # cmp_cross_border
        result = BE.resolve_border_crossing(hero, class_name, pending["border_name"], pending["target_zone"],
                                             pending["mob_name"], rng, M.RISK_TOLERANCE_BASE, True,
                                             decide_fn=decide_fn, hand=hand)

    if result.get("outcome") == "win" and "dead_scouts_map" in hero.acquired:
        hero.acquired.remove("dead_scouts_map")
        zone_id = hero.position[0] if isinstance(hero.position, tuple) else 1
        level = BE.TIER_TO_LEVEL[M.ZONE_TIER.get(zone_id, "tier_1")]
        deck = board.loot_decks.get(level)
        if deck:
            bonus_card = deck.draw(rng)
            if bonus_card:
                if M._bag_has_room(hero.bag, hero.locked):
                    M._add_item(hero.bag, hero.locked, bonus_card)
                else:
                    hero.pending_loot.append(bonus_card)

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


@app.route("/load", methods=["POST"])
def load_game():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "rb") as f:
                data = pickle.load(f)
            _S.clear()
            _S.update(data)
            _S.setdefault("flash", []).append("Game loaded successfully.")
            if _S.get("mode") == "competitive":
                return redirect(url_for("cmp_declare"))
            
            phase = _S.get("phase")
            if phase == "combat_plan":
                return redirect(url_for("combat_plan"))
            if phase == "scouted_pick":
                return redirect(url_for("scouted_pick"))
            
            hero = _S["board"].heroes[0] if _S.get("board") and _S["board"].heroes else None
            if hero and hero.position:
                if hero.position[1] == "town":
                    return redirect(url_for("town"))
                if hero.position[1] == "trainer":
                    return redirect(url_for("trainer"))

            return redirect(url_for("travel"))
        except Exception as e:
            app.logger.error(f"Load failed: {e}")
            _S.setdefault("flash", []).append(f"Failed to load: {e}")
    return redirect(url_for("index"))


@app.after_request
def auto_save_state(response):
    if response.status_code in (200, 302) and not request.path.startswith("/static/") and request.path != "/" and request.path != "/load":
        if _S and _S.get("board"):
            try:
                with open(SAVE_FILE, "wb") as f:
                    pickle.dump(_S, f)
            except Exception as e:
                app.logger.error(f"Failed to auto-save game: {e}")
    return response


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
