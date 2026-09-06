import sys
import os
import json

sim_path = os.path.join(os.path.dirname(__file__), '..', 'sim')
sys.path.append(sim_path)

import generate_card_reference as gcr
import macro_sim as M
import leveling_validation as LV

builders = {
    "warrior": gcr._warrior_lines,
    "wizard": gcr._wizard_lines,
    "cleric": gcr._cleric_lines,
    "paladin": gcr._paladin_lines,
    "rogue": gcr._rogue_lines,
    "ranger": gcr._ranger_lines,
    "runecaster": gcr._runecaster_lines,
    "druid": gcr._druid_lines,
    "necromancer": gcr._necromancer_lines,
}


def build_card_obj(cls, title_cls, name, text, aggro):
    """One card's full export record -- shared by both the base (Level 1) export loop and the
    Level 2 export loop below, so a Level 2 card gets exactly the same rendering treatment
    (badges, per-class stance/panel special-casing) as its base card, with zero duplicated
    logic. Reads gcr.CARDS_BY_CLASS[title_cls][name] fresh, which correctly reflects whichever
    card (base or leveled_kit-swapped) is currently registered under that name."""
    c_data = gcr.CARDS_BY_CLASS[title_cls][name]
    tags = gcr._tags(c_data)

    card_obj = {
        "text": text,
        "aggro": aggro,
        "tags": tags,
        "split": False,
        "version": c_data.get("version", 1)
    }

    # Extract badges
    badges = {}

    dmg_str = None
    if "curve" in c_data:
        cv = c_data["curve"]
        dmg_str = f"{cv[0]}|{cv[1]}|{cv[2]}"
    elif "dmg_if_prev_range" in c_data:
        dmg_str = f"{c_data['dmg_else']}|{c_data['dmg_if_prev_range']}"
    elif "dmg_if_wolf" in c_data:
        dmg_str = f"{c_data['dmg_else']}|{c_data['dmg_if_wolf']}"
    elif "chain_bonus_dmg" in c_data and c_data.get("chain_bonus_dmg") > 0:
        dmg_str = f"{c_data['dmg']}|{c_data['dmg'] + c_data['chain_bonus_dmg']}"
    elif "dmg" in c_data:
        dmg_val = c_data["dmg"]
        if isinstance(dmg_val, tuple):
            if dmg_val[1] > dmg_val[0]:
                dmg_str = f"{dmg_val[0]}|{dmg_val[1]}"
            elif dmg_val[0] > 0:
                dmg_str = str(dmg_val[0])
        elif dmg_val is not None and dmg_val > 0:
            if "round1_dmg" in c_data:
                dmg_str = f"{dmg_val}|{c_data['round1_dmg']}"
            else:
                dmg_str = str(dmg_val)

    if dmg_str:
        badges["dmg"] = dmg_str

    heal_val = c_data.get("heal", 0)
    if heal_val is not None and heal_val > 0:
        badges["heal"] = heal_val

    block_val = c_data.get("block", 0)

    # Beast Bond aura applies immediately on the turn it is played
    if c_data.get("beast_bond"):
        block_val += c_data.get("beast_block_value", 1)

    if block_val is not None and block_val > 0:
        badges["block"] = str(block_val)

    echo_dmg = c_data.get("echo_dmg", 0)
    if echo_dmg:
        badges["delayed_dmg"] = str(echo_dmg)

    echo_heal = c_data.get("echo_heal", 0)
    if echo_heal:
        badges["delayed_heal"] = str(echo_heal)

    if c_data.get("beast_bond"):
        badges["delayed_block"] = f"{c_data.get('beast_block_value', 1)}+"

    if c_data.get("grants_range"):
        badges["range"] = True

    # Only add badges if there is at least one
    if badges:
        card_obj["badges"] = badges

    if cls == "warrior":
        c_data = gcr.CARDS_BY_CLASS["Warrior"][name]
        if c_data.get("G") and c_data.get("C"):
            if c_data["G"] != c_data["C"] or c_data.get("chain_stance"):
                card_obj["split"] = True
                g_dmg, g_block = c_data["G"]
                c_dmg, c_block = c_data["C"]

                g_parts = [f"**{g_dmg} DMG**, **{g_block} Block**."]
                c_parts = [f"**{c_dmg} DMG**, **{c_block} Block**."]

                if c_data.get("sunder"):
                    s_text = "Marks the mob Sundered: all your later damaging cards this pull deal +2 DMG."
                    g_parts.append(s_text)
                    c_parts.append(s_text)

                if c_data.get("chain_stance"):
                    target = "Block" if c_data["chain_target"] == "block" else "DMG"
                    req = c_data["chain_requires"]
                    bonus = c_data["chain_bonus"]
                    bonus_text = f"If the previous round's card was {req}, **+{bonus} {target}**."
                    if c_data["chain_stance"] == "G":
                        g_parts.append(bonus_text)
                    else:
                        c_parts.append(bonus_text)

                card_obj["guardian_text"] = " ".join([p for p in g_parts if p])
                card_obj["champion_text"] = " ".join([p for p in c_parts if p])
                card_obj["aggro_G"] = c_data.get("aggro_G", c_data.get("aggro"))
                card_obj["aggro_C"] = c_data.get("aggro_C", c_data.get("aggro"))

                b_c = {}
                if c_dmg > 0: b_c["dmg"] = c_dmg
                if c_block > 0: b_c["block"] = c_block
                if b_c: card_obj["badges_C"] = b_c

                b_g = {}
                if g_dmg > 0: b_g["dmg"] = g_dmg
                if g_block > 0: b_g["block"] = g_block
                if b_g: card_obj["badges_G"] = b_g
            else:
                g_dmg, g_block = c_data["G"]
                base_text = f"**{g_dmg} DMG**, **{g_block} Block**."
                if c_data.get("sunder"):
                    base_text += " Marks the mob Sundered: all your later damaging cards this pull deal +2 DMG."
                card_obj["text"] = base_text

    if cls == "wizard":
        c_data = gcr.CARDS_BY_CLASS["Wizard"][name]
        card_obj["panels"] = []

        base_dmg, boosted_dmg = c_data["dmg"]
        block = c_data["block"]

        base_text = []
        if base_dmg > 0:
            if c_data.get("payoff") and boosted_dmg > base_dmg:
                base_text.append(f"**{base_dmg} DMG** OR <span class=\"magic-text\">**{boosted_dmg} DMG**</span> if SPELLWEAVE is armed.")
            else:
                base_text.append(f"**{base_dmg} DMG**.")
        if block > 0:
            base_text.append(f"**{block} Block**.")

        if base_text:
            card_obj["panels"].append({
                "type": "base",
                "text": " ".join(base_text)
            })

        if c_data.get("grants_range"):
            card_obj["panels"].append({
                "type": "positioning",
                "label": "POSITIONING",
                "text": "Grants At Range this round (evades a melee mob's attack)."
            })

        if c_data.get("weave_source"):
            card_obj["panels"].append({
                "type": "weave_source",
                "label": "SPELLWEAVE",
                "text": "Arms Weave: your next eligible payoff card gets its boosted damage."
            })

        if c_data.get("armor_pierce"):
            card_obj["panels"].append({
                "type": "rider",
                "label": "PIERCE",
                "text": "Ignores the mob's Block entirely."
            })

    if cls == "cleric":
        c_data = gcr.CARDS_BY_CLASS["Cleric"][name]
        card_obj["panels"] = []

        base_text = []
        if c_data["dmg"]:
            base_text.append(f"**{c_data['dmg']} DMG**.")
        if c_data["heal"]:
            base_text.append(f"Heal **{c_data['heal']} HP**.")
        if c_data["block"]:
            base_text.append(f"**{c_data['block']} Block**.")

        if base_text:
            card_obj["panels"].append({
                "type": "base",
                "text": " ".join(base_text)
            })

        if c_data.get("sacred_balance"):
            card_obj["panels"].append({
                "type": "sacred_balance",
                "label": "SACRED BALANCE",
                "text": f"Triggers Sacred Balance: heal **{gcr.C.SACRED_BALANCE_HEAL} HP** automatically."
            })

        if c_data.get("max_hp_buff"):
            card_obj["panels"].append({
                "type": "buff",
                "label": "FORTITUDE",
                "text": f"**+{c_data['max_hp_buff']} Max HP** for the rest of this pull."
            })

        if c_data.get("echo_dmg"):
            card_obj["panels"].append({
                "type": "echo",
                "label": "ECHO",
                "text": f"At the start of the next round, automatically deal **{c_data['echo_dmg']} more DMG** (no card spent)."
            })

    if cls == "paladin":
        c_data = gcr.CARDS_BY_CLASS["Paladin"][name]
        card_obj["panels"] = []

        base_text = []
        if c_data["dmg"]:
            base_text.append(f"**{c_data['dmg']} DMG**.")
        if c_data["heal"]:
            base_text.append(f"Heal **{c_data['heal']} HP**.")
        if c_data["block"]:
            base_text.append(f"**{c_data['block']} Block**.")

        if base_text:
            card_obj["panels"].append({
                "type": "base",
                "text": " ".join(base_text)
            })

        if c_data.get("invocation") == "sanctuary":
            b = gcr.P.INVOCATION_PER_STRIKE_BONUS
            card_obj["panels"].append({
                "type": "invocation",
                "label": "INVOCATION",
                "text": f"**+{b} DMG** per STRIKE card already played earlier this pull. Every STRIKE card played afterward also deals **+{b} DMG** when played. (Only one Invocation card may ever be played per pull.)"
            })
        elif c_data.get("invocation") == "grace":
            b = gcr.P.INVOCATION_PER_STRIKE_BONUS
            card_obj["panels"].append({
                "type": "invocation",
                "label": "INVOCATION",
                "text": f"Heal **{b} HP** per STRIKE card already played earlier this pull. Every STRIKE card played afterward also heals **+{b} HP** when played. (Only one Invocation card may ever be played per pull.)"
            })

        if c_data.get("grants_aura_block"):
            card_obj["panels"].append({
                "type": "invocation",
                "label": "AURA",
                "text": "Every STRIKE card played afterward also gains +1 Block per STRIKE card already played this pull, while this Invocation is active."
            })

    if cls == "rogue":
        c_data = gcr.CARDS_BY_CLASS["Rogue"][name]
        card_obj["panels"] = []

        base_text = []
        if c_data["kind"] == "finisher":
            c0, c1, c2 = c_data["curve"][0], c_data["curve"][1], c_data["curve"][2]
            card_obj["panels"].append({
                "type": "finisher",
                "label": "FINISHER",
                "text": f"**{c0}** / **{c1}** / **{c2} DMG** (based on 0 / 1 / 2+ previous STRIKE cards this pull)."
            })
            if c_data.get("killing_blow"):
                card_obj["panels"].append({
                    "type": "rider",
                    "label": "KILLING BLOW",
                    "text": "If this kills the mob, it deals no damage this round."
                })
        elif c_data["kind"] == "opener":
            base_text.append(f"**{c_data['dmg']} DMG** OR <span class=\"combo-text\">**{c_data['round1_dmg']} DMG**</span> if played in round 1.")
        else:
            if c_data["dmg"]:
                base_text.append(f"**{c_data['dmg']} DMG**.")
            if c_data["block"]:
                base_text.append(f"**{c_data['block']} Block**.")

        if c_data.get("armor_pierce"):
            base_text.append("Ignores the mob's Block entirely.")

        if base_text:
            card_obj["panels"].insert(0, {
                "type": "base",
                "text": " ".join(base_text)
            })

    return card_obj


