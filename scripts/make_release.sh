#!/usr/bin/env bash
# Creates a release archive of tracked files only.
# Usage: bash scripts/make_release.sh [version]
# Output: dist/nammapayana-<version>.tar.gz
set -euo pipefail

VERSION="${1:-$(git describe --tags --always --dirty 2>/dev/null || echo dev)}"
OUTDIR="dist"
mkdir -p "$OUTDIR"
OUTFILE="$OUTDIR/nammapayana-${VERSION}.tar.gz"

git archive --format=tar.gz --prefix="nammapayana-${VERSION}/" HEAD > "$OUTFILE"

echo "Release archive: $OUTFILE"
echo "Contents (first 20 files):"
tar -tzf "$OUTFILE" | head -20

# Sanity checks — these must NOT appear in the archive
if tar -tzf "$OUTFILE" | grep -qE '\.env$|venv/|__pycache__|\.db$'; then
    echo "ERROR: Archive contains excluded files!" >&2
    exit 1
fi
echo "Sanity check passed — no .env, venv, __pycache__, or .db files in archive."
