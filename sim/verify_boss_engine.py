"""
verify_boss_engine.py -- Verification test suite for Zone 4 Tier Gate Boss Trio.
Validates:
1. Boss profiles and pattern typing (range-sensitive 3-tuples vs 2-tuples).
2. Scout Token drawing (1 vs 2 candidates, token deduction).
3. 14 XP Capstone Quest grant ('The Citadel Commission') at Zone 4 Trainer.
4. Two-phase continuous combat resolution & P1 Knockout Rule.
5. All 4 outcomes: Triumph, P1 Damage Fail, P2 Timeout, and Death.
6. Equipment breaking on death and Blacksmith repair in Town.
7. 9-class x 3-boss execution gauntlet (all 27 combinations).
"""

import random
import boss_data as BD
import board_engine as BE
import board_state as B
import macro_sim as M
import combat_engine as CE
import equipment_data as EQ
from board_state import HeroBoardState


def test_boss_data_profiles():
    print("Testing boss data profiles and pattern typing...")
    assert len(BD.BOSS_IDS) == 3
    assert set(BD.BOSS_IDS) == {"malakor", "colossus", "eclipse"}

    # Test Malakor
    malakor = BD.BOSSES["malakor"]
    assert malakor["p1"]["hp"] == 10
    assert malakor["p2"]["hp"] == 10
    assert malakor["p1"]["types"] == ("ranged", "ranged", "ranged")

    # Range-sensitive class gets 3-tuples
    pat_wiz, hp_wiz = BD.get_phase_pattern_hp("malakor", 1, "wizard")
    assert hp_wiz == 10
    assert len(pat_wiz) == 3
    assert pat_wiz[0] == (4, 0, "ranged")

    # Non-range class gets 2-tuples
    pat_war, hp_war = BD.get_phase_pattern_hp("malakor", 1, "warrior")
    assert hp_war == 10
    assert len(pat_war) == 3
    assert pat_war[0] == (4, 0)

    # Colossus
    colossus = BD.BOSSES["colossus"]
    assert colossus["p1"]["hp"] == 10
    assert colossus["p2"]["hp"] == 10
    pat_rogue, _ = BD.get_phase_pattern_hp("colossus", 1, "rogue")
    assert pat_rogue[0] == (3, 2, "melee")

    # Eclipse
    eclipse = BD.BOSSES["eclipse"]
    assert eclipse["p1"]["hp"] == 10
    assert eclipse["p2"]["hp"] == 9
    pat_p2, _ = BD.get_phase_pattern_hp("eclipse", 2, "ranger")
    assert pat_p2[2] == (6, 0, "melee")

    print("  Boss data profiles OK.")


def test_scout_tokens():
    print("Testing Scout Token drawing...")
    rng = random.Random(42)

    # Standard draw: exactly 1 boss
    chosen, candidates = BD.draw_bosses(rng, scout_token=False)
    assert len(candidates) == 1
    assert chosen in BD.BOSS_IDS
    assert candidates[0] == chosen

    # Scout Token draw: exactly 2 unique bosses
    chosen2, candidates2 = BD.draw_bosses(rng, scout_token=True)
    assert len(candidates2) == 2
    assert len(set(candidates2)) == 2
    assert chosen2 in candidates2

    print("  Scout Token drawing OK.")


