#include "water_sort/border_oracle.hpp"
#include "water_sort/instance.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
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

using water_sort::Color;
using water_sort::Instance;

constexpr std::uint32_t kHeight = 7;
constexpr std::uint32_t kColors = 4;
constexpr std::uint32_t kEmpty = 2;
constexpr Color kQ = 0;
constexpr Color kB = 1;
constexpr Color kY = 2;
constexpr Color kX = 3;
constexpr std::uint64_t kExpectedLabeledLayouts = 381360;
constexpr std::uint64_t kExpectedLocalLosing = 2226;

struct Options {
    std::filesystem::path output_dir;
    std::uint64_t limit = 0;
    bool self_test = false;
};

struct PairKey {
    int s = 0;
    int u = 0;

    bool operator<(const PairKey& other) const {
        return std::tie(s, u) < std::tie(other.s, other.u);
    }
};

using Suffix = std::array<Color, 12>;

struct PrefixDecoration {
    std::array<std::vector<Color>, 4> columns;
};

struct PairStats {
    std::uint64_t suffix_decorations = 0;
    std::uint64_t prefix_arrangements = 0;
    std::uint64_t labeled_expected = 0;
    std::uint64_t labeled_checked = 0;
    std::uint64_t yes = 0;
    std::uint64_t no = 0;
    std::uint64_t canonical_unique = 0;
    std::uint64_t canonical_yes = 0;
    std::uint64_t canonical_no = 0;
    std::uint64_t oracle_states = 0;
    std::uint64_t max_oracle_states = 0;
    std::uint64_t oracle_transitions = 0;
    std::array<std::uint64_t, 4> first_action_counts{};
    std::optional<std::string> witness_encoding;
    std::vector<std::uint8_t> witness_moves;
};

struct RunStats {
    bool self_checks_passed = false;
    bool universe_complete = false;
    bool stopped_on_no = false;
    std::uint64_t labeled_checked = 0;
    std::uint64_t unique_checked = 0;
    std::uint64_t yes = 0;
    std::uint64_t no = 0;
    std::uint64_t unique_yes = 0;
    std::uint64_t unique_no = 0;
    std::uint64_t oracle_states_visited = 0;
    std::uint64_t oracle_transitions_tested = 0;
    std::uint64_t canonical_cache_hits = 0;
    double elapsed_seconds = 0.0;
    std::map<PairKey, PairStats> pairs;
    std::optional<std::array<std::string, 4>> no_columns;
};

void usage() {
    std::cerr << "Usage: water-c4-h7-tq-gate-check --output-dir DIR "
                 "[--limit N] [--self-test]\n";
}

Options parse_options(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        if (argument == "--output-dir" && i + 1 < argc) {
            options.output_dir = argv[++i];
        } else if (argument == "--limit" && i + 1 < argc) {
            options.limit = std::stoull(argv[++i]);
        } else if (argument == "--self-test") {
            options.self_test = true;
        } else if (argument == "--help") {
            usage();
            std::exit(0);
        } else {
            usage();
            throw std::runtime_error("unknown or incomplete argument: " + argument);
        }
    }
    if (options.output_dir.empty()) {
        usage();
        throw std::runtime_error("--output-dir is required");
    }
    return options;
}

std::vector<Suffix> enumerate_suffixes(int s) {
    std::vector<Suffix> result;
    Suffix word{};
    std::array<int, 4> remaining{0, s, 6, 6 - s};
    std::function<void(std::size_t)> visit = [&](std::size_t position) {
        if (position == word.size()) {
            result.push_back(word);
            return;
        }
        for (Color color : {kB, kY, kX}) {
            if (remaining[color] == 0) continue;
            --remaining[color];
            word[position] = color;
            visit(position + 1);
            ++remaining[color];
        }
    };
    visit(0);
    return result;
}

