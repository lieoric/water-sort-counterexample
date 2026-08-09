#include "water_sort/certificate.hpp"

#include <algorithm>
#include <array>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <vector>

namespace water_sort {
namespace {

constexpr std::array<char, 8> magic{'W', 'S', 'C', 'E', 'R', 'T', '1', '\0'};

void write_u32(std::ostream& output, std::uint32_t value) {
    for (unsigned shift = 0; shift < 32; shift += 8) {
        output.put(static_cast<char>((value >> shift) & 0xffU));
    }
}

void write_u64(std::ostream& output, std::uint64_t value) {
    for (unsigned shift = 0; shift < 64; shift += 8) {
        output.put(static_cast<char>((value >> shift) & 0xffU));
    }
}

std::uint32_t read_u32(std::istream& input) {
    std::uint32_t value = 0;
    for (unsigned shift = 0; shift < 32; shift += 8) {
        const auto byte = input.get();
        if (byte == std::char_traits<char>::eof()) {
            throw std::runtime_error("truncated certificate header");
        }
        value |= static_cast<std::uint32_t>(static_cast<unsigned char>(byte)) << shift;
    }
    return value;
}

std::uint64_t read_u64(std::istream& input) {
    std::uint64_t value = 0;
    for (unsigned shift = 0; shift < 64; shift += 8) {
        const auto byte = input.get();
        if (byte == std::char_traits<char>::eof()) {
            throw std::runtime_error("truncated certificate header");
        }
        value |= static_cast<std::uint64_t>(static_cast<unsigned char>(byte)) << shift;
    }
    return value;
}

bool bit_is_set(const std::vector<std::uint8_t>& bits, std::uint32_t id) {
    return (bits[id >> 3U] & static_cast<std::uint8_t>(1U << (id & 7U))) != 0;
}

std::uint32_t ceil_div(std::uint32_t numerator, std::uint32_t denominator) {
    return numerator == 0 ? 0 : 1 + (numerator - 1) / denominator;
}

} // namespace

void write_no_certificate(const Instance& instance,
                          std::uint32_t state_count,
                          const std::vector<std::uint8_t>& reachable_bits,
                          const std::filesystem::path& path) {
    instance.validate();
    const auto expected_bytes = (state_count + 7U) / 8U;
    if (reachable_bits.size() != expected_bytes || state_count == 0) {
        throw std::runtime_error("invalid reachable set for certificate");
    }
    std::ofstream output(path, std::ios::binary);
    if (!output) {
        throw std::runtime_error("cannot write certificate: " + path.string());
    }
    output.write(magic.data(), static_cast<std::streamsize>(magic.size()));
    write_u32(output, 1);
    write_u32(output, instance.height);
    write_u32(output, instance.color_count);
    write_u32(output, instance.empty_columns);
    write_u32(output, static_cast<std::uint32_t>(instance.columns.size()));
    write_u32(output, state_count);
    write_u32(output, expected_bytes);
    write_u64(output, instance_fingerprint(instance));
    output.write(reinterpret_cast<const char*>(reachable_bits.data()),
                 static_cast<std::streamsize>(reachable_bits.size()));
    if (!output) {
        throw std::runtime_error("failed while writing certificate");
    }
}

CertificateVerification verify_no_certificate(const Instance& instance,
                                               const std::filesystem::path& path) {
    instance.validate();
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        throw std::runtime_error("cannot open certificate: " + path.string());
    }
    std::array<char, 8> actual_magic{};
    input.read(actual_magic.data(), static_cast<std::streamsize>(actual_magic.size()));
    if (actual_magic != magic || read_u32(input) != 1) {
        throw std::runtime_error("unsupported certificate format");
    }
    const auto height = read_u32(input);
    const auto colors = read_u32(input);
    const auto empty = read_u32(input);
    const auto columns = read_u32(input);
    const auto state_count = read_u32(input);
    const auto byte_count = read_u32(input);
    const auto fingerprint = read_u64(input);
    if (height != instance.height || colors != instance.color_count ||
        empty != instance.empty_columns || columns != instance.columns.size() ||
        fingerprint != instance_fingerprint(instance)) {
        throw std::runtime_error("certificate does not match the supplied instance");
    }
    if (state_count == 0 || byte_count != (state_count + 7U) / 8U) {
        throw std::runtime_error("invalid certificate dimensions");
    }
    std::vector<std::uint8_t> bits(byte_count);
    input.read(reinterpret_cast<char*>(bits.data()), static_cast<std::streamsize>(bits.size()));
    if (input.gcount() != static_cast<std::streamsize>(bits.size())) {
        throw std::runtime_error("truncated certificate bitset");
    }

