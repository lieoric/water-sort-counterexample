#include "water_sort/border_oracle.hpp"
#include "water_sort/certificate.hpp"
#include "water_sort/instance.hpp"
#include "water_sort/water_solver.hpp"

#include <cstdint>
#include <filesystem>
#include <functional>
#include <iostream>
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
