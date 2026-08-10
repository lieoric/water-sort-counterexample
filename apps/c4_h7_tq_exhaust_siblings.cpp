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
constexpr std::uint64_t kExpectedUniqueParents = 6;
constexpr std::uint64_t kExpectedSiblingParents = 412;
constexpr std::uint64_t kExpectedUniqueEdges = 6;
constexpr std::uint64_t kExpectedSiblingEdges = 423;
constexpr std::uint64_t kExpectedLegalSiblingCards = 18177;
constexpr std::uint64_t kExpectedLegalSiblingJoint = 1220361;
constexpr std::uint64_t kExpectedAllQJoint = 1256148;
constexpr std::uint64_t kExpectedFeasible = 403685;
constexpr std::uint64_t kExpectedNonnegative = 406528;
constexpr std::uint64_t kExpectedResidualWords = 6131033832ULL;
constexpr std::uint64_t kExpectedTwoExhaustion = 70633;
constexpr std::uint64_t kExpectedTwoExhaustionWords = 8629839;
constexpr std::uint64_t kExpectedLiveHandoff = 254899;
constexpr std::uint64_t kExpectedLiveHandoffWords = 3235811235ULL;
constexpr std::uint64_t kExpectedObstruction = 78153;
constexpr std::uint64_t kExpectedObstructionWords = 2886592758ULL;
constexpr std::uint64_t kExpectedDirectCertified = 101922;
constexpr std::uint64_t kExpectedDirectCertifiedWords = 13128393;
constexpr std::uint64_t kExpectedHandoffNGe3 = 11226;
constexpr std::uint64_t kExpectedHandoffNGe3Words = 10591970;
constexpr std::uint64_t kExpectedHandoffNLe2 = 223321;
constexpr std::uint64_t kExpectedHandoffNLe2Words = 3223219144ULL;
constexpr std::uint64_t kExpectedD2Reduction = 67206;
constexpr std::uint64_t kExpectedD2ReductionWords = 2883858705ULL;
constexpr std::uint64_t kExpectedTqCornerOnly = 10;
constexpr std::uint64_t kExpectedTqCornerOnlyWords = 235620;

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
    Debts terminal_debts{}; // Labeled in the parent's color coordinates.
    int q_color = -1;
    std::array<int, 3> q_caps{};
    int legal_source_count = 0;
    bool old_bad_equals_q = false;
    std::uint64_t raw_expected = 0;
};

struct ClassStats {
    std::uint64_t decorations = 0;
    std::uint64_t residual_words = 0;
};

struct Sample {
    std::string id;
    std::size_t edge = 0;
    std::array<Card, 3> cards{};
    std::array<int, 3> free_tail_lengths{};
    Counts residual_after_forced{};
    std::uint64_t completion_count = 0;
    std::string classification;
    // Column order is bad, q0, q1, q2.  Each word is bottom-to-top.
    std::array<std::vector<int>, 4> hidden_words;
};

struct DecorationKey {
    std::size_t edge = 0;
    std::array<Card, 3> cards{};
};

struct EdgeStats {
    std::uint64_t raw_checked = 0;
    std::uint64_t nonnegative = 0;
    std::uint64_t feasible = 0;
    std::uint64_t infeasible = 0;
    std::uint64_t residual_words = 0;
    ClassStats two_exhaustion;
    ClassStats live_handoff;
    ClassStats obstruction;
    std::uint64_t handoff_n_ge_3 = 0;
    std::uint64_t handoff_n_ge_3_words = 0;
    std::uint64_t handoff_n_le_2 = 0;
    std::uint64_t handoff_n_le_2_words = 0;
    std::uint64_t immediate_tq_corner = 0;
    std::uint64_t immediate_tq_corner_words = 0;
    ClassStats direct_certified;
    ClassStats n_ge_3_certified;
    ClassStats n_le_2_certified;
    ClassStats d2_reduction;
    ClassStats tq_corner_only;
    std::optional<std::size_t> sample;
};

struct Bridge {
    std::vector<Edge> edges;
    std::uint64_t terminal_count = 0;
    std::uint64_t labeled_candidates = 0;
    std::uint64_t canonical_parent_count = 0;
    std::uint64_t canonical_edge_count = 0;
    std::uint64_t unique_parent_count = 0;
    std::uint64_t sibling_parent_count = 0;
    std::uint64_t unique_edge_count = 0;
    std::uint64_t sibling_edge_count = 0;
    std::map<int, std::uint64_t> parent_legal_distribution;
    std::map<int, std::uint64_t> edge_legal_distribution;
    bool action_unique = true;
    bool all_edges_replay = true;
    bool all_final_colors_isolated = true;
};

struct RunStats {
    bool self_checks_passed = false;
    bool next_run_universe_complete = false;
    std::uint64_t limit_requested = 0;
    std::uint64_t legal_sibling_cards = 0;
    std::uint64_t legal_sibling_joint = 0;
    std::uint64_t all_q_joint = 0;
    std::uint64_t raw_checked = 0;
    std::uint64_t nonnegative = 0;
    std::uint64_t feasible = 0;
    std::uint64_t infeasible = 0;
    std::uint64_t residual_words = 0;
    ClassStats two_exhaustion;
    ClassStats live_handoff;
    ClassStats obstruction;
    std::uint64_t handoff_n_ge_3 = 0;
    std::uint64_t handoff_n_ge_3_words = 0;
    std::uint64_t handoff_n_le_2 = 0;
    std::uint64_t handoff_n_le_2_words = 0;
    std::uint64_t immediate_tq_corner = 0;
    std::uint64_t immediate_tq_corner_words = 0;
    std::uint64_t immediate_tq_corner_card_count = 0;
    std::uint64_t immediate_tq_corner_edge_count = 0;
    std::uint64_t immediate_tq_corner_parent_count = 0;
    std::map<int, std::uint64_t> immediate_tq_corner_m_distribution;
    ClassStats direct_certified;
    ClassStats n_ge_3_certified;
    ClassStats n_le_2_certified;
    ClassStats d2_reduction;
    ClassStats tq_corner_only;
    std::vector<EdgeStats> per_edge;
    std::vector<Sample> samples;
    std::vector<DecorationKey> checked_prefix;
    double elapsed_seconds = 0.0;
};

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error("self-check failed: " + message);
}

