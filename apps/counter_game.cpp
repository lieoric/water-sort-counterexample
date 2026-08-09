#include <algorithm>
#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

constexpr std::size_t kColors = 4;
constexpr std::size_t kOriginalColumns = 4;
constexpr std::size_t kEmptyColumns = 2;
constexpr std::size_t kTargetExhausted = 2;

enum class ObservationMode { q_only, next_run };

struct Options {
    std::uint32_t height = 0;
    std::filesystem::path report = "counter-game-report.json";
    std::filesystem::path witness = "counter-game-witness.txt";
    std::uint64_t max_states = 5'000'000;
    std::uint64_t max_candidates = 100'000'000;
    ObservationMode observation = ObservationMode::q_only;
    bool self_test = false;
};

const char* observation_name(ObservationMode mode) {
    return mode == ObservationMode::q_only ? "q" : "next-run";
}

void ensure_parent(const std::filesystem::path& path);

struct ColorBucket {
    std::int32_t deficit = 0;
    std::uint8_t count = 0;
    std::array<std::uint16_t, kOriginalColumns> exposed{};

    friend bool operator==(const ColorBucket& lhs, const ColorBucket& rhs) {
        return lhs.deficit == rhs.deficit && lhs.count == rhs.count &&
               lhs.exposed == rhs.exposed;
    }
};

bool bucket_less(const ColorBucket& lhs, const ColorBucket& rhs) {
    if (lhs.deficit != rhs.deficit) return lhs.deficit < rhs.deficit;
    if (lhs.count != rhs.count) return lhs.count < rhs.count;
    return lhs.exposed < rhs.exposed;
}

struct State {
    std::uint8_t exhausted = 0;
    std::array<ColorBucket, kColors> colors{};

    friend bool operator==(const State& lhs, const State& rhs) {
        return lhs.exhausted == rhs.exhausted && lhs.colors == rhs.colors;
    }
};

bool state_less(const State& lhs, const State& rhs) {
    if (lhs.exhausted != rhs.exhausted) return lhs.exhausted < rhs.exhausted;
    for (std::size_t color = 0; color < kColors; ++color) {
        if (bucket_less(lhs.colors[color], rhs.colors[color])) return true;
        if (bucket_less(rhs.colors[color], lhs.colors[color])) return false;
    }
    return false;
}

std::size_t hash_combine(std::size_t seed, std::size_t value) {
    constexpr std::size_t golden = sizeof(std::size_t) == 8
        ? static_cast<std::size_t>(0x9e3779b97f4a7c15ULL)
        : static_cast<std::size_t>(0x9e3779b9UL);
    seed ^= value + golden + (seed << 6U) + (seed >> 2U);
    return seed;
}

struct StateHash {
    std::size_t operator()(const State& state) const noexcept {
        std::size_t seed = state.exhausted;
        for (const auto& bucket : state.colors) {
            seed = hash_combine(seed,
                                std::hash<std::int32_t>{}(bucket.deficit));
            seed = hash_combine(seed, bucket.count);
            for (const auto value : bucket.exposed) {
                seed = hash_combine(seed, value);
            }
        }
        return seed;
    }
};

void normalize_bucket(ColorBucket& bucket) {
    std::sort(bucket.exposed.begin(),
              bucket.exposed.begin() + bucket.count);
    std::fill(bucket.exposed.begin() + bucket.count,
              bucket.exposed.end(), 0);
}

State canonicalize(State state) {
    for (auto& bucket : state.colors) normalize_bucket(bucket);
    std::sort(state.colors.begin(), state.colors.end(), bucket_less);
    return state;
}

std::uint32_t bucket_exposed(const ColorBucket& bucket) {
    return std::accumulate(bucket.exposed.begin(),
                           bucket.exposed.begin() + bucket.count,
                           std::uint32_t{0});
}

std::uint32_t active_columns(const State& state) {
    std::uint32_t result = 0;
    for (const auto& bucket : state.colors) result += bucket.count;
    return result;
}

std::uint32_t remaining_items(const State& state, std::uint32_t height) {
    std::uint32_t result = 0;
    for (const auto& bucket : state.colors) {
        for (std::size_t index = 0; index < bucket.count; ++index) {
            result += height - bucket.exposed[index];
        }
    }
    return result;
}

std::array<std::int32_t, kColors> exposed_counts(const State& state) {
    std::array<std::int32_t, kColors> result{};
    for (std::size_t color = 0; color < kColors; ++color) {
        result[color] = state.colors[color].deficit +
                        static_cast<std::int32_t>(bucket_exposed(
                            state.colors[color]));
    }
    return result;
}

// Algebraic consistency is exact for the projection Q.  Think of every active
// original column as split at its current border.  Its exposed word has length
// s_i and ends in a_i; its nonempty hidden word has length h-s_i and starts in
// a color different from a_i.  Exhausted columns contribute z*h unconstrained
// exposed positions.  F_c=d_c+sum_{a_i=c}s_i recovers the exposed color totals.
bool algebraically_consistent(const State& state, std::uint32_t height) {
    if (state.exhausted > kOriginalColumns) return false;
    if (active_columns(state) + state.exhausted != kOriginalColumns) {
        return false;
    }

    std::uint32_t sum_s = 0;
    std::int64_t sum_d = 0;
    std::int64_t sum_f = 0;
    std::array<std::int32_t, kColors> remaining{};
    for (std::size_t color = 0; color < kColors; ++color) {
        const auto& bucket = state.colors[color];
        for (std::size_t index = 0; index < bucket.count; ++index) {
            const auto value = bucket.exposed[index];
            if (value == 0 || value >= height) return false;
            if (index != 0 && bucket.exposed[index - 1] > value) return false;
            sum_s += value;
        }
        for (std::size_t index = bucket.count; index < kOriginalColumns;
             ++index) {
            if (bucket.exposed[index] != 0) return false;
        }

        const auto f = bucket.deficit +
                       static_cast<std::int32_t>(bucket_exposed(bucket));
        if (f < static_cast<std::int32_t>(bucket.count) ||
            f > static_cast<std::int32_t>(height)) {
            return false;
        }
        remaining[color] = static_cast<std::int32_t>(height) - f;
        sum_d += bucket.deficit;
        sum_f += f;
    }

    if (sum_d != static_cast<std::int64_t>(state.exhausted) * height) {
        return false;
    }
    if (sum_f != static_cast<std::int64_t>(state.exhausted) * height +
                    sum_s) {
        return false;
    }

    const auto total_hidden = std::accumulate(remaining.begin(),
                                               remaining.end(),
                                               std::int32_t{0});
    if (total_hidden != static_cast<std::int32_t>(remaining_items(state,
                                                                   height))) {
        return false;
    }

    // Hall's condition for choosing the first hidden item of every active
    // column.  A column topped by c may use every remaining color except c.
    // Intersections of two different forbidden-color classes have all four
    // colors available, so these four inequalities are also sufficient.
    for (std::size_t color = 0; color < kColors; ++color) {
        if (static_cast<std::int32_t>(state.colors[color].count) >
            total_hidden - remaining[color]) {
            return false;
        }
    }
    return true;
}

