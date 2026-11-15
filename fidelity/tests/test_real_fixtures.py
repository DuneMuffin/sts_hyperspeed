"""Replay trimmed recordings of the real game. These pin down simulator behaviour that has
been checked against the real thing, so a rule regression fails here.

OPEN_FIELDS lists differences that are understood to exist but not yet explained
(see fidelity/README.md); anything else differing is a failure.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from spire_replay.compare import compare_recording  # noqa: E402
from spire_replay.replay import load  # noqa: E402

# fixture -> (expected steps, fields allowed to differ)
FIXTURES = {
    "fixture_act1_a20_ironclad.jsonl": (71, set()),
    "fixture_act2_floors18_19.jsonl": (19, set()),
    # Exact RNG state. Covers the Red Slaver move-selection fix. The card RNG counter after a
    # Skill Potion is the open question.
    "fixture_slavers_exact_rng.jsonl": (21, {"rng.card_random"}),
}


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_real_recording_replays(name):
    steps, open_fields = FIXTURES[name]
    results = compare_recording(load(ROOT / "recordings" / name))
    assert len(results) == steps
    assert not [r.summary() for r in results if r.error]
    unexpected = [r.summary() for r in results
                  if not r.ok and not {field for field, _, _ in r.diffs} <= open_fields]
    assert not unexpected, "\n".join(unexpected)
