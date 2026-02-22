#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# REPO_DIR  = the inner GoBreeder/ dir (sibling of scripts/)
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# DEPLOY_BASE = clone root; instances are created here as siblings of GoBreeder/
DEPLOY_BASE="$(cd "$REPO_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# Windows Java availability check
#
# The enemy Go program (gosumi) is a JAR file launched by gogui-twogtp.exe.
# gogui-twogtp.exe is a Windows binary (WSL2 interop) so when it spawns
# 'java -jar …' it runs a Windows process — it needs Windows Java on the
# Windows PATH, NOT the WSL2 Linux java.
#
# From WSL2 we can test Windows java via WSL2 interop: calling 'java.exe'
# resolves to the Windows java binary through the interop PATH bridge.
# If it is missing, every single game move causes Windows to open a browser
# window prompting the user to install Java.
# ---------------------------------------------------------------------------
if ! java.exe -version &>/dev/null; then
    echo "ERROR: Windows 'java.exe' not found or not accessible from WSL2." >&2
    echo "" >&2
    echo "gogui-twogtp.exe is a Windows process and needs Windows Java on the" >&2
    echo "Windows PATH.  Please install a Windows JRE/JDK, e.g.:" >&2
    echo "  https://adoptium.net/  (Temurin JRE is sufficient)" >&2
    echo "" >&2
    echo "After installing, ensure 'java' is on your Windows PATH and restart" >&2
    echo "your WSL2 session so the interop PATH is refreshed." >&2
    exit 1
fi
echo "Windows Java found: $(java.exe -version 2>&1 | head -1)"

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

