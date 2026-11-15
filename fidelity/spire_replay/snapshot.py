"""Convert CommunicationMod combat JSON into an sts_lightspeed snapshot dict.

Vendored from Jialeiv/sts-rl-agent (steam/steam_mcts.py, commit 039c199, MIT
licence, see LICENSE.sts-rl-agent), trimmed to the conversion tables and
build_snapshot. Local changes are marked with "LOCAL:".
"""

import re

from . import sts

CARD_ALIASES = {"Strike_R": "STRIKE_RED", "Defend_R": "DEFEND_RED"}
MONSTER_ALIASES = {
    "FuzzyLouseNormal": "RED_LOUSE",
    "FuzzyLouseDefensive": "GREEN_LOUSE",
    "TheGuardian": "THE_GUARDIAN",
    "Healer": "MYSTIC",
    "Champ": "THE_CHAMP",
    "Maw": "THE_MAW",
    "SlaverBlue": "BLUE_SLAVER",
    "SlaverRed": "RED_SLAVER",
    "GremlinWarrior": "MAD_GREMLIN",
    "GremlinThief": "SNEAKY_GREMLIN",
    "GremlinFat": "FAT_GREMLIN",
    "GremlinTsundere": "SHIELD_GREMLIN",
    "BanditChild": "POINTY",
    "BanditLeader": "ROMEO",
    "BanditBear": "BEAR",
    "Serpent": "SPIRE_GROWTH",
    "SlaverBoss": "TASKMASTER",
}
PLAYER_POWER_ALIASES = {
    "Weakened": "WEAK",
    "Flex": "LOSE_STRENGTH",
    "Confusion": "CONFUSED",
    "Regeneration": "REGEN",
    "DexLoss": "LOSE_DEXTERITY",
    "DuplicationPower": "DUPLICATION",
    "NoBlockPower": "NO_BLOCK",
    "Wraith Form v2": "WRAITH_FORM",
    "IntangiblePlayer": "INTANGIBLE",
    "EndTurnDeath": "BLASPHEMER",
    "MasterRealityPower": "MASTER_REALITY",
    "WrathNextTurnPower": "WRATH_NEXT_TURN",
    "DevaForm": "DEVA",
    "DevotionPower": "DEVOTION",
    "Draw Card": "DRAW_CARD_NEXT_TURN",
    "EstablishmentPower": "ESTABLISHMENT",
    "WireheadingPower": "FORESIGHT",
    "LikeWaterPower": "LIKE_WATER",
    "OmegaPower": "OMEGA",
    "WaveOfTheHandPower": "WAVE_OF_THE_HAND",
    "EnergizedBlue": "ENERGIZED",
    "Hello": "HELLO_WORLD",
}
MONSTER_POWER_ALIASES = {
    "Anger": "ANGRY",
    "BeatOfDeath": "BEAT_OF_DEATH",
    "BlockReturnPower": "BLOCK_RETURN",
    "Compulsive": "REACTIVE",
    "CorpseExplosionPower": "CORPSE_EXPLOSION",
    "Generic Strength Up Power": "GENERIC_STRENGTH_UP",
    "Life Link": "REGROW",
    "Lockon": "LOCK_ON",
    "PathToVictoryPower": "MARK",
    "Regenerate": "REGEN",
    "Weakened": "WEAK",
}
# MonsterStatusEffects.h has a stale enum-name array for these bool/secondary slots.
# Use the actual enum ordinals so snapshot restoration cannot silently select a neighbor.
MONSTER_POWER_IDS = {
    "REACTIVE": 32,
    "SHARP_HIDE": 33,
    "ASLEEP": 34,
    "BARRICADE": 35,
    "MINION": 36,
    "MINION_LEADER": 37,
    "PAINFUL_STABS": 38,
    "REGROW": 39,
}
IGNORED_MONSTER_POWERS = {"Split", "Explosive", "Unawakened"}  # Rebuilt from monster HP/moves.
POTION_ALIASES = {"Potion Slot": "EMPTY_POTION_SLOT"}
SMOKE_BOMB_ID = sts.potion_id_from_name("SMOKE_BOMB")
BOSS_ENCOUNTERS = {
    "THE_GUARDIAN": "THE_GUARDIAN", "SLIME_BOSS": "SLIME_BOSS", "HEXAGHOST": "HEXAGHOST",
    "BRONZE_AUTOMATON": "AUTOMATON", "THE_COLLECTOR": "COLLECTOR", "THE_CHAMP": "CHAMP",
    "AWAKENED_ONE": "AWAKENED_ONE", "TIME_EATER": "TIME_EATER",
    "DONU": "DONU_AND_DECA", "DECA": "DONU_AND_DECA",
}
BOSS_ENCOUNTER_IDS = {int(getattr(sts.MonsterEncounter, name))
                      for name in set(BOSS_ENCOUNTERS.values())}

