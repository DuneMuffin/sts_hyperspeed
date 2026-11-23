//
// Zero-leakage run-level determinization and CRN counterfactual rollout evaluation.
//

#include "sim/search/CounterfactualRollout.h"

#include "combat/BattleContext.h"
#include "constants/MonsterEncounters.h"
#include "constants/Relics.h"
#include "game/Map.h"
#include "game/Random.h"
#include "sim/search/ScumSearchAgent2.h"

#include <algorithm>
#include <array>
#include <memory>
#include <random>

namespace sts::search {

    namespace {

        std::uint64_t splitmix64(std::uint64_t x) {
            x += 0x9E3779B97F4A7C15ULL;
            x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ULL;
            x = (x ^ (x >> 27)) * 0x94D049BB133111EBULL;
            return x ^ (x >> 31);
        }

        template <typename T>
        void shuffleCanonicalVector(std::vector<T> &vec, std::uint64_t rngSeed) {
            std::sort(vec.begin(), vec.end(), [](const T &a, const T &b) {
                return static_cast<int>(a) < static_cast<int>(b);
            });
            java::Collections::shuffle(vec.begin(), vec.end(), java::Random(rngSeed));
        }

        struct RolloutOutcome {
            bool won = false;
            int floor = 0;
            int hp = 0;
            double score = 0.0;
        };

        bool reachedGoalAct(const GameContext &gc, Outcome bcOutcome, int maxAct) {
            if (gc.outcome == GameOutcome::PLAYER_VICTORY || gc.act > maxAct) {
                return true;
            }
            if (bcOutcome != Outcome::PLAYER_VICTORY) {
                return false;
            }
            if (gc.act != maxAct || gc.curRoom != Room::BOSS) {
                return false;
            }
            return maxAct < 3 || gc.screenState != ScreenState::BATTLE;
        }

        RolloutOutcome runActRollout(
            GameContext &gc,
            int rolloutSims,
            double bossMult,
            int maxAct,
            std::uint64_t agentSeed) {
            ScumSearchAgent2 agent;
            agent.simulationCountBase = rolloutSims;
            agent.bossSimulationMultiplier = bossMult;
            agent.pauseOnBattle = true;
            agent.rng.seed(static_cast<std::default_random_engine::result_type>(agentSeed));

            bool won = false;
            int stepGuard = 0;
            while (gc.outcome == GameOutcome::UNDECIDED && gc.act <= maxAct && stepGuard < 5000) {
                ++stepGuard;
                if (gc.screenState == ScreenState::BATTLE) {
                    BattleContext bc;
                    bc.init(gc);
                    agent.playoutBattle(bc);
                    const auto bcOut = bc.outcome;
                    bc.exitBattle(gc);
                    if (reachedGoalAct(gc, bcOut, maxAct)) {
                        won = true;
                        break;
                    }
                    if (bcOut != Outcome::PLAYER_VICTORY) {
                        break;
                    }
                } else {
                    agent.playout(gc);
                    if (gc.outcome == GameOutcome::PLAYER_VICTORY || gc.act > maxAct) {
                        won = true;
                        break;
                    }
                }
            }
            if (!won && (gc.outcome == GameOutcome::PLAYER_VICTORY || gc.act > maxAct)) {
                won = true;
            }

            RolloutOutcome out;
            out.won = won;
            out.floor = gc.floorNum;
            out.hp = gc.curHp;
            out.score = won
                ? (1000.0 + static_cast<double>(gc.curHp))
                : (static_cast<double>(gc.floorNum) * 10.0);
            return out;
        }

    }  // namespace