def test_capstone_trainer_grant():
    print("Testing Capstone Quest grant at Zone 4 Trainer...")
    hero = HeroBoardState(class_name="warrior", hp=18, max_hp=18, position=(4, "trainer"),
                           bag=[None] * 9, locked=[False] * 9, xp=12)

    # XP < 14: no grant
    setup1 = BE._trainer_automatic_setup(hero, "warrior")
    assert "citadel_commission_active" not in hero.acquired
    assert BD.CAPSTONE_QUEST_NAME not in hero.active_quests
    assert "completed_citadel_commission" not in hero.acquired

    # XP >= 14 at Zone 4 Trainer: grants Capstone Quest as an acquired flag
    hero.xp = 14
    setup2 = BE._trainer_automatic_setup(hero, "warrior")
    assert "citadel_commission_active" in hero.acquired
    assert BD.CAPSTONE_QUEST_NAME not in hero.active_quests

    # In Zone 2 at XP 14: does not grant Citadel Commission (Zone 4 exclusive)
    hero_z2 = HeroBoardState(class_name="warrior", hp=18, max_hp=18, position=(2, "trainer"),
                             bag=[None] * 9, locked=[False] * 9, xp=14)
    setup_z2 = BE._trainer_automatic_setup(hero_z2, "warrior")
    assert "citadel_commission_active" not in hero_z2.acquired
    assert BD.CAPSTONE_QUEST_NAME not in hero_z2.active_quests

    print("  Capstone Quest grant OK.")


def test_p1_damage_fail():
    print("Testing Phase 1 Damage Failure (P1 Knockout Rule)...")
    rng = random.Random(123)
    hero = HeroBoardState(class_name="warrior", hp=18, max_hp=18, position=(4, None),
                           bag=[None] * 9, locked=[False] * 9, xp=14)
    hero.acquired.add("citadel_commission_active")

    # Dummy decide_fn that plays lowest damage cards (or defends only) so boss HP > 0 after R3
    def turtle_decide(state, actions):
        legal = [a for a in actions if a.get("legal", False)]
        return min(legal, key=lambda a: a.get("dmg_dealt", 0))

    res = BE.resolve_boss_combat(hero, "warrior", "colossus", rng, decide_fn_p1=turtle_decide)
    assert res["outcome"] == "damage_fail_p1"
    assert hero.position == (5, "town")
    assert "completed_citadel_commission" in hero.acquired
    assert "citadel_commission_active" not in hero.acquired
    assert BD.CAPSTONE_QUEST_NAME not in hero.active_quests
    assert hero.hp == 1.0  # Arrives at 1 HP
    assert res["state2"] is None  # Phase 2 was never entered!
    assert hero.turns == 1  # 1 turn cost total

    print("  Phase 1 Damage Failure OK.")


def test_p2_triumph_and_spoils():
    print("Testing Phase 2 Triumph and spoils...")
    rng = random.Random(999)
    # Give warrior full health, Level 2 mandatory upgrade
    hero = HeroBoardState(class_name="warrior", hp=18, max_hp=18, position=(4, None),
                           bag=[None] * 9, locked=[False] * 9, xp=14, gold=10, tokens=0, bounty_credits=0)
    hero.acquired.add("mandatory")
    hero.acquired.add("citadel_commission_active")

    # Let QuestIntelligence run optimal play
    res = BE.resolve_boss_combat(hero, "warrior", "malakor", rng)
    # Malakor vs optimal Warrior should Triumph
    assert res["outcome"] == "triumph"
    assert res["gold_gained"] == 5
    assert hero.gold == 15
    assert hero.bounty_credits == 2
    assert res["bounty_credits_gained"] == 2
    assert hero.tokens == 0  # PvP tokens untouched!
    assert BD.TRIUMPH_KEY in hero.acquired
    assert BD.TRIUMPH_TROPHY in hero.acquired
    assert "completed_citadel_commission" in hero.acquired
    assert "citadel_commission_active" not in hero.acquired
    assert hero.position == (5, "town")
    assert res["state1"] is not None
    assert res["state2"] is not None
    assert hero.turns == 1  # 1 turn cost total

    print("  Phase 2 Triumph and spoils OK.")


