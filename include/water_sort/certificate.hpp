#pragma once

#include "water_sort/border_oracle.hpp"

#include <cstdint>
#include <filesystem>

namespace water_sort {

struct CertificateVerification {
    bool valid = false;
    std::uint64_t marked_states = 0;
    std::uint64_t transitions_checked = 0;
};

void write_no_certificate(const Instance& instance,
                          std::uint32_t state_count,
                          const std::vector<std::uint8_t>& reachable_bits,
                          const std::filesystem::path& path);

CertificateVerification verify_no_certificate(const Instance& instance,
                                               const std::filesystem::path& path);

} // namespace water_sort
