#include "water_sort/border_oracle.hpp"
#include "water_sort/certificate.hpp"
#include "water_sort/instance.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

namespace {

struct Options {
    std::filesystem::path input;
    std::filesystem::path out = "out/skeleton";
    std::uint32_t height = 0;
    std::uint32_t empty_columns = 2;
    std::uint32_t shard = 0;
    std::uint32_t shards = 1;
    std::uint64_t candidate_limit = 10000;
    std::uint32_t certificate_limit = 10;
};

struct Run {
    std::size_t column = 0;
    water_sort::Color color = 0;
    std::uint32_t hint = 0;
};

Options parse_options(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        const auto value = [&]() -> std::string {
            if (i + 1 >= argc) throw std::runtime_error("missing value for " + argument);
            return argv[++i];
        };
        if (argument == "--input") options.input = value();
        else if (argument == "--out") options.out = value();
        else if (argument == "--height") {
            options.height = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--empty") {
            options.empty_columns = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--shard") {
            options.shard = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--shards") {
            options.shards = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--candidate-limit") {
            options.candidate_limit = std::stoull(value());
        } else if (argument == "--certificate-limit") {
            options.certificate_limit = static_cast<std::uint32_t>(std::stoul(value()));
        } else if (argument == "--help") {
            std::cout << "water-skeleton --input INSTANCE [--height H] [--empty K] "
                         "[--shard I --shards N] [--candidate-limit N] "
                         "[--certificate-limit N] [--out DIR]\n";
            std::exit(0);
        } else {
            throw std::runtime_error("unknown argument: " + argument);
        }
    }
    if (options.input.empty() || options.shards == 0 || options.shard >= options.shards ||
        options.candidate_limit == 0) {
        throw std::runtime_error("invalid skeleton options");
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

std::vector<Run> extract_runs(const water_sort::Instance& instance) {
    std::vector<Run> runs;
    for (std::size_t column = 0; column < instance.columns.size(); ++column) {
        const auto& values = instance.columns[column];
        std::size_t start = 0;
        for (std::size_t position = 1; position <= values.size(); ++position) {
            if (position != values.size() && values[position] == values[position - 1]) continue;
            runs.push_back(Run{column, values[start],
                               static_cast<std::uint32_t>(position - start)});
            start = position;
        }
    }
    return runs;
}

std::vector<std::uint32_t> values_near(std::uint32_t hint, std::uint32_t maximum) {
    hint = std::max<std::uint32_t>(1, std::min(hint, maximum));
    std::vector<std::uint32_t> values;
    values.reserve(maximum);
    values.push_back(hint);
    for (std::uint32_t delta = 1; values.size() < maximum; ++delta) {
        if (hint > delta) values.push_back(hint - delta);
        if (hint + delta <= maximum) values.push_back(hint + delta);
    }
    return values;
}

} // namespace

int main(int argc, char** argv) try {
    auto options = parse_options(argc, argv);
    const auto skeleton = water_sort::read_instance(options.input);
    if (options.height == 0) options.height = skeleton.height;
    const auto runs = extract_runs(skeleton);

    std::vector<std::uint32_t> remaining_column(skeleton.columns.size(), options.height);
    std::vector<std::uint32_t> remaining_color(skeleton.color_count, options.height);
    std::vector<std::uint32_t> runs_in_column(skeleton.columns.size(), 0);
    std::vector<std::uint32_t> runs_of_color(skeleton.color_count, 0);
    for (const auto& run : runs) {
        ++runs_in_column[run.column];
        ++runs_of_color[run.color];
    }
    if (std::any_of(runs_in_column.begin(), runs_in_column.end(),
                    [&](std::uint32_t count) { return count > options.height; }) ||
        std::any_of(runs_of_color.begin(), runs_of_color.end(),
                    [&](std::uint32_t count) { return count > options.height; })) {
        throw std::runtime_error("target height is too small for this run skeleton");
    }

    std::filesystem::create_directories(options.out);
    std::ofstream rows(options.out / "results.tsv");
    if (!rows) throw std::runtime_error("cannot create results.tsv");
    rows << "class_id\tresult\theight\tempty\tborders\toracle_states\tterminals\t"
            "signatures\tlengths\tcanonical\n";

    std::vector<std::uint32_t> lengths(runs.size(), 0);
    std::unordered_set<std::string> seen;
    std::uint64_t feasible = 0;
    std::uint64_t assigned = 0;
    std::uint64_t solvable = 0;
    std::uint64_t unsolvable = 0;
    std::uint32_t certificates = 0;
    bool stopped_early = false;

    const auto classify = [&]() {
        ++feasible;
        water_sort::Instance candidate;
        candidate.height = options.height;
        candidate.color_count = skeleton.color_count;
        candidate.empty_columns = options.empty_columns;
        candidate.columns.resize(skeleton.columns.size());
        for (std::size_t i = 0; i < runs.size(); ++i) {
            auto& column = candidate.columns[runs[i].column];
            column.insert(column.end(), lengths[i], runs[i].color);
        }
        candidate.validate();
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
        std::ostringstream signatures;
        bool first = true;
        for (const auto& [signature, signature_count] : analysis.signatures) {
            if (!first) signatures << ';';
            first = false;
            signatures << signature.compact() << ':' << signature_count;
        }
        std::ostringstream length_text;
        for (std::size_t i = 0; i < lengths.size(); ++i) {
            if (i != 0) length_text << ',';
            length_text << lengths[i];
        }
        const auto id = hex_id(fingerprint);
        rows << id << '\t' << (is_solvable ? "YES" : "NO") << '\t'
             << options.height << '\t' << options.empty_columns << '\t'
             << runs.size() - skeleton.columns.size() << '\t'
             << (is_solvable ? count.states_evaluated : solve.states_visited) << '\t'
             << analysis.terminal_states << '\t' << signatures.str() << '\t'
             << length_text.str() << '\t' << encoding << '\n';
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

    std::function<void(std::size_t)> enumerate = [&](std::size_t index) {
        if (seen.size() >= options.candidate_limit) {
            stopped_early = true;
            return;
        }
        if (index == runs.size()) {
            const bool complete =
                std::all_of(remaining_column.begin(), remaining_column.end(),
                            [](std::uint32_t value) { return value == 0; }) &&
                std::all_of(remaining_color.begin(), remaining_color.end(),
                            [](std::uint32_t value) { return value == 0; });
            if (complete) classify();
            return;
        }

        const auto& run = runs[index];
        const auto column = run.column;
        const auto color = static_cast<std::size_t>(run.color);
        if (remaining_column[column] < runs_in_column[column] ||
            remaining_color[color] < runs_of_color[color]) {
            return;
        }
        const auto maximum = std::min(
            remaining_column[column] - (runs_in_column[column] - 1U),
            remaining_color[color] - (runs_of_color[color] - 1U));
        const auto scaled_hint = static_cast<std::uint32_t>(std::max<long>(
            1, std::lround(static_cast<double>(run.hint) * options.height /
                           skeleton.height)));
        for (const auto value : values_near(scaled_hint, maximum)) {
            lengths[index] = value;
            remaining_column[column] -= value;
            remaining_color[color] -= value;
            --runs_in_column[column];
            --runs_of_color[color];
            if (remaining_column[column] >= runs_in_column[column] &&
                remaining_color[color] >= runs_of_color[color]) {
                enumerate(index + 1);
            }
            ++runs_in_column[column];
            ++runs_of_color[color];
            remaining_column[column] += value;
            remaining_color[color] += value;
            if (stopped_early) return;
        }
    };
    enumerate(0);

    std::ofstream report(options.out / "report.json");
    report << "{\n"
           << "  \"height\": " << options.height << ",\n"
           << "  \"empty_columns\": " << options.empty_columns << ",\n"
           << "  \"runs\": " << runs.size() << ",\n"
           << "  \"borders\": " << runs.size() - skeleton.columns.size() << ",\n"
           << "  \"shard\": " << options.shard << ",\n"
           << "  \"shards\": " << options.shards << ",\n"
           << "  \"candidate_limit\": " << options.candidate_limit << ",\n"
           << "  \"feasible_examined\": " << feasible << ",\n"
           << "  \"assigned\": " << assigned << ",\n"
           << "  \"unique\": " << seen.size() << ",\n"
           << "  \"solvable\": " << solvable << ",\n"
           << "  \"unsolvable\": " << unsolvable << ",\n"
           << "  \"stopped_early\": " << (stopped_early ? "true" : "false") << ",\n"
           << "  \"certificates\": " << certificates << "\n"
           << "}\n";
    std::cout << "unique=" << seen.size() << " solvable=" << solvable
              << " unsolvable=" << unsolvable << '\n';
    return 0;
} catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
}
