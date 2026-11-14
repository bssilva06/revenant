# Upstream provenance: CBACT04C

| Item | Value |
| --- | --- |
| Project | AWS CardDemo |
| Repository | https://github.com/aws-samples/aws-mainframe-modernization-carddemo |
| Commit | `59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e` (2025-10-16) |
| Licence | Apache-2.0 (`LICENSE.upstream`, `NOTICE`) |
| Copied on | 2026-11-14 |

## Copied verbatim, never edited

| Here | Upstream path |
| --- | --- |
| `legacy/CBACT04C.cbl` | `app/cbl/CBACT04C.cbl` |
| `legacy/cpy/CVACT01Y.cpy`, `CVACT03Y.cpy`, `CVTRA01Y.cpy`, `CVTRA02Y.cpy`, `CVTRA05Y.cpy` | `app/cpy/` |
| `seed/acctdata.txt`, `cardxref.txt`, `discgrp.txt`, `tcatbal.txt` | `app/data/ASCII/` |

`SHA256SUMS` pins every file above. `build.sh` refuses to build if any hash differs.

## Added by Revenant, not part of CardDemo

- `support/RUNINT.cbl`: driver that passes the run date as the job control `PARM` did.
- `support/load-unload/*.cbl`: copy fixed-length records into and out of the indexed files.
- `build.sh`, this file and `SHA256SUMS`.
