#include "water_sort/border_oracle.hpp"
#include "water_sort/certificate.hpp"
#include "water_sort/instance.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

struct Options {
    std::uint64_t seed = 1;
    std::uint32_t shard = 0;
    std::uint32_t shards = 1;
    std::uint32_t height = 7;
    std::uint32_t colors = 4;
    std::uint32_t empty_columns = 2;
    std::uint32_t depth = 2;
    std::uint32_t goal_exhausted_columns = 0;
    std::uint32_t tail_mutations = 0;
    std::uint32_t tail_swaps = 2;
    std::uint64_t samples = 100;
    bool stop_on_no = true;
    std::filesystem::path input;
    std::filesystem::path out = "out";
};

struct Observation {
    std::string signature;
    std::uint64_t safe_columns = 0;
};

struct Aggregate {
    std::uint64_t occurrences = 0;
    std::uint64_t common_safe = 0;
    std::uint64_t observed_safe = 0;
    std::vector<std::string> witnesses;
};

struct Totals {
    std::uint64_t base_instances = 0;
    std::uint64_t instances = 0;
    std::uint64_t solvable_instances = 0;
    std::uint64_t unsolvable_instances = 0;
    std::uint64_t oracle_states = 0;
    std::uint64_t reachable_policy_states = 0;
    std::uint64_t observations = 0;
};

std::uint64_t fnv1a(const std::string& value) {
    std::uint64_t hash = 1469598103934665603ULL;
    for (const auto character : value) {
        hash ^= static_cast<unsigned char>(character);
        hash *= 1099511628211ULL;
    }
    return hash;
}

std::string hex_mask(std::uint64_t mask) {
    std::ostringstream output;
    output << "0x" << std::hex << mask;
    return output.str();
}

std::string compact_instance(const water_sort::Instance& instance) {
    std::ostringstream output;
    output << "h=" << instance.height << ";c=" << instance.color_count
           << ";k=" << instance.empty_columns << ";cols=";
    for (std::size_t column = 0; column < instance.columns.size(); ++column) {
        if (column != 0) output << '/';
        for (const auto color : instance.columns[column]) {
            output << water_sort::color_to_char(color);
        }
    }
    return output.str();
}

water_sort::Instance random_instance(const Options& options, std::mt19937_64& rng) {
    water_sort::Instance instance;
    instance.height = options.height;
    instance.color_count = options.colors;
    instance.empty_columns = options.empty_columns;
    std::vector<water_sort::Color> items;
    items.reserve(static_cast<std::size_t>(options.height) * options.colors);
    for (water_sort::Color color = 0; color < options.colors; ++color) {
        items.insert(items.end(), options.height, color);
    }
    std::shuffle(items.begin(), items.end(), rng);
    auto item = items.begin();
    for (std::uint32_t column = 0; column < options.colors; ++column) {
        auto& output = instance.columns.emplace_back();
        output.assign(item, item + options.height);
        item += options.height;
    }
    instance.validate();
    return instance;
}

std::vector<std::pair<std::size_t, std::size_t>> hidden_tail_positions(
    const water_sort::Instance& instance,
    std::uint32_t visible_boundaries) {
    std::vector<std::pair<std::size_t, std::size_t>> positions;
    for (std::size_t column = 0; column < instance.columns.size(); ++column) {
        const auto& items = instance.columns[column];
        std::uint32_t run = 0;
        for (std::size_t position = items.size(); position-- > 0;) {
            if (position + 1 < items.size() && items[position] != items[position + 1]) ++run;
            // Protect the visible runs plus one hidden run. This keeps the visible
            // color word and its truncated/not-truncated marker unchanged.
            if (run > visible_boundaries + 1U) positions.emplace_back(column, position);
        }
    }
    return positions;
}

