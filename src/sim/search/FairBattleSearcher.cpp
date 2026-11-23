//
// Fair-information (determinized) combat search built over BattleScumSearcher2.
//

#include "sim/search/FairBattleSearcher.h"

#include "constants/Relics.h"
#include "game/Random.h"
#include "sim/search/BattleScumSearcher2.h"

#include <algorithm>
#include <tuple>
#include <unordered_map>

namespace sts::search {

    namespace {

        std::uint64_t splitmix64(std::uint64_t x) {
            x += 0x9E3779B97F4A7C15ULL;
            x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ULL;
            x = (x ^ (x >> 27)) * 0x94D049BB133111EBULL;
            return x ^ (x >> 31);
        }

        bool isDrawPileSelectState(const BattleContext &bc) {
            if (bc.inputState != InputState::CARD_SELECT) {
                return false;
            }
            const auto task = bc.cardSelectInfo.cardSelectTask;
            return task == CardSelectTask::SECRET_TECHNIQUE
                || task == CardSelectTask::SECRET_WEAPON
                || task == CardSelectTask::SEEK;
        }

    }  // namespace

    BattleContext determinizeBattleContext(const BattleContext &src, std::uint64_t detSeed) {
        BattleContext bc(src);

        // Strip and re-seed combat seed and every RNG stream so hidden future outcomes
        // (monster AI rolls, random card/potion generation, future shuffles) are hidden.
        // Note: enemy intents for the current turn live on Monster::moveHistory[0] and stay
        // intact; future Runic Dome support (Act 2+ boss relic) would hide intents too.
        bc.seed = splitmix64(detSeed ^ 0x123456789ABCDEF0ULL);
        bc.aiRng = Random(splitmix64(detSeed ^ 0x9E3779B97F4A7C15ULL));
        bc.cardRandomRng = Random(splitmix64(detSeed ^ 0xBF58476D1CE4E5B9ULL));
        bc.miscRng = Random(splitmix64(detSeed ^ 0x94D049BB133111EBULL));
        bc.monsterHpRng = Random(splitmix64(detSeed ^ 0x2545F4914F6CDD1DULL));
        bc.potionRng = Random(splitmix64(detSeed ^ 0xD1B54A32D192ED03ULL));
        bc.shuffleRng = Random(splitmix64(detSeed ^ 0xA24BAED4963EE407ULL));

        if (!bc.player.hasRelic<RelicId::FROZEN_EYE>()) {
            // Canonicalize drawPile order before shuffling so the original secret draw order
            // cannot influence the determinized permutation.
            std::sort(
                bc.cards.drawPile.begin(),
                bc.cards.drawPile.end(),
                [](const CardInstance &a, const CardInstance &b) {
                    return std::make_tuple(
                               static_cast<int>(a.id),
                               a.upgraded,
                               a.cost,
                               a.costForTurn,
                               a.specialData,
                               a.freeToPlayOnce,
                               a.retain,
                               a.uniqueId)
                        < std::make_tuple(
                              static_cast<int>(b.id),
                              b.upgraded,
                              b.cost,
                              b.costForTurn,
                              b.specialData,
                              b.freeToPlayOnce,
                              b.retain,
                              b.uniqueId);
                });
            java::Collections::shuffle(
                bc.cards.drawPile.begin(),
                bc.cards.drawPile.end(),
                java::Random(splitmix64(detSeed ^ 0x517CC1B727220A95ULL)));
        }

        return bc;
    }

