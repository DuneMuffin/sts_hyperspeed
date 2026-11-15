"""Step-by-step comparison of the simulator against recorded real-game states.

For each pair of consecutive real combat decision states (S_t, S_t+1):
  1. rebuild a simulator BattleContext from S_t,
  2. try every legal action (and any card-select follow-ups),
  3. diff each result against S_t+1.
The step passes if some action reproduces S_t+1 exactly. Otherwise the closest
action and its remaining differences are reported, which localises the
simulator rule (or converter gap) that disagrees with the real game.

No action log is needed, so recordings of ordinary human play work.
"""

from collections import Counter
from dataclasses import dataclass, field

from . import sts
from .snapshot import build_snapshot

UNDECIDED = int(sts.Outcome.UNDECIDED)
CARD_SELECT = int(sts.InputState.CARD_SELECT)
PLAYER_NORMAL = int(sts.InputState.PLAYER_NORMAL)
END_TURN = sts.SearchActionType.END_TURN
MAX_SELECT_DEPTH = 3
MAX_BRANCHES = 400
MAX_SKIPPED_ACTIONS = 4   # recordings can miss states; allow this many actions between two of them
MAX_SEQUENCE_NODES = 30000


def _card_key(card):
    return (int(card["id"]), bool(card.get("upgraded", card.get("upgrades", 0))))


def _card_cost(card):
    return int(card["cost_for_turn"] if "cost_for_turn" in card else card["cost"])


def _powers(powers):
    return {int(p["id"]): int(p["amount"]) for p in powers}


def real_view(snapshot):
    """Comparable view of a real state (already converted by build_snapshot)."""
    player = snapshot["player"]
    return {
        "turn": snapshot["turn"],
        "player": {"hp": player["current_hp"], "block": player["block"], "energy": player["energy"],
                   "powers": _powers(p for p in player["powers"] if "bomb_turns" not in p)},
        "monsters": [{"id": m["id"], "hp": m["current_hp"], "block": m["block"], "move": m["move"],
                      "powers": _powers(m["powers"])}
                     for m in snapshot["monsters"] if not m["is_gone"] and m["current_hp"] > 0],
        "hand": [_card_key(c) for c in snapshot["hand"]],
        "hand_costs": [_card_cost(c) for c in snapshot["hand"]],
        "draw_pile": [_card_key(c) for c in snapshot["draw_pile"]],
        "discard_pile": [_card_key(c) for c in snapshot["discard_pile"]],
        "exhaust_pile": [_card_key(c) for c in snapshot["exhaust_pile"]],
        "potions": list(snapshot["potions"]),
        "rngs": snapshot.get("rngs"),
    }


def sim_view(battle):
    """Comparable view of a simulator state."""
    state = battle.state_dict()
    player = state["player"]
    return {
        "turn": state["turn"],
        "player": {"hp": player["current_hp"], "block": player["block"], "energy": player["energy"],
                   "powers": _powers(player["powers"])},
        "monsters": [{"id": m["id"], "hp": m["current_hp"], "block": m["block"], "move": m["move"],
                      "powers": _powers(m["powers"])}
                     for m in state["monsters"] if not m["is_gone"] and m["current_hp"] > 0],
        "hand": [_card_key(c) for c in state["hand"]],
        "hand_costs": [_card_cost(c) for c in state["hand"]],
        "draw_pile": [_card_key(c) for c in state["draw_pile"]],
        "discard_pile": [_card_key(c) for c in state["discard_pile"]],
        "exhaust_pile": [_card_key(c) for c in state["exhaust_pile"]],
        "potions": list(state["potions"]),
        "rngs": {name: dict(value) for name, value in battle.rng_states.items()},
    }


def diff_views(real, sim, exact_rng, after_end_turn):
    """List of (field, real value, sim value). Empty means the states agree.

    exact_rng: the recording carries the game's RNG state, so every random
    outcome (shuffles, monster move rolls) must match too. Without it, fields
    that depend on hidden randomness are skipped after an end of turn.
    """
    diffs = []

    def check(name, a, b):
        if a != b:
            diffs.append((name, a, b))

    check("turn", real["turn"], sim["turn"])
    for key in ("hp", "block", "energy"):
        check(f"player.{key}", real["player"][key], sim["player"][key])
    check("player.powers", real["player"]["powers"], sim["player"]["powers"])

    check("monsters.count", len(real["monsters"]), len(sim["monsters"]))
    for index, (rm, sm) in enumerate(zip(real["monsters"], sim["monsters"])):
        check(f"monster[{index}].id", rm["id"], sm["id"])
        check(f"monster[{index}].hp", rm["hp"], sm["hp"])
        check(f"monster[{index}].block", rm["block"], sm["block"])
        check(f"monster[{index}].powers", rm["powers"], sm["powers"])
        if exact_rng or not after_end_turn:
            check(f"monster[{index}].move", rm["move"], sm["move"])

    random_draws = after_end_turn and not exact_rng
    for pile in ("hand", "draw_pile", "discard_pile", "exhaust_pile"):
        check(f"{pile}.size", len(real[pile]), len(sim[pile]))
        if random_draws and pile in ("hand", "draw_pile"):
            continue
        if Counter(real[pile]) != Counter(sim[pile]):
            diffs.append((f"{pile}.cards", real[pile], sim[pile]))
        elif pile in ("hand", "draw_pile") and real[pile] != sim[pile]:
            diffs.append((f"{pile}.order", real[pile], sim[pile]))
    if not random_draws and real["hand"] == sim["hand"]:
        check("hand.costs", real["hand_costs"], sim["hand_costs"])
    check("potions", real["potions"], sim["potions"])
    if exact_rng and real["rngs"]:
        for name, value in real["rngs"].items():
            check(f"rng.{name}", value, sim["rngs"].get(name))
    return diffs