void usage() {
    std::cerr << "Usage: water-c4-h7-tq-exhaust-siblings "
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
    Debts adjusted = debts;
    adjusted[color] += cap;
    return positive_count(adjusted) <= kEmpty + z;
}

bool source_is_legal(const State& state, int z, int color, int cap) {
    return source_is_legal(state_debts(state), z, color, cap);
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
    for (const Source source : sources(state)) {
        if (source_is_legal(state, z, source.color, source.cap)) result.push_back(source);
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
        !source_is_legal(state, z, action.old_color, action.old_cap)) {
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
        std::set<int> unique_caps(parent[old_color].caps.begin(),
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

bool final_color_is_isolated(const State& parent, const ExhaustAction& action) {
    Debts debts = state_debts(parent);
    Caps caps = state_caps(parent);
    auto& old_caps = caps[action.old_color];
    const auto found = std::find(old_caps.begin(), old_caps.end(), action.old_cap);
    if (found == old_caps.end()) return false;
    old_caps.erase(found);
    debts[action.old_color] += action.old_cap;
    debts[action.final_color] += kHeight - action.old_cap;
    return debts[action.final_color] == kHeight - action.old_cap &&
           caps[action.final_color].empty();
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
                Debts test = debts;
                test[old_color] += old_cap;
                if (positive_count(test) > kEmpty) continue;
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
    std::set<State> unique_parents;
    std::set<State> sibling_parents;
    for (const auto& pair : pairs) {
        parents.insert(pair.first);
        const auto legal = legal_sources(pair.first, 0);
        if (legal.size() == 1) unique_parents.insert(pair.first);
        else sibling_parents.insert(pair.first);
    }
    bridge.canonical_parent_count = parents.size();
    bridge.unique_parent_count = unique_parents.size();
    bridge.sibling_parent_count = sibling_parents.size();
    for (const State& parent : parents) {
        const int count = static_cast<int>(legal_sources(parent, 0).size());
        if (count >= 2) ++bridge.parent_legal_distribution[count];
    }

    for (const auto& pair : pairs) {
        const State& parent = pair.first;
        const State& terminal = pair.second;
        const auto legal = legal_sources(parent, 0);
        const auto actions = exhausting_actions_to(parent, terminal);
        bridge.action_unique = bridge.action_unique && actions.size() == 1;
        if (actions.empty()) {
            bridge.all_edges_replay = false;
            continue;
        }
        const ExhaustAction bad = actions.front();
        bridge.all_edges_replay = bridge.all_edges_replay &&
            apply_exhausting_action(parent, 0, bad) == std::optional<State>(terminal);
        bridge.all_final_colors_isolated = bridge.all_final_colors_isolated &&
            final_color_is_isolated(parent, bad);
        if (legal.size() == 1) {
            ++bridge.unique_edge_count;
            continue;
        }
        ++bridge.edge_legal_distribution[static_cast<int>(legal.size())];
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
                "labeled bridge replay does not canonicalize to terminal");

        int q_color = -1;
        for (int color = 0; color < kColors; ++color) {
            if (remaining_caps[color].size() == 3) {
                require(q_color == -1, "bridge has more than one three-column color");
                q_color = color;
            } else {
                require(remaining_caps[color].empty(),
                        "bridge remainder is not an all-q triple");
            }
        }
        require(q_color >= 0, "bridge has no q color");
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
        edge.old_bad_equals_q = bad.old_color == q_color;
        edge.raw_expected = 1;
        for (const int cap : edge.q_caps) {
            edge.raw_expected *= static_cast<std::uint64_t>((kColors - 1) * (kHeight - cap));
        }
        bridge.edges.push_back(std::move(edge));
    }
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
    require(total >= 0 && total <= 20, "multinomial total exceeds exact table");
    std::uint64_t value = factorial[static_cast<std::size_t>(total)];
    for (const int count : counts) value /= factorial[static_cast<std::size_t>(count)];
    return value;
}

struct CompletionInfo {
    std::uint64_t count = 0;
    std::optional<std::array<std::vector<int>, 3>> free_tails;
};

CompletionInfo count_completions(const Counts& residual,
                                 const std::array<int, 3>& tail_lengths,
                                 const std::array<Card, 3>& cards,
                                 bool want_sample) {
    CompletionInfo result;
    int total_positions = 0;
    int distinguished = 0;
    for (int i = 0; i < 3; ++i) {
        if (tail_lengths[i] < 0) return result;
        total_positions += tail_lengths[i];
        distinguished += tail_lengths[i] > 0;
    }
    int residual_total = 0;
    for (const int count : residual) {
        if (count < 0) return result;
        residual_total += count;
    }
    if (residual_total != total_positions) return result;

    Counts remaining = residual;
    std::array<int, 3> chosen{{-1, -1, -1}};
    const auto recurse = [&](const auto& self, int column) -> void {
        while (column < 3 && tail_lengths[column] == 0) ++column;
        if (column == 3) {
            const std::uint64_t ways = multinomial(remaining);
            result.count += ways;
            if (want_sample && ways > 0 && !result.free_tails) {
                std::array<std::vector<int>, 3> tails;
                Counts pool = remaining;
                for (int i = 0; i < 3; ++i) {
                    tails[i].assign(static_cast<std::size_t>(tail_lengths[i]), -1);
                    if (tail_lengths[i] > 0) tails[i].back() = chosen[i];
                }
                for (int i = 0; i < 3; ++i) {
                    const int free_slots = tail_lengths[i] - (tail_lengths[i] > 0 ? 1 : 0);
                    for (int slot = 0; slot < free_slots; ++slot) {
                        int color = 0;
                        while (color < kColors && pool[color] == 0) ++color;
                        require(color < kColors, "sample pool ran out of colors");
                        tails[i][static_cast<std::size_t>(slot)] = color;
                        --pool[color];
                    }
                }
                require(std::all_of(pool.begin(), pool.end(), [](int x) { return x == 0; }),
                        "sample pool was not exhausted");
                result.free_tails = std::move(tails);
            }
            return;
        }
        for (int color = 0; color < kColors; ++color) {
            if (color == cards[column].color || remaining[color] == 0) continue;
            --remaining[color];
            chosen[column] = color;
            self(self, column + 1);
            ++remaining[color];
            chosen[column] = -1;
        }
    };
    recurse(recurse, 0);
    (void)distinguished;
    return result;
}

bool bad_source_legal_after_live(const Edge& edge, int q_cap, const Card& card) {
    Debts debts = state_debts(edge.parent);
    debts[edge.q_color] += q_cap;
    debts[card.color] -= q_cap;
    return source_is_legal(debts, 0, edge.bad.old_color, edge.bad.old_cap);
}

bool bad_source_legal_after_sibling_exhaust(const Edge& edge, int q_cap,
                                            const Card& card) {
    Debts debts = state_debts(edge.parent);
    debts[edge.q_color] += q_cap;
    debts[card.color] += kHeight - q_cap;
    return source_is_legal(debts, 1, edge.bad.old_color, edge.bad.old_cap);
}

bool q_source_is_legal(const Edge& edge, int cap) {
    return source_is_legal(edge.parent, 0, edge.q_color, cap);
}

bool immediate_tq_after_sibling_exhaust(const Edge& edge, int slot,
                                        const Card& card) {
    if (card.endpoint != kHeight) return false;
    Debts debts = state_debts(edge.parent);
    Caps caps = state_caps(edge.parent);
    auto& q_caps = caps[edge.q_color];
    const auto found = std::find(q_caps.begin(), q_caps.end(), edge.q_caps[slot]);
    require(found != q_caps.end(), "q slot is absent during direct replay");
    q_caps.erase(found);
    debts[edge.q_color] += edge.q_caps[slot];
    debts[card.color] += kHeight - edge.q_caps[slot];
    return is_tq_terminal(canonical_state(debts, caps));
}

std::string state_json(const State& state) {
    std::ostringstream out;
    out << '[';
    for (int i = 0; i < kColors; ++i) {
        if (i) out << ',';
        out << "{\"debt\":" << state[i].debt << ",\"caps\":[";
        for (std::size_t j = 0; j < state[i].caps.size(); ++j) {
            if (j) out << ',';
            out << state[i].caps[j];
        }
        out << "]}";
    }
    out << ']';
    return out.str();
}

template <typename T, std::size_t N>
std::string array_json(const std::array<T, N>& values) {
    std::ostringstream out;
    out << '[';
    for (std::size_t i = 0; i < N; ++i) {
        if (i) out << ',';
        out << values[i];
    }
    out << ']';
    return out.str();
}

std::string vector_json(const std::vector<int>& values) {
    std::ostringstream out;
    out << '[';
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i) out << ',';
        out << values[i];
    }
    out << ']';
    return out.str();
}

