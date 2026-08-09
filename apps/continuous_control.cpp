#include "water_sort/border_oracle.hpp"
#include "water_sort/instance.hpp"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

using Column = std::vector<water_sort::Color>;
using PhysicalState = std::vector<Column>;

struct Options {
    std::filesystem::path catalog;
    std::vector<std::filesystem::path> policies;
    std::filesystem::path out = "out";
    std::uint32_t goal_exhausted_columns = 2;
    std::uint32_t visible_boundaries = 3;
    std::uint32_t shard = 0;
    std::uint32_t shards = 1;
    std::uint32_t max_instances = 0;
    std::uint64_t max_bulk_moves = 0;
};

struct CatalogEntry {
    std::size_t index = 0;
    std::string encoding;
    water_sort::Instance instance;
};

struct Controller {
    std::string id;
    std::filesystem::path path;
    std::unordered_map<std::string, std::uint8_t> exceptions;
};

struct Observation {
    std::string signature;
    std::uint64_t action_columns = 0;
    std::vector<std::size_t> original_columns;
};

struct MoveRecord {
    std::size_t source = 0;
    std::size_t target = 0;
    std::size_t quantity = 0;
    water_sort::Color color = 0;
    std::string phase;
};

struct SimulationResult {
    bool success = false;
    std::string reason;
    std::string detail;
    std::uint64_t macro_steps = 0;
    std::uint64_t bulk_moves = 0;
    std::uint32_t state_id = 0;
    std::size_t source = std::numeric_limits<std::size_t>::max();
    std::string macro_signature;
    PhysicalState physical;
    std::vector<std::uint32_t> ranks;
    std::vector<MoveRecord> trace;
};

struct Gap : std::runtime_error {
    std::string reason;

    Gap(std::string reason_value, std::string detail)
        : std::runtime_error(std::move(detail)), reason(std::move(reason_value)) {}
};

std::vector<std::string> split(const std::string& value, char delimiter) {
    std::vector<std::string> result;
    std::stringstream input(value);
    std::string field;
    while (std::getline(input, field, delimiter)) result.push_back(field);
    return result;
}

std::string trim_cr(std::string value) {
    if (!value.empty() && value.back() == '\r') value.pop_back();
    return value;
}

water_sort::Instance parse_compact_instance(const std::string& encoding) {
    const auto fields = split(encoding, ';');
    if (fields.size() != 4 || fields[0].rfind("h=", 0) != 0 ||
        fields[1].rfind("c=", 0) != 0 || fields[2].rfind("k=", 0) != 0 ||
        fields[3].rfind("cols=", 0) != 0) {
        throw std::runtime_error("invalid compact instance: " + encoding);
    }

    water_sort::Instance instance;
    instance.height = static_cast<std::uint32_t>(std::stoul(fields[0].substr(2)));
    instance.color_count = static_cast<std::uint32_t>(std::stoul(fields[1].substr(2)));
    instance.empty_columns = static_cast<std::uint32_t>(std::stoul(fields[2].substr(2)));
    for (auto raw_column : split(fields[3].substr(5), '/')) {
        raw_column = trim_cr(std::move(raw_column));
        auto& column = instance.columns.emplace_back();
        for (const auto value : raw_column) {
            column.push_back(water_sort::char_to_color(value));
        }
    }
    instance.validate();
    return instance;
}

std::vector<CatalogEntry> read_catalog(const Options& options) {
    std::ifstream input(options.catalog);
    if (!input) throw std::runtime_error("cannot open instance catalog: " + options.catalog.string());

    std::string line;
    if (!std::getline(input, line)) throw std::runtime_error("empty instance catalog");
    std::vector<CatalogEntry> entries;
    std::size_t index = 0;
    while (std::getline(input, line)) {
        const auto tab = line.find('\t');
        if (tab == std::string::npos) throw std::runtime_error("invalid catalog row");
        auto encoding = trim_cr(line.substr(tab + 1));
        if (index % options.shards == options.shard) {
            entries.push_back({index, encoding, parse_compact_instance(encoding)});
        }
        ++index;
        if (options.max_instances != 0 && index >= options.max_instances) break;
    }
    if (entries.empty()) throw std::runtime_error("catalog shard is empty");
    return entries;
}

