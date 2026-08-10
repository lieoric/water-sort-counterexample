#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <numeric>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

namespace {

constexpr int kHeight = 7;
constexpr int kColors = 4;
constexpr int kEmpty = 2;
constexpr std::uint64_t kExpectedTqTerminals = 71;
constexpr std::uint64_t kExpectedLabeledCandidates = 624;
constexpr std::uint64_t kExpectedCanonicalParents = 418;
constexpr std::uint64_t kExpectedCanonicalEdges = 429;
constexpr std::uint64_t kExpectedSiblingEdges = 423;
constexpr std::uint64_t kExpectedSelectedEdges = 12;
constexpr std::uint64_t kExpectedDecorations = 1535;
constexpr std::uint64_t kExpectedResidualWords = 1106490;

using Debts = std::array<int, kColors>;
using Counts = std::array<int, kColors>;
using Caps = std::array<std::vector<int>, kColors>;

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
    Debts terminal_debts{};
    int q_color = -1;
    std::array<int, 3> q_caps{};
    int legal_source_count = 0;
};

struct Bridge {
    std::vector<Edge> edges;
    std::uint64_t terminal_count = 0;
    std::uint64_t labeled_candidates = 0;
    std::uint64_t canonical_parent_count = 0;
    std::uint64_t canonical_edge_count = 0;
    std::uint64_t sibling_edge_count = 0;
};

struct Decoration {
    std::size_t ordinal = 0;
    std::size_t edge_index = 0;
    std::array<Card, 3> cards{};
    Counts residual_after_forced{};
    std::array<int, 3> free_tail_lengths{};
    std::uint64_t residual_words_expected = 0;
};

struct FixedFixture {
    Debts debts{};
    std::array<Source, kColors> sources{};
    std::array<std::vector<int>, kColors> hidden_bottom_to_top;
};

struct EdgeStats {
    std::size_t edge_ordinal = 0;
    std::uint64_t decorations = 0;
    std::uint64_t residual_words_expected = 0;
    std::uint64_t residual_words_checked = 0;
    std::uint64_t local_yes = 0;
    std::uint64_t local_no = 0;
    std::uint64_t states = 0;
    std::uint64_t transitions = 0;
    std::map<std::uint32_t, std::uint64_t> safe_mask_distribution;
};

struct Sample {
    bool present = false;
    std::uint64_t future_index = 0;
    std::size_t decoration_index = 0;
    std::size_t edge_ordinal = 0;
    bool solvable = false;
    std::uint32_t safe_mask = 0;
    std::string path;
    std::array<std::string, kColors> hidden_words_bottom_to_top;
};

struct RunStats {
    bool self_checks_passed = false;
    bool universe_complete = false;
    std::uint64_t limit_requested = 0;
    std::uint64_t decorations_expected = 0;
    std::uint64_t residual_words_expected = 0;
    std::uint64_t residual_words_checked = 0;
    std::uint64_t local_yes = 0;
    std::uint64_t local_no = 0;
    std::uint64_t winning_paths_replayed = 0;
    std::uint64_t states = 0;
    std::uint64_t transitions = 0;
    std::uint64_t ledger_hash = 1469598103934665603ULL;
    std::vector<EdgeStats> per_edge;
    std::optional<Sample> first_yes;
    std::optional<Sample> first_no;
    double elapsed_seconds = 0.0;
};

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error("self-check failed: " + message);
}

void usage() {
    std::cerr << "Usage: water-c4-h7-d2-three-source --output-dir DIR "
                 "[--limit N] [--self-test]\n";
}

Options parse_options(int argc, char** argv) {
    Options options;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--output-dir" && index + 1 < argc) {
            options.output_dir = argv[++index];
        } else if (argument == "--limit" && index + 1 < argc) {
            options.limit = std::stoull(argv[++index]);
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

bool algebraically_consistent(const State& state, int exhausted) {
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
    if (cap_count != kColors - exhausted || debt_sum != exhausted * kHeight) {
        return false;
    }
    const Counts exposed = exposed_counts(state);
    Counts remaining{};
    for (int color = 0; color < kColors; ++color) {
        if (exposed[color] < multiplicity[color] || exposed[color] > kHeight) {
            return false;
        }
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

bool source_is_legal(const Debts& debts, int exhausted, int color, int cap) {
    Debts tested = debts;
    tested[color] += cap;
    return positive_count(tested) <= kEmpty + exhausted;
}

bool source_is_legal(const State& state, int exhausted, int color, int cap) {
    return source_is_legal(state_debts(state), exhausted, color, cap);
}

std::vector<Source> sources(const State& state) {
    std::vector<Source> result;
    for (int color = 0; color < kColors; ++color) {
        for (const int cap : state[color].caps) result.push_back({color, cap});
    }
    return result;
}

std::vector<Source> legal_sources(const State& state, int exhausted) {
    std::vector<Source> result;
    for (const Source source : sources(state)) {
        if (source_is_legal(state, exhausted, source.color, source.cap)) {
            result.push_back(source);
        }
    }
    return result;
}

bool is_tq_terminal(const State& state) {
    if (!algebraically_consistent(state, 1) || !legal_sources(state, 1).empty()) {
        return false;
    }
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
                                if (is_tq_terminal(state)) terminals.insert(state);
                            }
                        }
                    }
                }
            }
        }
    }
    return {terminals.begin(), terminals.end()};
}