# CommunicationMod exposes each Java monster's local byte move id. Keep this
# fail-closed table small and add entries only after a real-state fixture proves them.
MOVE_NAMES = {
    ("JAW_WORM", 1): "JAW_WORM_CHOMP",
    ("JAW_WORM", 2): "JAW_WORM_BELLOW",
    ("JAW_WORM", 3): "JAW_WORM_THRASH",
    ("RED_LOUSE", 3): "RED_LOUSE_BITE",
    ("RED_LOUSE", 4): "RED_LOUSE_GROW",
    ("GREEN_LOUSE", 3): "GREEN_LOUSE_BITE",
    ("GREEN_LOUSE", 4): "GREEN_LOUSE_SPIT_WEB",
    ("SPIKE_SLIME_S", 1): "SPIKE_SLIME_S_TACKLE",
    ("SPIKE_SLIME_M", 1): "SPIKE_SLIME_M_FLAME_TACKLE",
    ("SPIKE_SLIME_M", 4): "SPIKE_SLIME_M_LICK",
    ("ACID_SLIME_S", 1): "ACID_SLIME_S_TACKLE",
    ("ACID_SLIME_S", 2): "ACID_SLIME_S_LICK",
    ("ACID_SLIME_M", 1): "ACID_SLIME_M_CORROSIVE_SPIT",
    ("ACID_SLIME_M", 2): "ACID_SLIME_M_TACKLE",
    ("ACID_SLIME_M", 4): "ACID_SLIME_M_LICK",
    ("ACID_SLIME_L", 1): "ACID_SLIME_L_CORROSIVE_SPIT",
    ("ACID_SLIME_L", 2): "ACID_SLIME_L_TACKLE",
    ("ACID_SLIME_L", 3): "ACID_SLIME_L_SPLIT",
    ("ACID_SLIME_L", 4): "ACID_SLIME_L_LICK",
    ("CULTIST", 1): "CULTIST_DARK_STRIKE",
    ("CULTIST", 3): "CULTIST_INCANTATION",
    ("GREMLIN_NOB", 1): "GREMLIN_NOB_RUSH",
    ("GREMLIN_NOB", 2): "GREMLIN_NOB_SKULL_BASH",
    ("GREMLIN_NOB", 3): "GREMLIN_NOB_BELLOW",
    ("HEXAGHOST", 1): "HEXAGHOST_DIVIDER",
    ("HEXAGHOST", 2): "HEXAGHOST_TACKLE",
    ("HEXAGHOST", 3): "HEXAGHOST_INFLAME",
    ("HEXAGHOST", 4): "HEXAGHOST_SEAR",
    ("HEXAGHOST", 5): "HEXAGHOST_ACTIVATE",
    ("HEXAGHOST", 6): "HEXAGHOST_INFERNO",
    ("LAGAVULIN", 1): "LAGAVULIN_SIPHON_SOUL",
    ("LAGAVULIN", 3): "LAGAVULIN_ATTACK",
    ("LAGAVULIN", 4): "LAGAVULIN_SLEEP",
    ("LAGAVULIN", 5): "LAGAVULIN_SLEEP",
    ("LAGAVULIN", 6): "LAGAVULIN_SLEEP",
    ("FUNGI_BEAST", 1): "FUNGI_BEAST_BITE",
    ("FUNGI_BEAST", 2): "FUNGI_BEAST_GROW",
    ("EXPLODER", 1): "EXPLODER_SLAM",
    ("EXPLODER", 2): "EXPLODER_EXPLODE",
    ("REPULSOR", 1): "REPULSOR_REPULSE",
    ("REPULSOR", 2): "REPULSOR_BASH",
    ("SPIKER", 1): "SPIKER_CUT",
    ("SPIKER", 2): "SPIKER_SPIKE",
    ("SENTRY", 3): "SENTRY_BOLT",
    ("SENTRY", 4): "SENTRY_BEAM",
    ("SLIME_BOSS", 1): "SLIME_BOSS_SLAM",
    ("SLIME_BOSS", 2): "SLIME_BOSS_PREPARING",
    ("SLIME_BOSS", 3): "SLIME_BOSS_SPLIT",
    ("SLIME_BOSS", 4): "SLIME_BOSS_GOOP_SPRAY",
    ("SPIKE_SLIME_L", 1): "SPIKE_SLIME_L_FLAME_TACKLE",
    ("SPIKE_SLIME_L", 3): "SPIKE_SLIME_L_SPLIT",
    ("SPIKE_SLIME_L", 4): "SPIKE_SLIME_L_LICK",
    ("THE_GUARDIAN", 1): "THE_GUARDIAN_DEFENSIVE_MODE",
    ("THE_GUARDIAN", 2): "THE_GUARDIAN_FIERCE_BASH",
    ("THE_GUARDIAN", 3): "THE_GUARDIAN_ROLL_ATTACK",
    ("THE_GUARDIAN", 4): "THE_GUARDIAN_TWIN_SLAM",
    ("THE_GUARDIAN", 5): "THE_GUARDIAN_WHIRLWIND",
    ("THE_GUARDIAN", 6): "THE_GUARDIAN_CHARGING_UP",
    ("THE_GUARDIAN", 7): "THE_GUARDIAN_VENT_STEAM",
    ("BYRD", 1): "BYRD_PECK",
    ("BYRD", 2): "BYRD_FLY",
    ("BYRD", 3): "BYRD_SWOOP",
    ("BYRD", 4): "BYRD_STUNNED",
    ("BYRD", 5): "BYRD_HEADBUTT",
    ("BYRD", 6): "BYRD_CAW",
    ("BLUE_SLAVER", 1): "BLUE_SLAVER_STAB",
    ("BLUE_SLAVER", 4): "BLUE_SLAVER_RAKE",
    ("RED_SLAVER", 1): "RED_SLAVER_STAB",
    ("RED_SLAVER", 2): "RED_SLAVER_ENTANGLE",
    ("RED_SLAVER", 3): "RED_SLAVER_SCRAPE",
    ("BOOK_OF_STABBING", 1): "BOOK_OF_STABBING_MULTI_STAB",
    ("BOOK_OF_STABBING", 2): "BOOK_OF_STABBING_SINGLE_STAB",
    ("BRONZE_AUTOMATON", 1): "BRONZE_AUTOMATON_FLAIL",
    ("BRONZE_AUTOMATON", 2): "BRONZE_AUTOMATON_HYPER_BEAM",
    ("BRONZE_AUTOMATON", 3): "BRONZE_AUTOMATON_STUNNED",
    ("BRONZE_AUTOMATON", 4): "BRONZE_AUTOMATON_SPAWN_ORBS",
    ("BRONZE_AUTOMATON", 5): "BRONZE_AUTOMATON_BOOST",
    ("BRONZE_ORB", 1): "BRONZE_ORB_BEAM",
    ("BRONZE_ORB", 2): "BRONZE_ORB_SUPPORT_BEAM",
    ("BRONZE_ORB", 3): "BRONZE_ORB_STASIS",
    ("CENTURION", 1): "CENTURION_SLASH",
    ("CENTURION", 2): "CENTURION_DEFEND",
    ("CENTURION", 3): "CENTURION_FURY",
    ("THE_CHAMP", 1): "THE_CHAMP_HEAVY_SLASH",
    ("THE_CHAMP", 2): "THE_CHAMP_DEFENSIVE_STANCE",
    ("THE_CHAMP", 3): "THE_CHAMP_EXECUTE",
    ("THE_CHAMP", 4): "THE_CHAMP_FACE_SLAP",
    ("THE_CHAMP", 5): "THE_CHAMP_GLOAT",
    ("THE_CHAMP", 6): "THE_CHAMP_TAUNT",
    ("THE_CHAMP", 7): "THE_CHAMP_ANGER",
    ("CHOSEN", 1): "CHOSEN_ZAP",
    ("CHOSEN", 2): "CHOSEN_DRAIN",
    ("CHOSEN", 3): "CHOSEN_DEBILITATE",
    ("CHOSEN", 4): "CHOSEN_HEX",
    ("CHOSEN", 5): "CHOSEN_POKE",
    ("DARKLING", 1): "DARKLING_CHOMP",
    ("DARKLING", 2): "DARKLING_HARDEN",
    ("DARKLING", 3): "DARKLING_NIP",
    ("DARKLING", 4): "DARKLING_REGROW",
    ("DARKLING", 5): "DARKLING_REINCARNATE",
    ("GREMLIN_LEADER", 2): "GREMLIN_LEADER_RALLY",
    ("GREMLIN_LEADER", 3): "GREMLIN_LEADER_ENCOURAGE",
    ("GREMLIN_LEADER", 4): "GREMLIN_LEADER_STAB",
    ("FAT_GREMLIN", 2): "FAT_GREMLIN_SMASH",
    ("GREMLIN_WIZARD", 1): "GREMLIN_WIZARD_ULTIMATE_BLAST",
    ("GREMLIN_WIZARD", 2): "GREMLIN_WIZARD_CHARGING",
    ("MAD_GREMLIN", 1): "MAD_GREMLIN_SCRATCH",
    ("SHIELD_GREMLIN", 1): "SHIELD_GREMLIN_PROTECT",
    ("SHIELD_GREMLIN", 2): "SHIELD_GREMLIN_SHIELD_BASH",
    ("SNEAKY_GREMLIN", 1): "SNEAKY_GREMLIN_PUNCTURE",
    ("MYSTIC", 1): "MYSTIC_ATTACK_DEBUFF",
    ("MYSTIC", 2): "MYSTIC_HEAL",
    ("MYSTIC", 3): "MYSTIC_BUFF",
    ("MUGGER", 1): "MUGGER_MUG",
    ("MUGGER", 2): "MUGGER_SMOKE_BOMB",
    ("MUGGER", 3): "MUGGER_ESCAPE",
    ("MUGGER", 4): "MUGGER_LUNGE",
    ("THE_MAW", 2): "THE_MAW_ROAR",
    ("THE_MAW", 3): "THE_MAW_SLAM",
    ("THE_MAW", 4): "THE_MAW_DROOL",
    ("THE_MAW", 5): "THE_MAW_NOM",
    ("LOOTER", 1): "LOOTER_MUG",
    ("LOOTER", 2): "LOOTER_SMOKE_BOMB",
    ("LOOTER", 3): "LOOTER_ESCAPE",
    ("LOOTER", 4): "LOOTER_LUNGE",
    ("ORB_WALKER", 1): "ORB_WALKER_LASER",
    ("ORB_WALKER", 2): "ORB_WALKER_CLAW",
    ("SHELLED_PARASITE", 1): "SHELLED_PARASITE_FELL",
    ("SHELLED_PARASITE", 2): "SHELLED_PARASITE_DOUBLE_STRIKE",
    ("SHELLED_PARASITE", 3): "SHELLED_PARASITE_SUCK",
    ("SHELLED_PARASITE", 4): "SHELLED_PARASITE_STUNNED",
    ("SNAKE_PLANT", 1): "SNAKE_PLANT_CHOMP",
    ("SNAKE_PLANT", 2): "SNAKE_PLANT_ENFEEBLING_SPORES",
    ("SNECKO", 1): "SNECKO_PERPLEXING_GLARE",
    ("SNECKO", 2): "SNECKO_BITE",
    ("SNECKO", 3): "SNECKO_TAIL_WHIP",
    ("SPHERIC_GUARDIAN", 1): "SPHERIC_GUARDIAN_SLAM",
    ("SPHERIC_GUARDIAN", 2): "SPHERIC_GUARDIAN_ACTIVATE",
    ("SPHERIC_GUARDIAN", 3): "SPHERIC_GUARDIAN_HARDEN",
    ("SPHERIC_GUARDIAN", 4): "SPHERIC_GUARDIAN_ATTACK_DEBUFF",
    ("TASKMASTER", 2): "TASKMASTER_SCOURING_WHIP",
    ("THE_COLLECTOR", 1): "THE_COLLECTOR_SPAWN",
    ("THE_COLLECTOR", 2): "THE_COLLECTOR_FIREBALL",
    ("THE_COLLECTOR", 3): "THE_COLLECTOR_BUFF",
    ("THE_COLLECTOR", 4): "THE_COLLECTOR_MEGA_DEBUFF",
    ("THE_COLLECTOR", 5): "THE_COLLECTOR_SPAWN",
    ("TORCH_HEAD", 1): "TORCH_HEAD_TACKLE",
    ("POINTY", 1): "POINTY_ATTACK",
    ("ROMEO", 1): "ROMEO_CROSS_SLASH",
    ("ROMEO", 2): "ROMEO_MOCK",
    ("ROMEO", 3): "ROMEO_AGONIZING_SLASH",
    ("BEAR", 1): "BEAR_MAUL",
    ("BEAR", 2): "BEAR_BEAR_HUG",
    ("BEAR", 3): "BEAR_LUNGE",
    ("AWAKENED_ONE", 1): "AWAKENED_ONE_SLASH",
    ("AWAKENED_ONE", 2): "AWAKENED_ONE_SOUL_STRIKE",
    ("AWAKENED_ONE", 3): "AWAKENED_ONE_REBIRTH",
    ("AWAKENED_ONE", 5): "AWAKENED_ONE_DARK_ECHO",
    ("AWAKENED_ONE", 6): "AWAKENED_ONE_SLUDGE",
    ("AWAKENED_ONE", 8): "AWAKENED_ONE_TACKLE",
    ("DAGGER", 1): "DAGGER_STAB",
    ("DAGGER", 2): "DAGGER_EXPLODE",
    ("DECA", 0): "DECA_BEAM",
    ("DECA", 2): "DECA_SQUARE_OF_PROTECTION",
    ("DONU", 0): "DONU_BEAM",
    ("DONU", 2): "DONU_CIRCLE_OF_POWER",
    ("GIANT_HEAD", 1): "GIANT_HEAD_GLARE",
    ("GIANT_HEAD", 2): "GIANT_HEAD_IT_IS_TIME",
    ("GIANT_HEAD", 3): "GIANT_HEAD_COUNT",
    ("NEMESIS", 2): "NEMESIS_ATTACK",
    ("NEMESIS", 3): "NEMESIS_SCYTHE",
    ("NEMESIS", 4): "NEMESIS_DEBUFF",
    ("REPTOMANCER", 1): "REPTOMANCER_SNAKE_STRIKE",
    ("REPTOMANCER", 2): "REPTOMANCER_SUMMON",
    ("REPTOMANCER", 3): "REPTOMANCER_BIG_BITE",
    ("SPIRE_GROWTH", 1): "SPIRE_GROWTH_QUICK_TACKLE",
    ("SPIRE_GROWTH", 2): "SPIRE_GROWTH_CONSTRICT",
    ("SPIRE_GROWTH", 3): "SPIRE_GROWTH_SMASH",
    ("TRANSIENT", 1): "TRANSIENT_ATTACK",
    ("WRITHING_MASS", 0): "WRITHING_MASS_STRONG_STRIKE",
    ("WRITHING_MASS", 1): "WRITHING_MASS_MULTI_STRIKE",
    ("WRITHING_MASS", 2): "WRITHING_MASS_FLAIL",
    ("WRITHING_MASS", 3): "WRITHING_MASS_WITHER",
    ("WRITHING_MASS", 4): "WRITHING_MASS_IMPLANT",
    ("CORRUPT_HEART", 1): "CORRUPT_HEART_BLOOD_SHOTS",
    ("CORRUPT_HEART", 2): "CORRUPT_HEART_ECHO",
    ("CORRUPT_HEART", 3): "CORRUPT_HEART_DEBILITATE",
    ("CORRUPT_HEART", 4): "CORRUPT_HEART_BUFF",
    ("SPIRE_SHIELD", 1): "SPIRE_SHIELD_BASH",
    ("SPIRE_SHIELD", 2): "SPIRE_SHIELD_FORTIFY",
    ("SPIRE_SHIELD", 3): "SPIRE_SHIELD_SMASH",
    ("SPIRE_SPEAR", 1): "SPIRE_SPEAR_BURN_STRIKE",
    ("SPIRE_SPEAR", 2): "SPIRE_SPEAR_PIERCER",
    ("SPIRE_SPEAR", 3): "SPIRE_SPEAR_SKEWER",
    ("TIME_EATER", 2): "TIME_EATER_REVERBERATE",
    ("TIME_EATER", 3): "TIME_EATER_RIPPLE",
    ("TIME_EATER", 4): "TIME_EATER_HEAD_SLAM",
    ("TIME_EATER", 5): "TIME_EATER_HASTE",
}