void add_class(ClassStats& target, std::uint64_t completions) {
    ++target.decorations;
    target.residual_words += completions;
}

bool is_exact_live_tq_corner(const Edge& edge, int slot,
                             const std::array<Card, 3>& cards, int n_value) {
    if (n_value != 0 || cards[slot].endpoint != 3) return false;
    for (int other = 0; other < 3; ++other) {
        if (other == slot) continue;
        if (edge.q_caps[other] != 1 || cards[other].color != cards[slot].color ||
            cards[other].endpoint != 3) {
            return false;
        }
    }
    return true;
}

std::string refined_classification(bool direct_certified, bool n_ge_3,
                                   bool n_le_2_noncorner, bool nonhandoff,
                                   bool corner) {
    if (direct_certified) return "direct_exhaustion_certified_yes";
    if (n_ge_3) return "live_handoff_n_ge_3_certified_yes";
    if (n_le_2_noncorner) return "live_handoff_n_le_2_certified_yes";
    if (nonhandoff) return "live_nonhandoff_d2_reduction";
    if (corner) return "tq_low_energy_corner_only";
    return "unclassified";
}

void record_sample(const Edge& edge, const std::array<Card, 3>& cards,
                   const std::array<int, 3>& tails, const Counts& residual,
                   const CompletionInfo& completion, const std::string& classification,
                   RunStats& stats, EdgeStats& edge_stats) {
    require(completion.free_tails.has_value(), "feasible sample has no concrete tails");
    Sample sample;
    sample.edge = edge.ordinal;
    sample.id = "edge-" + std::to_string(edge.ordinal) + "-sample";
    sample.cards = cards;
    sample.free_tail_lengths = tails;
    sample.residual_after_forced = residual;
    sample.completion_count = completion.count;
    sample.classification = classification;
    sample.hidden_words[0].assign(
        static_cast<std::size_t>(kHeight - edge.bad.old_cap), edge.bad.final_color);
    for (int slot = 0; slot < 3; ++slot) {
        sample.hidden_words[slot + 1] = (*completion.free_tails)[slot];
        const int forced = cards[slot].endpoint - edge.q_caps[slot];
        sample.hidden_words[slot + 1].insert(
            sample.hidden_words[slot + 1].end(), static_cast<std::size_t>(forced),
            cards[slot].color);
        require(sample.hidden_words[slot + 1].size() ==
                    static_cast<std::size_t>(kHeight - edge.q_caps[slot]),
                "sample q word has the wrong length");
    }
    Counts used{};
    for (const auto& word : sample.hidden_words) {
        for (const int color : word) ++used[color];
    }
    const Counts exposed = exposed_counts(edge.parent);
    for (int color = 0; color < kColors; ++color) {
        require(used[color] == kHeight - exposed[color],
                "sample does not realize the parent color balance");
    }
    edge_stats.sample = stats.samples.size();
    stats.samples.push_back(std::move(sample));
}

