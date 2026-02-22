#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BREED_DIR="$(cd "$SCRIPT_DIR/../breed" && pwd)"

python3 "$BREED_DIR/play_gtp.py" "python3 $BREED_DIR/simple_go.py"