    GameContext determinizeGameContext(const GameContext &src, std::uint64_t detSeed) {
        GameContext gc(src);
        if (gc.map) {
            gc.map = std::make_shared<Map>(*gc.map);
        }

        // Strip seed and all 14 hidden Random streams.
        gc.seed = splitmix64(detSeed ^ 0x123456789ABCDEF0ULL);
        gc.aiRng = Random(splitmix64(detSeed ^ 0x9E3779B97F4A7C15ULL));
        gc.cardRandomRng = Random(splitmix64(detSeed ^ 0xBF58476D1CE4E5B9ULL));
        gc.cardRng = Random(splitmix64(detSeed ^ 0x94D049BB133111EBULL));
        gc.eventRng = Random(splitmix64(detSeed ^ 0x2545F4914F6CDD1DULL));
        gc.mathUtilRng = Random(splitmix64(detSeed ^ 0xD1B54A32D192ED03ULL));
        gc.merchantRng = Random(splitmix64(detSeed ^ 0xA24BAED4963EE407ULL));
        gc.miscRng = Random(splitmix64(detSeed ^ 0x517CC1B727220A95ULL));
        gc.monsterHpRng = Random(splitmix64(detSeed ^ 0x6A09E667F3BCC908ULL));
        gc.monsterRng = Random(splitmix64(detSeed ^ 0xBB67AE8584CAA73BULL));
        gc.neowRng = Random(splitmix64(detSeed ^ 0x3C6EF372FE94F82BULL));
        gc.potionRng = Random(splitmix64(detSeed ^ 0xA54FF53A5F1D36F1ULL));
        gc.relicRng = Random(splitmix64(detSeed ^ 0x510E527FADE682D1ULL));
        gc.shuffleRng = Random(splitmix64(detSeed ^ 0x9B05688C2B3E6C1FULL));
        gc.treasureRng = Random(splitmix64(detSeed ^ 0x1F83D9ABFB41BD6BULL));

        // Canonically sort and re-shuffle all hidden event/relic/card pools.
        shuffleCanonicalVector(gc.eventList, splitmix64(detSeed ^ 0x0101010101010101ULL));
        shuffleCanonicalVector(gc.shrineList, splitmix64(detSeed ^ 0x0202020202020202ULL));
        shuffleCanonicalVector(gc.specialOneTimeEventList, splitmix64(detSeed ^ 0x0303030303030303ULL));
        shuffleCanonicalVector(gc.commonRelicPool, splitmix64(detSeed ^ 0x0404040404040404ULL));
        shuffleCanonicalVector(gc.uncommonRelicPool, splitmix64(detSeed ^ 0x0505050505050505ULL));
        shuffleCanonicalVector(gc.rareRelicPool, splitmix64(detSeed ^ 0x0606060606060606ULL));
        shuffleCanonicalVector(gc.shopRelicPool, splitmix64(detSeed ^ 0x0707070707070707ULL));
        shuffleCanonicalVector(gc.bossRelicPool, splitmix64(detSeed ^ 0x0808080808080808ULL));

        gc.colorlessCardPool = baseColorlessPool;
        java::Collections::shuffle(
            gc.colorlessCardPool.begin(),
            gc.colorlessCardPool.end(),
            java::Random(splitmix64(detSeed ^ 0x0909090909090909ULL)));

        // Re-roll unseen future monster and elite encounter tails while preserving seen prefixes.
        if (gc.act >= 1 && gc.act <= 3) {
            const int oldMonOffset = std::max(0, gc.monsterListOffset);
            const int savedMonCount = std::min(oldMonOffset, static_cast<int>(gc.monsterList.size()));
            std::array<MonsterEncounter, 16> savedMonsters{};
            for (int i = 0; i < savedMonCount; ++i) {
                savedMonsters[i] = gc.monsterList[i];
            }
            gc.monsterList.clear();
            gc.generateWeakMonsters();
            const int weakPrefix = std::min(savedMonCount, static_cast<int>(gc.monsterList.size()));
            for (int i = 0; i < weakPrefix; ++i) {
                gc.monsterList[i] = savedMonsters[i];
            }
            gc.generateStrongMonsters();
            const int totalPrefix = std::min(savedMonCount, static_cast<int>(gc.monsterList.size()));
            for (int i = weakPrefix; i < totalPrefix; ++i) {
                gc.monsterList[i] = savedMonsters[i];
            }
            gc.monsterListOffset = oldMonOffset;

            const int oldEliteOffset = std::max(0, gc.eliteMonsterListOffset);
            const int savedEliteCount = std::min(oldEliteOffset, static_cast<int>(gc.eliteMonsterList.size()));
            std::array<MonsterEncounter, 10> savedElites{};
            for (int i = 0; i < savedEliteCount; ++i) {
                savedElites[i] = gc.eliteMonsterList[i];
            }
            gc.eliteMonsterList.clear();
            gc.generateElites();
            const int restoreElites = std::min(savedEliteCount, static_cast<int>(gc.eliteMonsterList.size()));
            for (int i = 0; i < restoreElites; ++i) {
                gc.eliteMonsterList[i] = savedElites[i];
            }
            gc.eliteMonsterListOffset = oldEliteOffset;

            if (gc.act == 3 && gc.ascension >= 20) {
                static constexpr std::array<MonsterEncounter, 3> act3Bosses {
                    MonsterEncounter::AWAKENED_ONE,
                    MonsterEncounter::TIME_EATER,
                    MonsterEncounter::DONU_AND_DECA,
                };
                std::array<MonsterEncounter, 2> candidates{};
                int cCount = 0;
                for (const auto b : act3Bosses) {
                    if (b != gc.boss && cCount < 2) {
                        candidates[cCount++] = b;
                    }
                }
                if (cCount > 0) {
                    const int pick = gc.monsterRng.random(0, cCount - 1);
                    gc.secondBoss = candidates[pick];
                }
            }
        }

        return gc;
    }

