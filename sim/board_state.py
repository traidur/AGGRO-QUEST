"""
BoardState -- shared zone/node/deck state for N=1-4 heroes, replacing macro_sim.py's blind
per-pull rng.choices() mob draw with a real, visible, finite deck dealt onto each occupied
Zone's Nodes every turn. Part 3a of unified-sprouting-aurora.md's revised plan.

Every locked number and rule below is read directly off OPEN_QUESTIONS.md's "Zone-node mob
dealing, and node-based (not mob-based) loot sourcing" entry, not off the plan document's own
paraphrase of it -- a first draft of this file got the deck composition (missed the Spice
slots) and the Discard semantics (assumed a sticky "refill only if empty" model instead of the
real full-reset-every-turn rule) wrong by trusting that paraphrase instead of the primary
source. Caught and corrected before this file was written, not after -- see the two
corresponding checkpoints in this project's session history if the reasoning needs revisiting.

Solo mode (mode="solo", one hero) is the N=1 degenerate case of the same machinery, not a
separate code path -- per the plan, this is what gets proven bit-for-bit identical to
macro_sim.py's existing run_one_trip/_trip_chain before either of those functions is retired.
Competitive N=2-4 and co-op modes are NOT built here (co-op is explicitly blocked on open
questions in OPEN_QUESTIONS.md) -- this file's scope is data shapes plus the Deal/Discard
mechanics that are identical across every mode. The Move-and-declare/resolve-contested turn
loop (including the "deal-on-entry" first-arrival rule, checkpointed separately: entering a
new Zone triggers an immediate deal for it as part of that same turn, before the hero
declares a node -- no blind commitment into an unseen board) is NOT built here; that's the
next layer, deliberately left for its own checkpoint given how much of this file's own design
had to be corrected against the primary source before writing a single line.

**Locked rules this file implements:**
- Deck composition (OPEN_QUESTIONS.md, "Tier 1's actual two decks, worked example"): Level 1 =
  18 Standard (3 copies each of Grunt/Bruiser/Enforcer/Raider/Ambusher/Scout) + 1 Spice = 19
  cards. Level 2 = 18 Standard + 3 Elite (1 each of Bulwark/Berserker/Warlord) + 2 Spice = 23
  cards. Spice itself isn't designed yet (still Unresolved in OPEN_QUESTIONS.md) -- reserved
  as inert placeholder slots (the SPICE marker) so the deck size and odds match the locked
  ratios now, with no invented mechanic attached. A caller must treat a Spice-dealt node as
  not a legal pull target until Spice itself is designed (see is_spice()).
- Deal is a FULL, unconditional refresh of every Node in a Zone, not a "top up what's missing"
  partial refill -- "this is a full refresh every turn, not a partial one" (verbatim).
- End-of-turn cleanup discards EVERY currently-dealt card in an occupied Zone, played or not,
  and nothing carries into the next turn's Deal -- "a mob you didn't get to this turn is
  simply gone" (verbatim).
- The deck reshuffles its discard pile back in whenever the draw pile runs dry -- "never
  actually stays empty" (verbatim).
- Node refill is replace-not-stack; a Node holds exactly one card at a time (solo/competitive
  -- co-op's multi-mob exception is out of scope here).
- HeroBoardState.position = (zone_or_border: int|str, node: str|None). node is a real Node
  name, the literal string "town" (Town is a real board position per this project's checkpoint
  discussion, not an abstract event the way it was pre-BoardState), or None (standing on a
  Border Node itself, not yet in either connected Zone).
- Capacity/contention: real Nodes have capacity 1; Town has unlimited capacity and is never
  contested -- it's a hub, not a fight; Border Nodes use the already-locked 3-case arrival
  ordering (OPEN_QUESTIONS.md's "Border Nodes and Scouted Pull"), not a capacity contest.
"""
from dataclasses import dataclass, field

import condensed_trip as T
import leveling_validation as LV

LEVEL2_TIER = "standard_l2"

# Reserved deck-slot marker -- not a real mob name, no mechanic defined yet
# (OPEN_QUESTIONS.md's "Deterministic Spice" entry is still Unresolved). Dealt like any other
# card so the deck's real size/odds match the locked ratios, but nothing in this codebase
# currently knows how to resolve declaring it.
SPICE = "__spice__"

_ELITE_NAMES = list(LV.ELITE_MELEE.keys())
_STANDARD_MOBS = T.MOB_TIERS["standard"]

