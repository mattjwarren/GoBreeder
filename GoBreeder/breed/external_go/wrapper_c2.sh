#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BREED_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

python "$BREED_DIR/mediator.py" -genome_file "$BREED_DIR/champ2"