std::vector<PrefixDecoration> enumerate_prefixes(int u) {
    if (u < 1 || u > 5) throw std::runtime_error("u is outside [1,5]");

    PrefixDecoration decoration;
    const std::array<int, 4> lengths{3, 3, 3, u};
    std::vector<std::pair<std::size_t, std::size_t>> free_slots;
    for (std::size_t column = 0; column < lengths.size(); ++column) {
        decoration.columns[column].assign(static_cast<std::size_t>(lengths[column]), kQ);
        for (int position = 1; position < lengths[column]; ++position) {
            free_slots.emplace_back(column, static_cast<std::size_t>(position));
        }
    }

    std::array<int, 4> remaining{3, 0, 1, 1 + u};
    std::vector<PrefixDecoration> result;
    std::function<void(std::size_t)> visit = [&](std::size_t slot) {
        if (slot == free_slots.size()) {
            result.push_back(decoration);
            return;
        }
        const auto [column, position] = free_slots[slot];
        for (Color color : {kQ, kY, kX}) {
            if (remaining[color] == 0) continue;
            --remaining[color];
            decoration.columns[column][position] = color;
            visit(slot + 1);
            ++remaining[color];
        }
    };
    visit(0);
    return result;
}

Instance make_instance(int s, int u, const Suffix& suffix,
                       const PrefixDecoration& prefix) {
    Instance instance;
    instance.height = kHeight;
    instance.color_count = kColors;
    instance.empty_columns = kEmpty;
    instance.columns.resize(kColors);

    for (std::size_t column = 0; column < 3; ++column) {
        auto& output = instance.columns[column];
        output.insert(output.end(), suffix.begin() + static_cast<std::ptrdiff_t>(4 * column),
                      suffix.begin() + static_cast<std::ptrdiff_t>(4 * column + 4));
        output.insert(output.end(), prefix.columns[column].begin(),
                      prefix.columns[column].end());
    }
    auto& special = instance.columns[3];
    special.insert(special.end(), static_cast<std::size_t>(kHeight - s), kB);
    special.insert(special.end(), static_cast<std::size_t>(s - u), kX);
    special.insert(special.end(), prefix.columns[3].begin(), prefix.columns[3].end());
    instance.validate();
    return instance;
}

// Exact Ito top-border recursion beginning at the P_{s,u} checkpoint rather
// than at the initial tops.  This duplicates the small recurrence used by
// BorderOracle so the local-suffix census does not depend on a heuristic.
class CheckpointSolver {
public:
    CheckpointSolver(const Instance& instance, const std::array<int, 4>& border_positions)
        : instance_(instance) {
        std::uint32_t product = 1;
        for (std::size_t column = 0; column < kColors; ++column) {
            auto& data = columns_[column];
            data.borders.push_back(0);
            for (std::uint32_t position = 1; position < kHeight; ++position) {
                if (instance_.columns[column][position - 1] !=
                    instance_.columns[column][position]) {
                    data.borders.push_back(position);
                }
            }
            data.multiplier = product;
            product *= static_cast<std::uint32_t>(data.borders.size());

            const auto wanted = static_cast<std::uint32_t>(border_positions[column]);
            const auto found = std::find(data.borders.begin(), data.borders.end(), wanted);
            if (found == data.borders.end()) {
                throw std::runtime_error("checkpoint is not a physical color border");
            }
            initial_state_ += static_cast<std::uint32_t>(found - data.borders.begin()) *
                              data.multiplier;

            data.f.resize(data.borders.size());
            data.g.resize(data.borders.size());
            for (std::size_t rank = 0; rank < data.borders.size(); ++rank) {
                data.f[rank].fill(0);
                data.g[rank].fill(0);
                const auto border = data.borders[rank];
                for (auto position = border; position < kHeight; ++position) {
                    ++data.f[rank][instance_.columns[column][position]];
                }
                if (border != 0) {
                    data.g[rank][instance_.columns[column][border]] =
                        static_cast<std::uint16_t>(kHeight - border);
                }
            }
        }
        memo_.assign(product, -1);
        memo_[0] = 1;
    }

    bool solve() { return visit(initial_state_); }

