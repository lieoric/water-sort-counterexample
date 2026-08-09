#include "water_sort/border_oracle.hpp"
#include "water_sort/certificate.hpp"
#include "water_sort/instance.hpp"

#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

void usage() {
    std::cerr << "Usage: water-oracle --input INSTANCE [--certificate FILE] [--count CAP]\n";
}

} // namespace

int main(int argc, char** argv) try {
    std::filesystem::path input_path;
    std::filesystem::path certificate_path;
    std::uint64_t count_cap = 0;
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        if (argument == "--input" && i + 1 < argc) {
            input_path = argv[++i];
        } else if (argument == "--certificate" && i + 1 < argc) {
            certificate_path = argv[++i];
        } else if (argument == "--count" && i + 1 < argc) {
            count_cap = std::stoull(argv[++i]);
        } else if (argument == "--help") {
            usage();
            return 0;
        } else {
            usage();
            throw std::runtime_error("unknown or incomplete argument: " + argument);
        }
    }
    if (input_path.empty()) {
        usage();
        return 2;
    }

    const auto instance = water_sort::read_instance(input_path);
    const water_sort::BorderOracle oracle(instance);
    if (count_cap != 0) {
        const auto count = oracle.count_solutions(count_cap);
        std::cout << "border_sequences=" << count.solutions;
        if (count.solutions == count.cap) std::cout << "+";
        std::cout << " states_evaluated=" << count.states_evaluated << '\n';
    }
    const auto result = oracle.solve();
    std::cout << (result.solvable ? "SOLVABLE" : "UNSOLVABLE") << '\n';
    std::cout << "top_border_states=" << oracle.state_count() << '\n';
    std::cout << "states_visited=" << result.states_visited << '\n';
    std::cout << "transitions_tested=" << result.transitions_tested << '\n';
    if (result.solvable) {
        std::cout << "border_removals=" << result.removal_columns.size() << '\n';
        std::cout << "removal_columns=";
        for (const auto column : result.removal_columns) {
            std::cout << static_cast<unsigned>(column);
        }
        std::cout << '\n';
    } else if (!certificate_path.empty()) {
        water_sort::write_no_certificate(instance, oracle.state_count(),
                                         result.reachable_bits, certificate_path);
        std::cout << "certificate=" << certificate_path.string() << '\n';
    }
    return 0;
} catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 1;
}
