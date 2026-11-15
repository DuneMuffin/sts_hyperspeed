"""Shrink a raw recording into a small test fixture.

    python -m spire_replay.trim recordings/real_<timestamp>.jsonl recordings/fixture_<name>.jsonl

Keeps only the messages and fields the replay reads (combat decision states plus
one marker between fights), dropping the map, deck, shop and screen data that make
raw recordings megabytes long. Replaying the fixture gives the same result.
"""

import json
import sys

from .compare import is_decision_state
from .replay import load

GAME_KEYS = ("screen_type", "seed", "floor", "act", "ascension_level", "class", "relics", "potions", "combat_state")
CARD_KEYS = ("id", "name", "cost", "upgrades", "misc", "uuid")
MONSTER_KEYS = ("id", "name", "current_hp", "max_hp", "block", "intent", "half_dead", "is_gone", "move_id",
                "last_move_id", "second_last_move_id", "move_base_damage", "move_adjusted_damage", "move_hits", "powers")


def _cards(cards):
    return [{k: c[k] for k in CARD_KEYS if k in c} for c in cards or []]


def trim_message(message):
    game = message["game_state"]
    out = {k: game[k] for k in GAME_KEYS if k in game}
    out["relics"] = [{k: r[k] for k in ("id", "name", "counter") if k in r} for r in game.get("relics") or []]
    out["potions"] = [{k: p[k] for k in ("id", "name") if k in p} for p in game.get("potions") or []]
    combat = dict(game["combat_state"])
    for pile in ("hand", "draw_pile", "discard_pile", "exhaust_pile", "limbo"):
        combat[pile] = _cards(combat.get(pile))
    combat.pop("card_in_play", None)
    combat["monsters"] = [{k: m[k] for k in MONSTER_KEYS if k in m} for m in combat.get("monsters") or []]
    return {"available_commands": [c for c in message.get("available_commands") or [] if c in ("play", "end")],
            "ready_for_command": True, "game_state": out}


def trim(messages):
    out, in_fight = [], False
    for message in messages:
        if is_decision_state(message):
            trimmed = trim_message(message)
            if not out or out[-1] != trimmed:
                out.append(trimmed)
            in_fight = True
        elif in_fight and not (message.get("game_state") or {}).get("combat_state"):
            game = message.get("game_state") or {}
            out.append({"game_state": {"screen_type": game.get("screen_type"), "floor": game.get("floor")}})
            in_fight = False
    return out


def main(argv=None):
    source, target = (argv or sys.argv[1:])[:2]
    messages = trim(load(source))
    with open(target, "w", encoding="utf-8") as handle:
        for message in messages:
            handle.write(json.dumps(message, separators=(",", ":")) + "\n")
    print(f"{len(messages)} messages written to {target}")


if __name__ == "__main__":
    main()