    std::vector<GameAction> getMacroDecisionActions(const GameContext &gc) {
        if (gc.outcome != GameOutcome::UNDECIDED) {
            return {};
        }

        if (gc.screenState == ScreenState::REWARDS && gc.info.rewardsContainer.cardRewardCount > 0) {
            std::vector<GameAction> actions;
            const auto &cards = gc.info.rewardsContainer.cardRewards[0];
            actions.reserve(static_cast<std::size_t>(cards.size()) + 1);
            for (int cIdx = 0; cIdx < cards.size(); ++cIdx) {
                actions.emplace_back(GameAction::RewardsActionType::CARD, 0, cIdx);
            }
            // Skip card reward (or trigger Singing Bowl if owned), leaving other rewards untouched.
            actions.emplace_back(GameAction::RewardsActionType::CARD, 0, 5);
            return actions;
        }

        auto actions = GameAction::getAllActionsInState(gc);
        if (gc.screenState == ScreenState::SHOP_ROOM) {
            const bool canHoldPotion = gc.potionCount < gc.potionCapacity && !gc.hasRelic(RelicId::SOZU);
            if (!canHoldPotion) {
                actions.erase(
                    std::remove_if(actions.begin(), actions.end(), [](const GameAction &a) {
                        return a.getRewardsActionType() == GameAction::RewardsActionType::POTION;
                    }),
                    actions.end());
            }
        }
        return actions;
    }

    std::vector<RolloutActionStat> evaluateGameActionsByRollout(
        const GameContext &gc,
        const std::vector<GameAction> &actions,
        const RolloutConfig &cfg) {
        std::vector<RolloutActionStat> stats;
        stats.reserve(actions.size());
        for (const auto &act : actions) {
            stats.push_back({act, 0, 0, 0.0, 0.0, 0.0});
        }
        if (actions.size() <= 1 || cfg.numRollouts <= 0) {
            return stats;
        }

        for (int m = 0; m < cfg.numRollouts; ++m) {
            const std::uint64_t detSeed =
                splitmix64(cfg.searchSeed + static_cast<std::uint64_t>(m) * 0x9E3779B97F4A7C15ULL);
            const std::uint64_t agentSeed = splitmix64(detSeed ^ 0xCAFEBABE12345678ULL);
            const GameContext baseDet = determinizeGameContext(gc, detSeed);

            for (std::size_t i = 0; i < actions.size(); ++i) {
                GameContext branch(baseDet);
                if (branch.map) {
                    branch.map = std::make_shared<Map>(*branch.map);
                }
                actions[i].execute(branch);
                const auto res = runActRollout(
                    branch, cfg.rolloutSims, cfg.bossSimMultiplier, cfg.maxAct, agentSeed);

                auto &st = stats[i];
                ++st.rollouts;
                if (res.won) {
                    ++st.wins;
                    st.winHpSum += static_cast<double>(res.hp);
                }
                st.scoreSum += res.score;
                st.floorSum += static_cast<double>(res.floor);
            }
        }

        std::stable_sort(
            stats.begin(),
            stats.end(),
            [](const RolloutActionStat &a, const RolloutActionStat &b) {
                if (a.meanScore() != b.meanScore()) {
                    return a.meanScore() > b.meanScore();
                }
                return a.winRate() > b.winRate();
            });

        return stats;
    }

}  // namespace sts::search