def enum_key(value):
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value).replace("-", " ").replace("'", ""))
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()


def card_snapshot(card):
    identifier = card.get("id") or card.get("name") or ""
    key = CARD_ALIASES.get(identifier, enum_key(identifier))
    return {"id": sts.card_id_from_name(key),
            "upgrades": int(card.get("upgrades") or 0),
            "cost": int(card.get("cost") if card.get("cost") is not None else 0),
            "misc": int(card.get("misc") or 0)}


def power_snapshot(power, owner):
    helper = sts.player_status_id_from_name if owner == "player" else sts.monster_status_id_from_name
    identifier = power.get("id") or power.get("name")
    if owner == "player" and str(identifier).startswith("TheBomb"):
        description = str(power.get("description") or "")
        return {"id": helper("THE_BOMB"), "amount": 50 if re.search(r"\b50\b", description) else 40,
                "bomb_turns": max(1, min(3, int(power.get("amount") or 1))), "just_applied": False}
    if owner == "monster" and identifier == "Stasis":
        raise ValueError("unsupported stateful monster power: Stasis card identity unavailable")
    if owner == "player":
        identifier = PLAYER_POWER_ALIASES.get(identifier, identifier)
        power_id = helper(identifier)
    else:
        identifier = MONSTER_POWER_ALIASES.get(identifier, identifier)
        # LOCAL: match case-insensitively; "Barricade" used to miss this table and fall through
        # to the stale name array, which returned the id of ASLEEP.
        power_id = MONSTER_POWER_IDS.get(enum_key(identifier))
        if power_id is None:
            power_id = helper(identifier)
    amount = power.get("amount")
    # LOCAL: Strength/Dexterity/Focus are legitimately negative (Siphon Soul,
    # Disarm, Shackled); upstream coerced every negative amount to 1.
    signed = str(identifier).upper() in {"STRENGTH", "DEXTERITY", "FOCUS"}
    return {"id": power_id,
            "amount": int(amount if amount is not None and (amount >= 0 or signed) else 1),
            "just_applied": bool(power.get("just_applied", False))}


