#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
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

constexpr int kHeight = 7;
constexpr int kColors = 4;
constexpr int kEmpty = 2;
constexpr std::uint64_t kCheckpointFutures = 1'106'490;
constexpr std::uint64_t kCheckpointLocalNo = 14'784;
constexpr std::uint64_t kBalancedRestorations = 285'600;
constexpr std::uint64_t kReachableRestorations = 281'904;
constexpr std::uint64_t kFNVOffset = 1'469'598'103'934'665'603ULL;
constexpr std::uint64_t kFNVPrime = 1'099'511'628'211ULL;

using Debts = std::array<int, kColors>;
using Words = std::array<std::string, kColors>;

struct Options {
    std::filesystem::path checkpoint_report;
    std::filesystem::path output_dir;
    std::uint64_t limit_restorations = 0;
    bool self_test = false;
};

struct ParentSpec {
    int edge = 0;
    Debts debts{};
    std::array<int, 3> bad{}; // old colour, old cap, final colour
    int q_color = 0;
    std::array<int, 3> q_caps{};
    std::uint64_t local_no_rows = 0;
    std::uint64_t prefix_candidates = 0;
    std::uint64_t prefix_reachable = 0;
    std::uint64_t legal_histories = 0;

    std::array<int, kColors> caps() const {
        return {{bad[1], q_caps[0], q_caps[1], q_caps[2]}};
    }
};

struct PastEvent {
    int old_color = 0;
    int old_cap = 0;
    int next_color = 0;
};

struct PrefixTemplate {
    std::size_t ordinal = 0;
    Words words_top_to_bottom;
    bool reachable = false;
    std::uint64_t legal_histories = 0;
    std::string first_witness;
};

struct LedgerRow {
    std::uint64_t future_index = 0;
    std::uint64_t decoration_index = 0;
    std::size_t spec_index = 0;
    Words hidden_bottom_to_top;
};

struct SolverResult {
    bool solvable = false;
    std::uint32_t safe_mask = 0;
    std::string path;
    std::uint64_t states = 0;
    std::uint64_t transitions = 0;
};

struct CanonicalLayout {
    Words columns_top_to_bottom;
    std::array<int, kColors> canonical_to_original{};
    std::string key;
};

struct Sample {
    bool present = false;
    std::uint64_t restoration_index = 0;
    std::uint64_t future_index = 0;
    int edge = 0;
    std::size_t prefix_index = 0;
    bool reachable = false;
    bool solvable = false;
    Words columns_top_to_bottom;
    Words columns_bottom_to_top;
    std::uint32_t safe_mask = 0;
    std::string path;
};

struct EdgeStats {
    int edge = 0;
    std::uint64_t local_no_rows = 0;
    std::uint64_t prefix_candidates = 0;
    std::uint64_t prefix_reachable = 0;
    std::uint64_t legal_histories = 0;
    std::uint64_t balanced_expected = 0;
    std::uint64_t reachable_expected = 0;
    std::uint64_t checked = 0;
    std::uint64_t reachable_checked = 0;
    std::uint64_t initial_yes = 0;
    std::uint64_t initial_no = 0;
};

struct RunStats {
    std::uint64_t limit_requested = 0;
    bool universe_complete = false;
    std::uint64_t restorations_checked = 0;
    std::uint64_t reachable_checked = 0;
    std::uint64_t unreachable_checked = 0;
    std::uint64_t initial_yes = 0;
    std::uint64_t initial_no = 0;
    std::uint64_t witnesses_replayed = 0;
    std::uint64_t canonical_classes_solved = 0;
    std::uint64_t symmetry_cache_hits = 0;
    std::uint64_t states = 0;
    std::uint64_t transitions = 0;
    std::uint64_t result_hash = kFNVOffset;
    double elapsed_seconds = 0.0;
    bool self_checks_passed = false;
    std::vector<EdgeStats> per_edge;
    std::optional<Sample> first_yes;
    std::optional<Sample> first_no;
};

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error("self-check failed: " + message);
}

std::vector<ParentSpec> expected_specs() {
    return {
        {116, {{-4, 0, 1, 3}}, {{0, 4, 1}}, 0, {{1, 1, 5}},
         210, 140, 140, 1184},
        {117, {{-4, 0, 2, 2}}, {{0, 4, 1}}, 0, {{1, 1, 5}},
         252, 210, 210, 2076},
        {184, {{-3, 0, 1, 2}}, {{0, 2, 1}}, 0, {{2, 2, 4}},
         462, 60, 60, 348},
        {236, {{-2, 0, 1, 1}}, {{0, 2, 1}}, 0, {{1, 1, 3}},
         924, 6, 6, 12},
        {242, {{-2, 0, 1, 1}}, {{0, 2, 1}}, 0, {{1, 2, 3}},
         11088, 12, 12, 26},
        {244, {{-2, 0, 1, 1}}, {{0, 2, 1}}, 0, {{1, 2, 4}},
         924, 20, 16, 30},
        {248, {{-2, 0, 1, 1}}, {{0, 2, 1}}, 0, {{2, 2, 3}},
         924, 20, 20, 44},
    };
}

void usage() {
    std::cerr
        << "Usage: water-c4-h7-d2-three-source-past "
           "--checkpoint-report PATH --output-dir DIR "
           "[--limit-restorations N] [--self-test]\n";
}

Options parse_options(int argc, char** argv) {
    Options options;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--checkpoint-report" && index + 1 < argc) {
            options.checkpoint_report = argv[++index];
        } else if (argument == "--output-dir" && index + 1 < argc) {
            options.output_dir = argv[++index];
        } else if (argument == "--limit-restorations" && index + 1 < argc) {
            options.limit_restorations = std::stoull(argv[++index]);
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
    return options;
}

std::string read_text(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("cannot open " + path.string());
    std::ostringstream buffer;
    buffer << input.rdbuf();
    return buffer.str();
}

std::size_t key_position(const std::string& text, const std::string& key) {
    const std::string needle = "\"" + key + "\"";
    const std::size_t found = text.find(needle);
    if (found == std::string::npos) {
        throw std::runtime_error("JSON key is missing: " + key);
    }
    const std::size_t colon = text.find(':', found + needle.size());
    if (colon == std::string::npos) {
        throw std::runtime_error("JSON key has no value: " + key);
    }
    std::size_t value = colon + 1;
    while (value < text.size() &&
           std::isspace(static_cast<unsigned char>(text[value])) != 0) {
        ++value;
    }
    return value;
}