bool is_initial_projection(const State& state, std::uint32_t height) {
    if (state.exhausted == 0) {
        return std::all_of(state.colors.begin(), state.colors.end(),
                           [](const ColorBucket& bucket) {
                               return bucket.deficit == 0;
                           });
    }
    if (state.exhausted != 1) return false;

    std::size_t full_deficits = 0;
    for (const auto& bucket : state.colors) {
        if (bucket.deficit == static_cast<std::int32_t>(height)) {
            ++full_deficits;
        } else if (bucket.deficit != 0) {
            return false;
        }
    }
    return full_deficits == 1;
}

struct SourceAction {
    std::uint8_t color = 0;
    std::uint16_t exposed = 0;
    std::uint8_t demand = 0;
};

std::uint8_t source_demand(const State& state, std::uint8_t source_color,
                           std::uint16_t exposed) {
    std::uint8_t demand = 0;
    for (std::size_t color = 0; color < kColors; ++color) {
        auto value = state.colors[color].deficit;
        if (color == source_color) value += exposed;
        if (value > 0) ++demand;
    }
    return demand;
}

std::vector<SourceAction> legal_actions(const State& state) {
    std::vector<SourceAction> actions;
    const auto available = static_cast<std::uint8_t>(kEmptyColumns +
                                                      state.exhausted);
    for (std::uint8_t color = 0; color < kColors; ++color) {
        const auto& bucket = state.colors[color];
        // Equal adjacent buckets are exchanged by a color automorphism of Q.
        // Keeping only the first makes these source choices genuine action
        // orbits rather than merely deduplicating identical s values inside a
        // single color.
        if (color != 0 && bucket == state.colors[color - 1]) continue;
        for (std::size_t index = 0; index < bucket.count; ++index) {
            if (index != 0 && bucket.exposed[index] ==
                                  bucket.exposed[index - 1]) {
                continue;
            }
            SourceAction action;
            action.color = color;
            action.exposed = bucket.exposed[index];
            action.demand = source_demand(state, color, action.exposed);
            if (action.demand <= available) actions.push_back(action);
        }
    }
    return actions;
}

void remove_exposed(ColorBucket& bucket, std::uint16_t exposed) {
    const auto end = bucket.exposed.begin() + bucket.count;
    const auto found = std::find(bucket.exposed.begin(), end, exposed);
    if (found == end) throw std::logic_error("source is absent from bucket");
    std::move(found + 1, end, found);
    --bucket.count;
    bucket.exposed[bucket.count] = 0;
}

void add_exposed(ColorBucket& bucket, std::uint16_t exposed) {
    if (bucket.count >= kOriginalColumns) {
        throw std::logic_error("too many active sources in color bucket");
    }
    bucket.exposed[bucket.count++] = exposed;
    normalize_bucket(bucket);
}

struct Outcome {
    std::uint8_t revealed_color = 0;
    std::uint16_t run_length = 0;
    bool goal = false;
    State successor;
};

std::vector<Outcome> outcomes(const State& state, const SourceAction& action,
                              std::uint32_t height) {
    std::vector<Outcome> result;
    const auto hidden = height - action.exposed;
    for (std::uint8_t revealed = 0; revealed < kColors; ++revealed) {
        if (revealed == action.color) continue;
        for (std::uint16_t run = 1; run <= hidden; ++run) {
            State successor = state;
            auto& source = successor.colors[action.color];
            auto& target = successor.colors[revealed];
            remove_exposed(source, action.exposed);

            if (run == hidden) {
                source.deficit += action.exposed;
                target.deficit += run;
                ++successor.exhausted;
            } else {
                source.deficit += action.exposed;
                target.deficit -= action.exposed;
                add_exposed(target,
                            static_cast<std::uint16_t>(action.exposed + run));
            }

            Outcome outcome;
            outcome.revealed_color = revealed;
            outcome.run_length = run;
            successor = canonicalize(successor);
            // Even a transition that reaches z=2 must correspond to a
            // balanced hidden completion.  Only after this feasibility check
            // may the strict z>=2 finishing theorem turn it into a goal edge.
            if (!algebraically_consistent(successor, height)) continue;
            outcome.goal = successor.exhausted >= kTargetExhausted;
            outcome.successor = std::move(successor);

            const auto duplicate = std::find_if(
                result.begin(), result.end(), [&](const Outcome& prior) {
                    if (prior.goal != outcome.goal) return false;
                    if (prior.goal) return true;
                    return prior.successor == outcome.successor;
                });
            if (duplicate == result.end()) result.push_back(std::move(outcome));
        }
    }
    return result;
}

struct Enumeration {
    std::vector<State> states;
    std::unordered_map<State, std::size_t, StateHash> index;
    std::uint64_t candidates = 0;
};

void insert_state(Enumeration& enumeration, State state,
                  const Options& options) {
    ++enumeration.candidates;
    if (enumeration.candidates > options.max_candidates) {
        throw std::runtime_error(
            "candidate limit exceeded; raise --max-candidates explicitly");
    }
    state = canonicalize(std::move(state));
    if (!algebraically_consistent(state, options.height)) return;
    if (enumeration.index.find(state) != enumeration.index.end()) return;
    if (enumeration.states.size() >= options.max_states) {
        throw std::runtime_error(
            "state limit exceeded; raise --max-states explicitly");
    }
    const auto id = enumeration.states.size();
    enumeration.states.push_back(state);
    enumeration.index.emplace(std::move(state), id);
}

void enumerate_f(const std::array<std::uint8_t, kColors>& counts,
                 const std::array<std::uint32_t, kColors>& g,
                 std::size_t color, std::int32_t remaining,
                 State& state, Enumeration& enumeration,
                 const Options& options) {
    if (color == kColors) {
        if (remaining == 0) insert_state(enumeration, state, options);
        return;
    }

    std::int32_t min_after = 0;
    std::int32_t max_after = 0;
    for (std::size_t next = color + 1; next < kColors; ++next) {
        min_after += counts[next];
        max_after += static_cast<std::int32_t>(options.height);
    }
    const auto lower = std::max<std::int32_t>(
        counts[color], remaining - max_after);
    const auto upper = std::min<std::int32_t>(
        static_cast<std::int32_t>(options.height), remaining - min_after);
    for (auto f = lower; f <= upper; ++f) {
        state.colors[color].deficit = f - static_cast<std::int32_t>(g[color]);
        enumerate_f(counts, g, color + 1, remaining - f, state,
                    enumeration, options);
    }
}