def monster_key(monster):
    identifier = monster.get("id") or monster.get("name") or ""
    return MONSTER_ALIASES.get(identifier, enum_key(identifier))


def move_id(monster, raw_key="move_id"):
    raw = monster.get(raw_key)
    if raw is None or int(raw) < 0:
        return sts.monster_move_id_from_name("INVALID")
    key = monster_key(monster)
    name = MOVE_NAMES.get((key, int(raw)))
    if not name:
        raise ValueError(f"unsupported monster move: {key} raw={raw} intent={monster.get('intent')}")
    return sts.monster_move_id_from_name(name)


def rng_snapshot(rng):
    return {"seed0": int(rng["seed0"]), "seed1": int(rng["seed1"]),
            "counter": int(rng.get("counter") or 0)}


# LOCAL: monsters whose simulator-internal `miscInfo` can be read off the intent
# the real game shows. Value is the JSON field that carries it.
OBSERVABLE_MISC = {
    "RED_LOUSE_BITE": "move_base_damage",
    "GREEN_LOUSE_BITE": "move_base_damage",
    "HEXAGHOST_DIVIDER": "move_base_damage",
    "BOOK_OF_STABBING_MULTI_STAB": "move_hits",
}


def observable_misc(monster, key):
    """(known, value) for the simulator's hidden per-monster state."""
    if key == "AWAKENED_ONE":
        powers = monster.get("powers") or []
        return True, 0 if any((p.get("id") or p.get("name")) == "Unawakened" for p in powers) else 1
    raw = monster.get("move_id")
    name = MOVE_NAMES.get((key, int(raw))) if raw is not None and int(raw) >= 0 else None
    field = OBSERVABLE_MISC.get(name)
    value = monster.get(field) if field else None
    if value is not None and int(value) > 0:
        return True, int(value)
    return False, 0


