#!/usr/bin/env bash
set -e
SRC="/mnt/h/Documents/dev/git_repos/GoBreeder/GoBreeder/breed/breeder.py"
for d in /home/matt/dev/gobreeders/0*/breed; do
    cp "$SRC" "$d/breeder.py"
    echo "Updated $d/breeder.py"
done
grep -n "subprocess args" /home/matt/dev/gobreeders/0*/breed/breeder.py
