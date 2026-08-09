#include "water_sort/border_oracle.hpp"
#include "water_sort/certificate.hpp"
#include "water_sort/instance.hpp"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct Options {
    std::filesystem::path out = "out/universe";
    std::uint32_t height = 0;
    std::uint32_t colors = 5;
    std::uint32_t empty_columns = 2;
    std::uint32_t shard = 0;
    std::uint32_t shards = 1;
    std::uint32_t shard_columns = 2;
    std::uint64_t candidate_limit = 0;
    std::uint32_t certificate_limit = 10;
    std::optional<std::uint64_t> expect_classes;
    std::optional<std::uint64_t> expect_unsolvable;
};

Options parse_options(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        const auto value = [&]() -> std::string {
            if (i + 1 >= argc) throw std::runtime_error("missing value for " + argument);
            return argv[++i];
        };
        if (argument == "--out") options.out = value();
        else if (argument == "--height") {
            options.height = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--colors") {
            options.colors = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--empty") {
            options.empty_columns = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--shard") {
            options.shard = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--shards") {
            options.shards = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--shard-columns") {
            options.shard_columns = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--candidate-limit") {
            options.candidate_limit = std::stoull(value());
        } else if (argument == "--certificate-limit") {
            options.certificate_limit = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--expect-classes") {
            options.expect_classes = std::stoull(value());
        } else if (argument == "--expect-unsolvable") {
            options.expect_unsolvable = std::stoull(value());
        } else if (argument == "--help") {
            std::cout << "water-universe --height H [--colors N] [--empty K] "
                         "[--shard I --shards N] [--shard-columns N] "
                         "[--candidate-limit N] [--certificate-limit N] [--out DIR]\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown argument: " + argument);
        }
    }
    if (options.height == 0 || options.colors == 0 || options.colors > 8 ||
        options.shards == 0 || options.shard >= options.shards ||
        options.shard_columns == 0) {
        throw std::runtime_error("invalid universe options");
    }
    options.shard_columns = std::min(options.shard_columns, options.colors);
    if (options.shards != 1 && (options.expect_classes || options.expect_unsolvable)) {
        throw std::runtime_error("expectations require a single unsharded scan");
    }
    return options;
}

std::string hex_id(std::uint64_t value) {
    std::ostringstream output;
    output << std::hex << std::setfill('0') << std::setw(16) << value;
    return output.str();
}

std::uint64_t hash_prefix(const std::vector<water_sort::Color>& cells,
                          std::size_t length) {
    std::uint64_t hash = 1469598103934665603ULL;
    for (std::size_t i = 0; i < length; ++i) {
        hash ^= static_cast<std::uint64_t>(cells[i]) + 1U;
        hash *= 1099511628211ULL;
    }
    hash ^= length;
    hash *= 1099511628211ULL;
    return hash;
}

std::uint64_t hash_encoding(const std::string& encoding) {
    std::uint64_t hash = 1469598103934665603ULL;
    for (const unsigned char byte : encoding) {
        hash ^= byte;
        hash *= 1099511628211ULL;
    }
    return hash;
}

std::string literal_encoding(const water_sort::Instance& instance) {
    std::ostringstream output;
    output << instance.height << ':' << instance.color_count << ':'
           << instance.empty_columns << ':';
    for (std::size_t column = 0; column < instance.columns.size(); ++column) {
        if (column != 0) output << '|';
        for (const auto color : instance.columns[column]) {
            output << water_sort::color_to_char(color);
        }
    }
    return output.str();
}

std::uint32_t border_count(const water_sort::Instance& instance) {
    std::uint32_t count = 0;
    for (const auto& column : instance.columns) {
        for (std::size_t i = 1; i < column.size(); ++i) {
            if (column[i] != column[i - 1]) ++count;
        }
    }
    return count;
}

} // namespace

