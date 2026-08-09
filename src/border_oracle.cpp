#include "water_sort/border_oracle.hpp"

#include <algorithm>
#include <functional>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <tuple>

namespace water_sort {
namespace {

bool bit_is_set(const std::vector<std::uint8_t>& bits, std::uint32_t id) {
    return (bits[id >> 3U] & static_cast<std::uint8_t>(1U << (id & 7U))) != 0;
}

void set_bit(std::vector<std::uint8_t>& bits, std::uint32_t id) {
    bits[id >> 3U] |= static_cast<std::uint8_t>(1U << (id & 7U));
}

std::uint32_t ceil_div(std::uint32_t numerator, std::uint32_t denominator) {
    return numerator == 0 ? 0 : 1 + (numerator - 1) / denominator;
}

} // namespace

bool DeadlockSignature::operator<(const DeadlockSignature& other) const {
    return std::tie(available_buffers, deficient_color_count, hosted_color_count,
                    need_by_source) <
           std::tie(other.available_buffers, other.deficient_color_count,
                    other.hosted_color_count, other.need_by_source);
}

std::string DeadlockSignature::compact() const {
    std::ostringstream output;
    output << "a" << available_buffers << "-d" << deficient_color_count
           << "-h" << hosted_color_count << "-n";
    for (std::size_t i = 0; i < need_by_source.size(); ++i) {
        if (i != 0) output << ',';
        output << need_by_source[i];
    }
    return output.str();
}

BorderOracle::BorderOracle(Instance instance) : instance_(std::move(instance)) {
    instance_.validate();
    const auto n = instance_.columns.size();
    data_.resize(n);
    radix_.resize(n);
    multiplier_.resize(n);

    std::uint64_t product = 1;
    for (std::size_t column = 0; column < n; ++column) {
        auto& data = data_[column];
        data.borders.push_back(0);
        for (std::uint32_t position = 1; position < instance_.height; ++position) {
            if (instance_.columns[column][position - 1] != instance_.columns[column][position]) {
                data.borders.push_back(position);
            }
        }

        radix_[column] = static_cast<std::uint32_t>(data.borders.size());
        multiplier_[column] = static_cast<std::uint32_t>(product);
        product *= radix_[column];
        if (product > std::numeric_limits<std::uint32_t>::max()) {
            throw std::runtime_error("top-border state space exceeds uint32_t");
        }

        data.f_contribution.assign(data.borders.size(),
                                   std::vector<std::uint16_t>(instance_.color_count, 0));
        data.g_contribution.assign(data.borders.size(),
                                   std::vector<std::uint16_t>(instance_.color_count, 0));
        for (std::size_t rank = 0; rank < data.borders.size(); ++rank) {
            const auto border = data.borders[rank];
            for (std::uint32_t position = border; position < instance_.height; ++position) {
                ++data.f_contribution[rank][instance_.columns[column][position]];
            }
            if (border > 0) {
                const auto top_color = instance_.columns[column][border];
                data.g_contribution[rank][top_color] =
                    static_cast<std::uint16_t>(instance_.height - border);
            }
        }
    }

    state_count_ = static_cast<std::uint32_t>(product);
    for (std::size_t column = 0; column < n; ++column) {
        initial_state_ += (radix_[column] - 1U) * multiplier_[column];
    }
}

void BorderOracle::decode(std::uint32_t state, std::vector<std::uint32_t>& ranks) const {
    for (std::size_t column = 0; column < ranks.size(); ++column) {
        ranks[column] = (state / multiplier_[column]) % radix_[column];
    }
}

void BorderOracle::totals(const std::vector<std::uint32_t>& ranks,
                          std::vector<std::uint32_t>& f,
                          std::vector<std::uint32_t>& g,
                          std::uint32_t& monochrome_bins) const {
    std::fill(f.begin(), f.end(), 0);
    std::fill(g.begin(), g.end(), 0);
    monochrome_bins = instance_.empty_columns;
    for (std::size_t column = 0; column < ranks.size(); ++column) {
        const auto rank = ranks[column];
        if (rank == 0) {
            ++monochrome_bins;
        }
        for (std::size_t color = 0; color < f.size(); ++color) {
            f[color] += data_[column].f_contribution[rank][color];
            g[color] += data_[column].g_contribution[rank][color];
        }
    }
}

bool BorderOracle::can_remove(const std::vector<std::uint32_t>& ranks,
                              std::size_t column,
                              const std::vector<std::uint32_t>& f,
                              const std::vector<std::uint32_t>& g,
                              std::uint32_t monochrome_bins) const {
    return buffers_needed(ranks, column, f, g) <= monochrome_bins;
}

std::uint32_t BorderOracle::buffers_needed(const std::vector<std::uint32_t>& ranks,
                                           std::size_t column,
                                           const std::vector<std::uint32_t>& f,
                                           const std::vector<std::uint32_t>& g) const {
    const auto rank = ranks[column];
    if (rank == 0) {
        return std::numeric_limits<std::uint32_t>::max();
    }
    const auto border = data_[column].borders[rank];
    const auto source_top_color = instance_.columns[column][border];
    std::uint32_t needed = 0;
    for (std::uint32_t color = 0; color < instance_.color_count; ++color) {
        auto usable = g[color];
        if (color == source_top_color) {
            usable -= instance_.height - border;
        }
        if (f[color] > usable) {
            needed += ceil_div(f[color] - usable, instance_.height);
        }
    }
    return needed;
}

OracleResult BorderOracle::solve() const {
    OracleResult result;
    result.reachable_bits.assign((state_count_ + 7U) / 8U, 0);
    std::vector<std::uint32_t> queue;
    queue.reserve(std::min<std::uint32_t>(state_count_, 1U << 20U));
    std::vector<std::uint32_t> parent(state_count_, std::numeric_limits<std::uint32_t>::max());
    std::vector<std::uint8_t> parent_move(state_count_, 0);

    set_bit(result.reachable_bits, initial_state_);
    queue.push_back(initial_state_);
    parent[initial_state_] = initial_state_;

    std::vector<std::uint32_t> ranks(instance_.columns.size());
    std::vector<std::uint32_t> f(instance_.color_count);
    std::vector<std::uint32_t> g(instance_.color_count);

    for (std::size_t head = 0; head < queue.size(); ++head) {
        const auto state = queue[head];
        ++result.states_visited;
        if (state == 0) {
            result.solvable = true;
            break;
        }

        decode(state, ranks);
        std::uint32_t monochrome_bins = 0;
        totals(ranks, f, g, monochrome_bins);
        for (std::size_t column = 0; column < ranks.size(); ++column) {
            if (ranks[column] == 0) {
                continue;
            }
            ++result.transitions_tested;
            if (!can_remove(ranks, column, f, g, monochrome_bins)) {
                continue;
            }
            const auto next = state - multiplier_[column];
            if (!bit_is_set(result.reachable_bits, next)) {
                set_bit(result.reachable_bits, next);
                parent[next] = state;
                parent_move[next] = static_cast<std::uint8_t>(column);
                queue.push_back(next);
            }
        }
    }

    if (result.solvable) {
        std::uint32_t state = 0;
        while (state != initial_state_) {
            result.removal_columns.push_back(parent_move[state]);
            state = parent[state];
        }
        std::reverse(result.removal_columns.begin(), result.removal_columns.end());
        result.reachable_bits.clear();
    }
    return result;
}

CountResult BorderOracle::count_solutions(std::uint64_t cap) const {
    if (cap == 0) {
        throw std::runtime_error("solution-count cap must be positive");
    }
    CountResult result;
    result.cap = cap;
    const auto unknown = std::numeric_limits<std::uint64_t>::max();
    std::vector<std::uint64_t> memo(state_count_, unknown);
    memo[0] = 1;

    std::vector<std::uint32_t> ranks(instance_.columns.size());
    std::vector<std::uint32_t> f(instance_.color_count);
    std::vector<std::uint32_t> g(instance_.color_count);

    std::function<std::uint64_t(std::uint32_t)> visit = [&](std::uint32_t state) -> std::uint64_t {
        if (memo[state] != unknown) {
            return memo[state];
        }
        ++result.states_evaluated;
        decode(state, ranks);
        const auto local_ranks = ranks;
        std::uint32_t monochrome_bins = 0;
        totals(local_ranks, f, g, monochrome_bins);
        const auto local_f = f;
        const auto local_g = g;

        std::uint64_t sum = 0;
        for (std::size_t column = 0; column < local_ranks.size(); ++column) {
            if (local_ranks[column] == 0 ||
                !can_remove(local_ranks, column, local_f, local_g, monochrome_bins)) {
                continue;
            }
            const auto count = visit(state - multiplier_[column]);
            if (count >= cap - sum) {
                sum = cap;
                break;
            }
            sum += count;
        }
        memo[state] = sum;
        return sum;
    };

    result.solutions = visit(initial_state_);
    return result;
}

PolicyTable BorderOracle::policy_table() const {
    return policy_table_impl(static_cast<std::uint32_t>(instance_.columns.size()));
}

PolicyTable BorderOracle::policy_table_to_exhausted_columns(
    std::uint32_t target_exhausted_columns) const {
    if (target_exhausted_columns == 0 ||
        target_exhausted_columns > instance_.columns.size()) {
        throw std::runtime_error("exhausted-column target is out of range");
    }
    return policy_table_impl(target_exhausted_columns);
}

PolicyTable BorderOracle::policy_table_impl(
    std::uint32_t target_exhausted_columns) const {
    if (instance_.columns.size() > 64) {
        throw std::runtime_error("policy masks support at most 64 full columns");
    }

    PolicyTable result;
    result.initial_state = initial_state_;
    result.target_exhausted_columns = target_exhausted_columns;
    result.solvable.assign(state_count_, 0);
    result.reachable.assign(state_count_, 0);
    result.goal.assign(state_count_, 0);
    result.legal_columns.assign(state_count_, 0);
    result.safe_columns.assign(state_count_, 0);

    std::vector<std::uint32_t> ranks(instance_.columns.size());
    std::vector<std::uint32_t> f(instance_.color_count);
    std::vector<std::uint32_t> g(instance_.color_count);
    for (std::uint32_t state = 0; state < state_count_; ++state) {
        ++result.states_evaluated;
        decode(state, ranks);
        const auto exhausted = static_cast<std::uint32_t>(
            std::count(ranks.begin(), ranks.end(), 0U));
        if (exhausted >= target_exhausted_columns) {
            result.goal[state] = 1;
            result.solvable[state] = 1;
            continue;
        }

        std::uint32_t monochrome_bins = 0;
        totals(ranks, f, g, monochrome_bins);
        std::uint64_t legal = 0;
        std::uint64_t safe = 0;
        for (std::size_t column = 0; column < ranks.size(); ++column) {
            if (ranks[column] == 0) continue;
            ++result.transitions_tested;
            if (!can_remove(ranks, column, f, g, monochrome_bins)) continue;
            const auto bit = std::uint64_t{1} << column;
            legal |= bit;
            const auto next = state - multiplier_[column];
            if (result.solvable[next] != 0) safe |= bit;
        }
        result.legal_columns[state] = legal;
        result.safe_columns[state] = safe;
        result.solvable[state] = safe != 0 ? 1 : 0;
    }

    std::vector<std::uint32_t> queue;
    queue.reserve(std::min<std::uint32_t>(state_count_, 1U << 20U));
    result.reachable[initial_state_] = 1;
    queue.push_back(initial_state_);
    for (std::size_t head = 0; head < queue.size(); ++head) {
        const auto state = queue[head];
        if (result.goal[state] != 0) continue;
        auto legal = result.legal_columns[state];
        while (legal != 0) {
            std::size_t column = 0;
            while ((legal & (std::uint64_t{1} << column)) == 0) ++column;
            legal &= legal - 1;
            const auto next = state - multiplier_[column];
            if (result.reachable[next] == 0) {
                result.reachable[next] = 1;
                queue.push_back(next);
            }
        }
    }

    for (std::uint32_t state = 0; state < state_count_; ++state) {
        if (result.solvable[state] != 0) ++result.solvable_states;
        if (result.reachable[state] != 0) ++result.reachable_states;
        if (result.solvable[state] != 0 && result.reachable[state] != 0) {
            ++result.reachable_solvable_states;
        }
    }
    return result;
}

PolicyStateView BorderOracle::policy_state(std::uint32_t state,
                                           std::uint32_t visible_boundaries) const {
    if (state >= state_count_) throw std::runtime_error("policy state is out of range");

    PolicyStateView result;
    result.ranks.resize(instance_.columns.size());
    result.f.resize(instance_.color_count);
    result.g.resize(instance_.color_count);
    decode(state, result.ranks);
    totals(result.ranks, result.f, result.g, result.available_buffers);
    result.columns.resize(instance_.columns.size());

    for (std::size_t column = 0; column < instance_.columns.size(); ++column) {
        auto& output = result.columns[column];
        auto cursor = result.ranks[column];
        output.remaining_borders = cursor;
        output.buffers_needed = buffers_needed(result.ranks, column, result.f, result.g);
        if (cursor == 0) {
            output.visible_runs.push_back(instance_.columns[column][0]);
            continue;
        }

        output.visible_runs.push_back(
            instance_.columns[column][data_[column].borders[cursor]]);
        std::uint32_t exposed = 0;
        while (cursor > 0 && exposed < visible_boundaries) {
            output.visible_runs.push_back(
                instance_.columns[column][data_[column].borders[cursor] - 1U]);
            --cursor;
            ++exposed;
        }
        output.truncated = cursor > 0;
    }
    return result;
}

std::uint32_t BorderOracle::policy_successor(std::uint32_t state,
                                              std::size_t column) const {
    if (state >= state_count_ || column >= instance_.columns.size()) {
        throw std::runtime_error("policy successor is out of range");
    }
    const auto rank = (state / multiplier_[column]) % radix_[column];
    if (rank == 0) throw std::runtime_error("exhausted policy column has no successor");
    return state - multiplier_[column];
}

AnalysisResult BorderOracle::analyze() const {
    AnalysisResult result;
    std::vector<std::uint8_t> seen((state_count_ + 7U) / 8U, 0);
    std::vector<std::uint32_t> queue;
    queue.reserve(std::min<std::uint32_t>(state_count_, 1U << 20U));
    set_bit(seen, initial_state_);
    queue.push_back(initial_state_);

    std::vector<std::uint32_t> ranks(instance_.columns.size());
    std::vector<std::uint32_t> f(instance_.color_count);
    std::vector<std::uint32_t> g(instance_.color_count);
    std::uint32_t initial_rank_sum = 0;
    for (const auto rank : radix_) initial_rank_sum += rank - 1U;
    auto min_depth = std::numeric_limits<std::uint32_t>::max();

    for (std::size_t head = 0; head < queue.size(); ++head) {
        const auto state = queue[head];
        ++result.reachable_states;
        if (state == 0) {
            result.solvable = true;
            continue;
        }

        decode(state, ranks);
        std::uint32_t rank_sum = 0;
        for (const auto rank : ranks) rank_sum += rank;
        const auto depth = initial_rank_sum - rank_sum;
        std::uint32_t monochrome_bins = 0;
        totals(ranks, f, g, monochrome_bins);

        bool has_successor = false;
        std::vector<std::uint32_t> needs;
        needs.reserve(ranks.size());
        for (std::size_t column = 0; column < ranks.size(); ++column) {
            if (ranks[column] == 0) continue;
            ++result.transitions_tested;
            const auto needed = buffers_needed(ranks, column, f, g);
            needs.push_back(needed);
            if (needed > monochrome_bins) continue;
            has_successor = true;
            const auto next = state - multiplier_[column];
            if (!bit_is_set(seen, next)) {
                set_bit(seen, next);
                queue.push_back(next);
            }
        }

        if (!has_successor) {
            ++result.terminal_states;
            min_depth = std::min(min_depth, depth);
            result.max_terminal_depth = std::max(result.max_terminal_depth, depth);
            DeadlockSignature signature;
            signature.available_buffers = monochrome_bins;
            signature.deficient_color_count = 0;
            signature.hosted_color_count = 0;
            for (std::size_t color = 0; color < f.size(); ++color) {
                if (f[color] > g[color]) ++signature.deficient_color_count;
                if (g[color] > 0) ++signature.hosted_color_count;
            }
            std::sort(needs.begin(), needs.end());
            signature.need_by_source = std::move(needs);
            ++result.signatures[signature];
        }
    }

    result.min_terminal_depth =
        min_depth == std::numeric_limits<std::uint32_t>::max() ? 0 : min_depth;
    return result;
}

} // namespace water_sort