std::string json_object(const std::string& text, const std::string& key) {
    const std::size_t start = key_position(text, key);
    require(start < text.size() && text[start] == '{', key + " is not an object");
    int depth = 0;
    bool quoted = false;
    bool escaped = false;
    for (std::size_t cursor = start; cursor < text.size(); ++cursor) {
        const char value = text[cursor];
        if (quoted) {
            if (escaped) escaped = false;
            else if (value == '\\') escaped = true;
            else if (value == '"') quoted = false;
            continue;
        }
        if (value == '"') quoted = true;
        else if (value == '{') ++depth;
        else if (value == '}' && --depth == 0) {
            return text.substr(start, cursor - start + 1);
        }
    }
    throw std::runtime_error("unterminated JSON object: " + key);
}

std::int64_t json_integer(const std::string& text, const std::string& key) {
    std::size_t cursor = key_position(text, key);
    const std::size_t begin = cursor;
    if (cursor < text.size() && text[cursor] == '-') ++cursor;
    while (cursor < text.size() &&
           std::isdigit(static_cast<unsigned char>(text[cursor])) != 0) {
        ++cursor;
    }
    require(cursor > begin && !(cursor == begin + 1 && text[begin] == '-'),
            key + " is not an integer");
    return std::stoll(text.substr(begin, cursor - begin));
}

bool json_boolean(const std::string& text, const std::string& key) {
    const std::size_t cursor = key_position(text, key);
    if (text.compare(cursor, 4, "true") == 0) return true;
    if (text.compare(cursor, 5, "false") == 0) return false;
    throw std::runtime_error(key + " is not a Boolean");
}

std::string json_string(const std::string& text, const std::string& key) {
    std::size_t cursor = key_position(text, key);
    require(cursor < text.size() && text[cursor] == '"', key + " is not a string");
    ++cursor;
    std::string result;
    bool escaped = false;
    for (; cursor < text.size(); ++cursor) {
        const char value = text[cursor];
        if (escaped) {
            result.push_back(value);
            escaped = false;
        } else if (value == '\\') {
            escaped = true;
        } else if (value == '"') {
            return result;
        } else {
            result.push_back(value);
        }
    }
    throw std::runtime_error("unterminated JSON string: " + key);
}

std::vector<int> json_integer_array(const std::string& text,
                                    const std::string& key) {
    std::size_t cursor = key_position(text, key);
    require(cursor < text.size() && text[cursor] == '[', key + " is not an array");
    ++cursor;
    std::vector<int> result;
    while (cursor < text.size()) {
        while (cursor < text.size() &&
               (std::isspace(static_cast<unsigned char>(text[cursor])) != 0 ||
                text[cursor] == ',')) {
            ++cursor;
        }
        if (cursor < text.size() && text[cursor] == ']') return result;
        const std::size_t begin = cursor;
        if (cursor < text.size() && text[cursor] == '-') ++cursor;
        while (cursor < text.size() &&
               std::isdigit(static_cast<unsigned char>(text[cursor])) != 0) {
            ++cursor;
        }
        require(cursor > begin, key + " contains a non-integer");
        result.push_back(std::stoi(text.substr(begin, cursor - begin)));
    }
    throw std::runtime_error("unterminated integer array: " + key);
}

std::vector<std::string> json_string_array(const std::string& text,
                                           const std::string& key) {
    std::size_t cursor = key_position(text, key);
    require(cursor < text.size() && text[cursor] == '[', key + " is not an array");
    ++cursor;
    std::vector<std::string> result;
    while (cursor < text.size()) {
        while (cursor < text.size() &&
               (std::isspace(static_cast<unsigned char>(text[cursor])) != 0 ||
                text[cursor] == ',')) {
            ++cursor;
        }
        if (cursor < text.size() && text[cursor] == ']') return result;
        require(cursor < text.size() && text[cursor] == '"',
                key + " contains a non-string");
        ++cursor;
        std::string value;
        while (cursor < text.size() && text[cursor] != '"') {
            require(text[cursor] != '\\', key + " uses an unsupported escape");
            value.push_back(text[cursor++]);
        }
        require(cursor < text.size(), "unterminated string in " + key);
        ++cursor;
        result.push_back(value);
    }
    throw std::runtime_error("unterminated string array: " + key);
}

std::vector<std::vector<PastEvent>> prefix_events(const Words& words) {
    std::vector<std::vector<PastEvent>> result(kColors);
    for (int column = 0; column < kColors; ++column) {
        const std::string& word = words[static_cast<std::size_t>(column)];
        require(!word.empty(), "past prefix column is empty");
        int old_color = word.front() - '0';
        int old_cap = 1;
        std::size_t cursor = 1;
        while (cursor < word.size()) {
            const int next_color = word[cursor] - '0';
            std::size_t end = cursor + 1;
            while (end < word.size() && word[end] == word[cursor]) ++end;
            const int next_cap = static_cast<int>(end);
            if (next_color != old_color) {
                result[static_cast<std::size_t>(column)].push_back(
                    {old_color, old_cap, next_color});
            }
            old_color = next_color;
            old_cap = next_cap;
            cursor = end;
        }
    }
    return result;
}

struct PastResult {
    std::uint64_t histories = 0;
    std::string witness;
    Debts final_debts{};
};