    std::uint32_t state_id() const { return initial_state_; }

private:
    struct ColumnData {
        std::vector<std::uint32_t> borders;
        std::vector<std::array<std::uint16_t, 4>> f;
        std::vector<std::array<std::uint16_t, 4>> g;
        std::uint32_t multiplier = 0;
    };

    const Instance& instance_;
    std::array<ColumnData, 4> columns_;
    std::uint32_t initial_state_ = 0;
    std::vector<std::int8_t> memo_;

    bool visit(std::uint32_t state) {
        if (memo_[state] >= 0) return memo_[state] != 0;

        std::array<std::uint32_t, 4> ranks{};
        std::array<std::uint32_t, 4> f{};
        std::array<std::uint32_t, 4> g{};
        std::uint32_t available = kEmpty;
        for (std::size_t column = 0; column < kColors; ++column) {
            const auto& data = columns_[column];
            const auto rank = (state / data.multiplier) % data.borders.size();
            ranks[column] = static_cast<std::uint32_t>(rank);
            if (rank == 0) ++available;
            for (std::size_t color = 0; color < kColors; ++color) {
                f[color] += data.f[rank][color];
                g[color] += data.g[rank][color];
            }
        }

        for (std::size_t column = 0; column < kColors; ++column) {
            const auto rank = ranks[column];
            if (rank == 0) continue;
            const auto& data = columns_[column];
            const auto border = data.borders[rank];
            const auto top = instance_.columns[column][border];
            std::uint32_t needed = 0;
            for (std::size_t color = 0; color < kColors; ++color) {
                auto usable = g[color];
                if (color == top) usable -= kHeight - border;
                if (f[color] > usable) {
                    needed += (f[color] - usable + kHeight - 1) / kHeight;
                }
            }
            if (needed <= available && visit(state - data.multiplier)) {
                memo_[state] = 1;
                return true;
            }
        }
        memo_[state] = 0;
        return false;
    }
};

std::array<int, 4> checkpoint_positions(int u) {
    return {4, 4, 4, static_cast<int>(kHeight) - u};
}

std::map<PairKey, std::vector<Suffix>> enumerate_local_losing() {
    std::map<PairKey, std::vector<Suffix>> result;
    for (int s = 2; s <= 6; ++s) {
        const auto suffixes = enumerate_suffixes(s);
        for (int u = 1; u < s; ++u) {
            auto prefixes = enumerate_prefixes(u);
            if (prefixes.empty()) throw std::runtime_error("empty prefix family");
            auto& losing = result[{s, u}];
            for (const auto& suffix : suffixes) {
                const auto instance = make_instance(s, u, suffix, prefixes.front());
                CheckpointSolver solver(instance, checkpoint_positions(u));
                if (!solver.solve()) losing.push_back(suffix);
            }
        }
    }
    return result;
}

std::uint32_t target_state_id(const Instance& instance,
                              const std::array<int, 4>& positions) {
    std::uint32_t multiplier = 1;
    std::uint32_t state = 0;
    for (std::size_t column = 0; column < kColors; ++column) {
        std::vector<std::uint32_t> borders{0};
        for (std::uint32_t position = 1; position < kHeight; ++position) {
            if (instance.columns[column][position - 1] !=
                instance.columns[column][position]) {
                borders.push_back(position);
            }
        }
        const auto wanted = static_cast<std::uint32_t>(positions[column]);
        const auto found = std::find(borders.begin(), borders.end(), wanted);
        if (found == borders.end()) throw std::runtime_error("target border missing");
        state += static_cast<std::uint32_t>(found - borders.begin()) * multiplier;
        multiplier *= static_cast<std::uint32_t>(borders.size());
    }
    return state;
}

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error("self-check failed: " + message);
}

