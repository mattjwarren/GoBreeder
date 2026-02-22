#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_BASE="$(cd "$SCRIPT_DIR/../.." && pwd)"

instance=${1}
TARGET_BREED="${DEPLOY_BASE}/GoBreeder_${instance}/breed"

cd "${TARGET_BREED}"
rm -f runlog.txt
uv run python3 mediator.py -gtp_breed -genome_file current_population.py &
sleep 3
tail -f runlog.txt
