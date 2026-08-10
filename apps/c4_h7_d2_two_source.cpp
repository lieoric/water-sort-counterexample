#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
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
constexpr std::uint64_t kExpectedEdges = 2;
constexpr std::uint64_t kExpectedDecorations = 190;
constexpr std::uint64_t kExpectedResidualWords = 12936;
constexpr std::uint64_t kExpectedPastTemplates = 20;
constexpr std::uint64_t kExpectedParentYes = 0;
constexpr std::uint64_t kExpectedParentLocalNo = kExpectedResidualWords;

using Debts = std::array<int, kColors>;
using Counts = std::array<int, kColors>;

struct Options {
    std::filesystem::path output_dir;
    std::uint64_t limit = 0;
    bool self_test = false;
};

struct Source {
    int color = 0;
    int cap = 0;
};

struct Card {
    int color = 0;
    int endpoint = 0;
};

struct Edge {
    std::string id;
    std::size_t ordinal = 0;
    Debts parent_debts{{-2, 0, 1, 1}};
    int q_color = 0;
    int final_color = 1;
    int bad_cap = 0;
    std::array<int, 3> q_caps{};
};

struct CandidateWord {
    std::vector<int> word_bottom_to_top;
    std::vector<int> free_top_to_bottom;
    Counts counts{};
};

struct Decoration {
    std::size_t ordinal = 0;
    std::size_t edge_index = 0;
    std::array<Card, 3> cards{};
    Counts hidden_balance{};
    std::uint64_t residual_words_expected = 0;
};

struct PastEvent {
    int old_color = 0;
    int old_cap = 0;
    int next_color = 0;
    int next_cap = 0;
};

struct PrefixColumn {
    std::vector<int> top_to_bottom;
    std::vector<PastEvent> events;
    Debts delta{};
};

struct PrefixTemplate {
    std::array<PrefixColumn, kColors> columns;
};

struct FixedFixture {
    Debts debts{};
    std::array<Source, kColors> sources{};
    std::array<std::vector<int>, kColors> hidden_bottom_to_top;
};

struct ResidualSample {
    bool present = false;
    bool solvable = false;
    std::size_t decoration = 0;
    std::array<std::string, kColors> words_bottom_to_top;
    std::array<std::string, kColors> columns_top_to_bottom;
    std::array<std::string, kColors> columns_bottom_to_top;
    std::uint32_t safe_mask = 0;
    std::string path;
};

struct DecorationStats {
    std::uint64_t expected = 0;
    std::uint64_t checked = 0;
    std::uint64_t parent_yes = 0;
    std::uint64_t parent_local_no = 0;
    std::uint64_t water_initial_checked = 0;
    std::uint64_t water_initial_yes = 0;
    std::uint64_t water_initial_no = 0;
    std::uint64_t parent_states = 0;
    std::uint64_t parent_transitions = 0;
    std::uint64_t water_states = 0;
    std::uint64_t water_transitions = 0;
};

struct PrefixRow {
    std::size_t decoration = 0;
    std::array<std::string, 3> free_tails_top_to_bottom;
    bool parent_solvable = false;
    std::uint32_t parent_safe_mask = 0;
    std::string parent_path;
    std::uint64_t water_initial_checked = 0;
    std::uint64_t water_initial_yes = 0;
    std::uint64_t water_initial_no = 0;
};

struct RunStats {
    bool self_checks_passed = false;
    bool universe_complete = false;
    std::uint64_t limit_requested = 0;
    std::uint64_t residual_words_expected = 0;
    std::uint64_t residual_words_checked = 0;
    std::uint64_t parent_yes = 0;
    std::uint64_t parent_local_no = 0;
    std::uint64_t recovered_parent_local_no = 0;
    std::uint64_t unresolved_parent_local_no = 0;
    std::uint64_t water_initial_checked = 0;
    std::uint64_t water_initial_yes = 0;
    std::uint64_t water_initial_no = 0;
    std::uint64_t water_witnesses_replayed = 0;
    std::uint64_t parent_states = 0;
    std::uint64_t parent_transitions = 0;
    std::uint64_t water_states = 0;
    std::uint64_t water_transitions = 0;
    std::vector<DecorationStats> per_decoration;
    std::vector<PrefixRow> checked_prefix;
    std::vector<ResidualSample> parent_local_no_samples;
    std::optional<ResidualSample> first_water_recovery;
    std::optional<ResidualSample> first_water_local_no;
    double elapsed_seconds = 0.0;
};

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error("self-check failed: " + message);
}

void usage() {
    std::cerr << "Usage: water-c4-h7-d2-two-source "
                 "[--output-dir DIR] [--limit N] [--self-test]\n";
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
    if (options.output_dir.empty() && !options.self_test) {
        usage();
        throw std::runtime_error("--output-dir is required unless --self-test is used");
    }
    return options;
}

int positive_count(const Debts& debts) {
    return static_cast<int>(std::count_if(
        debts.begin(), debts.end(), [](int value) { return value > 0; }));
}

bool source_legal(const Debts& debts, int exhausted, int color, int cap) {
    Debts test = debts;
    test[color] += cap;
    return positive_count(test) <= kEmpty + exhausted;
}

std::vector<Edge> build_edges() {
    std::vector<Edge> edges;
    edges.push_back({"exhaust-sibling-e245", 0, {{-2, 0, 1, 1}},
                     0, 1, 1, {{2, 3, 3}}});
    edges.push_back({"exhaust-sibling-e246", 1, {{-2, 0, 1, 1}},
                     0, 1, 2, {{1, 3, 3}}});
    for (const Edge& edge : edges) {
        require(source_legal(edge.parent_debts, 0, edge.q_color, edge.bad_cap),
                "stored bad source is not legal");
        require(source_legal(edge.parent_debts, 0, edge.q_color, edge.q_caps[0]),
                "stored sibling source is not legal");
        require(!source_legal(edge.parent_debts, 0, edge.q_color, edge.q_caps[1]) &&
                    !source_legal(edge.parent_debts, 0, edge.q_color, edge.q_caps[2]),
                "fixture does not have exactly two legal physical sources");
    }
    return edges;
}

