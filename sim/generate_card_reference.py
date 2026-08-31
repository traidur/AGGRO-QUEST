"""
Generates CARD_REFERENCE.md -- a human-readable, tabletop-facing rules-text listing for
every locked class, sourced directly from each class's real CARDS dict (never hand-copied).

Why this exists: every other artifact in this codebase is aimed at the solver or at an AI
reading design history (docstrings, CLASS_BALANCE_GUIDE.md, OPEN_QUESTIONS.md) -- nothing
produced actual "read this at the table" card text. This is that missing deliverable.
Regenerated from source each run specifically so it can't drift the way a hand-maintained
description could (the exact failure mode CLAUDE.md already flags for docstring prose vs.
the CARDS dict that actually runs -- see Paladin's Invocation of Grace for a real example
caught while building this: its docstring says "3 dmg + heal per STRIKE," but the executing
CARDS dict has dmg=4 flat and only the heal scales -- the generator below follows the dict).

Run: python generate_card_reference.py (from sim/), writes ../CARD_REFERENCE.md.

**Card versioning (added 2026-08-30):** every card carries a `version` field in its own
`CARDS` dict entry -- an integer bumped only when that specific card's printed text or numbers
actually change, never touched otherwise. Purely a printed-deck bookkeeping aid (lets a
physical deck owner tell which cards need reprinting after a rebalance pass) -- nothing in the
solver reads it. Necromancer is the one class currently exempted: its file is mid-investigation
(not a finished, locked decision), so neither "1" (implies nothing changed, false) nor "2"
(implies a decided rebalance, also false) would be accurate -- add its version numbers once
that class actually locks.
"""
import condensed_cleric as C
import condensed_paladin as P
import condensed_ranger as G
import condensed_rogue as R
import condensed_runecaster as N
import condensed_warrior as W
import condensed_wizard as Z
import condensed_druid as Du
import condensed_necromancer as Nm

IDENTITY = {
    "Warrior": "Guardian/Champion stance, locked once per pull. Sundering Blow stacks +2 damage on all later damaging cards. Vanguard Shield/Blade reward playing them back-to-back in the right stance.",
    "Wizard": "Weave: playing a Weave-source card arms a one-time damage boost for the next payoff card. Positioning: At Range evades a melee mob's attack entirely.",
    "Cleric": "Sacred Balance: Smite automatically heals a small flat amount on top of its damage. Cleansing Barrier and Fiery Fortitude carry incidental damage riders to keep a real damage floor.",
    "Paladin": "Invocation of Sanctuary/Grace -- pick exactly one per pull. Whichever is played first both pays off every STRIKE card already played and arms a bonus on every STRIKE card played afterward.",
    "Rogue": "Cutthroat/Envenom are finishers scaling off STRIKE cards played since your last finisher (0/1/2), resetting the count on use. Cutthroat alone carries a killing-blow rider.",
    "Ranger": "Beast Bond: Wolf grants persistent Block every round for the rest of the pull once played. Sniper/Point Blank Shot rewards having granted At Range the previous round.",
    "Runecaster": "Lightning Bolt rewards playing it right after Chain Lightning. Earth Strike Rune's damage and heal partially echo automatically at the start of the next round, no card spent.",
    "Druid": "Two mutually exclusive lines. Shapeshift: Grizzly boosts Maul/Swipe if played first, but cancels the Eclipse-stacking bonus (Solar Flare/Moonbeam/Nature's Wildguard) on any Eclipse card played after it.",
    "Necromancer": "Sowing Dread and Blight tag DOTs for Reap to pay off. Boneguard's Offering carries Death Pact: may lose 4 HP to deal 3 extra damage when played.",
}

HP = {
    "Warrior": W.WARRIOR_HP, "Wizard": Z.WIZARD_HP, "Cleric": C.CLERIC_HP,
    "Paladin": P.PALADIN_HP, "Rogue": R.ROGUE_HP, "Ranger": G.RANGER_HP,
    "Runecaster": N.RUNECASTER_HP, "Druid": Du.DRUID_HP, "Necromancer": Nm.NECROMANCER_HP,
}


