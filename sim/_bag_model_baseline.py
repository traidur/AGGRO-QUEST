"""One-off diagnostic: baseline economy metrics before/after the Bag data-model fix
(2026-08-22). Run once against the OLD (uncapped, closable loot slot) model, then again,
unchanged, after the fix, to see exactly how much the corrected model actually moves things --
not guessed, measured. Delete once the finding is written into DESIGN_DOC.md/MACRO_LOOP_GUIDE.md.
"""
import random

import board_engine as BE
import macro_sim as M

TURNS = 90
SEEDS = 10


def run_baseline():
    orig_pull = M._engine_pull
    orig_bag_has_room = M._bag_has_room
    orig_add_loot = M._add_loot

    stats = {}

    def traced_pull(class_name, mob_name, hand, pattern, mob_hp, hp):
        win, final_hp, rounds = orig_pull(class_name, mob_name, hand, pattern, mob_hp, hp)
        s = stats[class_name]
        s['pulls'] += 1
        if final_hp <= 0:
            s['deaths'] += 1
        elif win:
            s['wins'] += 1
        else:
            s['flees'] += 1
        return win, final_hp, rounds

    def traced_bag_has_room(bag, locked):
        result = orig_bag_has_room(bag, locked)
        if stats['_current'] is not None:
            s = stats[stats['_current']]
            s['bag_room_checks'] += 1
            if not result:
                s['bag_deadlocks'] += 1
        return result

    def traced_add_loot(bag, locked, loot_name):
        result = orig_add_loot(bag, locked, loot_name)
        if stats['_current'] is not None:
            s = stats[stats['_current']]
            if not result:
                s['no_room'] = s.get('no_room', 0) + 1
            for slot in bag:
                if isinstance(slot, dict) and 'loot' in slot:
                    total = sum(slot['loot'].values())
                    if total > s['max_slot_loot']:
                        s['max_slot_loot'] = total
                elif isinstance(slot, dict) and 'items' in slot:
                    total = sum(slot['items'].values())
                    if total > s['max_slot_loot']:
                        s['max_slot_loot'] = total
        return result

    M._engine_pull = traced_pull
    M._bag_has_room = traced_bag_has_room
    M._add_loot = traced_add_loot

    print(f"{'class':12s} {'gold':>6s} {'xp':>5s} {'g/turn':>7s} {'quests':>7s} "
          f"{'deaths':>7s} {'flee%':>6s} {'no_room':>8s} {'deadlk':>7s} {'max_slot':>9s}")

    try:
        for class_name in M.CARD_SOURCE:
            stats[class_name] = dict(pulls=0, wins=0, flees=0, deaths=0,
                                      bag_room_checks=0, bag_deadlocks=0, max_slot_loot=0, no_room=0)
            stats['_current'] = class_name
            total_gold = total_xp = total_turns = total_quests = 0
            for seed in range(SEEDS):
                rng = random.Random(seed + 7000)
                gold = xp = turns = quests = 0
                for alive, g, x, qc, trainer_turn, t in BE.run_solo_chain(
                        class_name, 'food_only', rng, max_turns=TURNS):
                    gold, xp, turns = g, x, t
                    quests += qc
                total_gold += gold
                total_xp += xp
                total_turns += turns
                total_quests += quests
            stats['_current'] = None
            s = stats[class_name]
            n = max(1, s['pulls'])
            print(f"{class_name:12s} {total_gold/SEEDS:6.1f} {total_xp/SEEDS:5.1f} "
                  f"{total_gold/max(1,total_turns):7.3f} {total_quests/SEEDS:7.1f} "
                  f"{s['deaths']:7d} {s['flees']/n:6.1%} {s['no_room']:8d} "
                  f"{s['bag_deadlocks']:7d} {s['max_slot_loot']:9d}")
    finally:
        M._engine_pull = orig_pull
        M._bag_has_room = orig_bag_has_room
        M._add_loot = orig_add_loot


if __name__ == "__main__":
    run_baseline()