    // This verifier intentionally rebuilds the transition relation directly
    // from the paper's definitions instead of calling BorderOracle.
    const auto n = instance.columns.size();
    std::vector<std::vector<std::uint32_t>> borders(n);
    std::vector<std::uint32_t> radix(n);
    std::vector<std::uint32_t> multiplier(n);
    std::uint64_t product = 1;
    std::uint32_t initial = 0;
    for (std::size_t column = 0; column < n; ++column) {
        borders[column].push_back(0);
        for (std::uint32_t position = 1; position < instance.height; ++position) {
            if (instance.columns[column][position - 1] != instance.columns[column][position]) {
                borders[column].push_back(position);
            }
        }
        multiplier[column] = static_cast<std::uint32_t>(product);
        radix[column] = static_cast<std::uint32_t>(borders[column].size());
        product *= radix[column];
        if (product > std::numeric_limits<std::uint32_t>::max()) {
            throw std::runtime_error("certificate state space is too large");
        }
        initial += (radix[column] - 1U) * multiplier[column];
    }
    if (product != state_count) {
        throw std::runtime_error("certificate state count does not match the instance");
    }
    if (!bit_is_set(bits, initial)) {
        throw std::runtime_error("certificate invariant omits the initial state");
    }
    if (bit_is_set(bits, 0)) {
        throw std::runtime_error("certificate invariant contains the goal state");
    }

    CertificateVerification result;
    std::vector<std::uint32_t> ranks(n);
    std::vector<std::uint32_t> f(instance.color_count);
    std::vector<std::uint32_t> g(instance.color_count);

    for (std::uint32_t state = 0; state < state_count; ++state) {
        if (!bit_is_set(bits, state)) {
            continue;
        }
        ++result.marked_states;
        std::fill(f.begin(), f.end(), 0);
        std::fill(g.begin(), g.end(), 0);
        std::uint32_t monochrome_bins = instance.empty_columns;
        for (std::size_t column = 0; column < n; ++column) {
            ranks[column] = (state / multiplier[column]) % radix[column];
            const auto border = borders[column][ranks[column]];
            if (border == 0) {
                ++monochrome_bins;
            }
            for (std::uint32_t position = border; position < instance.height; ++position) {
                ++f[instance.columns[column][position]];
            }
            if (border > 0) {
                g[instance.columns[column][border]] += instance.height - border;
            }
        }

        for (std::size_t source = 0; source < n; ++source) {
            if (ranks[source] == 0) {
                continue;
            }
            ++result.transitions_checked;
            const auto border = borders[source][ranks[source]];
            const auto top_color = instance.columns[source][border];
            std::uint32_t needed = 0;
            for (std::uint32_t color = 0; color < instance.color_count; ++color) {
                auto usable = g[color];
                if (color == top_color) {
                    usable -= instance.height - border;
                }
                if (f[color] > usable) {
                    needed += ceil_div(f[color] - usable, instance.height);
                }
            }
            if (needed <= monochrome_bins) {
                const auto next = state - multiplier[source];
                if (!bit_is_set(bits, next)) {
                    throw std::runtime_error("certificate invariant is not transition-closed");
                }
            }
        }
    }
    result.valid = true;
    return result;
}

} // namespace water_sort