def _warrior_lines():
    lines = []
    for name, c in W.CARDS.items():
        if c["execute_finisher"]:
            text = "6 DMG. Only playable once the mob is at 50% HP or lower. If this kills the mob, its attack this round is prevented."
            aggro = f"Aggro {c['aggro']}"
        else:
            g_dmg, g_block = c["G"]
            ch_dmg, ch_block = c["C"]
            parts = [f"**Guardian:** {g_dmg} DMG, {g_block} Block.", f"**Champion:** {ch_dmg} DMG, {ch_block} Block."]
            if c["sunder"]:
                parts.append("Marks the mob Sundered: all your later damaging cards this pull deal +2 DMG.")
            if c["chain_stance"]:
                target = "Block" if c["chain_target"] == "block" else "DMG"
                parts.append(f"**{'Guardian' if c['chain_stance']=='G' else 'Champion'} only:** if the previous round's card was {c['chain_requires']}, +{c['chain_bonus']} {target}.")
            text = " ".join(parts)
            aggro = f"Aggro {c['aggro']}" if "aggro" in c else f"Aggro G:{c['aggro_G']} / C:{c['aggro_C']}"
        lines.append((name, text, aggro))
    return lines


def _wizard_lines():
    lines = []
    for name, c in Z.CARDS.items():
        base, boosted = c["dmg"]
        parts = [f"{base} DMG" + (f" ({boosted} DMG if Weave is armed)" if base != boosted or c["payoff"] else "") + "."] if base or boosted else []
        if c["block"]:
            parts.append(f"{c['block']} Block.")
        if c["grants_range"]:
            parts.append("Grants At Range this round (evades a melee mob's attack).")
        if c["weave_source"]:
            parts.append("Arms Weave: your next eligible payoff card gets its boosted damage.")
        lines.append((name, " ".join(parts), f"Aggro {c['aggro']}"))
    return lines


def _cleric_lines():
    lines = []
    for name, c in C.CARDS.items():
        parts = []
        if c["dmg"]:
            parts.append(f"{c['dmg']} DMG.")
        if c["heal"]:
            parts.append(f"Heal {c['heal']} HP.")
        if c["block"]:
            parts.append(f"{c['block']} Block.")
        if c["sacred_balance"]:
            parts.append(f"Triggers Sacred Balance: heal {C.SACRED_BALANCE_HEAL} HP automatically.")
        if c["max_hp_buff"]:
            parts.append(f"+{c['max_hp_buff']} Max HP for the rest of this pull.")
        lines.append((name, " ".join(parts), f"Aggro {c['aggro']}"))
    return lines


def _paladin_lines():
    lines = []
    for name, c in P.CARDS.items():
        parts = []
        if c["invocation"] == "sanctuary":
            parts.append(f"Deal {c['dmg']} DMG, +1 DMG per STRIKE card already played earlier this pull.")
            parts.append("Every STRIKE card played afterward also deals +1 DMG when played.")
            parts.append("Only the first Invocation card played each pull gets any bonus (backward or forward) -- a second one is legal to play but deals/heals its flat base only and never becomes Active.")
        elif c["invocation"] == "grace":
            parts.append(f"Deal {c['dmg']} DMG. Heal 1 HP per STRIKE card already played earlier this pull.")
            parts.append("Every STRIKE card played afterward also heals +1 HP when played.")
            parts.append("Only the first Invocation card played each pull gets any bonus (backward or forward) -- a second one is legal to play but deals/heals its flat base only and never becomes Active.")
        else:
            if c["dmg"]:
                parts.append(f"{c['dmg']} DMG.")
            if c["heal"]:
                parts.append(f"Heal {c['heal']} HP.")
            if c["block"]:
                parts.append(f"{c['block']} Block.")
        lines.append((name, " ".join(parts), f"Aggro {c['aggro']}"))
    return lines


def _rogue_lines():
    lines = []
    for name, c in R.CARDS.items():
        parts = []
        if c["kind"] == "finisher":
            curve = c["curve"]
            parts.append(f"Deals {curve[0]}/{curve[1]}/{curve[2]} DMG based on STRIKE cards played "
                          f"since your last finisher (0/1/2). Resets the count to 0.")
            if c.get("killing_blow"):
                parts.append("If this attack kills the mob, its attack this round is prevented.")
        elif c["kind"] == "opener":
            parts.append(f"{c['dmg']} DMG ({c['round1_dmg']} DMG if played in round 1).")
        else:
            parts.append(f"{c['dmg']} DMG.")
        if c["block"]:
            parts.append(f"{c['block']} Block.")
        lines.append((name, " ".join(parts), f"Aggro {c['aggro']}"))
    return lines