std::vector<Card> cards_for(int q_color, int cap) {
    std::vector<Card> result;
    for (int color = 0; color < kColors; ++color) {
        if (color == q_color) continue;
        for (int endpoint = cap + 1; endpoint <= kHeight; ++endpoint) {
            result.push_back({color, endpoint});
        }
    }
    return result;
}

std::vector<CandidateWord> candidate_words(int old_cap, const Card& card) {
    const int forced = card.endpoint - old_cap;
    const int free = kHeight - card.endpoint;
    require(forced > 0 && free >= 0, "invalid next-run card");
    CandidateWord current;
    current.free_top_to_bottom.assign(static_cast<std::size_t>(free), 0);
    std::vector<CandidateWord> result;
    const auto visit = [&](const auto& self, int position) -> void {
        if (position == free) {
            if (free > 0 && current.free_top_to_bottom.front() == card.color) return;
            current.word_bottom_to_top.clear();
            for (auto iterator = current.free_top_to_bottom.rbegin();
                 iterator != current.free_top_to_bottom.rend(); ++iterator) {
                current.word_bottom_to_top.push_back(*iterator);
            }
            current.word_bottom_to_top.insert(
                current.word_bottom_to_top.end(), static_cast<std::size_t>(forced),
                card.color);
            current.counts.fill(0);
            // hidden_balance already excludes the forced next run.  Hall
            // completion therefore counts only the still-free residual tail.
            for (const int color : current.free_top_to_bottom) {
                ++current.counts[color];
            }
            result.push_back(current);
            return;
        }
        for (int color = 0; color < kColors; ++color) {
            current.free_top_to_bottom[static_cast<std::size_t>(position)] = color;
            self(self, position + 1);
        }
    };
    visit(visit, 0);
    return result;
}

std::uint32_t pack_counts(const Counts& counts) {
    std::uint32_t result = 0;
    for (int color = 0; color < kColors; ++color) {
        require(counts[color] >= 0 && counts[color] < 16, "cannot pack color count");
        result |= static_cast<std::uint32_t>(counts[color]) << (4 * color);
    }
    return result;
}

Counts subtract_counts(const Counts& total, const Counts& first,
                       const Counts& second, bool& valid) {
    Counts result{};
    valid = true;
    for (int color = 0; color < kColors; ++color) {
        result[color] = total[color] - first[color] - second[color];
        valid = valid && result[color] >= 0;
    }
    return result;
}

std::uint64_t completion_count(
    const Counts& balance,
    const std::array<std::vector<CandidateWord>, 3>& words) {
    std::unordered_map<std::uint32_t, std::uint64_t> third_counts;
    for (const CandidateWord& word : words[2]) {
        ++third_counts[pack_counts(word.counts)];
    }
    std::uint64_t total = 0;
    for (const CandidateWord& first : words[0]) {
        for (const CandidateWord& second : words[1]) {
            bool valid = false;
            const Counts needed = subtract_counts(balance, first.counts,
                                                  second.counts, valid);
            if (!valid) continue;
            const auto found = third_counts.find(pack_counts(needed));
            if (found != third_counts.end()) total += found->second;
        }
    }
    return total;
}

Counts hidden_balance(const Edge& edge, const std::array<Card, 3>& cards) {
    // At the shared P checkpoint, q is fully exposed and the two positive
    // colors each have one exposed item.
    Counts remaining{{0, 7, 6, 6}};
    remaining[edge.final_color] -= kHeight - edge.bad_cap;
    for (std::size_t slot = 0; slot < 3; ++slot) {
        remaining[cards[slot].color] -= cards[slot].endpoint - edge.q_caps[slot];
    }
    return remaining;
}

bool is_d2_reduction_decoration(const Edge& edge,
                                const std::array<Card, 3>& cards) {
    // Exactly one sibling is legal.  Therefore the upstream refined ledger
    // reaches D2 precisely when that sibling is live and the reserved bad
    // source is no longer legal after the live event.
    const Card& card = cards[0];
    if (card.endpoint == kHeight) return false;
    Debts after = edge.parent_debts;
    after[edge.q_color] += edge.q_caps[0];
    after[card.color] -= edge.q_caps[0];
    return !source_legal(after, 0, edge.q_color, edge.bad_cap);
}

std::vector<Decoration> enumerate_decorations(const std::vector<Edge>& edges) {
    std::vector<Decoration> result;
    std::array<std::uint64_t, 2> counts{};
    std::array<std::uint64_t, 2> weights{};
    for (const Edge& edge : edges) {
        const auto cards0 = cards_for(edge.q_color, edge.q_caps[0]);
        const auto cards1 = cards_for(edge.q_color, edge.q_caps[1]);
        const auto cards2 = cards_for(edge.q_color, edge.q_caps[2]);
        for (const Card& card0 : cards0) {
            for (const Card& card1 : cards1) {
                for (const Card& card2 : cards2) {
                    const std::array<Card, 3> cards{{card0, card1, card2}};
                    if (!is_d2_reduction_decoration(edge, cards)) continue;
                    const Counts balance = hidden_balance(edge, cards);
                    if (std::any_of(balance.begin(), balance.end(),
                                    [](int value) { return value < 0; })) {
                        continue;
                    }
                    std::array<std::vector<CandidateWord>, 3> words;
                    for (std::size_t slot = 0; slot < 3; ++slot) {
                        words[slot] = candidate_words(edge.q_caps[slot], cards[slot]);
                    }
                    const std::uint64_t completions = completion_count(balance, words);
                    if (completions == 0) continue;
                    Decoration decoration;
                    decoration.ordinal = result.size();
                    decoration.edge_index = edge.ordinal;
                    decoration.cards = cards;
                    decoration.hidden_balance = balance;
                    decoration.residual_words_expected = completions;
                    result.push_back(std::move(decoration));
                    ++counts[edge.ordinal];
                    weights[edge.ordinal] += completions;
                }
            }
        }
    }
    require(counts == std::array<std::uint64_t, 2>{{58, 132}},
            "per-edge D2 decoration counts are not 58/132");
    require(weights == std::array<std::uint64_t, 2>{{924, 12012}},
            "per-edge D2 residual counts are not 924/12012");
    require(result.size() == kExpectedDecorations,
            "two-source D2 decoration count is not 190");
    return result;
}

