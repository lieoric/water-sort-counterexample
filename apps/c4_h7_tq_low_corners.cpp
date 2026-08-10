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
#include <set>
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

constexpr std::uint64_t kExpectedTerminalCount = 71;
constexpr std::uint64_t kExpectedLabeledCandidates = 624;
constexpr std::uint64_t kExpectedCanonicalParents = 418;
constexpr std::uint64_t kExpectedCanonicalEdges = 429;
constexpr std::uint64_t kExpectedSiblingParents = 412;
constexpr std::uint64_t kExpectedSiblingEdges = 423;
constexpr std::uint64_t kExpectedCornerDecorations = 10;
constexpr std::uint64_t kExpectedCornerEdges = 9;
constexpr std::uint64_t kExpectedResidualWords = 235620;
constexpr std::uint64_t kExpectedParentCheckpointYes = 235494;
constexpr std::uint64_t kExpectedParentCheckpointLocalNo = 126;

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
using Caps = std::array<std::vector<int>, kColors>;

struct Source {
    int color = 0;
    int cap = 0;
};

struct ExhaustAction {
    int old_color = 0;
    int old_cap = 0;
    int final_color = 0;

    bool operator<(const ExhaustAction& other) const {
        return std::tie(old_color, old_cap, final_color) <
               std::tie(other.old_color, other.old_cap, other.final_color);
    }
};

struct Card {
    int color = 0;
    int endpoint = 0;
};

struct Edge {
    std::size_t ordinal = 0;
    State parent;
    State terminal;
    ExhaustAction bad;
    Debts terminal_debts{}; // Parent color coordinates, not canonicalized.
    int q_color = -1;
    std::array<int, 3> q_caps{};
};

struct CandidateWord {
    // The entire hidden suffix below the exposed top, bottom to top.
    std::vector<int> word;
    // Only the free tail, top to bottom.  This is the documented ordering key.
    std::vector<int> free_top_to_bottom;
    Counts counts{};
};

struct Decoration {
    std::size_t ordinal = 0;
    std::size_t edge_index = 0;
    int target_color = -1;
    std::array<Card, 3> cards{};
    Counts hidden_balance{};
    std::uint64_t residual_words_expected = 0;
};

struct Bridge {
    std::vector<Edge> sibling_edges;
    std::uint64_t terminal_count = 0;
    std::uint64_t labeled_candidates = 0;
    std::uint64_t canonical_parent_count = 0;
    std::uint64_t canonical_edge_count = 0;
    std::uint64_t sibling_parent_count = 0;
};

struct ResidualSample {
    bool present = false;
    bool solvable = false;
    std::size_t decoration = 0;
    std::array<std::string, 4> hidden_words_bottom_to_top;
    std::uint32_t initial_safe_mask = 0;
    std::string escape_columns;
};

struct DecorationStats {
    std::uint64_t expected = 0;
    std::uint64_t checked = 0;
    std::uint64_t parent_checkpoint_yes = 0;
    std::uint64_t parent_checkpoint_local_no = 0;
    std::uint64_t water_initial_checked = 0;
    std::uint64_t water_initial_yes = 0;
    std::uint64_t water_initial_no = 0;
    std::uint64_t states = 0;
    std::uint64_t transitions = 0;
    std::uint64_t water_initial_states = 0;
    std::uint64_t water_initial_transitions = 0;
    ResidualSample first_sample;
};

struct PrefixRow {
    std::size_t decoration = 0;
    std::array<std::string, 3> free_tails_top_to_bottom;
    bool parent_checkpoint_solvable = false;
    std::uint32_t parent_safe_mask = 0;
    std::string parent_escape_columns;
    std::optional<bool> water_initial_solvable;
    std::uint32_t water_initial_safe_mask = 0;
    std::string water_initial_escape_columns;
};

struct RunStats {
    bool self_checks_passed = false;
    bool residual_word_universe_complete = false;
    std::uint64_t limit_requested = 0;
    std::uint64_t residual_words_expected = 0;
    std::uint64_t residual_words_checked = 0;
    std::uint64_t parent_checkpoint_yes = 0;
    std::uint64_t parent_checkpoint_local_no = 0;
    std::uint64_t water_initial_layouts_checked = 0;
    std::uint64_t water_initial_yes = 0;
    std::uint64_t water_initial_no = 0;
    std::uint64_t mapped_parent_local_no = 0;
    std::uint64_t water_initial_witnesses_replayed = 0;
    std::uint64_t states = 0;
    std::uint64_t transitions = 0;
    std::uint64_t water_initial_states = 0;
    std::uint64_t water_initial_transitions = 0;
    std::vector<DecorationStats> per_decoration;
    std::vector<PrefixRow> checked_prefix;
    std::vector<ResidualSample> parent_local_no_residuals;
    std::optional<ResidualSample> first_water_initial_recovery;
    std::optional<ResidualSample> first_water_initial_no;
    double elapsed_seconds = 0.0;
};

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error("self-check failed: " + message);
}

