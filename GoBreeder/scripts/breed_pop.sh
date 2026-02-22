#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_BASE="$(cd "$SCRIPT_DIR/../.." && pwd)"

instance=${1}
TARGET_BREED="${DEPLOY_BASE}/GoBreeder_${instance}/breed"

cd "${TARGET_BREED}"
rm -f runlog.txt
# Pre-create the log file so tail -f can open it immediately.
touch runlog.txt

# Start the mediator in a new process group (setsid) so that when the user
# presses Ctrl-C the entire tree — gogui-twogtp, gosumi JARs, referee, child
# mediator processes — can be killed together via the process group.
setsid uv run python3 mediator.py -gtp_breed -genome_file current_population.py &
MEDIATOR_PID=$!

cleanup() {
    echo "" >&2
    echo "Stopping breeder (group PID ${MEDIATOR_PID})..." >&2
    # kill -- -PID sends SIGTERM to every process whose PGID = PID.
    # setsid makes the new session's PGID equal MEDIATOR_PID, so this
    # kills the whole tree (gogui-twogtp, gosumi JARs, referee, etc.).
    kill -- -"${MEDIATOR_PID}" 2>/dev/null || kill "${MEDIATOR_PID}" 2>/dev/null || true
    wait "${MEDIATOR_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Show the log in the foreground.  Ctrl-C interrupts tail, fires cleanup above.
# --retry keeps tail alive even if the file is briefly empty or recreated.
tail --retry -f runlog.txt
