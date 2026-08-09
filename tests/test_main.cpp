#include "water_sort/border_oracle.hpp"
#include "water_sort/certificate.hpp"
#include "water_sort/instance.hpp"
#include "water_sort/water_solver.hpp"

#include <cstdint>
#include <algorithm>
#include <filesystem>
#include <functional>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

water_sort::Instance make_instance(std::uint32_t height,
                                   std::uint32_t colors,
                                   std::uint32_t empty,
                                   const std::vector<std::vector<water_sort::Color>>& columns) {
    water_sort::Instance instance{height, colors, empty, columns};
    instance.validate();
    return instance;
}

water_sort::Instance ito_h3_k2_n9() {
    // Figure 10(a), Ito et al. Values are converted from 1..9 to 0..8.
    return make_instance(3, 9, 2, {
        {6, 3, 0}, {7, 3, 0}, {8, 3, 0},
        {6, 4, 1}, {7, 4, 1}, {8, 4, 1},
        {6, 5, 2}, {7, 5, 2}, {8, 5, 2},
    });
}

water_sort::Instance add_completed_color(water_sort::Instance instance) {
    const auto new_color = static_cast<water_sort::Color>(instance.color_count);
    instance.columns.emplace_back(instance.height, new_color);
    ++instance.color_count;
    instance.validate();
    return instance;
}

std::uint64_t exhaustive_cross_check(std::uint32_t height, std::uint32_t colors) {
    std::vector<std::uint32_t> remaining(colors, height);
    std::vector<water_sort::Color> cells(height * colors);
    std::uint64_t checked = 0;
    std::function<void(std::size_t)> enumerate = [&](std::size_t position) {
        if (position == cells.size()) {
            std::vector<std::vector<water_sort::Color>> columns(colors);
            for (std::size_t column = 0; column < colors; ++column) {
                const auto first = cells.begin() + static_cast<std::ptrdiff_t>(column * height);
                columns[column].assign(first, first + height);
            }
            const auto instance = make_instance(height, colors, 2, columns);
            const auto border = water_sort::BorderOracle(instance).solve();
            const auto water = water_sort::solve_water_exact(instance, 2'000'000);
            require(water.status != water_sort::WaterSolveStatus::state_limit_reached,
                    "full Water BFS hit its state limit in a small exhaustive test");
            const bool water_yes = water.status == water_sort::WaterSolveStatus::solvable;
            require(border.solvable == water_yes,
                    "border oracle disagrees with full Water BFS for h=" +
                    std::to_string(height) + " n=" + std::to_string(colors));
            ++checked;
            return;
        }
        for (std::uint32_t color = 0; color < colors; ++color) {
            if (remaining[color] == 0) continue;
            --remaining[color];
            cells[position] = static_cast<water_sort::Color>(color);
            enumerate(position + 1);
            ++remaining[color];
        }
    };
    enumerate(0);
    return checked;
}