PastResult past_reachability(const Words& words) {
    const auto events = prefix_events(words);
    std::array<std::uint32_t, kColors> multipliers{};
    std::uint32_t states = 1;
    for (int column = 0; column < kColors; ++column) {
        multipliers[static_cast<std::size_t>(column)] = states;
        states *= static_cast<std::uint32_t>(
            events[static_cast<std::size_t>(column)].size() + 1);
    }
    std::vector<std::int64_t> memo(states, -1);
    std::vector<int> first(states, -1);
    const auto decode = [&](std::uint32_t state) {
        std::array<std::size_t, kColors> ranks{};
        for (int column = 0; column < kColors; ++column) {
            const auto size = events[static_cast<std::size_t>(column)].size() + 1;
            ranks[static_cast<std::size_t>(column)] =
                (state / multipliers[static_cast<std::size_t>(column)]) % size;
        }
        return ranks;
    };
    const auto debts_at = [&](const std::array<std::size_t, kColors>& ranks) {
        Debts debts{};
        for (int column = 0; column < kColors; ++column) {
            const auto& chain = events[static_cast<std::size_t>(column)];
            for (std::size_t index = 0;
                 index < ranks[static_cast<std::size_t>(column)]; ++index) {
                const PastEvent& event = chain[index];
                debts[event.old_color] += event.old_cap;
                debts[event.next_color] -= event.old_cap;
            }
        }
        return debts;
    };
    const auto visit = [&](const auto& self, std::uint32_t state) -> std::uint64_t {
        const auto ranks = decode(state);
        bool goal = true;
        for (int column = 0; column < kColors; ++column) {
            goal = goal && ranks[static_cast<std::size_t>(column)] ==
                events[static_cast<std::size_t>(column)].size();
        }
        if (goal) return 1;
        std::int64_t& known = memo[state];
        if (known >= 0) return static_cast<std::uint64_t>(known);
        const Debts debts = debts_at(ranks);
        std::uint64_t count = 0;
        for (int column = 0; column < kColors; ++column) {
            const std::size_t rank = ranks[static_cast<std::size_t>(column)];
            const auto& chain = events[static_cast<std::size_t>(column)];
            if (rank == chain.size()) continue;
            const PastEvent& event = chain[rank];
            Debts tested = debts;
            tested[event.old_color] += event.old_cap;
            const int positives = static_cast<int>(std::count_if(
                tested.begin(), tested.end(), [](int value) { return value > 0; }));
            if (positives > kEmpty) continue;
            const std::uint64_t child = self(
                self, state + multipliers[static_cast<std::size_t>(column)]);
            if (child != 0 && first[state] < 0) first[state] = column;
            count += child;
        }
        known = static_cast<std::int64_t>(count);
        return count;
    };

    PastResult result;
    result.histories = visit(visit, 0);
    if (result.histories != 0) {
        std::uint32_t state = 0;
        while (true) {
            const auto ranks = decode(state);
            bool goal = true;
            for (int column = 0; column < kColors; ++column) {
                goal = goal && ranks[static_cast<std::size_t>(column)] ==
                    events[static_cast<std::size_t>(column)].size();
            }
            if (goal) {
                result.final_debts = debts_at(ranks);
                break;
            }
            require(first[state] >= 0, "reachable past has no witness successor");
            const int column = first[state];
            result.witness.push_back(static_cast<char>('0' + column));
            state += multipliers[static_cast<std::size_t>(column)];
        }
    } else {
        std::array<std::size_t, kColors> final_ranks{};
        for (int column = 0; column < kColors; ++column) {
            final_ranks[static_cast<std::size_t>(column)] =
                events[static_cast<std::size_t>(column)].size();
        }
        result.final_debts = debts_at(final_ranks);
    }
    return result;
}

std::vector<PrefixTemplate> enumerate_prefixes(const ParentSpec& spec) {
    const auto caps = spec.caps();
    Debts exposed = spec.debts;
    for (const int cap : caps) exposed[spec.q_color] += cap;
    Debts remaining = exposed;
    remaining[spec.q_color] -= kColors;
    require(std::all_of(remaining.begin(), remaining.end(),
                        [](int value) { return value >= 0; }),
            "reserved final q items exceed exposed inventory");
    int free_positions = 0;
    for (const int cap : caps) free_positions += cap - 1;
    require(std::accumulate(remaining.begin(), remaining.end(), 0) ==
                free_positions,
            "past residual inventory has the wrong size");

    std::vector<int> flat(static_cast<std::size_t>(free_positions), 0);
    std::vector<PrefixTemplate> templates;
    const auto visit = [&](const auto& self, int position, Debts counts) -> void {
        if (position == free_positions) {
            PrefixTemplate item;
            item.ordinal = templates.size();
            int cursor = 0;
            for (int column = 0; column < kColors; ++column) {
                std::string word;
                for (int index = 0; index < caps[static_cast<std::size_t>(column)] - 1;
                     ++index) {
                    word.push_back(static_cast<char>('0' +
                        flat[static_cast<std::size_t>(cursor++)]));
                }
                word.push_back(static_cast<char>('0' + spec.q_color));
                item.words_top_to_bottom[static_cast<std::size_t>(column)] =
                    std::move(word);
            }
            require(cursor == free_positions, "past prefix did not consume its pool");
            const PastResult past = past_reachability(item.words_top_to_bottom);
            item.reachable = past.histories != 0;
            item.legal_histories = past.histories;
            item.first_witness = past.witness;
            require(past.final_debts == spec.debts,
                    "past prefix final debts differ from its parent");
            templates.push_back(std::move(item));
            return;
        }
        for (int color = 0; color < kColors; ++color) {
            if (counts[static_cast<std::size_t>(color)] == 0) continue;
            flat[static_cast<std::size_t>(position)] = color;
            --counts[static_cast<std::size_t>(color)];
            self(self, position + 1, counts);
            ++counts[static_cast<std::size_t>(color)];
        }
    };
    visit(visit, 0, remaining);

    const std::uint64_t reachable = static_cast<std::uint64_t>(std::count_if(
        templates.begin(), templates.end(),
        [](const PrefixTemplate& item) { return item.reachable; }));
    std::uint64_t histories = 0;
    for (const PrefixTemplate& item : templates) histories += item.legal_histories;
    require(templates.size() == spec.prefix_candidates,
            "balanced prefix candidate census drifted on edge " +
                std::to_string(spec.edge));
    require(reachable == spec.prefix_reachable,
            "reachable prefix census drifted on edge " +
                std::to_string(spec.edge));
    require(histories == spec.legal_histories,
            "past-history census drifted on edge " +
                std::to_string(spec.edge));
    return templates;
}

class InitialSolver {
public:
    explicit InitialSolver(const Words& columns) {
        std::uint32_t size = 1;
        for (int column = 0; column < kColors; ++column) {
            build_events(column, columns[static_cast<std::size_t>(column)]);
            multipliers_[static_cast<std::size_t>(column)] = size;
            size *= static_cast<std::uint32_t>(
                events_[static_cast<std::size_t>(column)].size() + 1);
        }
        memo_.assign(size, -1);
    }

    SolverResult solve() {
        SolverResult result;
        result.solvable = visit(0);
        for (int column = 0; column < kColors; ++column) {
            if (safe_from(0, column)) result.safe_mask |= 1U << column;
        }
        if (result.solvable) {
            std::uint32_t state = 0;
            while (!goal(state)) {
                bool advanced = false;
                for (int column = 0; column < kColors; ++column) {
                    if (!safe_from(state, column)) continue;
                    result.path.push_back(static_cast<char>('0' + column));
                    state += multipliers_[static_cast<std::size_t>(column)];
                    advanced = true;
                    break;
                }
                require(advanced, "initial YES has no safe successor");
            }
        }
        result.states = states_;
        result.transitions = transitions_;
        return result;
    }

    bool replay(const std::string& path) const {
        std::uint32_t state = 0;
        for (const char value : path) {
            const int column = value - '0';
            if (column < 0 || column >= kColors || !legal(state, column)) {
                return false;
            }
            state += multipliers_[static_cast<std::size_t>(column)];
        }
        return goal(state);
    }

private:
    struct Event {
        int old_color = 0;
        int old_cap = 0;
        int next_color = 0;
        int next_cap = 0;
    };