def _ranger_lines():
    lines = []
    for name, c in G.CARDS.items():
        parts = []
        if c["payoff_prev_range"]:
            parts.append(f"{c['dmg_if_prev_range']} DMG if the previous round's card granted At Range, {c['dmg_else']} DMG otherwise.")
        elif c.get("payoff_wolf"):
            parts.append(f"{c['dmg_if_wolf']} DMG if the Wolf is active, {c['dmg_else']} DMG otherwise.")
        elif c["dmg"]:
            parts.append(f"{c['dmg']} DMG.")
        if c["block"]:
            parts.append(f"{c['block']} Block.")
        if c["beast_bond"]:
            parts.append(f"Activates the Wolf: from this round on (including this one), gain +{c['beast_block_value']} "
                          f"Block every round for the rest of the pull, stacking with any Block your card grants that round.")
        if c["grants_range"]:
            parts.append("Grants At Range this round (evades a melee mob's attack).")
        lines.append((name, " ".join(parts), f"Aggro {c['aggro']}"))
    return lines


def _runecaster_lines():
    lines = []
    for name, c in N.CARDS.items():
        parts = []
        if c["dmg"]:
            parts.append(f"{c['dmg']} DMG.")
        if c["heal"]:
            parts.append(f"Heal {c['heal']} HP.")
        if c["block"]:
            parts.append(f"{c['block']} Block.")
        if c["chain_bonus_if_prev"]:
            parts.append(f"+{c['chain_bonus_dmg']} DMG if the previous round's card was {c['chain_bonus_if_prev']}.")
        if c["grants_range"]:
            parts.append("Grants At Range this round (evades a melee mob's attack).")
        if c["echo_dmg"] or c["echo_heal"]:
            bits = []
            if c["echo_dmg"]:
                bits.append(f"{c['echo_dmg']} more DMG")
            if c["echo_heal"]:
                bits.append(f"heal {c['echo_heal']} more HP")
            parts.append(f"At the start of the next round, automatically deal {' and '.join(bits)} (no card spent).")
        lines.append((name, " ".join(parts), f"Aggro {c['aggro']}"))
    return lines


def _druid_lines():
    lines = []
    for name, c in Du.CARDS.items():
        parts = []
        if c["dmg"]:
            parts.append(f"{c['dmg']} DMG.")
        if c["heal"]:
            parts.append(f"Heal {c['heal']} HP.")
        if c["block"]:
            parts.append(f"{c['block']} Block.")
        if c["tag"] == "shapeshift" and name != "Shapeshift: Grizzly":
            parts.append("+1 DMG and +1 Block if Shapeshift: Grizzly was played in an earlier round this pull.")
        if name == "Shapeshift: Grizzly":
            parts.append("Maul/Swipe played in a later round gain +1 DMG/+1 Block.")
            parts.append("Cancels the Eclipse-stacking bonus on any Eclipse-tagged card played in a later round.")
        if c["tag"] == "eclipse":
            if c.get("heal_scales_with_eclipse"):
                parts.append("+1 Heal per other Eclipse-tagged card played in an earlier round this pull (voided if Shapeshift: Grizzly has already been played).")
            else:
                parts.append("+1 DMG per other Eclipse-tagged card played in an earlier round this pull (voided if Shapeshift: Grizzly has already been played).")
        lines.append((name, " ".join(parts), f"Aggro {c['aggro']}"))
    return lines


def _necromancer_lines():
    lines = []
    for name, c in Nm.CARDS.items():
        if name == Nm.BONEGUARD_OFFERING_BOOSTED:
            continue  # internal solver variant, not a real drawable card -- folded into Boneguard's Offering's own line below
        parts = []
        if c["dmg"]:
            parts.append(f"{c['dmg']} DMG.")
        if c["heal"]:
            parts.append(f"Heal {c['heal']} HP.")
        if c["block"]:
            parts.append(f"{c['block']} Block.")
        if c["grants_range"]:
            parts.append("Grants At Range this round (evades a melee mob's attack).")
        if c["dot_payoff"]:
            parts.append("+1 DMG per DOT-tagged card played in an earlier round this pull.")
        if c["echo_dmg"]:
            parts.append(f"At the start of the next round, automatically deal {c['echo_dmg']} more DMG (no card spent).")
        if c["killing_blow"]:
            parts.append("If this attack kills the mob, its attack this round is prevented.")
        if name == Nm.BONEGUARD_OFFERING:
            parts.append(f"Death Pact: when you play this card, you may lose {Nm.HP_FOR_DMG_COST} HP "
                         f"to deal {Nm.HP_FOR_DMG_BONUS} extra DMG.")
        lines.append((name, " ".join(parts), f"Aggro {c['aggro']}"))
    return lines