std::optional<State> apply_exhausting_action(const State& state, int exhausted,
                                             const ExhaustAction& action) {
    if (action.old_color < 0 || action.old_color >= kColors ||
        action.final_color < 0 || action.final_color >= kColors ||
        action.old_color == action.final_color || action.old_cap < 1 ||
        action.old_cap >= kHeight ||
        !source_is_legal(state, exhausted, action.old_color, action.old_cap)) {
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
    if (!algebraically_consistent(successor, exhausted + 1)) return std::nullopt;
    return successor;
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
                Debts tested = debts;
                tested[old_color] += old_cap;
                if (positive_count(tested) > kEmpty) continue;
                State parent = canonical_state(debts, caps);
                if (algebraically_consistent(parent, 0)) candidates.push_back(parent);
            }
        }
    }
    std::sort(candidates.begin(), candidates.end());
    return candidates;
}

std::vector<ExhaustAction> exhausting_actions_to(const State& parent,
                                                 const State& terminal) {
    std::set<ExhaustAction> actions;
    for (int old_color = 0; old_color < kColors; ++old_color) {
        const std::set<int> unique_caps(parent[old_color].caps.begin(),
                                        parent[old_color].caps.end());
        for (const int old_cap : unique_caps) {
            for (int final_color = 0; final_color < kColors; ++final_color) {
                ExhaustAction action{old_color, old_cap, final_color};
                const auto successor = apply_exhausting_action(parent, 0, action);
                if (successor && *successor == terminal) actions.insert(action);
            }
        }
    }
    return {actions.begin(), actions.end()};
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
    for (const auto& pair : pairs) parents.insert(pair.first);
    bridge.canonical_parent_count = parents.size();

    for (const auto& pair : pairs) {
        const State& parent = pair.first;
        const State& terminal = pair.second;
        const auto legal = legal_sources(parent, 0);
        const auto actions = exhausting_actions_to(parent, terminal);
        require(actions.size() == 1, "bridge edge does not have a unique bad action");
        const ExhaustAction bad = actions.front();
        if (legal.size() == 1) continue;
        ++bridge.sibling_edge_count;

        Debts labeled_terminal = state_debts(parent);
        Caps remaining_caps = state_caps(parent);
        auto& bad_caps = remaining_caps[bad.old_color];
        const auto found = std::find(bad_caps.begin(), bad_caps.end(), bad.old_cap);
        require(found != bad_caps.end(), "bridge bad source is absent");
        bad_caps.erase(found);
        labeled_terminal[bad.old_color] += bad.old_cap;
        labeled_terminal[bad.final_color] += kHeight - bad.old_cap;
        require(canonical_state(labeled_terminal, remaining_caps) == terminal,
                "labeled bridge replay does not reach its terminal");

        int q_color = -1;
        for (int color = 0; color < kColors; ++color) {
            if (remaining_caps[color].size() == 3) {
                require(q_color == -1, "bridge has two three-column colors");
                q_color = color;
            } else {
                require(remaining_caps[color].empty(),
                        "bridge remainder is not an all-q triple");
            }
        }
        require(q_color >= 0, "bridge has no terminal q color");
        std::sort(remaining_caps[q_color].begin(), remaining_caps[q_color].end());
        Edge edge;
        edge.ordinal = bridge.edges.size();
        edge.parent = parent;
        edge.terminal = terminal;
        edge.bad = bad;
        edge.terminal_debts = labeled_terminal;
        edge.q_color = q_color;
        std::copy(remaining_caps[q_color].begin(), remaining_caps[q_color].end(),
                  edge.q_caps.begin());
        edge.legal_source_count = static_cast<int>(legal.size());
        bridge.edges.push_back(std::move(edge));
    }

    require(bridge.terminal_count == kExpectedTqTerminals,
            "Tq terminal count is not 71");
    require(bridge.labeled_candidates == kExpectedLabeledCandidates,
            "labeled first-exhaust candidate count is not 624");
    require(bridge.canonical_parent_count == kExpectedCanonicalParents,
            "canonical parent count is not 418");
    require(bridge.canonical_edge_count == kExpectedCanonicalEdges,
            "canonical edge count is not 429");
    require(bridge.sibling_edge_count == kExpectedSiblingEdges,
            "sibling edge count is not 423");
    return bridge;
}

std::vector<Card> cards_for(int q_color, int cap) {
    std::vector<Card> cards;
    for (int color = 0; color < kColors; ++color) {
        if (color == q_color) continue;
        for (int endpoint = cap + 1; endpoint <= kHeight; ++endpoint) {
            cards.push_back({color, endpoint});
        }
    }
    return cards;
}

std::uint64_t multinomial(const Counts& counts) {
    static constexpr std::array<std::uint64_t, 21> factorial{{
        1ULL, 1ULL, 2ULL, 6ULL, 24ULL, 120ULL, 720ULL, 5040ULL,
        40320ULL, 362880ULL, 3628800ULL, 39916800ULL, 479001600ULL,
        6227020800ULL, 87178291200ULL, 1307674368000ULL,
        20922789888000ULL, 355687428096000ULL, 6402373705728000ULL,
        121645100408832000ULL, 2432902008176640000ULL}};
    int total = 0;
    for (const int count : counts) {
        if (count < 0) return 0;
        total += count;
    }
    require(total >= 0 && total <= 20, "multinomial total exceeds table");
    std::uint64_t result = factorial[static_cast<std::size_t>(total)];
    for (const int count : counts) {
        result /= factorial[static_cast<std::size_t>(count)];
    }
    return result;
}