    std::array<std::vector<Event>, kColors> events_;
    std::array<std::vector<Debts>, kColors> deltas_;
    std::array<std::uint32_t, kColors> multipliers_{};
    std::vector<std::int8_t> memo_;
    std::uint64_t states_ = 0;
    std::uint64_t transitions_ = 0;

    void build_events(int column, const std::string& word) {
        require(word.size() == kHeight, "initial column does not have height seven");
        require(std::all_of(word.begin(), word.end(), [](char value) {
                    return value >= '0' && value < '0' + kColors;
                }),
                "initial column has an invalid colour");
        int old_color = word.front() - '0';
        std::size_t cursor = 1;
        while (cursor < word.size() && word[cursor] == word.front()) ++cursor;
        int old_cap = static_cast<int>(cursor);
        while (cursor < word.size()) {
            const int next_color = word[cursor] - '0';
            std::size_t end = cursor + 1;
            while (end < word.size() && word[end] == word[cursor]) ++end;
            const int next_cap = static_cast<int>(end);
            events_[static_cast<std::size_t>(column)].push_back(
                {old_color, old_cap, next_color, next_cap});
            old_color = next_color;
            old_cap = next_cap;
            cursor = end;
        }
        auto& deltas = deltas_[static_cast<std::size_t>(column)];
        const auto& events = events_[static_cast<std::size_t>(column)];
        deltas.assign(events.size() + 1, Debts{});
        for (std::size_t index = 0; index < events.size(); ++index) {
            deltas[index + 1] = deltas[index];
            const Event& event = events[index];
            deltas[index + 1][event.old_color] += event.old_cap;
            if (event.next_cap == kHeight) {
                deltas[index + 1][event.next_color] +=
                    kHeight - event.old_cap;
            } else {
                deltas[index + 1][event.next_color] -= event.old_cap;
            }
        }
    }

    std::array<std::size_t, kColors> decode(std::uint32_t state) const {
        std::array<std::size_t, kColors> ranks{};
        for (int column = 0; column < kColors; ++column) {
            ranks[static_cast<std::size_t>(column)] =
                (state / multipliers_[static_cast<std::size_t>(column)]) %
                (events_[static_cast<std::size_t>(column)].size() + 1);
        }
        return ranks;
    }

    int exhausted(const std::array<std::size_t, kColors>& ranks) const {
        int count = 0;
        for (int column = 0; column < kColors; ++column) {
            count += ranks[static_cast<std::size_t>(column)] ==
                events_[static_cast<std::size_t>(column)].size();
        }
        return count;
    }

    bool goal(std::uint32_t state) const {
        return exhausted(decode(state)) >= kEmpty;
    }

    bool legal(std::uint32_t state, int column) const {
        const auto ranks = decode(state);
        const std::size_t rank = ranks[static_cast<std::size_t>(column)];
        const auto& events = events_[static_cast<std::size_t>(column)];
        if (rank == events.size()) return false;
        Debts debts{};
        for (int other = 0; other < kColors; ++other) {
            const Debts& delta = deltas_[static_cast<std::size_t>(other)]
                [ranks[static_cast<std::size_t>(other)]];
            for (int color = 0; color < kColors; ++color) {
                debts[static_cast<std::size_t>(color)] +=
                    delta[static_cast<std::size_t>(color)];
            }
        }
        const Event& event = events[rank];
        debts[event.old_color] += event.old_cap;
        const int positives = static_cast<int>(std::count_if(
            debts.begin(), debts.end(), [](int value) { return value > 0; }));
        return positives <= kEmpty + exhausted(ranks);
    }

    bool safe_from(std::uint32_t state, int column) {
        if (goal(state) || !legal(state, column)) return false;
        ++transitions_;
        return visit(state + multipliers_[static_cast<std::size_t>(column)]);
    }

    bool visit(std::uint32_t state) {
        if (goal(state)) return true;
        std::int8_t& known = memo_[state];
        if (known >= 0) return known != 0;
        ++states_;
        for (int column = 0; column < kColors; ++column) {
            if (safe_from(state, column)) {
                known = 1;
                return true;
            }
        }
        known = 0;
        return false;
    }
};

CanonicalLayout canonicalize(const Words& original) {
    CanonicalLayout best;
    bool present = false;
    std::array<int, kColors> colors{{0, 1, 2, 3}};
    do {
        std::vector<std::pair<std::string, int>> columns;
        for (int column = 0; column < kColors; ++column) {
            std::string recolored;
            for (const char value : original[static_cast<std::size_t>(column)]) {
                recolored.push_back(static_cast<char>(
                    '0' + colors[static_cast<std::size_t>(value - '0')]));
            }
            columns.emplace_back(std::move(recolored), column);
        }
        std::sort(columns.begin(), columns.end());
        std::string key;
        for (const auto& item : columns) key += item.first;
        if (!present || key < best.key) {
            present = true;
            best.key = key;
            for (int index = 0; index < kColors; ++index) {
                best.columns_top_to_bottom[static_cast<std::size_t>(index)] =
                    columns[static_cast<std::size_t>(index)].first;
                best.canonical_to_original[static_cast<std::size_t>(index)] =
                    columns[static_cast<std::size_t>(index)].second;
            }
        }
    } while (std::next_permutation(colors.begin(), colors.end()));
    require(present && best.key.size() == kColors * kHeight,
            "layout canonicalization failed");
    return best;
}

std::uint32_t map_mask(std::uint32_t canonical_mask,
                       const std::array<int, kColors>& mapping) {
    std::uint32_t result = 0;
    for (int column = 0; column < kColors; ++column) {
        if ((canonical_mask & (1U << column)) != 0) {
            result |= 1U << mapping[static_cast<std::size_t>(column)];
        }
    }
    return result;
}

std::string map_path(const std::string& canonical_path,
                     const std::array<int, kColors>& mapping) {
    std::string result;
    for (const char value : canonical_path) {
        const int column = value - '0';
        require(column >= 0 && column < kColors,
                "canonical path contains an invalid source");
        result.push_back(static_cast<char>(
            '0' + mapping[static_cast<std::size_t>(column)]));
    }
    return result;
}

std::string reversed(std::string value) {
    std::reverse(value.begin(), value.end());
    return value;
}

void update_hash(std::uint64_t& hash, const std::string& row) {
    for (const unsigned char value : row + "\n") {
        hash ^= value;
        hash *= kFNVPrime;
    }
}

std::string hex_u64(std::uint64_t value) {
    static constexpr char digits[] = "0123456789abcdef";
    std::string result(16, '0');
    for (int index = 15; index >= 0; --index) {
        result[static_cast<std::size_t>(index)] = digits[value & 15U];
        value >>= 4U;
    }
    return result;
}