Controller read_policy(const std::filesystem::path& path, std::size_t id) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("cannot open compressed policy: " + path.string());
    std::string line;
    if (!std::getline(input, line) ||
        (line != "action\tdomain\tsignature" &&
         line != "action\tdomain\tsignature\r")) {
        throw std::runtime_error("invalid compressed policy header: " + path.string());
    }

    Controller result;
    result.id = "p" + std::to_string(id);
    result.path = path;
    while (std::getline(input, line)) {
        const auto fields = split(line, '\t');
        if (fields.size() != 3) throw std::runtime_error("invalid compressed policy row");
        auto signature = trim_cr(fields[2]);
        const auto action = static_cast<std::uint32_t>(std::stoul(fields[0]));
        if (action >= 64) throw std::runtime_error("compressed action is out of range");
        const auto domain = std::stoull(fields[1], nullptr, 16);
        if ((domain & (std::uint64_t{1} << action)) == 0) {
            throw std::runtime_error("compressed action is outside its policy domain");
        }
        if (!result.exceptions.emplace(std::move(signature),
                                       static_cast<std::uint8_t>(action)).second) {
            throw std::runtime_error("compressed policy repeats a signature");
        }
    }
    return result;
}

Options parse_options(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        const auto value = [&]() -> std::string {
            if (i + 1 >= argc) throw std::runtime_error("missing value for " + argument);
            return argv[++i];
        };
        if (argument == "--catalog") options.catalog = value();
        else if (argument == "--policy") options.policies.emplace_back(value());
        else if (argument == "--out") options.out = value();
        else if (argument == "--goal-exhausted") {
            options.goal_exhausted_columns = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--visible-boundaries") {
            options.visible_boundaries = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--shard") {
            options.shard = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--shards") {
            options.shards = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--max-instances") {
            options.max_instances = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--max-bulk-moves") {
            options.max_bulk_moves = std::stoull(value());
        } else if (argument == "--help") {
            std::cout
                << "water-continuous-control --catalog FILE --policy FILE [--policy FILE] "
                   "[--goal-exhausted N] [--visible-boundaries N] "
                   "[--shard I --shards N] [--max-instances N] "
                   "[--max-bulk-moves N] [--out DIR]\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown argument: " + argument);
        }
    }
    if (options.catalog.empty() || options.policies.empty() ||
        options.goal_exhausted_columns == 0 || options.visible_boundaries == 0 ||
        options.shards == 0 || options.shard >= options.shards) {
        throw std::runtime_error("invalid continuous-control options");
    }
    return options;
}

Observation canonical_observation(const water_sort::PolicyStateView& state,
                                  std::uint64_t action_columns,
                                  std::uint32_t colors,
                                  std::uint32_t empty_columns) {
    std::vector<std::uint32_t> color_map(colors);
    std::iota(color_map.begin(), color_map.end(), 0U);
    Observation best;
    bool have_best = false;
    const auto need_cap = colors + empty_columns + 1U;
    do {
        std::ostringstream prefix;
        prefix << "a" << state.available_buffers << "|c";
        for (std::uint32_t canonical = 0; canonical < colors; ++canonical) {
            std::uint32_t original = 0;
            while (color_map[original] != canonical) ++original;
            prefix << (state.f[original] > state.g[original] ? 'd' : '-')
                   << (state.g[original] > 0 ? 'h' : '-');
        }
        prefix << '|';

        std::vector<std::pair<std::string, std::size_t>> columns;
        for (std::size_t column = 0; column < state.columns.size(); ++column) {
            const auto& view = state.columns[column];
            std::ostringstream descriptor;
            descriptor << (view.remaining_borders == 0 ? 'm' : 'b') << ':';
            for (const auto color : view.visible_runs) {
                descriptor << water_sort::color_to_char(
                    static_cast<water_sort::Color>(color_map[color]));
            }
            descriptor << (view.truncated ? '+' : '.') << ':';
            if (view.remaining_borders == 0) descriptor << 'x';
            else descriptor << std::min(view.buffers_needed, need_cap);
            columns.emplace_back(descriptor.str(), column);
        }
        std::stable_sort(columns.begin(), columns.end(),
                         [](const auto& left, const auto& right) {
                             return left.first < right.first;
                         });

        auto signature = prefix.str();
        std::uint64_t transformed = 0;
        std::vector<std::size_t> originals;
        for (std::size_t position = 0; position < columns.size(); ++position) {
            if (position != 0) signature.push_back('/');
            signature += columns[position].first;
            originals.push_back(columns[position].second);
            if ((action_columns & (std::uint64_t{1} << columns[position].second)) != 0) {
                transformed |= std::uint64_t{1} << position;
            }
        }
        if (!have_best || signature < best.signature) {
            best = {std::move(signature), transformed, std::move(originals)};
            have_best = true;
        }
    } while (std::next_permutation(color_map.begin(), color_map.end()));
    return best;
}