RunStats run_census(const Bridge& bridge, std::uint64_t limit) {
    const auto started = std::chrono::steady_clock::now();
    RunStats stats;
    stats.limit_requested = limit;
    stats.per_edge.resize(bridge.edges.size());

    std::set<State> direct_corner_parents;
    std::set<std::size_t> direct_corner_edges;
    for (const Edge& edge : bridge.edges) {
        std::uint64_t legal_joint = 1;
        int legal_q_slots = 0;
        for (int slot = 0; slot < 3; ++slot) {
            const auto cards = cards_for(edge.q_color, edge.q_caps[slot]);
            if (q_source_is_legal(edge, edge.q_caps[slot])) {
                ++legal_q_slots;
                stats.legal_sibling_cards += cards.size();
                legal_joint *= cards.size();
            }
        }
        require(legal_q_slots >= 1, "sibling edge has no legal q sibling");
        stats.legal_sibling_joint += legal_joint;
        stats.all_q_joint += edge.raw_expected;

        std::set<std::pair<int, int>> unique_direct_cards;
        for (int slot = 0; slot < 3; ++slot) {
            const int cap = edge.q_caps[slot];
            if (!q_source_is_legal(edge, cap)) continue;
            for (int color = 0; color < kColors; ++color) {
                if (color == edge.q_color) continue;
                const Card card{color, kHeight};
                if (!immediate_tq_after_sibling_exhaust(edge, slot, card)) continue;
                if (kHeight - edge.bad.old_cap + kHeight - cap > kHeight) continue;
                unique_direct_cards.emplace(cap, color);
            }
        }
        for (const auto& card_key : unique_direct_cards) {
            ++stats.immediate_tq_corner_card_count;
            direct_corner_edges.insert(edge.ordinal);
            direct_corner_parents.insert(edge.parent);
            const int energy = -edge.terminal_debts[edge.q_color];
            const int m_value = edge.bad.old_cap + energy - card_key.first;
            require(m_value == 0 || m_value == 1,
                    "jointly feasible immediate Tq card is not low-energy");
            std::vector<int> other_caps(edge.q_caps.begin(), edge.q_caps.end());
            const auto found = std::find(other_caps.begin(), other_caps.end(), card_key.first);
            require(found != other_caps.end(), "direct corner cap is absent");
            other_caps.erase(found);
            require(std::min({edge.bad.old_cap, other_caps[0], other_caps[1]}) > m_value,
                    "direct Tq corner violates its cap inequality");
            ++stats.immediate_tq_corner_m_distribution[m_value];
        }
    }
    stats.immediate_tq_corner_edge_count = direct_corner_edges.size();
    stats.immediate_tq_corner_parent_count = direct_corner_parents.size();

    bool stop = false;
    for (const Edge& edge : bridge.edges) {
        EdgeStats& edge_stats = stats.per_edge[edge.ordinal];
        const auto cards0 = cards_for(edge.q_color, edge.q_caps[0]);
        const auto cards1 = cards_for(edge.q_color, edge.q_caps[1]);
        const auto cards2 = cards_for(edge.q_color, edge.q_caps[2]);
        for (const Card& card0 : cards0) {
            for (const Card& card1 : cards1) {
                for (const Card& card2 : cards2) {
                    if (limit != 0 && stats.raw_checked >= limit) {
                        stop = true;
                        break;
                    }
                    const std::array<Card, 3> cards{{card0, card1, card2}};
                    ++stats.raw_checked;
                    ++edge_stats.raw_checked;
                    if (limit != 0) stats.checked_prefix.push_back({edge.ordinal, cards});

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
                    int residual_total = 0;
                    int tail_total = 0;
                    bool nonnegative = true;
                    for (const int value : residual) {
                        nonnegative = nonnegative && value >= 0;
                        residual_total += value;
                    }
                    for (const int length : tails) tail_total += length;
                    nonnegative = nonnegative && residual_total == tail_total;
                    if (nonnegative) {
                        ++stats.nonnegative;
                        ++edge_stats.nonnegative;
                    }

                    CompletionInfo completion = count_completions(
                        residual, tails, cards, !edge_stats.sample.has_value());
                    if (completion.count == 0) {
                        ++stats.infeasible;
                        ++edge_stats.infeasible;
                        continue;
                    }
                    ++stats.feasible;
                    ++edge_stats.feasible;
                    stats.residual_words += completion.count;
                    edge_stats.residual_words += completion.count;

                    bool two_exhaustion = false;
                    bool live_handoff = false;
                    bool direct_certified = false;
                    bool n_ge_3 = false;
                    bool n_le_2_noncorner = false;
                    bool nonhandoff = false;
                    bool corner = false;
                    bool direct_corner_present = false;
                    for (int slot = 0; slot < 3; ++slot) {
                        if (!q_source_is_legal(edge, edge.q_caps[slot])) continue;
                        const Card& card = cards[slot];
                        if (card.endpoint == kHeight) {
                            const bool immediate_tq =
                                immediate_tq_after_sibling_exhaust(edge, slot, card);
                            direct_corner_present = direct_corner_present || immediate_tq;
                            corner = corner || immediate_tq;
                            direct_certified = direct_certified || !immediate_tq;
                            two_exhaustion = two_exhaustion ||
                                bad_source_legal_after_sibling_exhaust(
                                    edge, edge.q_caps[slot], card);
                            continue;
                        }
                        const bool persists = bad_source_legal_after_live(
                            edge, edge.q_caps[slot], card);
                        if (!persists) {
                            nonhandoff = true;
                            continue;
                        }
                        live_handoff = true;
                        const int n_value =
                            edge.q_caps[slot] - edge.terminal_debts[card.color];
                        require(n_value >= 0, "live handoff has negative N");
                        if (n_value >= 3) {
                            n_ge_3 = true;
                        } else if (is_exact_live_tq_corner(edge, slot, cards, n_value)) {
                            corner = true;
                        } else {
                            n_le_2_noncorner = true;
                        }
                    }

                    std::string legacy_class;
                    if (two_exhaustion) {
                        legacy_class = "two_exhaustion";
                        add_class(stats.two_exhaustion, completion.count);
                        add_class(edge_stats.two_exhaustion, completion.count);
                    } else if (live_handoff) {
                        legacy_class = "live_bad_persistent";
                        add_class(stats.live_handoff, completion.count);
                        add_class(edge_stats.live_handoff, completion.count);
                    } else {
                        legacy_class = "obstruction";
                        add_class(stats.obstruction, completion.count);
                        add_class(edge_stats.obstruction, completion.count);
                    }
                    if (n_ge_3) {
                        ++stats.handoff_n_ge_3;
                        stats.handoff_n_ge_3_words += completion.count;
                        ++edge_stats.handoff_n_ge_3;
                        edge_stats.handoff_n_ge_3_words += completion.count;
                    }
                    if (live_handoff && !n_ge_3) {
                        ++stats.handoff_n_le_2;
                        stats.handoff_n_le_2_words += completion.count;
                        ++edge_stats.handoff_n_le_2;
                        edge_stats.handoff_n_le_2_words += completion.count;
                    }
                    if (direct_corner_present) {
                        ++stats.immediate_tq_corner;
                        stats.immediate_tq_corner_words += completion.count;
                        ++edge_stats.immediate_tq_corner;
                        edge_stats.immediate_tq_corner_words += completion.count;
                    }

                    const std::string refined = refined_classification(
                        direct_certified, n_ge_3, n_le_2_noncorner, nonhandoff, corner);
                    if (refined == "direct_exhaustion_certified_yes") {
                        add_class(stats.direct_certified, completion.count);
                        add_class(edge_stats.direct_certified, completion.count);
                    } else if (refined == "live_handoff_n_ge_3_certified_yes") {
                        add_class(stats.n_ge_3_certified, completion.count);
                        add_class(edge_stats.n_ge_3_certified, completion.count);
                    } else if (refined == "live_handoff_n_le_2_certified_yes") {
                        add_class(stats.n_le_2_certified, completion.count);
                        add_class(edge_stats.n_le_2_certified, completion.count);
                    } else if (refined == "live_nonhandoff_d2_reduction") {
                        add_class(stats.d2_reduction, completion.count);
                        add_class(edge_stats.d2_reduction, completion.count);
                    } else if (refined == "tq_low_energy_corner_only") {
                        add_class(stats.tq_corner_only, completion.count);
                        add_class(edge_stats.tq_corner_only, completion.count);
                    } else {
                        require(false, "feasible decoration was not classified");
                    }
                    if (!edge_stats.sample) {
                        record_sample(edge, cards, tails, residual, completion, legacy_class,
                                      stats, edge_stats);
                    }
                }
                if (stop) break;
            }
            if (stop) break;
        }
        if (stop) break;
    }
    stats.next_run_universe_complete = stats.raw_checked == stats.all_q_joint;
    stats.self_checks_passed = true;
    stats.elapsed_seconds = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - started).count();
    return stats;
}

