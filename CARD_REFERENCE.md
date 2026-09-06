# QUEST -- Card Reference

Generated directly from each class's real `CARDS` dict in `sim/condensed_<class>.py` -- regenerate with `python generate_card_reference.py` after any card change rather than hand-editing this file, so it can never drift out of sync with what the solver actually runs. Aggro is the co-op Party Pull targeting value (0-4) -- see `OPEN_QUESTIONS.md`'s "Co-op multi-hero vs. Elite/multi-mob nodes" entry. `v#` is the card's printed-revision number -- compare against your physical deck to see which cards need reprinting after a rebalance.

## Warrior (HP 18)

*Guardian/Champion stance, locked once per pull. Sundering Blow stacks +2 damage on all later damaging cards. Vanguard Shield/Blade reward playing them back-to-back in the right stance.*

**Heavy Swing** [RANGED] -- **Guardian:** 2 DMG, 0 Block. **Champion:** 4 DMG, 0 Block. (Aggro 2 v2)

**Sundering Blow** [MELEE | SUNDER] -- **Guardian:** 1 DMG, 0 Block. **Champion:** 1 DMG, 0 Block. Marks the mob Sundered: all your later damaging cards this pull deal +2 DMG. (Aggro 4 v1)

**Execute** [RANGED | KILLING BLOW] -- 6 DMG. Only playable once the mob is at 50% HP or lower. If this kills the mob, its attack this round is prevented. **PvP:** Playable at any time in PvP duels -- the 50% HP requirement doesn't apply. (Aggro 3 v3)

**Vanguard Shield** [MELEE | COMBO] -- **Guardian:** 2 DMG, 2 Block. **Champion:** 2 DMG, 2 Block. **Guardian only:** if the previous round's card was Vanguard Blade, +2 Block. (Aggro G:4 / C:2 v1)

**Shield Block** [MELEE] -- **Guardian:** 0 DMG, 5 Block. **Champion:** 0 DMG, 0 Block. (Aggro G:4 / C:0 v1)

**Vanguard Blade** [MELEE | COMBO] -- **Guardian:** 3 DMG, 2 Block. **Champion:** 3 DMG, 0 Block. **Champion only:** if the previous round's card was Vanguard Shield, +2 DMG. (Aggro 3 v1)


## Wizard (HP 14)

*Weave: playing a Weave-source card arms a one-time damage boost for the next payoff card. Positioning: At Range evades a melee mob's attack entirely.*

**Fire Blast** [RANGED | SPELLWEAVE: SOURCE] -- 3 DMG. Arms Weave: your next eligible payoff card gets its boosted damage. (Aggro 1 v1)

**Arcane Volley** [RANGED | SPELLWEAVE] -- 6 DMG (7 DMG if Weave is armed). (Aggro 3 v2)