std::uint8_t choose_controller_action(const Controller& controller,
                                      const Observation& legal_observation) {
    const auto exception = controller.exceptions.find(legal_observation.signature);
    if (exception != controller.exceptions.end()) return exception->second;
    std::uint8_t action = 0;
    bool found = false;
    for (std::uint8_t position = 0;
         position < legal_observation.original_columns.size(); ++position) {
        if ((legal_observation.action_columns & (std::uint64_t{1} << position)) != 0) {
            action = position;
            found = true;
        }
    }
    if (!found) throw Gap("no_legal_macro_action", "macro observation has no legal source");
    return action;
}

std::vector<std::vector<std::uint32_t>> original_borders(
    const water_sort::Instance& instance) {
    std::vector<std::vector<std::uint32_t>> result(instance.columns.size());
    for (std::size_t column = 0; column < instance.columns.size(); ++column) {
        result[column].push_back(0);
        for (std::uint32_t position = 1; position < instance.height; ++position) {
            if (instance.columns[column][position - 1] !=
                instance.columns[column][position]) {
                result[column].push_back(position);
            }
        }
    }
    return result;
}

bool is_monochrome(const Column& column) {
    return column.empty() || std::all_of(column.begin(), column.end(),
                                         [&](water_sort::Color color) {
                                             return color == column.front();
                                         });
}

bool is_locked(const Column& column, std::uint32_t height) {
    return column.size() == height && is_monochrome(column);
}

std::uint32_t top_border(const Column& column) {
    for (std::size_t position = column.size(); position > 1; --position) {
        if (column[position - 1] != column[position - 2]) {
            return static_cast<std::uint32_t>(position - 1);
        }
    }
    return 0;
}

std::uint32_t ceil_div(std::uint32_t numerator, std::uint32_t denominator) {
    return numerator == 0 ? 0 : 1U + (numerator - 1U) / denominator;
}

std::vector<std::uint32_t> demands(const water_sort::PolicyStateView& view,
                                   std::uint32_t height) {
    std::vector<std::uint32_t> result(view.f.size(), 0);
    for (std::size_t color = 0; color < result.size(); ++color) {
        if (view.f[color] > view.g[color]) {
            result[color] = ceil_div(view.f[color] - view.g[color], height);
        }
    }
    return result;
}

std::string compact_state(const PhysicalState& state) {
    std::ostringstream output;
    for (std::size_t column = 0; column < state.size(); ++column) {
        if (column != 0) output << '/';
        if (state[column].empty()) {
            output << '-';
            continue;
        }
        for (const auto color : state[column]) {
            output << water_sort::color_to_char(color);
        }
    }
    return output.str();
}

std::string compact_ranks(const std::vector<std::uint32_t>& ranks) {
    std::ostringstream output;
    for (std::size_t i = 0; i < ranks.size(); ++i) {
        if (i != 0) output << ',';
        output << ranks[i];
    }
    return output.str();
}

std::vector<std::uint32_t> monochrome_counts(const PhysicalState& state,
                                             std::uint32_t colors) {
    std::vector<std::uint32_t> result(colors, 0);
    for (const auto& column : state) {
        if (!column.empty() && is_monochrome(column)) ++result[column.back()];
    }
    return result;
}

