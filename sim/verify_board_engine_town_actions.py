"""
Verification for the human-facing macro Town seam (enter_town/get_town_actions/
apply_town_action, checkpointed 2026-08-22) -- the first slice of the "make this a real
player-run simulator backend" decision seam, mirroring combat_engine.py's get_legal_actions/
apply_action shape for the macro layer. Everything genuinely discretionary at Town (which
Purchase Queue item, in what order, when to stop) is now a real choice; everything that
isn't a real choice in the physical game (turn-in, restock, quest pickup, mandatory grant)
stays automatic via the shared _town_automatic_setup helper resolve_town_turn itself also
uses -- see that function's own docstring for why the two paths can't drift apart.

Two parts: (1) bit-for-bit proof that driving the new seam in strict queue order reproduces
_walk_purchase_queue's "save" policy exactly (stop at the first unaffordable item, don't skip
ahead) -- this is possible here, unlike most of this session's other checks, because
get_town_actions/apply_town_action don't touch randomness or the deck at all, only gold/
acquired/bag bookkeeping already fully covered by _town_automatic_setup's own no-op-verified
refactor. (2) Direct eligibility checks (Trainer-gating, Level-2-started-gating, affordability).
"""
import random

import board_engine as BE
import macro_sim as M
from board_state import HeroBoardState


def _walk_queue_order_greedy(hero, purchase_queue):
    """Drives get_town_actions/apply_town_action in STRICT queue order, stopping at the first
    item that isn't currently offered (not affordable or not eligible) -- reproduces
    _walk_purchase_queue's policy="save" behavior exactly using only the new human-facing
    primitives, to prove they're capable of it bit-for-bit when driven the same way."""
    for item in purchase_queue:
        if item["tag"] in hero.acquired:
            continue
        actions = BE.get_town_actions(hero, purchase_queue)
        matching = next((a for a in actions if a.get("tag") == item["tag"]), None)
        if matching is None:
            break  # this item isn't currently offered -- matches "save" stopping here
        BE.apply_town_action(hero, matching, purchase_queue)
    # Explicit leave_town, matching a real driver's final action -- doesn't change state.
    actions = BE.get_town_actions(hero, purchase_queue)
    leave = next(a for a in actions if a["type"] == "leave_town")
    BE.apply_town_action(hero, leave, purchase_queue)


def run_direct_checks(verbose=True):
    failures = []

    def check(name, condition, detail=""):
        if not condition:
            failures.append((name, detail))
            if verbose:
                print(f"FAIL: {name} -- {detail}")
        elif verbose:
            print(f"ok: {name}")

    purchase_queue = M._build_purchase_queue("warrior", 0)

    # 1. Skill purchases require standing in a Trainer Zone.
    hero = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, "town"),
                           bag=[None, None], locked=[False, False], gold=100,
                           acquired={"started_l2_quests"})
    actions = BE.get_town_actions(hero, purchase_queue)
    check("no skill purchase offered outside a Trainer Zone",
          not any(a.get("kind") == "skill" for a in actions), actions)
    hero.position = (2, "town")
    actions = BE.get_town_actions(hero, purchase_queue)
    check("skill purchase offered inside a Trainer Zone",
          any(a.get("kind") == "skill" for a in actions), actions)

    # 2. Bag Upgrade requires started_l2_quests.
    hero2 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(2, "town"),
                            bag=[None, None], locked=[False, False], gold=100, acquired=set())
    actions = BE.get_town_actions(hero2, purchase_queue)
    check("no Bag Upgrade offered before started_l2_quests",
          not any(a.get("tag") == "bag_upgrade" for a in actions), actions)
    hero2.acquired.add("started_l2_quests")
    actions = BE.get_town_actions(hero2, purchase_queue)
    check("Bag Upgrade offered once started_l2_quests is set",
          any(a.get("tag") == "bag_upgrade" for a in actions), actions)

    # 3. Affordability gating.
    hero3 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(2, "town"),
                            bag=[None, None], locked=[False, False], gold=0,
                            acquired={"started_l2_quests"})
    actions = BE.get_town_actions(hero3, purchase_queue)
    check("nothing but leave_town offered with 0 gold", actions == [{"type": "leave_town"}], actions)

    # 4. apply_town_action correctly spends gold, marks acquired, and grows the bag for a
    # bag_upgrade purchase specifically.
    hero4 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(2, "town"),
                            bag=[None, None], locked=[False, False], gold=M.BAG_UPGRADE_COST,
                            acquired={"started_l2_quests"})
    actions = BE.get_town_actions(hero4, purchase_queue)
    bag_action = next(a for a in actions if a["tag"] == "bag_upgrade")
    BE.apply_town_action(hero4, bag_action, purchase_queue)
    check("bag_upgrade purchase spends gold to 0", hero4.gold == 0, hero4.gold)
    check("bag_upgrade purchase marks acquired", "bag_upgrade" in hero4.acquired, hero4.acquired)
    check("bag_upgrade purchase grows the bag", len(hero4.bag) == 3 and len(hero4.locked) == 3,
          (hero4.bag, hero4.locked))

    # 5. leave_town costs no extra turn (enter_town already charged the one turn for the
    # whole visit) and doesn't mutate anything else.
    hero5 = HeroBoardState(class_name="warrior", hp=18.0, max_hp=18.0, position=(1, "town"),
                            bag=[None, None], locked=[False, False], gold=5)
    turns_before = hero5.turns
    actions = BE.get_town_actions(hero5, purchase_queue)
    leave = next(a for a in actions if a["type"] == "leave_town")
    still_in_town = BE.apply_town_action(hero5, leave, purchase_queue)
    check("leave_town returns False", still_in_town is False, still_in_town)
    check("leave_town doesn't touch turns itself", hero5.turns == turns_before, (hero5.turns, turns_before))

    print(f"\n{len(failures)} failures" if failures else "\nAll direct checks passed")
    return not failures


