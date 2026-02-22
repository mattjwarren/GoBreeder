#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BREED_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

python "$BREED_DIR/play_gtp.py" "python $BREED_DIR/simple_go.py"
