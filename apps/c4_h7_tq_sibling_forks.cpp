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
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <set>
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

constexpr int kHeight = 7;
constexpr int kColors = 4;
constexpr int kEmpty = 2;
constexpr std::uint64_t kExpectedResidualWords = 10073448;

struct Options {
    std::filesystem::path output_dir;
    std::uint64_t limit = 0;
    bool self_test = false;
};

struct Bucket {
    int debt = 0;
    std::vector<int> caps;

    bool operator<(const Bucket& other) const {
        return std::tie(debt, caps) < std::tie(other.debt, other.caps);
    }
    bool operator==(const Bucket& other) const {
        return debt == other.debt && caps == other.caps;
    }
};

using State = std::array<Bucket, kColors>;
using Debts = std::array<int, kColors>;
using Counts = std::array<int, kColors>;

struct Source {
    int color = 0;
    int cap = 0;
};

struct Action {
    int old_color = 0;
    int old_cap = 0;
    int new_color = 0;
    int new_cap = 0;

    bool operator<(const Action& other) const {
        return std::tie(old_color, old_cap, new_color, new_cap) <
               std::tie(other.old_color, other.old_cap,
                        other.new_color, other.new_cap);
    }
};

struct Card {
    int color = 0;
    int cap = 0; // cap==7 is the exhausting final run.
};

struct CandidateWord {
    std::vector<Color> word; // bottom to top, below the checkpoint border.
    Counts counts{};
};

struct Edge {
    std::size_t ordinal = 0;
    State parent;
    State terminal;
    Action bad;
    Debts parent_debts{};
    Debts terminal_debts{}; // in the parent's labeled coordinates.
    std::array<Source, 3> columns{}; // bad, sibling 0, sibling 1.
    Counts remaining{};
    std::uint64_t raw_single = 0;
    std::uint64_t raw_simultaneous = 0;
};

struct Decoration {
    std::size_t edge = 0;
    std::array<Card, 3> cards{}; // bad card, sibling cards.
    std::uint64_t completions = 0;
    bool direct_exhaustion = false;
    std::uint32_t persistent_bad_sources = 0;
};

struct Sample {
    bool present = false;
    bool solvable = false;
    std::array<std::string, 3> words;
    std::string removal_columns;
    std::uint32_t safe_mask = 0;
};

struct EdgeStats {
    std::uint64_t feasible_decorations = 0;
    std::uint64_t residual_words_expected = 0;
    std::uint64_t residual_words_checked = 0;
    std::uint64_t checkpoint_yes = 0;
    std::uint64_t local_no = 0;
    std::uint64_t states_evaluated = 0;
    std::uint64_t transitions_tested = 0;
    std::array<std::uint64_t, 3> safe_source_counts{};
    std::uint64_t both_siblings_safe = 0;
    Sample sample;
};

struct RunStats {
    bool self_checks_passed = false;
    bool next_run_census_complete = false;
    bool residual_word_universe_complete = false;
    std::uint64_t raw_single = 0;
    std::uint64_t raw_simultaneous = 0;
    std::uint64_t feasible_decorations = 0;
    std::uint64_t infeasible_decorations = 0;
    std::uint64_t direct_exhaustion_decorations = 0;
    std::uint64_t bad_source_persistent_decorations = 0;
    std::uint64_t obstruction_decorations = 0;
    std::uint64_t residual_words_expected = 0;
    std::uint64_t residual_words_checked = 0;
    std::uint64_t checkpoint_yes = 0;
    std::uint64_t local_no = 0;
    std::uint64_t states_evaluated = 0;
    std::uint64_t transitions_tested = 0;
    std::array<std::uint64_t, 3> safe_source_counts{};
    std::uint64_t both_siblings_safe = 0;
    double elapsed_seconds = 0.0;
    std::vector<EdgeStats> edges;
    std::optional<std::pair<std::size_t, Sample>> first_local_no;
};

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error("self-check failed: " + message);
}