def test_death_breaks_equipment_and_blacksmith_repairs():
    print("Testing death equipment breaking and Blacksmith repair...")
    rng = random.Random(456)

    # Hero with equipped gear
    hero = HeroBoardState(class_name="warrior", hp=18, max_hp=18, position=(4, None),
                           bag=[None] * 9, locked=[False] * 9, xp=14, gold=10)
    weapon_recipe = {
        "name": "Honed 1-Hander",
        "slot": "weapon",
        "grade": 1,
        "base": "1-Hander",
        "rider": "honed",
        "cost_gold": 1
    }
    armor_recipe = {
        "name": "Reinforced Heavy Armor",
        "slot": "armor",
        "grade": 2,
        "base": "Heavy Armor",
        "rider": "reinforced",
        "cost_gold": 3
    }
    hero.equipment["weapon"] = weapon_recipe
    hero.equipment["armor"] = armor_recipe

    # Mock death outcome
    res = BE.finalize_boss_combat(hero, "colossus", "death_p2")
    assert res["outcome"] == "death_p2"
    assert hero.position == (5, "town")
    assert hero.alive is True
    assert hero.hp == 1.0
    # Both items must be broken!
    assert "weapon" in hero.equipment_broken
    assert "armor" in hero.equipment_broken

    # In Town, check Blacksmith repair actions
    purchase_queue = M._build_purchase_queue("warrior", 0)
    actions = BE.get_town_actions(hero, purchase_queue)
    repair_actions = [a for a in actions if a["type"] == "repair_equipment"]
    assert len(repair_actions) == 2

    # Check repair costs: grade 1 = 1G, grade 2 = 2G
    rep_weapon = next(a for a in repair_actions if a["slot"] == "weapon")
    rep_armor = next(a for a in repair_actions if a["slot"] == "armor")
    assert rep_weapon["cost"] == 1
    assert rep_armor["cost"] == 2

    # Perform Blacksmith repair on weapon
    BE.apply_town_action(hero, rep_weapon, purchase_queue)
    assert hero.gold == 9  # 10 - 1
    assert "weapon" not in hero.equipment_broken
    assert "armor" in hero.equipment_broken  # armor still broken

    # Perform Blacksmith repair on armor
    BE.apply_town_action(hero, rep_armor, purchase_queue)
    assert hero.gold == 7  # 9 - 2
    assert "armor" not in hero.equipment_broken
    assert len(hero.equipment_broken) == 0

    print("  Equipment breaking and Blacksmith repair OK.")


def test_27_class_boss_gauntlet():
    print("Testing 9-class x 3-boss gauntlet (27 combinations)...")
    classes = list(M.CARD_SOURCE.keys())
    bosses = BD.BOSS_IDS

    results_count = {}
    for class_name in classes:
        mod = M.CARD_SOURCE[class_name]
        max_hp = float(getattr(mod, M.HP_ATTR[class_name]))
        for boss_id in bosses:
            rng = random.Random(100 + len(class_name) + len(boss_id))
            hero = HeroBoardState(class_name=class_name, hp=max_hp, max_hp=max_hp,
                                   position=(4, None), bag=[None] * 9, locked=[False] * 9, xp=14)
            hero.acquired.add("mandatory")
            res = BE.resolve_boss_combat(hero, class_name, boss_id, rng)
            outcome = res["outcome"]
            assert outcome in ("triumph", "timeout_p2", "damage_fail_p1", "death_p2")
            assert hero.position == (5, "town")
            assert "completed_citadel_commission" in hero.acquired
            results_count[outcome] = results_count.get(outcome, 0) + 1

    print(f"  Gauntlet resolved 27 encounters: {results_count}")
    assert results_count.get("triumph", 0) > 0
    print("  27-combination gauntlet OK.")


if __name__ == "__main__":
    test_boss_data_profiles()
    test_scout_tokens()
    test_capstone_trainer_grant()
    test_p1_damage_fail()
    test_p2_triumph_and_spoils()
    test_death_breaks_equipment_and_blacksmith_repairs()
    test_27_class_boss_gauntlet()
    print("\nALL BOSS ENGINE VERIFICATION TESTS PASSED SUCCESSFULLY!")
