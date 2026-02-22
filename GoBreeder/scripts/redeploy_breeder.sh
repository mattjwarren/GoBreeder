#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_BASE="$(cd "$SCRIPT_DIR/../.." && pwd)"

instance=${1}
INST_BREED="${DEPLOY_BASE}/GoBreeder_${instance}/breed"
SAVE_DIR="${DEPLOY_BASE}/.redeploy_save_${instance}"

echo "Clearing save cache at ${SAVE_DIR}"
rm -rf "${SAVE_DIR}"
mkdir -p "${SAVE_DIR}/histories" "${SAVE_DIR}/config" "${SAVE_DIR}/current"

echo "Saving current instance state"
mv "${INST_BREED}/histories/"* "${SAVE_DIR}/histories/" 2>/dev/null || true
mv "${INST_BREED}/config.py"       "${SAVE_DIR}/config/"
mv "${INST_BREED}/current_"*       "${SAVE_DIR}/current/" 2>/dev/null || true

echo "Redeploying instance ${instance}"
"${SCRIPT_DIR}/deploy_breeder_instance.sh" "${instance}"

echo "Restoring saved instance state"
mv "${SAVE_DIR}/histories/"*  "${INST_BREED}/histories/" 2>/dev/null || true
mv "${SAVE_DIR}/config/config.py" "${INST_BREED}/config.py"
mv "${SAVE_DIR}/current/current_"* "${INST_BREED}/" 2>/dev/null || true

rm -rf "${SAVE_DIR}"
echo "Done."