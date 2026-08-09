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
    std::string fitness = "solutions";
    std::uint64_t restart_interval = 2000;
    std::uint32_t height = 16;
    std::uint32_t colors = 5;
    std::uint32_t empty_columns = 2;
    std::int32_t uniform_layer = -1;
    bool isolate_uniform_layer = false;
    bool fully_alternating = false;
    std::filesystem::path input;
    std::filesystem::path out = "out";
};

struct Evaluation {
    std::uint64_t solutions = 0;
    std::uint64_t states = 0;
    std::uint32_t safe_initial = 0;
};

bool better(const Evaluation& left,
            const Evaluation& right,
            const Options& options) {
    if (options.fitness == "safe-initial" &&
        left.safe_initial != right.safe_initial) {
        return left.safe_initial < right.safe_initial;
    }
    if (left.solutions != right.solutions) {
        return left.solutions < right.solutions;
    }
    if (left.solutions == options.solution_cap && left.states != right.states) {
        return left.states > right.states;
    }
    return false;
}

std::uint32_t count_bits(std::uint64_t value) {
    std::uint32_t count = 0;
    while (value != 0) {
        value &= value - 1U;
        ++count;
    }
    return count;
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

Evaluation evaluate(const water_sort::Instance& instance,
                    const Options& options) {
    const water_sort::BorderOracle oracle(instance);
    const auto result = oracle.count_solutions(options.solution_cap);
    auto safe_initial = static_cast<std::uint32_t>(instance.columns.size());
    if (options.fitness == "safe-initial") {
        if (instance.empty_columns >= instance.color_count) {
            throw std::runtime_error(
                "safe-initial fitness requires fewer empty columns than colors");
        }
        const auto target = instance.color_count - instance.empty_columns;
        const auto policy = oracle.policy_table_to_exhausted_columns(target);
        const auto initial = policy.initial_state;
        safe_initial = policy.goal[initial] != 0
            ? static_cast<std::uint32_t>(instance.columns.size() + 1U)
            : count_bits(policy.safe_columns[initial]);
        if ((result.solutions == 0) != (policy.solvable[initial] == 0)) {
            throw std::runtime_error(
                "solution count and exhausted-frontier policy disagree");
        }
    }
    return {result.solutions, result.states_evaluated, safe_initial};
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
           << "  \"fitness\": \"" << options.fitness << "\",\n"
           << "  \"fitness_goal_exhausted_columns\": "
           << (options.fitness == "safe-initial"
                   ? std::to_string(options.colors - options.empty_columns)
                   : "null")
           << ",\n"
           << "  \"solution_cap\": " << options.solution_cap << ",\n"
           << "  \"restart_interval\": " << options.restart_interval << ",\n"
           << "  \"seed_instance\": \"" << options.input.generic_string()
           << "\",\n"
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
           << "  \"best_safe_initial_actions\": "
           << (options.fitness == "safe-initial"
                   ? std::to_string(best.safe_initial)
                   : "null")
           << ",\n"
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
        else if (argument == "--fitness") options.fitness = value();
        else if (argument == "--restart-interval") options.restart_interval = std::stoull(value());
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
        else if (argument == "--input") options.input = value();
        else if (argument == "--help") {
            std::cout << "water-hunter [--seed N] [--shard I --shards N] [--seconds N] "
                         "[--iterations N] [--solution-cap N] [--height H] [--colors N] "
                         "[--fitness solutions|safe-initial] "
                         "[--input INSTANCE] [--restart-interval N] "
                         "[--empty K] [--uniform-layer POSITION] "
                         "[--isolate-uniform-layer 0|1] [--fully-alternating 0|1] [--out DIR]\n";
            std::exit(0);
        } else throw std::runtime_error("unknown argument: " + argument);
    }
    if (options.shards == 0 || options.shard >= options.shards || options.solution_cap == 0 ||
        options.height == 0 || options.colors == 0 || options.colors > 36 ||
        (options.fitness != "solutions" && options.fitness != "safe-initial") ||
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
    const auto initial_instance = [&]() {
        if (options.input.empty()) return random_instance(options, rng);
        auto instance = water_sort::read_instance(options.input);
        if (instance.height != options.height ||
            instance.color_count != options.colors ||
            instance.empty_columns != options.empty_columns ||
            !satisfies_structure(instance, options)) {
            throw std::runtime_error(
                "seed instance does not match hunter parameters or structure");
        }
        return instance;
    }();
    auto current = initial_instance;
    auto current_eval = evaluate(current, options);
    auto best = current;
    auto best_eval = current_eval;
    water_sort::write_instance(best, options.out / "best.txt");
    if (best_eval.solutions == 0) {
        const water_sort::BorderOracle oracle(best);
        const auto proof = oracle.solve();
        if (proof.solvable) {
            throw std::runtime_error(
                "internal inconsistency: zero count but oracle found a solution");
        }
        water_sort::write_instance(best, options.out / "counterexample.txt");
        water_sort::write_no_certificate(
            best, oracle.state_count(), proof.reachable_bits,
            options.out / "counterexample.wscert");
        write_report(options, effective_seed, 0, best_eval, true);
        std::cout << "COUNTEREXAMPLE FOUND IN SEED\n";
        return 0;
    }

    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(options.seconds);
    std::uniform_real_distribution<double> probability(0.0, 1.0);
    std::uint64_t iteration = 0;
    bool found = false;
    while ((options.iterations == 0 || iteration < options.iterations) &&
           (options.seconds == 0 || std::chrono::steady_clock::now() < deadline)) {
        ++iteration;
        auto candidate = current;
        mutate(candidate, rng, options);
        const auto candidate_eval = evaluate(candidate, options);
        if (better(candidate_eval, best_eval, options)) {
            best = candidate;
            best_eval = candidate_eval;
            water_sort::write_instance(best, options.out / "best.txt");
            std::cout << "iteration=" << iteration;
            if (options.fitness == "safe-initial") {
                std::cout << " best_safe_initial=" << best_eval.safe_initial;
            }
            std::cout << " best_sequences=" << best_eval.solutions
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
        const bool equal_primary = options.fitness == "safe-initial"
            ? candidate_eval.safe_initial == current_eval.safe_initial
            : candidate_eval.solutions == current_eval.solutions;
        const bool accept = better(candidate_eval, current_eval, options) ||
                            (equal_primary && probability(rng) < 0.03) ||
                            probability(rng) < 0.002 * temperature;
        if (accept) {
            current = std::move(candidate);
            current_eval = candidate_eval;
        }
        if (iteration % 500 == 0) {
            write_report(options, effective_seed, iteration, best_eval, false);
        }
        if (options.restart_interval != 0 &&
            iteration % options.restart_interval == 0) {
            current = options.input.empty()
                ? random_instance(options, rng)
                : initial_instance;
            current_eval = evaluate(current, options);
        }
    }

    water_sort::write_instance(best, options.out / "best.txt");
    write_report(options, effective_seed, iteration, best_eval, found);
    std::cout << "completed iterations=" << iteration;
    if (options.fitness == "safe-initial") {
        std::cout << " best_safe_initial=" << best_eval.safe_initial;
    }
    std::cout << " best_sequences=" << best_eval.solutions
              << (best_eval.solutions == options.solution_cap ? "+" : "") << '\n';
    return 0;
} catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
}
