#!/usr/bin/env bash
# Builds the CBACT04C exhibit inside the Revenant container.
# The legacy source is compiled as-is; only the driver and file utilities are ours.
# Usage: exhibits/cbact04c/build.sh [output-dir]   (default: build/cbact04c)
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
out="${1:-$here/../../build/cbact04c}"
mkdir -p "$out"
out="$(cd "$out" && pwd)"

# Refuse to build if the legacy sources differ from the pinned upstream hashes.
(cd "$here" && sha256sum --quiet -c SHA256SUMS)

# -fsign=EBCDIC: signed display fields carry the sign as a mainframe overpunch
# ({ A-I positive, } J-R negative), the convention of the original platform and of
# CardDemo's seed data. The GnuCOBOL default differs and mis-reads seed negatives.
flags=(-std=ibm -fsign=EBCDIC -I "$here/legacy/cpy")

# One executable: the driver is the entry point and the legacy program is linked in.
cobc -x "${flags[@]}" -o "$out/runint" \
     "$here/support/RUNINT.cbl" "$here/legacy/CBACT04C.cbl"

for u in LOADTCAT LOADXREF LOADACCT LOADDISC DUMPACCT; do
  cobc -x "${flags[@]}" -o "$out/$(echo "$u" | tr 'A-Z' 'a-z')" \
       "$here/support/load-unload/$u.cbl"
done

cobc --version | head -1
sha256sum "$out/runint"
