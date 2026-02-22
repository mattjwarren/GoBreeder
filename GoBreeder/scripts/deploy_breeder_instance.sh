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

# Ensure all executables have the execute bit set.
# Windows .exe files need this in WSL2 for interop to invoke them.
# The Linux referee binary and all shell scripts also need it.
find "${target_dir}" -name "*.exe" -exec chmod +x {} +
find "${target_dir}" -name "*.sh"  -exec chmod +x {} +
chmod +x "${target_dir}/breed/ref_v0.1_exe"

# Create an isolated virtual environment for this instance and install all
# runtime dependencies declared in pyproject.toml.
# uv run (used by all scripts) walks up from the cwd and will find this .venv
# automatically when scripts cd into breed/.
echo "Creating virtual environment for instance ${instance}..."
cd "${target_dir}"
uv sync --no-dev
echo "Virtual environment ready at ${target_dir}/.venv"

