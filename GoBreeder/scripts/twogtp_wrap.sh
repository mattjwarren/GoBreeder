#!/usr/bin/env bash
# Manual twogtp test harness.
# Runs a game between two gogui-dummy players just to verify the twogtp/referee
# pipeline works end to end.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BREED_DIR="$(cd "$SCRIPT_DIR/../breed" && pwd)"

"$BREED_DIR/windows/gogui-twogtp.exe" \
    -black "sh $SCRIPT_DIR/wrapdummy.sh" \
    -white "sh $SCRIPT_DIR/wrapdummy.sh" \
    -size 9 -auto -verbose \
    -referee "$BREED_DIR/ref_v0.1_exe"
