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

add_executable(water-policy-learn apps/policy_learn.cpp)
target_link_libraries(water-policy-learn PRIVATE water_sort)

add_executable(water-policy-control apps/policy_control.cpp)
target_link_libraries(water-policy-control PRIVATE water_sort)

add_executable(water-unit-scenes apps/unit_scenes.cpp)
target_link_libraries(water-unit-scenes PRIVATE water_sort)

add_executable(water-depth-witness apps/depth_witness.cpp)
target_link_libraries(water-depth-witness PRIVATE water_sort)

add_executable(water-continuous-control apps/continuous_control.cpp)
target_link_libraries(water-continuous-control PRIVATE water_sort)

add_executable(water-counter-game apps/counter_game.cpp)
target_link_libraries(water-counter-game PRIVATE water_sort)

add_executable(water-c4-h7-tq-gate-check apps/c4_h7_tq_gate_check.cpp)
target_link_libraries(water-c4-h7-tq-gate-check PRIVATE water_sort)
if(MSVC)
    target_compile_options(water-c4-h7-tq-gate-check PRIVATE /W4)
    if(WSC_WARNINGS_AS_ERRORS)
        target_compile_options(water-c4-h7-tq-gate-check PRIVATE /WX)
    endif()
else()
    target_compile_options(water-c4-h7-tq-gate-check PRIVATE -Wall -Wextra -Wpedantic)
    if(WSC_WARNINGS_AS_ERRORS)
        target_compile_options(water-c4-h7-tq-gate-check PRIVATE -Werror)
    endif()
endif()

add_executable(water-c4-h7-tq-sibling-forks apps/c4_h7_tq_sibling_forks.cpp)
target_link_libraries(water-c4-h7-tq-sibling-forks PRIVATE water_sort)
if(MSVC)
    target_compile_options(water-c4-h7-tq-sibling-forks PRIVATE /W4)
    if(WSC_WARNINGS_AS_ERRORS)
        target_compile_options(water-c4-h7-tq-sibling-forks PRIVATE /WX)
    endif()
else()
    target_compile_options(water-c4-h7-tq-sibling-forks PRIVATE -Wall -Wextra -Wpedantic)
    if(WSC_WARNINGS_AS_ERRORS)
        target_compile_options(water-c4-h7-tq-sibling-forks PRIVATE -Werror)
    endif()
endif()

add_executable(water-c4-h7-tq-exhaust-siblings apps/c4_h7_tq_exhaust_siblings.cpp)
if(MSVC)
    target_compile_options(water-c4-h7-tq-exhaust-siblings PRIVATE /W4)
    if(WSC_WARNINGS_AS_ERRORS)
        target_compile_options(water-c4-h7-tq-exhaust-siblings PRIVATE /WX)
    endif()
else()
    target_compile_options(water-c4-h7-tq-exhaust-siblings PRIVATE -Wall -Wextra -Wpedantic)
    if(WSC_WARNINGS_AS_ERRORS)
        target_compile_options(water-c4-h7-tq-exhaust-siblings PRIVATE -Werror)
    endif()
endif()

add_executable(water-c4-h7-tq-low-corners apps/c4_h7_tq_low_corners.cpp)
if(MSVC)
    target_compile_options(water-c4-h7-tq-low-corners PRIVATE /W4)
    if(WSC_WARNINGS_AS_ERRORS)
        target_compile_options(water-c4-h7-tq-low-corners PRIVATE /WX)
    endif()
else()
    target_compile_options(water-c4-h7-tq-low-corners PRIVATE -Wall -Wextra -Wpedantic)
    if(WSC_WARNINGS_AS_ERRORS)
        target_compile_options(water-c4-h7-tq-low-corners PRIVATE -Werror)
    endif()
endif()

