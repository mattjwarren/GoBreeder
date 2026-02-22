#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BREED_DIR="$(cd "$SCRIPT_DIR/../breed" && pwd)"

# gogui-dummy.exe is a Windows binary; WSL2 interop launches it as a Windows process.
"$BREED_DIR/windows/gogui-dummy.exe"