def monster_snapshot(monster):
    powers = monster.get("powers") or []
    key = monster_key(monster)
    misc_known, misc_info = observable_misc(monster, key)
    return {
        "misc_known": misc_known,
        "id": sts.monster_id_from_name(key),
        "current_hp": int(monster.get("current_hp") or 0),
        "max_hp": int(monster.get("max_hp") or 0),
        "block": int(monster.get("block") or 0),
        "half_dead": bool(monster.get("half_dead", False)),
        "is_gone": bool(monster.get("is_gone", False)),
        "move": move_id(monster),
        "last_move": move_id(monster, "last_move_id"),
        "misc_info": misc_info,
        "powers": _monster_powers(key, powers),
    }


def _monster_powers(key, powers):
    names = [(power.get("id") or power.get("name")) for power in powers]
    out = [power_snapshot(power, "monster") for power, name in zip(powers, names)
           if name not in IGNORED_MONSTER_POWERS]
    # LOCAL: the real game keeps Lagavulin's sleep as internal state, not a power; the simulator
    # models it as ASLEEP. A Lagavulin still holding its Metallicize has not woken yet.
    if key == "LAGAVULIN" and "Metallicize" in names and MONSTER_POWER_IDS["ASLEEP"] not in [p["id"] for p in out]:
        out.append({"id": MONSTER_POWER_IDS["ASLEEP"], "amount": 1, "just_applied": False})
    return out


