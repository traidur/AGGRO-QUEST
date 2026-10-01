"""One-off: sweep candidate purchased-upgrade combinations for Runecaster's Level 2 slate,
after the 2026-08-30 rebalance (Chain Lightning 6->4, Call of the Glacier 3->4) plus a same-day
mob-Block-pooling engine fix (affects Echo cards specifically -- Earth Strike Rune is one of
Runecaster's 4 upgraded cards) shifted its win margin from a recorded +1.2 to a freshly-measured
-1.6. Mandatory (Tidal Ward [Lv 2]) held fixed throughout -- it's the class's diagnosed
defense-floor fix, not part of this investigation. Never touches condensed_runecaster.py's own
CARDS (Level 1 values stay exactly as locked)."""
import condensed_trip as T
import condensed_runecaster as N
import leveling_validation as LV

label = "Runecaster"
mod = T.CARD_SOURCE_BY_LABEL[label]
has_stance = T.HAS_STANCE_BY_LABEL[label]
max_hp = float(getattr(mod, T.HP_ATTR_BY_LABEL[label]))
mob_key = T.MOB_KEY_BY_LABEL[label]

MANDATORY = ("Tidal Ward", "Tidal Ward [Lv 2]",
             dict(dmg=0, heal=2, block=3, grants_range=False, chain_bonus_if_prev=None,
                  chain_bonus_dmg=0, echo_dmg=0, echo_heal=0, aggro=1))

CANDIDATES = {
    "LightningBolt_dmg4": ("Lightning Bolt", "Lightning Bolt [Lv 2]",
        dict(dmg=4, heal=0, block=0, grants_range=False, chain_bonus_if_prev="Chain Lightning",
             chain_bonus_dmg=0, echo_dmg=0, echo_heal=0, aggro=2)),
    "EarthStrike_echo2": ("Earth Strike Rune", "Earth Strike Rune [Lv 2]",
        dict(dmg=2, heal=1, block=0, grants_range=False, chain_bonus_if_prev=None,
             chain_bonus_dmg=0, echo_dmg=2, echo_heal=1, aggro=0)),
    "EarthStrike_dmg3": ("Earth Strike Rune", "Earth Strike Rune [Lv 2]",
        dict(dmg=3, heal=1, block=0, grants_range=False, chain_bonus_if_prev=None,
             chain_bonus_dmg=0, echo_dmg=1, echo_heal=1, aggro=0)),
    "Windstrike_dmg6": ("Windstrike", "Windstrike [Lv 2]",
        dict(dmg=6, heal=0, block=0, grants_range=False, chain_bonus_if_prev=None,
             chain_bonus_dmg=0, echo_dmg=0, echo_heal=0, aggro=3)),
    "Windstrike_dmg7": ("Windstrike", "Windstrike [Lv 2]",
        dict(dmg=7, heal=0, block=0, grants_range=False, chain_bonus_if_prev=None,
             chain_bonus_dmg=0, echo_dmg=0, echo_heal=0, aggro=3)),
    "ChainLightning_dmg5": ("Chain Lightning", "Chain Lightning [Lv 2]",
        dict(dmg=5, heal=0, block=0, grants_range=False, chain_bonus_if_prev=None,
             chain_bonus_dmg=0, echo_dmg=0, echo_heal=0, aggro=3)),
    "CallGlacier_dmg5": ("Call of the Glacier", "Call of the Glacier [Lv 2]",
        dict(dmg=5, heal=0, block=0, grants_range=True, chain_bonus_if_prev=None,
             chain_bonus_dmg=0, echo_dmg=0, echo_heal=0, aggro=3)),
}

COMBOS = {
    "A: current locked (LB4+ESR-echo2+WS6)": ["LightningBolt_dmg4", "EarthStrike_echo2", "Windstrike_dmg6"],
    "B: LB4+ESR-echo2+WS7": ["LightningBolt_dmg4", "EarthStrike_echo2", "Windstrike_dmg7"],
    "C: LB4+ESR-dmg3+WS6": ["LightningBolt_dmg4", "EarthStrike_dmg3", "Windstrike_dmg6"],
    "D: LB4+WS6+ChainLightning5": ["LightningBolt_dmg4", "Windstrike_dmg6", "ChainLightning_dmg5"],
    "E: LB4+WS6+CallGlacier5": ["LightningBolt_dmg4", "Windstrike_dmg6", "CallGlacier_dmg5"],
    "F: ESR-echo2+WS6+ChainLightning5": ["EarthStrike_echo2", "Windstrike_dmg6", "ChainLightning_dmg5"],
    "G: ESR-echo2+WS7+ChainLightning5": ["EarthStrike_echo2", "Windstrike_dmg7", "ChainLightning_dmg5"],
    "H: WS7+ChainLightning5+CallGlacier5": ["Windstrike_dmg7", "ChainLightning_dmg5", "CallGlacier_dmg5"],
}


def measure(purchased_keys):
    l1_cost = LV.cost_pct_for_level(mod, has_stance, max_hp, mob_key, level=1)
    l1_win = LV.win_rate_for_level(mod, has_stance, max_hp, mob_key, level=1)
    l1_pulls = LV.pulls_before_death(mod, has_stance, max_hp, mob_key, level=1, trials=3000)

    swaps = {}
    old_name, new_name, new_card = MANDATORY
    swaps[old_name] = (new_name, new_card)
    for key in purchased_keys:
        old_name, new_name, new_card = CANDIDATES[key]
        swaps[old_name] = (new_name, new_card)

    with LV.leveled_kit(mod, swaps):
        l2_cost = LV.cost_pct_for_level(mod, has_stance, max_hp, mob_key, level=2)
        l2_win = LV.win_rate_for_level(mod, has_stance, max_hp, mob_key, level=2)
        l2_pulls = LV.pulls_before_death(mod, has_stance, max_hp, mob_key, level=2, trials=3000)

    return l1_cost - l2_cost, l2_win - l1_win, l2_pulls - l1_pulls


if __name__ == "__main__":
    print(f"{'Combo':<42}{'cost':>8}{'win':>8}{'pulls':>8}")
    print(f"{'(target)':<42}{'-0.6':>8}{'+1.2':>8}{'+0.29':>8}")
    for name, keys in COMBOS.items():
        cost, win, pulls = measure(keys)
        print(f"{name:<42}{cost:>8.1f}{win:>8.1f}{pulls:>8.2f}")