std::string digits(const std::vector<int>& values) {
    std::string result;
    result.reserve(values.size());
    for (const int value : values) result.push_back(static_cast<char>('0' + value));
    return result;
}

class FixedFutureSolver {
public:
    struct Result {
        bool solvable = false;
        std::uint32_t safe_mask = 0;
        std::string path;
        std::uint64_t states = 0;
        std::uint64_t transitions = 0;
    };

    FixedFutureSolver(const Debts& debts,
                      const std::array<Source, kColors>& sources,
                      const std::array<std::vector<int>, kColors>& words)
        : initial_debts_(debts), sources_(sources) {
        std::uint32_t multiplier = 1;
        for (std::size_t column = 0; column < kColors; ++column) {
            build_events(column, words[column]);
            multipliers_[column] = multiplier;
            multiplier *= static_cast<std::uint32_t>(events_[column].size() + 1);
        }
        memo_.assign(multiplier, -1);
    }

    Result solve() {
        Result result;
        result.solvable = visit(0);
        for (std::size_t column = 0; column < kColors; ++column) {
            if (safe_from(0, column)) result.safe_mask |= 1U << column;
        }
        if (result.solvable) {
            std::uint32_t state = 0;
            while (!goal(state)) {
                bool advanced = false;
                for (std::size_t column = 0; column < kColors; ++column) {
                    if (!safe_from(state, column)) continue;
                    result.path.push_back(static_cast<char>('0' + column));
                    state += multipliers_[column];
                    advanced = true;
                    break;
                }
                require(advanced, "winning state has no winning successor");
            }
        }
        result.states = states_;
        result.transitions = transitions_;
        return result;
    }