std::uint64_t count_completions(const Counts& residual,
                                const std::array<int, 3>& tail_lengths,
                                const std::array<Card, 3>& cards) {
    int positions = 0;
    int residual_total = 0;
    for (const int length : tail_lengths) {
        if (length < 0) return 0;
        positions += length;
    }
    for (const int value : residual) {
        if (value < 0) return 0;
        residual_total += value;
    }
    if (positions != residual_total) return 0;

    Counts remaining = residual;
    std::uint64_t result = 0;
    const auto choose_boundaries = [&](const auto& self, int slot) -> void {
        while (slot < 3 && tail_lengths[slot] == 0) ++slot;
        if (slot == 3) {
            result += multinomial(remaining);
            return;
        }
        for (int color = 0; color < kColors; ++color) {
            if (color == cards[slot].color || remaining[color] == 0) continue;
            --remaining[color];
            self(self, slot + 1);
            ++remaining[color];
        }
    };
    choose_boundaries(choose_boundaries, 0);
    return result;
}

bool q_source_is_legal(const Edge& edge, int cap) {
    return source_is_legal(edge.parent, 0, edge.q_color, cap);
}

bool bad_source_legal_after_live(const Edge& edge, int q_cap, const Card& card) {
    Debts debts = state_debts(edge.parent);
    debts[edge.q_color] += q_cap;
    debts[card.color] -= q_cap;
    return source_is_legal(debts, 0, edge.bad.old_color, edge.bad.old_cap);
}

bool immediate_tq_after_sibling_exhaust(const Edge& edge, int slot,
                                        const Card& card) {
    if (card.endpoint != kHeight) return false;
    Debts debts = state_debts(edge.parent);
    Caps caps = state_caps(edge.parent);
    auto& q_caps = caps[edge.q_color];
    const auto found = std::find(q_caps.begin(), q_caps.end(), edge.q_caps[slot]);
    require(found != q_caps.end(), "direct sibling cap is absent");
    q_caps.erase(found);
    debts[edge.q_color] += edge.q_caps[slot];
    debts[card.color] += kHeight - edge.q_caps[slot];
    return is_tq_terminal(canonical_state(debts, caps));
}

bool is_exact_live_tq_corner(const Edge& edge, int slot,
                             const std::array<Card, 3>& cards, int n_value) {
    if (n_value != 0 || cards[slot].endpoint != 3) return false;
    for (int other = 0; other < 3; ++other) {
        if (other == slot) continue;
        if (edge.q_caps[other] != 1 ||
            cards[other].color != cards[slot].color ||
            cards[other].endpoint != 3) {
            return false;
        }
    }
    return true;
}

bool is_refined_d2_reduction(const Edge& edge,
                             const std::array<Card, 3>& cards) {
    bool direct_certified = false;
    bool n_ge_3 = false;
    bool n_le_2_noncorner = false;
    bool nonhandoff = false;
    for (int slot = 0; slot < 3; ++slot) {
        const int q_cap = edge.q_caps[slot];
        if (!q_source_is_legal(edge, q_cap)) continue;
        const Card& card = cards[slot];
        if (card.endpoint == kHeight) {
            direct_certified = direct_certified ||
                !immediate_tq_after_sibling_exhaust(edge, slot, card);
            continue;
        }
        if (!bad_source_legal_after_live(edge, q_cap, card)) {
            nonhandoff = true;
            continue;
        }
        const int n_value = q_cap - edge.terminal_debts[card.color];
        require(n_value >= 0, "live handoff has negative N");
        if (n_value >= 3) {
            n_ge_3 = true;
        } else if (!is_exact_live_tq_corner(edge, slot, cards, n_value)) {
            n_le_2_noncorner = true;
        }
    }
    return !direct_certified && !n_ge_3 && !n_le_2_noncorner && nonhandoff;
}

