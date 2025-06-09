#!/bin/bash
set -e

# $1: Percorso dell'eseguibile da testare
# $2: Directory di output per i log e lo stato
EXECUTABLE_PATH="$1"
OUTPUT_DIR="$2"

LOG_FILE="${OUTPUT_DIR}/smoke_test_run.log"
STATUS_FILE="${OUTPUT_DIR}/smoke_test_status.txt"
MONITOR_DURATION_SECONDS=60
GRACEFUL_SHUTDOWN_WAIT_SECONDS=5

echo "Smoke Test Log for: ${EXECUTABLE_PATH}" > "${LOG_FILE}"
echo "Start Time: $(date)" >> "${LOG_FILE}"
echo "Output Directory: ${OUTPUT_DIR}" >> "${LOG_FILE}"
echo "Monitoring Duration: ${MONITOR_DURATION_SECONDS}s" >> "${LOG_FILE}"
echo "---" >> "${LOG_FILE}"

echo "Making executable runnable: chmod +x ${EXECUTABLE_PATH}" >> "${LOG_FILE}"
chmod +x "${EXECUTABLE_PATH}"

echo "Starting executable with xvfb-run..." >> "${LOG_FILE}"
echo "Command: xvfb-run --auto-servernum --server-args='-screen 0 1024x768x24' \"${EXECUTABLE_PATH}\"" >> "${LOG_FILE}"
xvfb-run --auto-servernum --server-args='-screen 0 1024x768x24' "./${EXECUTABLE_PATH}" >> "${LOG_FILE}" 2>&1 &
PID=$!
echo "Process started with PID: ${PID}" >> "${LOG_FILE}"

echo "Monitoring process PID ${PID} for ${MONITOR_DURATION_SECONDS} seconds..." >> "${LOG_FILE}"
sleep "${MONITOR_DURATION_SECONDS}"

PROCESS_STATUS_AFTER_WAIT="RUNNING"
if ! kill -0 "${PID}" > /dev/null 2>&1; then
    PROCESS_STATUS_AFTER_WAIT="EXITED_EARLY"
    echo "Process ${PID} exited before the ${MONITOR_DURATION_SECONDS}s monitoring period ended." >> "${LOG_FILE}"
fi

if [ "${PROCESS_STATUS_AFTER_WAIT}" == "RUNNING" ]; then
    echo "Process ${PID} is still running. Attempting graceful shutdown (SIGTERM)..." >> "${LOG_FILE}"
    kill -TERM "${PID}"

    for i in $(seq 1 "${GRACEFUL_SHUTDOWN_WAIT_SECONDS}"); do
        if ! kill -0 "${PID}" > /dev/null 2>&1; then
            PROCESS_STATUS_AFTER_WAIT="TERMINATED_SIGTERM"
            echo "Process ${PID} terminated gracefully with SIGTERM after ${i}s." >> "${LOG_FILE}"
            break
        fi
        sleep 1
    done

    if [ "${PROCESS_STATUS_AFTER_WAIT}" == "RUNNING" ]; then
        echo "Process ${PID} did not terminate with SIGTERM after ${GRACEFUL_SHUTDOWN_WAIT_SECONDS}s. Sending SIGKILL..." >> "${LOG_FILE}"
        kill -KILL "${PID}"
        sleep 1
        if ! kill -0 "${PID}" > /dev/null 2>&1; then
            PROCESS_STATUS_AFTER_WAIT="KILLED_SIGKILL"
            echo "Process ${PID} terminated with SIGKILL." >> "${LOG_FILE}"
        else
            PROCESS_STATUS_AFTER_WAIT="FAILED_TO_KILL_SIGKILL"
            echo "ERROR: Process ${PID} did not terminate even after SIGKILL." >> "${LOG_FILE}"
        fi
    fi
fi

wait "${PID}" || true
EXIT_CODE=$?
echo "Final exit code of process ${PID}: ${EXIT_CODE}" >> "${LOG_FILE}"

SMOKE_TEST_RESULT="FAIL_UNKNOWN"

if [ "${PROCESS_STATUS_AFTER_WAIT}" == "TERMINATED_SIGTERM" ]; then
    if [ "${EXIT_CODE}" -eq 143 ] || [ "${EXIT_CODE}" -eq 0 ]; then
        SMOKE_TEST_RESULT="PASS_SIGTERM"
        echo "Outcome: PASS (Terminated by SIGTERM as expected or exited cleanly on SIGTERM)" >> "${LOG_FILE}"
    else
        SMOKE_TEST_RESULT="FAIL_SIGTERM_UNEXPECTED_EXIT_${EXIT_CODE}"
        echo "Outcome: FAIL (Terminated by SIGTERM but with unexpected exit code ${EXIT_CODE})" >> "${LOG_FILE}"
    fi
elif [ "${PROCESS_STATUS_AFTER_WAIT}" == "KILLED_SIGKILL" ]; then
    if [ "${EXIT_CODE}" -eq 137 ]; then
        SMOKE_TEST_RESULT="PASS_SIGKILL"
        echo "Outcome: PASS (Terminated by SIGKILL after SIGTERM timeout)" >> "${LOG_FILE}"
    else
        SMOKE_TEST_RESULT="FAIL_SIGKILL_UNEXPECTED_EXIT_${EXIT_CODE}"
        echo "Outcome: FAIL (Terminated by SIGKILL but with unexpected exit code ${EXIT_CODE})" >> "${LOG_FILE}"
    fi
elif [ "${PROCESS_STATUS_AFTER_WAIT}" == "EXITED_EARLY" ]; then
    if [ "${EXIT_CODE}" -eq 0 ]; then
        SMOKE_TEST_RESULT="FAIL_EXITED_0_EARLY"
        echo "Outcome: FAIL (Exited cleanly with 0 but too early for an interactive app)" >> "${LOG_FILE}"
    else
        SMOKE_TEST_RESULT="FAIL_EXITED_NONZERO_EARLY_${EXIT_CODE}"
        echo "Outcome: FAIL (Exited early with non-zero code ${EXIT_CODE})" >> "${LOG_FILE}"
    fi
elif [ "${PROCESS_STATUS_AFTER_WAIT}" == "FAILED_TO_KILL_SIGKILL" ]; then
    SMOKE_TEST_RESULT="FAIL_UNABLE_TO_TERMINATE"
    echo "Outcome: FAIL (Process could not be terminated even with SIGKILL)" >> "${LOG_FILE}"
else
    if [ "${EXIT_CODE}" -eq 0 ]; then
        SMOKE_TEST_RESULT="PASS_EXITED_0_UNEXPECTEDLY"
        echo "Outcome: PASS (Exited cleanly with 0, but termination path unclear)" >> "${LOG_FILE}"
    else
        SMOKE_TEST_RESULT="FAIL_EXITED_NONZERO_UNEXPECTEDLY_${EXIT_CODE}"
        echo "Outcome: FAIL (Exited with non-zero code ${EXIT_CODE}, termination path unclear)" >> "${LOG_FILE}"
    fi
fi

echo "---" >> "${LOG_FILE}"
echo "Final Smoke Test Status: ${SMOKE_TEST_RESULT}" >> "${LOG_FILE}"
echo "End Time: $(date)" >> "${LOG_FILE}"

echo "${SMOKE_TEST_RESULT}" > "${STATUS_FILE}"

exit 0