#include "water_sort/border_oracle.hpp"
#include "water_sort/instance.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
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
    std::uint32_t shard = 0;
    std::uint32_t shards = 1;
    std::uint32_t max_instances = 0;
};

struct Observation {
    std::string signature;
    std::uint64_t action_columns = 0;
    std::vector<std::size_t> original_columns;
};

struct Controller {
    std::string id;
    std::unordered_map<std::string, std::uint8_t> exceptions;
};

struct CatalogEntry {
    std::size_t index = 0;
    std::string encoding;
    water_sort::Instance instance;
};

struct Model {
    std::size_t index = 0;
    std::string encoding;
    water_sort::Instance instance;
    water_sort::BorderOracle oracle;
    water_sort::PolicyTable table;

    Model(CatalogEntry entry, std::uint32_t goal)
        : index(entry.index),
          encoding(std::move(entry.encoding)),
          instance(std::move(entry.instance)),
          oracle(instance),
          table(oracle.policy_table_to_exhausted_columns(goal)) {}

    Model(Model&&) = default;
    Model& operator=(Model&&) = default;
    Model(const Model&) = delete;
    Model& operator=(const Model&) = delete;
};

struct Aggregate {
    std::uint64_t occurrences = 0;
    std::uint64_t common_safe = 0;
    std::uint64_t observed_safe = 0;
    std::vector<std::string> witnesses;
};

struct Totals {
    std::uint64_t controller_instances = 0;
    std::uint64_t macro_states = 0;
    std::uint64_t unit_moves = 0;
    std::uint64_t retightening_gaps = 0;
    std::uint64_t exception_occurrences = 0;
};

std::vector<std::string> split(const std::string& value, char delimiter) {
    std::vector<std::string> result;
    std::stringstream input(value);
    std::string field;
    while (std::getline(input, field, delimiter)) result.push_back(field);
    return result;
}