void usage() {
    std::cerr << "Usage: water-c4-h7-tq-sibling-forks "
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

State canonical_state(const Debts& debts,
                      const std::array<std::vector<int>, kColors>& caps) {
    State result;
    for (int color = 0; color < kColors; ++color) {
        result[static_cast<std::size_t>(color)] = {debts[color], caps[color]};
        std::sort(result[static_cast<std::size_t>(color)].caps.begin(),
                  result[static_cast<std::size_t>(color)].caps.end());
    }
    std::sort(result.begin(), result.end());
    return result;
}

Debts state_debts(const State& state) {
    Debts result{};
    for (int color = 0; color < kColors; ++color) result[color] = state[color].debt;
    return result;
}

std::array<std::vector<int>, kColors> state_caps(const State& state) {
    std::array<std::vector<int>, kColors> result;
    for (int color = 0; color < kColors; ++color) result[color] = state[color].caps;
    return result;
}

Counts exposed_counts(const State& state) {
    Counts result{};
    for (int color = 0; color < kColors; ++color) {
        result[color] = state[color].debt;
        for (const int cap : state[color].caps) result[color] += cap;
    }
    return result;
}

int positive_count(const Debts& debts) {
    return static_cast<int>(std::count_if(
        debts.begin(), debts.end(), [](int value) { return value > 0; }));
}

bool algebraically_consistent(const State& state, int z) {
    if (!std::is_sorted(state.begin(), state.end())) return false;
    int cap_count = 0;
    int debt_sum = 0;
    Counts multiplicity{};
    for (int color = 0; color < kColors; ++color) {
        debt_sum += state[color].debt;
        multiplicity[color] = static_cast<int>(state[color].caps.size());
        cap_count += multiplicity[color];
        for (const int cap : state[color].caps) {
            if (cap < 1 || cap >= kHeight) return false;
        }
    }
    if (cap_count != kColors - z || debt_sum != z * kHeight) return false;
    const auto exposed = exposed_counts(state);
    Counts remaining{};
    for (int color = 0; color < kColors; ++color) {
        if (exposed[color] < multiplicity[color] || exposed[color] > kHeight) return false;
        remaining[color] = kHeight - exposed[color];
    }
    for (int color = 0; color < kColors; ++color) {
        int available = 0;
        for (int other = 0; other < kColors; ++other) {
            if (other != color) available += remaining[other];
        }
        if (multiplicity[color] > available) return false;
    }
    return true;
}

bool source_legal(const State& state, int z, int color, int cap) {
    auto debts = state_debts(state);
    debts[color] += cap;
    return positive_count(debts) <= kEmpty + z;
}

std::vector<Source> physical_sources(const State& state) {
    std::vector<Source> result;
    for (int color = 0; color < kColors; ++color) {
        for (const int cap : state[color].caps) result.push_back({color, cap});
    }
    return result;
}

std::vector<Source> legal_sources(const State& state, int z) {
    auto result = physical_sources(state);
    result.erase(std::remove_if(result.begin(), result.end(), [&](const Source& source) {
                     return !source_legal(state, z, source.color, source.cap);
                 }),
                 result.end());
    return result;
}

std::optional<State> apply_live(const State& state, int z, const Action& action) {
    if (action.old_color == action.new_color || action.old_cap < 1 ||
        action.old_cap >= action.new_cap || action.new_cap >= kHeight) {
        return std::nullopt;
    }
    auto debts = state_debts(state);
    auto caps = state_caps(state);
    auto found = std::find(caps[action.old_color].begin(),
                           caps[action.old_color].end(), action.old_cap);
    if (found == caps[action.old_color].end() ||
        !source_legal(state, z, action.old_color, action.old_cap)) {
        return std::nullopt;
    }
    caps[action.old_color].erase(found);
    caps[action.new_color].push_back(action.new_cap);
    debts[action.old_color] += action.old_cap;
    debts[action.new_color] -= action.old_cap;
    auto successor = canonical_state(debts, caps);
    if (!algebraically_consistent(successor, z)) return std::nullopt;
    return successor;
}

std::vector<Action> live_actions_to(const State& parent, const State& terminal) {
    std::vector<Action> result;
    for (int old_color = 0; old_color < kColors; ++old_color) {
        std::set<int> old_caps(parent[old_color].caps.begin(), parent[old_color].caps.end());
        for (const int old_cap : old_caps) {
            for (int new_color = 0; new_color < kColors; ++new_color) {
                if (new_color == old_color) continue;
                for (int new_cap = old_cap + 1; new_cap < kHeight; ++new_cap) {
                    const Action action{old_color, old_cap, new_color, new_cap};
                    const auto successor = apply_live(parent, 1, action);
                    if (successor && *successor == terminal) result.push_back(action);
                }
            }
        }
    }
    std::sort(result.begin(), result.end());
    return result;
}

bool tq_terminal(const State& state) {
    if (!algebraically_consistent(state, 1) || !legal_sources(state, 1).empty()) return false;
    int nonpositive = -1;
    int positives = 0;
    for (int color = 0; color < kColors; ++color) {
        if (state[color].debt > 0) ++positives;
        else {
            if (nonpositive != -1) return false;
            nonpositive = color;
        }
    }
    if (positives != 3 || nonpositive < 0) return false;
    for (int color = 0; color < kColors; ++color) {
        if (color == nonpositive) {
            if (state[color].caps.size() != 3) return false;
        } else if (!state[color].caps.empty()) {
            return false;
        }
    }
    return true;
}

std::vector<State> enumerate_tq_terminals() {
    std::set<State> states;
    for (int e = 0; e <= 2; ++e) {
        for (int a = 1; a < kHeight; ++a) {
            for (int b = a; b < kHeight; ++b) {
                for (int c = b; c < kHeight; ++c) {
                    if (a <= e || a + b + c - e > kHeight) continue;
                    for (int x = 1; x <= kHeight; ++x) {
                        for (int y = x; y <= kHeight; ++y) {
                            for (int z = y; z <= kHeight; ++z) {
                                if (x + y + z - e != kHeight) continue;
                                State state{{{-e, {a, b, c}}, {x, {}}, {y, {}}, {z, {}}}};
                                std::sort(state.begin(), state.end());
                                if (tq_terminal(state)) states.insert(std::move(state));
                            }
                        }
                    }
                }
            }
        }
    }
    return {states.begin(), states.end()};
}

std::vector<State> reverse_parents(const State& terminal) {
    std::set<State> parents;
    for (int new_color = 0; new_color < kColors; ++new_color) {
        std::set<int> new_caps(terminal[new_color].caps.begin(), terminal[new_color].caps.end());
        for (const int new_cap : new_caps) {
            for (int old_color = 0; old_color < kColors; ++old_color) {
                if (old_color == new_color) continue;
                for (int old_cap = 1; old_cap < new_cap; ++old_cap) {
                    auto debts = state_debts(terminal);
                    auto caps = state_caps(terminal);
                    auto found = std::find(caps[new_color].begin(),
                                           caps[new_color].end(), new_cap);
                    caps[new_color].erase(found);
                    caps[old_color].push_back(old_cap);
                    debts[old_color] -= old_cap;
                    debts[new_color] += old_cap;
                    auto test = debts;
                    test[old_color] += old_cap;
                    if (positive_count(test) > 3) continue;
                    auto parent = canonical_state(debts, caps);
                    if (algebraically_consistent(parent, 1)) parents.insert(std::move(parent));
                }
            }
        }
    }
    return {parents.begin(), parents.end()};
}

std::vector<Edge> enumerate_edges() {
    const auto terminals = enumerate_tq_terminals();
    require(terminals.size() == 71, "Tq terminal count is not 71");

    std::set<std::pair<State, State>> all_pairs;
    std::set<State> all_parents;
    for (const auto& terminal : terminals) {
        for (const auto& parent : reverse_parents(terminal)) {
            all_parents.insert(parent);
            all_pairs.emplace(parent, terminal);
        }
    }
    require(all_parents.size() == 80, "Tq reverse parent count is not 80");
    require(all_pairs.size() == 116, "Tq reverse edge count is not 116");

    std::vector<Edge> result;
    std::set<State> sibling_parents;
    for (const auto& pair : all_pairs) {
        const auto& parent = pair.first;
        const auto& terminal = pair.second;
        const auto legal = legal_sources(parent, 1);
        if (legal.size() < 2) continue;
        const auto actions = live_actions_to(parent, terminal);
        require(!actions.empty(), "reverse edge has no replay action");
        const auto bad = actions.front();

        auto sources = physical_sources(parent);
        auto selected = std::find_if(sources.begin(), sources.end(), [&](const Source& source) {
            return source.color == bad.old_color && source.cap == bad.old_cap;
        });
        require(selected != sources.end(), "bad physical source missing");
        Source bad_source = *selected;
        sources.erase(selected);
        require(sources.size() == 2, "z=1 parent does not have three sources");
        require(legal.size() == 3, "Tq sibling parent does not have three legal sources");
        require(sources[0].color == bad.new_color && sources[1].color == bad.new_color,
                "Tq siblings are not both q sources");

        Edge edge;
        edge.parent = parent;
        edge.terminal = terminal;
        edge.bad = bad;
        edge.parent_debts = state_debts(parent);
        edge.terminal_debts = edge.parent_debts;
        edge.terminal_debts[bad.old_color] += bad.old_cap;
        edge.terminal_debts[bad.new_color] -= bad.old_cap;
        edge.columns = {bad_source, sources[0], sources[1]};
        const auto exposed = exposed_counts(parent);
        for (int color = 0; color < kColors; ++color) {
            edge.remaining[color] = kHeight - exposed[color];
        }
        const auto cards0 = 3ULL * static_cast<std::uint64_t>(kHeight - sources[0].cap);
        const auto cards1 = 3ULL * static_cast<std::uint64_t>(kHeight - sources[1].cap);
        edge.raw_single = cards0 + cards1;
        edge.raw_simultaneous = cards0 * cards1;
        result.push_back(std::move(edge));
        sibling_parents.insert(parent);
    }
    require(sibling_parents.size() == 23, "Tq sibling parent count is not 23");
    require(result.size() == 32, "Tq sibling bad edge count is not 32");
    std::sort(result.begin(), result.end(), [](const Edge& left, const Edge& right) {
        return std::tie(left.parent, left.terminal, left.bad) <
               std::tie(right.parent, right.terminal, right.bad);
    });
    for (std::size_t i = 0; i < result.size(); ++i) result[i].ordinal = i;
    return result;
}

std::vector<Card> cards_for(const Source& source) {
    std::vector<Card> result;
    for (int color = 0; color < kColors; ++color) {
        if (color == source.color) continue;
        for (int cap = source.cap + 1; cap <= kHeight; ++cap) {
            result.push_back({color, cap});
        }
    }
    return result;
}

std::string word_string(const std::vector<Color>& word) {
    std::string result;
    for (const auto color : word) result.push_back(water_sort::color_to_char(color));
    return result;
}

std::vector<CandidateWord> candidate_words(int old_cap, const Card& card) {
    const int length = kHeight - old_cap;
    const int forced = card.cap - old_cap;
    const int free = length - forced;
    require(length > 0 && forced > 0 && free >= 0, "invalid candidate-word card");
    CandidateWord current;
    current.word.assign(static_cast<std::size_t>(length), 0);
    for (int position = free; position < length; ++position) {
        current.word[static_cast<std::size_t>(position)] =
            static_cast<Color>(card.color);
    }
    std::vector<CandidateWord> result;
    std::function<void(int)> visit = [&](int position) {
        if (position == free) {
            if (free > 0 && current.word[static_cast<std::size_t>(free - 1)] == card.color) {
                return;
            }
            current.counts.fill(0);
            for (const auto color : current.word) ++current.counts[color];
            result.push_back(current);
            return;
        }
        for (int color = 0; color < kColors; ++color) {
            current.word[static_cast<std::size_t>(position)] = static_cast<Color>(color);
            visit(position + 1);
        }
    };
    visit(0);
    return result;
}

std::uint32_t pack_counts(const Counts& counts) {
    std::uint32_t result = 0;
    for (int color = 0; color < kColors; ++color) {
        result |= static_cast<std::uint32_t>(counts[color]) << (4 * color);
    }
    return result;
}

Counts subtract_counts(const Counts& total, const Counts& left, const Counts& middle,
                       bool& valid) {
    Counts result{};
    valid = true;
    for (int color = 0; color < kColors; ++color) {
        result[color] = total[color] - left[color] - middle[color];
        if (result[color] < 0) valid = false;
    }
    return result;
}

bool bad_source_persists(const Edge& edge, const Source& sibling, const Card& card) {
    if (card.cap == kHeight) return false;
    auto debts = edge.parent_debts;
    debts[sibling.color] += sibling.cap;
    debts[card.color] -= sibling.cap;
    debts[edge.bad.old_color] += edge.bad.old_cap;
    return positive_count(debts) <= 3;
}

struct WordCacheKey {
    int old_cap = 0;
    int color = 0;
    int cap = 0;
    bool operator<(const WordCacheKey& other) const {
        return std::tie(old_cap, color, cap) <
               std::tie(other.old_cap, other.color, other.cap);
    }
};

using WordCache = std::map<WordCacheKey, std::vector<CandidateWord>>;

const std::vector<CandidateWord>& words_for(WordCache& cache, int old_cap,
                                            const Card& card) {
    const WordCacheKey key{old_cap, card.color, card.cap};
    auto found = cache.find(key);
    if (found == cache.end()) {
        found = cache.emplace(key, candidate_words(old_cap, card)).first;
    }
    return found->second;
}

std::uint64_t completion_count(const Edge& edge, const std::array<Card, 3>& cards,
                               WordCache& cache) {
    const auto& first = words_for(cache, edge.columns[0].cap, cards[0]);
    const auto& second = words_for(cache, edge.columns[1].cap, cards[1]);
    const auto& third = words_for(cache, edge.columns[2].cap, cards[2]);
    std::unordered_map<std::uint32_t, std::uint64_t> third_counts;
    for (const auto& word : third) ++third_counts[pack_counts(word.counts)];
    std::uint64_t total = 0;
    for (const auto& left : first) {
        for (const auto& middle : second) {
            bool valid = false;
            const auto needed = subtract_counts(edge.remaining, left.counts,
                                                middle.counts, valid);
            if (!valid) continue;
            const auto found = third_counts.find(pack_counts(needed));
            if (found != third_counts.end()) total += found->second;
        }
    }
    return total;
}

std::vector<Decoration> enumerate_decorations(const std::vector<Edge>& edges,
                                               WordCache& cache, RunStats& stats) {
    std::vector<Decoration> result;
    for (const auto& edge : edges) {
        stats.raw_single += edge.raw_single;
        stats.raw_simultaneous += edge.raw_simultaneous;
        const Card bad{edge.bad.new_color, edge.bad.new_cap};
        const auto left_cards = cards_for(edge.columns[1]);
        const auto right_cards = cards_for(edge.columns[2]);
        for (const auto& left : left_cards) {
            for (const auto& right : right_cards) {
                Decoration decoration;
                decoration.edge = edge.ordinal;
                decoration.cards = {bad, left, right};
                decoration.direct_exhaustion =
                    left.cap == kHeight || right.cap == kHeight;
                decoration.persistent_bad_sources =
                    static_cast<std::uint32_t>(bad_source_persists(
                        edge, edge.columns[1], left)) +
                    static_cast<std::uint32_t>(bad_source_persists(
                        edge, edge.columns[2], right));
                decoration.completions = completion_count(edge, decoration.cards, cache);
                if (decoration.completions == 0) {
                    ++stats.infeasible_decorations;
                    continue;
                }
                ++stats.feasible_decorations;
                stats.residual_words_expected += decoration.completions;
                if (decoration.direct_exhaustion) ++stats.direct_exhaustion_decorations;
                if (decoration.persistent_bad_sources != 0) {
                    ++stats.bad_source_persistent_decorations;
                } else if (!decoration.direct_exhaustion) {
                    ++stats.obstruction_decorations;
                }
                result.push_back(std::move(decoration));
            }
        }
    }
    stats.next_run_census_complete = true;
    require(stats.raw_single == 840, "raw single-card count is not 840");
    require(stats.raw_simultaneous == 5526, "raw simultaneous count is not 5526");
    require(stats.feasible_decorations == 2958, "feasible decoration count is not 2958");
    require(stats.residual_words_expected == kExpectedResidualWords,
            "residual-word count is not 10073448");
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

    FixedFutureSolver(const Edge& edge,
                      const std::array<const CandidateWord*, 3>& words)
        : initial_debts_(edge.parent_debts), columns_(edge.columns) {
        std::uint32_t multiplier = 1;
        for (std::size_t column = 0; column < 3; ++column) {
            build_events(column, words[column]->word);
            multipliers_[column] = multiplier;
            multiplier *= static_cast<std::uint32_t>(events_[column].size() + 1);
        }
        memo_.assign(multiplier, -1);
    }

    Result solve() {
        Result result;
        result.solvable = visit(0);
        for (std::size_t column = 0; column < 3; ++column) {
            if (safe_from(0, column)) result.safe_mask |= 1U << column;
        }
        if (result.solvable) {
            std::uint32_t state = 0;
            while (!goal(state)) {
                bool advanced = false;
                for (std::size_t column = 0; column < 3; ++column) {
                    if (!safe_from(state, column)) continue;
                    result.path.push_back(static_cast<char>('0' + column));
                    state += multipliers_[column];
                    advanced = true;
                    break;
                }
                if (!advanced) throw std::runtime_error("winning state has no safe source");
            }
        }
        result.states = states_;
        result.transitions = transitions_;
        return result;
    }

private:
    struct Event {
        int old_color = 0;
        int old_cap = 0;
        int next_color = 0;
        int next_cap = 0;
    };

    Debts initial_debts_{};
    std::array<Source, 3> columns_{};
    std::array<std::vector<Event>, 3> events_;
    std::array<std::vector<Debts>, 3> deltas_;
    std::array<std::uint32_t, 3> multipliers_{};
    std::vector<std::int8_t> memo_;
    std::uint64_t states_ = 0;
    std::uint64_t transitions_ = 0;

    void build_events(std::size_t column, const std::vector<Color>& word) {
        int old_color = columns_[column].color;
        int old_cap = columns_[column].cap;
        int cursor = static_cast<int>(word.size()) - 1;
        while (cursor >= 0) {
            const int next_color = word[static_cast<std::size_t>(cursor)];
            require(next_color != old_color, "future run repeats current top");
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
                "fixed future does not end in exhaustion");
        deltas_[column].assign(events_[column].size() + 1, Debts{});
        for (std::size_t index = 0; index < events_[column].size(); ++index) {
            deltas_[column][index + 1] = deltas_[column][index];
            const auto& event = events_[column][index];
            deltas_[column][index + 1][event.old_color] += event.old_cap;
            if (event.next_cap == kHeight) {
                deltas_[column][index + 1][event.next_color] +=
                    kHeight - event.old_cap;
            } else {
                deltas_[column][index + 1][event.next_color] -= event.old_cap;
            }
        }
    }

    std::array<std::size_t, 3> decode(std::uint32_t state) const {
        std::array<std::size_t, 3> ranks{};
        for (std::size_t column = 0; column < 3; ++column) {
            ranks[column] = (state / multipliers_[column]) %
                            (events_[column].size() + 1);
        }
        return ranks;
    }

    bool goal(std::uint32_t state) const {
        const auto ranks = decode(state);
        for (std::size_t column = 0; column < ranks.size(); ++column) {
            if (ranks[column] == events_[column].size()) return true;
        }
        return false;
    }

    bool legal(std::uint32_t state, std::size_t column) const {
        const auto ranks = decode(state);
        int exhausted = 0;
        Debts debts = initial_debts_;
        for (std::size_t other = 0; other < 3; ++other) {
            if (ranks[other] == events_[other].size()) ++exhausted;
            for (int color = 0; color < kColors; ++color) {
                debts[color] += deltas_[other][ranks[other]][color];
            }
        }
        if (ranks[column] == events_[column].size()) return false;
        const auto& event = events_[column][ranks[column]];
        debts[event.old_color] += event.old_cap;
        return positive_count(debts) <= kEmpty + 1 + exhausted;
    }

    bool safe_from(std::uint32_t state, std::size_t column) {
        if (goal(state) || !legal(state, column)) return false;
        ++transitions_;
        return visit(state + multipliers_[column]);
    }

    bool visit(std::uint32_t state) {
        if (goal(state)) return true;
        auto& memo = memo_[state];
        if (memo >= 0) return memo != 0;
        ++states_;
        for (std::size_t column = 0; column < 3; ++column) {
            if (safe_from(state, column)) {
                memo = 1;
                return true;
            }
        }
        memo = 0;
        return false;
    }
};

template <class Callback>
bool for_each_completion(const Edge& edge, const Decoration& decoration,
                         WordCache& cache, Callback&& callback) {
    const auto& first = words_for(cache, edge.columns[0].cap, decoration.cards[0]);
    const auto& second = words_for(cache, edge.columns[1].cap, decoration.cards[1]);
    const auto& third = words_for(cache, edge.columns[2].cap, decoration.cards[2]);
    std::unordered_map<std::uint32_t, std::vector<const CandidateWord*>> third_by_counts;
    for (const auto& word : third) third_by_counts[pack_counts(word.counts)].push_back(&word);
    for (const auto& left : first) {
        for (const auto& middle : second) {
            bool valid = false;
            const auto needed = subtract_counts(edge.remaining, left.counts,
                                                middle.counts, valid);
            if (!valid) continue;
            const auto found = third_by_counts.find(pack_counts(needed));
            if (found == third_by_counts.end()) continue;
            for (const auto* right : found->second) {
                const std::array<const CandidateWord*, 3> words{&left, &middle, right};
                if (!callback(words)) return false;
            }
        }
    }
    return true;
}

RunStats run(const Options& options, const std::vector<Edge>& edges,
             const std::vector<Decoration>& decorations, WordCache& cache,
             RunStats stats) {
    stats.edges.resize(edges.size());
    for (const auto& decoration : decorations) {
        auto& edge_stats = stats.edges[decoration.edge];
        ++edge_stats.feasible_decorations;
        edge_stats.residual_words_expected += decoration.completions;
    }

    const auto effective_limit = options.limit == 0
                                     ? stats.residual_words_expected
                                     : std::min(options.limit, stats.residual_words_expected);
    const auto started = std::chrono::steady_clock::now();
    bool stop = false;
    for (const auto& decoration : decorations) {
        const auto& edge = edges[decoration.edge];
        auto& edge_stats = stats.edges[decoration.edge];
        const bool complete = for_each_completion(
            edge, decoration, cache,
            [&](const std::array<const CandidateWord*, 3>& words) {
                if (stats.residual_words_checked >= effective_limit) return false;
                FixedFutureSolver solver(edge, words);
                const auto result = solver.solve();
                ++stats.residual_words_checked;
                ++edge_stats.residual_words_checked;
                stats.states_evaluated += result.states;
                stats.transitions_tested += result.transitions;
                edge_stats.states_evaluated += result.states;
                edge_stats.transitions_tested += result.transitions;
                if (result.solvable) {
                    ++stats.checkpoint_yes;
                    ++edge_stats.checkpoint_yes;
                } else {
                    ++stats.local_no;
                    ++edge_stats.local_no;
                }
                for (std::size_t column = 0; column < 3; ++column) {
                    if ((result.safe_mask & (1U << column)) != 0) {
                        ++edge_stats.safe_source_counts[column];
                        ++stats.safe_source_counts[column];
                    }
                }
                if ((result.safe_mask & 0x6U) == 0x6U) {
                    ++edge_stats.both_siblings_safe;
                    ++stats.both_siblings_safe;
                }
                Sample sample;
                sample.present = true;
                sample.solvable = result.solvable;
                sample.safe_mask = result.safe_mask;
                sample.removal_columns = result.path;
                for (std::size_t column = 0; column < 3; ++column) {
                    sample.words[column] = word_string(words[column]->word);
                }
                if (!edge_stats.sample.present) edge_stats.sample = sample;
                if (!result.solvable && !stats.first_local_no) {
                    stats.first_local_no = std::make_pair(decoration.edge, sample);
                }
                return true;
            });
        if (!complete && stats.residual_words_checked >= effective_limit) {
            stop = true;
            break;
        }
    }
    static_cast<void>(stop);
    stats.elapsed_seconds = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - started).count();
    stats.residual_word_universe_complete =
        stats.residual_words_checked == stats.residual_words_expected;
    stats.self_checks_passed = true;
    require(stats.checkpoint_yes + stats.local_no == stats.residual_words_checked,
            "checkpoint classification does not sum to checked words");
    require(stats.safe_source_counts[0] == 0,
            "a terminal-entering bad source was unexpectedly safe");
    require(stats.safe_source_counts[1] == stats.residual_words_checked &&
                stats.safe_source_counts[2] == stats.residual_words_checked &&
                stats.both_siblings_safe == stats.residual_words_checked,
            "both q siblings are not safe in every checked fixed future");
    return stats;
}