def expand(battle):
    """Yield (action descriptions, resulting battle, ended_turn) for every legal
    action from `battle`, following card-select screens to completion."""
    budget = [MAX_BRANCHES]

    def follow(state, path, ended, depth):
        if budget[0] <= 0:
            return
        if int(state.input_state) == CARD_SELECT and int(state.outcome) == UNDECIDED and depth < MAX_SELECT_DEPTH:
            for action in sts.get_legal_actions(state):
                child = state.clone()
                desc = action.desc(child)
                action.execute(child)
                yield from follow(child, path + [desc], ended, depth + 1)
            return
        budget[0] -= 1
        yield path, state, ended

    for action in sts.get_legal_actions(battle):
        child = battle.clone()
        desc = action.desc(child)
        ended = action.action_type == END_TURN
        action.execute(child)
        yield from follow(child, [desc], ended, 0)


@dataclass
class StepResult:
    index: int
    floor: int
    turn: int
    ok: bool
    action: list = field(default_factory=list)
    diffs: list = field(default_factory=list)
    error: str = ""
    candidates: int = 0
    counters: dict = field(default_factory=dict)  # cards/attacks/skills played this turn, for the next step
    hidden: list = field(default_factory=list)  # [(monster id, misc_info)] of living monsters, for the next step
    actions_taken: int = 1  # >1 means the recording skipped intermediate states

    def summary(self):
        head = f"step {self.index} floor {self.floor} turn {self.turn}"
        if self.error:
            return f"{head}: ERROR {self.error}"
        if self.ok:
            note = "" if self.actions_taken == 1 else f" [{self.actions_taken} actions, states skipped in recording]"
            return f"{head}: ok   {' ; '.join(self.action)}{note}"
        lines = [f"{head}: DIFF closest action {' ; '.join(self.action)} ({self.candidates} tried)"]
        lines += [f"    {name}: real={real!r} sim={sim!r}" for name, real, sim in self.diffs]
        return "\n".join(lines)


def is_decision_state(message):
    """True for a real-game message where the player may play a card or end turn."""
    game = message.get("game_state") or {}
    combat = game.get("combat_state")
    if not combat or not message.get("ready_for_command", True):
        return False
    if game.get("screen_type", "NONE") != "NONE":
        return False
    commands = message.get("available_commands") or ["play", "end"]
    if "play" not in commands and "end" not in commands:
        return False
    if combat.get("limbo") or combat.get("card_in_play"):
        return False  # a card is still resolving
    # Pre-combat initialisation states report placeholder intents.
    return all(m.get("intent") != "DEBUG" for m in combat.get("monsters") or [])


def combat_fingerprint(game):
    combat = game["combat_state"]
    return (game.get("floor"), combat.get("turn"), repr(combat.get("player")),
            repr(combat.get("monsters")), repr(combat.get("hand")),
            repr(combat.get("draw_pile")), repr(combat.get("discard_pile")),
            repr(combat.get("exhaust_pile")), repr(game.get("potions")))


def _turn_counters(result, ended):
    if ended:
        return {}
    player = result.state_dict()["player"]
    return {"cards": player["cards_played_this_turn"], "attacks": player["attacks_played_this_turn"],
            "skills": player["skills_played_this_turn"]}


def _hidden_state(result):
    return [(m["id"], m["misc_info"]) for m in result.state_dict()["monsters"] if not m["is_gone"]]


def _apply_hidden(snapshot, hidden):
    """Fill in monster state the real game does not expose (charge counters,
    "has used X" flags) from the simulator state that matched the previous step."""
    living = [m for m in snapshot["monsters"] if not m["is_gone"]]
    if not hidden or len(hidden) != len(living):
        return
    for monster, (monster_id, misc) in zip(living, hidden):
        if monster["id"] == monster_id and not monster.get("misc_known"):
            monster["misc_info"] = misc


