#include "water_sort/border_oracle.hpp"
#include "water_sort/instance.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <numeric>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace {

struct Options {
    std::filesystem::path catalog;
    std::filesystem::path conflicts;
    std::filesystem::path out = "out";
    std::uint32_t depth = 3;
    std::uint32_t goal_exhausted_columns = 2;
    std::uint32_t restarts = 256;
    std::uint32_t repair_passes = 128;
    std::uint32_t max_instances = 0;
    std::uint64_t seed = 1;
    std::string heuristic;
    std::string default_heuristic;
};

struct Observation {
    std::string signature;
    std::uint64_t safe_columns = 0;
    std::vector<std::size_t> original_columns;
};

struct Model {
    water_sort::BorderOracle oracle;
    water_sort::PolicyTable table;
    std::unordered_map<std::uint32_t, Observation> cache;

    Model(water_sort::Instance instance, std::uint32_t goal)
        : oracle(std::move(instance)),
          table(oracle.policy_table_to_exhausted_columns(goal)) {}

    Model(Model&&) = default;
    Model& operator=(Model&&) = default;
    Model(const Model&) = delete;
    Model& operator=(const Model&) = delete;
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
        for (const auto value : raw_column) column.push_back(water_sort::char_to_color(value));
    }
    instance.validate();
    return instance;
}

std::vector<water_sort::Instance> read_catalog(const Options& options) {
    std::ifstream input(options.catalog);
    if (!input) throw std::runtime_error("cannot open instance catalog");
    std::string line;
    std::getline(input, line);
    std::vector<water_sort::Instance> instances;
    while (std::getline(input, line)) {
        const auto tab = line.find('\t');
        if (tab == std::string::npos) throw std::runtime_error("invalid catalog row");
        instances.push_back(parse_compact_instance(line.substr(tab + 1)));
        if (options.max_instances != 0 && instances.size() >= options.max_instances) break;
    }
    if (instances.empty()) throw std::runtime_error("instance catalog is empty");
    return instances;
}

std::unordered_set<std::string> read_conflicts(const std::filesystem::path& path) {
    std::unordered_set<std::string> result;
    if (path.empty()) return result;
    std::ifstream input(path);
    if (!input) throw std::runtime_error("cannot open conflict table");
    std::string line;
    std::getline(input, line);
    while (std::getline(input, line)) {
        const auto fields = split(line, '\t');
        if (fields.size() < 4) throw std::runtime_error("invalid conflict row");
        auto signature = fields.back();
        if (!signature.empty() && signature.back() == '\r') signature.pop_back();
        result.insert(std::move(signature));
    }
    return result;
}

Observation canonical_observation(const water_sort::PolicyStateView& state,
                                  std::uint64_t safe_columns,
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
            if (view.remaining_borders == 0) descriptor << 'x';
            else descriptor << std::min(view.buffers_needed, need_cap);
            columns.emplace_back(descriptor.str(), column);
        }
        std::stable_sort(columns.begin(), columns.end(),
                         [](const auto& left, const auto& right) {
                             return left.first < right.first;
                         });

        auto signature = prefix.str();
        std::uint64_t transformed_mask = 0;
        std::vector<std::size_t> original_columns;
        original_columns.reserve(columns.size());
        for (std::size_t position = 0; position < columns.size(); ++position) {
            if (position != 0) signature.push_back('/');
            signature += columns[position].first;
            original_columns.push_back(columns[position].second);
            if ((safe_columns & (std::uint64_t{1} << columns[position].second)) != 0) {
                transformed_mask |= std::uint64_t{1} << position;
            }
        }

        if (!have_best || signature < best.signature) {
            best.signature = std::move(signature);
            best.safe_columns = transformed_mask;
            best.original_columns = std::move(original_columns);
            have_best = true;
        }
    } while (std::next_permutation(color_map.begin(), color_map.end()));
    return best;
}