std::size_t find_spec(const std::vector<ParentSpec>& specs, int edge) {
    const auto found = std::find_if(
        specs.begin(), specs.end(),
        [edge](const ParentSpec& spec) { return spec.edge == edge; });
    require(found != specs.end(), "local-NO ledger contains unexpected edge " +
                std::to_string(edge));
    return static_cast<std::size_t>(std::distance(specs.begin(), found));
}

std::filesystem::path validate_checkpoint_report(
    const std::filesystem::path& report_path) {
    const std::string report = read_text(report_path);
    require(json_integer(report, "schema_version") == 1,
            "checkpoint report schema drifted");
    require(json_string(report, "experiment") ==
                "c4_h7_d2_three_source_checkpoint",
            "checkpoint experiment drifted");
    require(json_string(report, "status") == "LOCAL_NO_RESIDUALS_EXPORTED",
            "checkpoint report is not the complete local-NO artifact");
    const std::string run = json_object(report, "run");
    require(json_boolean(run, "universe_complete"),
            "checkpoint universe is incomplete");
    require(json_integer(run, "fixed_futures_checked") ==
                static_cast<std::int64_t>(kCheckpointFutures),
            "checkpoint fixed-future count drifted");
    require(json_integer(run, "local_no") ==
                static_cast<std::int64_t>(kCheckpointLocalNo),
            "checkpoint local-NO count drifted");
    const std::string scope = json_object(report, "scope");
    require(json_boolean(scope, "parent_checkpoint_only"),
            "checkpoint scope lost its parent boundary");
    require(!json_boolean(scope, "zero_debt_past_restored"),
            "input unexpectedly claims a restored past");
    require(!json_boolean(scope, "full_h7_theorem"),
            "input unexpectedly claims the full h7 theorem");
    const std::string claims = json_object(report, "claims");
    require(!json_boolean(claims, "zero_debt_initial_family_eliminated") &&
                !json_boolean(claims, "universal_c4_h7_solvability"),
            "checkpoint artifact overclaims its conclusion");
    require(json_boolean(report, "self_checks_passed"),
            "checkpoint self-checks did not pass");
    const std::string ledgers = json_object(report, "ledgers");
    const std::string filename = json_string(ledgers, "local_no");
    require(filename == "local-no-ledger.jsonl",
            "checkpoint local-NO ledger name drifted");
    return report_path.parent_path() / filename;
}

std::vector<LedgerRow> load_ledger(const std::filesystem::path& path,
                                   const std::vector<ParentSpec>& specs) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("cannot open " + path.string());
    std::vector<LedgerRow> rows;
    std::vector<std::uint64_t> counts(specs.size(), 0);
    std::string line;
    std::uint64_t previous_future = 0;
    bool first = true;
    while (std::getline(input, line)) {
        if (line.empty()) continue;
        require(json_string(line, "local_status") == "NO" &&
                    json_integer(line, "safe_source_mask") == 0,
                "local-NO ledger row is not local NO");
        LedgerRow row;
        row.future_index = static_cast<std::uint64_t>(
            json_integer(line, "future_index"));
        row.decoration_index = static_cast<std::uint64_t>(
            json_integer(line, "decoration_index"));
        const int edge = static_cast<int>(json_integer(line, "bridge_edge"));
        row.spec_index = find_spec(specs, edge);
        const ParentSpec& spec = specs[row.spec_index];
        if (!first) require(row.future_index > previous_future,
                            "local-NO future indices are not increasing");
        first = false;
        previous_future = row.future_index;

        const auto debts = json_integer_array(line, "parent_debts");
        const auto bad = json_integer_array(line, "bad_source");
        const auto q_caps = json_integer_array(line, "q_caps");
        require(debts.size() == kColors &&
                    std::equal(debts.begin(), debts.end(), spec.debts.begin()),
                "parent debts drifted on edge " + std::to_string(edge));
        require(bad.size() == 3 &&
                    std::equal(bad.begin(), bad.end(), spec.bad.begin()),
                "bad source drifted on edge " + std::to_string(edge));
        require(json_integer(line, "q_color") == spec.q_color,
                "q colour drifted on edge " + std::to_string(edge));
        require(q_caps.size() == 3 &&
                    std::equal(q_caps.begin(), q_caps.end(), spec.q_caps.begin()),
                "q caps drifted on edge " + std::to_string(edge));
        const auto words = json_string_array(line, "hidden_words_bottom_to_top");
        require(words.size() == kColors,
                "local-NO fixture does not have four hidden words");
        for (int column = 0; column < kColors; ++column) {
            row.hidden_bottom_to_top[static_cast<std::size_t>(column)] =
                words[static_cast<std::size_t>(column)];
        }

        const auto caps = spec.caps();
        Debts hidden_counts{};
        for (int column = 0; column < kColors; ++column) {
            const std::string& word =
                row.hidden_bottom_to_top[static_cast<std::size_t>(column)];
            require(word.size() == static_cast<std::size_t>(
                        kHeight - caps[static_cast<std::size_t>(column)]),
                    "hidden word length drifted on edge " +
                        std::to_string(edge));
            require(!word.empty() && word.back() != '0' + spec.q_color,
                    "hidden word merges into the parent q boundary");
            for (const char value : word) {
                require(value >= '0' && value < '0' + kColors,
                        "hidden word has an invalid colour");
                ++hidden_counts[static_cast<std::size_t>(value - '0')];
            }
        }
        require(std::all_of(row.hidden_bottom_to_top[0].begin(),
                            row.hidden_bottom_to_top[0].end(),
                            [&spec](char value) {
                                return value == '0' + spec.bad[2];
                            }),
                "bad hidden suffix is not its forced final run");
        Debts exposed = spec.debts;
        for (const int cap : caps) exposed[spec.q_color] += cap;
        for (int color = 0; color < kColors; ++color) {
            require(hidden_counts[static_cast<std::size_t>(color)] ==
                        kHeight - exposed[static_cast<std::size_t>(color)],
                    "hidden inventory does not complement the parent");
        }
        ++counts[row.spec_index];
        rows.push_back(std::move(row));
    }
    require(rows.size() == kCheckpointLocalNo,
            "local-NO ledger does not contain 14784 rows");
    for (std::size_t index = 0; index < specs.size(); ++index) {
        require(counts[index] == specs[index].local_no_rows,
                "per-edge local-NO ledger count drifted on edge " +
                    std::to_string(specs[index].edge));
    }
    return rows;
}

