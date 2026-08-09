if(CASE STREQUAL "c4-q-h2")
    set(colors 4)
    set(height 2)
    set(observation q)
    set(expected
        "colors=4"
        "target_exhausted=2"
        "consistent_states=9"
        "winning_states=9"
        "losing_states=0"
        "initial_states=5"
        "winning_initial_states=5"
        "all_initial_states_winning=true")
elseif(CASE STREQUAL "c4-next-h2")
    set(colors 4)
    set(height 2)
    set(observation next-run)
    set(expected
        "colors=4"
        "target_exhausted=2"
        "initial_observations=9"
        "reachable_observations=15"
        "winning_reachable_observations=15"
        "losing_reachable_observations=0"
        "all_initial_observations_winning=true")
elseif(CASE STREQUAL "c3-q-h2")
    set(colors 3)
    set(height 2)
    set(observation q)
    set(expected
        "colors=3"
        "target_exhausted=1"
        "consistent_states=2"
        "winning_states=2"
        "losing_states=0"
        "initial_states=2"
        "winning_initial_states=2"
        "all_initial_states_winning=true")
elseif(CASE STREQUAL "c3-next-h3")
    set(colors 3)
    set(height 3)
    set(observation next-run)
    set(expected
        "colors=3"
        "target_exhausted=1"
        "base_consistent_q_states=38"
        "initial_observations=44"
        "reachable_observations=137"
        "winning_reachable_observations=137"
        "losing_reachable_observations=0"
        "all_initial_observations_winning=true")
else()
    message(FATAL_ERROR "unknown counter-game regression case: ${CASE}")
endif()

file(MAKE_DIRECTORY "${OUT}")
set(report "${OUT}/report.json")
set(witness "${OUT}/witness.txt")
execute_process(
    COMMAND "${PROGRAM}"
        --height "${height}"
        --colors "${colors}"
        --observation "${observation}"
        --self-test
        --report "${report}"
        --witness "${witness}"
    RESULT_VARIABLE result
    OUTPUT_VARIABLE output
    ERROR_VARIABLE error)

if(NOT result EQUAL 0)
    message(FATAL_ERROR
        "counter-game ${CASE} failed with ${result}\n${output}\n${error}")
endif()

file(READ "${report}" json)
foreach(expectation IN LISTS expected)
    string(REPLACE "=" ";" pair "${expectation}")
    list(GET pair 0 key)
    list(GET pair 1 value)
    if(NOT json MATCHES "\"${key}\"[ \t\r\n]*:[ \t\r\n]*${value}([,\r\n])")
        message(FATAL_ERROR
            "counter-game ${CASE}: expected ${key}=${value}\n${json}")
    endif()
endforeach()

if(NOT output MATCHES "height=${height} colors=${colors}")
    message(FATAL_ERROR
        "counter-game ${CASE}: parameter summary is missing\n${output}")
endif()
