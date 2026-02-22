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
uv run python3 mediator.py -gtp_breed -genome_file current_population.py &
# --retry keeps tail alive even if the file is briefly empty or recreated.
tail --retry -f runlog.txt