water_sort::Instance parse_compact_instance(const std::string& encoding) {
    const auto fields = split(encoding, ';');
    if (fields.size() != 4 || fields[0].rfind("h=", 0) != 0 ||
        fields[1].rfind("c=", 0) != 0 || fields[2].rfind("k=", 0) != 0 ||
        fields[3].rfind("cols=", 0) != 0) {
        throw std::runtime_error("invalid compact instance: " + encoding);
    }
    water_sort::Instance instance;
    instance.height = std::stoul(fields[0].substr(2));
    instance.color_count = std::stoul(fields[1].substr(2));
    instance.empty_columns = std::stoul(fields[2].substr(2));
    for (auto raw_column : split(fields[3].substr(5), '/')) {
        if (!raw_column.empty() && raw_column.back() == '\r') raw_column.pop_back();
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
    if (!input) throw std::runtime_error("cannot open instance catalog");
    std::string line;
    std::getline(input, line);
    std::vector<CatalogEntry> entries;
    std::size_t index = 0;
    while (std::getline(input, line)) {
        const auto tab = line.find('\t');
        if (tab == std::string::npos) throw std::runtime_error("invalid catalog row");
        auto encoding = line.substr(tab + 1);
        if (!encoding.empty() && encoding.back() == '\r') encoding.pop_back();
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
    if (!input) throw std::runtime_error("cannot open compressed policy");
    std::string line;
    std::getline(input, line);
    if (line != "action\tdomain\tsignature" &&
        line != "action\tdomain\tsignature\r") {
        throw std::runtime_error("invalid compressed policy header");
    }
    Controller result;
    result.id = "p" + std::to_string(id);
    while (std::getline(input, line)) {
        const auto fields = split(line, '\t');
        if (fields.size() != 3) throw std::runtime_error("invalid compressed policy row");
        auto signature = fields[2];
        if (!signature.empty() && signature.back() == '\r') signature.pop_back();
        const auto action = static_cast<std::uint32_t>(std::stoul(fields[0]));
        if (action >= 64) throw std::runtime_error("compressed action is out of range");
        const auto domain = std::stoull(fields[1], nullptr, 16);
        if ((domain & (std::uint64_t{1} << action)) == 0) {
            throw std::runtime_error("compressed action is outside its policy domain");
        }
        const auto inserted = result.exceptions.emplace(
            std::move(signature), static_cast<std::uint8_t>(action));
        if (!inserted.second) {
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
        else if (argument == "--goal-exhausted") {
            options.goal_exhausted_columns = std::stoul(value());
        } else if (argument == "--shard") options.shard = std::stoul(value());
        else if (argument == "--shards") options.shards = std::stoul(value());
        else if (argument == "--max-instances") options.max_instances = std::stoul(value());
        else if (argument == "--out") options.out = value();
        else if (argument == "--help") {
            std::cout << "water-unit-scenes --catalog FILE --policy FILE [--policy FILE] "
                         "[--goal-exhausted N] [--shard I --shards N] "
                         "[--max-instances N] [--out DIR]\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown argument: " + argument);
        }
    }
    if (options.catalog.empty() || options.policies.empty() ||
        options.goal_exhausted_columns == 0 || options.shards == 0 ||
        options.shard >= options.shards) {
        throw std::runtime_error("invalid unit-scene options");
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

PhysicalState make_tight_state(const water_sort::Instance& instance,
                               const water_sort::PolicyStateView& view) {
    const auto borders = original_borders(instance);
    const auto full_columns = instance.columns.size();
    PhysicalState state(full_columns + instance.empty_columns);
    std::vector<std::vector<std::size_t>> hosts(instance.color_count);
    std::vector<std::size_t> monochrome_bins;

    for (std::size_t column = 0; column < full_columns; ++column) {
        const auto rank = view.ranks[column];
        if (rank == 0) {
            monochrome_bins.push_back(column);
            continue;
        }
        const auto border = borders[column][rank];
        state[column].assign(instance.columns[column].begin(),
                             instance.columns[column].begin() + border);
        hosts[instance.columns[column][border]].push_back(column);
    }
    for (std::size_t column = full_columns; column < state.size(); ++column) {
        monochrome_bins.push_back(column);
    }

    std::size_t next_monochrome = 0;
    for (std::uint32_t color = 0; color < instance.color_count; ++color) {
        auto remaining = view.f[color];
        for (const auto column : hosts[color]) {
            if (remaining == 0) {
                throw std::runtime_error("tight construction cannot seed a host");
            }
            state[column].push_back(static_cast<water_sort::Color>(color));
            --remaining;
        }
        for (const auto column : hosts[color]) {
            const auto capacity = instance.height - state[column].size();
            const auto quantity = std::min<std::uint32_t>(
                remaining, static_cast<std::uint32_t>(capacity));
            state[column].insert(state[column].end(), quantity,
                                 static_cast<water_sort::Color>(color));
            remaining -= quantity;
        }
        while (remaining != 0) {
            if (next_monochrome == monochrome_bins.size()) {
                throw std::runtime_error("tight construction ran out of monochrome bins");
            }
            const auto column = monochrome_bins[next_monochrome++];
            const auto quantity = std::min<std::uint32_t>(remaining, instance.height);
            state[column].insert(state[column].end(), quantity,
                                 static_cast<water_sort::Color>(color));
            remaining -= quantity;
        }
    }

    std::vector<std::uint32_t> counts(instance.color_count, 0);
    for (const auto& column : state) {
        if (column.size() > instance.height) {
            throw std::runtime_error("tight construction overflowed a bin");
        }
        for (const auto color : column) ++counts[color];
    }
    if (std::any_of(counts.begin(), counts.end(),
                    [&](std::uint32_t count) { return count != instance.height; })) {
        throw std::runtime_error("tight construction changed color totals");
    }
    return state;
}

std::uint64_t legal_unit_actions(const PhysicalState& state,
                                 std::size_t source,
                                 std::uint32_t height) {
    if (source >= state.size() || state[source].empty() ||
        (state[source].size() == height && is_monochrome(state[source]))) {
        return 0;
    }
    const auto color = state[source].back();
    std::uint64_t result = 0;
    for (std::size_t target = 0; target < state.size(); ++target) {
        if (target == source || state[target].size() == height ||
            (!state[target].empty() && state[target].back() != color)) {
            continue;
        }
        const auto action = source * 8U + target;
        result |= std::uint64_t{1} << action;
    }
    return result;
}

std::uint64_t safe_start_actions(const PhysicalState& state,
                                 std::uint64_t safe_sources,
                                 std::uint32_t height) {
    std::uint64_t result = 0;
    while (safe_sources != 0) {
        std::size_t source = 0;
        while ((safe_sources & (std::uint64_t{1} << source)) == 0) ++source;
        safe_sources &= safe_sources - 1;
        const auto actions = legal_unit_actions(state, source, height);
        if (actions == 0) {
            throw std::runtime_error("safe border source has no unit move");
        }
        result |= actions;
    }
    return result;
}

std::size_t first_action(std::uint64_t actions) {
    if (actions == 0) throw std::runtime_error("cannot choose an empty unit action");
    std::size_t action = 0;
    while ((actions & (std::uint64_t{1} << action)) == 0) ++action;
    return action;
}

std::string unit_scene(const PhysicalState& state,
                       const std::vector<std::uint8_t>& mixed,
                       std::uint32_t window,
                       bool active,
                       std::size_t active_source,
                       std::uint32_t colors,
                       std::uint32_t height) {
    std::vector<int> color_map(colors, -1);
    int next_color = 0;
    auto map_color = [&](water_sort::Color color) {
        if (color_map[color] < 0) color_map[color] = next_color++;
        return static_cast<water_sort::Color>(color_map[color]);
    };

    if (active) {
        if (state[active_source].empty()) {
            throw std::runtime_error("active source unexpectedly empty");
        }
        map_color(state[active_source].back());
    }
    for (const auto& column : state) {
        const auto visible = std::min<std::size_t>(window, column.size());
        for (std::size_t offset = 0; offset < visible; ++offset) {
            map_color(column[column.size() - 1 - offset]);
        }
    }

    std::ostringstream output;
    output << (active ? "qA" : "qI");
    if (active) output << "s" << active_source;
    output << '|';
    for (std::size_t index = 0; index < state.size(); ++index) {
        if (index != 0) output << '/';
        const auto& column = state[index];
        char status = 'p';
        if (column.empty()) status = 'e';
        else if (column.size() == height && is_monochrome(column)) status = 'l';
        else if (column.size() == height) status = 'f';
        output << index << ':' << (mixed[index] != 0 ? 'b' : 'm') << status << ':';
        const auto visible = std::min<std::size_t>(window, column.size());
        for (std::size_t offset = 0; offset < visible; ++offset) {
            output << water_sort::color_to_char(static_cast<water_sort::Color>(
                color_map[column[column.size() - 1 - offset]]));
        }
        output << (column.size() > window ? '+' : '.');
    }
    return output.str();
}

struct TopRun {
    water_sort::Color color = 0;
    std::size_t length = 0;
};

std::vector<TopRun> top_runs(const Column& column, std::uint32_t window) {
    std::vector<TopRun> result;
    auto cursor = column.size();
    while (cursor != 0 && result.size() < window) {
        const auto color = column[cursor - 1];
        std::size_t length = 0;
        while (cursor != 0 && column[cursor - 1] == color) {
            --cursor;
            ++length;
        }
        result.push_back({color, length});
    }
    return result;
}

std::uint32_t ceil_div(std::uint32_t numerator, std::uint32_t denominator) {
    return numerator == 0 ? 0 : 1 + (numerator - 1) / denominator;
}

std::string run_scene(const PhysicalState& state,
                      const std::vector<std::uint8_t>& mixed,
                      const water_sort::PolicyStateView& view,
                      std::uint32_t run_window,
                      bool with_demand,
                      bool active,
                      std::size_t active_source,
                      std::uint32_t colors,
                      std::uint32_t empty_columns,
                      std::uint32_t height) {
    std::vector<std::uint32_t> color_map(colors);
    std::iota(color_map.begin(), color_map.end(), 0U);
    std::string best;
    bool have_best = false;
    const auto need_cap = colors + empty_columns + 1U;

    do {
        std::ostringstream output;
        output << (active ? "qA" : "qI");
        if (active) output << "s" << active_source;
        if (with_demand) {
            output << "|a" << view.available_buffers << "|c";
            for (std::uint32_t canonical = 0; canonical < colors; ++canonical) {
                std::uint32_t original = 0;
                while (color_map[original] != canonical) ++original;
                const auto deficit = view.f[original] > view.g[original]
                    ? ceil_div(view.f[original] - view.g[original], height)
                    : 0U;
                output << 'd' << std::min(deficit, need_cap)
                       << (view.g[original] > 0 ? 'h' : '-');
            }
        }
        output << '|';

        for (std::size_t index = 0; index < state.size(); ++index) {
            if (index != 0) output << '/';
            const auto& column = state[index];
            char status = 'p';
            if (column.empty()) status = 'e';
            else if (column.size() == height && is_monochrome(column)) status = 'l';
            else if (column.size() == height) status = 'f';
            output << index << ':' << (mixed[index] != 0 ? 'b' : 'm') << status;
            if (with_demand && index < view.columns.size()) {
                const auto& source = view.columns[index];
                output << (source.remaining_borders == 0 ? ":x" : ":n");
                if (source.remaining_borders != 0) {
                    output << std::min(source.buffers_needed, need_cap);
                }
            }
            output << ':';

            const auto runs = top_runs(column, run_window);
            std::size_t visible_items = 0;
            for (const auto& run : runs) {
                visible_items += run.length;
                output << water_sort::color_to_char(static_cast<water_sort::Color>(
                    color_map[run.color]));
            }
            output << (visible_items < column.size() ? '+' : '.');
        }

        auto signature = output.str();
        if (!have_best || signature < best) {
            best = std::move(signature);
            have_best = true;
        }
    } while (std::next_permutation(color_map.begin(), color_map.end()));

    return best;
}

void add_scene(std::unordered_map<std::string, Aggregate>& scenes,
               std::string signature,
               std::uint64_t safe_actions,
               const std::string& witness) {
    auto& aggregate = scenes[signature];
    if (aggregate.occurrences == 0) aggregate.common_safe = safe_actions;
    else aggregate.common_safe &= safe_actions;
    aggregate.observed_safe |= safe_actions;
    ++aggregate.occurrences;
    if (aggregate.witnesses.size() < 4) aggregate.witnesses.push_back(witness);
}

std::string hex_mask(std::uint64_t mask) {
    std::ostringstream output;
    output << "0x" << std::hex << mask;
    return output.str();
}

void write_scenes(const std::filesystem::path& out,
                  const std::string& label,
                  const std::unordered_map<std::string, Aggregate>& scenes) {
    std::vector<std::string> signatures;
    signatures.reserve(scenes.size());
    for (const auto& [signature, aggregate] : scenes) {
        static_cast<void>(aggregate);
        signatures.push_back(signature);
    }
    std::sort(signatures.begin(), signatures.end());
    std::ofstream all(out / ("scenes-" + label + ".tsv"));
    std::ofstream conflicts(out / ("conflicts-" + label + ".tsv"));
    const std::string header = "occurrences\tcommon_safe\tobserved_safe\twitnesses\tsignature\n";
    all << header;
    conflicts << header;
    for (const auto& signature : signatures) {
        const auto& aggregate = scenes.at(signature);
        std::ostringstream witnesses;
        for (std::size_t i = 0; i < aggregate.witnesses.size(); ++i) {
            if (i != 0) witnesses << ',';
            witnesses << aggregate.witnesses[i];
        }
        std::ostringstream row;
        row << aggregate.occurrences << '\t' << hex_mask(aggregate.common_safe)
            << '\t' << hex_mask(aggregate.observed_safe) << '\t'
            << witnesses.str() << '\t' << signature << '\n';
        all << row.str();
        if (aggregate.common_safe == 0) conflicts << row.str();
    }
}

std::uint8_t choose_controller_action(const Controller& controller,
                                      const Observation& legal_observation) {
    const auto exception = controller.exceptions.find(legal_observation.signature);
    if (exception != controller.exceptions.end()) return exception->second;
    std::uint8_t action = 0;
    for (std::uint8_t position = 0;
         position < legal_observation.original_columns.size(); ++position) {
        if ((legal_observation.action_columns & (std::uint64_t{1} << position)) != 0) {
            action = position;
        }
    }
    return action;
}

} // namespace

int main(int argc, char** argv) try {
    const auto options = parse_options(argc, argv);
    auto entries = read_catalog(options);
    std::vector<Controller> controllers;
    for (std::size_t i = 0; i < options.policies.size(); ++i) {
        controllers.push_back(read_policy(options.policies[i], i));
    }

    std::unordered_map<std::string, std::uint64_t> exception_coverage;
    for (const auto& controller : controllers) {
        for (const auto& [signature, action] : controller.exceptions) {
            static_cast<void>(action);
            exception_coverage.emplace(signature, 0);
        }
    }

    std::vector<Model> models;
    models.reserve(entries.size());
    for (auto& entry : entries) {
        models.emplace_back(std::move(entry), options.goal_exhausted_columns);
        if (models.back().instance.columns.size() +
                models.back().instance.empty_columns >
            8) {
            throw std::runtime_error(
                "unit-action encoding supports at most eight physical stacks");
        }
        if (models.back().table.solvable[models.back().table.initial_state] == 0) {
            throw std::runtime_error("catalog contains a frontier-unreachable instance");
        }
    }

    std::array<std::unordered_map<std::string, Aggregate>, 5> scenes;
    std::array<std::unordered_map<std::string, Aggregate>, 4> run_scenes;
    std::array<std::unordered_map<std::string, Aggregate>, 4> demand_run_scenes;
    Totals totals;
    std::filesystem::create_directories(options.out);
    std::ofstream occurrences(options.out / "exception_occurrences.tsv");
    occurrences << "policy\tmodel\theight\tstate\tcanonical_action\tsource\t"
                   "safe_sources\tmacro_signature\tinstance\n";

    for (const auto& controller : controllers) {
        for (auto& model : models) {
            ++totals.controller_instances;
            auto state_id = model.table.initial_state;
            while (model.table.goal[state_id] == 0) {
                ++totals.macro_states;
                const auto view = model.oracle.policy_state(state_id, 3);
                const auto legal_observation = canonical_observation(
                    view, model.table.legal_columns[state_id],
                    model.instance.color_count, model.instance.empty_columns);
                const auto action = choose_controller_action(controller, legal_observation);
                if ((legal_observation.action_columns &
                     (std::uint64_t{1} << action)) == 0) {
                    throw std::runtime_error("compressed controller selected an illegal source");
                }
                const auto source = legal_observation.original_columns[action];
                if ((model.table.safe_columns[state_id] &
                     (std::uint64_t{1} << source)) == 0) {
                    throw std::runtime_error("compressed controller selected an unsafe source");
                }

                const auto exception = controller.exceptions.find(
                    legal_observation.signature);
                if (exception != controller.exceptions.end()) {
                    ++totals.exception_occurrences;
                    ++exception_coverage[legal_observation.signature];
                    occurrences << controller.id << '\t' << model.index << '\t'
                                << model.instance.height << '\t' << state_id << '\t'
                                << static_cast<std::uint32_t>(action) << '\t' << source
                                << '\t' << hex_mask(model.table.safe_columns[state_id])
                                << '\t' << legal_observation.signature << '\t'
                                << model.encoding << '\n';
                }

                auto physical = make_tight_state(model.instance, view);
                std::vector<std::uint8_t> mixed(physical.size(), 0);
                for (std::size_t column = 0; column < view.ranks.size(); ++column) {
                    mixed[column] = view.ranks[column] != 0 ? 1 : 0;
                }
                const auto safe_starts = safe_start_actions(
                    physical, model.table.safe_columns[state_id], model.instance.height);
                const auto witness = controller.id + ":m" +
                    std::to_string(model.index) + ":s" + std::to_string(state_id) + ":I";
                for (std::uint32_t window = 2; window <= 6; ++window) {
                    add_scene(scenes[window - 2],
                              unit_scene(physical, mixed, window, false, source,
                                         model.instance.color_count, model.instance.height),
                              safe_starts, witness);
                }
                for (std::uint32_t window = 1; window <= 4; ++window) {
                    add_scene(run_scenes[window - 1],
                              run_scene(physical, mixed, view, window, false, false,
                                        source, model.instance.color_count,
                                        model.instance.empty_columns,
                                        model.instance.height),
                              safe_starts, witness);
                    add_scene(demand_run_scenes[window - 1],
                              run_scene(physical, mixed, view, window, true, false,
                                        source, model.instance.color_count,
                                        model.instance.empty_columns,
                                        model.instance.height),
                              safe_starts, witness);
                }

                auto chosen_unit_actions = legal_unit_actions(
                    physical, source, model.instance.height);
                if (chosen_unit_actions == 0) {
                    throw std::runtime_error("chosen border source has no unit action");
                }
                const auto moving_color = physical[source].back();
                std::uint32_t step = 0;
                while (!physical[source].empty() &&
                       physical[source].back() == moving_color) {
                    const auto safe_units = legal_unit_actions(
                        physical, source, model.instance.height);
                    if (safe_units == 0) {
                        throw std::runtime_error("unit trace cannot finish the selected border");
                    }
                    const auto active_witness = controller.id + ":m" +
                        std::to_string(model.index) + ":s" + std::to_string(state_id) +
                        ":A" + std::to_string(step);
                    for (std::uint32_t window = 2; window <= 6; ++window) {
                        add_scene(scenes[window - 2],
                                  unit_scene(physical, mixed, window, true, source,
                                             model.instance.color_count,
                                             model.instance.height),
                                  safe_units, active_witness);
                    }
                    for (std::uint32_t window = 1; window <= 4; ++window) {
                        add_scene(run_scenes[window - 1],
                                  run_scene(physical, mixed, view, window, false, true,
                                            source, model.instance.color_count,
                                            model.instance.empty_columns,
                                            model.instance.height),
                                  safe_units, active_witness);
                        add_scene(demand_run_scenes[window - 1],
                                  run_scene(physical, mixed, view, window, true, true,
                                            source, model.instance.color_count,
                                            model.instance.empty_columns,
                                            model.instance.height),
                                  safe_units, active_witness);
                    }
                    const auto unit_action = first_action(safe_units);
                    const auto unit_source = unit_action / 8U;
                    const auto target = unit_action % 8U;
                    if (unit_source != source) {
                        throw std::runtime_error("unit action changed the active source");
                    }
                    physical[source].pop_back();
                    physical[target].push_back(moving_color);
                    ++step;
                    ++totals.unit_moves;
                }
                const auto borders = original_borders(model.instance);
                const auto expected_border = borders[source][view.ranks[source]];
                if (physical[source].size() != expected_border ||
                    !std::equal(physical[source].begin(), physical[source].end(),
                                model.instance.columns[source].begin())) {
                    throw std::runtime_error(
                        "unit trace did not remove exactly the selected top border");
                }
                const auto successor = model.oracle.policy_successor(state_id, source);
                if (model.table.goal[successor] == 0) {
                    ++totals.retightening_gaps;
                }
                state_id = successor;
            }
        }
    }

    std::ofstream coverage(options.out / "exception_coverage.tsv");
    coverage << "occurrences\tsignature\n";
    std::vector<std::string> exception_signatures;
    for (const auto& [signature, count] : exception_coverage) {
        static_cast<void>(count);
        exception_signatures.push_back(signature);
    }
    std::sort(exception_signatures.begin(), exception_signatures.end());
    std::size_t witnessed_exceptions = 0;
    for (const auto& signature : exception_signatures) {
        const auto count = exception_coverage.at(signature);
        coverage << count << '\t' << signature << '\n';
        if (count != 0) ++witnessed_exceptions;
    }

    std::array<std::size_t, 5> conflicts{};
    std::array<std::size_t, 4> run_conflicts{};
    std::array<std::size_t, 4> demand_run_conflicts{};
    for (std::uint32_t window = 2; window <= 6; ++window) {
        write_scenes(options.out, "w" + std::to_string(window), scenes[window - 2]);
        conflicts[window - 2] = static_cast<std::size_t>(std::count_if(
            scenes[window - 2].begin(), scenes[window - 2].end(),
            [](const auto& item) { return item.second.common_safe == 0; }));
    }
    for (std::uint32_t window = 1; window <= 4; ++window) {
        write_scenes(options.out, "r" + std::to_string(window),
                     run_scenes[window - 1]);
        write_scenes(options.out, "rd" + std::to_string(window),
                     demand_run_scenes[window - 1]);
        run_conflicts[window - 1] = static_cast<std::size_t>(std::count_if(
            run_scenes[window - 1].begin(), run_scenes[window - 1].end(),
            [](const auto& item) { return item.second.common_safe == 0; }));
        demand_run_conflicts[window - 1] = static_cast<std::size_t>(std::count_if(
            demand_run_scenes[window - 1].begin(), demand_run_scenes[window - 1].end(),
            [](const auto& item) { return item.second.common_safe == 0; }));
    }

    std::ofstream report(options.out / "report.json");
    report << "{\n"
           << "  \"shard\": " << options.shard << ",\n"
           << "  \"shards\": " << options.shards << ",\n"
           << "  \"models\": " << models.size() << ",\n"
           << "  \"controllers\": " << controllers.size() << ",\n"
           << "  \"controller_instances\": " << totals.controller_instances << ",\n"
           << "  \"macro_states\": " << totals.macro_states << ",\n"
           << "  \"unit_moves\": " << totals.unit_moves << ",\n"
           << "  \"retightening_gaps\": " << totals.retightening_gaps << ",\n"
           << "  \"exception_signatures\": " << exception_signatures.size() << ",\n"
           << "  \"witnessed_exceptions\": " << witnessed_exceptions << ",\n"
           << "  \"exception_occurrences\": " << totals.exception_occurrences << ",\n"
           << "  \"scenes_w2\": " << scenes[0].size() << ",\n"
           << "  \"scenes_w3\": " << scenes[1].size() << ",\n"
           << "  \"scenes_w4\": " << scenes[2].size() << ",\n"
           << "  \"scenes_w5\": " << scenes[3].size() << ",\n"
           << "  \"scenes_w6\": " << scenes[4].size() << ",\n"
           << "  \"scenes_r1\": " << run_scenes[0].size() << ",\n"
           << "  \"scenes_r2\": " << run_scenes[1].size() << ",\n"
           << "  \"scenes_r3\": " << run_scenes[2].size() << ",\n"
           << "  \"scenes_r4\": " << run_scenes[3].size() << ",\n"
           << "  \"scenes_rd1\": " << demand_run_scenes[0].size() << ",\n"
           << "  \"scenes_rd2\": " << demand_run_scenes[1].size() << ",\n"
           << "  \"scenes_rd3\": " << demand_run_scenes[2].size() << ",\n"
           << "  \"scenes_rd4\": " << demand_run_scenes[3].size() << ",\n"
           << "  \"conflicts_w2\": " << conflicts[0] << ",\n"
           << "  \"conflicts_w3\": " << conflicts[1] << ",\n"
           << "  \"conflicts_w4\": " << conflicts[2] << ",\n"
           << "  \"conflicts_w5\": " << conflicts[3] << ",\n"
           << "  \"conflicts_w6\": " << conflicts[4] << ",\n"
           << "  \"conflicts_r1\": " << run_conflicts[0] << ",\n"
           << "  \"conflicts_r2\": " << run_conflicts[1] << ",\n"
           << "  \"conflicts_r3\": " << run_conflicts[2] << ",\n"
           << "  \"conflicts_r4\": " << run_conflicts[3] << ",\n"
           << "  \"conflicts_rd1\": " << demand_run_conflicts[0] << ",\n"
           << "  \"conflicts_rd2\": " << demand_run_conflicts[1] << ",\n"
           << "  \"conflicts_rd3\": " << demand_run_conflicts[2] << ",\n"
           << "  \"conflicts_rd4\": " << demand_run_conflicts[3] << "\n"
           << "}\n";
    std::cout << "models=" << models.size() << " macros=" << totals.macro_states
              << " unit_moves=" << totals.unit_moves
              << " exceptions=" << witnessed_exceptions << '/'
              << exception_signatures.size() << " conflicts=" << conflicts[0]
              << ',' << conflicts[1] << ',' << conflicts[2] << ','
              << conflicts[3] << ',' << conflicts[4]
              << " run_conflicts=" << run_conflicts[0] << ',' << run_conflicts[1]
              << ',' << run_conflicts[2] << ',' << run_conflicts[3]
              << " demand_run_conflicts=" << demand_run_conflicts[0] << ','
              << demand_run_conflicts[1] << ',' << demand_run_conflicts[2] << ','
              << demand_run_conflicts[3] << '\n';
    return 0;
} catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
}
