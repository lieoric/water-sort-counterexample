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

add_executable(water-skeleton apps/skeleton.cpp)
target_link_libraries(water-skeleton PRIVATE water_sort)

add_executable(water-universe apps/universe.cpp)
target_link_libraries(water-universe PRIVATE water_sort)

add_executable(water-descend apps/descend.cpp)
target_link_libraries(water-descend PRIVATE water_sort)

include(CTest)
if(BUILD_TESTING)
    add_executable(water-sort-tests tests/test_main.cpp)
    target_link_libraries(water-sort-tests PRIVATE water_sort)
    target_compile_definitions(water-sort-tests PRIVATE
        WSC_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}")
    add_test(NAME water-sort-tests COMMAND water-sort-tests)
    file(GLOB WSC_EXPERIMENT_INSTANCES "${CMAKE_CURRENT_SOURCE_DIR}/experiments/*.txt")
    foreach(WSC_EXPERIMENT_INSTANCE IN LISTS WSC_EXPERIMENT_INSTANCES)
        get_filename_component(WSC_EXPERIMENT_NAME ${WSC_EXPERIMENT_INSTANCE} NAME_WE)
        add_test(NAME water-experiment-${WSC_EXPERIMENT_NAME}
            COMMAND water-verify
                --input ${WSC_EXPERIMENT_INSTANCE}
                --certificate ${CMAKE_CURRENT_SOURCE_DIR}/experiments/${WSC_EXPERIMENT_NAME}.wscert)
    endforeach()
    add_test(NAME water-skeleton-smoke
        COMMAND water-skeleton
            --input ${CMAKE_CURRENT_SOURCE_DIR}/experiments/minimized-15b.txt
            --candidate-limit 20
            --certificate-limit 0
            --out ${CMAKE_CURRENT_BINARY_DIR}/test-skeleton-output)
    add_test(NAME water-family-radius-two-smoke
        COMMAND water-neighborhood
            --seed-dir ${CMAKE_CURRENT_SOURCE_DIR}/experiments
            --empty 2
            --radius 2
            --frontier-limit 1
            --certificate-limit 0
            --out ${CMAKE_CURRENT_BINARY_DIR}/test-family-output)
    add_test(NAME water-hunter-uniform-layer-smoke
        COMMAND water-hunter
            --seed 1
            --seconds 0
            --iterations 10
            --solution-cap 10
            --height 6
            --colors 4
            --empty 2
            --uniform-layer 1
            --isolate-uniform-layer 1
            --fully-alternating 1
            --out ${CMAKE_CURRENT_BINARY_DIR}/test-uniform-layer-output)
    add_test(NAME water-descend-noop-smoke
        COMMAND water-descend
            --input ${CMAKE_CURRENT_SOURCE_DIR}/experiments/minimum-h5-ce-000.txt
            --target-height 5
            --frontier-limit 4
            --seed 1
            --out ${CMAKE_CURRENT_BINARY_DIR}/test-descend-output)
    function(add_universe_regression NAME HEIGHT COLORS EMPTY CLASSES UNSOLVABLE)
        add_test(NAME ${NAME}
            COMMAND water-universe
                --height ${HEIGHT}
                --colors ${COLORS}
                --empty ${EMPTY}
                --candidate-limit 0
                --certificate-limit 0
                --expect-classes ${CLASSES}
                --expect-unsolvable ${UNSOLVABLE}
                --out ${CMAKE_CURRENT_BINARY_DIR}/${NAME}-output)
    endfunction()
    add_universe_regression(water-k1-c2-h3 3 2 1 7 0)
    add_universe_regression(water-k1-c3-h2 2 3 1 5 0)
    add_universe_regression(water-k1-c2-h4 4 2 1 23 1)
    add_universe_regression(water-k1-c3-h3 3 3 1 55 7)
    add_universe_regression(water-k1-c4-h2 2 4 1 12 1)
    add_test(NAME water-universe-height-two
        COMMAND water-universe
            --height 2
            --colors 5
            --empty 2
            --candidate-limit 1000
            --certificate-limit 0
            --expect-classes 20
            --expect-unsolvable 0
            --out ${CMAKE_CURRENT_BINARY_DIR}/test-universe-output)
endif()