void enumerate_source_multisets(std::uint8_t exhausted,
                                std::size_t depth, std::uint32_t first_type,
                                State& state, Enumeration& enumeration,
                                const Options& options) {
    const auto wanted = kOriginalColumns - exhausted;
    if (depth == wanted) {
        std::array<std::uint8_t, kColors> counts{};
        std::array<std::uint32_t, kColors> g{};
        std::uint32_t sum_s = 0;
        for (std::size_t color = 0; color < kColors; ++color) {
            const auto& bucket = state.colors[color];
            counts[color] = bucket.count;
            g[color] = bucket_exposed(bucket);
            sum_s += g[color];
        }
        const auto total_f = static_cast<std::int32_t>(exhausted) *
                                 static_cast<std::int32_t>(options.height) +
                             static_cast<std::int32_t>(sum_s);
        enumerate_f(counts, g, 0, total_f, state, enumeration, options);
        return;
    }

    const auto type_count = static_cast<std::uint32_t>(kColors) *
                            (options.height - 1U);
    for (auto type = first_type; type < type_count; ++type) {
        const auto color = static_cast<std::uint8_t>(
            type / (options.height - 1U));
        const auto exposed = static_cast<std::uint16_t>(
            type % (options.height - 1U) + 1U);
        auto& bucket = state.colors[color];
        bucket.exposed[bucket.count++] = exposed;
        enumerate_source_multisets(exhausted, depth + 1, type, state,
                                   enumeration, options);
        --bucket.count;
        bucket.exposed[bucket.count] = 0;
    }
}

Enumeration enumerate_states(const Options& options) {
    Enumeration enumeration;
    const auto reserve = static_cast<std::size_t>(
        std::min<std::uint64_t>(options.max_states, 1'000'000));
    enumeration.states.reserve(reserve);
    enumeration.index.reserve(reserve);
    for (std::uint8_t exhausted = 0; exhausted < kTargetExhausted;
         ++exhausted) {
        State state;
        state.exhausted = exhausted;
        enumerate_source_multisets(exhausted, 0, 0, state, enumeration,
                                   options);
    }
    return enumeration;
}

struct Solution {
    std::vector<std::uint8_t> winning;
    std::vector<std::uint32_t> rank;
    std::uint64_t legal_action_orbits = 0;
    std::uint64_t environment_edges = 0;
    std::uint64_t dead_ends = 0;
    std::uint64_t safe_action_orbits = 0;
};

Solution retrograde(const Enumeration& enumeration, const Options& options) {
    Solution solution;
    solution.winning.assign(enumeration.states.size(), 0);
    solution.rank.assign(enumeration.states.size(), 0);
    std::vector<std::uint8_t> processed(enumeration.states.size(), 0);
    std::vector<std::size_t> order(enumeration.states.size());
    std::iota(order.begin(), order.end(), std::size_t{0});
    std::sort(order.begin(), order.end(), [&](std::size_t lhs,
                                              std::size_t rhs) {
        const auto left = remaining_items(enumeration.states[lhs],
                                          options.height);
        const auto right = remaining_items(enumeration.states[rhs],
                                           options.height);
        if (left != right) return left < right;
        return state_less(enumeration.states[lhs], enumeration.states[rhs]);
    });

    for (const auto id : order) {
        const auto& state = enumeration.states[id];
        const auto actions = legal_actions(state);
        solution.legal_action_orbits += actions.size();
        if (actions.empty()) ++solution.dead_ends;

        bool state_winning = false;
        auto best_rank = std::numeric_limits<std::uint32_t>::max();
        for (const auto& action : actions) {
            const auto next = outcomes(state, action, options.height);
            if (next.empty()) {
                throw std::logic_error(
                    "consistent active source has no feasible hidden reveal");
            }
            solution.environment_edges += next.size();
            bool action_safe = true;
            std::uint32_t worst_rank = 0;
            for (const auto& outcome : next) {
                if (outcome.goal) continue;
                const auto found = enumeration.index.find(outcome.successor);
                if (found == enumeration.index.end()) {
                    throw std::logic_error(
                        "consistent successor is missing from enumeration");
                }
                const auto successor = found->second;
                if (remaining_items(enumeration.states[successor],
                                    options.height) >=
                    remaining_items(state, options.height)) {
                    throw std::logic_error("counter-game transition is not descending");
                }
                if (processed[successor] == 0) {
                    throw std::logic_error("retrograde order is invalid");
                }
                if (solution.winning[successor] == 0) action_safe = false;
                worst_rank = std::max(worst_rank, solution.rank[successor]);
            }
            if (action_safe) {
                ++solution.safe_action_orbits;
                state_winning = true;
                best_rank = std::min(best_rank, worst_rank + 1U);
            }
        }
        solution.winning[id] = state_winning ? 1U : 0U;
        if (state_winning) solution.rank[id] = best_rank;
        processed[id] = 1;
    }
    return solution;
}

struct VisibleSource {
    std::uint8_t top = 0;
    std::uint16_t exposed = 0;
    std::uint8_t next = 0;
    std::uint16_t next_run = 0;

    friend bool operator==(const VisibleSource& lhs,
                           const VisibleSource& rhs) {
        return std::tie(lhs.top, lhs.exposed, lhs.next, lhs.next_run) ==
               std::tie(rhs.top, rhs.exposed, rhs.next, rhs.next_run);
    }
};

bool visible_source_less(const VisibleSource& lhs, const VisibleSource& rhs) {
    return std::tie(lhs.top, lhs.exposed, lhs.next, lhs.next_run) <
           std::tie(rhs.top, rhs.exposed, rhs.next, rhs.next_run);
}

struct VisibleState {
    std::uint8_t exhausted = 0;
    std::uint8_t count = 0;
    std::array<std::int32_t, kColors> deficit{};
    std::array<VisibleSource, kOriginalColumns> sources{};

    friend bool operator==(const VisibleState& lhs, const VisibleState& rhs) {
        return lhs.exhausted == rhs.exhausted && lhs.count == rhs.count &&
               lhs.deficit == rhs.deficit && lhs.sources == rhs.sources;
    }
};

bool visible_state_less(const VisibleState& lhs, const VisibleState& rhs) {
    if (lhs.exhausted != rhs.exhausted) return lhs.exhausted < rhs.exhausted;
    if (lhs.count != rhs.count) return lhs.count < rhs.count;
    if (lhs.deficit != rhs.deficit) return lhs.deficit < rhs.deficit;
    return std::lexicographical_compare(
        lhs.sources.begin(), lhs.sources.begin() + lhs.count,
        rhs.sources.begin(), rhs.sources.begin() + rhs.count,
        visible_source_less);
}

