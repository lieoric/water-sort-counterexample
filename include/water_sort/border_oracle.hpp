#pragma once

#include "water_sort/instance.hpp"

#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace water_sort {

struct OracleResult {
    bool solvable = false;
    std::uint64_t states_visited = 0;
    std::uint64_t transitions_tested = 0;
    std::vector<std::uint8_t> removal_columns;
    std::vector<std::uint8_t> reachable_bits;
};

struct CountResult {
    std::uint64_t solutions = 0;
    std::uint64_t states_evaluated = 0;
    std::uint64_t cap = 0;
};

struct DeadlockSignature {
    std::uint32_t available_buffers = 0;
    std::uint32_t deficient_color_count = 0;
    std::uint32_t hosted_color_count = 0;
    std::vector<std::uint32_t> need_by_source;

    [[nodiscard]] bool operator<(const DeadlockSignature& other) const;
    [[nodiscard]] std::string compact() const;
};

struct AnalysisResult {
    bool solvable = false;
    std::uint64_t reachable_states = 0;
    std::uint64_t transitions_tested = 0;
    std::uint64_t terminal_states = 0;
    std::uint32_t min_terminal_depth = 0;
    std::uint32_t max_terminal_depth = 0;
    std::map<DeadlockSignature, std::uint64_t> signatures;
};

struct PolicyTable {
    std::uint32_t initial_state = 0;
    std::vector<std::uint8_t> solvable;
    std::vector<std::uint8_t> reachable;
    std::vector<std::uint64_t> legal_columns;
    std::vector<std::uint64_t> safe_columns;
    std::uint64_t states_evaluated = 0;
    std::uint64_t transitions_tested = 0;
    std::uint64_t solvable_states = 0;
    std::uint64_t reachable_states = 0;
    std::uint64_t reachable_solvable_states = 0;
};

struct PolicyColumnView {
    std::vector<Color> visible_runs; // top to bottom
    bool truncated = false;
    std::uint32_t remaining_borders = 0;
    std::uint32_t buffers_needed = 0;
};

struct PolicyStateView {
    std::vector<std::uint32_t> ranks;
    std::vector<PolicyColumnView> columns;
    std::vector<std::uint32_t> f;
    std::vector<std::uint32_t> g;
    std::uint32_t available_buffers = 0;
};

class BorderOracle {
public:
    explicit BorderOracle(Instance instance);

    [[nodiscard]] OracleResult solve() const;
    [[nodiscard]] CountResult count_solutions(std::uint64_t cap) const;
    [[nodiscard]] AnalysisResult analyze() const;
    [[nodiscard]] PolicyTable policy_table() const;
    [[nodiscard]] PolicyStateView policy_state(std::uint32_t state,
                                               std::uint32_t visible_boundaries) const;
    [[nodiscard]] std::uint32_t state_count() const { return state_count_; }

private:
    struct ColumnData {
        std::vector<std::uint32_t> borders;
        std::vector<std::vector<std::uint16_t>> f_contribution;
        std::vector<std::vector<std::uint16_t>> g_contribution;
    };

    Instance instance_;
    std::vector<ColumnData> data_;
    std::vector<std::uint32_t> radix_;
    std::vector<std::uint32_t> multiplier_;
    std::uint32_t state_count_ = 0;
    std::uint32_t initial_state_ = 0;

    void decode(std::uint32_t state, std::vector<std::uint32_t>& ranks) const;
    void totals(const std::vector<std::uint32_t>& ranks,
                std::vector<std::uint32_t>& f,
                std::vector<std::uint32_t>& g,
                std::uint32_t& monochrome_bins) const;
    [[nodiscard]] bool can_remove(const std::vector<std::uint32_t>& ranks,
                                  std::size_t column,
                                  const std::vector<std::uint32_t>& f,
                                  const std::vector<std::uint32_t>& g,
                                  std::uint32_t monochrome_bins) const;
    [[nodiscard]] std::uint32_t buffers_needed(const std::vector<std::uint32_t>& ranks,
                                               std::size_t column,
                                               const std::vector<std::uint32_t>& f,
                                               const std::vector<std::uint32_t>& g) const;
};

} // namespace water_sort