bool mutate_hidden_tail(water_sort::Instance& instance,
                        std::uint32_t visible_boundaries,
                        std::uint32_t swaps,
                        std::mt19937_64& rng) {
    const auto positions = hidden_tail_positions(instance, visible_boundaries);
    if (positions.size() < 2) return false;
    std::uniform_int_distribution<std::size_t> choose(0, positions.size() - 1);
    bool changed = false;
    for (std::uint32_t swap = 0; swap < swaps; ++swap) {
        bool swapped = false;
        for (std::uint32_t attempt = 0; attempt < 64; ++attempt) {
            const auto left = positions[choose(rng)];
            const auto right = positions[choose(rng)];
            auto& left_color = instance.columns[left.first][left.second];
            auto& right_color = instance.columns[right.first][right.second];
            if (left == right || left_color == right_color) continue;
            std::swap(left_color, right_color);
            swapped = true;
            changed = true;
            break;
        }
        if (!swapped) break;
    }
    if (changed) instance.validate();
    return changed;
}

Observation canonical_observation(const water_sort::PolicyStateView& state,
                                  std::uint64_t safe_columns,
                                  std::uint32_t colors,
                                  std::uint32_t empty_columns) {
    std::vector<std::uint32_t> color_map(colors);
    std::iota(color_map.begin(), color_map.end(), 0U);
    std::string best_signature;
    std::uint64_t best_mask = 0;
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
        columns.reserve(state.columns.size());
        for (std::size_t column = 0; column < state.columns.size(); ++column) {
            const auto& view = state.columns[column];
            std::ostringstream descriptor;
            descriptor << (view.remaining_borders == 0 ? 'm' : 'b') << ':';
            for (const auto color : view.visible_runs) {
                descriptor << water_sort::color_to_char(
                    static_cast<water_sort::Color>(color_map[color]));
            }
            descriptor << (view.truncated ? '+' : '.') << ':';
            if (view.remaining_borders == 0) {
                descriptor << 'x';
            } else {
                descriptor << std::min(view.buffers_needed, need_cap);
            }
            columns.emplace_back(descriptor.str(), column);
        }
        std::stable_sort(columns.begin(), columns.end(),
                         [](const auto& left, const auto& right) {
                             return left.first < right.first;
                         });

        auto signature = prefix.str();
        std::uint64_t transformed_mask = 0;
        for (std::size_t position = 0; position < columns.size(); ++position) {
            if (position != 0) signature.push_back('/');
            signature += columns[position].first;
            if ((safe_columns & (std::uint64_t{1} << columns[position].second)) != 0) {
                transformed_mask |= std::uint64_t{1} << position;
            }
        }

        if (!have_best || signature < best_signature) {
            best_signature = std::move(signature);
            best_mask = transformed_mask;
            have_best = true;
        } else if (signature == best_signature) {
            best_mask &= transformed_mask;
        }
    } while (std::next_permutation(color_map.begin(), color_map.end()));

    return {std::move(best_signature), best_mask};
}

void add_observation(std::map<std::string, Aggregate>& aggregates,
                     Observation observation,
                     const std::string& witness) {
    auto& aggregate = aggregates[observation.signature];
    if (aggregate.occurrences == 0) {
        aggregate.common_safe = observation.safe_columns;
    } else {
        aggregate.common_safe &= observation.safe_columns;
    }
    aggregate.observed_safe |= observation.safe_columns;
    ++aggregate.occurrences;
    if (aggregate.witnesses.size() < 6) {
        aggregate.witnesses.push_back(witness + ":" + hex_mask(observation.safe_columns));
    }
}