def dead_monster(name, move):
    return {"id": sts.monster_id_from_name(name), "current_hp": 0, "max_hp": 1,
            "block": 0, "half_dead": False, "is_gone": True,
            "move": sts.monster_move_id_from_name(move),
            "last_move": sts.monster_move_id_from_name("INVALID"), "powers": []}


def canonical_monsters(monsters):
    indexed = [(index, monster) for index, monster in enumerate(monsters)
               if not monster.get("is_gone")]
    collector = next(((index, monster) for index, monster in indexed
                      if monster_key(monster) == "THE_COLLECTOR"), None)
    if collector:
        torches = [(index, monster) for index, monster in indexed
                   if monster_key(monster) == "TORCH_HEAD"][:2]
        snapshots = [monster_snapshot(monster) for _, monster in torches]
        target_map = [index for index, _ in torches]
        while len(snapshots) < 2:
            snapshots.append(dead_monster("TORCH_HEAD", "TORCH_HEAD_TACKLE"))
            target_map.append(-1)
        snapshots.append(monster_snapshot(collector[1])); target_map.append(collector[0])
        return snapshots, target_map

    leader = next(((index, monster) for index, monster in indexed
                   if monster_key(monster) == "GREMLIN_LEADER"), None)
    if leader:
        minions = [(index, monster) for index, monster in indexed
                   if monster_key(monster) != "GREMLIN_LEADER"][:3]
        snapshots = [monster_snapshot(monster) for _, monster in minions]
        target_map = [index for index, _ in minions]
        while len(snapshots) < 3:
            snapshots.append(dead_monster("MAD_GREMLIN", "MAD_GREMLIN_SCRATCH"))
            target_map.append(-1)
        snapshots.append(monster_snapshot(leader[1])); target_map.append(leader[0])
        return snapshots, target_map

    return ([monster_snapshot(monster) for _, monster in indexed],
            [index for index, _ in indexed])