Words restore_layout(const ParentSpec& spec, const LedgerRow& row,
                     const PrefixTemplate& prefix) {
    Words result;
    Debts counts{};
    const auto caps = spec.caps();
    for (int column = 0; column < kColors; ++column) {
        const std::string hidden_top = reversed(
            row.hidden_bottom_to_top[static_cast<std::size_t>(column)]);
        const std::string& past =
            prefix.words_top_to_bottom[static_cast<std::size_t>(column)];
        require(past.size() ==
                    static_cast<std::size_t>(caps[static_cast<std::size_t>(column)]),
                "past prefix length drifted");
        require(!hidden_top.empty() && past.back() != hidden_top.front(),
                "restored checkpoint boundary merged");
        result[static_cast<std::size_t>(column)] = past + hidden_top;
        require(result[static_cast<std::size_t>(column)].size() == kHeight,
                "restored column does not have height seven");
        for (const char value : result[static_cast<std::size_t>(column)]) {
            ++counts[static_cast<std::size_t>(value - '0')];
        }
    }
    require(std::all_of(counts.begin(), counts.end(),
                        [](int value) { return value == kHeight; }),
            "restored initial layout is not colour-balanced");
    return result;
}

Sample make_sample(std::uint64_t restoration_index, const LedgerRow& row,
                   const ParentSpec& spec, const PrefixTemplate& prefix,
                   const Words& columns, bool solvable, std::uint32_t mask,
                   const std::string& path) {
    Sample sample;
    sample.present = true;
    sample.restoration_index = restoration_index;
    sample.future_index = row.future_index;
    sample.edge = spec.edge;
    sample.prefix_index = prefix.ordinal;
    sample.reachable = prefix.reachable;
    sample.solvable = solvable;
    sample.columns_top_to_bottom = columns;
    for (int column = 0; column < kColors; ++column) {
        sample.columns_bottom_to_top[static_cast<std::size_t>(column)] =
            reversed(columns[static_cast<std::size_t>(column)]);
    }
    sample.safe_mask = mask;
    sample.path = path;
    return sample;
}

void write_words_json(std::ostream& output, const Words& words) {
    output << '[';
    for (int column = 0; column < kColors; ++column) {
        if (column != 0) output << ',';
        output << '"' << words[static_cast<std::size_t>(column)] << '"';
    }
    output << ']';
}

void write_sample_json(std::ostream& output,
                       const std::optional<Sample>& optional) {
    if (!optional) {
        output << "null";
        return;
    }
    const Sample& sample = *optional;
    output << "{\"restoration_index\":" << sample.restoration_index
           << ",\"future_index\":" << sample.future_index
           << ",\"bridge_edge\":" << sample.edge
           << ",\"prefix_index\":" << sample.prefix_index
           << ",\"parent_reachable\":"
           << (sample.reachable ? "true" : "false")
           << ",\"initial_status\":\""
           << (sample.solvable ? "YES" : "NO")
           << "\",\"columns_top_to_bottom\":";
    write_words_json(output, sample.columns_top_to_bottom);
    output << ",\"columns_bottom_to_top\":";
    write_words_json(output, sample.columns_bottom_to_top);
    output << ",\"safe_source_mask\":" << sample.safe_mask
           << ",\"escape_columns\":\"" << sample.path << "\"}";
}

RunStats run(const Options& options, const std::vector<ParentSpec>& specs,
             const std::vector<std::vector<PrefixTemplate>>& prefixes,
             const std::vector<LedgerRow>& rows) {
    std::filesystem::create_directories(options.output_dir);
    std::ofstream result_ledger(options.output_dir / "initial-results.tsv",
                                std::ios::binary);
    std::ofstream no_ledger(options.output_dir / "initial-no-candidates.jsonl",
                            std::ios::binary);
    require(result_ledger && no_ledger, "cannot open restoration output ledgers");
    result_ledger
        << "restoration_index\tfuture_index\tbridge_edge\tprefix_index"
           "\tparent_reachable\tcolumns_top_to_bottom\tinitial_status"
           "\tsafe_source_mask\tescape_columns\n";

    RunStats stats;
    stats.limit_requested = options.limit_restorations;
    stats.per_edge.reserve(specs.size());
    for (const ParentSpec& spec : specs) {
        EdgeStats edge;
        edge.edge = spec.edge;
        edge.local_no_rows = spec.local_no_rows;
        edge.prefix_candidates = spec.prefix_candidates;
        edge.prefix_reachable = spec.prefix_reachable;
        edge.legal_histories = spec.legal_histories;
        edge.balanced_expected = spec.local_no_rows * spec.prefix_candidates;
        edge.reachable_expected = spec.local_no_rows * spec.prefix_reachable;
        stats.per_edge.push_back(edge);
    }
    const std::uint64_t expected_balanced = std::accumulate(
        stats.per_edge.begin(), stats.per_edge.end(), std::uint64_t{0},
        [](std::uint64_t sum, const EdgeStats& edge) {
            return sum + edge.balanced_expected;
        });
    const std::uint64_t expected_reachable = std::accumulate(
        stats.per_edge.begin(), stats.per_edge.end(), std::uint64_t{0},
        [](std::uint64_t sum, const EdgeStats& edge) {
            return sum + edge.reachable_expected;
        });
    require(expected_balanced == kBalancedRestorations,
            "balanced restoration universe is not 285600");
    require(expected_reachable == kReachableRestorations,
            "reachable restoration universe is not 281904");
    const std::uint64_t effective_limit = options.limit_restorations == 0
        ? expected_balanced
        : std::min(options.limit_restorations, expected_balanced);

    std::unordered_map<std::string, SolverResult> cache;
    const auto started = std::chrono::steady_clock::now();
    bool stop = false;
    for (const LedgerRow& row : rows) {
        if (stop) break;
        const ParentSpec& spec = specs[row.spec_index];
        EdgeStats& edge = stats.per_edge[row.spec_index];
        for (const PrefixTemplate& prefix : prefixes[row.spec_index]) {
            if (stats.restorations_checked >= effective_limit) {
                stop = true;
                break;
            }
            const std::uint64_t restoration_index = stats.restorations_checked;
            const Words columns = restore_layout(spec, row, prefix);
            const CanonicalLayout canonical = canonicalize(columns);
            SolverResult canonical_result;
            const auto found = cache.find(canonical.key);
            if (found == cache.end()) {
                InitialSolver solver(canonical.columns_top_to_bottom);
                canonical_result = solver.solve();
                require(!canonical_result.solvable ||
                            solver.replay(canonical_result.path),
                        "canonical initial YES path did not replay");
                cache.emplace(canonical.key, canonical_result);
                ++stats.canonical_classes_solved;
                stats.states += canonical_result.states;
                stats.transitions += canonical_result.transitions;
            } else {
                canonical_result = found->second;
                ++stats.symmetry_cache_hits;
            }
            const std::uint32_t mask = map_mask(
                canonical_result.safe_mask, canonical.canonical_to_original);
            const std::string path = map_path(
                canonical_result.path, canonical.canonical_to_original);
            if (canonical_result.solvable) {
                InitialSolver replay_solver(columns);
                require(replay_solver.replay(path),
                        "symmetry-translated initial YES path did not replay");
                ++stats.initial_yes;
                ++stats.witnesses_replayed;
                ++edge.initial_yes;
                if (!stats.first_yes) {
                    stats.first_yes = make_sample(
                        restoration_index, row, spec, prefix, columns, true,
                        mask, path);
                }
            } else {
                require(mask == 0 && path.empty(),
                        "initial NO has a winning witness");
                ++stats.initial_no;
                ++edge.initial_no;
                const Sample sample = make_sample(
                    restoration_index, row, spec, prefix, columns, false, 0,
                    "");
                if (!stats.first_no) stats.first_no = sample;
                no_ledger << "{\"scope\":\"complete_balanced_c4_h7_layout\",";
                no_ledger << "\"independently_verified\":false,\"candidate\":";
                write_sample_json(no_ledger, sample);
                no_ledger << "}\n";
            }

            ++stats.restorations_checked;
            ++edge.checked;
            if (prefix.reachable) {
                ++stats.reachable_checked;
                ++edge.reachable_checked;
            } else {
                ++stats.unreachable_checked;
            }
            std::ostringstream ledger_row;
            ledger_row << restoration_index << '\t' << row.future_index << '\t'
                       << spec.edge << '\t' << prefix.ordinal << '\t'
                       << (prefix.reachable ? 1 : 0) << '\t';
            for (int column = 0; column < kColors; ++column) {
                if (column != 0) ledger_row << ',';
                ledger_row << columns[static_cast<std::size_t>(column)];
            }
            ledger_row << '\t' << (canonical_result.solvable ? "YES" : "NO")
                       << '\t' << mask << '\t' << path;
            const std::string ledger_text = ledger_row.str();
            result_ledger << ledger_text << '\n';
            update_hash(stats.result_hash, ledger_text);

            if (stats.restorations_checked % 50'000 == 0) {
                std::cout << "progress restorations=" << stats.restorations_checked
                          << '/' << effective_limit
                          << " initial_no=" << stats.initial_no
                          << " classes=" << stats.canonical_classes_solved << '\n';
            }
        }
    }
    stats.elapsed_seconds = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - started).count();
    stats.universe_complete =
        stats.restorations_checked == kBalancedRestorations;
    require(stats.restorations_checked == effective_limit,
            "restoration run stopped before its requested limit");
    require(stats.initial_yes + stats.initial_no == stats.restorations_checked,
            "initial YES/NO counts do not partition restorations");
    require(stats.witnesses_replayed == stats.initial_yes,
            "an initial YES witness was not replayed");
    require(stats.reachable_checked + stats.unreachable_checked ==
                stats.restorations_checked,
            "reachable flag does not partition restorations");
    if (stats.universe_complete) {
        require(stats.reachable_checked == kReachableRestorations &&
                    stats.unreachable_checked ==
                        kBalancedRestorations - kReachableRestorations,
                "full run has the wrong reachable/unreachable split");
        for (const EdgeStats& edge : stats.per_edge) {
            require(edge.checked == edge.balanced_expected &&
                        edge.reachable_checked == edge.reachable_expected,
                    "full per-edge restoration coverage drifted");
        }
    }
    stats.self_checks_passed = true;
    return stats;
}