**Snap Freeze** [MELEE | AT RANGE | SPELLWEAVE: SOURCE] -- 1 DMG. 1 Block. Grants At Range this round (evades a melee mob's attack). Arms Weave: your next eligible payoff card gets its boosted damage. (Aggro 3 v1)

**Ice Barricade** [MELEE | SPELLWEAVE: SOURCE] -- 10 Block. Arms Weave: your next eligible payoff card gets its boosted damage. (Aggro 2 v1)

**Fire Ball** [RANGED | SPELLWEAVE] -- 5 DMG (7 DMG if Weave is armed). (Aggro 3 v1)

**Frozen Shot** [RANGED | AT RANGE | SPELLWEAVE] -- 2 DMG (5 DMG if Weave is armed). Grants At Range this round (evades a melee mob's attack). (Aggro 3 v2)


## Cleric (HP 14)

*Sacred Balance: Smite automatically heals a small flat amount on top of its damage. Cleansing Barrier and Fiery Fortitude carry incidental damage riders to keep a real damage floor.*

**Void Mark** [RANGED] -- 3 DMG. (Aggro 1 v1)

**Smite** [RANGED | SACRED BALANCE] -- 5 DMG. Triggers Sacred Balance: heal 1 HP automatically. (Aggro 2 v1)

**Call of the Void** [RANGED] -- 5 DMG. (Aggro 3 v2)

**Cleansing Barrier** [MELEE] -- 3 DMG. 5 Block. (Aggro 1 v1)

**Fiery Fortitude** [MELEE] -- 3 DMG. Heal 2 HP. +2 Max HP for the rest of this pull. (Aggro 2 v1)

**Heal** [RANGED] -- Heal 3 HP. (Aggro 3 v1)


## Paladin (HP 17)

*Invocation of Sanctuary/Grace -- pick exactly one per pull. Whichever is played first both pays off every STRIKE card already played and arms a bonus on every STRIKE card played afterward.*

**Might of the Aegis** [MELEE | STRIKE] -- 3 DMG. 2 Block. (Aggro 4 v2)

**Bastion's Hammer** [MELEE | STRIKE] -- 4 DMG. (Aggro 2 v2)

**Vigil of Light** [RANGED] -- Heal 3 HP. 1 Block. (Aggro 2 v2)

**Holy Fortress** [MELEE] -- 3 DMG. 4 Block. (Aggro 4 v2)

**Invocation of Sanctuary** [RANGED | INVOCATION] -- Deal 3 DMG, +2 DMG per STRIKE card already played earlier this pull. Every STRIKE card played afterward also deals +2 DMG when played. Only the first Invocation card played each pull gets any bonus (backward or forward) -- a second one is legal to play but deals/heals its flat base only and never becomes Active. (Aggro 3 v2)

**Invocation of Grace** [RANGED | INVOCATION] -- Deal 4 DMG. Heal 2 HP per STRIKE card already played earlier this pull. Every STRIKE card played afterward also heals +2 HP when played. Only the first Invocation card played each pull gets any bonus (backward or forward) -- a second one is legal to play but deals/heals its flat base only and never becomes Active. (Aggro 3 v2)


## Rogue (HP 15)

*Cutthroat/Envenom are finishers scaling off STRIKE cards played since your last finisher (0/1/2), resetting the count on use. Cutthroat alone carries a killing-blow rider.*

**Backstab and Dodge** [MELEE | STRIKE] -- 4 DMG. 2 Block. (Aggro 3 v1)

**Evasion** [MELEE] -- 0 DMG. 10 Block. (Aggro 1 v1)

**Quick Slash** [MELEE | STRIKE] -- 3 DMG. (Aggro 2 v1)

**Ambush** [RANGED | STRIKE | OPENER] -- 3 DMG (5 DMG if played in round 1). (Aggro 3 v2)

**Cutthroat** [MELEE | KILLING BLOW | FINISHER] -- Deals 2/3/6 DMG based on STRIKE cards played since your last finisher (0/1/2). Resets the count to 0. If this attack kills the mob, its attack this round is prevented. (Aggro 4 v1)

**Envenom** [RANGED | KILLING BLOW | FINISHER] -- Deals 3/4/5 DMG based on STRIKE cards played since your last finisher (0/1/2). Resets the count to 0. If this attack kills the mob, its attack this round is prevented. (Aggro 2 v1)


## Ranger (HP 15)

*Beast Bond: Wolf grants persistent Block every round for the rest of the pull once played. Sniper/Point Blank Shot rewards having granted At Range the previous round.*

**Beast Bond: Wolf** [MELEE | PET | PERSISTENT] -- 4 DMG. 1 Block. Activates the Wolf: from this round on (including this one), gain +1 Block every round for the rest of the pull, stacking with any Block your card grants that round. (Aggro 2 v1)

**Withdrawing Hip Shot** [RANGED | AT RANGE] -- 3 DMG. Grants At Range this round (evades a melee mob's attack). (Aggro 2 v2)

**Sniper/Point Blank Shot** [RANGED | COMBO] -- 5 DMG if the previous round's card granted At Range, 4 DMG otherwise. (Aggro 3 v2)

**Beast's Challenge** [MELEE | PET] -- 4 DMG if the Wolf is active, 2 DMG otherwise. (Aggro 3 v2)

**Sure Shot** [RANGED] -- 4 DMG. (Aggro 2 v1)

**Crippling Shot** [RANGED | AT RANGE] -- 2 DMG. 1 Block. Grants At Range this round (evades a melee mob's attack). (Aggro 3 v1)


## Runecaster (HP 16)

*Lightning Bolt rewards playing it right after Chain Lightning. Earth Strike Rune's damage and heal partially echo automatically at the start of the next round, no card spent.*

**Chain Lightning** [RANGED] -- 4 DMG. (Aggro 3 v2)

**Lightning Bolt** [RANGED | COMBO] -- 3 DMG. +1 DMG if the previous round's card was Chain Lightning. (Aggro 2 v1)

**Call of the Glacier** [RANGED | AT RANGE] -- 4 DMG. Grants At Range this round (evades a melee mob's attack). (Aggro 3 v2)

**Tidal Ward** [MELEE] -- Heal 2 HP. 2 Block. (Aggro 1 v1)

**Windstrike** [MELEE] -- 5 DMG. (Aggro 3 v1)

**Earth Strike Rune** [MELEE | ECHO] -- 2 DMG. Heal 1 HP. At the start of the next round, automatically deal 1 more DMG and heal 1 more HP (no card spent). (Aggro 0 v1)


## Druid (HP 15)

*Two mutually exclusive lines. Shapeshift: Grizzly boosts Maul/Swipe if played first, but cancels the Eclipse-stacking bonus (Solar Flare/Moonbeam/Nature's Wildguard) on any Eclipse card played after it.*

**Shapeshift: Grizzly** [MELEE | SHAPESHIFT] -- 2 DMG. 3 Block. Cancels the Eclipse-stacking bonus on any Eclipse-tagged card played in a later round. (Aggro 4 v1)

**Maul** [MELEE | SHAPESHIFT] -- 2 DMG. 2 Block. +1 DMG and +1 Block per Shapeshift-tagged card already played this pull (requires Shapeshift: Grizzly to have been played first). (Aggro 4 v1)

**Swipe** [MELEE | SHAPESHIFT] -- 3 DMG. +1 DMG and +1 Block per Shapeshift-tagged card already played this pull (requires Shapeshift: Grizzly to have been played first). (Aggro 3 v1)

**Solar Flare** [RANGED | ECLIPSE] -- 5 DMG. +1 DMG per other Eclipse-tagged card played in an earlier round this pull (voided if Shapeshift: Grizzly has already been played). (Aggro 2 v1)

**Moonbeam** [RANGED | ECLIPSE] -- 5 DMG. Heal 1 HP. +1 DMG per other Eclipse-tagged card played in an earlier round this pull (voided if Shapeshift: Grizzly has already been played). (Aggro 2 v1)

**Nature's Wildguard** [MELEE | ECLIPSE] -- Heal 2 HP. 2 Block. +1 Heal per other Eclipse-tagged card played in an earlier round this pull (voided if Shapeshift: Grizzly has already been played). (Aggro 2 v1)


## Necromancer (HP 14)

*Sowing Dread and Blight tag DOTs for Reap to pay off. Boneguard's Offering carries Death Pact: may lose 4 HP to deal 3 extra damage when played.*

**Boneguard's Offering** [MELEE | AT RANGE] -- 2 Block. Grants At Range this round (evades a melee mob's attack). Death Pact: when you play this card, you may lose 4 HP to deal 3 extra DMG. **PvP:** Death Pact costs no HP in PvP duels -- still deals its bonus damage for free. (Aggro 3 v2)

**Soul Harvest** [RANGED] -- 3 DMG. Heal 2 HP. (Aggro 2 v1)

**Sowing Dread** [RANGED | AT RANGE | DOT] -- 2 DMG. Grants At Range this round (evades a melee mob's attack). (Aggro 2 v1)

**Reap** [RANGED] -- 4 DMG. +1 DMG per DOT-tagged card played in an earlier round this pull. (Aggro 3 v2)

**Blight** [RANGED | ECHO | DOT] -- 1 DMG. At the start of the next round, automatically deal 3 more DMG (no card spent). (Aggro 1 v2)

**Death Blow** [RANGED | KILLING BLOW] -- 4 DMG. If this attack kills the mob, its attack this round is prevented. (Aggro 4 v1)