void verify_conserved(const water_sort::Instance& instance,
                      const PhysicalState& state) {
    if (state.size() != instance.columns.size() + instance.empty_columns) {
        throw Gap("invalid_physical_state", "physical stack count changed");
    }
    std::vector<std::uint32_t> counts(instance.color_count, 0);
    for (const auto& column : state) {
        if (column.size() > instance.height) {
            throw Gap("invalid_physical_state", "physical stack exceeds capacity");
        }
        for (const auto color : column) {
            if (color >= instance.color_count) {
                throw Gap("invalid_physical_state", "physical state has an unknown color");
            }
            ++counts[color];
        }
    }
    for (std::uint32_t color = 0; color < instance.color_count; ++color) {
        if (counts[color] != instance.height) {
            throw Gap("invalid_physical_state", "physical state changed a color total");
        }
    }
}

void verify_tight(const water_sort::Instance& instance,
                  const std::vector<std::vector<std::uint32_t>>& borders,
                  const water_sort::PolicyStateView& view,
                  const PhysicalState& state,
                  const std::string& phase) {
    verify_conserved(instance, state);
    for (std::size_t column = 0; column < instance.columns.size(); ++column) {
        const auto rank = view.ranks[column];
        if (rank >= borders[column].size()) {
            throw Gap("rank_out_of_range", phase + ": oracle rank is out of range");
        }
        const auto expected = borders[column][rank];
        const auto actual = top_border(state[column]);
        if (actual != expected) {
            std::ostringstream detail;
            detail << phase << ": stack " << column << " has top border " << actual
                   << ", expected " << expected;
            throw Gap("top_border_mismatch", detail.str());
        }
        if (rank != 0) {
            if (state[column].size() <= expected ||
                state[column].back() != instance.columns[column][expected]) {
                throw Gap("top_color_mismatch",
                          phase + ": non-monochrome stack has the wrong top color");
            }
            if (!std::equal(instance.columns[column].begin(),
                            instance.columns[column].begin() + expected,
                            state[column].begin())) {
                throw Gap("protected_prefix_changed",
                          phase + ": contents below a surviving border changed");
            }
        }
    }

    const auto expected_counts = demands(view, instance.height);
    const auto actual_counts = monochrome_counts(state, instance.color_count);
    if (actual_counts != expected_counts) {
        std::ostringstream detail;
        detail << phase << ": monochrome counts";
        for (std::size_t color = 0; color < actual_counts.size(); ++color) {
            detail << " c" << color << '=' << actual_counts[color]
                   << "/" << expected_counts[color];
        }
        throw Gap("not_tight", detail.str());
    }
}

std::size_t top_run_length(const Column& column) {
    if (column.empty()) return 0;
    const auto color = column.back();
    std::size_t run = 1;
    while (run < column.size() && column[column.size() - 1 - run] == color) ++run;
    return run;
}

std::size_t water_move(PhysicalState& state,
                       std::size_t source,
                       std::size_t target,
                       std::uint32_t height,
                       const std::string& phase,
                       std::vector<MoveRecord>& trace,
                       std::uint64_t max_bulk_moves) {
    if (source >= state.size() || target >= state.size() || source == target) {
        throw Gap("illegal_bulk_move", phase + ": invalid source or target");
    }
    if (state[source].empty()) {
        throw Gap("illegal_bulk_move", phase + ": source is empty");
    }
    if (is_locked(state[source], height)) {
        throw Gap("locked_source", phase + ": attempted to source a locked full monochrome stack");
    }
    if (state[target].size() == height) {
        throw Gap("illegal_bulk_move", phase + ": target is full");
    }
    const auto color = state[source].back();
    if (!state[target].empty() && state[target].back() != color) {
        throw Gap("illegal_bulk_move", phase + ": target top has another color");
    }
    const auto run = top_run_length(state[source]);
    const auto free_space = static_cast<std::size_t>(height) - state[target].size();
    const auto quantity = std::min(run, free_space);
    if (quantity == 0) throw Gap("illegal_bulk_move", phase + ": forced quantity is zero");

    state[source].resize(state[source].size() - quantity);
    state[target].insert(state[target].end(), quantity, color);
    trace.push_back({source, target, quantity, color, phase});
    if (max_bulk_moves != 0 && trace.size() > max_bulk_moves) {
        throw Gap("move_limit", "continuous trace exceeded --max-bulk-moves");
    }
    return quantity;
}

