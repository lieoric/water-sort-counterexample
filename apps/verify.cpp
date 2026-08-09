#include "water_sort/certificate.hpp"
#include "water_sort/instance.hpp"

#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc, char** argv) try {
    std::filesystem::path input_path;
    std::filesystem::path certificate_path;
    for (int i = 1; i < argc; ++i) {
        const std::string argument = argv[i];
        if (argument == "--input" && i + 1 < argc) {
            input_path = argv[++i];
        } else if (argument == "--certificate" && i + 1 < argc) {
            certificate_path = argv[++i];
        } else if (argument == "--help") {
            std::cout << "Usage: water-verify --input INSTANCE --certificate FILE\n";
            return 0;
        } else {
            throw std::runtime_error("unknown or incomplete argument: " + argument);
        }
    }
    if (input_path.empty() || certificate_path.empty()) {
        throw std::runtime_error("both --input and --certificate are required");
    }
    const auto instance = water_sort::read_instance(input_path);
    const auto result = water_sort::verify_no_certificate(instance, certificate_path);
    std::cout << "VALID NO CERTIFICATE\n";
    std::cout << "marked_states=" << result.marked_states << '\n';
    std::cout << "transitions_checked=" << result.transitions_checked << '\n';
    return result.valid ? 0 : 1;
} catch (const std::exception& error) {
    std::cerr << "INVALID: " << error.what() << '\n';
    return 1;
}