std::string distribution_json(const std::map<int, std::uint64_t>& distribution) {
    std::ostringstream out;
    out << '{';
    bool first = true;
    for (const auto& item : distribution) {
        if (!first) out << ',';
        first = false;
        out << '\"' << item.first << "\":" << item.second;
    }
    out << '}';
    return out.str();
}

std::string class_json(const ClassStats& stats) {
    std::ostringstream out;
    out << "{\"decorations\":" << stats.decorations
        << ",\"residual_words\":" << stats.residual_words << '}';
    return out.str();
}

std::string cards_json(const std::array<Card, 3>& cards) {
    std::ostringstream out;
    out << '[';
    for (int slot = 0; slot < 3; ++slot) {
        if (slot) out << ',';
        out << '[' << cards[slot].color << ',' << cards[slot].endpoint << ']';
    }
    out << ']';
    return out.str();
}

std::string render_json(const Bridge& bridge, const RunStats& stats) {
    const bool complete = stats.next_run_universe_complete;
    std::ostringstream out;
    out << "{\n"
        << "  \"schema_version\": 1,\n"
        << "  \"model\": {\"colors\":4,\"height\":7,\"empty_columns\":2},\n"
        << "  \"coverage_scope\": \"first_exhaustion_tq_sibling_next_run_forks\",\n"
        << "  \"status\": \"" << (complete ? "NEXT_RUN_CENSUS_COMPLETE" : "INCOMPLETE") << "\",\n"
        << "  \"verified\": " << (complete ? "true" : "false") << ",\n"
        << "  \"self_checks_passed\": " << (stats.self_checks_passed ? "true" : "false") << ",\n"
        << "  \"limit_requested\": " << stats.limit_requested << ",\n"
        << "  \"limit_unit\": \"raw_all_q_next_run_decorations\",\n"
        << "  \"ordering\": {\"edges\":\"lexicographic (parent,terminal) canonical states\","
           "\"q_slots\":\"nondecreasing cap, physical multiplicity retained\","
           "\"cards\":\"slot0 outer; slot2 inner; color-major then endpoint-major\"},\n"
        << "  \"bridge\": {\n"
        << "    \"terminal_count\": " << bridge.terminal_count << ",\n"
        << "    \"labeled_candidates\": " << bridge.labeled_candidates << ",\n"
        << "    \"canonical_parents\": " << bridge.canonical_parent_count << ",\n"
        << "    \"canonical_edges\": " << bridge.canonical_edge_count << ",\n"
        << "    \"unique_source_parents\": " << bridge.unique_parent_count << ",\n"
        << "    \"sibling_parents\": " << bridge.sibling_parent_count << ",\n"
        << "    \"unique_source_edges\": " << bridge.unique_edge_count << ",\n"
        << "    \"sibling_edges\": " << bridge.sibling_edge_count << ",\n"
        << "    \"parent_legal_source_distribution\": "
        << distribution_json(bridge.parent_legal_distribution) << ",\n"
        << "    \"edge_legal_source_distribution\": "
        << distribution_json(bridge.edge_legal_distribution) << ",\n"
        << "    \"action_unique\": " << (bridge.action_unique ? "true" : "false") << ",\n"
        << "    \"all_edges_replay\": " << (bridge.all_edges_replay ? "true" : "false") << ",\n"
        << "    \"all_final_colors_isolated\": "
        << (bridge.all_final_colors_isolated ? "true" : "false") << "\n  },\n"
        << "  \"raw\": {\"legal_sibling_cards\":" << stats.legal_sibling_cards
        << ",\"legal_sibling_joint_decorations\":" << stats.legal_sibling_joint
        << ",\"all_q_joint_decorations\":" << stats.all_q_joint
        << ",\"checked\":" << stats.raw_checked << "},\n"
        << "  \"census\": {\n"
        << "    \"nonnegative_decorations\": " << stats.nonnegative << ",\n"
        << "    \"feasible_decorations\": " << stats.feasible << ",\n"
        << "    \"infeasible_decorations\": " << stats.infeasible << ",\n"
        << "    \"residual_words\": " << stats.residual_words << ",\n"
        << "    \"legacy\": {\"two_exhaustion\":" << class_json(stats.two_exhaustion)
        << ",\"live_bad_persistent\":" << class_json(stats.live_handoff)
        << ",\"obstruction\":" << class_json(stats.obstruction) << "},\n"
        << "    \"refined\": {"
        << "\"direct_certified\":" << class_json(stats.direct_certified) << ','
        << "\"n_ge_3_certified\":" << class_json(stats.n_ge_3_certified) << ','
        << "\"n_le_2_certified\":" << class_json(stats.n_le_2_certified) << ','
        << "\"d2_reduction\":" << class_json(stats.d2_reduction) << ','
        << "\"tq_corner_only\":" << class_json(stats.tq_corner_only) << "},\n"
        << "    \"property_counts\": {"
        << "\"handoff_n_ge_3_present\":" << stats.handoff_n_ge_3 << ','
        << "\"handoff_n_ge_3_present_words\":" << stats.handoff_n_ge_3_words << ','
        << "\"handoff_n_le_2_present_after_n_ge_3_precedence\":" << stats.handoff_n_le_2 << ','
        << "\"handoff_n_le_2_present_words\":" << stats.handoff_n_le_2_words << ','
        << "\"direct_immediate_tq_corner_present\":" << stats.immediate_tq_corner << ','
        << "\"direct_immediate_tq_corner_present_words\":" << stats.immediate_tq_corner_words << "},\n"
        << "    \"direct_tq_corner_structure\": {"
        << "\"cards\":" << stats.immediate_tq_corner_card_count << ','
        << "\"edges\":" << stats.immediate_tq_corner_edge_count << ','
        << "\"parents\":" << stats.immediate_tq_corner_parent_count << ','
        << "\"m_distribution\":" << distribution_json(stats.immediate_tq_corner_m_distribution)
        << "}\n  },\n"
        << "  \"next_run_universe_complete\": " << (complete ? "true" : "false") << ",\n"
        << "  \"full_residual_word_coverage\": false,\n"
        << "  \"entry_family_eliminated\": false,\n"
        << "  \"full_layout_coverage\": false,\n"
        << "  \"per_edge\": [\n";
    for (std::size_t index = 0; index < bridge.edges.size(); ++index) {
        const Edge& edge = bridge.edges[index];
        const EdgeStats& row = stats.per_edge[index];
        out << "    {\"edge_id\":\"exhaust-sibling-e" << index << "\","
            << "\"parent\":" << state_json(edge.parent) << ','
            << "\"terminal\":" << state_json(edge.terminal) << ','
            << "\"bad_action\":[" << edge.bad.old_color << ',' << edge.bad.old_cap
            << ',' << edge.bad.final_color << "],"
            << "\"q_color\":" << edge.q_color << ','
            << "\"q_caps\":" << array_json(edge.q_caps) << ','
            << "\"old_bad_equals_q\":" << (edge.old_bad_equals_q ? "true" : "false") << ','
            << "\"legal_source_count\":" << edge.legal_source_count << ','
            << "\"raw_expected\":" << edge.raw_expected << ','
            << "\"raw_checked\":" << row.raw_checked << ','
            << "\"nonnegative\":" << row.nonnegative << ','
            << "\"feasible\":" << row.feasible << ','
            << "\"infeasible\":" << row.infeasible << ','
            << "\"residual_words\":" << row.residual_words << ','
            << "\"legacy\":{\"two_exhaustion\":" << class_json(row.two_exhaustion)
            << ",\"live_bad_persistent\":" << class_json(row.live_handoff)
            << ",\"obstruction\":" << class_json(row.obstruction) << "},"
            << "\"refined\":{"
            << "\"direct_certified\":" << class_json(row.direct_certified) << ','
            << "\"n_ge_3_certified\":" << class_json(row.n_ge_3_certified) << ','
            << "\"n_le_2_certified\":" << class_json(row.n_le_2_certified) << ','
            << "\"d2_reduction\":" << class_json(row.d2_reduction) << ','
            << "\"tq_corner_only\":" << class_json(row.tq_corner_only) << "},"
            << "\"sample_id\":";
        if (row.sample) out << '\"' << stats.samples[*row.sample].id << '\"';
        else out << "null";
        out << '}' << (index + 1 == bridge.edges.size() ? "\n" : ",\n");
    }
    out << "  ],\n  \"replay_samples\": [\n";
    for (std::size_t index = 0; index < stats.samples.size(); ++index) {
        const Sample& sample = stats.samples[index];
        const Edge& edge = bridge.edges[sample.edge];
        out << "    {\"sample_id\":\"" << sample.id << "\","
            << "\"edge_id\":\"exhaust-sibling-e" << sample.edge << "\","
            << "\"feasible\":true,"
            << "\"classification\":\"" << sample.classification << "\","
            << "\"bad_action\":[" << edge.bad.old_color << ',' << edge.bad.old_cap
            << ',' << edge.bad.final_color << "],"
            << "\"q_color\":" << edge.q_color << ','
            << "\"q_caps\":" << array_json(edge.q_caps) << ','
            << "\"cards\":" << cards_json(sample.cards) << ','
            << "\"free_tail_lengths\":" << array_json(sample.free_tail_lengths) << ','
            << "\"residual_after_forced\":" << array_json(sample.residual_after_forced) << ','
            << "\"completion_count\":" << sample.completion_count << ','
            << "\"hidden_words_bottom_to_top\":[";
        for (int column = 0; column < 4; ++column) {
            if (column) out << ',';
            out << vector_json(sample.hidden_words[column]);
        }
        out << "]}" << (index + 1 == stats.samples.size() ? "\n" : ",\n");
    }
    out << "  ],\n  \"hall_regression\": {"
        << "\"residual_counts\":[0,5,0,0],"
        << "\"tail_lengths\":[3,2,0],"
        << "\"forbidden_colors\":[1,2,null],"
        << "\"nonnegative\":true,\"feasible\":false},\n"
        << "  \"checked_prefix\": [";
    for (std::size_t index = 0; index < stats.checked_prefix.size(); ++index) {
        if (index) out << ',';
        out << "{\"edge_id\":\"exhaust-sibling-e" << stats.checked_prefix[index].edge
            << "\",\"cards\":" << cards_json(stats.checked_prefix[index].cards) << '}';
    }
    out << "],\n  \"elapsed_seconds\": " << stats.elapsed_seconds << "\n}\n";
    return out.str();
}