std::vector<Decoration> enumerate_decorations(const Bridge& bridge) {
    static constexpr std::array<std::tuple<std::size_t, std::uint64_t,
                                           std::uint64_t>, 12> expected{{
        {116, 198, 64680}, {117, 732, 252252}, {174, 263, 620928},
        {175, 192, 51744}, {178, 104, 19404}, {184, 6, 462},
        {236, 8, 72072}, {237, 6, 11088}, {238, 4, 924},
        {242, 8, 11088}, {244, 6, 924}, {248, 8, 924}}};

    std::map<std::size_t, std::pair<std::uint64_t, std::uint64_t>> rows;
    std::vector<Decoration> decorations;
    for (const Edge& edge : bridge.edges) {
        if (edge.legal_source_count != 3) continue;
        const auto cards0 = cards_for(edge.q_color, edge.q_caps[0]);
        const auto cards1 = cards_for(edge.q_color, edge.q_caps[1]);
        const auto cards2 = cards_for(edge.q_color, edge.q_caps[2]);
        for (const Card& card0 : cards0) {
            for (const Card& card1 : cards1) {
                for (const Card& card2 : cards2) {
                    const std::array<Card, 3> cards{{card0, card1, card2}};
                    Counts residual{};
                    const Counts exposed = exposed_counts(edge.parent);
                    for (int color = 0; color < kColors; ++color) {
                        residual[color] = kHeight - exposed[color];
                    }
                    residual[edge.bad.final_color] -= kHeight - edge.bad.old_cap;
                    std::array<int, 3> tails{};
                    for (int slot = 0; slot < 3; ++slot) {
                        residual[cards[slot].color] -=
                            cards[slot].endpoint - edge.q_caps[slot];
                        tails[slot] = kHeight - cards[slot].endpoint;
                    }
                    const std::uint64_t completions =
                        count_completions(residual, tails, cards);
                    if (completions == 0 ||
                        !is_refined_d2_reduction(edge, cards)) {
                        continue;
                    }
                    Decoration decoration;
                    decoration.ordinal = decorations.size();
                    decoration.edge_index = edge.ordinal;
                    decoration.cards = cards;
                    decoration.residual_after_forced = residual;
                    decoration.free_tail_lengths = tails;
                    decoration.residual_words_expected = completions;
                    decorations.push_back(decoration);
                    auto& row = rows[edge.ordinal];
                    ++row.first;
                    row.second += completions;
                }
            }
        }
    }

    require(rows.size() == kExpectedSelectedEdges,
            "three-source D2 edge count is not 12");
    for (const auto& item : expected) {
        const std::size_t edge = std::get<0>(item);
        const auto found = rows.find(edge);
        require(found != rows.end(), "expected three-source edge is absent");
        require(found->second.first == std::get<1>(item) &&
                    found->second.second == std::get<2>(item),
                "three-source per-edge decoration ledger drifted");
    }
    require(decorations.size() == kExpectedDecorations,
            "three-source D2 decoration count is not 1535");
    const std::uint64_t words = std::accumulate(
        decorations.begin(), decorations.end(), std::uint64_t{0},
        [](std::uint64_t sum, const Decoration& decoration) {
            return sum + decoration.residual_words_expected;
        });
    require(words == kExpectedResidualWords,
            "three-source residual-word weight is not 1106490");
    return decorations;
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
                require(advanced, "winning fixed future has no safe successor");
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
            require(next_color != old_color, "hidden word repeats current top color");
            int first = cursor;
            while (first > 0 &&
                   word[static_cast<std::size_t>(first - 1)] == next_color) {
                --first;
            }
            const int length = cursor - first + 1;
            const int next_cap = old_cap + length;
            events_[column].push_back({old_color, old_cap, next_color, next_cap});
            old_color = next_color;
            old_cap = next_cap;
            cursor = first - 1;
        }
        require(!events_[column].empty() &&
                    events_[column].back().next_cap == kHeight,
                "fixed future does not exhaust its column at height seven");
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
        int result = 0;
        for (std::size_t column = 0; column < kColors; ++column) {
            result += ranks[column] == events_[column].size();
        }
        return result;
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

std::string digits(const std::vector<int>& values) {
    std::string result;
    result.reserve(values.size());
    for (const int value : values) {
        result.push_back(static_cast<char>('0' + value));
    }
    return result;
}

FixedFixture make_fixture(const Edge& edge,
                          const std::array<std::vector<int>, 3>& q_words) {
    FixedFixture fixture;
    fixture.debts = state_debts(edge.parent);
    fixture.sources[0] = {edge.bad.old_color, edge.bad.old_cap};
    fixture.hidden_bottom_to_top[0].assign(
        static_cast<std::size_t>(kHeight - edge.bad.old_cap),
        edge.bad.final_color);
    for (std::size_t slot = 0; slot < 3; ++slot) {
        fixture.sources[slot + 1] = {edge.q_color, edge.q_caps[slot]};
        fixture.hidden_bottom_to_top[slot + 1] = q_words[slot];
    }

    Counts used{};
    for (std::size_t column = 0; column < kColors; ++column) {
        const auto& word = fixture.hidden_bottom_to_top[column];
        require(word.size() == static_cast<std::size_t>(
                    kHeight - fixture.sources[column].cap),
                "fixture hidden word has the wrong length");
        require(!word.empty() && word.back() != fixture.sources[column].color,
                "fixture does not begin at a genuine run boundary");
        for (const int color : word) ++used[color];
    }
    const Counts exposed = exposed_counts(edge.parent);
    for (int color = 0; color < kColors; ++color) {
        require(used[color] == kHeight - exposed[color],
                "fixture does not realize the parent color inventory");
    }
    return fixture;
}

