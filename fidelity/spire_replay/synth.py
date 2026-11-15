"""Generate fake "real game" recordings from the simulator itself.

Plays simulated runs with random combat actions and writes each decision state
in CommunicationMod's JSON shape. Replaying such a recording must give zero
differences: any difference is a gap in the converter, in the simulator's
snapshot restore, or in the comparer, not in the game rules. This is the
harness's own self-test and needs no game client.
"""

import random

from . import sts
from .snapshot import MONSTER_POWER_IDS, MOVE_NAMES, OBSERVABLE_MISC

UNDECIDED = sts.Outcome.UNDECIDED
CARD_SELECT = sts.InputState.CARD_SELECT

_RAW_MOVE = {(monster, name): raw for (monster, raw), name in MOVE_NAMES.items()}
_MONSTER_POWER_NAME = {power_id: name for name, power_id in MONSTER_POWER_IDS.items()}


class Unexportable(Exception):
    """The simulator state uses something the real-game format cannot express yet."""


def _card(card):
    return {"id": sts.CardId(card["id"]).name, "name": card["name"], "uuid": str(card["unique_id"]),
            "cost": card["cost_for_turn"], "upgrades": int(card["upgraded"]), "misc": card["misc"]}


def _raw_move(monster, move_name):
    if move_name == "INVALID":
        return -1
    raw = _RAW_MOVE.get((monster, move_name))
    if raw is None:
        raise Unexportable(f"no raw move id for {monster} {move_name}")
    return raw


def _monster(monster, move_names):
    observable = OBSERVABLE_MISC.get(monster["move_name"])
    extra = {observable: monster["misc_info"]} if observable else {}
    return {
        **extra,
        "id": monster["name"], "name": monster["name"],
        "current_hp": monster["current_hp"], "max_hp": monster["max_hp"], "block": monster["block"],
        "half_dead": monster["half_dead"], "is_gone": monster["is_gone"], "intent": "UNKNOWN",
        "move_id": _raw_move(monster["name"], monster["move_name"]),
        "last_move_id": _raw_move(monster["name"], move_names[monster["last_move"]]),
        "powers": [{"id": _MONSTER_POWER_NAME.get(p["id"], p["name"]), "amount": p["amount"]}
                   for p in monster["powers"]],
    }


def export_message(gc, battle, ascension, move_names):
    """One CommunicationMod-shaped message for the current simulator state."""
    state = battle.state_dict()
    player = state["player"]
    if any(player["bombs"]):
        raise Unexportable("The Bomb")
    counters = dict(battle.snapshot_counters)
    relic_counters = {"HAPPY_FLOWER": "happy_flower", "INCENSE_BURNER": "incense_burner",
                      "INK_BOTTLE": "ink_bottle", "INSERTER": "inserter", "NUNCHAKU": "nunchaku",
                      "PEN_NIB": "pen_nib", "SUNDIAL": "sundial"}
    relics = []
    for relic in gc.relics:
        name = relic.id.name
        relics.append({"id": name, "name": name, "counter": counters.get(relic_counters.get(name), -1)})
    return {
        "available_commands": ["play", "end", "state"], "ready_for_command": True, "in_game": True,
        "game_state": {
            "screen_type": "NONE", "seed": gc.seed, "floor": gc.floor_num, "ascension_level": ascension,
            "relics": relics,
            "potions": [{"id": name, "name": name} for name in state["potion_names"]],
            "combat_state": {
                "turn": state["turn"],
                "cards_discarded_this_turn": player["cards_discarded_this_turn"],
                "times_damaged": player["times_damaged"],
                "energy_per_turn": player["energy_per_turn"],
                "rngs": {name: {"seed0": str(v["seed0"]), "seed1": str(v["seed1"]), "counter": v["counter"]}
                         for name, v in battle.rng_states.items()},
                "player": {"current_hp": player["current_hp"], "max_hp": player["max_hp"],
                           "block": player["block"], "energy": player["energy"],
                           "powers": [{"id": p["name"], "amount": p["amount"], "just_applied": p["just_applied"]}
                                      for p in player["powers"]]},
                "hand": [_card(c) for c in state["hand"]],
                "draw_pile": [_card(c) for c in state["draw_pile"]],
                "discard_pile": [_card(c) for c in state["discard_pile"]],
                "exhaust_pile": [_card(c) for c in state["exhaust_pile"]],
                "monsters": [_monster(m, move_names) for m in state["monsters"]],
            },
        },
    }


def _move_names():
    """Simulator move-id -> name table, recovered through the name lookup binding."""
    names = {0: "INVALID"}
    for name in set(MOVE_NAMES.values()):
        names[sts.monster_move_id_from_name(name)] = name
    return names


class _Default(dict):
    def __missing__(self, key):
        raise Unexportable(f"move id {key} has no name mapping")


def synthesize_run(seed, ascension=20, max_fights=60, rng=None, random_rate=0.3, simulations=100):
    """Play one simulated run; return (messages, skipped_fights).

    Combat actions are a mix of the simulator's own search (so runs get deep
    enough to meet later acts) and uniformly random legal actions (so unusual
    lines are covered too)."""
    rng = rng or random.Random(seed)
    move_names = _Default(_move_names())
    gc = sts.GameContext(sts.CharacterClass.IRONCLAD, seed, ascension)
    messages, skipped = [], []
    for _ in range(max_fights):
        agent = sts.Agent()
        agent.pause_on_battle = True
        agent.simulation_count_base = 50
        agent.playout(gc)
        if gc.outcome != sts.GameOutcome.UNDECIDED or gc.screen_state != sts.ScreenState.BATTLE:
            break
        battle = sts.BattleContext()
        battle.init(gc)
        fight = []
        try:
            for _ in range(2000):
                if battle.outcome != UNDECIDED:
                    break
                if battle.input_state != CARD_SELECT:
                    fight.append(export_message(gc, battle, ascension, move_names))
                actions = sts.get_legal_actions(battle)
                if not actions:
                    break
                if rng.random() < random_rate or battle.input_state == CARD_SELECT:
                    action = rng.choice(actions)
                else:
                    action = sts.mcts_recommend(battle, simulations)
                    if not action.is_valid(battle):
                        action = rng.choice(actions)
                action.execute(battle)
        except Unexportable as exc:
            skipped.append((gc.floor_num, str(gc.encounter), str(exc)))
            fight = fight[:-1] if fight else fight
        messages.extend(fight)
        messages.append({"available_commands": ["proceed"], "ready_for_command": True, "in_game": True,
                         "game_state": {"screen_type": "COMBAT_REWARD", "seed": gc.seed, "floor": gc.floor_num}})
        if battle.outcome == UNDECIDED:
            # Fight abandoned (unexportable or stuck): let the built-in agent finish the run instead.
            agent = sts.Agent()
            agent.simulation_count_base = 50
            agent.playout(gc)
            break
        battle.exit_battle(gc)
    return messages, skipped