std::string status(const RunStats& stats) {
    if (!stats.residual_word_universe_complete) return "INCOMPLETE";
    if (stats.local_no != 0) return "RESIDUALS_EXPORTED";
    return "ENTRY_FAMILY_ELIMINATED";
}

std::string json_state(const State& state) {
    std::ostringstream output;
    output << '[';
    for (std::size_t color = 0; color < state.size(); ++color) {
        if (color != 0) output << ',';
        output << "{\"debt\":" << state[color].debt << ",\"caps\":[";
        for (std::size_t i = 0; i < state[color].caps.size(); ++i) {
            if (i != 0) output << ',';
            output << state[color].caps[i];
        }
        output << "]}";
    }
    output << ']';
    return output.str();
}

void write_sample(std::ostream& output, const Sample& sample) {
    if (!sample.present) {
        output << "null";
        return;
    }
    output << "{\"solvable\":" << (sample.solvable ? "true" : "false")
           << ",\"hidden_words_bottom_to_top\":[";
    for (std::size_t i = 0; i < sample.words.size(); ++i) {
        if (i != 0) output << ',';
        output << '"' << sample.words[i] << '"';
    }
    output << "],\"safe_source_mask\":" << sample.safe_mask
           << ",\"escape_columns\":\"" << sample.removal_columns << "\"}";
}