def verify_queue_order_matches_save_policy(class_name, trials=20, seed=1, verbose=False):
    """Bit-for-bit: driving the new seam in strict queue order should land on the exact same
    (gold, acquired, bag, locked) as resolve_town_turn's own policy="save" walk, for a battery
    of hand-built starting states covering a range of gold/acquired/position combinations."""
    mismatches = []
    purchase_queue = M._build_purchase_queue(class_name, 0)
    mod = M.CARD_SOURCE[class_name]
    max_hp = float(getattr(mod, M.HP_ATTR[class_name]))

    scenarios = 0
    for seed_i in range(trials):
        rng_gold = random.Random(seed_i + seed)
        gold = rng_gold.randint(0, 60)
        position = rng_gold.choice([1, 2, 3, 4])
        acquired = set(rng_gold.sample(["started_l2_quests"], rng_gold.randint(0, 1)))
        scenarios += 1

        hero_a = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(position, "town"),
                                 bag=[None, None], locked=[False, False], gold=gold, acquired=set(acquired))
        hero_a.gold, _tt = M._walk_purchase_queue(purchase_queue, hero_a.acquired, hero_a.bag, hero_a.locked,
                                                    position, hero_a.gold, "save")

        hero_b = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp, position=(position, "town"),
                                 bag=[None, None], locked=[False, False], gold=gold, acquired=set(acquired))
        _walk_queue_order_greedy(hero_b, purchase_queue)

        state_a = (hero_a.gold, hero_a.acquired, hero_a.bag, hero_a.locked)
        state_b = (hero_b.gold, hero_b.acquired, hero_b.bag, hero_b.locked)
        if state_a != state_b:
            mismatches.append((seed_i, state_a, state_b))
            if verbose:
                print(f"MISMATCH {class_name} seed={seed_i}: old={state_a} new={state_b}")
    return scenarios, mismatches


def verify_all(trials=20, seed=1, verbose=False):
    grand_scenarios = 0
    grand_mismatches = 0
    for class_name in M.CARD_SOURCE:
        scenarios, mismatches = verify_queue_order_matches_save_policy(class_name, trials=trials,
                                                                         seed=seed, verbose=verbose)
        grand_scenarios += scenarios
        grand_mismatches += len(mismatches)
        status = "OK" if not mismatches else f"{len(mismatches)} MISMATCHES"
        print(f"{class_name:12s} {scenarios:4d} scenarios  {status}")
    print(f"\nTotal: {grand_scenarios} scenarios, {grand_mismatches} mismatches")
    return grand_mismatches == 0


if __name__ == "__main__":
    ok1 = run_direct_checks()
    print()
    ok2 = verify_all(verbose=True)
    raise SystemExit(0 if (ok1 and ok2) else 1)
