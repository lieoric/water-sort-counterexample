#include "water_sort/border_oracle.hpp"
#include "water_sort/certificate.hpp"
#include "water_sort/instance.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>

namespace {

struct Options {
    std::uint64_t seed = 0;
    std::uint32_t shard = 0;
    std::uint32_t shards = 1;
    std::uint64_t seconds = 60;
    std::uint64_t iterations = 0;
    std::uint64_t solution_cap = 10000;
    std::uint32_t height = 16;
    std::uint32_t colors = 5;
    std::uint32_t empty_columns = 2;
    std::int32_t uniform_layer = -1;
    bool isolate_uniform_layer = false;
    bool fully_alternating = false;
    std::filesystem::path out = "out";
};

struct Evaluation {
    std::uint64_t solutions = 0;
    std::uint64_t states = 0;
};

bool better(const Evaluation& left, const Evaluation& right, std::uint64_t cap) {
    if (left.solutions != right.solutions) {
        return left.solutions < right.solutions;
    }
    if (left.solutions == cap && left.states != right.states) {
        return left.states > right.states;
    }
    return false;
}

bool satisfies_structure(const water_sort::Instance& instance, const Options& options) {
    for (const auto& column : instance.columns) {
        if (options.uniform_layer >= 0 &&
            column[static_cast<std::size_t>(options.uniform_layer)] != 0) {
            return false;
        }
        for (std::size_t position = 0; position < column.size(); ++position) {
            if (options.isolate_uniform_layer && column[position] == 0 &&
                (static_cast<std::int32_t>(position) == options.uniform_layer - 1 ||
                 static_cast<std::int32_t>(position) == options.uniform_layer + 1)) {
                return false;
            }
            if (options.fully_alternating && position > 0 &&
                column[position] == column[position - 1]) {
                return false;
            }
        }
    }
    return true;
}

water_sort::Instance random_instance(const Options& options, std::mt19937_64& rng) {
    while (true) {
        water_sort::Instance instance;
        instance.height = options.height;
        instance.color_count = options.colors;
        instance.empty_columns = options.empty_columns;
        std::vector<water_sort::Color> items;
        items.reserve(static_cast<std::size_t>(options.height) * options.colors);
        for (water_sort::Color color = 0; color < options.colors; ++color) {
            auto count = options.height;
            if (options.uniform_layer >= 0 && color == 0) {
                count -= options.colors;
            }
            items.insert(items.end(), count, color);
        }
        std::shuffle(items.begin(), items.end(), rng);
        auto item = items.begin();
        for (std::size_t column = 0; column < options.colors; ++column) {
            auto& output = instance.columns.emplace_back();
            output.reserve(options.height);
            for (std::uint32_t position = 0; position < options.height; ++position) {
                if (options.uniform_layer >= 0 &&
                    position == static_cast<std::uint32_t>(options.uniform_layer)) {
                    output.push_back(0);
                } else {
                    output.push_back(*item++);
                }
            }
        }
        if (satisfies_structure(instance, options)) return instance;
    }
}

void mutate(water_sort::Instance& instance,
            std::mt19937_64& rng,
            const Options& options) {
    const auto cell_count = instance.columns.size() * instance.height;
    std::uniform_int_distribution<std::size_t> position(0, cell_count - 1);
    const auto is_fixed = [&](std::size_t index) {
        return options.uniform_layer >= 0 &&
            index % instance.height == static_cast<std::size_t>(options.uniform_layer);
    };
    while (true) {
        auto first = position(rng);
        while (is_fixed(first)) first = position(rng);
        auto second = position(rng);
        auto& a = instance.columns[first / instance.height][first % instance.height];
        while (is_fixed(second) || second == first ||
               instance.columns[second / instance.height][second % instance.height] == a) {
            second = position(rng);
        }
        auto& b = instance.columns[second / instance.height][second % instance.height];
        std::swap(a, b);
        if (satisfies_structure(instance, options)) return;
        std::swap(a, b);
    }
}

Evaluation evaluate(const water_sort::Instance& instance, std::uint64_t cap) {
    const water_sort::BorderOracle oracle(instance);
    const auto result = oracle.count_solutions(cap);
    return {result.solutions, result.states_evaluated};
}

void write_report(const Options& options,
                  std::uint64_t effective_seed,
                  std::uint64_t iterations,
                  const Evaluation& best,
                  bool found) {
    std::ofstream report(options.out / "report.json");
    report << "{\n"
           << "  \"shard\": " << options.shard << ",\n"
           << "  \"shards\": " << options.shards << ",\n"
           << "  \"seed\": " << effective_seed << ",\n"
           << "  \"iterations\": " << iterations << ",\n"
           << "  \"solution_cap\": " << options.solution_cap << ",\n"
           << "  \"height\": " << options.height << ",\n"
           << "  \"colors\": " << options.colors << ",\n"
           << "  \"empty_columns\": " << options.empty_columns << ",\n"
           << "  \"uniform_layer\": " << options.uniform_layer << ",\n"
           << "  \"isolate_uniform_layer\": "
           << (options.isolate_uniform_layer ? "true" : "false") << ",\n"
           << "  \"fully_alternating\": "
           << (options.fully_alternating ? "true" : "false") << ",\n"
           << "  \"best_border_sequences\": " << best.solutions << ",\n"
           << "  \"best_states_evaluated\": " << best.states << ",\n"
           << "  \"counterexample_found\": " << (found ? "true" : "false") << "\n"
           << "}\n";
}

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
        if (argument == "--seed") options.seed = std::stoull(value());
        else if (argument == "--shard") options.shard = static_cast<std::uint32_t>(std::stoul(value()));
        else if (argument == "--shards") options.shards = static_cast<std::uint32_t>(std::stoul(value()));
        else if (argument == "--seconds") options.seconds = std::stoull(value());
        else if (argument == "--iterations") options.iterations = std::stoull(value());
        else if (argument == "--solution-cap") options.solution_cap = std::stoull(value());
        else if (argument == "--height") {
            options.height = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--colors") {
            options.colors = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--empty") {
            options.empty_columns = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--uniform-layer") {
            options.uniform_layer = static_cast<std::int32_t>(std::stoi(value()));
        } else if (argument == "--isolate-uniform-layer") {
            options.isolate_uniform_layer = std::stoi(value()) != 0;
        } else if (argument == "--fully-alternating") {
            options.fully_alternating = std::stoi(value()) != 0;
        }
        else if (argument == "--out") options.out = value();
        else if (argument == "--help") {
            std::cout << "water-hunter [--seed N] [--shard I --shards N] [--seconds N] "
                         "[--iterations N] [--solution-cap N] [--height H] [--colors N] "
                         "[--empty K] [--uniform-layer POSITION] "
                         "[--isolate-uniform-layer 0|1] [--fully-alternating 0|1] [--out DIR]\n";
            std::exit(0);
        } else throw std::runtime_error("unknown argument: " + argument);
    }
    if (options.shards == 0 || options.shard >= options.shards || options.solution_cap == 0 ||
        options.height == 0 || options.colors == 0 || options.colors > 36 ||
        options.uniform_layer < -1 ||
        options.uniform_layer >= static_cast<std::int32_t>(options.height) ||
        (options.uniform_layer >= 0 && options.height < options.colors) ||
        (options.isolate_uniform_layer && options.uniform_layer < 0) ||
        (options.seconds == 0 && options.iterations == 0)) {
        throw std::runtime_error("invalid hunter options");
    }
    return options;
}

} // namespace