std::uint64_t transform_column_mask(
    std::uint64_t original_mask,
    const std::vector<std::size_t>& original_columns) {
    std::uint64_t transformed = 0;
    for (std::size_t position = 0; position < original_columns.size(); ++position) {
        if ((original_mask & (std::uint64_t{1} << original_columns[position])) != 0) {
            transformed |= std::uint64_t{1} << position;
        }
    }
    return transformed;
}

std::uint8_t choose_action(std::uint64_t mask, std::mt19937_64& rng) {
    if (mask == 0) throw std::runtime_error("cannot choose from an empty action mask");
    std::vector<std::uint8_t> actions;
    for (std::uint8_t action = 0; action < 64; ++action) {
        if ((mask & (std::uint64_t{1} << action)) != 0) actions.push_back(action);
    }
    std::uniform_int_distribution<std::size_t> choose(0, actions.size() - 1);
    return actions[choose(rng)];
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
        if (argument == "--catalog") options.catalog = value();
        else if (argument == "--conflicts") options.conflicts = value();
        else if (argument == "--depth") options.depth = std::stoul(value());
        else if (argument == "--goal-exhausted") {
            options.goal_exhausted_columns = std::stoul(value());
        }
        else if (argument == "--restarts") options.restarts = std::stoul(value());
        else if (argument == "--repair-passes") options.repair_passes = std::stoul(value());
        else if (argument == "--max-instances") options.max_instances = std::stoul(value());
        else if (argument == "--seed") options.seed = std::stoull(value());
        else if (argument == "--heuristic") options.heuristic = value();
        else if (argument == "--default-heuristic") options.default_heuristic = value();
        else if (argument == "--out") options.out = value();
        else if (argument == "--help") {
            std::cout << "water-policy-control --catalog FILE [--conflicts FILE] "
                         "[--depth D --goal-exhausted N] [--restarts N] "
                         "[--repair-passes N] [--max-instances N] [--seed N] "
                         "[--heuristic NAME] "
                         "[--default-heuristic NAME] "
                         "[--out DIR]\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown argument: " + argument);
        }
    }
    if (options.catalog.empty() || options.depth == 0 ||
        options.goal_exhausted_columns == 0 || options.restarts == 0 ||
        options.repair_passes == 0) {
        throw std::runtime_error("invalid controlled-policy options");
    }
    const std::unordered_set<std::string> heuristics{
        "", "first", "last", "finish", "expose", "min-need", "max-need",
        "deficient-first", "deficient-finish"};
    if (heuristics.count(options.heuristic) == 0) {
        throw std::runtime_error("unknown direct heuristic: " + options.heuristic);
    }
    if (heuristics.count(options.default_heuristic) == 0) {
        throw std::runtime_error("unknown default heuristic: " + options.default_heuristic);
    }
    if (!options.heuristic.empty() && !options.default_heuristic.empty()) {
        throw std::runtime_error("direct and default heuristics are mutually exclusive");
    }
    return options;
}