std::string render_markdown(const Bridge& bridge, const RunStats& stats) {
    std::ostringstream out;
    out << "# c=4, h=7 first-exhaustion Tq sibling next-run census\n\n"
        << "- Status: **" << (stats.next_run_universe_complete
            ? "NEXT_RUN_CENSUS_COMPLETE" : "INCOMPLETE") << "**.\n"
        << "- Scope: committed next runs only; this is not full residual-word or layout coverage.\n"
        << "- Tq terminals / canonical bridge parents / edges: " << bridge.terminal_count
        << " / " << bridge.canonical_parent_count << " / " << bridge.canonical_edge_count << ".\n"
        << "- Sibling parents / edges: " << bridge.sibling_parent_count << " / "
        << bridge.sibling_edge_count << ".\n"
        << "- Raw all-q decorations checked: " << stats.raw_checked << " / "
        << stats.all_q_joint << ".\n"
        << "- Nonnegative / Hall-feasible decorations: " << stats.nonnegative << " / "
        << stats.feasible << ".\n"
        << "- Represented labeled residual words: " << stats.residual_words << ".\n\n"
        << "## Legacy first-layer classification\n\n"
        << "| Class | Decorations | Residual words |\n|---|---:|---:|\n"
        << "| two exhaustions | " << stats.two_exhaustion.decorations << " | "
        << stats.two_exhaustion.residual_words << " |\n"
        << "| live bad handoff | " << stats.live_handoff.decorations << " | "
        << stats.live_handoff.residual_words << " |\n"
        << "| obstruction | " << stats.obstruction.decorations << " | "
        << stats.obstruction.residual_words << " |\n\n"
        << "The refined labels in `report.json` are mathematical reconnaissance.  "
           "D2/Tq labels are reductions, not global NO certificates.\n";
    return out.str();
}