template <class Callback>
bool for_each_fixed_future(const Decoration& decoration, const Edge& edge,
                           Callback&& callback) {
    Counts remaining = decoration.residual_after_forced;
    std::array<int, 3> boundaries{{-1, -1, -1}};
    std::uint64_t emitted = 0;
    bool stopped = false;

    const auto choose_boundaries = [&](const auto& self, int slot) -> void {
        if (stopped) return;
        while (slot < 3 && decoration.free_tail_lengths[slot] == 0) ++slot;
        if (slot < 3) {
            for (int color = 0; color < kColors; ++color) {
                if (color == decoration.cards[slot].color || remaining[color] == 0) {
                    continue;
                }
                --remaining[color];
                boundaries[slot] = color;
                self(self, slot + 1);
                boundaries[slot] = -1;
                ++remaining[color];
                if (stopped) return;
            }
            return;
        }

        std::vector<int> pool;
        for (int color = 0; color < kColors; ++color) {
            pool.insert(pool.end(), static_cast<std::size_t>(remaining[color]), color);
        }
        std::array<std::vector<int>, 3> free_top_to_bottom;
        int free_slots = 0;
        for (int q_slot = 0; q_slot < 3; ++q_slot) {
            const int length = decoration.free_tail_lengths[q_slot];
            free_top_to_bottom[q_slot].assign(static_cast<std::size_t>(length), -1);
            if (length > 0) {
                require(boundaries[q_slot] >= 0, "free tail has no boundary color");
                free_top_to_bottom[q_slot][0] = boundaries[q_slot];
                free_slots += length - 1;
            }
        }
        require(static_cast<int>(pool.size()) == free_slots,
                "free-tail pool has the wrong size");

        do {
            std::size_t cursor = 0;
            for (int q_slot = 0; q_slot < 3; ++q_slot) {
                for (std::size_t position = 1;
                     position < free_top_to_bottom[q_slot].size(); ++position) {
                    free_top_to_bottom[q_slot][position] = pool[cursor++];
                }
            }
            require(cursor == pool.size(), "free-tail permutation was not consumed");

            std::array<std::vector<int>, 3> q_words_bottom_to_top;
            for (int q_slot = 0; q_slot < 3; ++q_slot) {
                q_words_bottom_to_top[q_slot].assign(
                    free_top_to_bottom[q_slot].rbegin(),
                    free_top_to_bottom[q_slot].rend());
                const int forced = decoration.cards[q_slot].endpoint -
                                   edge.q_caps[q_slot];
                q_words_bottom_to_top[q_slot].insert(
                    q_words_bottom_to_top[q_slot].end(),
                    static_cast<std::size_t>(forced),
                    decoration.cards[q_slot].color);
            }
            ++emitted;
            if (!callback(q_words_bottom_to_top, free_top_to_bottom)) {
                stopped = true;
                return;
            }
        } while (std::next_permutation(pool.begin(), pool.end()));
    };
    choose_boundaries(choose_boundaries, 0);
    if (!stopped) {
        require(emitted == decoration.residual_words_expected,
                "fixed-future enumeration disagrees with its exact weight");
    }
    return !stopped;
}

std::string join_words(const std::array<std::vector<int>, kColors>& words,
                       char separator) {
    std::ostringstream output;
    for (std::size_t column = 0; column < kColors; ++column) {
        if (column != 0) output << separator;
        output << digits(words[column]);
    }
    return output.str();
}

std::string cards_text(const std::array<Card, 3>& cards) {
    std::ostringstream output;
    for (std::size_t slot = 0; slot < 3; ++slot) {
        if (slot != 0) output << ',';
        output << cards[slot].color << ':' << cards[slot].endpoint;
    }
    return output.str();
}

void update_hash(std::uint64_t& hash, const std::string& text) {
    static constexpr std::uint64_t prime = 1099511628211ULL;
    for (const unsigned char value : text) {
        hash ^= value;
        hash *= prime;
    }
    hash ^= static_cast<unsigned char>('\n');
    hash *= prime;
}

Sample make_sample(std::uint64_t future_index, const Decoration& decoration,
                   const Edge& edge, const FixedFixture& fixture,
                   const FixedFutureSolver::Result& result) {
    Sample sample;
    sample.present = true;
    sample.future_index = future_index;
    sample.decoration_index = decoration.ordinal;
    sample.edge_ordinal = edge.ordinal;
    sample.solvable = result.solvable;
    sample.safe_mask = result.safe_mask;
    sample.path = result.path;
    for (std::size_t column = 0; column < kColors; ++column) {
        sample.hidden_words_bottom_to_top[column] =
            digits(fixture.hidden_bottom_to_top[column]);
    }
    return sample;
}

void write_local_no(std::ostream& output, const Sample& sample,
                    const Edge& edge, const Decoration& decoration) {
    output << "{\"future_index\":" << sample.future_index
           << ",\"decoration_index\":" << sample.decoration_index
           << ",\"bridge_edge\":" << sample.edge_ordinal
           << ",\"parent_debts\":[";
    const Debts debts = state_debts(edge.parent);
    for (int color = 0; color < kColors; ++color) {
        if (color != 0) output << ',';
        output << debts[color];
    }
    output << "],\"bad_source\":[" << edge.bad.old_color << ','
           << edge.bad.old_cap << ',' << edge.bad.final_color
           << "],\"q_color\":" << edge.q_color << ",\"q_caps\":[";
    for (std::size_t slot = 0; slot < 3; ++slot) {
        if (slot != 0) output << ',';
        output << edge.q_caps[slot];
    }
    output << "],\"cards\":[";
    for (std::size_t slot = 0; slot < 3; ++slot) {
        if (slot != 0) output << ',';
        output << '[' << decoration.cards[slot].color << ','
               << decoration.cards[slot].endpoint << ']';
    }
    output << "],\"hidden_words_bottom_to_top\":[";
    for (std::size_t column = 0; column < kColors; ++column) {
        if (column != 0) output << ',';
        output << '"' << sample.hidden_words_bottom_to_top[column] << '"';
    }
    output << "],\"local_status\":\"NO\",\"safe_source_mask\":0}\n";
}

