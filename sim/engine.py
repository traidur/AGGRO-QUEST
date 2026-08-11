"""Card/mob data loading and single-round hand solving for the QUEST balance sim.

Scope note: this models a single hero against a single static mob, across
however many rounds a Slog takes (mob HP whittles, per DESIGN_DOC.md SS2).
It does not model cross-pull deck pollution (Winded/OOM cards
accumulating over a multi-pull trip), Bag Tetris, or co-op/Party Pulls.
Those are later layers once the core per-pull math is calibrated. (Note:
simulate.py's run_trip has since grown a cross-pull trip model on top of
this single-pull engine — this scope note describes engine.py alone.)

Exhaust (Wall of Ice, Confound) is DECIDED to be trip-scoped, not
pull-scoped (see OPEN_QUESTIONS.md) — an exhausted card should stay gone
until a Town visit. This module currently only implements pull-scoped
removal (a fresh deck every run_pull call) because trip-level state
doesn't exist yet. Don't read the current behavior as the design intent.

Known simplifications, flagged rather than silently assumed:
- Card-granted draw (Shoot Wand, Void's Veil) does not let you play the
  newly drawn card the same round. It's tracked but has no combat effect
  yet.
- Spellweaving's Instant-before-Cast discount is applied optimally
  (see CLASSES.md) rather than modeling turn-order choice explicitly.
- Vanguard Blade/Shield's "if the last card you played was an Attack"
  bonuses are approximated as "the chosen subset contains another
  Attack-tagged card," assuming optimal sequencing (same treatment as
  Spellweaving). This can over-award both bonuses in the rare case where
  a hand contains exactly Vanguard Blade + Vanguard Shield and no third
  Attack card, since only one of the two could actually be sequenced
  last in a real single ordering.
- Sunder tokens placed this round do not retroactively boost this same
  round's damage — only tokens carried in from previous rounds apply.
  Mildly conservative, easy to reason about.
- Stance Dance's Guardian charge is boolean (max 1 banked), not a
  stacking counter.
- Teleport (disengage) waives the Cast Penalty for every card in the
  same round's play (an "opener," assumed sequenced first) but has no
  effect on future rounds — Engagement next round follows the normal
  mob-engages-on-failed-OTK rule regardless of this round's Teleport.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

CLASS_HP = {"warrior": 18, "cleric": 12, "wizard": 10}
SACRED_BALANCE_HEAL = 0.0  # removed per designer decision — was letting Cleric escape the shared HP-attrition ceiling


@dataclass(frozen=True)
class Mode:
    """One way a card can be played (or not played)."""

    label: str
    cost: float
    dmg: float = 0.0
    dot: float = 0.0
    block: float = 0.0
    heal: float = 0.0
    hot: float = 0.0
    draw: int = 0
    is_cast: bool = False
    is_attack: bool = False
    is_brutal: bool = False
    generates_block: bool = False
    triggers_sacred_balance: bool = False
    execute_gated: bool = False
    is_exhaust: bool = False
    untargetable: bool = False
    evades_melee: bool = False  # like untargetable, but only vs melee mobs -- a "step back," not full immunity
    disengage: bool = False
    waives_cast_penalty: bool = False
    incapacitate: bool = False
    places_sunder: int = 0
    champion_atk_bonus: float = 0.0  # Vanguard Blade, requires another Attack in the play
    guardian_block_bonus: float = 0.0  # Vanguard Blade, unconditional in Guardian
    guardian_atk_bonus: float = 0.0  # Vanguard Shield, requires another Attack in the play
    guardian_counter: bool = False  # Stance Dance: banks a charge in Guardian
    taxes_oom: bool = False  # caster heal/best-hitter tax -> generates an OOM trash card
    taxes_winded: bool = False  # melee mitigation tax -> generates a Winded trash card
    max_hp_buff: float = 0.0  # temp Max HP raise while held (e.g. Blessed Fortitude)
    is_power_card: bool = False  # held (not exhausted) until Food OR Water is used, or Town -- a
    # different persistence rule than Exhaust: any restorative discards it, not just the class's own


NOT_PLAYED = Mode(label="pass", cost=0.0)


@dataclass(frozen=True)
class Card:
    name: str
    class_name: str
    modes: tuple[Mode, ...]


def _tagset(raw: str) -> set[str]:
    return {t.strip() for t in raw.split(";") if t.strip()}


@lru_cache(maxsize=None)
def load_cards(class_name: str) -> list[Card]:
    """Cached — this file doesn't change mid-run, and run_pull calls this
    once per pull, so re-parsing the CSV every time was wasted I/O."""
    cards: list[Card] = []
    with open(DATA_DIR / "cards.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["class"] != class_name:
                continue
            tags = _tagset(row["tags"])
            base = Mode(
                label="base",
                cost=float(row["cost"]),
                dmg=float(row["dmg"]),
                dot=float(row["dot_dmg"]),
                block=float(row["block"]),
                heal=float(row["heal"]),
                hot=float(row["hot_heal"]),
                draw=int(row["draw"]),
                is_cast=(row["card_type"] == "Cast"),
                is_attack="attack" in tags,
                is_brutal="brutal" in tags,
                generates_block=float(row["block"]) > 0,
                triggers_sacred_balance="sacred_balance" in tags,
                execute_gated="execute_below_50pct" in tags,
                is_exhaust="exhaust" in tags,
                untargetable="untargetable" in tags,
                evades_melee="evades_melee" in tags,
                disengage="disengage" in tags,
                waives_cast_penalty="waives_cast_penalty" in tags,
                incapacitate="incapacitate" in tags,
                places_sunder=1 if "sunder1" in tags else 0,
                champion_atk_bonus=2.0 if "champion_atk2" in tags else 0.0,
                guardian_block_bonus=2.0 if "guardian_block2" in tags else 0.0,
                guardian_atk_bonus=1.0 if "guardian_atk1" in tags else 0.0,
                guardian_counter="guardian_counter3" in tags,
                taxes_oom="taxes_oom" in tags,
                taxes_winded="taxes_winded" in tags,
                max_hp_buff=4.0 if "max_hp_buff4" in tags else 0.0,
                is_power_card="power_card" in tags,
            )
            modes = [base]
            if "pay1_for_4dmg" in tags:
                modes.append(
                    Mode(
                        label="empowered",
                        cost=base.cost + 1,
                        dmg=4.0,
                        is_cast=base.is_cast,
                        is_attack=base.is_attack,
                        is_brutal=base.is_brutal,
                    )
                )
            if row["card_type"] == "Power":
                # Non-combat (e.g. Blessed Fortitude) — excluded from the
                # per-pull math per CLASSES.md. Drawing it just occupies a
                # hand slot, same texture as a dead card.
                modes = []
            copies = int(row["copies"])
            for _ in range(copies):
                cards.append(Card(name=row["name"], class_name=class_name, modes=tuple(modes)))
    return cards


def load_mobs() -> dict[str, dict]:
    mobs: dict[str, dict] = {}
    with open(DATA_DIR / "mobs.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mobs[row["mob_id"]] = {
                "name": row["name"],
                "tier": int(row["tier"]),
                "hp": float(row["hp"]),
                "atk": float(row["atk"]),
                "mob_type": row["mob_type"],
            }
    return mobs


def enumerate_hand_plays(
    hand: list[Card],
    class_name: str,
    engaged: bool,
    mob_hp: float,
    mob_max_hp: float,
    sunder_tokens: int = 0,
) -> list[dict]:
    """All legal (subset-of-hand, stance) plays within the 3-Energy cap.

    Each result carries `combo` — the chosen Mode per hand position, in the
    same order as `hand` — so callers can tell which physical cards were
    actually played (needed for exhaust removal).
    """
    import itertools

    per_card_options: list[list[Mode]] = []
    for card in hand:
        opts = [NOT_PLAYED]
        for m in card.modes:
            if m.execute_gated and not (mob_hp <= 0.5 * mob_max_hp):
                continue
            opts.append(m)
        per_card_options.append(opts)

    stances = ["guardian", "champion"] if class_name == "warrior" else [None]
    results: list[dict] = []

    for stance in stances:
        for combo in itertools.product(*per_card_options):
            played = [m for m in combo if m is not NOT_PLAYED]
            if not played:
                continue

            disengage = any(m.disengage for m in played)
            waives_penalty = any(m.waives_cast_penalty for m in played)
            effective_engaged = engaged and not (disengage or waives_penalty)
            costed = [[m, m.cost + (1.0 if (effective_engaged and m.is_cast) else 0.0)] for m in played]

            if class_name == "wizard":
                instants = [m for m in played if not m.is_cast]
                discount_slots = min(2, len(instants))
                cast_entries = sorted((e for e in costed if e[0].is_cast), key=lambda e: -e[1])
                for e in cast_entries[:discount_slots]:
                    e[1] = max(0.0, e[1] - 1.0)

            total_cost = sum(c for _, c in costed)
            if total_cost > 3:
                continue

            dmg = sum(m.dmg for m in played)
            dot = sum(m.dot for m in played)
            block = sum(m.block for m in played)
            heal = sum(m.heal for m in played)
            hot = sum(m.hot for m in played)
            draw = sum(m.draw for m in played)
            sb_triggers = sum(1 for m in played if m.triggers_sacred_balance)
            heal += SACRED_BALANCE_HEAL * sb_triggers

            attack_count = sum(1 for m in played if m.is_attack)

            if class_name == "warrior":
                if stance == "champion":
                    dmg += sum(1 for m in played if m.is_brutal and m.dmg > 0)
                    dmg += sum(m.champion_atk_bonus for m in played if attack_count >= 2)
                else:
                    block += sum(1 for m in played if m.generates_block)
                    block += sum(m.guardian_block_bonus for m in played)
                    dmg += sum(m.guardian_atk_bonus for m in played if attack_count >= 2)

            # Sunder: pre-existing tokens (not ones placed this round) boost
            # every damage source played this round.
            if sunder_tokens > 0:
                dmg += sunder_tokens * sum(1 for m in played if m.dmg > 0)
                dot += sunder_tokens * sum(1 for m in played if m.dot > 0)

            sunder_placed = sum(m.places_sunder for m in played)
            oom_generated = sum(1 for m in played if m.taxes_oom)
            winded_generated = sum(1 for m in played if m.taxes_winded)
            untargetable = any(m.untargetable for m in played)
            evades_melee = any(m.evades_melee for m in played)
            incapacitate = any(m.incapacitate for m in played)
            banks_charge = stance == "guardian" and any(m.guardian_counter for m in played)
            exhausted_indices = [i for i, m in enumerate(combo) if m is not NOT_PLAYED and m.is_exhaust]
            held_indices = [i for i, m in enumerate(combo) if m is not NOT_PLAYED and m.is_power_card]
            max_hp_buff_gained = sum(m.max_hp_buff for m in played)

            results.append(
                dict(
                    dmg=dmg,
                    dot=dot,
                    block=block,
                    heal=heal,
                    hot=hot,
                    draw=draw,
                    cost=total_cost,
                    stance=stance,
                    combo=combo,
                    sunder_placed=sunder_placed,
                    untargetable=untargetable,
                    evades_melee=evades_melee,
                    disengage=disengage,
                    incapacitate=incapacitate,
                    banks_charge=banks_charge,
                    exhausted_indices=exhausted_indices,
                    held_indices=held_indices,
                    oom_generated=oom_generated,
                    winded_generated=winded_generated,
                    max_hp_buff_gained=max_hp_buff_gained,
                )
            )

    return results


def _dmg_taken(play: dict, mob_atk: float, mob_type: str | None = None) -> float:
    """What a play actually costs in HP if the mob gets to strike.
    Untargetable and Incapacitate both mean zero, full stop — neither
    shows up in the `block` field, so anything sorting on block alone
    is blind to them. evades_melee is the same, but conditional on the
    mob actually being melee — it does nothing against a ranged mob."""
    if play.get("untargetable") or play.get("incapacitate"):
        return 0.0
    if play.get("evades_melee") and mob_type == "melee":
        return 0.0
    return max(0.0, mob_atk - play["block"])


def _net_hp_change(play: dict, mob_atk: float, mob_type: str | None = None) -> float:
    """Healing and damage avoidance are both real HP, and a safety
    comparison that only looks at one is blind to the other — the bug
    that made Cleric's dedicated heal cards invisible to both the greedy
    scorer and the rollout's continuation policy."""
    return play["heal"] - _dmg_taken(play, mob_atk, mob_type)