void write_outputs(const Options& options, const Bridge& bridge, const RunStats& stats) {
    if (options.output_dir.empty()) return;
    std::filesystem::create_directories(options.output_dir);
    {
        std::ofstream file(options.output_dir / "report.json");
        if (!file) throw std::runtime_error("cannot write report.json");
        file << render_json(bridge, stats);
    }
    {
        std::ofstream file(options.output_dir / "summary.md");
        if (!file) throw std::runtime_error("cannot write summary.md");
        file << render_markdown(bridge, stats);
    }
}

void verify_structural_counts(const Bridge& bridge, const RunStats& stats) {
    require(stats.legal_sibling_cards == kExpectedLegalSiblingCards,
            "legal sibling card count mismatch");
    require(stats.legal_sibling_joint == kExpectedLegalSiblingJoint,
            "legal-sibling joint count mismatch");
    require(stats.all_q_joint == kExpectedAllQJoint,
            "all-q joint count mismatch");
    require(bridge.parent_legal_distribution ==
                std::map<int, std::uint64_t>{{2, 1}, {3, 12}, {4, 399}},
            "parent legal-source distribution mismatch");
    require(bridge.edge_legal_distribution ==
                std::map<int, std::uint64_t>{{2, 2}, {3, 14}, {4, 407}},
            "edge legal-source distribution mismatch");
    require(stats.immediate_tq_corner_card_count == 12,
            "jointly feasible direct Tq card count mismatch");
    require(stats.immediate_tq_corner_edge_count == 12,
            "jointly feasible direct Tq edge count mismatch");
    require(stats.immediate_tq_corner_parent_count == 10,
            "jointly feasible direct Tq parent count mismatch");
    require(stats.immediate_tq_corner_m_distribution ==
                std::map<int, std::uint64_t>{{0, 8}, {1, 4}},
            "direct Tq M distribution mismatch");

    const Counts hall_counts{{0, 5, 0, 0}};
    const std::array<int, 3> hall_tails{{3, 2, 0}};
    const std::array<Card, 3> hall_cards{{Card{1, 4}, Card{2, 5}, Card{0, 7}}};
    require(count_completions(hall_counts, hall_tails, hall_cards, false).count == 0,
            "Hall regression unexpectedly has a completion");
}

