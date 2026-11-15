"""Harness self-test sweep: simulated runs replayed through the comparer must show no differences."""
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spire_replay.compare import compare_recording, summarize  # noqa: E402
from spire_replay.synth import synthesize_run  # noqa: E402

n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
start = time.time()
total, fields, skips, errors, floors, examples = Counter(), Counter(), Counter(), Counter(), [], []
for seed in range(1, n + 1):
    messages, skipped = synthesize_run(seed, ascension=0 if seed % 2 else 20)
    floors.append(max((m["game_state"]["floor"] for m in messages), default=0))
    skips.update(why for _, _, why in skipped)
    results = compare_recording(messages)
    summary = summarize(results)
    for key in ("steps", "ok", "diff", "error"):
        total[key] += summary[key]
    fields.update(summary["diff_fields"])
    for result in results:
        if result.error:
            errors[result.error] += 1
        elif not result.ok and len(examples) < 8:
            examples.append((seed, result))
print(dict(total), f"{time.time() - start:.0f}s", "deepest floors:", sorted(floors)[-8:])
print("diff fields:", dict(fields.most_common(15)))
print("errors:", errors.most_common(12))
print("skipped fights:", skips.most_common(12))
for seed, result in examples:
    print("seed", seed, result.summary()[:1400])