void usage() {
    std::cerr << "Usage: water-c4-h7-tq-low-corners "
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

State canonical_state(const Debts& debts, Caps caps) {
    State result;
    for (int color = 0; color < kColors; ++color) {
        std::sort(caps[color].begin(), caps[color].end());
        result[static_cast<std::size_t>(color)] = {debts[color], caps[color]};
    }
    std::sort(result.begin(), result.end());
    return result;
}

Debts state_debts(const State& state) {
    Debts result{};
    for (int color = 0; color < kColors; ++color) result[color] = state[color].debt;
    return result;
}

Caps state_caps(const State& state) {
    Caps result;
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
    const Counts exposed = exposed_counts(state);
    Counts remaining{};
    for (int color = 0; color < kColors; ++color) {
        if (exposed[color] < multiplicity[color] || exposed[color] > kHeight) return false;
        remaining[color] = kHeight - exposed[color];
    }
    for (int color = 0; color < kColors; ++color) {
        int allowed = 0;
        for (int other = 0; other < kColors; ++other) {
            if (other != color) allowed += remaining[other];
        }
        if (multiplicity[color] > allowed) return false;
    }
    return true;
}

bool source_is_legal(const Debts& debts, int z, int color, int cap) {
    Debts test = debts;
    test[color] += cap;
    return positive_count(test) <= kEmpty + z;
}

std::vector<Source> sources(const State& state) {
    std::vector<Source> result;
    for (int color = 0; color < kColors; ++color) {
        for (const int cap : state[color].caps) result.push_back({color, cap});
    }
    return result;
}

std::vector<Source> legal_sources(const State& state, int z) {
    std::vector<Source> result;
    const Debts debts = state_debts(state);
    for (const Source source : sources(state)) {
        if (source_is_legal(debts, z, source.color, source.cap)) result.push_back(source);
    }
    return result;
}

bool is_tq_terminal(const State& state) {
    if (!algebraically_consistent(state, 1) || !legal_sources(state, 1).empty()) return false;
    int positive = 0;
    int nonpositive = 0;
    int topped_nonpositive = 0;
    int topped_positive = 0;
    for (const Bucket& bucket : state) {
        if (bucket.debt > 0) {
            ++positive;
            topped_positive += !bucket.caps.empty();
        } else {
            ++nonpositive;
            topped_nonpositive += !bucket.caps.empty();
        }
    }
    return positive == 3 && nonpositive == 1 && topped_nonpositive == 1 &&
           topped_positive == 0;
}

std::vector<State> enumerate_tq_terminals() {
    std::set<State> terminals;
    for (int energy = 0; energy <= 2; ++energy) {
        for (int c0 = 1; c0 < kHeight; ++c0) {
            for (int c1 = c0; c1 < kHeight; ++c1) {
                for (int c2 = c1; c2 < kHeight; ++c2) {
                    if (c0 <= energy || c0 + c1 + c2 - energy > kHeight) continue;
                    for (int p0 = 1; p0 <= kHeight; ++p0) {
                        for (int p1 = p0; p1 <= kHeight; ++p1) {
                            for (int p2 = p1; p2 <= kHeight; ++p2) {
                                if (p0 + p1 + p2 - energy != kHeight) continue;
                                Debts debts{{-energy, p0, p1, p2}};
                                Caps caps;
                                caps[0] = {c0, c1, c2};
                                State state = canonical_state(debts, caps);
                                if (is_tq_terminal(state)) terminals.insert(std::move(state));
                            }
                        }
                    }
                }
            }
        }
    }
    return {terminals.begin(), terminals.end()};
}

std::optional<State> apply_exhausting_action(const State& state, int z,
                                             const ExhaustAction& action) {
    if (action.old_color < 0 || action.old_color >= kColors ||
        action.final_color < 0 || action.final_color >= kColors ||
        action.old_color == action.final_color || action.old_cap < 1 ||
        action.old_cap >= kHeight ||
        !source_is_legal(state_debts(state), z, action.old_color, action.old_cap)) {
        return std::nullopt;
    }
    Debts debts = state_debts(state);
    Caps caps = state_caps(state);
    auto& old_caps = caps[action.old_color];
    const auto found = std::find(old_caps.begin(), old_caps.end(), action.old_cap);
    if (found == old_caps.end()) return std::nullopt;
    old_caps.erase(found);
    debts[action.old_color] += action.old_cap;
    debts[action.final_color] += kHeight - action.old_cap;
    State successor = canonical_state(debts, caps);
    if (!algebraically_consistent(successor, z + 1)) return std::nullopt;
    return successor;
}

std::vector<ExhaustAction> exhausting_actions_to(const State& parent,
                                                 const State& terminal) {
    std::set<ExhaustAction> actions;
    for (int old_color = 0; old_color < kColors; ++old_color) {
        const std::set<int> unique_caps(parent[old_color].caps.begin(),
                                        parent[old_color].caps.end());
        for (const int old_cap : unique_caps) {
            for (int final_color = 0; final_color < kColors; ++final_color) {
                const ExhaustAction action{old_color, old_cap, final_color};
                const auto successor = apply_exhausting_action(parent, 0, action);
                if (successor && *successor == terminal) actions.insert(action);
            }
        }
    }
    return {actions.begin(), actions.end()};
}

std::vector<State> reverse_exhausting_candidates(const State& terminal) {
    std::vector<State> candidates;
    for (int old_cap = 1; old_cap < kHeight; ++old_cap) {
        for (int old_color = 0; old_color < kColors; ++old_color) {
            for (int final_color = 0; final_color < kColors; ++final_color) {
                if (old_color == final_color) continue;
                Debts debts = state_debts(terminal);
                Caps caps = state_caps(terminal);
                debts[old_color] -= old_cap;
                debts[final_color] -= kHeight - old_cap;
                caps[old_color].push_back(old_cap);
                Debts source_test = debts;
                source_test[old_color] += old_cap;
                if (positive_count(source_test) > kEmpty) continue;
                State parent = canonical_state(debts, caps);
                if (algebraically_consistent(parent, 0)) candidates.push_back(std::move(parent));
            }
        }
    }
    std::sort(candidates.begin(), candidates.end());
    return candidates;
}

Bridge build_bridge() {
    Bridge bridge;
    const auto terminals = enumerate_tq_terminals();
    bridge.terminal_count = terminals.size();
    std::vector<std::pair<State, State>> labeled;
    std::set<std::pair<State, State>> pairs;
    for (const State& terminal : terminals) {
        for (const State& parent : reverse_exhausting_candidates(terminal)) {
            labeled.emplace_back(parent, terminal);
            pairs.emplace(parent, terminal);
        }
    }
    bridge.labeled_candidates = labeled.size();
    bridge.canonical_edge_count = pairs.size();
    std::set<State> parents;
    std::set<State> sibling_parents;
    for (const auto& pair : pairs) {
        parents.insert(pair.first);
        if (legal_sources(pair.first, 0).size() >= 2) sibling_parents.insert(pair.first);
    }
    bridge.canonical_parent_count = parents.size();
    bridge.sibling_parent_count = sibling_parents.size();

    for (const auto& pair : pairs) {
        const State& parent = pair.first;
        const State& terminal = pair.second;
        if (legal_sources(parent, 0).size() < 2) continue;
        const auto actions = exhausting_actions_to(parent, terminal);
        require(actions.size() == 1, "canonical bridge edge does not have one bad action");
        const ExhaustAction bad = actions.front();

        Debts labeled_terminal = state_debts(parent);
        Caps remaining_caps = state_caps(parent);
        auto& bad_caps = remaining_caps[bad.old_color];
        const auto found = std::find(bad_caps.begin(), bad_caps.end(), bad.old_cap);
        require(found != bad_caps.end(), "bad source is missing from bridge parent");
        bad_caps.erase(found);
        labeled_terminal[bad.old_color] += bad.old_cap;
        labeled_terminal[bad.final_color] += kHeight - bad.old_cap;
        require(canonical_state(labeled_terminal, remaining_caps) == terminal,
                "labeled bad exhaustion does not replay to its terminal");

        int q_color = -1;
        for (int color = 0; color < kColors; ++color) {
            if (remaining_caps[color].size() == 3) {
                require(q_color == -1, "bridge edge has two q colors");
                q_color = color;
            } else {
                require(remaining_caps[color].empty(), "bridge remainder is not all-q");
            }
        }
        require(q_color >= 0, "bridge edge has no q color");
        std::sort(remaining_caps[q_color].begin(), remaining_caps[q_color].end());

        Edge edge;
        edge.ordinal = bridge.sibling_edges.size();
        edge.parent = parent;
        edge.terminal = terminal;
        edge.bad = bad;
        edge.terminal_debts = labeled_terminal;
        edge.q_color = q_color;
        std::copy(remaining_caps[q_color].begin(), remaining_caps[q_color].end(),
                  edge.q_caps.begin());
        bridge.sibling_edges.push_back(std::move(edge));
    }
    return bridge;
}

std::vector<CandidateWord> candidate_words(int old_cap, const Card& card) {
    const int length = kHeight - old_cap;
    const int forced = card.endpoint - old_cap;
    const int free = length - forced;
    require(length > 0 && forced > 0 && free >= 0, "invalid next-run card");

    CandidateWord current;
    current.free_top_to_bottom.assign(static_cast<std::size_t>(free), 0);
    std::vector<CandidateWord> result;
    const auto visit = [&](const auto& self, int position) -> void {
        if (position == free) {
            if (free > 0 && current.free_top_to_bottom.front() == card.color) return;
            current.word.clear();
            current.word.reserve(static_cast<std::size_t>(length));
            for (auto iterator = current.free_top_to_bottom.rbegin();
                 iterator != current.free_top_to_bottom.rend(); ++iterator) {
                current.word.push_back(*iterator);
            }
            current.word.insert(current.word.end(), static_cast<std::size_t>(forced),
                                card.color);
            current.counts.fill(0);
            for (const int color : current.word) ++current.counts[color];
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
    std::uint32_t packed = 0;
    for (int color = 0; color < kColors; ++color) {
        require(counts[color] >= 0 && counts[color] < 16, "count cannot be packed");
        packed |= static_cast<std::uint32_t>(counts[color]) << (4 * color);
    }
    return packed;
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

Counts hidden_balance_after_bad(const Edge& edge) {
    Counts balance{};
    const Counts exposed = exposed_counts(edge.parent);
    for (int color = 0; color < kColors; ++color) balance[color] = kHeight - exposed[color];
    balance[edge.bad.final_color] -= kHeight - edge.bad.old_cap;
    require(std::all_of(balance.begin(), balance.end(), [](int value) { return value >= 0; }),
            "fixed bad tail exceeds the parent color balance");
    return balance;
}

std::uint64_t completion_count(const Counts& balance,
                               const std::array<std::vector<CandidateWord>, 3>& words) {
    std::unordered_map<std::uint32_t, std::uint64_t> third_counts;
    for (const auto& word : words[2]) ++third_counts[pack_counts(word.counts)];
    std::uint64_t total = 0;
    for (const auto& first : words[0]) {
        for (const auto& second : words[1]) {
            bool valid = false;
            const Counts needed = subtract_counts(balance, first.counts, second.counts, valid);
            if (!valid) continue;
            const auto found = third_counts.find(pack_counts(needed));
            if (found != third_counts.end()) total += found->second;
        }
    }
    return total;
}

bool is_exact_corner_target(const Edge& edge, int target_color) {
    if (target_color == edge.q_color || edge.terminal_debts[edge.q_color] != 0 ||
        edge.terminal_debts[target_color] != 1 ||
        !std::all_of(edge.q_caps.begin(), edge.q_caps.end(),
                     [](int cap) { return cap == 1; })) {
        return false;
    }
    // Equation (31): each q_1 -> target_3 handoff must leave the stored bad
    // exhaustion legal at z=0.  Identical q caps make this test slot-independent.
    Debts after_live = state_debts(edge.parent);
    ++after_live[edge.q_color];
    --after_live[target_color];
    return source_is_legal(after_live, 0, edge.bad.old_color, edge.bad.old_cap);
}

std::vector<Decoration> enumerate_corner_decorations(const Bridge& bridge) {
    std::vector<Decoration> result;
    for (const Edge& edge : bridge.sibling_edges) {
        for (int target = 0; target < kColors; ++target) {
            if (!is_exact_corner_target(edge, target)) continue;
            require(source_is_legal(state_debts(edge.parent), 0, edge.q_color, 1),
                    "corner q_1 source is not legal at its parent");
            Decoration decoration;
            decoration.ordinal = result.size();
            decoration.edge_index = edge.ordinal;
            decoration.target_color = target;
            decoration.cards = {{{target, 3}, {target, 3}, {target, 3}}};
            decoration.hidden_balance = hidden_balance_after_bad(edge);
            std::array<std::vector<CandidateWord>, 3> words;
            for (std::size_t slot = 0; slot < words.size(); ++slot) {
                words[slot] = candidate_words(edge.q_caps[slot], decoration.cards[slot]);
            }
            decoration.residual_words_expected = completion_count(decoration.hidden_balance,
                                                                  words);
            if (decoration.residual_words_expected == 0) continue;
            result.push_back(std::move(decoration));
        }
    }
    for (std::size_t index = 0; index < result.size(); ++index) result[index].ordinal = index;
    return result;
}

std::string word_string(const std::vector<int>& word) {
    std::string result;
    result.reserve(word.size());
    for (const int color : word) result.push_back(static_cast<char>('0' + color));
    return result;
}

class FixedFutureSolver {
public:
    struct Result {
        bool solvable = false;
        std::uint32_t initial_safe_mask = 0;
        std::string path;
        std::uint64_t states = 0;
        std::uint64_t transitions = 0;
    };

    FixedFutureSolver(const Edge& edge,
                      const std::array<const CandidateWord*, 3>& q_words)
    {
        std::array<Source, kColors> columns{};
        columns[0] = {edge.bad.old_color, edge.bad.old_cap};
        for (std::size_t slot = 0; slot < 3; ++slot) {
            columns[slot + 1] = {edge.q_color, edge.q_caps[slot]};
        }
        std::array<std::vector<int>, kColors> words;
        std::vector<int> bad_word(static_cast<std::size_t>(kHeight - edge.bad.old_cap),
                                  edge.bad.final_color);
        words[0] = std::move(bad_word);
        for (std::size_t slot = 0; slot < 3; ++slot) {
            words[slot + 1] = q_words[slot]->word;
        }
        initialize(state_debts(edge.parent), columns, words);
    }

    FixedFutureSolver(const Debts& initial_debts,
                      const std::array<Source, kColors>& columns,
                      const std::array<std::vector<int>, kColors>& words) {
        initialize(initial_debts, columns, words);
    }

    bool replay_path(const std::string& path) {
        std::uint32_t state = 0;
        for (const char step : path) {
            const std::size_t column = static_cast<std::size_t>(step - '0');
            if (column >= kColors || !legal(state, column)) return false;
            state += multipliers_[column];
        }
        return goal(state);
    }

private:
    void initialize(const Debts& initial_debts,
                    const std::array<Source, kColors>& columns,
                    const std::array<std::vector<int>, kColors>& words) {
        initial_debts_ = initial_debts;
        columns_ = columns;
        for (std::size_t column = 0; column < kColors; ++column) {
            build_events(column, words[column]);
        }
        std::uint32_t multiplier = 1;
        for (std::size_t column = 0; column < kColors; ++column) {
            multipliers_[column] = multiplier;
            multiplier *= static_cast<std::uint32_t>(events_[column].size() + 1);
        }
        memo_.assign(multiplier, -1);
    }

public:

    Result solve() {
        Result result;
        result.solvable = visit(0);
        for (std::size_t column = 0; column < kColors; ++column) {
            if (safe_from(0, column)) result.initial_safe_mask |= 1U << column;
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
                require(advanced, "winning fixed-future state has no winning move");
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
    std::array<Source, kColors> columns_{};
    std::array<std::vector<Event>, kColors> events_;
    std::array<std::vector<Debts>, kColors> deltas_;
    std::array<std::uint32_t, kColors> multipliers_{};
    std::vector<std::int8_t> memo_;
    std::uint64_t states_ = 0;
    std::uint64_t transitions_ = 0;

    void build_events(std::size_t column, const std::vector<int>& word) {
        int old_color = columns_[column].color;
        int old_cap = columns_[column].cap;
        int cursor = static_cast<int>(word.size()) - 1;
        while (cursor >= 0) {
            const int next_color = word[static_cast<std::size_t>(cursor)];
            require(next_color != old_color, "hidden word repeats its current top color");
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
            const Event& event = events_[column][index];
            deltas_[column][index + 1][event.old_color] += event.old_cap;
            if (event.next_cap == kHeight) {
                deltas_[column][index + 1][event.next_color] += kHeight - event.old_cap;
            } else {
                deltas_[column][index + 1][event.next_color] -= event.old_cap;
            }
        }
    }

    std::array<std::size_t, kColors> decode(std::uint32_t state) const {
        std::array<std::size_t, kColors> ranks{};
        for (std::size_t column = 0; column < kColors; ++column) {
            ranks[column] = (state / multipliers_[column]) % (events_[column].size() + 1);
        }
        return ranks;
    }

    int exhausted_count(const std::array<std::size_t, kColors>& ranks) const {
        int exhausted = 0;
        for (std::size_t column = 0; column < kColors; ++column) {
            exhausted += ranks[column] == events_[column].size();
        }
        return exhausted;
    }

    bool goal(std::uint32_t state) const {
        return exhausted_count(decode(state)) >= kEmpty;
    }

    bool legal(std::uint32_t state, std::size_t column) const {
        const auto ranks = decode(state);
        if (ranks[column] == events_[column].size()) return false;
        const int z = exhausted_count(ranks);
        Debts debts = initial_debts_;
        for (std::size_t other = 0; other < kColors; ++other) {
            for (int color = 0; color < kColors; ++color) {
                debts[color] += deltas_[other][ranks[other]][color];
            }
        }
        const Event& event = events_[column][ranks[column]];
        debts[event.old_color] += event.old_cap;
        return positive_count(debts) <= kEmpty + z;
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

template <class Callback>
bool for_each_completion(const Decoration& decoration,
                         const std::array<std::vector<CandidateWord>, 3>& words,
                         Callback&& callback) {
    std::unordered_map<std::uint32_t, std::vector<const CandidateWord*>> third_by_counts;
    for (const auto& third : words[2]) {
        third_by_counts[pack_counts(third.counts)].push_back(&third);
    }
    for (const auto& first : words[0]) {
        for (const auto& second : words[1]) {
            bool valid = false;
            const Counts needed = subtract_counts(decoration.hidden_balance, first.counts,
                                                  second.counts, valid);
            if (!valid) continue;
            const auto found = third_by_counts.find(pack_counts(needed));
            if (found == third_by_counts.end()) continue;
            for (const CandidateWord* third : found->second) {
                const std::array<const CandidateWord*, 3> selected{{&first, &second, third}};
                if (!callback(selected)) return false;
            }
        }
    }
    return true;
}

ResidualSample make_sample(std::size_t decoration_index, const Edge& edge,
                           const std::array<const CandidateWord*, 3>& q_words,
                           const FixedFutureSolver::Result& result) {
    ResidualSample sample;
    sample.present = true;
    sample.solvable = result.solvable;
    sample.decoration = decoration_index;
    sample.hidden_words_bottom_to_top[0] = std::string(
        static_cast<std::size_t>(kHeight - edge.bad.old_cap),
        static_cast<char>('0' + edge.bad.final_color));
    for (std::size_t slot = 0; slot < 3; ++slot) {
        sample.hidden_words_bottom_to_top[slot + 1] = word_string(q_words[slot]->word);
    }
    sample.initial_safe_mask = result.initial_safe_mask;
    sample.escape_columns = result.path;
    return sample;
}

struct WaterInitialFixture {
    Debts debts{};
    std::array<Source, kColors> columns{};
    std::array<std::vector<int>, kColors> words;
};

std::optional<WaterInitialFixture> reconstruct_water_initial(
    const Edge& edge, const Decoration& decoration,
    const std::array<const CandidateWord*, 3>& q_words) {
    const int a = edge.bad.old_color;
    const int f = edge.bad.final_color;
    const int q = edge.q_color;
    if (edge.bad.old_cap != 3 || decoration.target_color != a ||
        edge.q_caps != std::array<int, 3>{{1, 1, 1}}) {
        return std::nullopt;
    }
    int b = -1;
    const Debts parent_debts = state_debts(edge.parent);
    for (int color = 0; color < kColors; ++color) {
        if (color != a && color != f && color != q && parent_debts[color] == 2) {
            if (b != -1) return std::nullopt;
            b = color;
        }
    }
    if (b < 0 || parent_debts[a] != -2 || parent_debts[f] != 0 ||
        parent_debts[q] != 0) {
        return std::nullopt;
    }

    Counts tail_counts{};
    for (const CandidateWord* word : q_words) {
        if (word->free_top_to_bottom.size() != 4 ||
            word->free_top_to_bottom.front() != f) {
            return std::nullopt;
        }
        for (std::size_t index = 1; index < word->free_top_to_bottom.size(); ++index) {
            const int color = word->free_top_to_bottom[index];
            if (color != q && color != b) return std::nullopt;
            ++tail_counts[color];
        }
    }
    if (tail_counts[q] != 4 || tail_counts[b] != 5) return std::nullopt;

    WaterInitialFixture fixture;
    fixture.columns[0] = {b, 2};
    fixture.words[0].assign(4, f);
    fixture.words[0].push_back(a); // bottom-to-top: ffff,a below the b_2 top.
    for (std::size_t slot = 0; slot < 3; ++slot) {
        fixture.columns[slot + 1] = {q, 1};
        fixture.words[slot + 1] = q_words[slot]->word;
    }

    // Physical balance is checked directly at the actual zero-debt start.
    Counts physical{};
    physical[b] += 2;
    for (std::size_t column = 0; column < kColors; ++column) {
        if (column != 0) ++physical[q];
        for (const int color : fixture.words[column]) ++physical[color];
    }
    require(std::all_of(physical.begin(), physical.end(),
                        [](int count) { return count == kHeight; }),
            "reconstructed water initial layout is not color-balanced");

    // Removing the initial b_2 border exposes a at cumulative depth 3 and
    // reproduces the report's labeled z=0 checkpoint exactly.
    Debts reached{};
    reached[b] += 2;
    reached[a] -= 2;
    require(reached == parent_debts, "water-initial prefix does not reach parent debts");
    Caps reached_caps;
    reached_caps[a].push_back(3);
    reached_caps[q] = {1, 1, 1};
    require(canonical_state(reached, reached_caps) == edge.parent,
            "water-initial prefix does not reach the parent border state");
    require(source_is_legal(fixture.debts, 0, b, 2),
            "water-initial prefix move is not legal");
    return fixture;
}

ResidualSample make_water_initial_sample(
    std::size_t decoration_index, const WaterInitialFixture& fixture,
    const FixedFutureSolver::Result& result) {
    ResidualSample sample;
    sample.present = true;
    sample.solvable = result.solvable;
    sample.decoration = decoration_index;
    for (std::size_t column = 0; column < kColors; ++column) {
        sample.hidden_words_bottom_to_top[column] = word_string(fixture.words[column]);
    }
    sample.initial_safe_mask = result.initial_safe_mask;
    sample.escape_columns = result.path;
    return sample;
}

RunStats run(const Options& options, const Bridge& bridge,
             const std::vector<Decoration>& decorations) {
    RunStats stats;
    stats.limit_requested = options.limit;
    stats.per_decoration.resize(decorations.size());
    for (const Decoration& decoration : decorations) {
        stats.residual_words_expected += decoration.residual_words_expected;
        stats.per_decoration[decoration.ordinal].expected = decoration.residual_words_expected;
    }
    const std::uint64_t effective_limit = options.limit == 0
        ? stats.residual_words_expected
        : std::min(options.limit, stats.residual_words_expected);
    const auto started = std::chrono::steady_clock::now();
    bool stop = false;
    for (const Decoration& decoration : decorations) {
        const Edge& edge = bridge.sibling_edges[decoration.edge_index];
        DecorationStats& row = stats.per_decoration[decoration.ordinal];
        std::array<std::vector<CandidateWord>, 3> words;
        for (std::size_t slot = 0; slot < words.size(); ++slot) {
            words[slot] = candidate_words(edge.q_caps[slot], decoration.cards[slot]);
        }
        const bool completed = for_each_completion(
            decoration, words,
            [&](const std::array<const CandidateWord*, 3>& selected) {
                if (stats.residual_words_checked >= effective_limit) return false;
                FixedFutureSolver solver(edge, selected);
                const auto result = solver.solve();
                ++stats.residual_words_checked;
                ++row.checked;
                stats.states += result.states;
                row.states += result.states;
                stats.transitions += result.transitions;
                row.transitions += result.transitions;
                if (result.solvable) {
                    ++stats.parent_checkpoint_yes;
                    ++row.parent_checkpoint_yes;
                } else {
                    ++stats.parent_checkpoint_local_no;
                    ++row.parent_checkpoint_local_no;
                }
                const ResidualSample sample = make_sample(decoration.ordinal, edge,
                                                          selected, result);
                if (!row.first_sample.present) row.first_sample = sample;
                if (!result.solvable) {
                    stats.parent_local_no_residuals.push_back(sample);
                }
                std::optional<FixedFutureSolver::Result> water_result;
                if (!result.solvable) {
                    const auto fixture = reconstruct_water_initial(edge, decoration, selected);
                    if (fixture) {
                        ++stats.mapped_parent_local_no;
                        ++stats.water_initial_layouts_checked;
                        ++row.water_initial_checked;
                        FixedFutureSolver water_solver(fixture->debts, fixture->columns,
                                                       fixture->words);
                        water_result = water_solver.solve();
                        stats.water_initial_states += water_result->states;
                        row.water_initial_states += water_result->states;
                        stats.water_initial_transitions += water_result->transitions;
                        row.water_initial_transitions += water_result->transitions;
                        if (water_result->solvable) {
                            ++stats.water_initial_yes;
                            ++row.water_initial_yes;
                            require(water_solver.replay_path(water_result->path),
                                    "water-initial winning path did not replay");
                            ++stats.water_initial_witnesses_replayed;
                            if (!stats.first_water_initial_recovery) {
                                stats.first_water_initial_recovery =
                                    make_water_initial_sample(
                                        decoration.ordinal, *fixture, *water_result);
                            }
                        } else {
                            ++stats.water_initial_no;
                            ++row.water_initial_no;
                            if (!stats.first_water_initial_no) {
                                stats.first_water_initial_no = make_water_initial_sample(
                                    decoration.ordinal, *fixture, *water_result);
                            }
                        }
                    }
                }
                if (options.limit != 0) {
                    PrefixRow prefix;
                    prefix.decoration = decoration.ordinal;
                    for (std::size_t slot = 0; slot < 3; ++slot) {
                        prefix.free_tails_top_to_bottom[slot] =
                            word_string(selected[slot]->free_top_to_bottom);
                    }
                    prefix.parent_checkpoint_solvable = result.solvable;
                    prefix.parent_safe_mask = result.initial_safe_mask;
                    prefix.parent_escape_columns = result.path;
                    if (water_result) {
                        prefix.water_initial_solvable = water_result->solvable;
                        prefix.water_initial_safe_mask = water_result->initial_safe_mask;
                        prefix.water_initial_escape_columns = water_result->path;
                    }
                    stats.checked_prefix.push_back(std::move(prefix));
                }
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
    stats.residual_word_universe_complete =
        stats.residual_words_checked == stats.residual_words_expected;
    stats.self_checks_passed = true;
    require(stats.residual_words_expected == kExpectedResidualWords,
            "corner residual-word universe is not 235620");
    require(stats.parent_checkpoint_yes + stats.parent_checkpoint_local_no ==
                stats.residual_words_checked,
            "parent-checkpoint classification does not partition checked words");
    require(stats.water_initial_yes + stats.water_initial_no ==
                stats.water_initial_layouts_checked,
            "water-initial classification does not partition fallback layouts");
    require(stats.water_initial_witnesses_replayed == stats.water_initial_yes,
            "a water-initial winning witness did not replay");
    if (stats.residual_word_universe_complete) {
        require(stats.parent_checkpoint_yes == kExpectedParentCheckpointYes,
                "full parent-checkpoint YES count is not 235494");
        require(stats.parent_checkpoint_local_no == kExpectedParentCheckpointLocalNo,
                "full parent-checkpoint local-NO count is not 126");
        require(stats.mapped_parent_local_no == kExpectedParentCheckpointLocalNo &&
                    stats.water_initial_layouts_checked ==
                        kExpectedParentCheckpointLocalNo &&
                    stats.water_initial_yes == kExpectedParentCheckpointLocalNo &&
                    stats.water_initial_no == 0 &&
                    stats.water_initial_witnesses_replayed ==
                        kExpectedParentCheckpointLocalNo,
                "the 126-word water-initial fallback did not close exactly");
        for (std::size_t index = 0; index < stats.per_decoration.size(); ++index) {
            const std::uint64_t expected = index == 3 ? 126 : 0;
            require(stats.per_decoration[index].parent_checkpoint_local_no == expected,
                    "parent local-NO distribution is not confined to decoration 3");
        }
    }
    return stats;
}

std::string status(const RunStats& stats) {
    if (!stats.residual_word_universe_complete) return "INCOMPLETE";
    const bool fallback_closed =
        stats.mapped_parent_local_no == stats.parent_checkpoint_local_no &&
        stats.water_initial_layouts_checked == stats.parent_checkpoint_local_no &&
        stats.water_initial_yes == stats.parent_checkpoint_local_no &&
        stats.water_initial_no == 0 &&
        stats.water_initial_witnesses_replayed == stats.parent_checkpoint_local_no;
    if (!fallback_closed) {
        return "LOCAL_NO_RESIDUALS_EXPORTED";
    }
    return "CORNER_FAMILY_ELIMINATED";
}

std::string json_state(const State& state) {
    std::ostringstream output;
    output << '[';
    for (std::size_t color = 0; color < state.size(); ++color) {
        if (color != 0) output << ',';
        output << "{\"debt\":" << state[color].debt << ",\"caps\":[";
        for (std::size_t index = 0; index < state[color].caps.size(); ++index) {
            if (index != 0) output << ',';
            output << state[color].caps[index];
        }
        output << "]}";
    }
    output << ']';
    return output.str();
}

void write_sample(std::ostream& output, const ResidualSample& sample) {
    if (!sample.present) {
        output << "null";
        return;
    }
    output << "{\"decoration_index\":" << sample.decoration
           << ",\"solvable\":" << (sample.solvable ? "true" : "false")
           << ",\"hidden_words_bottom_to_top\":[";
    for (std::size_t column = 0; column < sample.hidden_words_bottom_to_top.size(); ++column) {
        if (column != 0) output << ',';
        output << '"' << sample.hidden_words_bottom_to_top[column] << '"';
    }
    output << "],\"safe_mask\":" << sample.initial_safe_mask
           << ",\"escape_columns\":\"" << sample.escape_columns << "\"}";
}

std::string decoration_id(const Decoration& decoration, const Edge& edge) {
    std::ostringstream output;
    output << "corner-e" << edge.ordinal << "-x" << decoration.target_color;
    return output.str();
}

void write_report(const Options& options, const Bridge& bridge,
                  const std::vector<Decoration>& decorations,
                  const RunStats& stats) {
    if (options.output_dir.empty()) return;
    std::filesystem::create_directories(options.output_dir);
    std::ofstream json(options.output_dir / "report.json");
    if (!json) throw std::runtime_error("cannot write report.json");
    const bool complete = stats.residual_word_universe_complete;
    const std::uint64_t unresolved_parent_local_no =
        stats.parent_checkpoint_local_no - stats.mapped_parent_local_no;
    const std::uint64_t final_local_no =
        unresolved_parent_local_no + stats.water_initial_no;
    const bool eliminated = complete &&
        stats.mapped_parent_local_no == stats.parent_checkpoint_local_no &&
        stats.water_initial_layouts_checked == stats.parent_checkpoint_local_no &&
        stats.water_initial_yes == stats.parent_checkpoint_local_no &&
        stats.water_initial_no == 0 &&
        stats.water_initial_witnesses_replayed == stats.parent_checkpoint_local_no;
    json << "{\n"
         << "  \"schema_version\": 1,\n"
         << "  \"model\": {\"colors\":4,\"height\":7,\"empty_stacks\":2},\n"
         << "  \"coverage_scope\": \"c4_h7_first_exhaustion_tq_low_energy_corners\",\n"
         << "  \"status\": \"" << status(stats) << "\",\n"
         << "  \"verified\": " << (complete && stats.self_checks_passed ? "true" : "false") << ",\n"
         << "  \"self_checks_passed\": " << (stats.self_checks_passed ? "true" : "false") << ",\n"
         << "  \"limit_requested\": " << stats.limit_requested << ",\n"
         << "  \"limit_unit\": \"residual_words\",\n"
         << "  \"ordering\": \"semantic (parent,terminal,bad_action,target_color), then three free tails top-to-bottom flattened lexicographically\",\n"
         << "  \"bridge\": {\"terminal_count\":" << bridge.terminal_count
         << ",\"labeled_reverse_candidates\":" << bridge.labeled_candidates
         << ",\"canonical_parent_count\":" << bridge.canonical_parent_count
         << ",\"canonical_edge_count\":" << bridge.canonical_edge_count
         << ",\"sibling_parent_count\":" << bridge.sibling_parent_count
         << ",\"sibling_edge_count\":" << bridge.sibling_edges.size() << "},\n"
         << "  \"corner_decorations_expected\": " << decorations.size() << ",\n"
         << "  \"corner_edges_expected\": " << kExpectedCornerEdges << ",\n"
         << "  \"corner_edge_count\": " << kExpectedCornerEdges << ",\n"
         << "  \"residual_words_expected\": " << stats.residual_words_expected << ",\n"
         << "  \"residual_words_checked\": " << stats.residual_words_checked << ",\n"
         << "  \"parent_checkpoint_yes_count\": " << stats.parent_checkpoint_yes << ",\n"
         << "  \"parent_checkpoint_local_no_count\": "
         << stats.parent_checkpoint_local_no << ",\n"
         << "  \"parent_local_no_mapped_to_water_initial\": "
         << stats.mapped_parent_local_no << ",\n"
         << "  \"unresolved_parent_local_no_count\": "
         << unresolved_parent_local_no << ",\n"
         << "  \"water_initial_layouts_checked\": "
         << stats.water_initial_layouts_checked << ",\n"
         << "  \"water_initial_yes_count\": " << stats.water_initial_yes << ",\n"
         << "  \"water_initial_no_count\": " << stats.water_initial_no << ",\n"
         << "  \"water_initial_witnesses_replayed\": "
         << stats.water_initial_witnesses_replayed << ",\n"
         << "  \"local_no_count\": " << final_local_no << ",\n"
         << "  \"global_no_count\": 0,\n"
         << "  \"universe_complete\": " << (complete ? "true" : "false") << ",\n"
         << "  \"residual_word_universe_complete\": " << (complete ? "true" : "false") << ",\n"
         << "  \"full_residual_word_coverage\": " << (complete ? "true" : "false") << ",\n"
         << "  \"corner_family_eliminated\": " << (eliminated ? "true" : "false") << ",\n"
         << "  \"entry_family_eliminated\": false,\n"
         << "  \"full_layout_coverage\": false,\n"
         << "  \"states_evaluated\": " << stats.states << ",\n"
         << "  \"transitions_tested\": " << stats.transitions << ",\n"
         << "  \"water_initial_states_evaluated\": "
         << stats.water_initial_states << ",\n"
         << "  \"water_initial_transitions_tested\": "
         << stats.water_initial_transitions << ",\n"
         << "  \"per_decoration\": [\n";
    for (std::size_t index = 0; index < decorations.size(); ++index) {
        if (index != 0) json << ",\n";
        const Decoration& decoration = decorations[index];
        const Edge& edge = bridge.sibling_edges[decoration.edge_index];
        const DecorationStats& row = stats.per_decoration[index];
        json << "    {\"decoration_id\":\"" << decoration_id(decoration, edge) << "\",";
        json << "\"decoration_index\":" << decoration.ordinal
             << ",\"edge_index\":" << edge.ordinal
             << ",\"parent\":" << json_state(edge.parent)
             << ",\"terminal\":" << json_state(edge.terminal)
             << ",\"bad_action\":[" << edge.bad.old_color << ',' << edge.bad.old_cap
             << ',' << edge.bad.final_color << ']'
             << ",\"q_color\":" << edge.q_color << ",\"q_caps\":["
             << edge.q_caps[0] << ',' << edge.q_caps[1] << ',' << edge.q_caps[2] << ']'
             << ",\"target_color\":" << decoration.target_color
             << ",\"cards\":[[" << decoration.target_color << ",3],["
             << decoration.target_color << ",3],[" << decoration.target_color << ",3]]"
             << ",\"residual_words_expected\":" << row.expected
             << ",\"residual_words_checked\":" << row.checked
             << ",\"parent_checkpoint_yes_count\":" << row.parent_checkpoint_yes
             << ",\"parent_checkpoint_local_no_count\":"
             << row.parent_checkpoint_local_no
             << ",\"water_initial_layouts_checked\":" << row.water_initial_checked
             << ",\"water_initial_yes_count\":" << row.water_initial_yes
             << ",\"water_initial_no_count\":" << row.water_initial_no
             << ",\"states_evaluated\":" << row.states
             << ",\"transitions_tested\":" << row.transitions
             << ",\"water_initial_states_evaluated\":" << row.water_initial_states
             << ",\"water_initial_transitions_tested\":"
             << row.water_initial_transitions
             << ",\"first_sample\":";
        write_sample(json, row.first_sample);
        json << '}';
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
             << (row.parent_checkpoint_solvable ? "true" : "false")
             << ",\"parent_safe_mask\":" << row.parent_safe_mask
             << ",\"parent_escape_columns\":\"" << row.parent_escape_columns << "\""
             << ",\"water_initial_solvable\":";
        if (row.water_initial_solvable) {
            json << (*row.water_initial_solvable ? "true" : "false");
        } else {
            json << "null";
        }
        json << ",\"water_initial_safe_mask\":" << row.water_initial_safe_mask
             << ",\"water_initial_escape_columns\":\""
             << row.water_initial_escape_columns << "\"}";
    }
    json << ']';
    if (!stats.parent_local_no_residuals.empty()) {
        json << ",\n  \"first_parent_checkpoint_local_no\": ";
        write_sample(json, stats.parent_local_no_residuals.front());
    }
    if (stats.first_water_initial_recovery) {
        json << ",\n  \"first_water_initial_recovery\": ";
        write_sample(json, *stats.first_water_initial_recovery);
    }
    if (stats.first_water_initial_no) {
        json << ",\n  \"first_water_initial_no\": ";
        write_sample(json, *stats.first_water_initial_no);
    }
    json << ",\n  \"elapsed_seconds\": " << stats.elapsed_seconds << "\n}\n";

    std::ofstream markdown(options.output_dir / "report.md");
    if (!markdown) throw std::runtime_error("cannot write report.md");
    markdown << "# c=4, h=7 first-exhaustion Tq low-corner census\n\n"
             << "- Status: **" << status(stats) << "**\n"
             << "- Scope: the 10 low-energy Tq-corner next-run decorations only.\n"
             << "- Exact residual words checked: " << stats.residual_words_checked
             << " / " << stats.residual_words_expected << ".\n"
             << "- Original z=0 parent checkpoint YES / local NO: "
             << stats.parent_checkpoint_yes << " / "
             << stats.parent_checkpoint_local_no << ".\n"
             << "- Reconstructed zero-debt water initials checked / YES / NO: "
             << stats.water_initial_layouts_checked << " / "
             << stats.water_initial_yes << " / " << stats.water_initial_no << ".\n"
             << "- Full h=7 layout coverage: no.\n";

    if (!stats.parent_local_no_residuals.empty()) {
        std::ofstream residuals(
            options.output_dir / "parent-checkpoint-local-no-residuals.jsonl");
        if (!residuals) {
            throw std::runtime_error(
                "cannot write parent-checkpoint-local-no-residuals.jsonl");
        }
        for (const ResidualSample& sample : stats.parent_local_no_residuals) {
            residuals << "{\"scope\":\"parent_checkpoint_local_residual\",\"residual\":";
            write_sample(residuals, sample);
            residuals << "}\n";
        }
    }
}

void structural_self_checks(const Bridge& bridge,
                            const std::vector<Decoration>& decorations) {
    require(bridge.terminal_count == kExpectedTerminalCount, "Tq terminal count drifted");
    require(bridge.labeled_candidates == kExpectedLabeledCandidates,
            "labeled reverse-candidate count drifted");
    require(bridge.canonical_parent_count == kExpectedCanonicalParents,
            "canonical bridge-parent count drifted");
    require(bridge.canonical_edge_count == kExpectedCanonicalEdges,
            "canonical bridge-edge count drifted");
    require(bridge.sibling_parent_count == kExpectedSiblingParents,
            "sibling-parent count drifted");
    require(bridge.sibling_edges.size() == kExpectedSiblingEdges,
            "sibling-edge count drifted");
    require(decorations.size() == kExpectedCornerDecorations,
            "low-energy corner-decoration count is not 10");
    std::set<std::size_t> edge_indices;
    std::vector<std::size_t> actual_indices;
    std::vector<std::uint64_t> actual_weights;
    for (const Decoration& decoration : decorations) {
        const Edge& edge = bridge.sibling_edges[decoration.edge_index];
        edge_indices.insert(edge.ordinal);
        actual_indices.push_back(edge.ordinal);
        actual_weights.push_back(decoration.residual_words_expected);
        require(edge.terminal_debts[edge.q_color] == 0,
                "corner terminal does not have E=0");
        require(edge.terminal_debts[decoration.target_color] == 1,
                "corner target does not have terminal debt one");
        require(edge.q_caps == std::array<int, 3>{{1, 1, 1}},
                "corner does not have q caps (1,1,1)");
        require(std::all_of(decoration.cards.begin(), decoration.cards.end(),
                            [&](const Card& card) {
                                return card.color == decoration.target_color &&
                                       card.endpoint == 3;
                            }),
                "corner cards are not three copies of q_1 -> x_3");
    }
    require(edge_indices.size() == kExpectedCornerEdges, "corner edge count is not 9");
    require(actual_indices == std::vector<std::size_t>{
                99, 145, 192, 254, 328, 328, 379, 390, 401, 412},
            "corner semantic edge ordering drifted");
    require(actual_weights == std::vector<std::uint64_t>{
                13860, 27720, 34650, 27720, 13860,
                13860, 27720, 34650, 27720, 13860},
            "corner per-decoration residual weights drifted");
    std::uint64_t total = 0;
    for (const Decoration& decoration : decorations) {
        total += decoration.residual_words_expected;
    }
    require(total == kExpectedResidualWords, "corner residual-word total is not 235620");

    // One member of the predicted 126-word hard core exercises both solver
    // origins without scanning the production universe.  It is losing at the
    // abstract report parent P, but winning in the reconstructed zero-debt
    // physical layout.  This guards the crucial distinction between those two
    // meanings of "initial".
    const auto hard_decoration = std::find_if(
        decorations.begin(), decorations.end(), [&](const Decoration& decoration) {
            const Edge& edge = bridge.sibling_edges[decoration.edge_index];
            return edge.ordinal == 254 && decoration.target_color == edge.bad.old_color;
        });
    require(hard_decoration != decorations.end(), "known low-corner regression is absent");
    const Edge& hard_edge = bridge.sibling_edges[hard_decoration->edge_index];
    int hard_b = -1;
    const Debts hard_debts = state_debts(hard_edge.parent);
    for (int color = 0; color < kColors; ++color) {
        if (color != hard_edge.bad.old_color && color != hard_edge.bad.final_color &&
            color != hard_edge.q_color && hard_debts[color] == 2) {
            hard_b = color;
        }
    }
    require(hard_b >= 0, "known hard core has no b color");
    const std::array<std::vector<int>, 3> wanted{{
        {hard_edge.bad.final_color, hard_edge.q_color, hard_edge.q_color,
         hard_edge.q_color},
        {hard_edge.bad.final_color, hard_edge.q_color, hard_b, hard_b},
        {hard_edge.bad.final_color, hard_b, hard_b, hard_b}}};
    std::array<std::vector<CandidateWord>, 3> word_sets;
    std::array<const CandidateWord*, 3> selected{};
    for (std::size_t slot = 0; slot < 3; ++slot) {
        word_sets[slot] = candidate_words(1, hard_decoration->cards[slot]);
        const auto found = std::find_if(
            word_sets[slot].begin(), word_sets[slot].end(),
            [&](const CandidateWord& word) {
                return word.free_top_to_bottom == wanted[slot];
            });
        require(found != word_sets[slot].end(), "known hard-core word is absent");
        selected[slot] = &*found;
    }
    Counts used{};
    for (const CandidateWord* word : selected) {
        for (int color = 0; color < kColors; ++color) used[color] += word->counts[color];
    }
    require(used == hard_decoration->hidden_balance,
            "known hard-core words do not meet the parent balance");
    FixedFutureSolver parent_solver(hard_edge, selected);
    const auto parent_result = parent_solver.solve();
    require(!parent_result.solvable, "known hard core is not parent-checkpoint local NO");
    const auto fixture = reconstruct_water_initial(hard_edge, *hard_decoration, selected);
    require(fixture.has_value(), "known hard core did not reconstruct to water initial");
    FixedFutureSolver water_solver(fixture->debts, fixture->columns, fixture->words);
    const auto water_result = water_solver.solve();
    require(water_result.solvable, "known hard core is not water-initial YES");
    require(water_solver.replay_path(water_result.path),
            "known water-initial escape did not replay");
}

} // namespace

int main(int argc, char** argv) {
    try {
        Options options = parse_options(argc, argv);
        const Bridge bridge = build_bridge();
        const auto decorations = enumerate_corner_decorations(bridge);
        structural_self_checks(bridge, decorations);
        if (options.self_test && options.output_dir.empty() && options.limit == 0) {
            options.limit = 64;
        }
        const RunStats stats = run(options, bridge, decorations);
        write_report(options, bridge, decorations, stats);
        std::cout << "status=" << status(stats)
                  << " decorations=" << decorations.size()
                  << " residual=" << stats.residual_words_checked << '/'
                  << stats.residual_words_expected
                  << " parent_yes=" << stats.parent_checkpoint_yes
                  << " parent_local_no=" << stats.parent_checkpoint_local_no
                  << " water_initial_yes=" << stats.water_initial_yes
                  << " water_initial_no=" << stats.water_initial_no << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
