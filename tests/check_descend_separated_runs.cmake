execute_process(
    COMMAND "${PROGRAM}"
        --input "${INPUT}"
        --target-height 7
        --frontier-limit 100
        --seed 1
        --out "${OUT}"
    RESULT_VARIABLE result
    OUTPUT_VARIABLE output
    ERROR_VARIABLE error)

if(NOT result EQUAL 2)
    message(FATAL_ERROR
        "expected descent to stop without a NO child (exit 2), got ${result}\n${output}\n${error}")
endif()

if(NOT output MATCHES "height=8->7 unique=54 tested=54 no=0")
    message(FATAL_ERROR "separated-run children were not enumerated completely\n${output}")
endif()
