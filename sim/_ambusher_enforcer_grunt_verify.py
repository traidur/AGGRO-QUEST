"""Full-trial A/B verification for the 3-mob combination (Ambusher +
Enforcer + Grunt changed simultaneously, Scout/Raider/Bruiser left at
their original Level 1 patterns)."""
import condensed_trip as T

CHANGES = {
    "Ambusher": [(4, 0), (4, 1), (2, 0)],
    "Enforcer": [(5, 1), (3, 1), (4, 2)],
    "Grunt": [(3, 0), (2, 2), (3, 0)],
}


def rebuild_mobs():
    T.MOBS = {
        name: dict(
            warrior=(pattern, hp),
            wizard=([(a, b, T._MOB_TYPES.get(name, "melee")) for a, b in pattern], hp),
            cleric=(pattern, hp),
            paladin=(pattern, hp),
            rogue=([(a, b, T._MOB_TYPES.get(name, "melee")) for a, b in pattern], hp),
            ranger=([(a, b, T._MOB_TYPES.get(name, "melee")) for a, b in pattern], hp),
            runecaster=([(a, b, T._MOB_TYPES.get(name, "melee")) for a, b in pattern], hp),
            druid=(pattern, hp),
            necromancer=([(a, b, T._MOB_TYPES.get(name, "melee")) for a, b in pattern], hp),
        )
        for name, (pattern, hp) in T._RAW_MOBS.items()
    }
    T.MOB_NAMES = list(T.MOBS.keys())


print("### BASELINE (current locked roster, all 6 mobs original) ###")
before = T.full_report(trials=1500, seed=42)

for name, new_pattern in CHANGES.items():
    _, hp = T._RAW_MOBS[name]
    T._RAW_MOBS[name] = (new_pattern, hp)
rebuild_mobs()

print()
print("### AFTER (Ambusher + Enforcer + Grunt changed together) ###")
after = T.full_report(trials=1500, seed=42)

print()
T.compare_reports(before, after, "Level 1 (all original)", "Level 2 (Ambusher+Enforcer+Grunt variants)")