int main(int argc, char** argv) try {
    const auto options = parse_options(argc, argv);
    std::filesystem::create_directories(options.out);
    std::ofstream rows(options.out / "results.tsv");
    if (!rows) throw std::runtime_error("cannot create results.tsv");
    rows << "class_id\tresult\theight\tcolors\tempty\tborders\toracle_states\t"
            "terminals\tsignatures\tcanonical\n";

    const auto cell_count = static_cast<std::size_t>(options.height) * options.colors;
    const auto shard_depth = static_cast<std::size_t>(options.height) * options.shard_columns;
    std::vector<water_sort::Color> cells(cell_count, 0);
    std::vector<std::uint32_t> remaining(options.colors, options.height);
    std::uint64_t representations = 0;
    std::uint64_t canonical_classes = 0;
    std::uint64_t solvable = 0;
    std::uint64_t unsolvable = 0;
    std::uint32_t certificates = 0;
    bool stopped_early = false;

    const auto classify = [&]() {
        ++representations;
        water_sort::Instance candidate;
        candidate.height = options.height;
        candidate.color_count = options.colors;
        candidate.empty_columns = options.empty_columns;
        candidate.columns.resize(options.colors);
        for (std::size_t column = 0; column < options.colors; ++column) {
            const auto first = cells.begin() +
                static_cast<std::ptrdiff_t>(column * options.height);
            candidate.columns[column].assign(first, first + options.height);
        }
        const auto literal = literal_encoding(candidate);
        const auto canonical = water_sort::canonical_encoding(candidate);
        if (literal != canonical) return;
        ++canonical_classes;

        const water_sort::BorderOracle oracle(candidate);
        const auto count = oracle.count_solutions(1);
        const bool is_solvable = count.solutions != 0;
        water_sort::OracleResult solve;
        water_sort::AnalysisResult analysis;
        if (!is_solvable) {
            solve = oracle.solve();
            analysis = oracle.analyze();
        }
        std::ostringstream signatures;
        bool first = true;
        for (const auto& [signature, signature_count] : analysis.signatures) {
            if (!first) signatures << ';';
            first = false;
            signatures << signature.compact() << ':' << signature_count;
        }
        const auto fingerprint = hash_encoding(canonical);
        const auto id = hex_id(fingerprint);
        rows << id << '\t' << (is_solvable ? "YES" : "NO") << '\t'
             << options.height << '\t' << options.colors << '\t'
             << options.empty_columns << '\t' << border_count(candidate) << '\t'
             << (is_solvable ? count.states_evaluated : solve.states_visited) << '\t'
             << analysis.terminal_states << '\t' << signatures.str() << '\t'
             << canonical << '\n';
        if (is_solvable) {
            ++solvable;
        } else {
            ++unsolvable;
            if (certificates < options.certificate_limit) {
                const auto base = options.out / ("no-" + id);
                water_sort::write_instance(candidate, base.string() + ".txt");
                water_sort::write_no_certificate(candidate, oracle.state_count(),
                                                 solve.reachable_bits,
                                                 base.string() + ".wscert");
                ++certificates;
            }
        }
    };

    std::function<void(std::size_t, int)> enumerate =
        [&](std::size_t position, int max_used) {
            if (options.candidate_limit != 0 &&
                canonical_classes >= options.candidate_limit) {
                stopped_early = true;
                return;
            }
            if (position == cell_count) {
                if (max_used + 1 == static_cast<int>(options.colors) &&
                    std::all_of(remaining.begin(), remaining.end(),
                                [](std::uint32_t value) { return value == 0; })) {
                    classify();
                }
                return;
            }
            if (options.shards > 1 && position == shard_depth &&
                hash_prefix(cells, shard_depth) % options.shards != options.shard) {
                return;
            }

            const auto column = position / options.height;
            const auto offset = position % options.height;
            int column_relation = 1;
            if (column != 0) {
                column_relation = 0;
                const auto current_start = column * options.height;
                const auto previous_start = current_start - options.height;
                for (std::size_t i = 0; i < offset; ++i) {
                    if (cells[current_start + i] < cells[previous_start + i]) return;
                    if (cells[current_start + i] > cells[previous_start + i]) {
                        column_relation = 1;
                        break;
                    }
                }
            }

            const auto maximum = std::min<std::uint32_t>(
                options.colors - 1U, static_cast<std::uint32_t>(max_used + 1));
            for (std::uint32_t color = 0; color <= maximum; ++color) {
                if (remaining[color] == 0) continue;
                if (column != 0 && column_relation == 0 &&
                    color < cells[position - options.height]) {
                    continue;
                }
                cells[position] = static_cast<water_sort::Color>(color);
                --remaining[color];
                enumerate(position + 1, std::max(max_used, static_cast<int>(color)));
                ++remaining[color];
                if (stopped_early) return;
            }
        };
    enumerate(0, -1);

    std::ofstream report(options.out / "report.json");
    report << "{\n"
           << "  \"height\": " << options.height << ",\n"
           << "  \"colors\": " << options.colors << ",\n"
           << "  \"empty_columns\": " << options.empty_columns << ",\n"
           << "  \"shard\": " << options.shard << ",\n"
           << "  \"shards\": " << options.shards << ",\n"
           << "  \"representations\": " << representations << ",\n"
           << "  \"canonical_classes\": " << canonical_classes << ",\n"
           << "  \"solvable\": " << solvable << ",\n"
           << "  \"unsolvable\": " << unsolvable << ",\n"
           << "  \"stopped_early\": " << (stopped_early ? "true" : "false") << ",\n"
           << "  \"certificates\": " << certificates << "\n"
           << "}\n";
    report.close();

    if (options.expect_classes && canonical_classes != *options.expect_classes) {
        throw std::runtime_error("expected " + std::to_string(*options.expect_classes) +
                                 " classes, got " + std::to_string(canonical_classes));
    }
    if (options.expect_unsolvable && unsolvable != *options.expect_unsolvable) {
        throw std::runtime_error("expected " + std::to_string(*options.expect_unsolvable) +
                                 " unsolvable classes, got " + std::to_string(unsolvable));
    }
    std::cout << "representations=" << representations
              << " canonical_classes=" << canonical_classes
              << " solvable=" << solvable << " unsolvable=" << unsolvable << '\n';
    return 0;
} catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
}