void run_solver_self_tests() {
    {
        const Debts debts{{-5, 0, 2, 3}};
        const std::array<Source, kColors> sources{{
            Source{0, 3}, Source{0, 3}, Source{0, 3}, Source{0, 3}}};
        const std::array<std::vector<int>, kColors> words{{
            std::vector<int>{2, 2, 2, 1},
            std::vector<int>{3, 3, 2, 1},
            std::vector<int>{3, 3, 2, 1},
            std::vector<int>{1, 1, 1, 1}}};
        FixedFutureSolver solver(debts, sources, words);
        const auto result = solver.solve();
        require(!result.solvable && result.safe_mask == 0 && result.path.empty(),
                "known four-way local lock did not solve as local NO");
    }
    {
        const Debts debts{};
        const std::array<Source, kColors> sources{{
            Source{0, 6}, Source{1, 6}, Source{2, 6}, Source{3, 6}}};
        const std::array<std::vector<int>, kColors> words{{
            std::vector<int>{1}, std::vector<int>{2},
            std::vector<int>{3}, std::vector<int>{0}}};
        FixedFutureSolver solver(debts, sources, words);
        const auto result = solver.solve();
        require(result.solvable && result.safe_mask != 0,
                "synthetic two-exhaustion fixture is not YES");
        require(solver.replay(result.path),
                "synthetic winning path did not replay");
    }
}

RunStats run(const Options& options, const Bridge& bridge,
             const std::vector<Decoration>& decorations) {
    RunStats stats;
    stats.limit_requested = options.limit;
    stats.decorations_expected = decorations.size();
    for (const Decoration& decoration : decorations) {
        stats.residual_words_expected += decoration.residual_words_expected;
    }
    require(stats.decorations_expected == kExpectedDecorations,
            "run decoration universe is not 1535");
    require(stats.residual_words_expected == kExpectedResidualWords,
            "run fixed-future universe is not 1106490");

    std::map<std::size_t, std::size_t> row_for_edge;
    for (const Decoration& decoration : decorations) {
        const std::size_t edge_ordinal = bridge.edges[decoration.edge_index].ordinal;
        auto found = row_for_edge.find(edge_ordinal);
        if (found == row_for_edge.end()) {
            const std::size_t row = stats.per_edge.size();
            row_for_edge.emplace(edge_ordinal, row);
            EdgeStats edge_stats;
            edge_stats.edge_ordinal = edge_ordinal;
            stats.per_edge.push_back(edge_stats);
            found = row_for_edge.find(edge_ordinal);
        }
        EdgeStats& edge_stats = stats.per_edge[found->second];
        ++edge_stats.decorations;
        edge_stats.residual_words_expected += decoration.residual_words_expected;
    }
    require(stats.per_edge.size() == kExpectedSelectedEdges,
            "run edge universe is not 12");

    std::optional<std::ofstream> result_ledger;
    std::optional<std::ofstream> local_no_ledger;
    if (!options.output_dir.empty()) {
        std::filesystem::create_directories(options.output_dir);
        result_ledger.emplace(options.output_dir / "fixed-future-results.tsv",
                              std::ios::binary);
        local_no_ledger.emplace(options.output_dir / "local-no-ledger.jsonl",
                                std::ios::binary);
        require(*result_ledger && *local_no_ledger,
                "could not open fixed-future ledgers");
        *result_ledger << "future_index\tdecoration_index\tbridge_edge\tcards"
                          "\thidden_words_bottom_to_top\tlocal_status"
                          "\tsafe_source_mask\tescape_columns\n";
    }

    const std::uint64_t effective_limit = options.limit == 0
        ? stats.residual_words_expected
        : std::min(options.limit, stats.residual_words_expected);
    const auto started = std::chrono::steady_clock::now();
    bool stop = false;
    for (const Decoration& decoration : decorations) {
        if (stop) break;
        const Edge& edge = bridge.edges[decoration.edge_index];
        EdgeStats& edge_stats = stats.per_edge[row_for_edge.at(edge.ordinal)];
        std::uint64_t decoration_checked = 0;
        const bool complete_decoration = for_each_fixed_future(
            decoration, edge,
            [&](const std::array<std::vector<int>, 3>& q_words,
                const std::array<std::vector<int>, 3>&) {
                if (stats.residual_words_checked >= effective_limit) return false;
                const FixedFixture fixture = make_fixture(edge, q_words);
                FixedFutureSolver solver(fixture.debts, fixture.sources,
                                         fixture.hidden_bottom_to_top);
                const auto result = solver.solve();
                const std::uint64_t future_index = stats.residual_words_checked;
                ++stats.residual_words_checked;
                ++edge_stats.residual_words_checked;
                ++decoration_checked;
                stats.states += result.states;
                stats.transitions += result.transitions;
                edge_stats.states += result.states;
                edge_stats.transitions += result.transitions;
                ++edge_stats.safe_mask_distribution[result.safe_mask];

                if (result.solvable) {
                    require(result.safe_mask != 0 && !result.path.empty(),
                            "local YES has no safe first source or path");
                    require(solver.replay(result.path),
                            "local YES escape path did not replay");
                    ++stats.local_yes;
                    ++edge_stats.local_yes;
                    ++stats.winning_paths_replayed;
                    if (!stats.first_yes) {
                        stats.first_yes = make_sample(
                            future_index, decoration, edge, fixture, result);
                    }
                } else {
                    require(result.safe_mask == 0 && result.path.empty(),
                            "local NO unexpectedly has a winning first source");
                    ++stats.local_no;
                    ++edge_stats.local_no;
                    const Sample sample = make_sample(
                        future_index, decoration, edge, fixture, result);
                    if (!stats.first_no) stats.first_no = sample;
                    if (local_no_ledger) {
                        write_local_no(*local_no_ledger, sample, edge, decoration);
                    }
                }

                std::ostringstream row;
                row << future_index << '\t' << decoration.ordinal << '\t'
                    << edge.ordinal << '\t' << cards_text(decoration.cards) << '\t'
                    << join_words(fixture.hidden_bottom_to_top, ',') << '\t'
                    << (result.solvable ? "YES" : "NO") << '\t'
                    << result.safe_mask << '\t' << result.path;
                const std::string row_text = row.str();
                update_hash(stats.ledger_hash, row_text);
                if (result_ledger) *result_ledger << row_text << '\n';

                if (stats.residual_words_checked % 100000 == 0) {
                    std::cout << "progress fixed_futures="
                              << stats.residual_words_checked << '/'
                              << stats.residual_words_expected
                              << " local_no=" << stats.local_no << '\n';
                }
                return true;
            });
        if (complete_decoration) {
            require(decoration_checked == decoration.residual_words_expected,
                    "complete decoration did not enumerate its exact weight");
        }
        if (stats.residual_words_checked >= effective_limit) stop = true;
    }

    stats.elapsed_seconds = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - started).count();
    stats.universe_complete =
        stats.residual_words_checked == stats.residual_words_expected;
    stats.self_checks_passed = true;
    require(stats.local_yes + stats.local_no == stats.residual_words_checked,
            "local YES/NO counts do not partition checked futures");
    require(stats.winning_paths_replayed == stats.local_yes,
            "not every local YES path replayed");
    for (const EdgeStats& edge_stats : stats.per_edge) {
        require(edge_stats.local_yes + edge_stats.local_no ==
                    edge_stats.residual_words_checked,
                "per-edge YES/NO counts do not partition checked futures");
        if (stats.universe_complete) {
            require(edge_stats.residual_words_checked ==
                        edge_stats.residual_words_expected,
                    "full run did not cover a selected edge");
        }
    }
    return stats;
}

