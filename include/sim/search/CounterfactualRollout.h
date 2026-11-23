//
// Zero-leakage run-level determinization and CRN counterfactual rollout evaluation.
//

#ifndef STS_LIGHTSPEED_COUNTERFACTUALROLLOUT_H
#define STS_LIGHTSPEED_COUNTERFACTUALROLLOUT_H

#include "game/GameContext.h"
#include "sim/search/GameAction.h"

#include <cstdint>
#include <vector>

namespace sts::search {

    struct RolloutConfig {
        int numRollouts = 16;
        int rolloutSims = 100;
        double bossSimMultiplier = 3.0;
        int maxAct = 1;
        std::uint64_t searchSeed = 1;
    };

    struct RolloutActionStat {
        GameAction action;
        int rollouts = 0;
        int wins = 0;
        double scoreSum = 0.0;
        double floorSum = 0.0;
        double winHpSum = 0.0;

        [[nodiscard]] double winRate() const {
            return rollouts > 0 ? static_cast<double>(wins) / static_cast<double>(rollouts) : 0.0;
        }

        [[nodiscard]] double meanScore() const {
            return rollouts > 0 ? scoreSum / static_cast<double>(rollouts) : 0.0;
        }
    };

    /**
     * Clone a GameContext and scramble all hidden RNG streams, event/relic pools,
     * and unseen future encounter queues from detSeed while keeping visible run
     * state (map layout, boss, deck, relics, HP, gold, seen prefixes) intact.
     */
    GameContext determinizeGameContext(const GameContext &src, std::uint64_t detSeed);

    /**
     * Enumerate candidate macro decisions for the current non-combat screen.
     * On REWARDS screens with card rewards, returns individual card picks + card skip
     * (CARD(0, 5)) before leaving the reward screen.
     */
    std::vector<GameAction> getMacroDecisionActions(const GameContext &gc);

    /**
     * Evaluate candidate macro actions using Common Random Numbers (CRN) across
     * cfg.numRollouts sampled futures, sorted best-first by meanScore() then winRate().
     */
    std::vector<RolloutActionStat> evaluateGameActionsByRollout(
        const GameContext &gc,
        const std::vector<GameAction> &actions,
        const RolloutConfig &cfg);

}  // namespace sts::search

#endif  // STS_LIGHTSPEED_COUNTERFACTUALROLLOUT_H
