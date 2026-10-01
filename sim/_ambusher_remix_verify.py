"""Full-trial re-verification of the winning candidate from
_level2_mob_remix_search.py's search pass (footprint=2.06, the lowest found
across all 6 Standard mobs' round-order permutations): Ambusher's Level 2
appearance gets [(4,0),(4,1),(2,0)] instead of the Level 1 [(4,1),(4,0),(2,0)]
-- same front-loaded-then-fading shape (4,4,2 damage), Block just moves from
round 1 to round 2. Uses condensed_trip.full_report()/compare_reports() at
the real trial count, not the search pass's lighter/faster diagnostic."""
import condensed_trip as T

print("### BASELINE (current locked roster, Ambusher unmodified) ###")
before = T.full_report(trials=1500, seed=42)

T._RAW_MOBS["Ambusher"] = ([(4, 0), (4, 1), (2, 0)], 8)
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

print()
print("### AFTER (Ambusher's Level 2 variant: Block moved round 1 -> round 2) ###")
after = T.full_report(trials=1500, seed=42)

print()
T.compare_reports(before, after, "Level 1 Ambusher", "Level 2 Ambusher variant")
