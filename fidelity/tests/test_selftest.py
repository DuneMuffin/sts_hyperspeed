"""Harness self-test: simulator-generated recordings must replay with (almost) no differences.

Any difference here is a gap in snapshot restore / conversion / comparison, not a
game-rule bug. The known gaps are listed in README.md; the bound below is the
current count and should only ever go down.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spire_replay.compare import compare_recording, summarize  # noqa: E402
from spire_replay.synth import synthesize_run  # noqa: E402

KNOWN_GAP_STEPS = 23


def test_simulated_recordings_replay_cleanly():
    steps = ok = errors = 0
    for seed in range(1, 31):
        messages, _ = synthesize_run(seed, ascension=0 if seed % 2 else 20)
        summary = summarize(compare_recording(messages))
        steps += summary["steps"]
        ok += summary["ok"]
        errors += summary["error"]
    assert steps > 2000
    assert errors == 0
    assert steps - ok <= KNOWN_GAP_STEPS, f"{steps - ok} differing steps (known gaps: {KNOWN_GAP_STEPS})"


def test_a_wrong_rule_is_detected():
    """Corrupt one real value and check the comparer reports it (the test can fail)."""
    messages, _ = synthesize_run(2, ascension=0)
    states = [m for m in messages if "combat_state" in m["game_state"]]
    states[5]["game_state"]["combat_state"]["player"]["current_hp"] -= 1
    results = compare_recording(messages)
    assert any(not r.ok and any(name == "player.hp" for name, _, _ in r.diffs) for r in results)