std::string status(const RunStats& stats) {
    if (stats.initial_no != 0) return "INITIAL_NO_CANDIDATES_EXPORTED";
    if (!stats.universe_complete) return "INCOMPLETE";
    return "THREE_SOURCE_PAST_FAMILY_ELIMINATED";
}

void write_report(const Options& options, const std::vector<ParentSpec>& specs,
                  const RunStats& stats) {
    std::ofstream json(options.output_dir / "report.json");
    require(static_cast<bool>(json), "cannot write report.json");
    const bool eliminated = stats.universe_complete && stats.initial_no == 0;
    json << "{\n"
         << "  \"schema_version\": 1,\n"
         << "  \"experiment\": \"c4_h7_d2_three_source_past_restoration\",\n"
         << "  \"status\": \"" << status(stats) << "\",\n"
         << "  \"parameters\": {\"colors\":4,\"height\":7,\"empty\":2},\n"
         << "  \"input\": {\"checkpoint_report\":\""
         << options.checkpoint_report.filename().string()
         << "\",\"checkpoint_status\":\"LOCAL_NO_RESIDUALS_EXPORTED\","
            "\"fixed_futures\":1106490,\"checkpoint_local_no\":14784},\n"
         << "  \"scope\": {\"balanced_completion_superset_only\":true,"
            "\"checkpoint_reachable_subset_tracked\":true,"
            "\"full_h7_theorem\":false},\n"
         << "  \"universe\": {\"parent_families\":7,"
            "\"checkpoint_local_no_rows\":14784,"
            "\"balanced_restorations\":285600,"
            "\"reachable_restorations\":281904,"
            "\"unreachable_balanced_completions\":3696},\n"
         << "  \"run\": {\"limit_requested\":" << stats.limit_requested
         << ",\"universe_complete\":"
         << (stats.universe_complete ? "true" : "false")
         << ",\"restorations_checked\":" << stats.restorations_checked
         << ",\"reachable_checked\":" << stats.reachable_checked
         << ",\"unreachable_checked\":" << stats.unreachable_checked
         << ",\"initial_yes\":" << stats.initial_yes
         << ",\"initial_no\":" << stats.initial_no
         << ",\"winning_paths_replayed\":" << stats.witnesses_replayed
         << ",\"canonical_classes_solved\":"
         << stats.canonical_classes_solved
         << ",\"symmetry_cache_hits\":" << stats.symmetry_cache_hits
         << ",\"states\":" << stats.states
         << ",\"transitions\":" << stats.transitions
         << ",\"elapsed_seconds\":" << stats.elapsed_seconds << "},\n"
         << "  \"claims\": {\"restoration_family_eliminated\":"
         << (eliminated ? "true" : "false")
         << ",\"reachable_past_family_eliminated\":"
         << (eliminated ? "true" : "false")
         << ",\"universal_c4_h7_solvability\":false,"
            "\"initial_no_candidates_found\":"
         << (stats.initial_no != 0 ? "true" : "false")
         << ",\"global_no_certified\":false,"
            "\"global_no_independently_verified\":false,"
            "\"independent_verification_complete\":false},\n"
         << "  \"ledgers\": {\"initial_results\":\"initial-results.tsv\","
            "\"initial_no_candidates\":\"initial-no-candidates.jsonl\","
            "\"result_rows_fnv1a64\":\""
         << hex_u64(stats.result_hash) << "\"},\n"
         << "  \"first_initial_yes\": ";
    write_sample_json(json, stats.first_yes);
    json << ",\n  \"first_initial_no\": ";
    write_sample_json(json, stats.first_no);
    json << ",\n  \"per_edge\": [\n";
    for (std::size_t index = 0; index < stats.per_edge.size(); ++index) {
        if (index != 0) json << ",\n";
        const EdgeStats& edge = stats.per_edge[index];
        const ParentSpec& spec = specs[index];
        json << "    {\"bridge_edge\":" << edge.edge
             << ",\"parent_debts\":[" << spec.debts[0] << ','
             << spec.debts[1] << ',' << spec.debts[2] << ','
             << spec.debts[3] << "]"
             << ",\"caps\":[" << spec.bad[1] << ',' << spec.q_caps[0]
             << ',' << spec.q_caps[1] << ',' << spec.q_caps[2] << ']'
             << ",\"checkpoint_local_no\":" << edge.local_no_rows
             << ",\"prefix_candidates\":" << edge.prefix_candidates
             << ",\"prefix_reachable\":" << edge.prefix_reachable
             << ",\"legal_prefix_histories\":" << edge.legal_histories
             << ",\"balanced_restorations_expected\":"
             << edge.balanced_expected
             << ",\"reachable_restorations_expected\":"
             << edge.reachable_expected
             << ",\"restorations_checked\":" << edge.checked
             << ",\"reachable_checked\":" << edge.reachable_checked
             << ",\"initial_yes\":" << edge.initial_yes
             << ",\"initial_no\":" << edge.initial_no << '}';
    }
    json << "\n  ],\n  \"self_checks_passed\": "
         << (stats.self_checks_passed ? "true" : "false") << "\n}\n";

    std::ofstream markdown(options.output_dir / "report.md");
    require(static_cast<bool>(markdown), "cannot write report.md");
    markdown << "# c=4, h=7 three-source zero-debt past restoration\n\n"
             << "- Status: **" << status(stats) << "**\n"
             << "- Balanced restoration superset checked: "
             << stats.restorations_checked << " / "
             << kBalancedRestorations << ".\n"
             << "- Parent-reachable restorations checked: "
             << stats.reachable_checked << " / "
             << kReachableRestorations << ".\n"
             << "- Zero-debt initial YES / NO: " << stats.initial_yes
             << " / " << stats.initial_no << ".\n"
             << "- Canonical symmetry classes solved: "
             << stats.canonical_classes_solved << ".\n"
             << "- Scope: only the 285,600 balanced completions of the 14,784 "
                "three-source checkpoint-local-NO rows.\n"
             << "- This report does not claim universal c4/h7 solvability.\n";

    if (stats.first_no) {
        std::ofstream candidate_json(
            options.output_dir / "initial-no-candidate.json");
        require(static_cast<bool>(candidate_json),
                "cannot write initial-no-candidate.json");
        candidate_json
            << "{\"scope\":\"complete_balanced_c4_h7_layout\","
               "\"independently_verified\":false,\"candidate\":";
        write_sample_json(candidate_json, stats.first_no);
        candidate_json << "}\n";

        std::ofstream candidate_text(
            options.output_dir / "initial-no-candidate.txt");
        require(static_cast<bool>(candidate_text),
                "cannot write initial-no-candidate.txt");
        candidate_text << "# c=4 h=7 complete balanced candidate\n"
                       << "# Columns are written bottom-to-top.\n"
                       << "height=7\ncolors=4\nempty=2\n";
        for (const std::string& column :
             stats.first_no->columns_bottom_to_top) {
            candidate_text << "column=" << column << '\n';
        }
    }
}

