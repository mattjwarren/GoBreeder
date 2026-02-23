#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# REPO_DIR  = the inner GoBreeder/ dir (sibling of scripts/)
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# DEPLOY_BASE = clone root; instances are created here as siblings of GoBreeder/
DEPLOY_BASE="$(cd "$REPO_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# Dependency checks
#
# Game execution is entirely Linux-native:
#   gogui-twogtp  (Linux, bundled in gogui-v1.6.0-bin/)  orchestrates games
#   java          (Linux)  runs the gosumi opponent JAR and gogui-twogtp
#   ref_v0.1_exe  (Linux)  acts as referee
#
# No Windows Java or WSL2 interop is needed.
# ---------------------------------------------------------------------------

# Linux Java – needed to run gogui-twogtp.jar and the gosumi JARs.
if ! command -v java &>/dev/null; then
    echo "ERROR: 'java' not found in this WSL2 environment." >&2
    echo "Please install a JRE/JDK, e.g.:" >&2
    echo "  sudo apt-get install -y default-jre" >&2
    exit 1
fi
echo "Linux Java found: $(java -version 2>&1 | head -1)"

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
# The Linux referee binary and all shell scripts need it.
# The bundled gogui bin/ scripts also need it.
find "${target_dir}" -name "*.sh"  -exec chmod +x {} +
chmod +x "${target_dir}/breed/ref_v0.1_exe"
find "${target_dir}/gogui-v1.6.0-bin/gogui/bin" -type f -exec chmod +x {} +

# Create an isolated virtual environment for this instance and install all
# runtime dependencies declared in pyproject.toml.
# uv run (used by all scripts) walks up from the cwd and will find this .venv
# automatically when scripts cd into breed/.
echo "Creating virtual environment for instance ${instance}..."
cd "${target_dir}"
uv sync --no-dev
echo "Virtual environment ready at ${target_dir}/.venv"

# ---------------------------------------------------------------------------
# Rust VM extension (go_vm_rs)
#
# Copy the Rust source from the repo root into the instance directory and
# build it in-place so the platform-specific .so is installed into the
# instance's own .venv.  Building locally ensures the binary matches the
# host architecture (important for ARM nodes such as pi2/pi3).
#
# If Rust or maturin are unavailable the build is skipped and vm.py falls
# back transparently to the pure-Python VM.
# ---------------------------------------------------------------------------
RUST_SRC="${DEPLOY_BASE}/go_vm_rs"
RUST_DEST="${target_dir}/go_vm_rs"

build_rust_vm() {
    echo "Building Rust VM extension for instance ${instance}..."

    # Ensure Rust toolchain is available; install rustup if not.
    if ! command -v cargo &>/dev/null; then
        if ! command -v rustup &>/dev/null; then
            echo "  Rust not found – installing rustup..."
            curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
                | sh -s -- -y --no-modify-path
        fi
        # shellcheck source=/dev/null
        source "${HOME}/.cargo/env"
        # Also export so child processes (maturin build) see the updated PATH.
        export PATH="${HOME}/.cargo/bin:${PATH}"
    fi

    echo "  Rust: $(rustc --version)"

    # Install maturin into the instance venv (build-time only).
    "${target_dir}/.venv/bin/pip" install --quiet maturin

    # Build and install the Rust extension directly into the instance venv.
    # maturin develop --release compiles with full optimisations and installs
    # the resulting .so into the venv in a single step.
    cd "${RUST_DEST}"
    "${target_dir}/.venv/bin/maturin" develop --release 2>&1 | sed 's/^/  /'

    # Verify the extension is importable before declaring success.
    "${target_dir}/.venv/bin/python" -c \
        'import go_vm_rs; print("  go_vm_rs imported OK")'

    echo "Rust VM extension built and installed."
}

if [ -d "${RUST_SRC}" ]; then
    # Copy Rust source (exclude the target/ build cache to save space).
    rsync -a --exclude='target/' "${RUST_SRC}/" "${RUST_DEST}/"

    if build_rust_vm; then
        echo "Rust VM ready for instance ${instance}."
    else
        echo "WARNING: Rust VM build failed – instance will use the Python VM fallback." >&2
    fi
else
    echo "WARNING: go_vm_rs source not found at ${RUST_SRC}; skipping Rust VM build." >&2
fi

cd "${target_dir}"

