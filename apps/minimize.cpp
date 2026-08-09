#include "water_sort/border_oracle.hpp"
#include "water_sort/certificate.hpp"
#include "water_sort/instance.hpp"

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_set>

namespace {

struct Options {
    std::filesystem::path input;
    std::filesystem::path out = "out/minimize";
    std::uint64_t seed = 0;
    std::uint64_t seconds = 900;
    std::uint64_t iterations = 0;
    std::uint32_t shard = 0;
};

struct Score {
    std::uint32_t borders = 0;
    std::uint32_t singleton_runs = 0;
    std::uint64_t reachable_states = 0;
    std::uint32_t min_terminal_depth = 0;

    [[nodiscard]] bool operator<(const Score& other) const {
        return std::tie(borders, singleton_runs, reachable_states, min_terminal_depth) <
               std::tie(other.borders, other.singleton_runs, other.reachable_states,
                        other.min_terminal_depth);
    }
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
        else if (argument == "--seed") options.seed = std::stoull(value());
        else if (argument == "--seconds") options.seconds = std::stoull(value());
        else if (argument == "--iterations") options.iterations = std::stoull(value());
        else if (argument == "--shard") {
            options.shard = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--help") {
            std::cout << "water-minimize --input INSTANCE [--seconds N] [--iterations N] "
                         "[--seed N] [--shard N] [--out DIR]\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown argument: " + argument);
        }
    }
    if (options.input.empty() || (options.seconds == 0 && options.iterations == 0)) {
        throw std::runtime_error("invalid minimizer options");
    }
    return options;
}

Score score_instance(const water_sort::Instance& instance) {
    Score score;
    for (const auto& column : instance.columns) {
        std::size_t run_start = 0;
        for (std::size_t position = 1; position <= column.size(); ++position) {
            if (position != column.size() && column[position] == column[position - 1]) continue;
            if (position - run_start == 1) ++score.singleton_runs;
            if (position != column.size()) ++score.borders;
            run_start = position;
        }
    }
    const auto analysis = water_sort::BorderOracle(instance).analyze();
    score.reachable_states = analysis.reachable_states;
    score.min_terminal_depth = analysis.min_terminal_depth;
    return score;
}

bool is_no(const water_sort::Instance& instance) {
    return water_sort::BorderOracle(instance).count_solutions(1).solutions == 0;
}

void mutate(water_sort::Instance& instance, std::mt19937_64& rng) {
    const auto cell_count = instance.columns.size() * instance.height;
    std::uniform_int_distribution<std::size_t> position(0, cell_count - 1);
    const auto first = position(rng);
    auto second = position(rng);
    const auto first_color = instance.columns[first / instance.height][first % instance.height];
    while (second == first ||
           instance.columns[second / instance.height][second % instance.height] == first_color) {
        second = position(rng);
    }
    std::swap(instance.columns[first / instance.height][first % instance.height],
              instance.columns[second / instance.height][second % instance.height]);
}

} // namespace

int main(int argc, char** argv) try {
    const auto options = parse_options(argc, argv);
    std::filesystem::create_directories(options.out);
    auto current = water_sort::canonicalize_instance(water_sort::read_instance(options.input));
    if (!is_no(current)) throw std::runtime_error("minimizer input must be unsolvable");
    auto current_score = score_instance(current);
    auto best = current;
    auto best_score = current_score;
    water_sort::write_instance(best, options.out / "best.txt");

    const auto effective_seed = options.seed +
        0x9e3779b97f4a7c15ULL * static_cast<std::uint64_t>(options.shard + 1);
    std::mt19937_64 rng(effective_seed);
    std::uniform_real_distribution<double> probability(0.0, 1.0);
    std::unordered_set<std::string> seen{water_sort::canonical_encoding(current)};
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(options.seconds);
    std::uint64_t iteration = 0;
    std::uint64_t no_candidates = 0;

    while ((options.iterations == 0 || iteration < options.iterations) &&
           (options.seconds == 0 || std::chrono::steady_clock::now() < deadline)) {
        ++iteration;
        auto candidate = current;
        mutate(candidate, rng);
        candidate = water_sort::canonicalize_instance(candidate);
        const auto encoding = water_sort::canonical_encoding(candidate);
        if (!seen.insert(encoding).second || !is_no(candidate)) continue;
        ++no_candidates;
        const auto candidate_score = score_instance(candidate);
        if (candidate_score < best_score) {
            best = candidate;
            best_score = candidate_score;
            water_sort::write_instance(best, options.out / "best.txt");
            std::cout << "iteration=" << iteration << " borders=" << best_score.borders
                      << " singleton_runs=" << best_score.singleton_runs
                      << " reachable=" << best_score.reachable_states
                      << " terminal_depth=" << best_score.min_terminal_depth << '\n';
        }
        if (candidate_score < current_score || probability(rng) < 0.02) {
            current = std::move(candidate);
            current_score = candidate_score;
        }
        if (iteration % 2000 == 0) {
            current = best;
            current_score = best_score;
        }
    }

    const water_sort::BorderOracle oracle(best);
    const auto proof = oracle.solve();
    if (proof.solvable) throw std::runtime_error("minimizer produced a solvable instance");
    water_sort::write_instance(best, options.out / "minimized.txt");
    water_sort::write_no_certificate(best, oracle.state_count(), proof.reachable_bits,
                                     options.out / "minimized.wscert");
    std::ofstream report(options.out / "report.json");
    report << "{\n"
           << "  \"seed\": " << effective_seed << ",\n"
           << "  \"iterations\": " << iteration << ",\n"
           << "  \"unique_visited\": " << seen.size() << ",\n"
           << "  \"no_candidates\": " << no_candidates << ",\n"
           << "  \"borders\": " << best_score.borders << ",\n"
           << "  \"singleton_runs\": " << best_score.singleton_runs << ",\n"
           << "  \"reachable_states\": " << best_score.reachable_states << ",\n"
           << "  \"min_terminal_depth\": " << best_score.min_terminal_depth << "\n"
           << "}\n";
    std::cout << "completed iterations=" << iteration << " best_borders=" << best_score.borders
              << '\n';
    return 0;
} catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
}