struct VisibleStateHash {
    std::size_t operator()(const VisibleState& state) const noexcept {
        std::size_t seed = hash_combine(state.exhausted, state.count);
        for (const auto value : state.deficit) {
            seed = hash_combine(seed, std::hash<std::int32_t>{}(value));
        }
        for (const auto& source : state.sources) {
            seed = hash_combine(seed, source.top);
            seed = hash_combine(seed, source.exposed);
            seed = hash_combine(seed, source.next);
            seed = hash_combine(seed, source.next_run);
        }
        return seed;
    }
};

const std::vector<std::array<std::uint8_t, kColors>>& color_permutations() {
    static const auto permutations = [] {
        std::vector<std::array<std::uint8_t, kColors>> result;
        std::array<std::uint8_t, kColors> value{0, 1, 2, 3};
        do {
            result.push_back(value);
        } while (std::next_permutation(value.begin(), value.end()));
        return result;
    }();
    return permutations;
}

VisibleState canonicalize_visible(const VisibleState& state) {
    std::optional<VisibleState> best;
    for (const auto& permutation : color_permutations()) {
        VisibleState candidate;
        candidate.exhausted = state.exhausted;
        candidate.count = state.count;
        for (std::size_t old_color = 0; old_color < kColors; ++old_color) {
            candidate.deficit[permutation[old_color]] =
                state.deficit[old_color];
        }
        for (std::size_t index = 0; index < state.count; ++index) {
            candidate.sources[index] = state.sources[index];
            candidate.sources[index].top =
                permutation[state.sources[index].top];
            candidate.sources[index].next =
                permutation[state.sources[index].next];
        }
        std::sort(candidate.sources.begin(),
                  candidate.sources.begin() + candidate.count,
                  visible_source_less);
        if (!best.has_value() || visible_state_less(candidate, *best)) {
            best = candidate;
        }
    }
    return *best;
}

State project_visible(const VisibleState& visible) {
    State projected;
    projected.exhausted = visible.exhausted;
    for (std::size_t color = 0; color < kColors; ++color) {
        projected.colors[color].deficit = visible.deficit[color];
    }
    for (std::size_t index = 0; index < visible.count; ++index) {
        const auto& source = visible.sources[index];
        auto& bucket = projected.colors[source.top];
        bucket.exposed[bucket.count++] = source.exposed;
    }
    for (auto& bucket : projected.colors) normalize_bucket(bucket);
    return projected;
}

bool visible_consistent(const VisibleState& visible, std::uint32_t height) {
    if (visible.count + visible.exhausted != kOriginalColumns) return false;
    const auto projected = project_visible(visible);
    if (!algebraically_consistent(projected, height)) return false;

    const auto f = exposed_counts(projected);
    std::array<std::int32_t, kColors> residual{};
    for (std::size_t color = 0; color < kColors; ++color) {
        residual[color] = static_cast<std::int32_t>(height) - f[color];
    }
    std::array<std::uint8_t, kColors> residual_forbidden{};
    std::int32_t residual_slots = 0;
    for (std::size_t index = 0; index < visible.count; ++index) {
        const auto& source = visible.sources[index];
        if (source.top >= kColors || source.next >= kColors ||
            source.top == source.next || source.exposed == 0 ||
            source.exposed >= height || source.next_run == 0 ||
            source.next_run > height - source.exposed) {
            return false;
        }
        residual[source.next] -= source.next_run;
        if (residual[source.next] < 0) return false;
        const auto below = height - source.exposed - source.next_run;
        residual_slots += static_cast<std::int32_t>(below);
        if (below != 0) ++residual_forbidden[source.next];
    }
    const auto residual_items = std::accumulate(residual.begin(),
                                                residual.end(),
                                                std::int32_t{0});
    if (residual_items != residual_slots) return false;
    for (std::size_t color = 0; color < kColors; ++color) {
        if (static_cast<std::int32_t>(residual_forbidden[color]) >
            residual_items - residual[color]) {
            return false;
        }
    }
    return true;
}

std::uint32_t visible_remaining(const VisibleState& state,
                                std::uint32_t height) {
    std::uint32_t result = 0;
    for (std::size_t index = 0; index < state.count; ++index) {
        result += height - state.sources[index].exposed;
    }
    return result;
}

struct VisibleAction {
    VisibleSource source;
    std::uint8_t demand = 0;
};

std::vector<VisibleAction> visible_actions(const VisibleState& state) {
    std::vector<VisibleAction> result;
    const auto available = static_cast<std::uint8_t>(kEmptyColumns +
                                                      state.exhausted);
    for (std::size_t index = 0; index < state.count; ++index) {
        const auto& source = state.sources[index];
        if (index != 0 && source == state.sources[index - 1]) continue;
        std::uint8_t demand = 0;
        for (std::size_t color = 0; color < kColors; ++color) {
            auto value = state.deficit[color];
            if (color == source.top) value += source.exposed;
            if (value > 0) ++demand;
        }
        if (demand <= available) result.push_back({source, demand});
    }
    return result;
}

void remove_visible_source(VisibleState& state, const VisibleSource& source) {
    const auto end = state.sources.begin() + state.count;
    const auto found = std::find(state.sources.begin(), end, source);
    if (found == end) throw std::logic_error("visible source is absent");
    std::move(found + 1, end, found);
    --state.count;
    state.sources[state.count] = {};
}

struct VisibleOutcome {
    bool goal = false;
    std::uint8_t new_next = 0;
    std::uint16_t new_run = 0;
    VisibleState successor;
};

std::vector<VisibleOutcome> visible_outcomes(const VisibleState& state,
                                             const VisibleAction& action,
                                             std::uint32_t height) {
    VisibleState base = state;
    remove_visible_source(base, action.source);
    const auto hidden = height - action.source.exposed;
    if (action.source.next_run == hidden) {
        base.deficit[action.source.top] += action.source.exposed;
        base.deficit[action.source.next] += action.source.next_run;
        ++base.exhausted;
        base = canonicalize_visible(base);
        if (!visible_consistent(base, height)) {
            throw std::logic_error("committed exhausting run became infeasible");
        }
        return {{base.exhausted >= kTargetExhausted, 0, 0, base}};
    }

    base.deficit[action.source.top] += action.source.exposed;
    base.deficit[action.source.next] -= action.source.exposed;
    VisibleSource replacement;
    replacement.top = action.source.next;
    replacement.exposed = static_cast<std::uint16_t>(
        action.source.exposed + action.source.next_run);

    std::vector<VisibleOutcome> result;
    const auto remaining = height - replacement.exposed;
    for (std::uint8_t next = 0; next < kColors; ++next) {
        if (next == replacement.top) continue;
        replacement.next = next;
        for (std::uint16_t run = 1; run <= remaining; ++run) {
            replacement.next_run = run;
            VisibleState successor = base;
            successor.sources[successor.count++] = replacement;
            successor = canonicalize_visible(successor);
            if (!visible_consistent(successor, height)) continue;
            const auto duplicate = std::find_if(
                result.begin(), result.end(),
                [&](const VisibleOutcome& prior) {
                    return prior.successor == successor;
                });
            if (duplicate == result.end()) {
                result.push_back({false, next, run, std::move(successor)});
            }
        }
    }
    if (result.empty()) {
        throw std::logic_error("visible state has no feasible third run");
    }
    return result;
}