void run_self_tests() {
    const auto specs = expected_specs();
    std::uint64_t balanced = 0;
    std::uint64_t reachable = 0;
    for (const ParentSpec& spec : specs) {
        const auto prefixes = enumerate_prefixes(spec);
        balanced += spec.local_no_rows * prefixes.size();
        reachable += spec.local_no_rows * static_cast<std::uint64_t>(
            std::count_if(prefixes.begin(), prefixes.end(),
                          [](const PrefixTemplate& item) {
                              return item.reachable;
                          }));
    }
    require(balanced == kBalancedRestorations,
            "self-test balanced restoration count drifted");
    require(reachable == kReachableRestorations,
            "self-test reachable restoration count drifted");

    const Words solid{{"0000000", "1111111", "2222222", "3333333"}};
    InitialSolver solid_solver(solid);
    const SolverResult solid_result = solid_solver.solve();
    require(solid_result.solvable && solid_solver.replay(solid_result.path),
            "solid initial fixture is not solved");

    const Words ring{{"0000001", "1111112", "2222223", "3333330"}};
    InitialSolver ring_solver(ring);
    const SolverResult ring_result = ring_solver.solve();
    require(ring_result.solvable && !ring_result.path.empty() &&
                ring_solver.replay(ring_result.path),
            "nontrivial initial fixture is not solved");

    Words permuted{{ring[2], ring[0], ring[3], ring[1]}};
    for (std::string& word : permuted) {
        for (char& value : word) value = static_cast<char>('0' + (value - '0' + 1) % 4);
    }
    require(canonicalize(ring).key == canonicalize(permuted).key,
            "colour/column canonicalization is not invariant");
}

} // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parse_options(argc, argv);
        if (options.self_test) run_self_tests();
        if (options.checkpoint_report.empty()) {
            if (options.self_test) {
                std::cout << "three-source past-restoration self-test passed\n";
                return 0;
            }
            throw std::runtime_error("--checkpoint-report is required");
        }
        if (options.output_dir.empty()) {
            throw std::runtime_error("--output-dir is required");
        }
        const auto specs = expected_specs();
        std::vector<std::vector<PrefixTemplate>> prefixes;
        prefixes.reserve(specs.size());
        for (const ParentSpec& spec : specs) {
            prefixes.push_back(enumerate_prefixes(spec));
        }
        const std::filesystem::path ledger_path =
            validate_checkpoint_report(options.checkpoint_report);
        const auto rows = load_ledger(ledger_path, specs);
        const RunStats stats = run(options, specs, prefixes, rows);
        write_report(options, specs, stats);
        std::cout << "status=" << status(stats)
                  << " restorations=" << stats.restorations_checked << '/'
                  << kBalancedRestorations
                  << " reachable=" << stats.reachable_checked << '/'
                  << kReachableRestorations
                  << " initial_yes=" << stats.initial_yes
                  << " initial_no=" << stats.initial_no
                  << " classes=" << stats.canonical_classes_solved << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