std::optional<std::size_t> best_nonempty_target(const PhysicalState& state,
                                                std::size_t source,
                                                water_sort::Color color,
                                                std::uint32_t height) {
    std::optional<std::size_t> best;
    std::size_t best_space = 0;
    for (std::size_t target = 0; target < state.size(); ++target) {
        if (target == source || state[target].empty() ||
            state[target].size() == height || state[target].back() != color) {
            continue;
        }
        const auto space = static_cast<std::size_t>(height) - state[target].size();
        if (!best || space > best_space) {
            best = target;
            best_space = space;
        }
    }
    return best;
}

void empty_monochrome_bin(PhysicalState& state,
                          std::size_t source,
                          water_sort::Color color,
                          const water_sort::Instance& instance,
                          std::vector<MoveRecord>& trace,
                          std::uint64_t max_bulk_moves) {
    if (state[source].empty() || !is_monochrome(state[source]) ||
        state[source].back() != color) {
        throw Gap("retight_invalid_source", "retight source is not the requested monochrome bin");
    }
    if (is_locked(state[source], instance.height)) {
        throw Gap("retight_locked_extra",
                  "retightening would require sourcing a locked completed bin");
    }
    while (!state[source].empty()) {
        const auto target = best_nonempty_target(state, source, color, instance.height);
        if (!target) {
            throw Gap("retight_no_target",
                      "no non-empty compatible target can absorb the extra monochrome bin");
        }
        water_move(state, source, *target, instance.height, "retight", trace,
                   max_bulk_moves);
    }
}

void retighten(PhysicalState& state,
               const water_sort::Instance& instance,
               const water_sort::PolicyStateView& successor_view,
               std::vector<MoveRecord>& trace,
               std::uint64_t max_bulk_moves) {
    const auto required = demands(successor_view, instance.height);
    for (std::uint32_t color = 0; color < instance.color_count; ++color) {
        while (true) {
            const auto counts = monochrome_counts(state, instance.color_count);
            if (counts[color] < required[color]) {
                throw Gap("retight_missing_bin",
                          "border elimination produced fewer monochrome bins than M_c");
            }
            if (counts[color] == required[color]) break;

            std::optional<std::size_t> extra;
            for (std::size_t column = 0; column < state.size(); ++column) {
                if (!state[column].empty() && is_monochrome(state[column]) &&
                    state[column].back() == color &&
                    state[column].size() < instance.height) {
                    extra = column;
                    break;
                }
            }
            if (!extra) {
                throw Gap("retight_locked_extra",
                          "all excess monochrome bins are locked and full");
            }
            empty_monochrome_bin(state, *extra, static_cast<water_sort::Color>(color),
                                 instance, trace, max_bulk_moves);
        }
    }
}

