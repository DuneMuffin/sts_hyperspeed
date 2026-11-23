//
// Fair-information (determinized) combat search built over BattleScumSearcher2.
//

#ifndef STS_LIGHTSPEED_FAIRBATTLESEARCHER_H
#define STS_LIGHTSPEED_FAIRBATTLESEARCHER_H

#include "combat/BattleContext.h"
#include "sim/search/Action.h"

#include <cstdint>
#include <vector>

namespace sts::search {

    enum class FairAggregation {
        VISITS = 0,
        POOLED_MEAN = 1,
    };

    struct FairSearchConfig {
        int totalSims = 1000;
        int numDeterminizations = 8;
        double bossSimMultiplier = 3.0;
        bool fair = true;
        FairAggregation aggregation = FairAggregation::POOLED_MEAN;
        std::uint64_t searchSeed = 1;
    };

    struct FairActionStat {
        Action action;
        std::int64_t totalVisits = 0;
        double evalSum = 0.0;

        [[nodiscard]] double meanEval() const {
            return totalVisits > 0 ? evalSum / static_cast<double>(totalVisits) : 0.0;
        }
    };

    struct FairSearchResult {
        std::vector<FairActionStat> actionStats;
        std::int64_t simsUsed = 0;
    };

    struct FairPlayoutResult {
        std::int64_t simsTotal = 0;
        int decisions = 0;
        int nontrivialDecisions = 0;
        bool timedOut = false;
    };

    /**
     * Strip hidden information (RNG states, draw-pile order unless Frozen Eye)
     * and re-sample a concrete determinization from detSeed.
     */
    BattleContext determinizeBattleContext(const BattleContext &src, std::uint64_t detSeed);

    /**
     * Run root-determinized MCTS (fair=true) or 1-step true-state MCTS (fair=false)
     * and return aggregated root action statistics sorted best-first.
     */
    FairSearchResult fairSearchDecision(
        const BattleContext &bc,
        const FairSearchConfig &cfg,
        std::uint64_t decisionSeed);

    /**
     * Convenience single-decision recommendation using cfg.searchSeed.
     */
    Action fairSearchRecommend(const BattleContext &bc, const FairSearchConfig &cfg);

    /**
     * Play a BattleContext to completion using step-by-step fair or 1-step oracle search.
     */
    FairPlayoutResult playoutBattleFair(
        BattleContext &bc,
        const FairSearchConfig &cfg,
        int maxDecisions = 2000);

}  // namespace sts::search

#endif  // STS_LIGHTSPEED_FAIRBATTLESEARCHER_H
