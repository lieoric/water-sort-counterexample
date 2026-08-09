#pragma once

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace water_sort {

using Color = std::uint8_t;

struct Instance {
    std::uint32_t height = 0;
    std::uint32_t color_count = 0;
    std::uint32_t empty_columns = 0;
    std::vector<std::vector<Color>> columns; // bottom to top

    void validate() const;
};

Instance read_instance(const std::filesystem::path& path);
void write_instance(const Instance& instance, const std::filesystem::path& path);
std::uint64_t instance_fingerprint(const Instance& instance);
Instance canonicalize_instance(const Instance& instance);
std::string canonical_encoding(const Instance& instance);
std::uint64_t canonical_fingerprint(const Instance& instance);

char color_to_char(Color color);
Color char_to_color(char value);

} // namespace water_sort