void write_report(const Options& options,
                  bool success,
                  std::uint32_t restart,
                  std::uint32_t repairs,
                  std::uint64_t traversed_states,
                  std::uint64_t verified_replay_states,
                  std::size_t model_count,
                  std::size_t completed_instances,
                  std::size_t catalog_conflicts,
                  const std::unordered_map<std::string, std::uint8_t>& choices,
                  const std::unordered_map<std::string, std::uint64_t>& final_domains,
                  const std::unordered_set<std::string>& reached_conflicts,
                  const std::string& last_failure) {
    std::filesystem::create_directories(options.out);
    std::ofstream policy(options.out / "policy.tsv");
    policy << "action\tdomain\tsignature\n";
    std::vector<std::string> signatures;
    signatures.reserve(choices.size());
    for (const auto& [signature, action] : choices) {
        static_cast<void>(action);
        signatures.push_back(signature);
    }
    std::sort(signatures.begin(), signatures.end());
    for (const auto& signature : signatures) {
        const auto domain = final_domains.find(signature);
        policy << static_cast<std::uint32_t>(choices.at(signature)) << "\t0x" << std::hex
               << (domain == final_domains.end() ? 0 : domain->second) << std::dec << '\t'
               << signature << '\n';
    }

    std::ofstream report(options.out / "report.json");
    report << "{\n"
           << "  \"mode\": \"controlled-synthesis\",\n"
           << "  \"default_heuristic\": \"" << options.default_heuristic << "\",\n"
           << "  \"success\": " << (success ? "true" : "false") << ",\n"
           << "  \"instances\": " << model_count << ",\n"
           << "  \"visible_boundaries\": " << options.depth << ",\n"
           << "  \"goal_exhausted_columns\": " << options.goal_exhausted_columns << ",\n"
           << "  \"seed\": " << options.seed << ",\n"
           << "  \"restart_limit\": " << options.restarts << ",\n"
           << "  \"restart\": " << restart << ",\n"
           << "  \"repair_passes\": " << repairs << ",\n"
           << "  \"traversed_states\": " << traversed_states << ",\n"
           << "  \"verified_replay_states\": " << verified_replay_states << ",\n"
           << "  \"completed_instances\": " << completed_instances << ",\n"
           << "  \"policy_rules\": " << choices.size() << ",\n"
           << "  \"observed_signatures\": " << final_domains.size() << ",\n"
           << "  \"catalog_global_conflicts\": " << catalog_conflicts << ",\n"
           << "  \"reached_global_conflicts\": " << reached_conflicts.size() << ",\n"
           << "  \"last_failure\": \"" << last_failure << "\"\n"
           << "}\n";
}

std::uint8_t choose_direct_heuristic(const std::string& heuristic,
                                     const Observation& observation,
                                     const water_sort::PolicyStateView& state);

std::uint64_t verify_controller(
    std::vector<Model>& models,
    const std::unordered_map<std::string, std::uint8_t>& choices,
    const Options& options,
    std::uint32_t colors,
    std::uint32_t empty_columns) {
    std::uint64_t replay_states = 0;
    for (auto& model : models) {
        auto state = model.table.initial_state;
        while (model.table.goal[state] == 0) {
            ++replay_states;
            const auto view = model.oracle.policy_state(state, options.depth);
            const auto observation = canonical_observation(
                view,
                model.table.safe_columns[state], colors, empty_columns);
            const auto choice = choices.find(observation.signature);
            std::uint8_t action = 0;
            if (choice != choices.end()) {
                action = choice->second;
            } else if (!options.default_heuristic.empty()) {
                auto legal_observation = observation;
                legal_observation.safe_columns = transform_column_mask(
                    model.table.legal_columns[state], observation.original_columns);
                action = choose_direct_heuristic(
                    options.default_heuristic, legal_observation, view);
            } else {
                throw std::runtime_error("controller replay is missing a rule");
            }
            if (action == std::numeric_limits<std::uint8_t>::max()) {
                throw std::runtime_error("controller replay reached a direct deadlock");
            }
            const auto bit = std::uint64_t{1} << action;
            if ((observation.safe_columns & bit) == 0 ||
                action >= observation.original_columns.size()) {
                throw std::runtime_error("controller replay selected an unsafe action");
            }
            state = model.oracle.policy_successor(
                state, observation.original_columns[action]);
        }
    }
    return replay_states;
}