    FairSearchResult fairSearchDecision(
        const BattleContext &bc,
        const FairSearchConfig &cfg,
        std::uint64_t decisionSeed) {
        FairSearchResult result;
        if (bc.outcome != Outcome::UNDECIDED) {
            return result;
        }

        BattleScumSearcher2 proto(bc);
        BattleScumSearcher2::Node rootProto;
        proto.enumerateActionsForNode(rootProto, bc);
        if (rootProto.edges.empty()) {
            return result;
        }

        result.actionStats.reserve(rootProto.edges.size());
        for (const auto &edge : rootProto.edges) {
            result.actionStats.push_back({edge.action, 0, 0.0});
        }
        if (rootProto.edges.size() == 1) {
            return result;
        }

        const bool drawSelect = isDrawPileSelectState(bc);
        std::unordered_map<std::int16_t, std::size_t> uidToOrigIdx;
        std::unordered_map<std::uint32_t, std::size_t> bitsToOrigIdx;
        if (drawSelect) {
            uidToOrigIdx.reserve(rootProto.edges.size());
            for (std::size_t i = 0; i < rootProto.edges.size(); ++i) {
                const int selIdx = rootProto.edges[i].action.getSelectIdx();
                uidToOrigIdx.emplace(bc.cards.drawPile[selIdx].uniqueId, i);
            }
        } else {
            bitsToOrigIdx.reserve(rootProto.edges.size());
            for (std::size_t i = 0; i < rootProto.edges.size(); ++i) {
                bitsToOrigIdx.emplace(rootProto.edges[i].action.bits, i);
            }
        }

        const int simBudget = std::max(
            1,
            isBossEncounter(bc.encounter)
                ? static_cast<int>(cfg.totalSims * cfg.bossSimMultiplier)
                : cfg.totalSims);
        const int numDets = cfg.fair
            ? std::max(1, std::min(cfg.numDeterminizations, simBudget))
            : 1;

        for (int d = 0; d < numDets; ++d) {
            const int simsD = simBudget / numDets + (d < (simBudget % numDets) ? 1 : 0);
            const std::uint64_t detSeed =
                splitmix64(decisionSeed + static_cast<std::uint64_t>(d) * 0x9E3779B97F4A7C15ULL);
            const BattleContext detBc = cfg.fair ? determinizeBattleContext(bc, detSeed) : bc;

            BattleScumSearcher2 searcher(detBc);
            searcher.search(simsD);
            result.simsUsed += searcher.root.simulationCount;

            for (const auto &edge : searcher.root.edges) {
                std::size_t origIdx = 0;
                bool found = false;
                if (drawSelect) {
                    const int selIdx = edge.action.getSelectIdx();
                    if (selIdx >= 0 && selIdx < static_cast<int>(detBc.cards.drawPile.size())) {
                        const auto it = uidToOrigIdx.find(detBc.cards.drawPile[selIdx].uniqueId);
                        if (it != uidToOrigIdx.end()) {
                            origIdx = it->second;
                            found = true;
                        }
                    }
                } else {
                    const auto it = bitsToOrigIdx.find(edge.action.bits);
                    if (it != bitsToOrigIdx.end()) {
                        origIdx = it->second;
                        found = true;
                    }
                }
                if (found) {
                    result.actionStats[origIdx].totalVisits += edge.node.simulationCount;
                    result.actionStats[origIdx].evalSum += edge.node.evaluationSum;
                }
            }
        }

        std::stable_sort(
            result.actionStats.begin(),
            result.actionStats.end(),
            [&](const FairActionStat &a, const FairActionStat &b) {
                if (cfg.aggregation == FairAggregation::POOLED_MEAN) {
                    const bool aVisited = a.totalVisits > 0;
                    const bool bVisited = b.totalVisits > 0;
                    if (aVisited != bVisited) {
                        return aVisited;
                    }
                    if (a.meanEval() != b.meanEval()) {
                        return a.meanEval() > b.meanEval();
                    }
                    return a.totalVisits > b.totalVisits;
                }
                if (a.totalVisits != b.totalVisits) {
                    return a.totalVisits > b.totalVisits;
                }
                return a.meanEval() > b.meanEval();
            });

        return result;
    }

    Action fairSearchRecommend(const BattleContext &bc, const FairSearchConfig &cfg) {
        const auto res = fairSearchDecision(bc, cfg, cfg.searchSeed);
        if (res.actionStats.empty()) {
            return Action(ActionType::END_TURN);
        }
        return res.actionStats.front().action;
    }

    FairPlayoutResult playoutBattleFair(
        BattleContext &bc,
        const FairSearchConfig &cfg,
        int maxDecisions) {
        FairPlayoutResult out;
        while (bc.outcome == Outcome::UNDECIDED && out.decisions < maxDecisions) {
            const std::uint64_t stepSeed =
                splitmix64(cfg.searchSeed + static_cast<std::uint64_t>(out.decisions) * 0xBF58476D1CE4E5B9ULL);
            const auto decision = fairSearchDecision(bc, cfg, stepSeed);
            if (decision.actionStats.empty()) {
                out.timedOut = true;
                return out;
            }
            ++out.decisions;
            if (decision.actionStats.size() > 1) {
                ++out.nontrivialDecisions;
            }
            out.simsTotal += decision.simsUsed;
            decision.actionStats.front().action.execute(bc);
        }
        if (bc.outcome == Outcome::UNDECIDED) {
            out.timedOut = true;
        }
        return out;
    }

}  // namespace sts::search