include(CTest)
if(BUILD_TESTING)
    add_executable(water-sort-tests tests/test_main.cpp)
    target_link_libraries(water-sort-tests PRIVATE water_sort)
    target_compile_definitions(water-sort-tests PRIVATE
        WSC_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}")
    add_test(NAME water-sort-tests COMMAND water-sort-tests)
    add_test(NAME water-c4-h7-tq-sibling-forks-smoke
        COMMAND water-c4-h7-tq-sibling-forks
            --self-test
            --limit 64
            --output-dir ${CMAKE_CURRENT_BINARY_DIR}/test-c4-h7-tq-sibling-forks-output)
    add_test(NAME water-c4-h7-tq-exhaust-siblings-smoke
        COMMAND water-c4-h7-tq-exhaust-siblings
            --self-test
            --limit 64
            --output-dir ${CMAKE_CURRENT_BINARY_DIR}/test-c4-h7-tq-exhaust-siblings-output)
    add_test(NAME water-c4-h7-tq-low-corners-smoke
        COMMAND water-c4-h7-tq-low-corners
            --self-test
            --limit 64
            --output-dir ${CMAKE_CURRENT_BINARY_DIR}/test-c4-h7-tq-low-corners-output)
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
            --fitness safe-initial
            --height 6
            --colors 4
            --empty 2
            --uniform-layer 1
            --isolate-uniform-layer 1
            --fully-alternating 1
            --out ${CMAKE_CURRENT_BINARY_DIR}/test-uniform-layer-output)
    add_test(NAME water-hunter-seeded-no-smoke
        COMMAND water-hunter
            --input ${CMAKE_CURRENT_SOURCE_DIR}/experiments/c4-k2-h9-no-000.txt
            --seconds 0
            --iterations 1
            --solution-cap 10
            --fitness safe-initial
            --restart-interval 0
            --height 9
            --colors 4
            --empty 2
            --out ${CMAKE_CURRENT_BINARY_DIR}/test-seeded-no-output)
    set_tests_properties(water-hunter-seeded-no-smoke PROPERTIES
        PASS_REGULAR_EXPRESSION "COUNTEREXAMPLE FOUND IN SEED")
    add_test(NAME water-descend-noop-smoke
        COMMAND water-descend
            --input ${CMAKE_CURRENT_SOURCE_DIR}/experiments/minimum-h5-ce-000.txt
            --target-height 5
            --frontier-limit 4
            --seed 1
            --out ${CMAKE_CURRENT_BINARY_DIR}/test-descend-output)
    add_test(NAME water-descend-separated-runs-regression
        COMMAND ${CMAKE_COMMAND}
            -DPROGRAM=$<TARGET_FILE:water-descend>
            -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/experiments/c4-k2-h8-no-001.txt
            -DOUT=${CMAKE_CURRENT_BINARY_DIR}/test-descend-separated-runs-output
            -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/check_descend_separated_runs.cmake)
    add_test(NAME water-policy-learn-smoke
        COMMAND water-policy-learn
            --height 3
            --colors 3
            --empty 2
            --depth 2
            --goal-exhausted 2
            --tail-mutations 1
            --tail-swaps 1
            --samples 8
            --seed 1
            --stop-on-no 1
            --out ${CMAKE_CURRENT_BINARY_DIR}/test-policy-output)
    add_test(NAME water-policy-control-smoke
        COMMAND water-policy-control
            --catalog ${CMAKE_CURRENT_SOURCE_DIR}/tests/data/policy-catalog.tsv
            --depth 3
            --goal-exhausted 2
            --restarts 8
            --repair-passes 16
            --seed 1
            --out ${CMAKE_CURRENT_BINARY_DIR}/test-policy-control-output)
    add_test(NAME water-policy-compression-smoke
        COMMAND water-policy-control
            --catalog ${CMAKE_CURRENT_SOURCE_DIR}/tests/data/policy-catalog.tsv
            --depth 3
            --goal-exhausted 2
            --default-heuristic last
            --restarts 8
            --repair-passes 16
            --seed 1
            --out ${CMAKE_CURRENT_BINARY_DIR}/test-policy-compression-output)
    add_test(NAME water-unit-scenes-smoke
        COMMAND water-unit-scenes
            --catalog ${CMAKE_CURRENT_SOURCE_DIR}/tests/data/policy-catalog.tsv
            --policy ${CMAKE_CURRENT_SOURCE_DIR}/tests/data/empty-policy.tsv
            --goal-exhausted 2
            --max-instances 2
            --out ${CMAKE_CURRENT_BINARY_DIR}/test-unit-scenes-output)
    add_test(NAME water-depth-obstruction
        COMMAND water-depth-witness
            --left ${CMAKE_CURRENT_SOURCE_DIR}/tests/data/depth-obstruction-a.txt
            --left-state 489067
            --right ${CMAKE_CURRENT_SOURCE_DIR}/tests/data/depth-obstruction-b.txt
            --right-state 10211
            --scale 6
            --window 6
            --goal-exhausted 2)
    set_tests_properties(water-depth-obstruction PROPERTIES
        PASS_REGULAR_EXPRESSION "\"run_scenes_equal\": false")
    add_test(NAME water-continuous-control-smoke
        COMMAND water-continuous-control
            --catalog ${CMAKE_CURRENT_SOURCE_DIR}/tests/data/policy-catalog.tsv
            --policy ${CMAKE_CURRENT_SOURCE_DIR}/tests/data/empty-policy.tsv
            --goal-exhausted 2
            --max-instances 2
            --out ${CMAKE_CURRENT_BINARY_DIR}/test-continuous-control-output)
    add_test(NAME water-counter-game-q-smoke
        COMMAND water-counter-game
            --height 2
            --observation q
            --self-test
            --report ${CMAKE_CURRENT_BINARY_DIR}/test-counter-q/report.json
            --witness ${CMAKE_CURRENT_BINARY_DIR}/test-counter-q/witness.txt)
    add_test(NAME water-counter-game-next-run-smoke
        COMMAND water-counter-game
            --height 2
            --observation next-run
            --self-test
            --report ${CMAKE_CURRENT_BINARY_DIR}/test-counter-next/report.json
            --witness ${CMAKE_CURRENT_BINARY_DIR}/test-counter-next/witness.txt)
    add_test(NAME water-c4-h7-tq-gate-check-smoke
        COMMAND water-c4-h7-tq-gate-check
            --self-test
            --limit 100
            --output-dir ${CMAKE_CURRENT_BINARY_DIR}/test-c4-h7-tq-gate-output)
    function(add_counter_game_regression NAME CASE_NAME)
        add_test(NAME ${NAME}
            COMMAND ${CMAKE_COMMAND}
                -DPROGRAM=$<TARGET_FILE:water-counter-game>
                -DCASE=${CASE_NAME}
                -DOUT=${CMAKE_CURRENT_BINARY_DIR}/${NAME}-output
                -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/check_counter_game.cmake)
    endfunction()
    add_counter_game_regression(water-counter-game-c4-q-h2 c4-q-h2)
    add_counter_game_regression(water-counter-game-c4-next-h2 c4-next-h2)
    add_counter_game_regression(water-counter-game-c3-q-h2 c3-q-h2)
    add_counter_game_regression(water-counter-game-c3-next-h3 c3-next-h3)
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