std::uint8_t choose_direct_heuristic(const std::string& heuristic,
                                     const Observation& observation,
                                     const water_sort::PolicyStateView& state) {
    if (observation.safe_columns == 0) return std::numeric_limits<std::uint8_t>::max();
    std::uint8_t selected = 0;
    std::tuple<int, int, int, int> best_score;
    bool have_best = false;
    bool deficient = false;
    for (std::size_t color = 0; color < state.f.size(); ++color) {
        deficient = deficient || state.f[color] > state.g[color];
    }
    for (std::uint8_t position = 0;
         position < observation.original_columns.size(); ++position) {
        if ((observation.safe_columns & (std::uint64_t{1} << position)) == 0) continue;
        const auto& column = state.columns[observation.original_columns[position]];
        const auto truncated = column.truncated ? 1 : 0;
        const auto visible = static_cast<int>(column.visible_runs.size());
        const auto need = static_cast<int>(std::min<std::uint32_t>(
            column.buffers_needed, static_cast<std::uint32_t>(1000)));
        std::tuple<int, int, int, int> score;
        if (heuristic == "first") score = {position, 0, 0, 0};
        else if (heuristic == "last") score = {-position, 0, 0, 0};
        else if (heuristic == "finish") score = {truncated, visible, need, position};
        else if (heuristic == "expose") score = {-truncated, need, visible, position};
        else if (heuristic == "min-need") score = {need, truncated, visible, position};
        else if (heuristic == "max-need") score = {-need, truncated, visible, position};
        else if (heuristic == "deficient-first") {
            score = state.available_buffers == 2 && deficient
                ? std::tuple<int, int, int, int>{position, 0, 0, 0}
                : std::tuple<int, int, int, int>{-position, 0, 0, 0};
        } else if (heuristic == "deficient-finish") {
            score = state.available_buffers == 2 && deficient
                ? std::tuple<int, int, int, int>{truncated, visible, need, position}
                : std::tuple<int, int, int, int>{-position, 0, 0, 0};
        }
        else throw std::runtime_error("direct heuristic is empty");
        if (!have_best || score < best_score) {
            best_score = score;
            selected = position;
            have_best = true;
        }
    }
    return selected;
}

void evaluate_direct_heuristic(
    const Options& options,
    std::vector<Model>& models,
    const std::unordered_set<std::string>& global_conflicts,
    std::uint32_t colors,
    std::uint32_t empty_columns) {
    std::unordered_map<std::string, std::uint8_t> rules;
    std::unordered_set<std::string> reached_conflicts;
    std::vector<std::tuple<std::size_t, std::string, std::string>> failures;
    std::uint64_t traversed_states = 0;
    std::size_t completed = 0;
    std::size_t unsafe_failures = 0;
    std::size_t deadlock_failures = 0;

    for (std::size_t model_index = 0; model_index < models.size(); ++model_index) {
        auto& model = models[model_index];
        auto state_id = model.table.initial_state;
        bool failed = false;
        while (model.table.goal[state_id] == 0) {
            ++traversed_states;
            const auto state = model.oracle.policy_state(state_id, options.depth);
            const auto observation = canonical_observation(
                state, model.table.legal_columns[state_id], colors, empty_columns);
            if (global_conflicts.count(observation.signature) != 0) {
                reached_conflicts.insert(observation.signature);
            }
            const auto action = choose_direct_heuristic(
                options.heuristic, observation, state);
            if (action == std::numeric_limits<std::uint8_t>::max()) {
                ++deadlock_failures;
                if (failures.size() < 20) {
                    failures.emplace_back(model_index, "deadlock", observation.signature);
                }
                failed = true;
                break;
            }
            const auto [rule, inserted] = rules.emplace(observation.signature, action);
            if (!inserted && rule->second != action) {
                throw std::runtime_error("direct heuristic is not signature-deterministic");
            }
            const auto original_column = observation.original_columns[action];
            if ((model.table.safe_columns[state_id] &
                 (std::uint64_t{1} << original_column)) == 0) {
                ++unsafe_failures;
                if (failures.size() < 20) {
                    failures.emplace_back(model_index, "unsafe", observation.signature);
                }
                failed = true;
                break;
            }
            state_id = model.oracle.policy_successor(state_id, original_column);
        }
        if (!failed) ++completed;
    }

    std::filesystem::create_directories(options.out);
    std::vector<std::string> signatures;
    signatures.reserve(rules.size());
    for (const auto& [signature, action] : rules) {
        static_cast<void>(action);
        signatures.push_back(signature);
    }
    std::sort(signatures.begin(), signatures.end());
    std::ofstream policy(options.out / "policy.tsv");
    policy << "action\tsignature\n";
    for (const auto& signature : signatures) {
        policy << static_cast<std::uint32_t>(rules.at(signature)) << '\t'
               << signature << '\n';
    }
    std::ofstream failure_table(options.out / "failures.tsv");
    failure_table << "model\treason\tsignature\n";
    for (const auto& [model, reason, signature] : failures) {
        failure_table << model << '\t' << reason << '\t' << signature << '\n';
    }
    const auto success = completed == models.size();
    std::ofstream report(options.out / "report.json");
    report << "{\n"
           << "  \"mode\": \"direct-heuristic\",\n"
           << "  \"heuristic\": \"" << options.heuristic << "\",\n"
           << "  \"success\": " << (success ? "true" : "false") << ",\n"
           << "  \"instances\": " << models.size() << ",\n"
           << "  \"completed_instances\": " << completed << ",\n"
           << "  \"unsafe_failures\": " << unsafe_failures << ",\n"
           << "  \"deadlock_failures\": " << deadlock_failures << ",\n"
           << "  \"traversed_states\": " << traversed_states << ",\n"
           << "  \"observed_rules\": " << rules.size() << ",\n"
           << "  \"reached_global_conflicts\": " << reached_conflicts.size() << "\n"
           << "}\n";
    std::cout << "heuristic=" << options.heuristic
              << " success=" << (success ? 1 : 0)
              << " completed=" << completed << '/' << models.size()
              << " unsafe=" << unsafe_failures
              << " deadlock=" << deadlock_failures
              << " rules=" << rules.size() << '\n';
}

} // namespace