std::string status(const RunStats& stats) {
    if (!stats.universe_complete) return "INCOMPLETE";
    if (stats.local_no != 0) return "LOCAL_NO_RESIDUALS_EXPORTED";
    return "THREE_SOURCE_D2_CHECKPOINT_FAMILY_ELIMINATED";
}

std::string bool_json(bool value) {
    return value ? "true" : "false";
}

std::string hex_u64(std::uint64_t value) {
    static constexpr char digits_table[] = "0123456789abcdef";
    std::string result(16, '0');
    for (int index = 15; index >= 0; --index) {
        result[static_cast<std::size_t>(index)] = digits_table[value & 15U];
        value >>= 4U;
    }
    return result;
}

void write_sample_json(std::ostream& output, const std::optional<Sample>& sample) {
    if (!sample) {
        output << "null";
        return;
    }
    output << "{\"future_index\":" << sample->future_index
           << ",\"decoration_index\":" << sample->decoration_index
           << ",\"bridge_edge\":" << sample->edge_ordinal
           << ",\"local_status\":\""
           << (sample->solvable ? "YES" : "NO")
           << "\",\"safe_source_mask\":" << sample->safe_mask
           << ",\"escape_columns\":\"" << sample->path
           << "\",\"hidden_words_bottom_to_top\":[";
    for (std::size_t column = 0; column < kColors; ++column) {
        if (column != 0) output << ',';
        output << '"' << sample->hidden_words_bottom_to_top[column] << '"';
    }
    output << "]}";
}