    bool replay(const std::string& path) const {
        std::uint32_t state = 0;
        for (const char value : path) {
            const std::size_t column = static_cast<std::size_t>(value - '0');
            if (column >= kColors || !legal(state, column)) return false;
            state += multipliers_[column];
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

    Debts initial_debts_{};
    std::array<Source, kColors> sources_{};
    std::array<std::vector<Event>, kColors> events_;
    std::array<std::vector<Debts>, kColors> deltas_;
    std::array<std::uint32_t, kColors> multipliers_{};
    std::vector<std::int8_t> memo_;
    std::uint64_t states_ = 0;
    std::uint64_t transitions_ = 0;

    void build_events(std::size_t column, const std::vector<int>& word) {
        int old_color = sources_[column].color;
        int old_cap = sources_[column].cap;
        int cursor = static_cast<int>(word.size()) - 1;
        while (cursor >= 0) {
            const int next_color = word[static_cast<std::size_t>(cursor)];
            require(next_color != old_color, "word repeats current top color");
            int first = cursor;
            while (first > 0 && word[static_cast<std::size_t>(first - 1)] == next_color) {
                --first;
            }
            const int length = cursor - first + 1;
            const int next_cap = old_cap + length;
            events_[column].push_back({old_color, old_cap, next_color, next_cap});
            old_color = next_color;
            old_cap = next_cap;
            cursor = first - 1;
        }
        require(!events_[column].empty() && events_[column].back().next_cap == kHeight,
                "fixed column does not end at height seven");
        deltas_[column].assign(events_[column].size() + 1, Debts{});
        for (std::size_t index = 0; index < events_[column].size(); ++index) {
            deltas_[column][index + 1] = deltas_[column][index];
            const Event& event = events_[column][index];
            deltas_[column][index + 1][event.old_color] += event.old_cap;
            if (event.next_cap == kHeight) {
                deltas_[column][index + 1][event.next_color] +=
                    kHeight - event.old_cap;
            } else {
                deltas_[column][index + 1][event.next_color] -= event.old_cap;
            }
        }
    }

    std::array<std::size_t, kColors> decode(std::uint32_t state) const {
        std::array<std::size_t, kColors> ranks{};
        for (std::size_t column = 0; column < kColors; ++column) {
            ranks[column] = (state / multipliers_[column]) %
                            (events_[column].size() + 1);
        }
        return ranks;
    }

    int exhausted(const std::array<std::size_t, kColors>& ranks) const {
        int count = 0;
        for (std::size_t column = 0; column < kColors; ++column) {
            count += ranks[column] == events_[column].size();
        }
        return count;
    }

    bool goal(std::uint32_t state) const {
        return exhausted(decode(state)) >= kEmpty;
    }

    bool legal(std::uint32_t state, std::size_t column) const {
        const auto ranks = decode(state);
        if (ranks[column] == events_[column].size()) return false;
        Debts debts = initial_debts_;
        for (std::size_t other = 0; other < kColors; ++other) {
            for (int color = 0; color < kColors; ++color) {
                debts[color] += deltas_[other][ranks[other]][color];
            }
        }
        const Event& event = events_[column][ranks[column]];
        debts[event.old_color] += event.old_cap;
        return positive_count(debts) <= kEmpty + exhausted(ranks);
    }

    bool safe_from(std::uint32_t state, std::size_t column) {
        if (goal(state) || !legal(state, column)) return false;
        ++transitions_;
        return visit(state + multipliers_[column]);
    }

    bool visit(std::uint32_t state) {
        if (goal(state)) return true;
        std::int8_t& memo = memo_[state];
        if (memo >= 0) return memo != 0;
        ++states_;
        for (std::size_t column = 0; column < kColors; ++column) {
            if (safe_from(state, column)) {
                memo = 1;
                return true;
            }
        }
        memo = 0;
        return false;
    }
};

PrefixColumn make_prefix_column(const std::vector<int>& prefix) {
    require(!prefix.empty() && prefix.back() == 0,
            "past prefix does not end at q");
    PrefixColumn result;
    result.top_to_bottom = prefix;
    struct Run { int color; int length; };
    std::vector<Run> runs;
    for (const int color : prefix) {
        if (!runs.empty() && runs.back().color == color) ++runs.back().length;
        else runs.push_back({color, 1});
    }
    int old_color = runs.front().color;
    int old_cap = runs.front().length;
    for (std::size_t index = 1; index < runs.size(); ++index) {
        const int next_cap = old_cap + runs[index].length;
        result.events.push_back({old_color, old_cap, runs[index].color, next_cap});
        result.delta[old_color] += old_cap;
        result.delta[runs[index].color] -= old_cap;
        old_color = runs[index].color;
        old_cap = next_cap;
    }
    require(old_color == 0 && old_cap == static_cast<int>(prefix.size()),
            "past prefix does not expose q at the requested cap");
    return result;
}

std::vector<PrefixColumn> possible_prefix_columns(int cap) {
    std::vector<PrefixColumn> result;
    std::vector<int> prefix(static_cast<std::size_t>(cap), 0);
    const auto visit = [&](const auto& self, int position) -> void {
        if (position == cap - 1) {
            prefix.back() = 0;
            result.push_back(make_prefix_column(prefix));
            return;
        }
        for (int color = 0; color < kColors; ++color) {
            prefix[static_cast<std::size_t>(position)] = color;
            self(self, position + 1);
        }
    };
    visit(visit, 0);
    return result;
}

bool past_template_reachable(const PrefixTemplate& past) {
    std::array<std::uint32_t, kColors> multipliers{};
    std::uint32_t size = 1;
    for (std::size_t column = 0; column < kColors; ++column) {
        multipliers[column] = size;
        size *= static_cast<std::uint32_t>(past.columns[column].events.size() + 1);
    }
    std::vector<std::int8_t> memo(size, -1);
    const auto decode = [&](std::uint32_t state) {
        std::array<std::size_t, kColors> ranks{};
        for (std::size_t column = 0; column < kColors; ++column) {
            ranks[column] = (state / multipliers[column]) %
                            (past.columns[column].events.size() + 1);
        }
        return ranks;
    };
    const auto visit = [&](const auto& self, std::uint32_t state) -> bool {
        const auto ranks = decode(state);
        bool goal = true;
        for (std::size_t column = 0; column < kColors; ++column) {
            goal = goal && ranks[column] == past.columns[column].events.size();
        }
        if (goal) return true;
        std::int8_t& known = memo[state];
        if (known >= 0) return known != 0;
        Debts debts{};
        for (std::size_t column = 0; column < kColors; ++column) {
            for (std::size_t index = 0; index < ranks[column]; ++index) {
                const PastEvent& event = past.columns[column].events[index];
                debts[event.old_color] += event.old_cap;
                debts[event.next_color] -= event.old_cap;
            }
        }
        for (std::size_t column = 0; column < kColors; ++column) {
            if (ranks[column] == past.columns[column].events.size()) continue;
            const PastEvent& event = past.columns[column].events[ranks[column]];
            if (!source_legal(debts, 0, event.old_color, event.old_cap)) continue;
            if (self(self, state + multipliers[column])) {
                known = 1;
                return true;
            }
        }
        known = 0;
        return false;
    };
    return visit(visit, 0);
}

std::vector<PrefixTemplate> enumerate_past_templates(const Edge& edge) {
    const std::array<int, kColors> caps{{edge.bad_cap, edge.q_caps[0],
                                        edge.q_caps[1], edge.q_caps[2]}};
    std::array<std::vector<PrefixColumn>, kColors> choices;
    for (std::size_t column = 0; column < kColors; ++column) {
        choices[column] = possible_prefix_columns(caps[column]);
    }
    std::vector<PrefixTemplate> result;
    for (const PrefixColumn& c0 : choices[0]) {
        for (const PrefixColumn& c1 : choices[1]) {
            for (const PrefixColumn& c2 : choices[2]) {
                for (const PrefixColumn& c3 : choices[3]) {
                    PrefixTemplate candidate{{c0, c1, c2, c3}};
                    Debts total{};
                    for (const PrefixColumn& column : candidate.columns) {
                        for (int color = 0; color < kColors; ++color) {
                            total[color] += column.delta[color];
                        }
                    }
                    if (total != edge.parent_debts ||
                        !past_template_reachable(candidate)) {
                        continue;
                    }
                    result.push_back(std::move(candidate));
                }
            }
        }
    }
    require(result.size() == kExpectedPastTemplates,
            "zero-debt past-prefix template count is not 20");
    return result;
}

FixedFixture parent_fixture(
    const Edge& edge, const std::array<const CandidateWord*, 3>& q_words) {
    FixedFixture fixture;
    fixture.debts = edge.parent_debts;
    fixture.sources[0] = {edge.q_color, edge.bad_cap};
    fixture.hidden_bottom_to_top[0].assign(
        static_cast<std::size_t>(kHeight - edge.bad_cap), edge.final_color);
    for (std::size_t slot = 0; slot < 3; ++slot) {
        fixture.sources[slot + 1] = {edge.q_color, edge.q_caps[slot]};
        fixture.hidden_bottom_to_top[slot + 1] =
            q_words[slot]->word_bottom_to_top;
    }
    return fixture;
}

FixedFixture water_initial_fixture(
    const PrefixTemplate& past, const FixedFixture& parent) {
    FixedFixture result;
    Counts physical{};
    for (std::size_t column = 0; column < kColors; ++column) {
        std::vector<int> full_top_to_bottom = past.columns[column].top_to_bottom;
        for (auto iterator = parent.hidden_bottom_to_top[column].rbegin();
             iterator != parent.hidden_bottom_to_top[column].rend(); ++iterator) {
            full_top_to_bottom.push_back(*iterator);
        }
        require(full_top_to_bottom.size() == kHeight,
                "reconstructed initial column does not have height seven");
        for (const int color : full_top_to_bottom) ++physical[color];
        const int top_color = full_top_to_bottom.front();
        std::size_t top_length = 1;
        while (top_length < full_top_to_bottom.size() &&
               full_top_to_bottom[top_length] == top_color) {
            ++top_length;
        }
        result.sources[column] = {top_color, static_cast<int>(top_length)};
        result.hidden_bottom_to_top[column].assign(
            full_top_to_bottom.rbegin(),
            full_top_to_bottom.rend() - static_cast<std::ptrdiff_t>(top_length));
    }
    require(std::all_of(physical.begin(), physical.end(),
                        [](int count) { return count == kHeight; }),
            "reconstructed zero-debt layout is not color-balanced");
    return result;
}

template <class Callback>
bool for_each_completion(
    const Decoration& decoration,
    const std::array<std::vector<CandidateWord>, 3>& words,
    Callback&& callback) {
    std::unordered_map<std::uint32_t, std::vector<const CandidateWord*>> third;
    for (const CandidateWord& word : words[2]) {
        third[pack_counts(word.counts)].push_back(&word);
    }
    for (const CandidateWord& first : words[0]) {
        for (const CandidateWord& second : words[1]) {
            bool valid = false;
            const Counts needed = subtract_counts(decoration.hidden_balance,
                                                  first.counts, second.counts, valid);
            if (!valid) continue;
            const auto found = third.find(pack_counts(needed));
            if (found == third.end()) continue;
            for (const CandidateWord* last : found->second) {
                const std::array<const CandidateWord*, 3> selected{{
                    &first, &second, last}};
                if (!callback(selected)) return false;
            }
        }
    }
    return true;
}

ResidualSample sample_for(std::size_t decoration, const FixedFixture& fixture,
                          const FixedFutureSolver::Result& result) {
    ResidualSample sample;
    sample.present = true;
    sample.solvable = result.solvable;
    sample.decoration = decoration;
    for (std::size_t column = 0; column < kColors; ++column) {
        sample.words_bottom_to_top[column] =
            digits(fixture.hidden_bottom_to_top[column]);
        sample.columns_top_to_bottom[column].assign(
            static_cast<std::size_t>(fixture.sources[column].cap),
            static_cast<char>('0' + fixture.sources[column].color));
        for (auto iterator = fixture.hidden_bottom_to_top[column].rbegin();
             iterator != fixture.hidden_bottom_to_top[column].rend(); ++iterator) {
            sample.columns_top_to_bottom[column].push_back(
                static_cast<char>('0' + *iterator));
        }
        require(sample.columns_top_to_bottom[column].size() == kHeight,
                "sample column does not have height seven");
        sample.columns_bottom_to_top[column] =
            sample.columns_top_to_bottom[column];
        std::reverse(sample.columns_bottom_to_top[column].begin(),
                     sample.columns_bottom_to_top[column].end());
    }
    sample.safe_mask = result.safe_mask;
    sample.path = result.path;
    return sample;
}

RunStats run(const Options& options, const std::vector<Edge>& edges,
             const std::vector<Decoration>& decorations,
             const std::array<std::vector<PrefixTemplate>, 2>& past_templates) {
    RunStats stats;
    stats.limit_requested = options.limit;
    stats.per_decoration.resize(decorations.size());
    for (const Decoration& decoration : decorations) {
        stats.residual_words_expected += decoration.residual_words_expected;
        stats.per_decoration[decoration.ordinal].expected =
            decoration.residual_words_expected;
    }
    require(stats.residual_words_expected == kExpectedResidualWords,
            "two-source residual-word universe is not 12936");
    const std::uint64_t effective_limit = options.limit == 0
        ? stats.residual_words_expected
        : std::min(options.limit, stats.residual_words_expected);
    const auto started = std::chrono::steady_clock::now();
    bool stop = false;
    for (const Decoration& decoration : decorations) {
        const Edge& edge = edges[decoration.edge_index];
        DecorationStats& row = stats.per_decoration[decoration.ordinal];
        std::array<std::vector<CandidateWord>, 3> words;
        for (std::size_t slot = 0; slot < 3; ++slot) {
            words[slot] = candidate_words(edge.q_caps[slot], decoration.cards[slot]);
        }
        const bool completed = for_each_completion(
            decoration, words,
            [&](const std::array<const CandidateWord*, 3>& selected) {
                if (stats.residual_words_checked >= effective_limit) return false;
                const FixedFixture parent = parent_fixture(edge, selected);
                FixedFutureSolver parent_solver(parent.debts, parent.sources,
                                                parent.hidden_bottom_to_top);
                const auto parent_result = parent_solver.solve();
                ++stats.residual_words_checked;
                ++row.checked;
                stats.parent_states += parent_result.states;
                row.parent_states += parent_result.states;
                stats.parent_transitions += parent_result.transitions;
                row.parent_transitions += parent_result.transitions;
                if (parent_result.solvable) {
                    ++stats.parent_yes;
                    ++row.parent_yes;
                } else {
                    ++stats.parent_local_no;
                    ++row.parent_local_no;
                    stats.parent_local_no_samples.push_back(
                        sample_for(decoration.ordinal, parent, parent_result));
                }

                std::uint64_t local_water_checked = 0;
                std::uint64_t local_water_yes = 0;
                std::uint64_t local_water_no = 0;
                bool recovered = true;
                for (const PrefixTemplate& past : past_templates[edge.ordinal]) {
                    const FixedFixture initial = water_initial_fixture(past, parent);
                    FixedFutureSolver water_solver(
                        initial.debts, initial.sources, initial.hidden_bottom_to_top);
                    const auto water_result = water_solver.solve();
                    ++stats.water_initial_checked;
                    ++row.water_initial_checked;
                    ++local_water_checked;
                    stats.water_states += water_result.states;
                    row.water_states += water_result.states;
                    stats.water_transitions += water_result.transitions;
                    row.water_transitions += water_result.transitions;
                    if (water_result.solvable) {
                        ++stats.water_initial_yes;
                        ++row.water_initial_yes;
                        ++local_water_yes;
                        require(water_solver.replay(water_result.path),
                                "water-initial winning path did not replay");
                        ++stats.water_witnesses_replayed;
                        if (!stats.first_water_recovery) {
                            stats.first_water_recovery = sample_for(
                                decoration.ordinal, initial, water_result);
                        }
                    } else {
                        ++stats.water_initial_no;
                        ++row.water_initial_no;
                        ++local_water_no;
                        recovered = false;
                        if (!stats.first_water_local_no) {
                            stats.first_water_local_no = sample_for(
                                decoration.ordinal, initial, water_result);
                        }
                    }
                }
                if (!parent_result.solvable) {
                    if (recovered) ++stats.recovered_parent_local_no;
                    else ++stats.unresolved_parent_local_no;
                }
                PrefixRow prefix;
                prefix.decoration = decoration.ordinal;
                for (std::size_t slot = 0; slot < 3; ++slot) {
                    prefix.free_tails_top_to_bottom[slot] =
                        digits(selected[slot]->free_top_to_bottom);
                }
                prefix.parent_solvable = parent_result.solvable;
                prefix.parent_safe_mask = parent_result.safe_mask;
                prefix.parent_path = parent_result.path;
                prefix.water_initial_checked = local_water_checked;
                prefix.water_initial_yes = local_water_yes;
                prefix.water_initial_no = local_water_no;
                stats.checked_prefix.push_back(std::move(prefix));
                return true;
            });
        if (!completed && stats.residual_words_checked >= effective_limit) {
            stop = true;
            break;
        }
    }
    static_cast<void>(stop);
    stats.elapsed_seconds = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - started).count();
    stats.universe_complete =
        stats.residual_words_checked == stats.residual_words_expected;
    stats.self_checks_passed = true;
    require(stats.parent_yes + stats.parent_local_no == stats.residual_words_checked,
            "parent results do not partition checked residuals");
    require(stats.checked_prefix.size() == stats.residual_words_checked,
            "checked-prefix ledger does not cover every checked residual");
    require(stats.recovered_parent_local_no + stats.unresolved_parent_local_no ==
                stats.parent_local_no,
            "water fallback does not partition parent local NOs");
    require(stats.water_initial_yes + stats.water_initial_no ==
                stats.water_initial_checked,
            "water-initial results do not partition reconstructed layouts");
    require(stats.water_initial_checked ==
                stats.residual_words_checked * kExpectedPastTemplates,
            "water-initial audit did not cover all 20 past templates per word");
    require(stats.water_witnesses_replayed == stats.water_initial_yes,
            "a water-initial YES witness did not replay");
    if (stats.universe_complete) {
        require(stats.parent_yes == kExpectedParentYes,
                "full parent-checkpoint YES count is not zero");
        require(stats.parent_local_no == kExpectedParentLocalNo,
                "full parent-checkpoint local-NO count is not 12936");
    }
    return stats;
}

bool eliminated(const RunStats& stats) {
    return stats.universe_complete && stats.unresolved_parent_local_no == 0 &&
           stats.water_initial_no == 0 &&
           stats.recovered_parent_local_no == stats.parent_local_no &&
           stats.water_initial_checked ==
               stats.residual_words_checked * kExpectedPastTemplates &&
           stats.water_witnesses_replayed == stats.water_initial_yes;
}

std::string status(const RunStats& stats) {
    if (stats.water_initial_no != 0) return "GLOBAL_NO_FOUND";
    if (!stats.universe_complete) return "INCOMPLETE";
    if (!eliminated(stats)) return "LOCAL_NO_RESIDUALS_EXPORTED";
    return "TWO_SOURCE_D2_FAMILY_ELIMINATED";
}

void write_sample(std::ostream& output, const ResidualSample& sample) {
    if (!sample.present) {
        output << "null";
        return;
    }
    output << "{\"decoration_index\":" << sample.decoration
           << ",\"solvable\":" << (sample.solvable ? "true" : "false")
           << ",\"hidden_words_bottom_to_top\":[";
    for (std::size_t column = 0; column < kColors; ++column) {
        if (column != 0) output << ',';
        output << '"' << sample.words_bottom_to_top[column] << '"';
    }
    output << "],\"columns_top_to_bottom\":[";
    for (std::size_t column = 0; column < kColors; ++column) {
        if (column != 0) output << ',';
        output << '\"' << sample.columns_top_to_bottom[column] << '\"';
    }
    output << "],\"columns_bottom_to_top\":[";
    for (std::size_t column = 0; column < kColors; ++column) {
        if (column != 0) output << ',';
        output << '\"' << sample.columns_bottom_to_top[column] << '\"';
    }
    output << "],\"safe_mask\":" << sample.safe_mask
           << ",\"escape_columns\":\"" << sample.path << "\"}";
}

std::string cards_json(const std::array<Card, 3>& cards) {
    std::ostringstream output;
    output << '[';
    for (std::size_t slot = 0; slot < 3; ++slot) {
        if (slot != 0) output << ',';
        output << '[' << cards[slot].color << ',' << cards[slot].endpoint << ']';
    }
    output << ']';
    return output.str();
}

void write_report(const Options& options, const std::vector<Edge>& edges,
                  const std::vector<Decoration>& decorations,
                  const RunStats& stats) {
    if (options.output_dir.empty()) return;
    std::filesystem::create_directories(options.output_dir);
    std::ofstream json(options.output_dir / "report.json");
    if (!json) throw std::runtime_error("cannot write report.json");
    json << "{\n"
         << "  \"schema_version\": 1,\n"
         << "  \"coverage_scope\": \"c4_h7_d2_reduction_two_legal_source_fixed_residuals\",\n"
         << "  \"status\": \"" << status(stats) << "\",\n"
         << "  \"verified\": "
         << (stats.universe_complete && stats.self_checks_passed ? "true" : "false")
         << ",\n"
         << "  \"global_no_independently_verified\": false,\n"
         << "  \"self_checks_passed\": "
         << (stats.self_checks_passed ? "true" : "false") << ",\n"
         << "  \"limit_requested\": " << stats.limit_requested << ",\n"
         << "  \"limit_unit\": \"edge_summed_fixed_residual_words\",\n"
         << "  \"ordering\": \"edge e245 then e246; q slots in stored cap order; cards color-major then endpoint-major; free tails top-to-bottom lexicographic\",\n"
         << "  \"source_first_exhaust_report\": {"
         << "\"legal_source_count\":2,\"canonical_edges\":2,"
         << "\"d2_decorations\":190,\"edge_summed_residual_words\":12936},\n"
         << "  \"canonical_edge_count\": " << edges.size() << ",\n"
         << "  \"decorations_expected\": " << decorations.size() << ",\n"
         << "  \"residual_words_expected\": " << stats.residual_words_expected << ",\n"
         << "  \"residual_words_checked\": " << stats.residual_words_checked << ",\n"
         << "  \"parent_checkpoint_yes_count\": " << stats.parent_yes << ",\n"
         << "  \"parent_checkpoint_local_no_count\": "
         << stats.parent_local_no << ",\n"
         << "  \"past_prefix_templates_per_edge\": 20,\n"
         << "  \"parent_local_no_recovered_count\": "
         << stats.recovered_parent_local_no << ",\n"
         << "  \"unresolved_parent_local_no_count\": "
         << stats.unresolved_parent_local_no << ",\n"
         << "  \"water_initial_layouts_checked\": "
         << stats.water_initial_checked << ",\n"
         << "  \"water_initial_yes_count\": " << stats.water_initial_yes << ",\n"
         << "  \"water_initial_no_count\": " << stats.water_initial_no << ",\n"
         << "  \"water_initial_witnesses_replayed\": "
         << stats.water_witnesses_replayed << ",\n"
         << "  \"local_no_count\": "
         << stats.unresolved_parent_local_no << ",\n"
         << "  \"global_no_count\": " << stats.water_initial_no << ",\n"
         << "  \"universe_complete\": "
         << (stats.universe_complete ? "true" : "false") << ",\n"
         << "  \"fixed_residual_universe_complete\": "
         << (stats.universe_complete ? "true" : "false") << ",\n"
         << "  \"two_source_d2_family_eliminated\": "
         << (eliminated(stats) ? "true" : "false") << ",\n"
         << "  \"d2_family_eliminated\": false,\n"
         << "  \"entry_family_eliminated\": false,\n"
         << "  \"full_layout_coverage\": false,\n"
         << "  \"parent_states_evaluated\": " << stats.parent_states << ",\n"
         << "  \"parent_transitions_tested\": " << stats.parent_transitions << ",\n"
         << "  \"water_initial_states_evaluated\": " << stats.water_states << ",\n"
         << "  \"water_initial_transitions_tested\": "
         << stats.water_transitions << ",\n"
         << "  \"per_edge\": [";
    for (std::size_t edge_index = 0; edge_index < edges.size(); ++edge_index) {
        if (edge_index != 0) json << ',';
        std::uint64_t expected = 0;
        std::uint64_t checked = 0;
        std::uint64_t yes = 0;
        std::uint64_t no = 0;
        for (const Decoration& decoration : decorations) {
            if (decoration.edge_index != edge_index) continue;
            const DecorationStats& row = stats.per_decoration[decoration.ordinal];
            expected += row.expected;
            checked += row.checked;
            yes += row.parent_yes;
            no += row.parent_local_no;
        }
        const Edge& edge = edges[edge_index];
        json << "{\"edge_id\":\"" << edge.id << "\",\"bad_cap\":"
             << edge.bad_cap << ",\"q_caps\":[" << edge.q_caps[0] << ','
             << edge.q_caps[1] << ',' << edge.q_caps[2]
             << "],\"residual_words_expected\":" << expected
             << ",\"residual_words_checked\":" << checked
             << ",\"parent_checkpoint_yes_count\":" << yes
             << ",\"parent_checkpoint_local_no_count\":" << no << '}';
    }
    json << "],\n  \"per_decoration\": [\n";
    for (std::size_t index = 0; index < decorations.size(); ++index) {
        if (index != 0) json << ",\n";
        const Decoration& decoration = decorations[index];
        const Edge& edge = edges[decoration.edge_index];
        const DecorationStats& row = stats.per_decoration[index];
        json << "    {\"decoration_index\":" << index
             << ",\"edge_id\":\"" << edge.id << "\",\"cards\":"
             << cards_json(decoration.cards)
             << ",\"residual_words_expected\":" << row.expected
             << ",\"residual_words_checked\":" << row.checked
             << ",\"parent_checkpoint_yes_count\":" << row.parent_yes
             << ",\"parent_checkpoint_local_no_count\":" << row.parent_local_no
             << ",\"water_initial_layouts_checked\":"
             << row.water_initial_checked
             << ",\"water_initial_yes_count\":" << row.water_initial_yes
             << ",\"water_initial_no_count\":" << row.water_initial_no << '}';
    }
    json << "\n  ],\n  \"checked_prefix\": [";
    for (std::size_t index = 0; index < stats.checked_prefix.size(); ++index) {
        if (index != 0) json << ',';
        const PrefixRow& row = stats.checked_prefix[index];
        json << "{\"decoration_index\":" << row.decoration
             << ",\"free_tails_top_to_bottom\":[\""
             << row.free_tails_top_to_bottom[0] << "\",\""
             << row.free_tails_top_to_bottom[1] << "\",\""
             << row.free_tails_top_to_bottom[2] << "\"]"
             << ",\"parent_checkpoint_solvable\":"
             << (row.parent_solvable ? "true" : "false")
             << ",\"parent_safe_mask\":" << row.parent_safe_mask
             << ",\"parent_escape_columns\":\"" << row.parent_path << "\""
             << ",\"water_initial_layouts_checked\":"
             << row.water_initial_checked
             << ",\"water_initial_yes_count\":" << row.water_initial_yes
             << ",\"water_initial_no_count\":" << row.water_initial_no << '}';
    }
    json << ']';
    if (!stats.parent_local_no_samples.empty()) {
        json << ",\n  \"first_parent_checkpoint_local_no\": ";
        write_sample(json, stats.parent_local_no_samples.front());
    }
    if (stats.first_water_recovery) {
        json << ",\n  \"first_water_initial_recovery\": ";
        write_sample(json, *stats.first_water_recovery);
    }
    if (stats.first_water_local_no) {
        json << ",\n  \"first_water_initial_local_no\": ";
        write_sample(json, *stats.first_water_local_no);
        json << ",\n  \"first_global_no_candidate\": ";
        write_sample(json, *stats.first_water_local_no);
    }
    json << ",\n  \"elapsed_seconds\": " << stats.elapsed_seconds << "\n}\n";

    std::ofstream markdown(options.output_dir / "report.md");
    if (!markdown) throw std::runtime_error("cannot write report.md");
    markdown << "# c=4, h=7 two-legal-source D2 residual audit\n\n"
             << "- Status: **" << status(stats) << "**\n"
             << "- Scope: 190 D2-reduction decorations on edges e245/e246 only.\n"
             << "- Edge-summed fixed residual words: "
             << stats.residual_words_checked << " / "
             << stats.residual_words_expected << ".\n"
             << "- Parent checkpoint YES / local NO: " << stats.parent_yes
             << " / " << stats.parent_local_no << ".\n"
             << "- Reconstructed zero-debt layouts checked / YES / local NO: "
             << stats.water_initial_checked << " / " << stats.water_initial_yes
             << " / " << stats.water_initial_no << ".\n"
             << "- Complete balanced-layout global-NO candidates: "
             << stats.water_initial_no << ".\n"
             << "- This does not eliminate the 3-source or 4-source D2 remainder.\n";

    if (!stats.parent_local_no_samples.empty()) {
        std::ofstream residuals(
            options.output_dir / "parent-checkpoint-local-no-residuals.jsonl");
        if (!residuals) {
            throw std::runtime_error(
                "cannot write parent-checkpoint-local-no-residuals.jsonl");
        }
        for (const ResidualSample& sample : stats.parent_local_no_samples) {
            residuals << "{\"scope\":\"two_source_d2_parent_checkpoint\","
                         "\"residual\":";
            write_sample(residuals, sample);
            residuals << "}\n";
        }
    }

    if (stats.first_water_local_no) {
        std::ofstream candidate_json(options.output_dir / "global-no-candidate.json");
        if (!candidate_json) {
            throw std::runtime_error("cannot write global-no-candidate.json");
        }
        candidate_json << "{\"scope\":\"complete_balanced_c4_h7_layout\","
                          "\"independently_verified\":false,\"candidate\":";
        write_sample(candidate_json, *stats.first_water_local_no);
        candidate_json << "}\n";

        std::ofstream candidate_text(options.output_dir / "global-no-candidate.txt");
        if (!candidate_text) {
            throw std::runtime_error("cannot write global-no-candidate.txt");
        }
        candidate_text << "# c=4 h=7 complete balanced candidate\n"
                       << "# Columns are written bottom-to-top.\n"
                       << "height=7\ncolors=4\nempty=2\n";
        for (const std::string& column :
             stats.first_water_local_no->columns_bottom_to_top) {
            candidate_text << "column=" << column << '\n';
        }
    }
}

} // namespace

int main(int argc, char** argv) {
    try {
        Options options = parse_options(argc, argv);
        const auto edges = build_edges();
        const auto decorations = enumerate_decorations(edges);
        std::array<std::vector<PrefixTemplate>, 2> past_templates;
        for (const Edge& edge : edges) {
            past_templates[edge.ordinal] = enumerate_past_templates(edge);
        }
        if (options.self_test && options.output_dir.empty() && options.limit == 0) {
            options.limit = 64;
        }
        const RunStats stats = run(options, edges, decorations, past_templates);
        write_report(options, edges, decorations, stats);
        std::cout << "status=" << status(stats)
                  << " edges=" << edges.size()
                  << " decorations=" << decorations.size()
                  << " residual=" << stats.residual_words_checked << '/'
                  << stats.residual_words_expected
                  << " parent_yes=" << stats.parent_yes
                  << " parent_local_no=" << stats.parent_local_no
                  << " water_yes=" << stats.water_initial_yes
                  << " water_local_no=" << stats.water_initial_no << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
