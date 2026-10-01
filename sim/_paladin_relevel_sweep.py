"""One-off: sweep candidate purchased-upgrade combinations for Paladin's Level 2 slate, after
the 2026-08-30 base-kit rebalance invalidated the original locked numbers (see
LEVELING_GUIDE.md's Paladin section investigation, 2026-09-04). Never touches condensed_paladin.py's
own CARDS (Level 1 values stay exactly as locked) -- every candidate here is a leveled_kit swap
only. Mandatory (Invoking Aura of Sanctuary, grants_aura_block now decoupled to its own
INVOCATION_AURA_BLOCK_BONUS=1 constant) is held fixed across all combos; only the 3 purchased
slots vary. Reference targets (locked pre-rebalance): cost +0.7, win -0.7, pulls +0.55."""
import condensed_trip as T
import condensed_paladin as P
import leveling_validation as LV

label = "Paladin"
mod = T.CARD_SOURCE_BY_LABEL[label]
has_stance = T.HAS_STANCE_BY_LABEL[label]
max_hp = float(getattr(mod, T.HP_ATTR_BY_LABEL[label]))
mob_key = T.MOB_KEY_BY_LABEL[label]

MANDATORY = ("Invocation of Sanctuary", "Invoking Aura of Sanctuary",
             dict(dmg=3, heal=0, block=1, strike=False, invocation="sanctuary", aggro=3,
                  grants_aura_block=True))

# Candidate purchased upgrades -- current base values are dmg-only bumps unless noted.
CANDIDATES = {
    "Might_dmg4":     ("Might of the Aegis", "Might of the Aegis [Lv 2]",
                        dict(dmg=4, heal=0, block=2, strike=True, invocation=None, aggro=4, grants_aura_block=False)),
    "Bastion_dmg5":   ("Bastion's Hammer", "Bastion's Breaker",
                        dict(dmg=5, heal=0, block=0, strike=True, invocation=None, aggro=2, grants_aura_block=False)),
    "Bastion_dmg6":   ("Bastion's Hammer", "Bastion's Breaker",
                        dict(dmg=6, heal=0, block=0, strike=True, invocation=None, aggro=2, grants_aura_block=False)),
    "Grace_dmg5":     ("Invocation of Grace", "Invocation of Grace [Lv 2]",
                        dict(dmg=5, heal=0, block=0, strike=False, invocation="grace", aggro=3, grants_aura_block=False)),
    "Vigil_heal4":    ("Vigil of Light", "Sanctified Light",
                        dict(dmg=0, heal=4, block=1, strike=False, invocation=None, aggro=2, grants_aura_block=False)),
    "HolyFortress_dmg4": ("Holy Fortress", "Holy Fortress [Lv 2]",
                        dict(dmg=4, heal=0, block=4, strike=False, invocation=None, aggro=4, grants_aura_block=False)),
}

COMBOS = {
    "A: Might+Grace+Bastion(5)": ["Might_dmg4", "Grace_dmg5", "Bastion_dmg5"],
    "B: Might+Grace+Bastion(6)": ["Might_dmg4", "Grace_dmg5", "Bastion_dmg6"],
    "C: Might+Grace+Vigil": ["Might_dmg4", "Grace_dmg5", "Vigil_heal4"],
    "D: Might+Bastion(5)+Vigil": ["Might_dmg4", "Bastion_dmg5", "Vigil_heal4"],
    "E: Might+HolyFortress+Grace": ["Might_dmg4", "HolyFortress_dmg4", "Grace_dmg5"],
    "F: Grace+Bastion(5)+Vigil": ["Grace_dmg5", "Bastion_dmg5", "Vigil_heal4"],
    "G: Might+Bastion(6)+Vigil": ["Might_dmg4", "Bastion_dmg6", "Vigil_heal4"],
}


def measure(purchased_keys, mandatory_block=1):
    mand = ("Invocation of Sanctuary", "Invoking Aura of Sanctuary",
            dict(dmg=3, heal=0, block=mandatory_block, strike=False, invocation="sanctuary", aggro=3,
                 grants_aura_block=True))
    l1_cost = LV.cost_pct_for_level(mod, has_stance, max_hp, mob_key, level=1)
    l1_win = LV.win_rate_for_level(mod, has_stance, max_hp, mob_key, level=1)
    l1_pulls = LV.pulls_before_death(mod, has_stance, max_hp, mob_key, level=1, trials=3000)

    swaps = {}
    old_name, new_name, new_card = mand
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
    print(f"{'Combo':<32}{'cost margin':>12}{'win margin':>12}{'pulls margin':>14}")
    print(f"{'(target)':<32}{'+0.7':>12}{'-0.7':>12}{'+0.55':>14}")
    for name, keys in COMBOS.items():
        cost, win, pulls = measure(keys)
        print(f"{name:<32}{cost:>12.1f}{win:>12.1f}{pulls:>14.2f}")

    print()
    print("=== Mandatory block=0 variant (grants_aura_block only, no flat block bump) ===")
    for name, keys in COMBOS.items():
        cost, win, pulls = measure(keys, mandatory_block=0)
        print(f"{name:<32}{cost:>12.1f}{win:>12.1f}{pulls:>14.2f}")
