#!/usr/bin/env python3
"""Recorder: run as CommunicationMod's external process while you play by hand.

Writes the game's state messages to recordings/real_<timestamp>.jsonl. It never
sends a game action, so you play normally.

Left alone, CommunicationMod skips many states during manual play (the first
recording had 71 combat transitions for a whole act). So by default this script
polls: it sends the read-only `state` command a few times a second and writes
every message that differs from the previous one, plus how many polls each one
stayed unchanged. Pass --no-poll for the old purely passive behaviour.

stdout is CommunicationMod's command channel: only "ready" and "state" are ever
written to it.

Set in ~/Library/Preferences/ModTheSpire/CommunicationMod/config.properties:
    command=<abs path to .venv/bin/python> <abs path to this file>
"""

import argparse
import json
import sys
import threading
import time
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "recordings"


def _send(command, lock):
    with lock:
        sys.stdout.write(command + "\n")
        sys.stdout.flush()


def _poll(interval, lock, stop):
    while not stop.wait(interval):
        try:
            _send("state", lock)
        except (BrokenPipeError, ValueError):
            return


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-poll", action="store_true")
    parser.add_argument("--interval", type=float, default=0.2, help="seconds between polls")
    args = parser.parse_args(argv)

    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / time.strftime("real_%Y%m%d_%H%M%S.jsonl")
    lock, stop = threading.Lock(), threading.Event()
    _send("ready", lock)
    if not args.no_poll:
        threading.Thread(target=_poll, args=(args.interval, lock, stop), daemon=True).start()

    # Write every message that differs from the one before it. Repeats (the state
    # sitting unchanged between polls) are counted and written as a small
    # {"repeat": n} line, so the replay can tell settled states from mid-animation ones.
    previous_line, repeats = None, 0
    try:
        with open(path, "a", encoding="utf-8") as out:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                if line == previous_line:
                    repeats += 1
                    continue
                if repeats:
                    out.write(json.dumps({"t": time.time(), "repeat": repeats}) + "\n")
                previous_line, repeats = line, 0
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    message = {"unparsed": line}
                out.write(json.dumps({"t": time.time(), "message": message}) + "\n")
                out.flush()
    finally:
        stop.set()


if __name__ == "__main__":
    main()
