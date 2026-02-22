#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# REPO_DIR  = the inner GoBreeder/ dir (sibling of scripts/)
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# DEPLOY_BASE = clone root; instances are created here as siblings of GoBreeder/
DEPLOY_BASE="$(cd "$REPO_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# Java availability check
#
# The enemy Go program (gosumi) is a JAR file.  It is launched by
# gogui-twogtp.exe, which is a Windows binary executed via WSL2 interop.
# Because gogui-twogtp.exe runs as a Windows process it cannot see the WSL2
# Linux java directly; instead config.py wraps the command with 'wsl java …'
# so that gogui-twogtp.exe delegates back to the WSL2 runtime.
#
# This means we need Linux java (java / java.exe via 'wsl') to be present
# inside WSL2.  If it is missing, every single move attempt causes Windows to
# open a browser window prompting the user to install Java.
# ---------------------------------------------------------------------------
if ! command -v java &>/dev/null; then
    echo "ERROR: 'java' not found in this WSL2 environment." >&2
    echo "" >&2
    echo "The gosumi opponent is a Java JAR launched by gogui-twogtp.exe (a Windows" >&2
    echo "binary). config.py routes the java call back through WSL2 using 'wsl java'." >&2
    echo "Please install a JRE/JDK inside WSL2 before deploying, e.g.:" >&2
    echo "  sudo apt-get install -y default-jre" >&2
    exit 1
fi
echo "Java found: $(java -version 2>&1 | head -1)"

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