# Per-level deck recipe: {card_name: copy_count}. Numbers are the locked ones from
# OPEN_QUESTIONS.md's "Tier 1's actual two decks, worked example" -- transcribed, not derived.
LEVEL_DECK_COMPOSITION = {
    1: {**{mob: 3 for mob in _STANDARD_MOBS}, SPICE: 1},
    2: {**{mob: 3 for mob in _STANDARD_MOBS}, **{elite: 1 for elite in _ELITE_NAMES}, SPICE: 2},
}


def is_spice(card_name):
    return card_name == SPICE


@dataclass
class LevelDeck:
    """One shared deck per level (not per Zone) -- OPEN_QUESTIONS.md's "the deck is curated
    per level, not per zone" (verbatim), rejected the per-zone-recipe alternative for authoring
    overhead."""
    draw_pile: list
    discard_pile: list = field(default_factory=list)

    @classmethod
    def new(cls, level, rng):
        composition = LEVEL_DECK_COMPOSITION[level]
        cards = [name for name, count in composition.items() for _ in range(count)]
        rng.shuffle(cards)
        return cls(draw_pile=cards)

    def draw(self, rng):
        """Reshuffles discard back into draw automatically when the draw pile runs dry --
        matches the locked rule exactly, no special-casing needed by any caller."""
        if not self.draw_pile:
            if not self.discard_pile:
                raise RuntimeError("LevelDeck exhausted with nothing to reshuffle -- composition is empty")
            self.draw_pile, self.discard_pile = self.discard_pile, []
            rng.shuffle(self.draw_pile)
        return self.draw_pile.pop()

    def discard(self, card_name):
        self.discard_pile.append(card_name)


@dataclass
class ZoneBoardState:
    """Only exists for currently-occupied Zones -- "an unoccupied zone's nodes aren't tracked
    or refreshed at all" (verbatim). dealt maps each of that Zone's real Node names to the
    card currently sitting on it (a mob name, an Elite name, or SPICE) -- never missing a key
    once a Deal has happened for this Zone this turn, since Deal is a full, unconditional
    refresh of every Node, not a partial one."""
    dealt: dict = field(default_factory=dict)


@dataclass
class HeroBoardState:
    class_name: str
    hp: float
    max_hp: float
    position: tuple  # (zone_or_border: int|str, node: str|None)
    bag: list
    locked: list
    gold: int = 0
    xp: int = 0
    active_quests: list = field(default_factory=list)
    acquired: set = field(default_factory=set)
    consumables_used: dict = field(default_factory=lambda: {"food": 0, "potion": 0})
    corpse_node: object = None  # (zone, node) of an unrecovered corpse, or None
    alive: bool = True


@dataclass
class BoardState:
    mode: str  # "solo" for now -- "competitive"/"coop" arrive later, once solo is verified
    heroes: list
    zones: dict  # zone_id -> ZoneBoardState, only currently-occupied Zones present
    level_decks: dict  # level (1 or 2) -> LevelDeck
    turn_num: int = 0
    priority_token_holder: int = 0  # hero_idx -- competitive/co-op only, unused in solo


def deal_zone(state, zone_id, level, node_names, rng):
    """Full, unconditional deal to every Node named in node_names for this one Zone --
    "every node in an occupied zone gets a fresh card from that level's shared deck,
    unconditionally" (verbatim). The single primitive both real invocation contexts share:
    the top-of-turn refresh for a Zone a hero already occupied last turn, and the reactive
    "deal-on-entry" deal for a Zone a hero is moving into for the first time this turn (the
    turn-loop layer, not built here, decides which Zones to call this for and when)."""
    if zone_id not in state.zones:
        state.zones[zone_id] = ZoneBoardState()
    deck = state.level_decks[level]
    zone_board = state.zones[zone_id]
    for node_name in node_names:
        zone_board.dealt[node_name] = deck.draw(rng)


def discard_zone(state, zone_id, level):
    """End-of-turn cleanup for one Zone: every currently-dealt card goes to that level's
    discard pile, played or not -- "nothing persists into next turn; a mob you didn't get to
    this turn is simply gone" (verbatim). Leaves the Zone's own ZoneBoardState in place
    (empty dealt dict) -- whether to drop it from state.zones entirely once nobody's there
    anymore is the turn-loop layer's call, not this function's."""
    deck = state.level_decks[level]
    zone_board = state.zones[zone_id]
    for card_name in zone_board.dealt.values():
        deck.discard(card_name)
    zone_board.dealt.clear()
