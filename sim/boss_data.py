"""
boss_data.py -- Authoritative specifications and helpers for Zone 4 Tier Gate Bosses.
From DESIGN_DOC.md Section VIII.4 (Locked Specifications 2026-10-02/2026-10-06).

Three Gatekeeper Bosses:
1. High Inquisitor Malakor / The Sunward Archon (Anti-Caster / Pure Ranged P1)
2. Citadel Colossus / Aethelgard the Sun-Forged (The Granite Titan / Anti-Melee Slams)
3. Eclipse Sovereign / Cheryl the Sun-Dethroned (The Twilight Duelist / Twilight Guillotine)
"""

from typing import Dict, List, Tuple, Any
import condensed_trip as T

# Qualification and Capstone constants
CAPSTONE_XP_THRESHOLD = 14
CAPSTONE_QUEST_NAME = "The Citadel Commission"
CAPSTONE_ZONES = frozenset({4})
CAPSTONE_LANDMARK_NODES = ("gleaming_citadel", "sunward_throne")

# Spoils and rewards
TRIUMPH_GOLD = 5
TRIUMPH_BOUNTY_CREDITS = 2
TRIUMPH_KEY = "level3_dungeon_key"
TRIUMPH_TROPHY = "boss_trophy"

# Boss profiles
BOSSES: Dict[str, Dict[str, Any]] = {
    "malakor": {
        "id": "malakor",
        "title": "High Inquisitor Malakor",
        "subtitle": "The Sunward Archon",
        "archetype": "Anti-Caster / Holy Mage-Hunter",
        "flavor": (
            "Radiant prelate radiating continuous holy light. Heavy Ranged magic attacks deny "
            "distance evasion, directly challenging low-HP casters while physical armor and "
            "heavy shields soak the rays."
        ),
        "p1": {
            "name": "The Radiant Bulwark",
            "hp": 10,
            "pattern": ((4, 0), (3, 1), (4, 0)),
            "types": ("ranged", "ranged", "ranged"),
            "abilities": ("Holy Ray", "Consecrated Radiance", "Solar Flare"),
        },
        "p2": {
            "name": "Unleashed Avatar of Light",
            "hp": 10,
            "pattern": ((4, 0), (4, 0), (5, 0)),
            "types": ("ranged", "ranged", "melee"),
            "abilities": ("Pillar of Radiance", "Sunward Searing", "Avatar's Wrath"),
        },
    },
    "colossus": {
        "id": "colossus",
        "title": "Citadel Colossus",
        "subtitle": "Aethelgard the Sun-Forged",
        "archetype": "The Granite Titan / Anti-Melee",
        "flavor": (
            "Ancient granite titan. Crushing 5-damage melee slams and heavy stone plating "
            "shatter close-combat brawlers, but slow movement leaves it vulnerable to ranged "
            "artillery and magic pierce."
        ),
        "p1": {
            "name": "Granite Sentinel",
            "hp": 10,
            "pattern": ((3, 2), (5, 0), (4, 0)),
            "types": ("melee", "melee", "ranged"),
            "abilities": ("Heavy Stone Bracing", "Crushing Fist Slam", "Prismatic Eye Beam"),
        },
        "p2": {
            "name": "Superheated Molten Core",
            "hp": 10,
            "pattern": ((5, 0), (4, 1), (4, 0)),
            "types": ("melee", "melee", "ranged"),
            "abilities": ("Molten Hammer", "Core Reinforcement", "Thermal Steam Vent"),
        },
    },
    "eclipse": {
        "id": "eclipse",
        "title": "Eclipse Sovereign",
        "subtitle": "Cheryl the Sun-Dethroned",
        "archetype": "The Twilight Duelist / Anti-Attrition",
        "flavor": (
            "Fallen solar monarch. Parries with dual eclipse rapiers in melee, dropping guard "
            "to unleash sweeping dark solar magic before executing stalling heroes with a "
            "Round 6 Guillotine."
        ),
        "p1": {
            "name": "Dusk Rapier",
            "hp": 10,
            "pattern": ((4, 1), (4, 0), (5, 0)),
            "types": ("melee", "ranged", "melee"),
            "abilities": ("Twin Rapier Parry", "Eclipse Javelin", "Shadowstep Thrust"),
        },
        "p2": {
            "name": "Twilight Ascendant",
            "hp": 9,
            "pattern": ((4, 0), (4, 1), (6, 0)),
            "types": ("ranged", "melee", "melee"),
            "abilities": ("Black Sun Nova", "Dusk Guard", "Twilight Guillotine!"),
        },
    },
}

BOSS_IDS = list(BOSSES.keys())


def get_phase_pattern_hp(boss_id: str, phase_num: int, class_name: str) -> Tuple[List[Tuple], int]:
    """
    Returns (pattern, mob_hp) for the specified boss phase formatted for the given class.
    For range-sensitive classes (wizard, rogue, ranger, runecaster, necromancer), pattern items
    are (atk, blk, mob_combat_type). For other classes, pattern items are (atk, blk).
    """
    boss = BOSSES[boss_id]
    phase_data = boss["p1"] if phase_num == 1 else boss["p2"]
    raw_pat = phase_data["pattern"]
    types = phase_data["types"]
    hp = phase_data["hp"]

    if class_name in T._RANGE_TAGGED_MOB_KEYS:
        pattern = [(raw_pat[i][0], raw_pat[i][1], types[i]) for i in range(3)]
    else:
        pattern = [(raw_pat[i][0], raw_pat[i][1]) for i in range(3)]
    return pattern, hp


def draw_bosses(rng, scout_token: bool = False) -> Tuple[str, List[str]]:
    """
    Draws boss candidate(s) from the trio.
    If scout_token is True: draws 2 unique candidates (caller picks 1).
    If scout_token is False: draws 1 candidate at random.
    Returns (chosen_or_first_boss_id, candidate_boss_ids).
    """
    candidates = rng.sample(BOSS_IDS, 2 if scout_token else 1)
    return candidates[0], candidates


# Locked Cross-Boss Matchup Matrix (DESIGN_DOC.md Section VIII.4)
MATCHUP_WIN_RATES: Dict[str, Dict[str, float]] = {
    "malakor": {
        "warrior": 0.944, "paladin": 0.960, "wizard": 0.696, "rogue": 0.881,
        "ranger": 0.748, "necromancer": 0.529, "druid": 0.933, "runecaster": 0.572, "cleric": 0.778
    },
    "colossus": {
        "warrior": 0.809, "paladin": 0.796, "wizard": 0.855, "rogue": 0.610,
        "ranger": 0.698, "necromancer": 0.810, "druid": 0.530, "runecaster": 0.581, "cleric": 0.409
    },
    "eclipse": {
        "warrior": 0.858, "paladin": 0.797, "wizard": 0.902, "rogue": 0.881,
        "ranger": 0.834, "necromancer": 0.898, "druid": 0.704, "runecaster": 0.704, "cleric": 0.508
    },
}


def best_boss_for_class(class_name: str, candidates: List[str]) -> str:
    """Returns the candidate boss with the highest baseline win rate for class_name."""
    return max(candidates, key=lambda b: MATCHUP_WIN_RATES.get(b, {}).get(class_name, 0.5))