struct VisibleInitials {
    std::vector<VisibleState> states;
    std::unordered_map<VisibleState, std::size_t, VisibleStateHash> index;
    std::uint64_t candidates = 0;
};

void enumerate_visible_assignments(
    VisibleState& state, std::size_t index,
    const std::array<std::int32_t, kColors>& remaining,
    std::array<std::int32_t, kColors>& used,
    VisibleInitials& initials, const Options& options) {
    if (index == state.count) {
        ++initials.candidates;
        if (initials.candidates > options.max_candidates) {
            throw std::runtime_error(
                "next-run initial candidate limit exceeded; raise "
                "--max-candidates explicitly");
        }
        if (!visible_consistent(state, options.height)) return;
        auto canonical = canonicalize_visible(state);
        if (initials.index.find(canonical) != initials.index.end()) return;
        if (initials.states.size() >= options.max_states) {
            throw std::runtime_error(
                "next-run initial state limit exceeded; raise --max-states");
        }
        const auto id = initials.states.size();
        initials.states.push_back(canonical);
        initials.index.emplace(std::move(canonical), id);
        return;
    }

    auto& source = state.sources[index];
    const auto hidden = options.height - source.exposed;
    for (std::uint8_t next = 0; next < kColors; ++next) {
        if (next == source.top) continue;
        source.next = next;
        for (std::uint16_t run = 1; run <= hidden; ++run) {
            if (used[next] + run > remaining[next]) continue;
            source.next_run = run;
            used[next] += run;
            enumerate_visible_assignments(state, index + 1, remaining, used,
                                          initials, options);
            used[next] -= run;
        }
    }
    source.next = 0;
    source.next_run = 0;
}

