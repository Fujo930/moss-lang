#!/bin/sh
# Moss Native — compile .moss to .mbc (Python) and run on C VM.
# Usage: ./moss-native run examples/order.moss

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
MBC="${TMPDIR:-/tmp}/moss_$$.mbc"

compile() {
    python -m mosslang.cli compile "$1" -o "$MBC"
    echo "compiled: $1 -> $MBC ($(wc -c < "$MBC") bytes)"
}

run() {
    compile "$1"
    "$ROOT/bin/mossvm" "$MBC"
    rm -f "$MBC"
}

build() {
    make -C "$ROOT"
}

case "${1:-}" in
    run)     shift; run "$@";;
    build)   build;;
    compile) compile "$2";;
    *)       echo "usage: moss-native {run <file.moss>|build|compile <file.moss>}"; exit 1;;
esac