void run_tests() {
    {
        const auto solved = make_instance(2, 2, 2, {{0, 0}, {1, 1}});
        const auto border = water_sort::BorderOracle(solved).solve();
        const auto water = water_sort::solve_water_exact(solved);
        require(border.solvable && border.removal_columns.empty(), "solved oracle case failed");
        require(water.status == water_sort::WaterSolveStatus::solvable && water.states_visited == 1,
                "locked completed columns were not terminal");
    }
    {
        const auto no_instance = ito_h3_k2_n9();
        const water_sort::BorderOracle oracle(no_instance);
        const auto count = oracle.count_solutions(100);
        const auto result = oracle.solve();
        require(count.solutions == 0, "Ito Figure 10(a) unexpectedly has a border sequence");
        require(!result.solvable, "Ito Figure 10(a) unexpectedly solved");

        const auto certificate = std::filesystem::temp_directory_path() / "water-sort-test.wscert";
        water_sort::write_no_certificate(no_instance, oracle.state_count(),
                                         result.reachable_bits, certificate);
        const auto verification = water_sort::verify_no_certificate(no_instance, certificate);
        std::filesystem::remove(certificate);
        require(verification.valid && verification.marked_states > 0,
                "NO certificate verification failed");
    }

    {
        const auto corpus = std::filesystem::path(WSC_SOURCE_DIR) / "counterexamples";
        const std::vector<std::string> ids{"000", "004", "005", "006", "007"};
        for (const auto& id : ids) {
            const auto path = corpus / ("ce-" + id + ".txt");
            const auto certificate = corpus / ("ce-" + id + ".wscert");
            auto instance = water_sort::read_instance(path);
            const auto oracle = water_sort::BorderOracle(instance);
            require(!oracle.solve().solvable, "committed counterexample unexpectedly solved");
            require(water_sort::verify_no_certificate(instance, certificate).valid,
                    "committed counterexample certificate failed verification");
            instance.empty_columns = 3;
            require(water_sort::BorderOracle(instance).solve().solvable,
                    "committed counterexample did not solve with a third empty column");
        }

        auto original = water_sort::read_instance(corpus / "ce-000.txt");
        auto symmetric = original;
        std::reverse(symmetric.columns.begin(), symmetric.columns.end());
        for (auto& column : symmetric.columns) {
            for (auto& color : column) color = static_cast<water_sort::Color>(4 - color);
        }
        require(water_sort::canonical_encoding(original) ==
                    water_sort::canonical_encoding(symmetric),
                "canonicalization failed to remove color and column symmetries");

        const auto analysis = water_sort::BorderOracle(original).analyze();
        require(!analysis.solvable && analysis.reachable_states == 440 &&
                    analysis.terminal_states == 60 && analysis.min_terminal_depth == 4 &&
                    analysis.max_terminal_depth == 12,
                "unexpected analysis metrics for ce-000");
        require(analysis.signatures.size() == 1 &&
                    analysis.signatures.begin()->first.compact() == "a2-d2-h3-n3,3,3,3,3" &&
                    analysis.signatures.begin()->second == 60,
                "unexpected deadlock signature for ce-000");
    }

    {
        const auto experiments = std::filesystem::path(WSC_SOURCE_DIR) / "experiments";
        const auto minimum = water_sort::read_instance(experiments / "minimum-h5-ce-000.txt");
        std::vector<water_sort::Color> bottom_layer(minimum.color_count);
        std::iota(bottom_layer.begin(), bottom_layer.end(), water_sort::Color{0});
        std::uint32_t lifts = 0;
        do {
            auto lifted = minimum;
            ++lifted.height;
            for (std::size_t column = 0; column < lifted.columns.size(); ++column) {
                lifted.columns[column].insert(lifted.columns[column].begin(),
                                              bottom_layer[column]);
            }
            lifted.validate();
            require(!water_sort::BorderOracle(lifted).solve().solvable,
                    "balanced bottom-layer lift unexpectedly became solvable");
            ++lifts;
        } while (std::next_permutation(bottom_layer.begin(), bottom_layer.end()));
        require(lifts == 120, "unexpected number of balanced bottom-layer lifts");
    }

    {
        const auto experiments = std::filesystem::path(WSC_SOURCE_DIR) / "experiments";
        const std::vector<std::string> names{
            "k1-minimal-c2-h4", "k1-minimal-c3-h3", "k1-minimal-c4-h2"};
        for (const auto& name : names) {
            const auto instance = water_sort::read_instance(experiments / (name + ".txt"));
            require(!water_sort::BorderOracle(instance).solve().solvable,
                    "one-empty minimal obstruction unexpectedly solved");
            require(water_sort::verify_no_certificate(
                        instance, experiments / (name + ".wscert")).valid,
                    "one-empty minimal obstruction certificate failed verification");
            require(!water_sort::BorderOracle(add_completed_color(instance)).solve().solvable,
                    "adding an inert completed color unexpectedly solved a NO instance");
        }
    }

    std::uint64_t exhaustive_cases = 0;
    exhaustive_cases += exhaustive_cross_check(2, 2);
    exhaustive_cases += exhaustive_cross_check(2, 3);
    exhaustive_cases += exhaustive_cross_check(3, 2);
    exhaustive_cases += exhaustive_cross_check(3, 3);
    require(exhaustive_cases == 1796, "unexpected exhaustive test count");
    std::cout << "cross-checked " << exhaustive_cases
              << " small initial arrangements against full Water BFS\n";
}

} // namespace

int main() try {
    run_tests();
    std::cout << "all tests passed\n";
    return 0;
} catch (const std::exception& error) {
    std::cerr << "test failure: " << error.what() << '\n';
    return 1;
}
