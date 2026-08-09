#include "water_sort/border_oracle.hpp"

#include <algorithm>
#include <functional>
#include <limits>
#include <stdexcept>

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
    const auto rank = ranks[column];
    if (rank == 0) {
        return false;
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
    return needed <= monochrome_bins;
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

} // namespace water_sort
