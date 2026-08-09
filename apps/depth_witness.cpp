#include "water_sort/border_oracle.hpp"
#include "water_sort/instance.hpp"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using Column = std::vector<water_sort::Color>;
using PhysicalState = std::vector<Column>;

struct Options {
    std::filesystem::path left;
    std::filesystem::path right;
    std::filesystem::path out;
    std::uint32_t left_state = 0;
    std::uint32_t right_state = 0;
    std::uint32_t goal_exhausted = 2;
    std::uint32_t scale = 1;
    std::uint32_t window = 1;
};

struct Witness {
    std::string scene;
    std::uint64_t safe_sources = 0;
    std::uint64_t safe_units = 0;
    PhysicalState physical;
};

bool is_monochrome(const Column& column) {
    return column.empty() || std::all_of(column.begin(), column.end(),
                                         [&](water_sort::Color color) {
                                             return color == column.front();
                                         });
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
            if (remaining == 0) throw std::runtime_error("cannot seed tight host");
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
                throw std::runtime_error("tight construction ran out of bins");
            }
            const auto column = monochrome_bins[next_monochrome++];
            const auto quantity = std::min<std::uint32_t>(remaining, instance.height);
            state[column].insert(state[column].end(), quantity,
                                 static_cast<water_sort::Color>(color));
            remaining -= quantity;
        }
    }
    return state;
}

water_sort::Instance scale_instance(const water_sort::Instance& instance,
                                    std::uint32_t factor) {
    auto scaled = instance;
    scaled.height *= factor;
    for (std::size_t column = 0; column < instance.columns.size(); ++column) {
        scaled.columns[column].clear();
        for (const auto color : instance.columns[column]) {
            scaled.columns[column].insert(scaled.columns[column].end(), factor, color);
        }
    }
    scaled.validate();
    return scaled;
}

PhysicalState scale_physical(const PhysicalState& state, std::uint32_t factor) {
    PhysicalState scaled(state.size());
    for (std::size_t column = 0; column < state.size(); ++column) {
        for (const auto color : state[column]) {
            scaled[column].insert(scaled[column].end(), factor, color);
        }
    }
    return scaled;
}

std::uint64_t legal_unit_actions(const PhysicalState& state,
                                 std::size_t source,
                                 std::uint32_t height) {
    if (state[source].empty() ||
        (state[source].size() == height && is_monochrome(state[source]))) {
        return 0;
    }
    const auto color = state[source].back();
    std::uint64_t actions = 0;
    for (std::size_t target = 0; target < state.size(); ++target) {
        if (target == source || state[target].size() == height ||
            (!state[target].empty() && state[target].back() != color)) {
            continue;
        }
        actions |= std::uint64_t{1} << (source * 8U + target);
    }
    return actions;
}

std::uint64_t safe_start_actions(const PhysicalState& state,
                                 std::uint64_t safe_sources,
                                 std::uint32_t height) {
    std::uint64_t actions = 0;
    for (std::size_t source = 0; source < state.size(); ++source) {
        if ((safe_sources & (std::uint64_t{1} << source)) != 0) {
            actions |= legal_unit_actions(state, source, height);
        }
    }
    return actions;
}

std::string scene_signature(const PhysicalState& state,
                            const std::vector<std::uint32_t>& ranks,
                            std::uint32_t colors,
                            std::uint32_t height,
                            std::uint32_t window) {
    std::vector<int> color_map(colors, -1);
    int next_color = 0;
    for (const auto& column : state) {
        const auto visible = std::min<std::size_t>(window, column.size());
        for (std::size_t offset = 0; offset < visible; ++offset) {
            const auto color = column[column.size() - 1 - offset];
            if (color_map[color] < 0) color_map[color] = next_color++;
        }
    }

    std::ostringstream output;
    output << "qI|";
    for (std::size_t index = 0; index < state.size(); ++index) {
        if (index != 0) output << '/';
        const auto& column = state[index];
        char status = 'p';
        if (column.empty()) status = 'e';
        else if (column.size() == height && is_monochrome(column)) status = 'l';
        else if (column.size() == height) status = 'f';
        const auto mixed = index < ranks.size() && ranks[index] != 0;
        output << index << ':' << (mixed ? 'b' : 'm') << status << ':';
        const auto visible = std::min<std::size_t>(window, column.size());
        for (std::size_t offset = 0; offset < visible; ++offset) {
            const auto color = column[column.size() - 1 - offset];
            output << water_sort::color_to_char(
                static_cast<water_sort::Color>(color_map[color]));
        }
        output << (column.size() > window ? '+' : '.');
    }
    return output.str();
}