void write_report(const Options& options, const Bridge& bridge,
                  const RunStats& stats) {
    require(!options.output_dir.empty(), "report output directory is empty");
    const std::string run_status = status(stats);
    const bool eliminated = stats.universe_complete && stats.local_no == 0;
    std::ofstream json(options.output_dir / "report.json", std::ios::binary);
    require(static_cast<bool>(json), "could not create report.json");
    json << "{\n"
         << "  \"schema_version\": 1,\n"
         << "  \"experiment\": \"c4_h7_d2_three_source_checkpoint\",\n"
         << "  \"status\": \"" << run_status << "\",\n"
         << "  \"parameters\": {\"colors\":4,\"height\":7,\"empty\":2},\n"
         << "  \"scope\": {\n"
         << "    \"parent_checkpoint_only\": true,\n"
         << "    \"fixed_hidden_futures\": true,\n"
         << "    \"zero_debt_past_restored\": false,\n"
         << "    \"full_h7_theorem\": false\n"
         << "  },\n"
         << "  \"bridge_reconstruction\": {\"tq_terminals\":"
         << bridge.terminal_count << ",\"labeled_candidates\":"
         << bridge.labeled_candidates << ",\"canonical_parents\":"
         << bridge.canonical_parent_count << ",\"canonical_edges\":"
         << bridge.canonical_edge_count << ",\"sibling_edges\":"
         << bridge.sibling_edge_count << "},\n"
         << "  \"universe\": {\"selected_edges\":" << stats.per_edge.size()
         << ",\"decorations\":" << stats.decorations_expected
         << ",\"labeled_fixed_futures\":" << stats.residual_words_expected
         << "},\n"
         << "  \"run\": {\"limit_requested\":" << stats.limit_requested
         << ",\"universe_complete\":" << bool_json(stats.universe_complete)
         << ",\"fixed_futures_checked\":" << stats.residual_words_checked
         << ",\"local_yes\":" << stats.local_yes
         << ",\"local_no\":" << stats.local_no
         << ",\"winning_paths_replayed\":" << stats.winning_paths_replayed
         << ",\"states\":" << stats.states
         << ",\"transitions\":" << stats.transitions
         << ",\"elapsed_seconds\":" << stats.elapsed_seconds << "},\n"
         << "  \"claims\": {\"three_source_checkpoint_family_eliminated\":"
         << bool_json(eliminated)
         << ",\"zero_debt_initial_family_eliminated\":false,"
            "\"universal_c4_h7_solvability\":false},\n"
         << "  \"ledgers\": {\"fixed_future_results\":"
            "\"fixed-future-results.tsv\",\"local_no\":"
            "\"local-no-ledger.jsonl\",\"result_rows_fnv1a64\":\""
         << hex_u64(stats.ledger_hash) << "\"},\n"
         << "  \"first_local_yes\": ";
    write_sample_json(json, stats.first_yes);
    json << ",\n  \"first_local_no\": ";
    write_sample_json(json, stats.first_no);
    json << ",\n  \"per_edge\": [\n";
    for (std::size_t index = 0; index < stats.per_edge.size(); ++index) {
        const EdgeStats& row = stats.per_edge[index];
        if (index != 0) json << ",\n";
        json << "    {\"bridge_edge\":" << row.edge_ordinal
             << ",\"decorations\":" << row.decorations
             << ",\"fixed_futures_expected\":" << row.residual_words_expected
             << ",\"fixed_futures_checked\":" << row.residual_words_checked
             << ",\"local_yes\":" << row.local_yes
             << ",\"local_no\":" << row.local_no
             << ",\"states\":" << row.states
             << ",\"transitions\":" << row.transitions
             << ",\"safe_mask_distribution\":{";
        bool first = true;
        for (const auto& mask : row.safe_mask_distribution) {
            if (!first) json << ',';
            first = false;
            json << '"' << mask.first << "\":" << mask.second;
        }
        json << "}}";
    }
    json << "\n  ],\n  \"self_checks_passed\": "
         << bool_json(stats.self_checks_passed) << "\n}\n";
    require(static_cast<bool>(json), "failed while writing report.json");

    std::ofstream markdown(options.output_dir / "report.md", std::ios::binary);
    require(static_cast<bool>(markdown), "could not create report.md");
    markdown << "# c=4, h=7 three-source D2 checkpoint audit\n\n"
             << "- Status: `" << run_status << "`.\n"
             << "- Exact target universe: 12 bridge edges, 1,535 decorations, "
                "1,106,490 labeled fixed futures.\n"
             << "- Checked fixed futures: " << stats.residual_words_checked
             << ".\n"
             << "- Parent-checkpoint local YES / NO: " << stats.local_yes
             << " / " << stats.local_no << ".\n"
             << "- Replayed winning paths: " << stats.winning_paths_replayed
             << ".\n\n"
             << "This audit starts at the nonzero-debt first-exhaustion parent. "
                "It does not restore any zero-debt past, eliminate an initial-layout "
                "family, or prove the full c=4,h=7 theorem.\n\n"
             << "| Bridge edge | Decorations | Expected futures | Checked | "
                "Local YES | Local NO |\n"
             << "|---:|---:|---:|---:|---:|---:|\n";
    for (const EdgeStats& row : stats.per_edge) {
        markdown << '|' << row.edge_ordinal << '|' << row.decorations << '|'
                 << row.residual_words_expected << '|'
                 << row.residual_words_checked << '|' << row.local_yes << '|'
                 << row.local_no << "|\n";
    }
    require(static_cast<bool>(markdown), "failed while writing report.md");
}

} // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parse_options(argc, argv);
        if (options.self_test) run_solver_self_tests();
        const Bridge bridge = build_bridge();
        const auto decorations = enumerate_decorations(bridge);
        const RunStats stats = run(options, bridge, decorations);
        if (!options.output_dir.empty()) write_report(options, bridge, stats);
        std::cout << "status=" << status(stats)
                  << " edges=" << stats.per_edge.size()
                  << " decorations=" << stats.decorations_expected
                  << " fixed_futures=" << stats.residual_words_checked << '/'
                  << stats.residual_words_expected
                  << " local_yes=" << stats.local_yes
                  << " local_no=" << stats.local_no
                  << " elapsed_seconds=" << stats.elapsed_seconds << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 2;
    }
}