bool process_instance(const Options& options,
                      const water_sort::Instance& instance,
                      std::map<std::string, Aggregate>& aggregates,
                      std::map<std::uint64_t, std::string>& witness_instances,
                      Totals& totals) {
    ++totals.instances;
    const auto fingerprint = water_sort::instance_fingerprint(instance);
    const auto [catalog, inserted] = witness_instances.emplace(
        fingerprint, compact_instance(instance));
    if (!inserted && catalog->second != compact_instance(instance)) {
        throw std::runtime_error("instance fingerprint collision");
    }
    const water_sort::BorderOracle oracle(instance);
    const auto table = options.goal_exhausted_columns == 0
        ? oracle.policy_table()
        : oracle.policy_table_to_exhausted_columns(options.goal_exhausted_columns);
    totals.oracle_states += table.states_evaluated;
    const bool solvable = table.solvable[table.initial_state] != 0;
    if (!solvable) {
        ++totals.unsolvable_instances;
        if (!std::filesystem::exists(options.out / "counterexample.txt")) {
            const auto proof = oracle.solve();
            if (proof.solvable) {
                throw std::runtime_error(
                    "full solution exists but the exhausted-column frontier is unreachable");
            }
            water_sort::write_instance(instance, options.out / "counterexample.txt");
            water_sort::write_no_certificate(instance, oracle.state_count(), proof.reachable_bits,
                                             options.out / "counterexample.wscert");
        }
        return !options.stop_on_no;
    }
    ++totals.solvable_instances;

    for (std::uint32_t state = 1; state < oracle.state_count(); ++state) {
        if (table.reachable[state] == 0 || table.solvable[state] == 0 ||
            table.goal[state] != 0) {
            continue;
        }
        ++totals.reachable_policy_states;
        const auto view = oracle.policy_state(state, options.depth);
        auto observation = canonical_observation(view, table.safe_columns[state],
                                                 options.colors, options.empty_columns);
        std::ostringstream witness;
        witness << std::hex << fingerprint << std::dec << ':' << state;
        add_observation(aggregates, std::move(observation), witness.str());
        ++totals.observations;
    }
    return true;
}