void validate_scaled_physical(const water_sort::Instance& instance,
                              const water_sort::PolicyStateView& view,
                              const PhysicalState& physical) {
    const auto borders = original_borders(instance);
    std::vector<std::uint32_t> counts(instance.color_count, 0);
    for (std::size_t column = 0; column < physical.size(); ++column) {
        if (physical[column].size() > instance.height) {
            throw std::runtime_error("scaled physical column overflowed");
        }
        for (const auto color : physical[column]) ++counts[color];
        if (column >= instance.columns.size()) {
            if (!is_monochrome(physical[column])) {
                throw std::runtime_error("scaled buffer is not monochrome");
            }
            continue;
        }
        const auto rank = view.ranks[column];
        if (rank == 0) {
            if (!is_monochrome(physical[column])) {
                throw std::runtime_error("exhausted scaled column is not monochrome");
            }
            continue;
        }
        const auto border = borders[column][rank];
        if (physical[column].size() <= border ||
            !std::equal(physical[column].begin(), physical[column].begin() + border,
                        instance.columns[column].begin())) {
            throw std::runtime_error("scaled physical prefix does not match its border");
        }
        const auto host_color = instance.columns[column][border];
        if (!std::all_of(physical[column].begin() + border, physical[column].end(),
                         [&](water_sort::Color color) {
                             return color == host_color;
                         })) {
            throw std::runtime_error("scaled physical host is not tight");
        }
    }
    if (std::any_of(counts.begin(), counts.end(), [&](std::uint32_t count) {
            return count != instance.height;
        })) {
        throw std::runtime_error("scaled physical state changed color totals");
    }
}

Witness analyze(const std::filesystem::path& path,
                std::uint32_t state_id,
                const Options& options) {
    const auto base = water_sort::read_instance(path);
    const water_sort::BorderOracle base_oracle(base);
    const auto base_table = base_oracle.policy_table_to_exhausted_columns(
        options.goal_exhausted);
    if (state_id >= base_table.solvable.size() || base_table.solvable[state_id] == 0) {
        throw std::runtime_error("base witness state is not frontier-winning");
    }
    const auto base_view = base_oracle.policy_state(state_id, 1);
    const auto base_physical = make_tight_state(base, base_view);
    const auto base_units = safe_start_actions(
        base_physical, base_table.safe_columns[state_id], base.height);

    const auto scaled = scale_instance(base, options.scale);
    const water_sort::BorderOracle scaled_oracle(scaled);
    const auto scaled_table = scaled_oracle.policy_table_to_exhausted_columns(
        options.goal_exhausted);
    if (scaled_table.solvable.size() != base_table.solvable.size()) {
        throw std::runtime_error("scaling changed the top-border state space");
    }
    const auto scaled_view = scaled_oracle.policy_state(state_id, 1);
    const auto scaled_physical = scale_physical(base_physical, options.scale);
    validate_scaled_physical(scaled, scaled_view, scaled_physical);
    if (scaled_table.safe_columns[state_id] != base_table.safe_columns[state_id]) {
        throw std::runtime_error("scaling changed the exact safe-source mask");
    }
    const auto scaled_units = safe_start_actions(
        scaled_physical, scaled_table.safe_columns[state_id], scaled.height);
    if (scaled_units != base_units) {
        throw std::runtime_error("scaling changed the exact safe unit actions");
    }
    return {scene_signature(scaled_physical, scaled_view.ranks, scaled.color_count,
                            scaled.height, options.window),
            scaled_table.safe_columns[state_id], scaled_units, scaled_physical};
}

std::string hex_mask(std::uint64_t mask) {
    std::ostringstream output;
    output << "0x" << std::hex << mask;
    return output.str();
}

Options parse_options(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        const auto value = [&]() -> std::string {
            if (i + 1 >= argc) throw std::runtime_error("missing option value");
            return argv[++i];
        };
        if (argument == "--left") options.left = value();
        else if (argument == "--left-state") options.left_state = std::stoul(value());
        else if (argument == "--right") options.right = value();
        else if (argument == "--right-state") options.right_state = std::stoul(value());
        else if (argument == "--goal-exhausted") options.goal_exhausted = std::stoul(value());
        else if (argument == "--scale") options.scale = std::stoul(value());
        else if (argument == "--window") options.window = std::stoul(value());
        else if (argument == "--out") options.out = value();
        else if (argument == "--help") {
            std::cout << "water-depth-witness --left FILE --left-state N "
                         "--right FILE --right-state N --scale L --window D "
                         "[--goal-exhausted N] [--out FILE]\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown option: " + argument);
        }
    }
    if (options.left.empty() || options.right.empty() || options.scale == 0 ||
        options.window == 0 || options.goal_exhausted == 0) {
        throw std::runtime_error("invalid depth-witness options");
    }
    return options;
}

} // namespace

int main(int argc, char** argv) try {
    const auto options = parse_options(argc, argv);
    const auto left = analyze(options.left, options.left_state, options);
    const auto right = analyze(options.right, options.right_state, options);
    if (left.scene != right.scene) {
        throw std::runtime_error("scaled witnesses do not share one observation");
    }
    if ((left.safe_units & right.safe_units) != 0) {
        throw std::runtime_error("scaled witnesses still share a safe unit action");
    }

    std::ostringstream report;
    report << "{\n"
           << "  \"scale\": " << options.scale << ",\n"
           << "  \"window\": " << options.window << ",\n"
           << "  \"left_safe_sources\": \"" << hex_mask(left.safe_sources) << "\",\n"
           << "  \"right_safe_sources\": \"" << hex_mask(right.safe_sources) << "\",\n"
           << "  \"left_safe_units\": \"" << hex_mask(left.safe_units) << "\",\n"
           << "  \"right_safe_units\": \"" << hex_mask(right.safe_units) << "\",\n"
           << "  \"common_safe_units\": \"0x0\",\n"
           << "  \"scene\": \"" << left.scene << "\"\n"
           << "}\n";
    if (!options.out.empty()) {
        std::ofstream output(options.out);
        output << report.str();
    }
    std::cout << report.str();
    return 0;
} catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
}