void write_report(const Options& options, const std::vector<Edge>& edges,
                  const RunStats& stats) {
    if (options.output_dir.empty()) return;
    std::filesystem::create_directories(options.output_dir);
    const auto report_path = options.output_dir / "report.json";
    std::ofstream json(report_path);
    if (!json) throw std::runtime_error("cannot write " + report_path.string());
    const bool verified = stats.self_checks_passed &&
                          stats.next_run_census_complete &&
                          stats.residual_word_universe_complete;
    json << "{\n"
         << "  \"schema_version\": 1,\n"
         << "  \"coverage_scope\": \"same_z_tq_sibling_entry_family\",\n"
         << "  \"status\": \"" << status(stats) << "\",\n"
         << "  \"self_checks_passed\": "
         << (stats.self_checks_passed ? "true" : "false") << ",\n"
         << "  \"verified\": " << (verified ? "true" : "false") << ",\n"
         << "  \"universe_complete\": "
         << (stats.residual_word_universe_complete ? "true" : "false") << ",\n"
         << "  \"next_run_census_complete\": "
         << (stats.next_run_census_complete ? "true" : "false") << ",\n"
         << "  \"residual_word_universe_complete\": "
         << (stats.residual_word_universe_complete ? "true" : "false") << ",\n"
         << "  \"full_residual_word_coverage\": "
         << (stats.residual_word_universe_complete ? "true" : "false") << ",\n"
         << "  \"full_layout_coverage\": false,\n"
         << "  \"terminal_count\": 71,\n"
         << "  \"sibling_parent_count\": 23,\n"
         << "  \"bad_edge_count\": 32,\n"
         << "  \"raw_single_next_run_outcomes\": " << stats.raw_single << ",\n"
         << "  \"raw_simultaneous_decorations\": " << stats.raw_simultaneous << ",\n"
         << "  \"feasible_decorations\": " << stats.feasible_decorations << ",\n"
         << "  \"infeasible_decorations\": " << stats.infeasible_decorations << ",\n"
         << "  \"direct_exhaustion_decorations\": "
         << stats.direct_exhaustion_decorations << ",\n"
         << "  \"bad_source_persistent_decorations\": "
         << stats.bad_source_persistent_decorations << ",\n"
         << "  \"obstruction_decorations\": " << stats.obstruction_decorations << ",\n"
         << "  \"residual_words_expected\": " << stats.residual_words_expected << ",\n"
         << "  \"fixed_future_completions\": " << stats.residual_words_expected << ",\n"
         << "  \"residual_words_checked\": " << stats.residual_words_checked << ",\n"
         << "  \"checked_completions\": " << stats.residual_words_checked << ",\n"
         << "  \"checkpoint_yes_count\": " << stats.checkpoint_yes << ",\n"
         << "  \"yes_count\": " << stats.checkpoint_yes << ",\n"
         << "  \"local_no_count\": " << stats.local_no << ",\n"
         << "  \"no_count\": " << stats.local_no << ",\n"
         << "  \"global_no_count\": 0,\n"
         << "  \"safe_source_counts\": [" << stats.safe_source_counts[0] << ','
         << stats.safe_source_counts[1] << ',' << stats.safe_source_counts[2] << "],\n"
         << "  \"both_siblings_safe_count\": " << stats.both_siblings_safe << ",\n"
         << "  \"edge_summed_residual_words\": true,\n"
         << "  \"states_evaluated\": " << stats.states_evaluated << ",\n"
         << "  \"transitions_tested\": " << stats.transitions_tested << ",\n"
         << "  \"elapsed_seconds\": " << stats.elapsed_seconds << ",\n"
         << "  \"per_edge\": [\n";
    for (std::size_t i = 0; i < edges.size(); ++i) {
        if (i != 0) json << ",\n";
        const auto& edge = edges[i];
        const auto& row = stats.edges[i];
        json << "    {\"edge_id\":\"tq-sibling-e" << i << "\","
             << "\"parent\":" << json_state(edge.parent) << ','
             << "\"terminal\":" << json_state(edge.terminal) << ','
             << "\"bad_action\":[" << edge.bad.old_color << ',' << edge.bad.old_cap
             << ',' << edge.bad.new_color << ',' << edge.bad.new_cap << "],"
             << "\"columns\":[[" << edge.columns[0].color << ',' << edge.columns[0].cap
             << "],[" << edge.columns[1].color << ',' << edge.columns[1].cap
             << "],[" << edge.columns[2].color << ',' << edge.columns[2].cap << "]],"
             << "\"raw_single_next_run_outcomes\":" << edge.raw_single << ','
             << "\"raw_simultaneous_decorations\":" << edge.raw_simultaneous << ','
             << "\"feasible_decorations\":" << row.feasible_decorations << ','
             << "\"residual_words_expected\":" << row.residual_words_expected << ','
             << "\"residual_words_checked\":" << row.residual_words_checked << ','
             << "\"checkpoint_yes_count\":" << row.checkpoint_yes << ','
             << "\"local_no_count\":" << row.local_no << ','
             << "\"safe_source_counts\":[" << row.safe_source_counts[0] << ','
             << row.safe_source_counts[1] << ',' << row.safe_source_counts[2] << "],"
             << "\"both_siblings_safe_count\":" << row.both_siblings_safe << ','
             << "\"sample\":";
        write_sample(json, row.sample);
        json << '}';
    }
    json << "\n  ]";
    if (stats.first_local_no) {
        json << ",\n  \"first_local_no\": {\"edge_index\":"
             << stats.first_local_no->first << ",\"residual\":";
        write_sample(json, stats.first_local_no->second);
        json << '}';
    }
    json << "\n}\n";

    std::ofstream markdown(options.output_dir / "report.md");
    if (!markdown) throw std::runtime_error("cannot write report.md");
    markdown << "# c=4, h=7, k=2 same-z Tq sibling-fork census\n\n"
             << "- Scope: checkpoint residual words for the 23 same-z Tq sibling parents.\n"
             << "- Status: **" << status(stats) << "**\n"
             << "- Terminals / sibling parents / bad edges: 71 / 23 / 32.\n"
             << "- Raw single cards / simultaneous decorations: " << stats.raw_single
             << " / " << stats.raw_simultaneous << ".\n"
             << "- Color-feasible decorations: " << stats.feasible_decorations << ".\n"
             << "- Complete residual words checked: " << stats.residual_words_checked
             << " / " << stats.residual_words_expected << ".\n"
             << "- Checkpoint YES / local NO: " << stats.checkpoint_yes << " / "
             << stats.local_no << ".\n"
             << "- Full initial-layout coverage: no (not needed when every checkpoint is YES).\n";
}

} // namespace

int main(int argc, char** argv) {
    try {
        auto options = parse_options(argc, argv);
        const auto edges = enumerate_edges();
        WordCache cache;
        RunStats structural;
        const auto decorations = enumerate_decorations(edges, cache, structural);
        structural.self_checks_passed = true;

        // A bare self-test deliberately checks a small exact prefix.  Supplying
        // --output-dir and --limit exercises the normal report path instead.
        if (options.self_test && options.output_dir.empty() && options.limit == 0) {
            options.limit = 64;
        }
        const auto stats = run(options, edges, decorations, cache, structural);
        write_report(options, edges, stats);
        std::cout << "status=" << status(stats)
                  << " terminals=71 parents=23 edges=32"
                  << " raw_single=" << stats.raw_single
                  << " raw_simultaneous=" << stats.raw_simultaneous
                  << " feasible=" << stats.feasible_decorations
                  << " residual=" << stats.residual_words_checked << '/'
                  << stats.residual_words_expected
                  << " yes=" << stats.checkpoint_yes
                  << " local_no=" << stats.local_no << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
