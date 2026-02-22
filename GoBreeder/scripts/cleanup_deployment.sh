#!/usr/bin/env bash
# cleanup_deployment.sh [--archive-genomes] <instance>
#
# Archives all genome/population files from a deployed breeder instance into a
# timestamped compressed tarball saved to DEPLOY_BASE.
# By default also deletes the instance after archiving.
#
# Options:
#   --archive-genomes   Create the tarball only; do not delete the instance.
#
# Archive contents:
#   breed/current_population.py             – live population being evaluated
#   breed/current_population.py_save        – previous generation snapshot
#   breed/current_population.py_save_stats  – stats for previous generation
#   breed/breeding_genome.py                – most recent per-match genome
#   breed/vm_running_genome.py              – genome last executed by the VM
#   breed/histories/                        – per-genome historical run stats

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_BASE="$(cd "$REPO_DIR/.." && pwd)"

ARCHIVE_ONLY=false

# Parse flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --archive-genomes)
            ARCHIVE_ONLY=true
            shift
            ;;
        -*)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 [--archive-genomes] <instance>" >&2
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

if [ $# -lt 1 ]; then
    echo "Usage: $0 [--archive-genomes] <instance>" >&2
    exit 1
fi

instance=${1}
INST_DIR="${DEPLOY_BASE}/GoBreeder_${instance}"

if [ ! -d "${INST_DIR}" ]; then
    echo "Error: instance directory not found: ${INST_DIR}" >&2
    exit 1
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE_NAME="GoBreeder_${instance}_genomes_${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="${DEPLOY_BASE}/${ARCHIVE_NAME}"

INST_BREED="${INST_DIR}/breed"

# Build list of genome files/dirs that actually exist in this instance.
TARGETS=()
for f in \
    "breed/current_population.py" \
    "breed/current_population.py_save" \
    "breed/current_population.py_save_stats" \
    "breed/breeding_genome.py" \
    "breed/vm_running_genome.py" \
    "breed/histories"
do
    if [ -e "${INST_DIR}/${f}" ]; then
        TARGETS+=("${f}")
    fi
done

if [ ${#TARGETS[@]} -eq 0 ]; then
    echo "Warning: no genome files found in ${INST_DIR} — nothing to archive." >&2
else
    echo "Archiving genome files from GoBreeder_${instance} to ${ARCHIVE_PATH}..."
    tar -czf "${ARCHIVE_PATH}" -C "${INST_DIR}" "${TARGETS[@]}"
    echo "Archive created: ${ARCHIVE_PATH}"
fi

if [ "${ARCHIVE_ONLY}" = true ]; then
    echo "Archive-only mode — GoBreeder_${instance} left in place."
else
    echo "Deleting instance ${instance} at ${INST_DIR}..."
    rm -rf "${INST_DIR}"
    echo "Done. GoBreeder_${instance} removed."
fi