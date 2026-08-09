cmake_minimum_required(VERSION 3.20)
project(water_sort_counterexample VERSION 0.1.0 LANGUAGES CXX)

option(WSC_ENABLE_SANITIZERS "Enable AddressSanitizer and UndefinedBehaviorSanitizer" OFF)
option(WSC_WARNINGS_AS_ERRORS "Treat compiler warnings as errors" OFF)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(water_sort
    src/instance.cpp
    src/border_oracle.cpp
    src/certificate.cpp
    src/water_solver.cpp
)
target_include_directories(water_sort PUBLIC include)

if(MSVC)
    target_compile_options(water_sort PRIVATE /W4)
    if(WSC_WARNINGS_AS_ERRORS)
        target_compile_options(water_sort PRIVATE /WX)
    endif()
else()
    target_compile_options(water_sort PRIVATE -Wall -Wextra -Wpedantic)
    if(WSC_WARNINGS_AS_ERRORS)
        target_compile_options(water_sort PRIVATE -Werror)
    endif()
    if(WSC_ENABLE_SANITIZERS)
        target_compile_options(water_sort PUBLIC -fsanitize=address,undefined -fno-omit-frame-pointer)
        target_link_options(water_sort PUBLIC -fsanitize=address,undefined)
    endif()
endif()

add_executable(water-oracle apps/oracle.cpp)
target_link_libraries(water-oracle PRIVATE water_sort)

add_executable(water-verify apps/verify.cpp)
target_link_libraries(water-verify PRIVATE water_sort)

add_executable(water-hunter apps/hunter.cpp)
target_link_libraries(water-hunter PRIVATE water_sort)

add_executable(water-neighborhood apps/neighborhood.cpp)
target_link_libraries(water-neighborhood PRIVATE water_sort)

add_executable(water-minimize apps/minimize.cpp)
target_link_libraries(water-minimize PRIVATE water_sort)

include(CTest)
if(BUILD_TESTING)
    add_executable(water-sort-tests tests/test_main.cpp)
    target_link_libraries(water-sort-tests PRIVATE water_sort)
    target_compile_definitions(water-sort-tests PRIVATE
        WSC_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}")
    add_test(NAME water-sort-tests COMMAND water-sort-tests)
endif()
