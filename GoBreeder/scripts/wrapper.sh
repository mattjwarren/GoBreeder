#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BREED_DIR="$(cd "$SCRIPT_DIR/../breed" && pwd)"

uv run python3 "$BREED_DIR/mediator.py" -genome_file "$BREED_DIR/champion_genome.py"
