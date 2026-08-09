#include "water_sort/border_oracle.hpp"
#include "water_sort/certificate.hpp"
#include "water_sort/instance.hpp"

#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

namespace {

struct Options {
    std::filesystem::path seed_dir;
    std::filesystem::path out = "out/neighborhood";
    std::uint32_t empty_columns = 3;
    std::uint32_t shard = 0;
    std::uint32_t shards = 1;
    std::uint32_t certificate_limit = 10;
};

Options parse_options(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        const auto value = [&]() -> std::string {
            if (i + 1 >= argc) throw std::runtime_error("missing value for " + argument);
            return argv[++i];
        };
        if (argument == "--seed-dir") options.seed_dir = value();
        else if (argument == "--out") options.out = value();
        else if (argument == "--empty") {
            options.empty_columns = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--shard") {
            options.shard = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--shards") {
            options.shards = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--certificate-limit") {
            options.certificate_limit = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--help") {
            std::cout << "water-neighborhood --seed-dir DIR [--empty K] "
                         "[--shard I --shards N] [--certificate-limit N] [--out DIR]\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown argument: " + argument);
        }
    }
    if (options.seed_dir.empty() || options.shards == 0 || options.shard >= options.shards) {
        throw std::runtime_error("invalid neighborhood options");
    }
    return options;
}

std::string hex_id(std::uint64_t value) {
    std::ostringstream output;
    output << std::hex << std::setfill('0') << std::setw(16) << value;
    return output.str();
}

std::uint64_t shard_hash(std::uint64_t value) {
    value ^= value >> 30U;
    value *= 0xbf58476d1ce4e5b9ULL;
    value ^= value >> 27U;
    value *= 0x94d049bb133111ebULL;
    return value ^ (value >> 31U);
}

std::vector<std::filesystem::path> seed_paths(const std::filesystem::path& directory) {
    std::vector<std::filesystem::path> paths;
    for (const auto& entry : std::filesystem::directory_iterator(directory)) {
        if (entry.is_regular_file() && entry.path().extension() == ".txt") {
            paths.push_back(entry.path());
        }
    }
    std::sort(paths.begin(), paths.end());
    if (paths.empty()) throw std::runtime_error("seed directory contains no .txt instances");
    return paths;
}

} // namespace

int main(int argc, char** argv) try {
    const auto options = parse_options(argc, argv);
    std::filesystem::create_directories(options.out);
    std::ofstream rows(options.out / "results.tsv");
    if (!rows) throw std::runtime_error("cannot create results.tsv");
    rows << "class_id\tresult\tempty\tborders\toracle_states\tterminals\tsignatures\tcanonical\n";

    std::unordered_set<std::string> seen;
    std::uint64_t generated = 0;
    std::uint64_t assigned = 0;
    std::uint64_t solvable = 0;
    std::uint64_t unsolvable = 0;
    std::uint32_t certificates = 0;

    auto consider = [&](water_sort::Instance candidate) {
        ++generated;
        candidate.empty_columns = options.empty_columns;
        const auto fingerprint = water_sort::canonical_fingerprint(candidate);
        if (shard_hash(fingerprint) % options.shards != options.shard) return;
        ++assigned;
        const auto encoding = water_sort::canonical_encoding(candidate);
        if (!seen.insert(encoding).second) return;
        candidate = water_sort::canonicalize_instance(candidate);

        const water_sort::BorderOracle oracle(candidate);
        const auto count = oracle.count_solutions(1);
        const bool is_solvable = count.solutions != 0;
        water_sort::OracleResult solve;
        water_sort::AnalysisResult analysis;
        if (!is_solvable) {
            solve = oracle.solve();
            analysis = oracle.analyze();
        }
        std::uint32_t borders = 0;
        for (const auto& column : candidate.columns) {
            for (std::size_t i = 1; i < column.size(); ++i) {
                if (column[i - 1] != column[i]) ++borders;
            }
        }
        std::ostringstream signatures;
        bool first = true;
        for (const auto& [signature, count] : analysis.signatures) {
            if (!first) signatures << ';';
            first = false;
            signatures << signature.compact() << ':' << count;
        }
        const auto id = hex_id(fingerprint);
        rows << id << '\t' << (is_solvable ? "YES" : "NO") << '\t'
             << options.empty_columns << '\t' << borders << '\t'
             << (is_solvable ? count.states_evaluated : solve.states_visited)
             << '\t' << analysis.terminal_states << '\t' << signatures.str() << '\t'
             << encoding << '\n';
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

    for (const auto& path : seed_paths(options.seed_dir)) {
        const auto seed = water_sort::read_instance(path);
        consider(seed);
        const auto cell_count = seed.columns.size() * seed.height;
        for (std::size_t first = 0; first < cell_count; ++first) {
            for (std::size_t second = first + 1; second < cell_count; ++second) {
                const auto first_column = first / seed.height;
                const auto first_position = first % seed.height;
                const auto second_column = second / seed.height;
                const auto second_position = second % seed.height;
                if (seed.columns[first_column][first_position] ==
                    seed.columns[second_column][second_position]) {
                    continue;
                }
                auto candidate = seed;
                std::swap(candidate.columns[first_column][first_position],
                          candidate.columns[second_column][second_position]);
                consider(std::move(candidate));
            }
        }
    }

    std::ofstream report(options.out / "report.json");
    report << "{\n"
           << "  \"empty_columns\": " << options.empty_columns << ",\n"
           << "  \"shard\": " << options.shard << ",\n"
           << "  \"shards\": " << options.shards << ",\n"
           << "  \"generated\": " << generated << ",\n"
           << "  \"assigned\": " << assigned << ",\n"
           << "  \"unique\": " << seen.size() << ",\n"
           << "  \"solvable\": " << solvable << ",\n"
           << "  \"unsolvable\": " << unsolvable << ",\n"
           << "  \"certificates\": " << certificates << "\n"
           << "}\n";
    std::cout << "unique=" << seen.size() << " solvable=" << solvable
              << " unsolvable=" << unsolvable << '\n';
    return 0;
} catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
}
