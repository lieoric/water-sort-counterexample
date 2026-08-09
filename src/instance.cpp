#include "water_sort/instance.hpp"

#include <algorithm>
#include <array>
#include <cctype>
#include <fstream>
#include <numeric>
#include <sstream>
#include <stdexcept>

namespace water_sort {
namespace {

std::string trim(std::string value) {
    const auto first = std::find_if_not(value.begin(), value.end(), [](unsigned char c) {
        return std::isspace(c) != 0;
    });
    const auto last = std::find_if_not(value.rbegin(), value.rend(), [](unsigned char c) {
        return std::isspace(c) != 0;
    }).base();
    if (first >= last) {
        return {};
    }
    return {first, last};
}

std::pair<std::string, std::string> split_assignment(const std::string& line) {
    auto pos = line.find('=');
    if (pos == std::string::npos) {
        pos = line.find_first_of(" \t");
    }
    if (pos == std::string::npos) {
        throw std::runtime_error("expected key=value line: " + line);
    }
    return {trim(line.substr(0, pos)), trim(line.substr(pos + 1))};
}

} // namespace

char color_to_char(Color color) {
    if (color < 10) {
        return static_cast<char>('0' + color);
    }
    if (color < 36) {
        return static_cast<char>('A' + (color - 10));
    }
    throw std::runtime_error("color cannot be represented as one character");
}

Color char_to_color(char value) {
    if (value >= '0' && value <= '9') {
        return static_cast<Color>(value - '0');
    }
    value = static_cast<char>(std::toupper(static_cast<unsigned char>(value)));
    if (value >= 'A' && value <= 'Z') {
        return static_cast<Color>(10 + value - 'A');
    }
    throw std::runtime_error(std::string("invalid color character: ") + value);
}

void Instance::validate() const {
    if (height == 0 || height > 255) {
        throw std::runtime_error("height must be in [1, 255]");
    }
    if (color_count == 0 || color_count > 36) {
        throw std::runtime_error("colors must be in [1, 36]");
    }
    if (columns.size() != color_count) {
        throw std::runtime_error("this project requires one full column per color");
    }
    std::vector<std::uint32_t> counts(color_count, 0);
    for (const auto& column : columns) {
        if (column.size() != height) {
            throw std::runtime_error("every initial full column must have exactly height items");
        }
        for (const auto color : column) {
            if (color >= color_count) {
                throw std::runtime_error("color is outside the declared range");
            }
            ++counts[color];
        }
    }
    if (std::any_of(counts.begin(), counts.end(), [&](std::uint32_t count) { return count != height; })) {
        throw std::runtime_error("every color must occur exactly height times");
    }
}

Instance read_instance(const std::filesystem::path& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot open instance: " + path.string());
    }

    Instance instance;
    std::string line;
    while (std::getline(input, line)) {
        line = trim(line);
        if (line.empty() || line.front() == '#') {
            continue;
        }
        const auto [key, value] = split_assignment(line);
        if (key == "height") {
            instance.height = static_cast<std::uint32_t>(std::stoul(value));
        } else if (key == "colors") {
            instance.color_count = static_cast<std::uint32_t>(std::stoul(value));
        } else if (key == "empty") {
            instance.empty_columns = static_cast<std::uint32_t>(std::stoul(value));
        } else if (key == "column") {
            std::vector<Color> column;
            for (const char c : value) {
                if (std::isspace(static_cast<unsigned char>(c)) == 0) {
                    column.push_back(char_to_color(c));
                }
            }
            instance.columns.push_back(std::move(column));
        } else {
            throw std::runtime_error("unknown instance key: " + key);
        }
    }
    instance.validate();
    return instance;
}

void write_instance(const Instance& instance, const std::filesystem::path& path) {
    instance.validate();
    std::ofstream output(path);
    if (!output) {
        throw std::runtime_error("cannot write instance: " + path.string());
    }
    output << "# Columns are written bottom-to-top.\n";
    output << "height=" << instance.height << '\n';
    output << "colors=" << instance.color_count << '\n';
    output << "empty=" << instance.empty_columns << '\n';
    for (const auto& column : instance.columns) {
        output << "column=";
        for (const auto color : column) {
            output << color_to_char(color);
        }
        output << '\n';
    }
}

std::uint64_t instance_fingerprint(const Instance& instance) {
    instance.validate();
    std::uint64_t hash = 1469598103934665603ULL;
    const auto mix = [&](std::uint8_t byte) mutable {
        hash ^= byte;
        hash *= 1099511628211ULL;
    };
    auto mutable_mix = mix;
    for (unsigned shift = 0; shift < 32; shift += 8) mutable_mix(static_cast<std::uint8_t>(instance.height >> shift));
    for (unsigned shift = 0; shift < 32; shift += 8) mutable_mix(static_cast<std::uint8_t>(instance.color_count >> shift));
    for (unsigned shift = 0; shift < 32; shift += 8) mutable_mix(static_cast<std::uint8_t>(instance.empty_columns >> shift));
    for (const auto& column : instance.columns) {
        for (const auto color : column) mutable_mix(color);
    }
    return hash;
}

Instance canonicalize_instance(const Instance& instance) {
    instance.validate();
    if (instance.color_count > 8) {
        throw std::runtime_error("exact color canonicalization is limited to at most 8 colors");
    }

    std::vector<Color> permutation(instance.color_count);
    std::iota(permutation.begin(), permutation.end(), static_cast<Color>(0));
    std::vector<std::vector<Color>> best_columns;
    bool have_best = false;
    do {
        std::vector<std::vector<Color>> columns = instance.columns;
        for (auto& column : columns) {
            for (auto& color : column) {
                color = permutation[color];
            }
        }
        std::sort(columns.begin(), columns.end());
        if (!have_best || columns < best_columns) {
            best_columns = std::move(columns);
            have_best = true;
        }
    } while (std::next_permutation(permutation.begin(), permutation.end()));

    return Instance{instance.height, instance.color_count, instance.empty_columns,
                    std::move(best_columns)};
}

std::string canonical_encoding(const Instance& instance) {
    const auto canonical = canonicalize_instance(instance);
    std::ostringstream output;
    output << canonical.height << ':' << canonical.color_count << ':'
           << canonical.empty_columns << ':';
    for (std::size_t column = 0; column < canonical.columns.size(); ++column) {
        if (column != 0) output << '|';
        for (const auto color : canonical.columns[column]) {
            output << color_to_char(color);
        }
    }
    return output.str();
}

std::uint64_t canonical_fingerprint(const Instance& instance) {
    std::uint64_t hash = 1469598103934665603ULL;
    for (const unsigned char byte : canonical_encoding(instance)) {
        hash ^= byte;
        hash *= 1099511628211ULL;
    }
    return hash;
}

} // namespace water_sort