int main(int argc, char** argv) try {
    const auto options = parse_options(argc, argv);
    std::filesystem::create_directories(options.out);
    const auto effective_seed = options.seed +
        0x9e3779b97f4a7c15ULL * static_cast<std::uint64_t>(options.shard + 1);
    std::mt19937_64 rng(effective_seed);
    auto current = random_instance(options, rng);
    auto current_eval = evaluate(current, options.solution_cap);
    auto best = current;
    auto best_eval = current_eval;
    water_sort::write_instance(best, options.out / "best.txt");

    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(options.seconds);
    std::uniform_real_distribution<double> probability(0.0, 1.0);
    std::uint64_t iteration = 0;
    bool found = false;
    while ((options.iterations == 0 || iteration < options.iterations) &&
           (options.seconds == 0 || std::chrono::steady_clock::now() < deadline)) {
        ++iteration;
        auto candidate = current;
        mutate(candidate, rng, options);
        const auto candidate_eval = evaluate(candidate, options.solution_cap);
        if (better(candidate_eval, best_eval, options.solution_cap)) {
            best = candidate;
            best_eval = candidate_eval;
            water_sort::write_instance(best, options.out / "best.txt");
            std::cout << "iteration=" << iteration << " best_sequences=" << best_eval.solutions
                      << " states=" << best_eval.states << '\n';
        }
        if (candidate_eval.solutions == 0) {
            best = candidate;
            best_eval = candidate_eval;
            const water_sort::BorderOracle oracle(best);
            const auto proof = oracle.solve();
            if (proof.solvable) {
                throw std::runtime_error("internal inconsistency: zero count but oracle found a solution");
            }
            water_sort::write_instance(best, options.out / "counterexample.txt");
            water_sort::write_no_certificate(best, oracle.state_count(), proof.reachable_bits,
                                             options.out / "counterexample.wscert");
            found = true;
            std::cout << "COUNTEREXAMPLE FOUND\n";
            break;
        }
        const auto temperature = std::max(0.01, 1.0 - static_cast<double>(iteration % 2000) / 2000.0);
        const bool accept = better(candidate_eval, current_eval, options.solution_cap) ||
                            (candidate_eval.solutions == current_eval.solutions && probability(rng) < 0.03) ||
                            probability(rng) < 0.002 * temperature;
        if (accept) {
            current = std::move(candidate);
            current_eval = candidate_eval;
        }
        if (iteration % 500 == 0) {
            write_report(options, effective_seed, iteration, best_eval, false);
        }
        if (iteration % 2000 == 0) {
            current = random_instance(options, rng);
            current_eval = evaluate(current, options.solution_cap);
        }
    }

    water_sort::write_instance(best, options.out / "best.txt");
    write_report(options, effective_seed, iteration, best_eval, found);
    std::cout << "completed iterations=" << iteration << " best_sequences=" << best_eval.solutions
              << (best_eval.solutions == options.solution_cap ? "+" : "") << '\n';
    return 0;
} catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
}
