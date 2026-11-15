"""Replay a recording of real-game states through the simulator and report differences.

    python -m spire_replay.replay recordings/run.jsonl [--all] [--limit N]

A recording is a JSON-lines file of CommunicationMod messages (see recorder.py).
"""

import argparse
import json
import sys

from .compare import compare_recording, summarize


def load(path):
    messages = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if "repeat" in record:  # the previous message stayed unchanged for this many polls
                if messages:
                    messages[-1]["_repeats"] = record["repeat"]
                continue
            messages.append(record.get("message", record))
    return messages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("recording")
    parser.add_argument("--all", action="store_true", help="print passing steps too")
    parser.add_argument("--limit", type=int, default=40, help="max differing steps to print")
    args = parser.parse_args(argv)

    messages = load(args.recording)
    results = compare_recording(messages)
    has_rng = any("rngs" in ((m.get("game_state") or {}).get("combat_state") or {}) for m in messages)
    shown = 0
    for result in results:
        if result.ok and not args.all:
            continue
        if not result.ok:
            shown += 1
            if shown > args.limit:
                continue
        print(result.summary())
    summary = summarize(results)
    print(f"\n{summary['steps']} steps: {summary['ok']} match, {summary['diff']} differ, "
          f"{summary['error']} could not be converted")
    print("exact RNG state in recording:", "yes" if has_rng else
          "NO (random outcomes after each end of turn are not checked)")
    if summary["diff_fields"]:
        print("differing fields:", summary["diff_fields"])
    return 0 if summary["ok"] == summary["steps"] else 1


if __name__ == "__main__":
    sys.exit(main())