void eliminate_border(PhysicalState& state,
                      const water_sort::Instance& instance,
                      const std::vector<std::vector<std::uint32_t>>& borders,
                      const water_sort::PolicyStateView& view,
                      std::size_t source,
                      const water_sort::PolicyStateView& successor_view,
                      std::vector<MoveRecord>& trace,
                      std::uint64_t max_bulk_moves) {
    if (source >= instance.columns.size() || view.ranks[source] == 0) {
        throw Gap("invalid_macro_source", "selected source has no surviving border");
    }
    const auto border = borders[source][view.ranks[source]];
    auto& source_column = state[source];
    if (top_border(source_column) != border || source_column.size() <= border) {
        throw Gap("source_border_mismatch", "physical source does not expose the selected border");
    }
    const auto color = source_column.back();
    const auto current_demands = demands(view, instance.height);
    auto usable = view.g[color];
    const auto removed_host_capacity = instance.height - border;
    if (usable < removed_host_capacity) {
        throw Gap("invalid_oracle_totals", "G_c is smaller than the selected host capacity");
    }
    usable -= removed_host_capacity;
    const auto source_demand = view.f[color] > usable
        ? ceil_div(view.f[color] - usable, instance.height)
        : 0U;

    if (source_demand == current_demands[color]) {
        while (source_column.size() > border) {
            const auto target = best_nonempty_target(state, source, color, instance.height);
            if (!target) {
                throw Gap("eliminate_no_target",
                          "M_c^b=M_c but no compatible non-empty target has capacity");
            }
            water_move(state, source, *target, instance.height, "eliminate-hosted",
                       trace, max_bulk_moves);
        }
    } else {
        if (source_demand != current_demands[color] + 1U) {
            throw Gap("unexpected_source_demand",
                      "removing one host changed M_c by more than one");
        }
        std::optional<std::size_t> empty;
        for (std::size_t target = 0; target < state.size(); ++target) {
            if (target != source && state[target].empty()) {
                empty = target;
                break;
            }
        }
        if (!empty) {
            throw Gap("eliminate_no_empty",
                      "M_c^b>M_c but the tight physical state has no empty stack");
        }
        while (source_column.size() > border) {
            water_move(state, source, *empty, instance.height, "eliminate-empty",
                       trace, max_bulk_moves);
            if (source_column.size() > border && state[*empty].size() == instance.height) {
                throw Gap("eliminate_empty_overflow",
                          "one empty stack could not absorb the selected top layer");
            }
        }
    }
    if (source_column.size() != border) {
        throw Gap("eliminate_wrong_height", "selected top layer was not removed exactly");
    }

    retighten(state, instance, successor_view, trace, max_bulk_moves);
}

SimulationResult simulate(const CatalogEntry& entry,
                          const Controller& controller,
                          const Options& options,
                          const water_sort::BorderOracle& oracle,
                          const water_sort::PolicyTable& table) {
    SimulationResult result;
    result.state_id = table.initial_state;
    result.physical = entry.instance.columns;
    result.physical.resize(entry.instance.columns.size() + entry.instance.empty_columns);
    const auto borders = original_borders(entry.instance);

    try {
        if (table.solvable[table.initial_state] == 0) {
            throw Gap("frontier_unreachable",
                      "catalog instance cannot reach the requested exhausted-column frontier");
        }
        auto initial_view = oracle.policy_state(result.state_id, options.visible_boundaries);
        result.ranks = initial_view.ranks;
        verify_tight(entry.instance, borders, initial_view, result.physical, "initial");

        while (table.goal[result.state_id] == 0) {
            const auto view = oracle.policy_state(result.state_id,
                                                  options.visible_boundaries);
            result.ranks = view.ranks;
            verify_tight(entry.instance, borders, view, result.physical, "before");

            const auto observation = canonical_observation(
                view, table.legal_columns[result.state_id], entry.instance.color_count,
                entry.instance.empty_columns);
            result.macro_signature = observation.signature;
            const auto action = choose_controller_action(controller, observation);
            if (action >= observation.original_columns.size() ||
                (observation.action_columns & (std::uint64_t{1} << action)) == 0) {
                throw Gap("policy_illegal", "compressed controller selected an illegal source");
            }
            result.source = observation.original_columns[action];
            if ((table.safe_columns[result.state_id] &
                 (std::uint64_t{1} << result.source)) == 0) {
                throw Gap("policy_unsafe", "compressed controller selected an unsafe source");
            }

            const auto successor = oracle.policy_successor(result.state_id, result.source);
            const auto successor_view = oracle.policy_state(successor,
                                                            options.visible_boundaries);
            eliminate_border(result.physical, entry.instance, borders, view, result.source,
                             successor_view, result.trace, options.max_bulk_moves);
            result.state_id = successor;
            result.ranks = successor_view.ranks;
            ++result.macro_steps;
            verify_tight(entry.instance, borders, successor_view, result.physical, "after");
        }

        // At the requested frontier there are enough monochrome bins to host
        // every color in the focused c4,k2 model. Continue with any legal
        // border until the exact all-zero top-border goal is reached.
        while (result.state_id != 0) {
            const auto view = oracle.policy_state(result.state_id,
                                                  options.visible_boundaries);
            result.ranks = view.ranks;
            verify_tight(entry.instance, borders, view, result.physical,
                         "finish-before");

            std::optional<std::size_t> source;
            for (std::size_t column = 0; column < view.columns.size(); ++column) {
                if (view.ranks[column] != 0 &&
                    view.columns[column].buffers_needed <= view.available_buffers) {
                    source = column;
                    break;
                }
            }
            if (!source) {
                throw Gap("finish_no_legal_source",
                          "frontier reached but no remaining border is removable");
            }

            result.source = *source;
            const auto successor = oracle.policy_successor(result.state_id, *source);
            const auto successor_view = oracle.policy_state(
                successor, options.visible_boundaries);
            eliminate_border(result.physical, entry.instance, borders, view, *source,
                             successor_view, result.trace, options.max_bulk_moves);
            result.state_id = successor;
            result.ranks = successor_view.ranks;
            ++result.macro_steps;
            verify_tight(entry.instance, borders, successor_view, result.physical,
                         "finish-after");
        }
        result.bulk_moves = result.trace.size();
        result.success = true;
        result.reason = "ok";
        result.detail = "continuous tight construction reached the full sorted goal";
    } catch (const Gap& gap) {
        result.bulk_moves = result.trace.size();
        result.success = false;
        result.reason = gap.reason;
        result.detail = gap.what();
    }
    return result;
}