def _search_sequence(battle, target, exact_rng):
    """Shortest sequence of 2..MAX_SKIPPED_ACTIONS actions that reproduces `target`."""
    budget = [MAX_SEQUENCE_NODES]
    for limit in range(2, MAX_SKIPPED_ACTIONS + 1):
        seen = set()

        def walk(state, path, ended_any, depth):
            for step_path, result, ended in expand(state):
                if budget[0] <= 0:
                    return None
                budget[0] -= 1
                if int(result.outcome) != UNDECIDED:
                    continue
                full = path + step_path
                # After an end of turn the hand is redrawn from hidden order, so skip
                # the random-draw fields for the rest of the sequence too.
                now_ended = ended_any or ended
                if depth + 1 == limit:
                    if not diff_views(target, sim_view(result), exact_rng, now_ended):
                        return full, result, now_ended, limit
                    continue
                key = repr(result.state_dict())
                if key in seen:
                    continue
                seen.add(key)
                found = walk(result, full, now_ended, depth + 1)
                if found:
                    return found
            return None

        found = walk(battle, [], False, 0)
        if found:
            return found
    return None


def compare_step(index, before, after, counters=None, hidden=None):
    """Compare one real transition. `before`/`after` are game_state dicts.

    `counters` carries cards/attacks/skills played so far this turn, which the
    real game's JSON does not expose but relics such as Kunai depend on."""
    floor = int(before.get("floor") or 0)
    turn = int((before.get("combat_state") or {}).get("turn") or 0)
    try:
        snap_before = build_snapshot(before, counters)
        _apply_hidden(snap_before, hidden)
        snap_after = build_snapshot(after)
        battle = sts.BattleContext.from_snapshot(snap_before, 0)
    except Exception as exc:  # unmapped card / monster move / power
        return StepResult(index, floor, turn, False, error=f"{type(exc).__name__}: {exc}")

    exact_rng = bool(snap_before.get("rngs"))
    target = real_view(snap_after)
    if real_view(snap_before) == target:
        return None  # only cosmetic fields changed (animations, intent display); not a transition
    best = None
    count = 0
    for path, result, ended in expand(battle):
        count += 1
        if int(result.outcome) != UNDECIDED:
            continue  # the real fight continued, so this action cannot be the one taken
        diffs = diff_views(target, sim_view(result), exact_rng, ended)
        if not diffs:
            return StepResult(index, floor, turn, True, action=path, candidates=count,
                              counters=_turn_counters(result, ended), hidden=_hidden_state(result))
        if best is None or len(diffs) < len(best[1]):
            best = (path, diffs, _turn_counters(result, ended), _hidden_state(result))
    # No single action explains the transition. The recording may have skipped
    # states, so look for a short sequence of actions that does.
    found = _search_sequence(battle, target, exact_rng)
    if found:
        path, result, ended, depth = found
        return StepResult(index, floor, turn, True, action=path, candidates=count,
                          counters=_turn_counters(result, ended), hidden=_hidden_state(result),
                          actions_taken=depth)
    if best is None:
        return StepResult(index, floor, turn, False, error="no legal action keeps the fight going", candidates=count)
    if not exact_rng and any("DISCOVERY" in step for step in best[0]) and {n for n, _, _ in best[1]} <= {"hand.cards"}:
        return StepResult(index, floor, turn, True, action=best[0] + ["(random card offer not checked: no RNG state)"],
                          candidates=count, counters=best[2], hidden=best[3])
    return StepResult(index, floor, turn, False, action=best[0], diffs=best[1], candidates=count,
                      counters=best[2], hidden=best[3])


def compare_recording(messages):
    """Compare every in-combat transition in a list of CommunicationMod messages."""
    results = []
    previous = None
    counters, hidden = {}, []
    for message in messages:
        if not is_decision_state(message):
            if not (message.get("game_state") or {}).get("combat_state"):
                previous, counters, hidden = None, {}, []  # left combat; do not pair across fights
            continue
        game = message["game_state"]
        if previous is not None and combat_fingerprint(previous) == combat_fingerprint(game):
            continue
        same_fight = (previous is not None and previous.get("floor") == game.get("floor")
                      and previous.get("seed") == game.get("seed")
                      and int(game["combat_state"].get("turn") or 0) >= int(previous["combat_state"].get("turn") or 0))
        if same_fight:
            result = compare_step(len(results), previous, game, counters, hidden)
            if result is None:
                continue
            results.append(result)
            counters, hidden = result.counters, result.hidden
        else:
            counters, hidden = {}, []
        previous = game
    return results


def summarize(results):
    total = len(results)
    ok = sum(r.ok for r in results)
    errors = sum(bool(r.error) for r in results)
    fields = Counter()
    for result in results:
        for name, _, _ in result.diffs:
            fields[name.split("[")[0] if name.startswith("monster[") else name] += 1
    return {"steps": total, "ok": ok, "diff": total - ok - errors, "error": errors,
            "diff_fields": dict(fields.most_common())}