void write_outputs(const Options& options,
                   const std::map<std::string, Aggregate>& aggregates,
                   const std::map<std::uint64_t, std::string>& witness_instances,
                   const Totals& totals,
                   std::uint64_t effective_seed) {
    std::ofstream signatures(options.out / "signatures.tsv");
    signatures << "signature_hash\toccurrences\tcommon_safe\tobserved_safe\t"
                  "witnesses\tsignature\n";
    std::ofstream conflicts(options.out / "conflicts.tsv");
    conflicts << "signature_hash\toccurrences\tobserved_safe\twitnesses\tsignature\n";
    std::uint64_t conflict_count = 0;
    for (const auto& [signature, aggregate] : aggregates) {
        const auto hash = fnv1a(signature);
        signatures << std::hex << hash << std::dec << '\t' << aggregate.occurrences << '\t'
                   << hex_mask(aggregate.common_safe) << '\t'
                   << hex_mask(aggregate.observed_safe) << '\t';
        for (std::size_t i = 0; i < aggregate.witnesses.size(); ++i) {
            if (i != 0) signatures << ',';
            signatures << aggregate.witnesses[i];
        }
        signatures << '\t' << signature << '\n';
        if (aggregate.common_safe != 0) continue;
        ++conflict_count;
        conflicts << std::hex << hash << std::dec << '\t' << aggregate.occurrences << '\t'
                  << hex_mask(aggregate.observed_safe) << '\t';
        for (std::size_t i = 0; i < aggregate.witnesses.size(); ++i) {
            if (i != 0) conflicts << ',';
            conflicts << aggregate.witnesses[i];
        }
        conflicts << '\t' << signature << '\n';
    }

    std::ofstream instances(options.out / "instances.tsv");
    instances << "fingerprint\tinstance\n";
    for (const auto& [fingerprint, encoding] : witness_instances) {
        instances << std::hex << fingerprint << std::dec << '\t' << encoding << '\n';
    }

    std::ofstream report(options.out / "report.json");
    report << "{\n"
           << "  \"height\": " << options.height << ",\n"
           << "  \"colors\": " << options.colors << ",\n"
           << "  \"empty_columns\": " << options.empty_columns << ",\n"
           << "  \"visible_boundaries\": " << options.depth << ",\n"
           << "  \"goal_exhausted_columns\": " << options.goal_exhausted_columns << ",\n"
           << "  \"tail_mutations\": " << options.tail_mutations << ",\n"
           << "  \"tail_swaps\": " << options.tail_swaps << ",\n"
           << "  \"shard\": " << options.shard << ",\n"
           << "  \"shards\": " << options.shards << ",\n"
           << "  \"seed\": " << effective_seed << ",\n"
           << "  \"base_instances\": " << totals.base_instances << ",\n"
           << "  \"instances\": " << totals.instances << ",\n"
           << "  \"solvable_instances\": " << totals.solvable_instances << ",\n"
           << "  \"unsolvable_instances\": " << totals.unsolvable_instances << ",\n"
           << "  \"oracle_states\": " << totals.oracle_states << ",\n"
           << "  \"reachable_policy_states\": " << totals.reachable_policy_states << ",\n"
           << "  \"observations\": " << totals.observations << ",\n"
           << "  \"signatures\": " << aggregates.size() << ",\n"
           << "  \"conflicting_signatures\": " << conflict_count << "\n"
           << "}\n";

    std::cout << "instances=" << totals.instances << " policy_states="
              << totals.reachable_policy_states << " signatures=" << aggregates.size()
              << " conflicts=" << conflict_count << " no=" << totals.unsolvable_instances << '\n';
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
        else if (argument == "--shard") options.shard = std::stoul(value());
        else if (argument == "--shards") options.shards = std::stoul(value());
        else if (argument == "--height") options.height = std::stoul(value());
        else if (argument == "--colors") options.colors = std::stoul(value());
        else if (argument == "--empty") options.empty_columns = std::stoul(value());
        else if (argument == "--depth") options.depth = std::stoul(value());
        else if (argument == "--goal-exhausted") {
            options.goal_exhausted_columns = std::stoul(value());
        }
        else if (argument == "--tail-mutations") options.tail_mutations = std::stoul(value());
        else if (argument == "--tail-swaps") options.tail_swaps = std::stoul(value());
        else if (argument == "--samples") options.samples = std::stoull(value());
        else if (argument == "--stop-on-no") options.stop_on_no = std::stoi(value()) != 0;
        else if (argument == "--input") options.input = value();
        else if (argument == "--out") options.out = value();
        else if (argument == "--help") {
            std::cout << "water-policy-learn [--height H --colors C --empty K] [--depth D] "
                         "[--samples N] [--seed N] [--shard I --shards N] [--input FILE] "
                         "[--goal-exhausted N] [--tail-mutations N --tail-swaps N] "
                         "[--stop-on-no 0|1] [--out DIR]\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown argument: " + argument);
        }
    }
    if (options.height == 0 || options.colors == 0 || options.colors > 6 ||
        options.colors > 64 || options.depth == 0 || options.samples == 0 ||
        options.shards == 0 || options.shard >= options.shards ||
        options.goal_exhausted_columns > options.colors || options.tail_swaps == 0) {
        throw std::runtime_error("invalid policy-learning options");
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
    std::map<std::string, Aggregate> aggregates;
    std::map<std::uint64_t, std::string> witness_instances;
    Totals totals;

    if (!options.input.empty()) {
        totals.base_instances = 1;
        process_instance(options, water_sort::read_instance(options.input), aggregates,
                         witness_instances, totals);
    } else {
        for (std::uint64_t sample = 0; sample < options.samples; ++sample) {
            ++totals.base_instances;
            const auto base = random_instance(options, rng);
            if (!process_instance(options, base, aggregates, witness_instances, totals)) break;
            std::set<std::uint64_t> fingerprints{water_sort::instance_fingerprint(base)};
            bool keep_going = true;
            for (std::uint32_t mutation = 0;
                 mutation < options.tail_mutations && keep_going;
                 ++mutation) {
                auto variant = base;
                if (!mutate_hidden_tail(variant, options.depth, options.tail_swaps, rng)) continue;
                const auto fingerprint = water_sort::instance_fingerprint(variant);
                if (!fingerprints.insert(fingerprint).second) continue;
                keep_going = process_instance(options, variant, aggregates,
                                              witness_instances, totals);
            }
            if (!keep_going) break;
        }
    }
    write_outputs(options, aggregates, witness_instances, totals, effective_seed);
    return 0;
} catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
}