def encounter_id(monsters):
    for monster in monsters:
        encounter = BOSS_ENCOUNTERS.get(monster_key(monster))
        if encounter:
            return int(getattr(sts.MonsterEncounter, encounter))
    return int(sts.MonsterEncounter.INVALID)


def build_snapshot(game_state, counters=None):
    combat = game_state.get("combat_state") or {}
    player = combat.get("player") or {}
    player_powers = player.get("powers") or []
    monsters, target_map = canonical_monsters(combat.get("monsters") or [])
    berserk_energy = sum(int(power.get("amount") or 0) for power in player_powers
                         if (power.get("id") or power.get("name")) == "Berserk")
    counters = counters or {}
    snapshot = {
        # LOCAL: the game reports the seed as a signed Java long; the simulator wants it unsigned.
        "seed": int(game_state.get("seed") or 0) & 0xFFFFFFFFFFFFFFFF,
        "floor": int(game_state.get("floor") or 0),
        "ascension": int(game_state.get("ascension_level") or 0),
        "encounter": encounter_id(combat.get("monsters") or []),
        "turn": int(combat.get("turn") or 1),
        "cards_played_this_turn": int(counters.get("cards", 0)),
        "attacks_played_this_turn": int(counters.get("attacks", 0)),
        "skills_played_this_turn": int(counters.get("skills", 0)),
        "cards_discarded_this_turn": int(combat.get("cards_discarded_this_turn") or 0),
        "times_damaged": int(combat.get("times_damaged") or 0),
        "player": {
            "current_hp": int(player.get("current_hp") or 0),
            "max_hp": int(player.get("max_hp") or game_state.get("max_hp") or 0),
            "block": int(player.get("block") or 0),
            "energy": int(player.get("energy") or 0),
            "energy_per_turn": int(combat.get("energy_per_turn") or 3) + berserk_energy,
            "powers": [power_snapshot(power, "player") for power in player_powers
                       if (power.get("id") or power.get("name")) != "Berserk"],
        },
        "hand": [card_snapshot(card) for card in combat.get("hand") or []],
        "draw_pile": [card_snapshot(card) for card in combat.get("draw_pile") or []],
        "discard_pile": [card_snapshot(card) for card in combat.get("discard_pile") or []],
        "exhaust_pile": [card_snapshot(card) for card in combat.get("exhaust_pile") or []],
        "monsters": monsters,
        "target_map": target_map,
        "relics": [{"id": sts.relic_id_from_name(relic.get("id") or relic.get("name")),
                    "counter": int(relic.get("counter") if relic.get("counter") is not None else -1)}
                   for relic in game_state.get("relics") or []],
        "potions": [sts.potion_id_from_name(POTION_ALIASES.get(
            potion.get("id") or potion.get("name"), potion.get("id") or potion.get("name")))
            for potion in game_state.get("potions") or []],
    }
    if combat.get("rngs"):
        snapshot["rngs"] = {name: rng_snapshot(rng) for name, rng in combat["rngs"].items()}
    return snapshot

