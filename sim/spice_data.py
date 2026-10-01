"""
SPICE_DATA: Complete registry and resolution engine for the 16-card Universal Fantasy Spice Deck.
Locked 2026-09-30.

Level 1 Mob Deck contains 1 random Spice card (1/19 cards, ~5.3%).
Level 2 Mob Deck contains 2 random Spice cards (2/23 cards, ~8.7%).

Zone Level scaling:
  Zone 1 & 2 (Level 1) -> Zone Level = 1
  Zone 3 & 4 (Level 2) -> Zone Level = 2
  Zone 5 & 6 (Level 3) -> Zone Level = 3
"""

import random

# The 16 cards shuffled into the setup Spice Deck
SPICE_DECK = [
    "scuttling_hoarder",
    "warded_strongbox",
    "sacred_well",
    "forgotten_passage",
    "dead_scouts_map",
    "ruined_watchtower",
    "wandering_hermit",
    "runic_monolith",
    "abandoned_hearth",
    "masters_forge",
    "wandering_peddler",
    "trappers_cache",
    "alchemists_alembic",
    "monstrous_clutch",
    "couriers_satchel",
    "arcane_golem",
]

# Combat spawns that resolve via combat_engine
SPICE_COMBAT_SPAWNS = {
    "scuttling_hoarder",
    "warded_strongbox",
    "monstrous_clutch",
    "broodmother",
    "arcane_golem",
}

# Adventure events that resolve via interactive choices or direct triggers
SPICE_EVENTS = {
    "sacred_well",
    "forgotten_passage",
    "dead_scouts_map",
    "ruined_watchtower",
    "wandering_hermit",
    "runic_monolith",
    "abandoned_hearth",
    "masters_forge",
    "wandering_peddler",
    "trappers_cache",
    "alchemists_alembic",
    "couriers_satchel",
}

SPICE_CARDS = set(SPICE_DECK) | {"broodmother"}

# Combat mob stat profiles: (raw_pattern, hp, max_rounds)
SPICE_MOB_STATS = {
    "scuttling_hoarder": ([(2, 0), (2, 0), (0, 0)], 5, 2),  # Flees after Round 2
    "warded_strongbox": ([(0, 0), (0, 0), (0, 0)], 14, 3), # Damage race
    "monstrous_clutch": ([(4, 0), (3, 0), (3, 0)], 8, 3),  # Broodmother combat
    "broodmother": ([(4, 0), (3, 0), (3, 0)], 8, 3),       # Average ~4.08 HP damage taken
    "arcane_golem": ([(0, 2), (3, 0), (4, 0)], 10, 3),     # Charges Round 1, strikes R2/R3
}

# The 3 new 1x1 Delivery Bag Tokens
SPICE_DELIVERY_TOKENS = {
    "couriers_satchel",
    "beast_egg",
    "gilded_relic",
}

HERB_TOKENS = {"Snap-Root", "River-Mint", "Astral-Moss", "Scorch-Blossom", "Lantern-Spore", "Tyrant's-Crest"}
ORE_TOKENS = {"Crag-Iron", "Sun-Copper", "Ember-Vein Ore", "Glacier-Metal", "Nether-Slag", "Crown-Gold"}


def zone_level_for_zone(zone_id):
    """Computes Zone Level: Zones 1 & 2 = 1, Zones 3 & 4 = 2, Zones 5 & 6 = 3."""
    if isinstance(zone_id, int):
        return (zone_id - 1) // 2 + 1
    return 1


def is_spice(card_name):
    if not card_name:
        return False
    base = card_name.replace("_loot", "")
    return base in SPICE_CARDS or base == "__spice__"


def is_spice_combat(card_name):
    if not card_name:
        return False
    base = card_name.replace("_loot", "")
    return base in SPICE_COMBAT_SPAWNS


def is_spice_event(card_name):
    if not card_name:
        return False
    base = card_name.replace("_loot", "")
    return base in SPICE_EVENTS


def get_spice_display_name(card_name):
    base = card_name.replace("_loot", "")
    names = {
        "scuttling_hoarder": "The Scuttling Hoarder",
        "warded_strongbox": "The Warded Strongbox",
        "sacred_well": "The Sacred Well",
        "forgotten_passage": "Forgotten Passage",
        "dead_scouts_map": "The Dead Scout's Map",
        "ruined_watchtower": "The Ruined Watchtower",
        "wandering_hermit": "The Wandering Hermit",
        "runic_monolith": "The Runic Monolith",
        "abandoned_hearth": "The Abandoned Hearth",
        "masters_forge": "The Master's Forge",
        "wandering_peddler": "The Wandering Peddler",
        "trappers_cache": "The Trapper's Cache",
        "alchemists_alembic": "The Alchemist's Field Alembic",
        "monstrous_clutch": "The Monstrous Clutch",
        "broodmother": "The Broodmother",
        "couriers_satchel": "The Courier's Satchel",
        "arcane_golem": "The Arcane Golem",
    }
    return names.get(base, base.replace("_", " ").title())


def get_spice_pattern_hp(class_name, mob_name):
    """Returns (pattern, hp) for a Spice combat spawn tailored to class_name."""
    base = mob_name.replace("_loot", "")
    if base not in SPICE_MOB_STATS:
        raise ValueError(f"Unknown Spice combat mob: {mob_name}")
    raw_pattern, hp, _max_r = SPICE_MOB_STATS[base]
    # Check if class requires 3-tuple pattern (range tag)
    range_classes = {"wizard", "rogue", "ranger", "runecaster", "necromancer"}
    if class_name in range_classes:
        pattern = [(atk, blk, "melee") for atk, blk in raw_pattern]
    else:
        pattern = [(atk, blk) for atk, blk in raw_pattern]
    return pattern, hp


def get_spice_max_rounds(mob_name):
    base = mob_name.replace("_loot", "")
    if base in SPICE_MOB_STATS:
        return SPICE_MOB_STATS[base][2]
    return 3
