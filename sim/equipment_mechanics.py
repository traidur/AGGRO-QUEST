# Reinforced's flat single-round Block bonus by armor weight -- trimmed from the original
# +2/+3/+4 to +1/+2/+3 (locked with the user 2026-09-08) after the sweep showed the old values
# made Reinforced the single strongest item in several classes' entire armor track, outright
# beating multiple Level 2 items it was supposed to sit below.
REINFORCED_BLOCK = {"Light": 1, "Medium": 2, "Heavy": 3}

# Persistent, rebuilt as a weight-scaled Echo (locked 2026-09-08) -- replaces the old "carries
# leftover Block into next round" design, which measured at a flat 0.0pp for Warrior and was
# the weakest item in Paladin's kit: leftover block is worthless exactly when a hero is in
# danger and has none to spare. The new version grants Reinforced's own this-round bonus PLUS
# an automatic, unconditional bonus next round (no card spent, same shape as Blight/Earth
# Strike Rune's Echo) -- tempered down at higher weights rather than a flat doubling, since a
# full second copy of Reinforced's bonus would compound Block+Echo on the same weight axis
# that already produced the highest single-item values in the sweep, which is the exact
# "Block/Echo interaction quietly produces a cannot-die result" failure mode EQUIPMENT_GUIDE.md
# named from this item's very first draft (already hit twice elsewhere in this project: Cleric,
# then Runecaster).
PERSISTENT_THIS_ROUND = {"Light": 1, "Medium": 2, "Heavy": 3}
PERSISTENT_NEXT_ROUND = {"Light": 1, "Medium": 1, "Heavy": 2}


def _weight_class(base):
    for weight in ("Light", "Medium", "Heavy"):
        if weight in base:
            return weight
    return None


def apply_equipment_mechanics(outcome, rider, base, round_num, equip_round, mob_pattern, state_tracker=None, grants_range=False):
    """
    outcome: RoundOutcome
    rider: str (e.g. "honed", "ruthless")
    base: str (e.g. "1-Hander", "Heavy Armor")
    round_num: int
    equip_round: int (when it was activated)
    state_tracker: dict for cross-round effects (sunder, persistent's echo)
    grants_range: whether THIS round's card granted At Range (read from the card's own
        CARDS[...]["grants_range"] field by the caller) -- Thorns' trigger condition (locked
        2026-09-08, replacing "only fires if you actually took damage"): reflects damage
        whenever the hero is in melee (not At Range) this round, regardless of whether the
        mob's attack connected. The old dmg_taken>0 gate meant Thorns only ever fired on
        rounds that were already going wrong; this fires in the normal case and only skips
        the (for most classes, nonexistent) At-Range rounds.
    """
    if state_tracker is None: state_tracker = {}

    new_dmg = outcome.raw_dmg
    block = outcome.block
    heal = outcome.heal
    pat = mob_pattern[round_num] if round_num < len(mob_pattern) else (0, 0, "melee")
    mob_atk, mob_block = pat[0], pat[1]
    mob_type = pat[2] if len(pat) > 2 else "melee"

    is_active_round = (round_num == equip_round)

    # 1. Apply Persistent's echoed Block from a PRIOR round's activation -- unconditional, no
    # card spent, resolves at the start of the round exactly like Blight/Earth Strike Rune's
    # own Echo. Popped (not just read) so it only ever fires once per activation.
    pending_echo = state_tracker.pop("persistent_echo_block", 0)
    if pending_echo:
        block += pending_echo

    # 2. Apply Sunder from previous or current rounds
    if state_tracker.get("sunder_active", False) or (is_active_round and rider == "sunder"):
        if is_active_round and rider == "sunder":
            state_tracker["sunder_active"] = True
        new_dmg += 1

    # Apply Active Round effects
    if is_active_round:
        if rider == "honed":
            new_dmg += 1 if base in ["1-Hander", "Wand"] else 2
        elif rider == "blessed":
            heal += 1
        elif rider == "greater_blessed":
            heal += 2
        elif rider == "reinforced":
            block += REINFORCED_BLOCK.get(_weight_class(base), 0)
        elif rider == "persistent":
            weight = _weight_class(base)
            block += PERSISTENT_THIS_ROUND.get(weight, 0)
            state_tracker["persistent_echo_block"] = PERSISTENT_NEXT_ROUND.get(weight, 0)

    # Calculate new outcome
    dmg_dealt = max(0.0, new_dmg - mob_block)
    
    if is_active_round and rider == "pierce":
        reduced_block = max(0, mob_block - 2)
        dmg_dealt = max(0.0, new_dmg - reduced_block)
        
    new_rem = outcome.new_mob_hp_remaining + outcome.dmg_dealt - dmg_dealt
    
    dmg_taken = max(0.0, mob_atk - block)
    
    if is_active_round and rider == "elusive" and mob_type == "melee":
        dmg_taken = 0.0
    if is_active_round and rider == "ruthless" and new_rem <= 0:
        dmg_taken = 0.0
        
    if is_active_round and rider == "thorns" and not grants_range:
        thorns_dmg = 2 if "Medium" in base else 3
        new_rem -= thorns_dmg

    new_hp = outcome.new_hp + outcome.dmg_taken - outcome.heal - dmg_taken + heal
    new_hp = min(new_hp, outcome.new_hero_max_hp)

    from dataclasses import replace
    return replace(outcome, new_hp=new_hp, new_mob_hp_remaining=new_rem, dmg_dealt=dmg_dealt, dmg_taken=dmg_taken, raw_dmg=new_dmg, block=block, heal=heal)
