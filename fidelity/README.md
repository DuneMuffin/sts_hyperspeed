# Fidelity: checking the simulator against the real game

A replay test for this simulator. It takes recordings of real Slay the Spire combat (captured
through CommunicationMod), rebuilds each state in the simulator, tries every legal action, and
reports any real transition the simulator cannot reproduce exactly.

- `spire_replay/snapshot.py` — real-game JSON → simulator snapshot (vendored from
  `Jialeiv/sts-rl-agent`, MIT; local changes marked `LOCAL:`).
- `spire_replay/compare.py` — the comparison. No action log is needed, so recordings of ordinary
  hand-played games work.
- `spire_replay/replay.py` — command line: replay a recording and print differences.
- `spire_replay/recorder.py` — CommunicationMod process that records a game you play by hand.
- `spire_replay/trim.py` — shrink a raw recording into a small fixture.
- `spire_replay/synth.py` — simulator-generated recordings, used to self-test the harness.
- `mod/` — Steam State Export mod: adds the game's exact RNG state to its combat JSON, so shuffles
  and monster move rolls are checked too (from `Jialeiv/sts-rl-agent`, MIT).
- `recordings/` — `fixture_*` are trimmed real recordings used by the tests; raw `real_*` files
  are gitignored.

## Run

Build the `slaythespire` module first (see the top-level README), then from this folder:

```bash
python -m pytest tests -q
python -m spire_replay.replay recordings/fixture_slavers_exact_rng.jsonl --all
```

## Record a real game (macOS, Steam Workshop mods)

1. Build and install the RNG mod (needs a JDK), then tick "Steam State Export" in ModTheSpire:
   `STS_INSTALL_MOD=1 mod/build.sh`
2. In `~/Library/Preferences/ModTheSpire/CommunicationMod/config.properties` set
   `command=<python> <abs path>/fidelity/spire_replay/recorder.py`
3. Restart the game and play Ironclad normally. A file appears in `recordings/`.
4. `python -m spire_replay.replay recordings/real_<timestamp>.jsonl`

## Reading a difference

`ok` means some legal simulator action (or short sequence, if the recording skipped states)
reproduces the real next state exactly. A `DIFF` is one of:

1. **Harness gap** — the game's JSON cannot fully describe a simulator state (hidden monster
   counters, internal flags, states captured mid-animation). Fix here.
2. **Simulator rule bug** — confirm against the game's own code before fixing, e.g.
   `javap -c -p -cp <game>/desktop-1.0.jar com.megacrit.cardcrawl.monsters.exordium.SlaverRed`.
3. **Unexplained** — list it below.

## Results (Nov 2026, A20 Ironclad)

| Fixture | Steps | Match | RNG checked |
| --- | --- | --- | --- |
| Act 1 | 71 | 71 | no |
| Act 2, floors 18–19 | 19 | 19 | no |
| Slavers | 21 | 19 | yes |

Simulator bugs found and fixed: Red Slaver move selection (Entangle never recorded as used; Stab
threshold 50 instead of 55; Scrape allowed twice in a row at A17+).

Open question: after a Skill Potion the real game's card RNG counter advances by 19, then by 30
more with no visible state change; the simulator advances it by 3. The offered cards matched.
Unknown whether this is the base game or another mod (mintySpire, StSLib were loaded).

## Known harness gaps

Self-test: 2,411 of 2,434 simulator-generated steps replay exactly. The rest:

- Panache's cards-remaining counter and the Guardian's Mode Shift growth are not restored.
- Hidden monster state is carried forward from the previous matched step, so a recording that
  starts mid-fight can mis-predict a monster's next move.
- A cost changed for this turn only restores as changed for the whole combat.
- Ironclad only: no orbs or stances.
