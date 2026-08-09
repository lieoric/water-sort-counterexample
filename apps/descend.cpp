#include "water_sort/border_oracle.hpp"
#include "water_sort/certificate.hpp"
#include "water_sort/instance.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

namespace {

struct Options {
    std::filesystem::path input;
    std::filesystem::path out = "out/descend";
    std::uint32_t target_height = 1;
    std::uint32_t frontier_limit = 64;
    std::uint64_t seed = 0;
};

struct Node {
    water_sort::Instance instance;
    std::vector<water_sort::Instance> path;
};

struct Candidate {
    water_sort::Instance instance;
    std::size_t parent = 0;
};

struct LevelReport {
    std::uint32_t from_height = 0;
    std::uint64_t unique_candidates = 0;
    std::uint64_t candidates_tested = 0;
    std::uint64_t no_descendants = 0;
};

Options parse_options(int argc, char** argv) {
    Options options;
    options.seed = static_cast<std::uint64_t>(
        std::chrono::high_resolution_clock::now().time_since_epoch().count());
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        const auto value = [&]() -> std::string {
            if (i + 1 >= argc) throw std::runtime_error("missing value for " + argument);
            return argv[++i];
        };
        if (argument == "--input") options.input = value();
        else if (argument == "--out") options.out = value();
        else if (argument == "--target-height") {
            options.target_height = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--frontier-limit") {
            options.frontier_limit = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--seed") {
            options.seed = std::stoull(value());
        } else if (argument == "--help") {
            std::cout << "water-descend --input INSTANCE --target-height H "
                         "[--frontier-limit N] [--seed N] [--out DIR]\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown argument: " + argument);
        }
    }
    if (options.input.empty() || options.target_height == 0 || options.frontier_limit == 0) {
        throw std::runtime_error("invalid descent options");
    }
    return options;
}

void enumerate_balanced_children(const water_sort::Instance& parent,
                                 std::size_t column,
                                 std::uint64_t used_colors,
                                 std::vector<std::size_t>& removals,
                                 std::vector<water_sort::Instance>& output,
                                 std::unordered_set<std::string>& seen) {
    if (column == parent.columns.size()) {
        auto child = parent;
        --child.height;
        for (std::size_t index = 0; index < child.columns.size(); ++index) {
            child.columns[index].erase(child.columns[index].begin() +
                                        static_cast<std::ptrdiff_t>(removals[index]));
        }
        child = water_sort::canonicalize_instance(child);
        const auto encoding = water_sort::canonical_encoding(child);
        if (seen.insert(encoding).second) output.push_back(std::move(child));
        return;
    }

    std::uint64_t colors_seen_in_column = 0;
    for (std::size_t position = 0; position < parent.columns[column].size(); ++position) {
        const auto color = parent.columns[column][position];
        const auto bit = std::uint64_t{1} << color;
        if ((used_colors & bit) != 0 || (colors_seen_in_column & bit) != 0) continue;
        colors_seen_in_column |= bit;
        removals[column] = position;
        enumerate_balanced_children(parent, column + 1, used_colors | bit,
                                    removals, output, seen);
    }
}

bool is_no(const water_sort::Instance& instance) {
    return water_sort::BorderOracle(instance).count_solutions(1).solutions == 0;
}

void save_path(const Node& node, const std::filesystem::path& out) {
    for (const auto& instance : node.path) {
        const auto stem = std::string("h") + std::to_string(instance.height);
        water_sort::write_instance(instance, out / (stem + ".txt"));
        const water_sort::BorderOracle oracle(instance);
        const auto proof = oracle.solve();
        if (proof.solvable) throw std::runtime_error("descent path contains a solvable instance");
        water_sort::write_no_certificate(instance, oracle.state_count(), proof.reachable_bits,
                                         out / (stem + ".wscert"));
    }
}

void write_report(const Options& options,
                  const std::vector<LevelReport>& levels,
                  bool reached) {
    std::ofstream report(options.out / "report.json");
    report << "{\n"
           << "  \"seed\": " << options.seed << ",\n"
           << "  \"target_height\": " << options.target_height << ",\n"
           << "  \"frontier_limit\": " << options.frontier_limit << ",\n"
           << "  \"target_reached\": " << (reached ? "true" : "false") << ",\n"
           << "  \"levels\": [\n";
    for (std::size_t index = 0; index < levels.size(); ++index) {
        const auto& level = levels[index];
        report << "    {\"from_height\": " << level.from_height
               << ", \"unique_candidates\": " << level.unique_candidates
               << ", \"candidates_tested\": " << level.candidates_tested
               << ", \"no_descendants\": " << level.no_descendants << "}";
        if (index + 1 != levels.size()) report << ',';
        report << '\n';
    }
    report << "  ]\n}\n";
}

} // namespace

int main(int argc, char** argv) try {
    const auto options = parse_options(argc, argv);
    std::filesystem::create_directories(options.out);
    auto initial = water_sort::canonicalize_instance(water_sort::read_instance(options.input));
    if (options.target_height > initial.height) {
        throw std::runtime_error("target height exceeds input height");
    }
    if (initial.color_count > 63 || initial.columns.size() != initial.color_count) {
        throw std::runtime_error("balanced descent requires at most 63 colors and c full columns");
    }
    if (!is_no(initial)) throw std::runtime_error("descent input must be unsolvable");

    std::mt19937_64 rng(options.seed);
    std::vector<Node> frontier{{initial, {initial}}};
    std::vector<LevelReport> reports;

    while (frontier.front().instance.height > options.target_height) {
        LevelReport level;
        level.from_height = frontier.front().instance.height;
        std::vector<Candidate> candidates;
        std::unordered_set<std::string> seen;
        for (std::size_t parent = 0; parent < frontier.size(); ++parent) {
            std::vector<water_sort::Instance> children;
            std::vector<std::size_t> removals(frontier[parent].instance.columns.size());
            enumerate_balanced_children(frontier[parent].instance, 0, 0, removals,
                                        children, seen);
            for (auto& child : children) {
                candidates.push_back({std::move(child), parent});
            }
        }
        level.unique_candidates = candidates.size();
        std::shuffle(candidates.begin(), candidates.end(), rng);

        std::vector<Node> next;
        for (auto& candidate : candidates) {
            ++level.candidates_tested;
            if (!is_no(candidate.instance)) continue;
            ++level.no_descendants;
            auto path = frontier[candidate.parent].path;
            path.push_back(candidate.instance);
            next.push_back({std::move(candidate.instance), std::move(path)});
            if (next.size() == options.frontier_limit) break;
        }
        reports.push_back(level);
        std::cout << "height=" << level.from_height << "->" << level.from_height - 1
                  << " unique=" << level.unique_candidates
                  << " tested=" << level.candidates_tested
                  << " no=" << level.no_descendants << '\n';
        if (next.empty()) {
            write_report(options, reports, false);
            std::cout << "DESCENT STOPPED\n";
            return 2;
        }
        frontier = std::move(next);
    }

    save_path(frontier.front(), options.out);
    write_report(options, reports, true);
    std::cout << "TARGET REACHED height=" << options.target_height << '\n';
    return 0;
} catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
}