CARDS_BY_CLASS = {
    "Warrior": W.CARDS, "Wizard": Z.CARDS, "Cleric": C.CARDS, "Paladin": P.CARDS,
    "Rogue": R.CARDS, "Ranger": G.CARDS, "Runecaster": N.CARDS, "Druid": Du.CARDS,
    "Necromancer": Nm.CARDS,
}


def _tags(card):
    """Keyword badges, derived purely from the card's own fields via .get() (safe across
    classes whose dicts don't share every key) -- taxonomy locked with the user card by card,
    see CLASS_BALANCE_GUIDE.md / this module's own history for the naming reasoning (SUNDER,
    SACRED BALANCE, SPELLWEAVE, INVOCATION, PET, ECHO, FINISHER, OPENER are each named after
    the mechanic itself, not invented ad hoc)."""
    tags = []
    if card.get("grants_range"):
        tags.append("AT RANGE")
    if card.get("strike"):
        tags.append("STRIKE")
    if card.get("killing_blow"):
        tags.append("KILLING BLOW")
    if card.get("kind") == "finisher":
        tags.append("FINISHER")
    if card.get("kind") == "opener":
        tags.append("OPENER")
    if card.get("sacred_balance"):
        tags.append("SACRED BALANCE")
    if card.get("sunder"):
        tags.append("SUNDER")
    if card.get("invocation") is not None:
        tags.append("INVOCATION")
    if card.get("weave_source"):
        tags.append("SPELLWEAVE: SOURCE")
    elif card.get("payoff"):
        tags.append("SPELLWEAVE")
    if card.get("beast_bond") or card.get("payoff_wolf"):
        tags.append("PET")
    if card.get("beast_bond"):
        tags.append("PERSISTENT")
    if card.get("chain_stance") or card.get("chain_bonus_if_prev") or card.get("payoff_prev_range"):
        tags.append("COMBO")
    if card.get("echo_dmg") or card.get("echo_heal"):
        tags.append("ECHO")
    if card.get("tag") == "shapeshift":
        tags.append("SHAPESHIFT")
    if card.get("tag") == "eclipse":
        tags.append("ECLIPSE")
    if card.get("dot"):
        tags.append("DOT")
    return tags


BUILDERS = {
    "Warrior": _warrior_lines, "Wizard": _wizard_lines, "Cleric": _cleric_lines,
    "Paladin": _paladin_lines, "Rogue": _rogue_lines, "Ranger": _ranger_lines,
    "Runecaster": _runecaster_lines, "Druid": _druid_lines, "Necromancer": _necromancer_lines,
}


def generate():
    out = ["# QUEST -- Card Reference\n",
           "Generated directly from each class's real `CARDS` dict in `sim/condensed_<class>.py` "
           "-- regenerate with `python generate_card_reference.py` after any card change rather "
           "than hand-editing this file, so it can never drift out of sync with what the solver "
           "actually runs. Aggro is the co-op Party Pull targeting value (0-4) -- see "
           "`OPEN_QUESTIONS.md`'s \"Co-op multi-hero vs. Elite/multi-mob nodes\" entry. `v#` is "
           "the card's printed-revision number -- compare against your physical deck to see "
           "which cards need reprinting after a rebalance.\n"]
    for cls, builder in BUILDERS.items():
        out.append(f"## {cls} (HP {HP[cls]})\n")
        out.append(f"*{IDENTITY[cls]}*\n")
        for name, text, aggro in builder():
            card = CARDS_BY_CLASS[cls][name]
            tags = _tags(card)
            tag_str = f" [{' | '.join(tags)}]" if tags else ""
            version_str = f" v{card['version']}" if "version" in card else ""
            out.append(f"**{name}**{tag_str} -- {text} ({aggro}{version_str})\n")
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    content = generate()
    with open("../CARD_REFERENCE.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("Wrote CARD_REFERENCE.md")