void verify_full_counts(const RunStats& stats) {
    if (!stats.next_run_universe_complete) return;
    require(stats.raw_checked == kExpectedAllQJoint, "full raw count mismatch");
    require(stats.nonnegative == kExpectedNonnegative, "nonnegative count mismatch");
    require(stats.feasible == kExpectedFeasible, "feasible count mismatch");
    require(stats.infeasible == kExpectedAllQJoint - kExpectedFeasible,
            "infeasible count mismatch");
    require(stats.residual_words == kExpectedResidualWords, "residual-word weight mismatch");
    require(stats.two_exhaustion.decorations == kExpectedTwoExhaustion &&
                stats.two_exhaustion.residual_words == kExpectedTwoExhaustionWords,
            "two-exhaustion class mismatch");
    require(stats.live_handoff.decorations == kExpectedLiveHandoff &&
                stats.live_handoff.residual_words == kExpectedLiveHandoffWords,
            "live-handoff class mismatch");
    require(stats.obstruction.decorations == kExpectedObstruction &&
                stats.obstruction.residual_words == kExpectedObstructionWords,
            "obstruction class mismatch");
    require(stats.direct_certified.decorations == kExpectedDirectCertified &&
                stats.direct_certified.residual_words == kExpectedDirectCertifiedWords,
            "refined direct-certified class mismatch");
    require(stats.n_ge_3_certified.decorations == kExpectedHandoffNGe3 &&
                stats.n_ge_3_certified.residual_words == kExpectedHandoffNGe3Words,
            "refined N>=3 class mismatch");
    require(stats.n_le_2_certified.decorations == kExpectedHandoffNLe2 &&
                stats.n_le_2_certified.residual_words == kExpectedHandoffNLe2Words,
            "refined N<=2 class mismatch");
    require(stats.d2_reduction.decorations == kExpectedD2Reduction &&
                stats.d2_reduction.residual_words == kExpectedD2ReductionWords,
            "refined D2-reduction class mismatch");
    require(stats.tq_corner_only.decorations == kExpectedTqCornerOnly &&
                stats.tq_corner_only.residual_words == kExpectedTqCornerOnlyWords,
            "refined Tq-corner class mismatch");
    require(stats.samples.size() == kExpectedSiblingEdges,
            "full census does not have one sample per edge");
}

} // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parse_options(argc, argv);
        const Bridge bridge = build_bridge();
        require(bridge.terminal_count == kExpectedTqTerminals, "Tq terminal count mismatch");
        require(bridge.labeled_candidates == kExpectedLabeledCandidates,
                "labeled candidate count mismatch");
        require(bridge.canonical_parent_count == kExpectedCanonicalParents,
                "canonical parent count mismatch");
        require(bridge.canonical_edge_count == kExpectedCanonicalEdges,
                "canonical edge count mismatch");
        require(bridge.unique_parent_count == kExpectedUniqueParents,
                "unique parent count mismatch");
        require(bridge.sibling_parent_count == kExpectedSiblingParents,
                "sibling parent count mismatch");
        require(bridge.unique_edge_count == kExpectedUniqueEdges,
                "unique edge count mismatch");
        require(bridge.sibling_edge_count == kExpectedSiblingEdges,
                "sibling edge count mismatch");
        require(bridge.action_unique && bridge.all_edges_replay &&
                    bridge.all_final_colors_isolated,
                "bridge replay checks failed");

        std::uint64_t effective_limit = options.limit;
        if (options.self_test && effective_limit == 0) effective_limit = 64;
        // A limit covering the whole finite universe is an ordinary full run.
        // Normalizing it to zero avoids retaining every decoration in the
        // bounded-run checked-prefix audit trail.
        if (effective_limit >= kExpectedAllQJoint) effective_limit = 0;
        RunStats stats = run_census(bridge, effective_limit);
        verify_structural_counts(bridge, stats);
        verify_full_counts(stats);
        write_outputs(options, bridge, stats);
        std::cout << "status="
                  << (stats.next_run_universe_complete
                          ? "NEXT_RUN_CENSUS_COMPLETE" : "INCOMPLETE")
                  << " raw=" << stats.raw_checked << '/' << stats.all_q_joint
                  << " feasible=" << stats.feasible
                  << " residual_words=" << stats.residual_words << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
