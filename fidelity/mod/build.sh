#!/bin/bash
# Build the Steam State Export mod (from Jialeiv/sts-rl-agent, MIT). It adds the game's exact
# RNG state and energy-per-turn to CommunicationMod's combat JSON, so replays can be checked
# exactly, including shuffles and monster move rolls. Needs a JDK (e.g. `brew install openjdk`).
# Paths are for Steam Workshop installs of ModTheSpire, BaseMod and CommunicationMod on macOS.
set -eu
# Homebrew's JDK is not on PATH by default; use it if no working javac is found.
if ! javac -version >/dev/null 2>&1 && [ -x /opt/homebrew/opt/openjdk/bin/javac ]; then
  PATH="/opt/homebrew/opt/openjdk/bin:$PATH"
fi
RES="${STS_GAME_RESOURCES:-$HOME/Library/Application Support/Steam/steamapps/common/SlayTheSpire/SlayTheSpire.app/Contents/Resources}"
WS="${STS_WORKSHOP:-$HOME/Library/Application Support/Steam/steamapps/workshop/content/646570}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/build"
rm -rf "$OUT"; mkdir -p "$OUT/classes"
javac -source 8 -target 8 -encoding UTF-8 \
  -cp "$RES/desktop-1.0.jar:$WS/1605833019/BaseMod.jar:$WS/2131373661/CommunicationMod.jar:$WS/1605060445/ModTheSpire.jar" \
  -d "$OUT/classes" "$HERE/src/steamstateexport/CombatStatePatch.java"
cp "$HERE/ModTheSpire.json" "$OUT/classes/"
jar cf "$OUT/SteamStateExport.jar" -C "$OUT/classes" .
echo "Built $OUT/SteamStateExport.jar"
if [ "${STS_INSTALL_MOD:-0}" = "1" ]; then
  mkdir -p "$RES/mods"; cp "$OUT/SteamStateExport.jar" "$RES/mods/"; echo "Installed to $RES/mods"
fi