out_data = {}
for cls, builder in builders.items():
    out_data[cls] = {}
    title_cls = cls.capitalize()
    for name, text, aggro in builder():
        out_data[cls][name] = build_card_obj(cls, title_cls, name, text, aggro)

# Level 2 upgrade cards -- read from macro_sim.py's LEVEL2_MANDATORY/LEVEL2_PURCHASED_ORDER,
# never from condensed_<class>.py's own CARDS (base Level 1 kits are untouched by leveling).
# Renders each leveled card through leveled_kit + the SAME per-class builder/build_card_obj
# used for base cards above -- zero duplicated rendering logic, so a Level 2 card can never
# drift from what the base-card renderer already does for stance-split/panel-tagged classes.
for cls, builder in builders.items():
    title_cls = cls.capitalize()
    if cls not in M.LEVEL2_MANDATORY:
        continue  # skips any class with no Level 2 slate registered in macro_sim.py

    mod, mand_old, mand_new, mand_card = M.LEVEL2_MANDATORY[cls]
    upgrades = [(mand_old, mand_new, mand_card, "mandatory")]
    upgrades += [(old, new, card, "purchased") for old, new, card in M.LEVEL2_PURCHASED_ORDER.get(cls, [])]

    for old_name, new_name, new_card, tier in upgrades:
        with LV.leveled_kit(mod, {old_name: (new_name, new_card)}):
            for name, text, aggro in builder():
                if name != new_name:
                    continue
                obj = build_card_obj(cls, title_cls, name, text, aggro)
                obj["level2"] = True
                obj["tier"] = tier
                obj["replaces"] = old_name
                out_data[cls][new_name] = obj
                break

output_path = os.path.join(os.path.dirname(__file__), 'src', 'cards_text.json')
with open(output_path, "w") as f:
    json.dump(out_data, f, indent=2)

print(f"Exported cards text to {output_path}")
