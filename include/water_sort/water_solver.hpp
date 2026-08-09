#pragma once

#include "water_sort/instance.hpp"

#include <cstdint>

namespace water_sort {

enum class WaterSolveStatus {
    solvable,
    unsolvable,
    state_limit_reached,
};

struct WaterSolveResult {
    WaterSolveStatus status = WaterSolveStatus::unsolvable;
    std::uint64_t states_visited = 0;
};

// Exact full-state BFS for small instances. A full monochrome column is locked
// and cannot be used as a source. max_states == 0 means unlimited.
WaterSolveResult solve_water_exact(const Instance& instance, std::uint64_t max_states = 0);

} // namespace water_sort