std::string tsv_field(std::string value) {
    for (auto& c : value) {
        if (c == '\t' || c == '\n' || c == '\r') c = ' ';
    }
    return value;
}

std::string json_escape(const std::string& value) {
    std::ostringstream output;
    for (const unsigned char c : value) {
        switch (c) {
        case '\\': output << "\\\\"; break;
        case '"': output << "\\\""; break;
        case '\n': output << "\\n"; break;
        case '\r': output << "\\r"; break;
        case '\t': output << "\\t"; break;
        default:
            if (c < 0x20) {
                output << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                       << static_cast<unsigned>(c) << std::dec;
            } else {
                output << static_cast<char>(c);
            }
        }
    }
    return output.str();
}

void write_gap_witness(const std::filesystem::path& path,
                       const CatalogEntry& entry,
                       const Controller& controller,
                       const SimulationResult& result) {
    std::ofstream output(path);
    if (!output) throw std::runtime_error("cannot write gap witness");
    output << "policy=" << controller.id << '\n'
           << "policy_path=" << controller.path.string() << '\n'
           << "catalog_index=" << entry.index << '\n'
           << "reason=" << result.reason << '\n'
           << "detail=" << result.detail << '\n'
           << "macro_steps=" << result.macro_steps << '\n'
           << "bulk_moves=" << result.bulk_moves << '\n'
           << "state=" << result.state_id << '\n'
           << "source=";
    if (result.source == std::numeric_limits<std::size_t>::max()) output << "none";
    else output << result.source;
    output << '\n'
           << "ranks=" << compact_ranks(result.ranks) << '\n'
           << "macro_signature=" << result.macro_signature << '\n'
           << "instance=" << entry.encoding << '\n'
           << "physical=" << compact_state(result.physical) << '\n'
           << "trace_begin\n";
    for (std::size_t step = 0; step < result.trace.size(); ++step) {
        const auto& move = result.trace[step];
        output << step << '\t' << move.phase << '\t' << move.source << "->"
               << move.target << '\t' << move.quantity << '\t'
               << water_sort::color_to_char(move.color) << '\n';
    }
    output << "trace_end\n";
}

} // namespace