void verify_local_census(const std::map<PairKey, std::vector<Suffix>>& losing,
                         bool cross_check_oracle) {
    const std::map<PairKey, std::uint64_t> expected{
        {{2, 1}, 0},   {{3, 1}, 84},  {{3, 2}, 84},  {{4, 1}, 252},
        {{4, 2}, 252}, {{4, 3}, 462}, {{5, 1}, 252}, {{5, 2}, 252},
        {{5, 3}, 336}, {{5, 4}, 0},   {{6, 1}, 84},  {{6, 2}, 84},
        {{6, 3}, 84},  {{6, 4}, 0},   {{6, 5}, 0},
    };
    require(losing.size() == expected.size(), "candidate pair count is not 15");
    std::uint64_t total = 0;
    std::uint64_t nonzero = 0;
    for (const auto& [pair, wanted] : expected) {
        const auto found = losing.find(pair);
        require(found != losing.end(), "missing (s,u) pair");
        require(found->second.size() == wanted, "local losing matrix mismatch");
        total += found->second.size();
        if (!found->second.empty()) ++nonzero;
    }
    require(total == kExpectedLocalLosing, "local losing total is not 2226");
    require(nonzero == 11, "nonzero local pair count is not 11");

    const std::map<int, std::uint64_t> expected_suffixes{
        {1, 5544}, {2, 13860}, {3, 18480}, {4, 13860}, {5, 5544}, {6, 924},
    };
    for (const auto& [s, wanted] : expected_suffixes) {
        require(enumerate_suffixes(s).size() == wanted, "raw suffix count mismatch");
    }
    const std::map<int, std::uint64_t> expected_prefixes{
        {1, 60}, {2, 140}, {3, 280}, {4, 504}, {5, 840},
    };
    for (const auto& [u, wanted] : expected_prefixes) {
        require(enumerate_prefixes(u).size() == wanted, "prefix count mismatch");
    }

    std::uint64_t labeled = 0;
    for (const auto& [pair, suffixes] : losing) {
        labeled += suffixes.size() * enumerate_prefixes(pair.u).size();
    }
    require(labeled == kExpectedLabeledLayouts, "labeled universe is not 381360");

    // If x_s is the only legal source at C_s and its final hidden run is b,
    // exhausting it changes d by s*e_x + (7-s)*e_b and increments z.  This is
    // deliberately not the same-z live-edge update s*(e_x-e_b).
    for (int s = 1; s <= 6; ++s) {
        std::array<int, 4> debt{-2, 0, 1, 1};
        debt[kX] += s;
        debt[kB] += static_cast<int>(kHeight) - s;
        require(debt == std::array<int, 4>{-2, 7 - s, 1, 1 + s},
                "C_s exhausting update does not produce the Tq debt");
    }

    if (!cross_check_oracle) return;
    // Cross-check one losing checkpoint from each nonzero pair against the
    // production BorderOracle policy table.  This also checks mixed-radix
    // state encoding and the exhausting transition handled at rank zero.
    for (const auto& [pair, suffixes] : losing) {
        if (suffixes.empty()) continue;
        const auto prefix = enumerate_prefixes(pair.u).front();
        const auto instance = make_instance(pair.s, pair.u, suffixes.front(), prefix);
        const auto state = target_state_id(instance, checkpoint_positions(pair.u));
        const water_sort::BorderOracle oracle(instance);
        const auto policy = oracle.policy_table();
        require(state < policy.solvable.size(), "checkpoint state out of range");
        require(policy.solvable[state] == 0, "local DP disagrees with BorderOracle");
    }
}

std::string instance_encoding(const Instance& instance) {
    std::ostringstream output;
    for (std::size_t column = 0; column < instance.columns.size(); ++column) {
        if (column != 0) output << '|';
        for (const auto color : instance.columns[column]) {
            output << water_sort::color_to_char(color);
        }
    }
    return output.str();
}

