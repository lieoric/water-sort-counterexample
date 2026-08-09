#include "water_sort/water_solver.hpp"

#include <algorithm>
#include <deque>
#include <string>
#include <unordered_set>
#include <vector>

namespace water_sort {
namespace {

using Column = std::vector<Color>;
using State = std::vector<Column>;

bool is_monochrome(const Column& column) {
    return column.empty() || std::all_of(column.begin(), column.end(), [&](Color color) {
        return color == column.front();
    });
}

bool is_locked(const Column& column, std::uint32_t height) {
    return column.size() == height && is_monochrome(column);
}

bool is_goal(const State& state, std::uint32_t height) {
    return std::all_of(state.begin(), state.end(), [&](const Column& column) {
        return column.empty() || is_locked(column, height);
    });
}

void canonicalize(State& state) {
    std::sort(state.begin(), state.end());
}

std::string encode(const State& state) {
    std::string key;
    std::size_t size = state.size();
    for (const auto& column : state) size += column.size();
    key.reserve(size);
    for (const auto& column : state) {
        key.push_back(static_cast<char>(column.size()));
        for (const auto color : column) {
            key.push_back(static_cast<char>(color + 1));
        }
    }
    return key;
}

} // namespace

WaterSolveResult solve_water_exact(const Instance& instance, std::uint64_t max_states) {
    instance.validate();
    State initial = instance.columns;
    initial.resize(initial.size() + instance.empty_columns);
    canonicalize(initial);

    std::deque<State> queue;
    std::unordered_set<std::string> seen;
    seen.insert(encode(initial));
    queue.push_back(std::move(initial));

    WaterSolveResult result;
    while (!queue.empty()) {
        auto state = std::move(queue.front());
        queue.pop_front();
        ++result.states_visited;
        if (is_goal(state, instance.height)) {
            result.status = WaterSolveStatus::solvable;
            return result;
        }
        if (max_states != 0 && seen.size() >= max_states) {
            result.status = WaterSolveStatus::state_limit_reached;
            return result;
        }

        for (std::size_t source = 0; source < state.size(); ++source) {
            if (state[source].empty() || is_locked(state[source], instance.height)) {
                continue;
            }
            const auto color = state[source].back();
            std::size_t run = 1;
            while (run < state[source].size() &&
                   state[source][state[source].size() - 1 - run] == color) {
                ++run;
            }
            for (std::size_t target = 0; target < state.size(); ++target) {
                if (source == target || state[target].size() == instance.height ||
                    (!state[target].empty() && state[target].back() != color)) {
                    continue;
                }
                const auto free_space = instance.height - state[target].size();
                const auto quantity = std::min<std::size_t>(run, free_space);
                auto next = state;
                next[source].resize(next[source].size() - quantity);
                next[target].insert(next[target].end(), quantity, color);
                canonicalize(next);
                auto key = encode(next);
                if (seen.insert(std::move(key)).second) {
                    queue.push_back(std::move(next));
                }
            }
        }
    }
    result.status = WaterSolveStatus::unsolvable;
    return result;
}

} // namespace water_sort
