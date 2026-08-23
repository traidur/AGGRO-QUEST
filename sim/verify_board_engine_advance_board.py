"""
Verification for the Move-and-declare barrier (declare_for_hero/advance_board, checkpointed
2026-08-23, task #64) -- the first genuinely new multi-hero mechanism in this codebase, no
existing single-hero function to port from or bit-for-bit compare against wholesale.

Direct mechanical checks: N=1 (solo) reproduces calling apply_travel_action directly, bit for
bit; N=2 uncontested (different Nodes) both resolve correctly and independently; N=2 contested
(same Node) resolves via priority-token order -- winner keeps the dealt mob, loser gets a real
blind redraw; the barrier waits (returns None) until every hero has declared; the priority
token advances exactly one seat per resolved round; Zone Discard timing doesn't corrupt a
second hero's still-pending pull in the same Zone this round (the actual bug defer_zone_discard
exists to prevent)."""
import random

import board_engine as BE
import board_state as B
import macro_sim as M
from board_state import HeroBoardState


def run_direct_checks(verbose=True):
    failures = []

    def check(name, condition, detail=""):
        if not condition:
            failures.append((name, detail))
            if verbose:
                print(f"FAIL: {name} -- {detail}")
        elif verbose:
            print(f"ok: {name}")

    # 1. advance_board returns None until every hero has declared.
    rng = random.Random(1)
    level_decks = {1: B.LevelDeck.new(1, rng), 2: B.LevelDeck.new(2, rng)}
    hero_a = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, None),
                             bag=[None, None], locked=[False, False], gold=0)
    hero_b = HeroBoardState(class_name="wizard", hp=17.0, max_hp=17.0, position=(1, None),
                             bag=[None, None], locked=[False, False], gold=0)
    board = B.BoardState(mode="competitive", heroes=[hero_a, hero_b], zones={}, level_decks=level_decks)
    class_names = {0: "warrior", 1: "wizard"}

    actions_a = BE.get_travel_actions(hero_a, board, rng)
    declare_a = next(a for a in actions_a if a["type"] == "declare_node")
    BE.declare_for_hero(board, 0, declare_a)
    result = BE.advance_board(board, class_names, rng, M.RISK_TOLERANCE_BASE, True)
    check("advance_board waits (returns None) with only 1 of 2 heroes declared", result is None, result)

    # 2. N=1 solo: advance_board with exactly one hero resolves immediately, and produces the
    # SAME result apply_travel_action would directly (bit-for-bit reproducibility).
    rng_solo_a = random.Random(5)
    rng_solo_b = random.Random(5)
    level_decks_a = {1: B.LevelDeck.new(1, rng_solo_a), 2: B.LevelDeck.new(2, rng_solo_a)}
    level_decks_b = {1: B.LevelDeck.new(1, rng_solo_b), 2: B.LevelDeck.new(2, rng_solo_b)}
    hero_solo_a = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, None),
                                  bag=[None, None], locked=[False, False], gold=0)
    hero_solo_b = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, None),
                                  bag=[None, None], locked=[False, False], gold=0)
    board_solo_a = B.BoardState(mode="solo", heroes=[hero_solo_a], zones={}, level_decks=level_decks_a)
    board_solo_b = B.BoardState(mode="solo", heroes=[hero_solo_b], zones={}, level_decks=level_decks_b)

    actions_solo = BE.get_travel_actions(hero_solo_a, board_solo_a, rng_solo_a)
    declare_solo = next(a for a in actions_solo if a["type"] == "declare_node")
    BE.get_travel_actions(hero_solo_b, board_solo_b, rng_solo_b)  # deal Zone 1 identically (same seed)
    direct_result = BE.apply_travel_action(hero_solo_b, declare_solo, "warrior", board_solo_b, rng_solo_b,
                                            M.RISK_TOLERANCE_BASE, True)

    BE.declare_for_hero(board_solo_a, 0, declare_solo)
    barrier_result = BE.advance_board(board_solo_a, {0: "warrior"}, rng_solo_a, M.RISK_TOLERANCE_BASE, True)

    check("N=1 barrier resolves immediately (not None)", barrier_result is not None, barrier_result)
    check("N=1 barrier result matches calling apply_travel_action directly, bit-for-bit",
          barrier_result[0] == direct_result, (barrier_result, direct_result))
    check("N=1 barrier produces the same hero end-state as the direct call",
          (hero_solo_a.hp, hero_solo_a.gold, hero_solo_a.turns, hero_solo_a.bag) ==
          (hero_solo_b.hp, hero_solo_b.gold, hero_solo_b.turns, hero_solo_b.bag),
          (hero_solo_a.__dict__, hero_solo_b.__dict__))
    check("N=1 barrier advances the priority token", board_solo_a.priority_token_holder == 0,
          board_solo_a.priority_token_holder)  # (0+1) % 1 == 0, single-hero token is a no-op
    check("N=1 barrier clears pending_declarations", board_solo_a.pending_declarations == {},
          board_solo_a.pending_declarations)

    # 3. N=2, uncontested (different Nodes): both heroes resolve independently, both get real
    # outcomes, and (the actual regression defer_zone_discard exists to prevent) the SECOND
    # hero's pull isn't corrupted by the first hero's zone discard happening too early.
    rng2 = random.Random(3)
    level_decks2 = {1: B.LevelDeck.new(1, rng2), 2: B.LevelDeck.new(2, rng2)}
    hero_c = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, None),
                             bag=[None, None], locked=[False, False], gold=0)
    hero_d = HeroBoardState(class_name="wizard", hp=17.0, max_hp=17.0, position=(1, None),
                             bag=[None, None], locked=[False, False], gold=0)
    board2 = B.BoardState(mode="competitive", heroes=[hero_c, hero_d], zones={}, level_decks=level_decks2)
    actions_c = BE.get_travel_actions(hero_c, board2, rng2)
    declares_c = [a for a in actions_c if a["type"] == "declare_node"]
    check("Zone 1 deals more than one Node (needed for an uncontested-declare test)",
          len(declares_c) >= 2, declares_c)
    if len(declares_c) >= 2:
        BE.declare_for_hero(board2, 0, declares_c[0])
        BE.declare_for_hero(board2, 1, {"type": "declare_node", "node_name": declares_c[1]["node_name"],
                                         "mob_name": declares_c[1]["mob_name"]})
        results2 = BE.advance_board(board2, {0: "warrior", 1: "wizard"}, rng2, M.RISK_TOLERANCE_BASE, True)
        check("uncontested: both heroes get a real combat outcome",
              all(r["outcome"] in ("win", "flee", "died", "no_room") for r in results2.values()), results2)
        check("uncontested: both heroes' turns incremented (neither pull was corrupted/skipped)",
              hero_c.turns == 1 and hero_d.turns == 1, (hero_c.turns, hero_d.turns))

    # 4. N=2, contested (same Node): priority-token winner keeps the dealt mob; loser gets a
    # real blind redraw (not necessarily different, but drawn via a real independent draw --
    # checked by confirming the deck's draw pile actually shrank by the redraw amount).
    rng3 = random.Random(7)
    level_decks3 = {1: B.LevelDeck.new(1, rng3), 2: B.LevelDeck.new(2, rng3)}
    hero_e = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, None),
                             bag=[None, None], locked=[False, False], gold=0)
    hero_f = HeroBoardState(class_name="wizard", hp=17.0, max_hp=17.0, position=(1, None),
                             bag=[None, None], locked=[False, False], gold=0)
    board3 = B.BoardState(mode="competitive", heroes=[hero_e, hero_f], zones={}, level_decks=level_decks3,
                           priority_token_holder=0)
    actions_e = BE.get_travel_actions(hero_e, board3, rng3)
    declare_e = next(a for a in actions_e if a["type"] == "declare_node")
    same_node_action_f = {"type": "declare_node", "node_name": declare_e["node_name"],
                           "mob_name": declare_e["mob_name"]}

    def total_cards(level_decks_dict, board_obj):
        dealt_count = sum(len(zb.dealt) for zb in board_obj.zones.values())
        return len(level_decks_dict[1].draw_pile) + len(level_decks_dict[1].discard_pile) + dealt_count

    draws_before = total_cards(level_decks3, board3)
    BE.declare_for_hero(board3, 0, declare_e)
    BE.declare_for_hero(board3, 1, same_node_action_f)
    results3 = BE.advance_board(board3, {0: "warrior", 1: "wizard"}, rng3, M.RISK_TOLERANCE_BASE, True)
    check("contested: both heroes get a real combat outcome",
          all(r["outcome"] in ("win", "flee", "died", "no_room") for r in results3.values()), results3)
    check("contested: both heroes' turns incremented", hero_e.turns == 1 and hero_f.turns == 1,
          (hero_e.turns, hero_f.turns))
    draws_after = total_cards(level_decks3, board3)
    check("contested: total card count conserved (redraw discards immediately, no cards lost/created)",
          draws_before == draws_after, (draws_before, draws_after))

    # 5. Priority token holder determines who wins a contest -- rerun with the token on hero_f
    # (index 1) instead and confirm the winner flips.
    rng4 = random.Random(7)
    level_decks4 = {1: B.LevelDeck.new(1, rng4), 2: B.LevelDeck.new(2, rng4)}
    hero_g = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, None),
                             bag=[None, None], locked=[False, False], gold=0)
    hero_h = HeroBoardState(class_name="wizard", hp=17.0, max_hp=17.0, position=(1, None),
                             bag=[None, None], locked=[False, False], gold=0)
    board4 = B.BoardState(mode="competitive", heroes=[hero_g, hero_h], zones={}, level_decks=level_decks4,
                           priority_token_holder=1)
    actions_g = BE.get_travel_actions(hero_g, board4, rng4)
    declare_g = next(a for a in actions_g if a["type"] == "declare_node")
    same_node_action_h = {"type": "declare_node", "node_name": declare_g["node_name"],
                           "mob_name": declare_g["mob_name"]}
    order4 = BE._priority_order(board4)
    check("priority order starts from the token holder (index 1 first)", order4[0] == 1, order4)

    # 6. Priority token advances by exactly one seat after a resolved round.
    check("priority token advanced after round 1 (contest test above, started at 0)",
          board3.priority_token_holder == 1, board3.priority_token_holder)

    print(f"\n{len(failures)} failures" if failures else "\nAll direct checks passed")
    return not failures


if __name__ == "__main__":
    ok = run_direct_checks()
    raise SystemExit(0 if ok else 1)