std::string moves_encoding(const std::vector<std::uint8_t>& moves) {
    std::string result;
    result.reserve(moves.size());
    for (const auto move : moves) result.push_back(static_cast<char>('0' + move));
    return result;
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

std::string status(const RunStats& stats) {
    if (stats.stopped_on_no) return "NO_FOUND";
    if (!stats.universe_complete) return "INCOMPLETE";
    return "ALL_YES";
}

void write_report(const Options& options, const RunStats& stats) {
    std::filesystem::create_directories(options.output_dir);
    const auto json_path = options.output_dir / "report.json";
    const auto markdown_path = options.output_dir / "report.md";

    std::ofstream json(json_path);
    if (!json) throw std::runtime_error("cannot write " + json_path.string());
    json << "{\n"
         << "  \"schema_version\": 1,\n"
         << "  \"verified\": "
         << (stats.self_checks_passed && (stats.universe_complete || stats.stopped_on_no)
                 ? "true"
                 : "false")
         << ",\n"
         << "  \"status\": \"" << status(stats) << "\",\n"
         << "  \"universe_complete\": " << (stats.universe_complete ? "true" : "false")
         << ",\n"
         << "  \"candidate_pairs_total\": 15,\n"
         << "  \"nonzero_losing_pairs\": 11,\n"
         << "  \"zero_losing_pairs\": 4,\n"
         << "  \"local_losing_decorations\": 2226,\n"
         << "  \"per_u_prefix_arrangements\": {\"1\": 60, \"2\": 140, \"3\": 280},\n"
         << "  \"labeled_layouts_expected\": " << kExpectedLabeledLayouts << ",\n"
         << "  \"labeled_layouts_checked\": " << stats.labeled_checked << ",\n"
         << "  \"unique_layouts_checked\": " << stats.unique_checked << ",\n"
         << "  \"yes_count\": " << stats.yes << ",\n"
         << "  \"no_count\": " << stats.no << ",\n"
         << "  \"unique_yes_count\": " << stats.unique_yes << ",\n"
         << "  \"unique_no_count\": " << stats.unique_no << ",\n"
         << "  \"canonical_cache_hits\": " << stats.canonical_cache_hits << ",\n"
         << "  \"oracle_states_visited\": " << stats.oracle_states_visited << ",\n"
         << "  \"oracle_transitions_tested\": " << stats.oracle_transitions_tested << ",\n"
         << "  \"elapsed_seconds\": " << std::fixed << std::setprecision(6)
         << stats.elapsed_seconds << ",\n"
         << "  \"orientation\": \"all column strings are bottom-to-top\",\n"
         << "  \"construction\": \"q=0,b=1,y=2,x=3; columns 0..2 are "
            "4-cell suffix plus 3-cell prefix; column 3 is b^(7-s),x^(s-u),"
            "u-cell prefix; every prefix begins with q\",\n"
         << "  \"pairs\": [\n";

    bool first = true;
    for (const auto& [pair, pair_stats] : stats.pairs) {
        if (!first) json << ",\n";
        first = false;
        json << "    {\"s\": " << pair.s << ", \"u\": " << pair.u
             << ", \"local_losing\": " << pair_stats.suffix_decorations
             << ", \"prefix_arrangements\": " << pair_stats.prefix_arrangements
             << ", \"labeled_layouts\": " << pair_stats.labeled_expected
             << ", \"labeled_checked\": " << pair_stats.labeled_checked
             << ", \"yes_count\": " << pair_stats.yes
             << ", \"no_count\": " << pair_stats.no
             << ", \"canonical_unique\": " << pair_stats.canonical_unique
             << ", \"canonical_yes\": " << pair_stats.canonical_yes
             << ", \"canonical_no\": " << pair_stats.canonical_no
             << ", \"oracle_states\": " << pair_stats.oracle_states
             << ", \"max_oracle_states\": " << pair_stats.max_oracle_states
             << ", \"oracle_transitions\": " << pair_stats.oracle_transitions
             << ", \"first_action_counts\": [" << pair_stats.first_action_counts[0]
             << ", " << pair_stats.first_action_counts[1] << ", "
             << pair_stats.first_action_counts[2] << ", "
             << pair_stats.first_action_counts[3] << ']';
        if (pair_stats.witness_encoding) {
            std::array<std::string, 4> columns;
            std::istringstream input(*pair_stats.witness_encoding);
            for (auto& column : columns) std::getline(input, column, '|');
            json << ", \"solvable_witness\": {\"columns\": [";
            for (std::size_t i = 0; i < columns.size(); ++i) {
                if (i != 0) json << ", ";
                json << '"' << json_escape(columns[i]) << '"';
            }
            json << "], \"encoding\": \""
                 << json_escape(*pair_stats.witness_encoding)
                 << "\", \"removal_columns\": \""
                 << moves_encoding(pair_stats.witness_moves) << "\"}";
        }
        json << '}';
    }
    json << "\n  ]";
    if (stats.no_columns) {
        json << ",\n  \"no_witness\": {\"orientation\": \"bottom-to-top\", \"columns\": [";
        for (std::size_t i = 0; i < stats.no_columns->size(); ++i) {
            if (i != 0) json << ", ";
            json << '"' << json_escape((*stats.no_columns)[i]) << '"';
        }
        json << "]}";
    }
    json << "\n}\n";

    std::ofstream markdown(markdown_path);
    if (!markdown) throw std::runtime_error("cannot write " + markdown_path.string());
    markdown << "# c=4, h=7, k=2 Tq gate targeted census\n\n"
             << "- Status: **" << status(stats) << "**\n"
             << "- Local checkpoint census: 15 `(s,u)` pairs, 11 nonzero, 4 zero, "
                "2,226 losing suffix decorations.\n"
             << "- Labeled full layouts: " << stats.labeled_checked << " / "
             << kExpectedLabeledLayouts << "\n"
             << "- Canonical unique layouts checked: " << stats.unique_checked << "\n"
             << "- Exact results (labeled): YES=" << stats.yes << ", NO=" << stats.no
             << "\n"
             << "- Orientation: every stored column is bottom-to-top.\n\n"
             << "| s | u | losing suffixes | prefixes | labeled expected | checked | YES | NO |\n"
             << "|---:|---:|---:|---:|---:|---:|---:|---:|\n";
    for (const auto& [pair, pair_stats] : stats.pairs) {
        markdown << "| " << pair.s << " | " << pair.u << " | "
                 << pair_stats.suffix_decorations << " | "
                 << pair_stats.prefix_arrangements << " | "
                 << pair_stats.labeled_expected << " | "
                 << pair_stats.labeled_checked << " | " << pair_stats.yes << " | "
                 << pair_stats.no << " |\n";
    }
}

RunStats run(const Options& options,
             const std::map<PairKey, std::vector<Suffix>>& losing) {
    RunStats stats;
    for (const auto& [pair, suffixes] : losing) {
        auto& pair_stats = stats.pairs[pair];
        pair_stats.suffix_decorations = suffixes.size();
        pair_stats.prefix_arrangements = enumerate_prefixes(pair.u).size();
        pair_stats.labeled_expected =
            pair_stats.suffix_decorations * pair_stats.prefix_arrangements;
    }
    stats.self_checks_passed = true;

    struct CachedResult {
        bool solvable = false;
    };
    std::unordered_map<std::string, CachedResult> global_unique;
    global_unique.reserve(100000);
    std::optional<Instance> first_no;
    const auto effective_limit =
        options.limit == 0 ? kExpectedLabeledLayouts
                           : std::min(options.limit, kExpectedLabeledLayouts);

    const auto started = std::chrono::steady_clock::now();
    bool stop = false;
    for (const auto& [pair, suffixes] : losing) {
        std::unordered_map<std::string, CachedResult> pair_cache;
        pair_cache.reserve(static_cast<std::size_t>(
            std::min<std::uint64_t>(stats.pairs.at(pair).labeled_expected, 50000)));
        auto prefixes = enumerate_prefixes(pair.u);
        auto& pair_stats = stats.pairs.at(pair);
        for (const auto& suffix : suffixes) {
            for (const auto& prefix : prefixes) {
                if (stats.labeled_checked >= effective_limit) {
                    stop = true;
                    break;
                }
                const auto instance = make_instance(pair.s, pair.u, suffix, prefix);
                const auto canonical = water_sort::canonical_encoding(instance);
                bool solvable = false;
                std::vector<std::uint8_t> witness;
                const auto cached = pair_cache.find(canonical);
                if (cached == pair_cache.end()) {
                    const water_sort::BorderOracle oracle(instance);
                    auto result = oracle.solve();
                    solvable = result.solvable;
                    witness = std::move(result.removal_columns);
                    stats.oracle_states_visited += result.states_visited;
                    stats.oracle_transitions_tested += result.transitions_tested;
                    pair_cache.emplace(canonical, CachedResult{solvable});
                    ++pair_stats.canonical_unique;
                    if (solvable) ++pair_stats.canonical_yes;
                    else ++pair_stats.canonical_no;
                    pair_stats.oracle_states += result.states_visited;
                    pair_stats.max_oracle_states =
                        std::max(pair_stats.max_oracle_states, result.states_visited);
                    pair_stats.oracle_transitions += result.transitions_tested;
                    if (solvable && !witness.empty()) {
                        ++pair_stats.first_action_counts[witness.front()];
                    }
                    const auto [global_it, inserted] =
                        global_unique.emplace(canonical, CachedResult{solvable});
                    static_cast<void>(global_it);
                    if (inserted) {
                        ++stats.unique_checked;
                        if (solvable) ++stats.unique_yes;
                        else ++stats.unique_no;
                    }
                } else {
                    ++stats.canonical_cache_hits;
                    solvable = cached->second.solvable;
                }

                ++stats.labeled_checked;
                ++pair_stats.labeled_checked;
                if (solvable) {
                    ++stats.yes;
                    ++pair_stats.yes;
                    if (!pair_stats.witness_encoding) {
                        if (witness.empty()) {
                            const water_sort::BorderOracle oracle(instance);
                            witness = oracle.solve().removal_columns;
                        }
                        pair_stats.witness_encoding = instance_encoding(instance);
                        pair_stats.witness_moves = std::move(witness);
                    }
                } else {
                    ++stats.no;
                    ++pair_stats.no;
                    first_no = instance;
                    std::array<std::string, 4> columns;
                    for (std::size_t i = 0; i < columns.size(); ++i) {
                        for (const auto color : instance.columns[i]) {
                            columns[i].push_back(water_sort::color_to_char(color));
                        }
                    }
                    stats.no_columns = columns;
                    stats.stopped_on_no = true;
                    stop = true;
                    break;
                }
            }
            if (stop) break;
        }
        if (stop) break;
    }
    stats.universe_complete =
        !stats.stopped_on_no && stats.labeled_checked == kExpectedLabeledLayouts;
    stats.elapsed_seconds = std::chrono::duration<double>(
                                std::chrono::steady_clock::now() - started)
                                .count();

    if (first_no) {
        std::filesystem::create_directories(options.output_dir);
        water_sort::write_instance(*first_no, options.output_dir / "no-instance.txt");
    }
    return stats;
}

} // namespace

int main(int argc, char** argv) try {
    const auto options = parse_options(argc, argv);
    std::filesystem::create_directories(options.output_dir);

    std::cout << "Enumerating exact local P_{s,u} checkpoint losses...\n";
    const auto losing = enumerate_local_losing();
    verify_local_census(losing, options.self_test);
    std::cout << "Local census verified: 15 pairs, 11 nonzero, 2226 decorations.\n";

    auto stats = run(options, losing);
    write_report(options, stats);
    std::cout << "status=" << status(stats)
              << " labeled=" << stats.labeled_checked << '/' << kExpectedLabeledLayouts
              << " unique=" << stats.unique_checked << " yes=" << stats.yes
              << " no=" << stats.no << " seconds=" << std::fixed
              << std::setprecision(3) << stats.elapsed_seconds << '\n';
    std::cout << "report=" << (options.output_dir / "report.json").string() << '\n';
    return 0;
} catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
}