VisibleInitials enumerate_visible_initials(const Enumeration& enumeration,
                                           const Options& options) {
    VisibleInitials initials;
    initials.states.reserve(std::min<std::size_t>(
        static_cast<std::size_t>(options.max_states), 250'000));
    initials.index.reserve(initials.states.capacity());
    for (const auto& projected : enumeration.states) {
        if (!is_initial_projection(projected, options.height)) continue;
        VisibleState state;
        state.exhausted = projected.exhausted;
        for (std::size_t color = 0; color < kColors; ++color) {
            state.deficit[color] = projected.colors[color].deficit;
            for (std::size_t source = 0;
                 source < projected.colors[color].count; ++source) {
                state.sources[state.count++] = {
                    static_cast<std::uint8_t>(color),
                    projected.colors[color].exposed[source], 0, 0};
            }
        }
        const auto f = exposed_counts(projected);
        std::array<std::int32_t, kColors> remaining{};
        for (std::size_t color = 0; color < kColors; ++color) {
            remaining[color] = static_cast<std::int32_t>(options.height) -
                               f[color];
        }
        std::array<std::int32_t, kColors> used{};
        enumerate_visible_assignments(state, 0, remaining, used, initials,
                                      options);
    }
    return initials;
}

struct VisibleNode {
    // 1=visiting, 2=winning, 3=losing.
    std::uint8_t status = 0;
    std::uint32_t rank = 0;
};

struct VisibleSearch {
    std::unordered_map<VisibleState, VisibleNode, VisibleStateHash> nodes;
    std::uint64_t legal_actions = 0;
    std::uint64_t environment_edges = 0;
    std::uint64_t safe_actions = 0;
    std::uint64_t dead_ends = 0;
};

bool solve_visible(const VisibleState& state, VisibleSearch& search,
                   const Options& options) {
    const auto known = search.nodes.find(state);
    if (known != search.nodes.end()) {
        if (known->second.status == 1) {
            throw std::logic_error("cycle in descending next-run game");
        }
        return known->second.status == 2;
    }
    if (search.nodes.size() >= options.max_states) {
        throw std::runtime_error(
            "next-run reachable state limit exceeded; raise --max-states");
    }
    search.nodes.emplace(state, VisibleNode{1, 0});

    const auto actions = visible_actions(state);
    search.legal_actions += actions.size();
    if (actions.empty()) ++search.dead_ends;
    bool winning = false;
    auto best_rank = std::numeric_limits<std::uint32_t>::max();
    for (const auto& action : actions) {
        const auto next = visible_outcomes(state, action, options.height);
        search.environment_edges += next.size();
        bool safe = true;
        std::uint32_t worst_rank = 0;
        for (const auto& outcome : next) {
            if (outcome.goal) continue;
            if (visible_remaining(outcome.successor, options.height) >=
                visible_remaining(state, options.height)) {
                throw std::logic_error("next-run transition is not descending");
            }
            const auto child_winning = solve_visible(outcome.successor, search,
                                                     options);
            safe = safe && child_winning;
            const auto child = search.nodes.find(outcome.successor);
            if (child == search.nodes.end()) {
                throw std::logic_error("solved next-run child disappeared");
            }
            worst_rank = std::max(worst_rank, child->second.rank);
        }
        if (safe) {
            ++search.safe_actions;
            winning = true;
            best_rank = std::min(best_rank, worst_rank + 1U);
        }
    }
    auto finished = search.nodes.find(state);
    if (finished == search.nodes.end()) {
        throw std::logic_error("next-run parent disappeared");
    }
    finished->second.status = winning ? 2U : 3U;
    finished->second.rank = winning ? best_rank : 0U;
    return winning;
}

std::string visible_state_text(const VisibleState& state,
                               std::uint32_t height) {
    std::ostringstream output;
    output << "z=" << static_cast<unsigned>(state.exhausted)
           << " A=" << (kEmptyColumns + state.exhausted)
           << " remaining=" << visible_remaining(state, height) << " d=[";
    for (std::size_t color = 0; color < kColors; ++color) {
        if (color != 0) output << ',';
        output << state.deficit[color];
    }
    output << "]\n";
    for (std::size_t index = 0; index < state.count; ++index) {
        const auto& source = state.sources[index];
        output << "  source" << index << ": top=c"
               << static_cast<unsigned>(source.top) << " s=" << source.exposed
               << " next=c" << static_cast<unsigned>(source.next)
               << " run=" << source.next_run << '\n';
    }
    return output.str();
}

std::optional<VisibleState> minimum_losing_visible(
    const std::vector<VisibleState>& candidates, const VisibleSearch& search,
    std::uint32_t height) {
    std::optional<VisibleState> best;
    for (const auto& state : candidates) {
        const auto found = search.nodes.find(state);
        if (found == search.nodes.end() || found->second.status != 3) continue;
        if (!best.has_value() ||
            std::make_tuple(visible_remaining(state, height),
                            visible_actions(state).size()) <
                std::make_tuple(visible_remaining(*best, height),
                                visible_actions(*best).size()) ||
            (std::make_tuple(visible_remaining(state, height),
                             visible_actions(state).size()) ==
                 std::make_tuple(visible_remaining(*best, height),
                                 visible_actions(*best).size()) &&
             visible_state_less(state, *best))) {
            best = state;
        }
    }
    return best;
}

void write_visible_results(const Options& options,
                           const Enumeration& enumeration,
                           const VisibleInitials& initials,
                           const VisibleSearch& search,
                           const std::optional<VisibleState>& losing_initial) {
    std::uint64_t winning_states = 0;
    std::uint64_t winning_initial = 0;
    std::uint32_t maximum_rank = 0;
    for (const auto& entry : search.nodes) {
        winning_states += entry.second.status == 2 ? 1U : 0U;
        maximum_rank = std::max(maximum_rank, entry.second.rank);
    }
    for (const auto& state : initials.states) {
        const auto found = search.nodes.find(state);
        if (found != search.nodes.end() && found->second.status == 2) {
            ++winning_initial;
        }
    }

    ensure_parent(options.witness);
    std::ofstream witness(options.witness);
    if (!witness) throw std::runtime_error("cannot write next-run witness");
    witness << "FINITE TOP-TWO-RUN ONLINE COUNTER-GAME\nheight="
            << options.height << "\n\nWARNING\n"
            << "A losing observation refutes only an online controller that "
               "sees Q plus every current next run. The environment commits "
               "those runs before source choice and chooses only the newly "
               "exposed third run afterwards. This is not automatically a "
               "Water Sort NO instance.\n\n";
    if (!losing_initial.has_value()) {
        witness << "No losing initial top-two-run observation at this finite "
                   "height.\n";
    } else {
        witness << "Minimum losing initial top-two-run observation:\n"
                << visible_state_text(*losing_initial, options.height)
                << "For every legal source orbit, one losing third-run reply "
                   "is:\n";
        for (const auto& action : visible_actions(*losing_initial)) {
            const auto next = visible_outcomes(*losing_initial, action,
                                               options.height);
            const VisibleOutcome* reply = nullptr;
            for (const auto& outcome : next) {
                if (outcome.goal) continue;
                const auto found = search.nodes.find(outcome.successor);
                if (found != search.nodes.end() && found->second.status == 3) {
                    reply = &outcome;
                    break;
                }
            }
            if (reply == nullptr) {
                throw std::logic_error("losing next-run action lacks reply");
            }
            witness << "  choose(top=c"
                    << static_cast<unsigned>(action.source.top)
                    << ",s=" << action.source.exposed << ",next=c"
                    << static_cast<unsigned>(action.source.next)
                    << ",run=" << action.source.next_run << ",N="
                    << static_cast<unsigned>(action.demand)
                    << ") -> new next=c"
                    << static_cast<unsigned>(reply->new_next)
                    << ",run=" << reply->new_run << '\n';
        }
    }

    ensure_parent(options.report);
    std::ofstream report(options.report);
    if (!report) throw std::runtime_error("cannot write next-run report");
    report << "{\n"
           << "  \"schema\": \"water-sort-counter-game-v1\",\n"
           << "  \"scope\": \"finite-height online Q plus committed "
              "next-run game\",\n"
           << "  \"observation\": \"next-run\",\n"
           << "  \"height\": " << options.height << ",\n"
           << "  \"max_states\": " << options.max_states << ",\n"
           << "  \"max_candidates\": " << options.max_candidates << ",\n"
           << "  \"base_consistent_q_states\": "
           << enumeration.states.size() << ",\n"
           << "  \"initial_assignment_candidates\": "
           << initials.candidates << ",\n"
           << "  \"initial_observations\": " << initials.states.size()
           << ",\n"
           << "  \"reachable_observations\": " << search.nodes.size()
           << ",\n"
           << "  \"winning_reachable_observations\": " << winning_states
           << ",\n"
           << "  \"losing_reachable_observations\": "
           << (search.nodes.size() - winning_states) << ",\n"
           << "  \"winning_initial_observations\": " << winning_initial
           << ",\n"
           << "  \"losing_initial_observations\": "
           << (initials.states.size() - winning_initial) << ",\n"
           << "  \"all_initial_observations_winning\": "
           << (initials.states.size() == winning_initial ? "true" : "false")
           << ",\n"
           << "  \"legal_action_orbits\": " << search.legal_actions
           << ",\n"
           << "  \"safe_action_orbits\": " << search.safe_actions << ",\n"
           << "  \"environment_edges\": " << search.environment_edges
           << ",\n"
           << "  \"dead_end_observations\": " << search.dead_ends << ",\n"
           << "  \"maximum_winning_rank\": " << maximum_rank << ",\n"
           << "  \"enumeration_complete\": true,\n"
           << "  \"finite_result_only\": true,\n"
           << "  \"caveat\": \"A loss refutes the top-two-run online "
              "observation policy, not universal Water Sort solvability.\"\n"
           << "}\n";

    std::cout << "height=" << options.height << " observation=next-run"
              << " initial=" << initials.states.size()
              << " initial_winning=" << winning_initial
              << " reachable=" << search.nodes.size()
              << " winning=" << winning_states << '\n'
              << "report=" << options.report.string() << '\n'
              << "witness=" << options.witness.string() << '\n';
}

std::string state_text(const State& state, std::uint32_t height) {
    std::ostringstream output;
    output << "z=" << static_cast<unsigned>(state.exhausted)
           << " A=" << (kEmptyColumns + state.exhausted)
           << " remaining=" << remaining_items(state, height) << '\n';
    const auto f = exposed_counts(state);
    for (std::size_t color = 0; color < kColors; ++color) {
        const auto& bucket = state.colors[color];
        output << "  c" << color << ": d=" << bucket.deficit
               << " F=" << f[color] << " active_s=[";
        for (std::size_t index = 0; index < bucket.count; ++index) {
            if (index != 0) output << ',';
            output << bucket.exposed[index];
        }
        output << "]\n";
    }
    return output.str();
}

std::optional<std::size_t> minimum_losing(
    const Enumeration& enumeration, const Solution& solution,
    std::uint32_t height, bool initial_only) {
    std::optional<std::size_t> best;
    for (std::size_t id = 0; id < enumeration.states.size(); ++id) {
        if (solution.winning[id] != 0) continue;
        if (initial_only &&
            !is_initial_projection(enumeration.states[id], height)) {
            continue;
        }
        if (!best.has_value()) {
            best = id;
            continue;
        }
        const auto& candidate = enumeration.states[id];
        const auto& incumbent = enumeration.states[*best];
        const auto candidate_key = std::make_tuple(
            remaining_items(candidate, height),
            legal_actions(candidate).size());
        const auto incumbent_key = std::make_tuple(
            remaining_items(incumbent, height),
            legal_actions(incumbent).size());
        if (candidate_key < incumbent_key ||
            (candidate_key == incumbent_key &&
             state_less(candidate, incumbent))) {
            best = id;
        }
    }
    return best;
}

void ensure_parent(const std::filesystem::path& path) {
    if (!path.has_parent_path()) return;
    std::error_code error;
    std::filesystem::create_directories(path.parent_path(), error);
    if (error) {
        throw std::runtime_error("cannot create output directory: " +
                                 error.message());
    }
}

void write_witness(const Options& options, const Enumeration& enumeration,
                   const Solution& solution,
                   const std::optional<std::size_t>& losing,
                   const std::optional<std::size_t>& losing_initial) {
    ensure_parent(options.witness);
    std::ofstream output(options.witness);
    if (!output) throw std::runtime_error("cannot write witness file");
    output << "FINITE FOUR-COLOR / TWO-EMPTY ONLINE COUNTER-GAME\n"
           << "height=" << options.height << "\n\n"
           << "WARNING\n"
           << "A losing Q refutes only a strategy that observes Q and learns a "
              "hidden run after choosing its source.  It is not, by itself, "
              "an unsolvable Water Sort instance.\n\n";

    if (!losing.has_value()) {
        output << "No losing algebraically consistent Q exists at this height.\n";
        return;
    }

    const auto emit = [&](std::size_t id, const std::string& title) {
        const auto& state = enumeration.states[id];
        output << title << "\n" << state_text(state, options.height);
        const auto actions = legal_actions(state);
        if (actions.empty()) {
            output << "  obstruction: no legal source (every N_i > A)\n";
            for (std::size_t color = 0; color < kColors; ++color) {
                const auto& bucket = state.colors[color];
                for (std::size_t index = 0; index < bucket.count; ++index) {
                    const auto demand = source_demand(state,
                                                      static_cast<std::uint8_t>(color),
                                                      bucket.exposed[index]);
                    output << "    source(c" << color << ",s="
                           << bucket.exposed[index] << "): N="
                           << static_cast<unsigned>(demand) << '\n';
                }
            }
        } else {
            output << "  every legal action has a losing environment reply:\n";
            for (const auto& action : actions) {
                const auto next = outcomes(state, action, options.height);
                const Outcome* reply = nullptr;
                for (const auto& outcome : next) {
                    if (outcome.goal) continue;
                    const auto found = enumeration.index.find(outcome.successor);
                    if (found != enumeration.index.end() &&
                        solution.winning[found->second] == 0) {
                        reply = &outcome;
                        break;
                    }
                }
                if (reply == nullptr) {
                    throw std::logic_error("losing state has an unrefuted action");
                }
                output << "    choose(c" << static_cast<unsigned>(action.color)
                       << ",s=" << action.exposed << ",N="
                       << static_cast<unsigned>(action.demand) << ") -> reveal(c"
                       << static_cast<unsigned>(reply->revealed_color)
                       << ",r=" << reply->run_length << ")\n";
                std::istringstream successor_text(
                    state_text(reply->successor, options.height));
                std::string line;
                while (std::getline(successor_text, line)) {
                    output << "      " << line << '\n';
                }
            }
        }
        output << '\n';
    };

    emit(*losing,
         "Minimum losing consistent Q (ordered by remaining items, action "
         "orbits, canonical key):");
    if (losing_initial.has_value() && losing_initial != losing) {
        emit(*losing_initial, "Minimum losing initial projection:");
    } else if (!losing_initial.has_value()) {
        output << "No initial projection is losing at this finite height.\n";
    }
}

void write_report(const Options& options, const Enumeration& enumeration,
                  const Solution& solution,
                  const std::optional<std::size_t>& losing,
                  const std::optional<std::size_t>& losing_initial) {
    std::uint64_t winning = 0;
    std::uint64_t initial = 0;
    std::uint64_t initial_winning = 0;
    std::uint32_t maximum_rank = 0;
    for (std::size_t id = 0; id < enumeration.states.size(); ++id) {
        winning += solution.winning[id] != 0 ? 1U : 0U;
        maximum_rank = std::max(maximum_rank, solution.rank[id]);
        if (is_initial_projection(enumeration.states[id], options.height)) {
            ++initial;
            initial_winning += solution.winning[id] != 0 ? 1U : 0U;
        }
    }

    ensure_parent(options.report);
    std::ofstream output(options.report);
    if (!output) throw std::runtime_error("cannot write report file");
    output << "{\n"
           << "  \"schema\": \"water-sort-counter-game-v1\",\n"
           << "  \"scope\": \"finite-height online Q-observation game\",\n"
           << "  \"observation\": \"" << observation_name(options.observation)
           << "\",\n"
           << "  \"height\": " << options.height << ",\n"
           << "  \"colors\": " << kColors << ",\n"
           << "  \"original_columns\": " << kOriginalColumns << ",\n"
           << "  \"empty_columns\": " << kEmptyColumns << ",\n"
           << "  \"target_exhausted\": " << kTargetExhausted << ",\n"
           << "  \"max_states\": " << options.max_states << ",\n"
           << "  \"max_candidates\": " << options.max_candidates << ",\n"
           << "  \"enumeration_complete\": true,\n"
           << "  \"symmetry\": \"unlabeled original columns and color "
              "permutations\",\n"
           << "  \"constraints\": [\n"
           << "    \"active count plus z equals four\",\n"
           << "    \"1 <= s_i < h for every active source\",\n"
           << "    \"F_c = d_c + sum[a_i=c] s_i lies between the active "
              "top count and h\",\n"
           << "    \"sum_c d_c = z*h\",\n"
           << "    \"each hidden suffix is nonempty and starts in a color "
              "different from a_i (Hall inequalities)\"\n"
           << "  ],\n"
           << "  \"candidates_examined\": " << enumeration.candidates << ",\n"
           << "  \"consistent_states\": " << enumeration.states.size()
           << ",\n"
           << "  \"winning_states\": " << winning << ",\n"
           << "  \"losing_states\": "
           << (enumeration.states.size() - winning) << ",\n"
           << "  \"initial_states\": " << initial << ",\n"
           << "  \"winning_initial_states\": " << initial_winning << ",\n"
           << "  \"losing_initial_states\": " << (initial - initial_winning)
           << ",\n"
           << "  \"all_initial_states_winning\": "
           << (initial == initial_winning ? "true" : "false") << ",\n"
           << "  \"legal_action_orbits\": " << solution.legal_action_orbits
           << ",\n"
           << "  \"safe_action_orbits\": " << solution.safe_action_orbits
           << ",\n"
           << "  \"environment_edges\": " << solution.environment_edges
           << ",\n"
           << "  \"dead_end_states\": " << solution.dead_ends << ",\n"
           << "  \"maximum_winning_rank\": " << maximum_rank << ",\n"
           << "  \"minimum_losing_state_id\": ";
    if (losing.has_value()) output << *losing;
    else output << "null";
    output << ",\n  \"minimum_losing_initial_state_id\": ";
    if (losing_initial.has_value()) output << *losing_initial;
    else output << "null";
    output << ",\n"
           << "  \"finite_result_only\": true,\n"
           << "  \"caveat\": \"Winning all initial Q at this H is not an "
              "arbitrary-height proof. Losing Q only refutes a Q-only online "
              "policy and is not automatically a Water Sort NO instance.\"\n"
           << "}\n";

    std::cout << "height=" << options.height
              << " states=" << enumeration.states.size()
              << " winning=" << winning
              << " losing=" << (enumeration.states.size() - winning)
              << " initial=" << initial
              << " initial_winning=" << initial_winning
              << " candidates=" << enumeration.candidates << '\n'
              << "report=" << options.report.string() << '\n'
              << "witness=" << options.witness.string() << '\n';
}

Options parse_options(int argc, char** argv) {
    Options options;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        const auto value = [&]() -> std::string {
            if (++index >= argc) {
                throw std::invalid_argument("missing value after " + argument);
            }
            return argv[index];
        };
        if (argument == "--height") {
            options.height = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--report") {
            options.report = value();
        } else if (argument == "--witness") {
            options.witness = value();
        } else if (argument == "--max-states") {
            options.max_states = std::stoull(value());
        } else if (argument == "--max-candidates") {
            options.max_candidates = std::stoull(value());
        } else if (argument == "--observation") {
            const auto mode = value();
            if (mode == "q") options.observation = ObservationMode::q_only;
            else if (mode == "next-run") {
                options.observation = ObservationMode::next_run;
            } else {
                throw std::invalid_argument(
                    "--observation must be q or next-run");
            }
        } else if (argument == "--self-test") {
            options.self_test = true;
        } else if (argument == "--help") {
            std::cout
                << "usage: water-counter-game --height H [--report FILE] "
                   "[--witness FILE] [--max-states N] "
                   "[--max-candidates N] [--observation q|next-run] "
                   "[--self-test]\n";
            std::exit(0);
        } else {
            throw std::invalid_argument("unknown argument: " + argument);
        }
    }
    if (options.height < 2) {
        throw std::invalid_argument("--height H with H >= 2 is required");
    }
    if (options.height > std::numeric_limits<std::uint16_t>::max()) {
        throw std::invalid_argument("height exceeds the counter encoding");
    }
    if (options.max_states == 0 || options.max_candidates == 0) {
        throw std::invalid_argument("enumeration limits must be positive");
    }
    return options;
}

void self_test(std::uint32_t height) {
    State state;
    state.exhausted = 0;
    for (std::size_t color = 0; color < kColors; ++color) {
        state.colors[color].count = 1;
        state.colors[color].exposed[0] = 1;
    }
    state = canonicalize(state);
    if (!algebraically_consistent(state, height)) {
        throw std::logic_error("self-test initial Q should be consistent");
    }
    if (!is_initial_projection(state, height)) {
        throw std::logic_error("self-test initial Q was not recognized");
    }
    for (const auto& action : legal_actions(state)) {
        const auto next = outcomes(state, action, height);
        for (const auto& outcome : next) {
            if (!outcome.goal &&
                remaining_items(outcome.successor, height) >=
                    remaining_items(state, height)) {
                throw std::logic_error("self-test found non-descending outcome");
            }
        }
    }

    VisibleState visible;
    for (std::uint8_t color = 0; color < kColors; ++color) {
        visible.sources[visible.count++] = {
            color, 1, static_cast<std::uint8_t>((color + 1U) % kColors),
            static_cast<std::uint16_t>(height - 1U)};
    }
    visible = canonicalize_visible(visible);
    if (!visible_consistent(visible, height)) {
        throw std::logic_error("self-test visible initial state is inconsistent");
    }
    const auto first_actions = visible_actions(visible);
    if (first_actions.empty()) {
        throw std::logic_error("self-test visible initial state has no action");
    }
    const auto first_outcomes = visible_outcomes(visible, first_actions.front(),
                                                 height);
    if (first_outcomes.size() != 1 || first_outcomes.front().goal ||
        first_outcomes.front().successor.exhausted != 1) {
        throw std::logic_error(
            "first exhausted source was incorrectly treated as the z=2 goal");
    }
    const auto second_actions = visible_actions(first_outcomes.front().successor);
    if (second_actions.empty()) {
        throw std::logic_error("self-test z=1 visible state has no action");
    }
    const auto second_outcomes = visible_outcomes(
        first_outcomes.front().successor, second_actions.front(), height);
    if (second_outcomes.size() != 1 || !second_outcomes.front().goal ||
        second_outcomes.front().successor.exhausted != kTargetExhausted) {
        throw std::logic_error("second exhausted source did not reach z=2");
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const auto options = parse_options(argc, argv);
        if (options.self_test) self_test(options.height);
        auto enumeration = enumerate_states(options);
        if (options.observation == ObservationMode::next_run) {
            const auto initials = enumerate_visible_initials(enumeration,
                                                              options);
            VisibleSearch search;
            search.nodes.reserve(std::min<std::size_t>(
                static_cast<std::size_t>(options.max_states), 1'000'000));
            for (const auto& state : initials.states) {
                solve_visible(state, search, options);
            }
            const auto losing_initial = minimum_losing_visible(
                initials.states, search, options.height);
            write_visible_results(options, enumeration, initials, search,
                                  losing_initial);
            return 0;
        }
        const auto solution = retrograde(enumeration, options);
        const auto losing = minimum_losing(enumeration, solution,
                                           options.height, false);
        const auto losing_initial = minimum_losing(enumeration, solution,
                                                   options.height, true);
        write_witness(options, enumeration, solution, losing, losing_initial);
        write_report(options, enumeration, solution, losing, losing_initial);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