int main(int argc, char** argv) try {
    const auto options = parse_options(argc, argv);
    const auto entries = read_catalog(options);
    std::vector<Controller> controllers;
    controllers.reserve(options.policies.size());
    for (std::size_t id = 0; id < options.policies.size(); ++id) {
        controllers.push_back(read_policy(options.policies[id], id));
    }

    std::filesystem::create_directories(options.out);
    std::filesystem::remove(options.out / "first_gap.txt");
    std::ofstream rows(options.out / "report.tsv");
    if (!rows) throw std::runtime_error("cannot write report.tsv");
    rows << "policy\tmodel\theight\tsuccess\treason\tmacro_steps\tbulk_moves\t"
            "state\tsource\tranks\tdetail\tphysical\tinstance\n";

    std::uint64_t runs = 0;
    std::uint64_t successes = 0;
    std::uint64_t total_macro_steps = 0;
    std::uint64_t total_bulk_moves = 0;
    std::uint64_t max_bulk_moves = 0;
    std::map<std::string, std::uint64_t> reasons;
    bool have_first_gap = false;
    std::size_t first_gap_model = 0;
    std::string first_gap_policy;
    std::string first_gap_reason;
    std::string first_gap_detail;

    for (const auto& entry : entries) {
        water_sort::BorderOracle oracle(entry.instance);
        const auto table = oracle.policy_table_to_exhausted_columns(
            options.goal_exhausted_columns);
        for (const auto& controller : controllers) {
            const auto result = simulate(entry, controller, options, oracle, table);
            ++runs;
            if (result.success) ++successes;
            ++reasons[result.reason];
            total_macro_steps += result.macro_steps;
            total_bulk_moves += result.bulk_moves;
            max_bulk_moves = std::max(max_bulk_moves, result.bulk_moves);

            rows << controller.id << '\t' << entry.index << '\t'
                 << entry.instance.height << '\t' << (result.success ? 1 : 0) << '\t'
                 << result.reason << '\t' << result.macro_steps << '\t'
                 << result.bulk_moves << '\t' << result.state_id << '\t';
            if (result.source == std::numeric_limits<std::size_t>::max()) rows << "-";
            else rows << result.source;
            rows << '\t' << compact_ranks(result.ranks) << '\t'
                 << tsv_field(result.detail) << '\t'
                 << compact_state(result.physical) << '\t' << entry.encoding << '\n';

            if (!result.success && !have_first_gap) {
                have_first_gap = true;
                first_gap_model = entry.index;
                first_gap_policy = controller.id;
                first_gap_reason = result.reason;
                first_gap_detail = result.detail;
                write_gap_witness(options.out / "first_gap.txt", entry, controller, result);
            }
        }
    }

    std::ofstream json(options.out / "report.json");
    if (!json) throw std::runtime_error("cannot write report.json");
    json << "{\n"
         << "  \"catalog\": \"" << json_escape(options.catalog.string()) << "\",\n"
         << "  \"shard\": " << options.shard << ",\n"
         << "  \"shards\": " << options.shards << ",\n"
         << "  \"models\": " << entries.size() << ",\n"
         << "  \"controllers\": " << controllers.size() << ",\n"
         << "  \"runs\": " << runs << ",\n"
         << "  \"successes\": " << successes << ",\n"
         << "  \"gaps\": " << (runs - successes) << ",\n"
         << "  \"macro_steps\": " << total_macro_steps << ",\n"
         << "  \"bulk_moves\": " << total_bulk_moves << ",\n"
         << "  \"max_bulk_moves_per_run\": " << max_bulk_moves << ",\n"
         << "  \"locked_source_violations\": "
         << (reasons.count("locked_source") ? reasons.at("locked_source") : 0) +
                (reasons.count("retight_locked_extra")
                     ? reasons.at("retight_locked_extra") : 0)
         << ",\n"
         << "  \"reasons\": {";
    bool first_reason = true;
    for (const auto& [reason, count] : reasons) {
        if (!first_reason) json << ',';
        json << "\n    \"" << json_escape(reason) << "\": " << count;
        first_reason = false;
    }
    if (!reasons.empty()) json << '\n';
    json << "  },\n"
         << "  \"first_gap\": ";
    if (!have_first_gap) {
        json << "null\n";
    } else {
        json << "{\n"
             << "    \"policy\": \"" << json_escape(first_gap_policy) << "\",\n"
             << "    \"model\": " << first_gap_model << ",\n"
             << "    \"reason\": \"" << json_escape(first_gap_reason) << "\",\n"
             << "    \"detail\": \"" << json_escape(first_gap_detail) << "\",\n"
             << "    \"witness\": \"first_gap.txt\"\n"
             << "  }\n";
    }
    json << "}\n";

    std::cout << "successes=" << successes << " gaps=" << (runs - successes)
              << " runs=" << runs << " macro_steps=" << total_macro_steps
              << " bulk_moves=" << total_bulk_moves << '\n';
    return successes == runs ? 0 : 2;
} catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
}
