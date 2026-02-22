#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# REPO_DIR  = the inner GoBreeder/ dir (sibling of scripts/)
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# DEPLOY_BASE = clone root; instances are created here as siblings of GoBreeder/
DEPLOY_BASE="$(cd "$REPO_DIR/.." && pwd)"

instance=${1}

deploy_base="${DEPLOY_BASE}"
target_dir="${deploy_base}/GoBreeder_${instance}"

if [ -d "${target_dir}" ]; then
    rm -rf "${target_dir}"
fi

mkdir -p "${target_dir}"

# Copy the inner repo dir (breed/, scripts/, …) into the numbered instance.
# config.py auto-detects its own basepath via __file__, so no sed rewrite needed.
cp -R "${REPO_DIR}/"* "${target_dir}"