def choose_play(
    results: list[dict],
    mob_hp: float,
    hero_hp: float | None = None,
    mob_atk: float | None = None,
    mob_type: str | None = None,
    danger_floor: float = 0.0,
) -> dict:
    """A rational player: prefer a clean kill, then a DOT-assisted kill
    (minimizing damage taken among those), then triage between pushing
    damage progress and playing defensively.

    Triage rule (only applies when hero_hp/mob_atk are supplied): if the
    damage-maximizing play would leave the hero at or below danger_floor
    this round, and a safer alternative would keep the hero above it,
    take the safer play instead. "Safer" is measured by net HP change
    (_net_hp_change: healing minus damage taken), not raw Block, so
    Untargetable/Incapacitate/evades_melee and dedicated heal cards are
    all correctly recognized as real defensive value. mob_type matters
    specifically for evades_melee, which is conditional on it — pass it
    whenever the caller has it, or that card's safety will be invisible
    to this triage the same way heal cards used to be. If nothing
    survives either way, there's nothing to protect — push for damage.

    This only looks one round ahead. It won't avoid drifting into an
    unwinnable position two rounds out; it just won't walk into a death
    this round when a safer option was sitting right there.
    """
    immediate_kill = [r for r in results if r["dmg"] >= mob_hp]
    if immediate_kill:
        return max(immediate_kill, key=lambda r: r["block"])
    dot_kill = [r for r in results if r["dmg"] + r["dot"] >= mob_hp]
    if dot_kill:
        return max(dot_kill, key=lambda r: r["block"])

    damage_first = max(results, key=lambda r: (r["dmg"] + r["dot"], r["block"]))
    if hero_hp is None or mob_atk is None:
        return damage_first

    if hero_hp + _net_hp_change(damage_first, mob_atk, mob_type) > danger_floor:
        return damage_first

    safest = max(results, key=lambda r: (_net_hp_change(r, mob_atk, mob_type), r["dmg"] + r["dot"]))
    if hero_hp + _net_hp_change(safest, mob_atk, mob_type) > danger_floor:
        return safest

    return damage_first