int main(int argc, char** argv) try {
    const auto options = parse_options(argc, argv);
    auto instances = read_catalog(options);
    const auto colors = instances.front().color_count;
    const auto empty_columns = instances.front().empty_columns;
    for (const auto& instance : instances) {
        if (instance.color_count != colors || instance.empty_columns != empty_columns) {
            throw std::runtime_error("catalog mixes color or empty-column counts");
        }
    }
    const auto global_conflicts = read_conflicts(options.conflicts);

    std::vector<Model> models;
    models.reserve(instances.size());
    for (auto& instance : instances) {
        models.emplace_back(std::move(instance), options.goal_exhausted_columns);
        if (models.back().table.solvable[models.back().table.initial_state] == 0) {
            throw std::runtime_error("catalog contains a frontier-unreachable instance");
        }
    }

    if (!options.heuristic.empty()) {
        evaluate_direct_heuristic(options, models, global_conflicts,
                                  colors, empty_columns);
        return 0;
    }

    std::mt19937_64 rng(options.seed);
    std::vector<std::size_t> order(models.size());
    std::iota(order.begin(), order.end(), 0U);
    std::unordered_map<std::string, std::uint8_t> best_choices;
    std::unordered_map<std::string, std::uint64_t> best_domains;
    std::unordered_set<std::string> best_reached_conflicts;
    std::string last_failure;
    std::uint64_t total_traversed = 0;
    std::uint32_t final_restart = options.restarts;
    std::uint32_t final_repairs = 0;
    std::size_t best_completed = 0;
    bool have_best = false;
    bool found = false;

    for (std::uint32_t restart = 0; restart < options.restarts && !found; ++restart) {
        std::shuffle(order.begin(), order.end(), rng);
        std::unordered_map<std::string, std::uint8_t> choices;
        for (std::uint32_t repair = 0; repair < options.repair_passes; ++repair) {
            std::unordered_map<std::string, std::uint64_t> domains;
            std::unordered_set<std::string> reached_conflicts;
            bool changed = false;
            bool hard_conflict = false;
            std::size_t completed = 0;

            for (const auto model_index : order) {
                auto& model = models[model_index];
                auto state = model.table.initial_state;
                while (model.table.goal[state] == 0) {
                    ++total_traversed;
                    auto cached = model.cache.find(state);
                    if (cached == model.cache.end()) {
                        auto observation = canonical_observation(
                            model.oracle.policy_state(state, options.depth),
                            model.table.safe_columns[state], colors, empty_columns);
                        cached = model.cache.emplace(state, std::move(observation)).first;
                    }
                    const auto& observation = cached->second;
                    if (observation.safe_columns == 0) {
                        throw std::runtime_error("frontier-winning state has no safe action");
                    }
                    auto [domain, inserted] = domains.emplace(
                        observation.signature, observation.safe_columns);
                    if (!inserted) domain->second &= observation.safe_columns;
                    if (global_conflicts.count(observation.signature) != 0) {
                        reached_conflicts.insert(observation.signature);
                    }
                    if (domain->second == 0) {
                        hard_conflict = true;
                        last_failure = observation.signature;
                        break;
                    }

                    auto choice = choices.find(observation.signature);
                    std::uint8_t action = 0;
                    if (choice == choices.end()) {
                        if (options.default_heuristic.empty()) {
                            choice = choices.emplace(observation.signature,
                                                     choose_action(domain->second, rng)).first;
                            action = choice->second;
                        } else {
                            auto legal_observation = observation;
                            legal_observation.safe_columns = transform_column_mask(
                                model.table.legal_columns[state],
                                observation.original_columns);
                            const auto view = model.oracle.policy_state(state, options.depth);
                            const auto fallback = choose_direct_heuristic(
                                options.default_heuristic, legal_observation, view);
                            if (fallback != std::numeric_limits<std::uint8_t>::max() &&
                                (domain->second &
                                 (std::uint64_t{1} << fallback)) != 0) {
                                action = fallback;
                            } else {
                                choice = choices.emplace(
                                    observation.signature,
                                    choose_action(domain->second, rng)).first;
                                action = choice->second;
                                if (!inserted) {
                                    changed = true;
                                    break;
                                }
                            }
                        }
                    } else if ((domain->second & (std::uint64_t{1} << choice->second)) == 0) {
                        choice->second = choose_action(domain->second, rng);
                        changed = true;
                        break;
                    } else {
                        action = choice->second;
                    }

                    const auto position = static_cast<std::size_t>(action);
                    if (position >= observation.original_columns.size()) {
                        throw std::runtime_error("canonical action is out of range");
                    }
                    state = model.oracle.policy_successor(
                        state, observation.original_columns[position]);
                }
                if (hard_conflict || changed) break;
                ++completed;
            }

            if (completed > best_completed || !have_best) {
                have_best = true;
                best_completed = completed;
                best_choices = choices;
                best_domains = domains;
                best_reached_conflicts = reached_conflicts;
            }
            if (hard_conflict) break;
            if (changed) continue;
            if (completed == models.size()) {
                found = true;
                best_completed = completed;
                final_restart = restart;
                final_repairs = repair + 1;
                best_choices = std::move(choices);
                best_domains = std::move(domains);
                best_reached_conflicts = std::move(reached_conflicts);
                break;
            }
        }
    }

    if (found) {
        for (auto rule = best_choices.begin(); rule != best_choices.end();) {
            if (best_domains.count(rule->first) == 0) rule = best_choices.erase(rule);
            else ++rule;
        }
    }
    const auto verified_replay_states = found
        ? verify_controller(models, best_choices, options, colors, empty_columns)
        : 0;
    write_report(options, found, final_restart, final_repairs, total_traversed,
                 verified_replay_states, models.size(), best_completed,
                 global_conflicts.size(), best_choices, best_domains,
                 best_reached_conflicts, last_failure);
    std::cout << "success=" << (found ? 1 : 0) << " instances=" << models.size()
              << " rules=" << best_choices.size()
              << " reached_conflicts=" << best_reached_conflicts.size()
              << " traversed=" << total_traversed << '\n';
    return 0;
} catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
}
