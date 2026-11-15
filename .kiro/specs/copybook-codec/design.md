# Design Document

## Overview

One of six engine components. Two modules, `engine/revenant/copybook.py` (text to `Record_Schema`) and `engine/revenant/codec.py` (schema + logical record to bytes and back). Requirements are in `requirements.md` and are not changed here. Steering and `docs/build-log.md` win over `docs/design.md` section 5: signs use the `-fsign=EBCDIC` overpunch (`{`, `A`-`I`, `}`, `J`-`R`), never `p`-`y`.

Decisions:

1. **Two modules only**, plus an empty `engine/revenant/__init__.py` (no code, no version). `Field_Schema`, `Group_Span`, `Record_Schema` are `@dataclass(frozen=True)` in `copybook.py`. Run time uses the standard library only. No third module and no shipped test helper. The helper lives in `tests/support/copybook_text.py`.
2. **No float, no Decimal.** Integer-only division uses `//` and `divmod`. Digits are handled as strings and `int` arithmetic (`10**n`, `abs`, `rjust`, `int(str)`). `bool` is an `int` subclass, so every numeric value check is `type(value) is int`, and every text check is `type(value) is str`. This rejects `bool`, `float`, `Decimal`, `None`, `str` and `bytes` in a numeric field, and error text uses `type(value).__name__`. A static test (Property 22) enforces it. It does not forbid the `/` operator, which path joins use.
3. **Nesting is stored as `level`** (see "Nesting representation").
4. **Importability by `ENV PYTHONPATH=/work/engine`** in the Dockerfile (see "Packaging").
5. **The codec is engine-only.** Ports never import it (see "Port independence").

## Architecture

```text
copybook text --> normalise lines --> split declarations --> tokenise --> level-stack builder --> Record_Schema
                                                                                                   |
logical record (dict of int/str) <--decode_record / encode_record--> bytes (fixed width) <----------+
```

The parser fails closed: the first problem raises, nothing partial is returned, nothing is guessed. The codec encodes fully into a list of field byte strings and joins them only after every field succeeded, so no partial bytes escape.

## Components and Interfaces

### copybook.py

| Name | Signature / shape |
|---|---|
| `Field_Schema` | frozen: `name: str, level: int, offset: int, length: int, kind: str, scale: int`. `kind` in `alnum, uint, sdec, filler`. |
| `Group_Span` | frozen: `name: str, level: int, offset: int, length: int` |
| `Record_Schema` | frozen: `name: str, length: int, fields: tuple[Field_Schema,...], groups: tuple[Group_Span,...]`; method `field_named(name) -> Field_Schema` |
| `parse_copybook` | `(text: str, source: str = "<text>") -> Record_Schema` |
| `parse_copybook_file` | `(path) -> Record_Schema`; reads bytes, decodes ASCII (a non-ASCII byte raises `CopybookError` naming the path), calls `parse_copybook(text, source=str(path))` |
| `CopybookError(Exception)` | attributes `item: str \| None`, `source: str`, `line: int \| None`; message contains the item name, or the source when no item applies |
| `UnsupportedClause(CopybookError)` | same attributes; `item` is the item name; message also contains the clause keyword, PIC string or level number as written |

### codec.py

| Name | Signature |
|---|---|
| `encode_record` | `(schema, record: Mapping[str, int \| str]) -> bytes` |
| `decode_record` | `(schema, data: bytes \| bytearray) -> dict[str, int \| str]` (no fillers) |
| `encode_field` | `(field: Field_Schema, value) -> bytes` |
| `decode_field` | `(field: Field_Schema, data: bytes \| bytearray) -> int \| str` |
| `CodecError(Exception)` | attribute `field: str` (the record name for record-level errors); message contains it |

Module docstring states the overpunch matches `cobc -std=ibm -fsign=EBCDIC`, not the GnuCOBOL native convention (10.11).

### Parser approach

1. **Line normaliser.** `text.splitlines()` (handles CRLF). For each line, in this order: a tab in columns 1-72 raises with the line number; fewer than 7 columns is blank; column 7 of `*` or `/` is a comment; any other column 7 character except space raises `CopybookError` with the line number (continuation and debug lines are unsupported, fail closed). Otherwise keep `line[7:72]`, right-stripped. Columns 1-6 and 73-80 are dropped.
2. **Declaration splitter.** Join kept lines with one space. A declaration ends at the first `.` followed by whitespace or end of text. Record the start line of each. Text left over without a period raises with that start line (2.10). A `.` inside a token, such as `ZZ9.99`, is not a terminator, so it reaches the PIC check and is reported there.
3. **Tokenizer.** Split on whitespace. Token 1 is the level, token 2 the name. Tokens are upper-cased for matching and the original is kept for messages. Left to right: levels 66/77/88 raise `UnsupportedClause`; `PIC`/`PICTURE` takes an optional `IS` and then the picture string; any other token raises `UnsupportedClause` (known keywords such as `COMP*`, `BINARY`, `PACKED-DECIMAL`, `OCCURS`, `REDEFINES`, `VALUE`, `USAGE`, `SIGN`, `SYNC*`, `JUST*`, `BLANK`, `RENAMES` and also any unknown token). The picture string must full-match one of five regexes: `X\((\d{1,5})\)`, `9\((\d{1,5})\)`, `S9\((\d{1,5})\)`, `S9\((\d{1,5})\)V9\((\d{1,5})\)`, `S9\((\d{1,5})\)V(9+)`. A length of 0 or over 99,999 fails. A non-matching picture raises `UnsupportedClause` naming item and picture. A `FILLER` whose picture is not `X(n)` raises `UnsupportedClause` with `FILLER` and the line number.
4. **Level-stack builder.** Per declaration, in this order: (a) pop open groups whose level is greater than or equal to the new level, closing each with `length = cursor - start` and raising `CopybookError` if the length is 0 (no children, which also covers an item with no PIC and no children, 3.5 and 1.18); (b) tokenise the new item (so unsupported-clause errors come out in declaration order, 3.8); (c) if it has no PIC, push it as a group; otherwise append a `Field_Schema` at `cursor` and advance. The first declaration must be level 01; a second 01 or a missing 01 raises with the zero/more-than-one wording. A level other than 1-49 and an item with no open parent raise `CopybookError` (1.17). An 01 with PIC raises. Duplicate non-filler names raise at the second occurrence. At end of text all open groups are closed the same way.

### Nesting representation

Decision: store `level: int` on `Field_Schema` and `Group_Span`. No `parent`.

Why: a group's `offset`/`length` plus the levels of the fields inside it fix the nesting, so the round trip in 3.13 can compare levels and the generator and parser agree on structure. It adds one integer per item and no pointer structure.

Ordering: `fields` and `groups` are two tuples, each in declaration order. Their interleaving is recoverable by sorting on `(offset, level)`: a group sits at the same offset as its first child and has the lower level. No merged tuple is kept. The 01 record is `Record_Schema.name` and `length`; its level is implicitly 1.

Lookup: `Record_Schema.field_named(name)` uses a private dict `_index` (name to field, non-filler only) built in `__post_init__` through `object.__setattr__`, declared `dc_field(init=False, repr=False, compare=False)`. The method is named `field_named` so it cannot clash with `dataclasses.field` in the class body, and `copybook.py` imports it under an alias: `from dataclasses import dataclass, field as dc_field`. A missing name raises `KeyError(name)` (1.13 asks only for an error naming the name).

### Codec rules

| Kind | Encode | Decode |
|---|---|---|
| alnum | `type is str`; `len <= length`; every char in 0x20-0x7E; `value.encode("ascii").ljust(length, b" ")` | check length, check every byte in 0x20-0x7E, `rstrip(b" ")`, ascii decode |
| uint | `type is int`; `0 <= v < 10**length`; `str(v).rjust(length, "0")` | all bytes in `0x30-0x39`, then `int(text)` |
| sdec | `type is int`; `abs(v) < 10**length`; digits = `str(abs(v)).rjust(length, "0")`; last digit replaced by overpunch for the sign | first `length-1` bytes digits; last byte in the 20-character table; `int(digits)` with the sign |
| filler | `b" " * length` | skipped, never validated (6.15) |

Overpunch tables (digit index 0-9): `POS = "{ABCDEFGHI"`, `NEG = "}JKLMNOPQR"`. Encode uses `NEG` only when `v < 0`, so zero is `{`. Decode maps each of the 20 characters to `(digit, negative)`, and `}` with all-zero digits returns 0 (a negative zero is never produced). Other last bytes, including `p`-`y`, a plain digit, a space and `-`, raise.

Record encode order of checks: missing fields (schema order), then unknown keys (sorted, `FILLER` included), then field values in schema order. Record decode order: input type (9.6, before anything else), length, then fields in schema order, first malformed field wins. `bytes` and `bytearray` go through `bytes(data)` once at the entry. `decode_field` checks the type and the field length first (9.7). The Python 3.12 int/str conversion limit (4,300 digits) is not designed around (see the last section).

## Data Models

Logical values are `int` and `str`. A `Logical_Record` is a `dict[str, int | str]` keyed by non-filler field name. An `sdec` value is the count of the smallest unit (100.50 with scale 2 is 10050); the codec does not use `scale` for arithmetic, it only reports it. Encoded and decoded bytes are `bytes`.

Test-side model (in `tests/support/copybook_text.py`, never in `engine/`): `Item(name, level, kind, length, scale, children)` and a `Layout(record_name, items)`. `render(layout, style)` returns text. `expected_schema(layout)` computes offsets and the expected `(name, level, kind, offset, length, scale)` tuples and group tuples independently of the parser, by a plain walk of the tree.

## Packaging, image, pytest

**Importability.** Choice: `ENV PYTHONPATH=/work/engine` in `docker/Dockerfile`. `./rv` bind-mounts the repo at `/work` at run time and builds the image from `docker/` as context, so `engine/` is not in the image at build time. An editable install made at build time would point at a path that is empty then. Installing at each run would need a wrapper change. The env line works with the existing `./rv` unchanged and `import revenant.copybook` works from any working directory. A root `pyproject.toml` is **not in scope** (it is planned for a later milestone; the engine CLI will need it then). A small `pytest.ini` at the root is in scope:

```ini
[pytest]
testpaths = tests
addopts = -p no:cacheprovider
```

(`no:cacheprovider` stops root-owned `.pytest_cache` appearing in the host checkout. `database=None` in the Hypothesis profiles does the same for `.hypothesis`.)

**Dockerfile edit** (after the existing `mcp` install, same `--break-system-packages` style):

```dockerfile
ARG PYTEST_VERSION=9.2.0
ARG HYPOTHESIS_VERSION=6.170.15
RUN pip install --no-cache-dir --break-system-packages \
      "pytest==${PYTEST_VERSION}" "hypothesis==${HYPOTHESIS_VERSION}"
ENV PYTHONPATH=/work/engine
```

The versions are pinned with `==` as required by requirement 11.10, and recorded in `docs/build-log.md`.

**Rebuild.** `./rv` builds the image only when it is missing, so after this edit run once: `docker build -t revenant:dev -f docker/Dockerfile docker`.

**Hypothesis profiles** are registered in `tests/conftest.py`: `dev` (default, `max_examples=100`, `deadline=None`, `database=None`) and `ci` (`derandomize=True`, `max_examples=200`, `deadline=None`, `database=None`). CI selects `ci` with `--hypothesis-profile=ci`. Property tests use no per-test `max_examples` override, so every property gets at least 100 cases (7.10). `tests/conftest.py` also registers `--require-witness` (below). Tests import the helper as `tests.support.copybook_text`; empty `__init__.py` files in `tests/`, `tests/unit/`, `tests/property/`, `tests/integration/`, `tests/support/` make this work because `python3 -m pytest` puts `/work` on `sys.path`.

**Commands** (all from the repo root, all through `./rv`):

| Purpose | Command |
|---|---|
| unit + property | `./rv python3 -m pytest tests/unit tests/property` |
| integration | `./rv exhibits/cbact04c/build.sh` once, then `./rv python3 -m pytest tests/integration -rs` |
| everything | `./rv python3 -m pytest tests -rs` |
| CI | build first, then `./rv python3 -m pytest tests --hypothesis-profile=ci -rs --require-witness` |

**Integration precondition and skip rule.** The test needs `build/cbact04c` (with `runint` and the loaders), produced by `./rv exhibits/cbact04c/build.sh`. Requirement 10.5 says WHERE the program is built, so the test skips when `build/cbact04c/runint` is absent, with the reason "build/cbact04c not built: run ./rv exhibits/cbact04c/build.sh". The skip is visible with `-rs` and a skip is never a pass. With `--require-witness` (CI) the missing binary is a failure instead of a skip. The test encodes its TCATBALF and DISCGRP input records with the codec, then loads `scripts/m1_proof.py` by path with `importlib.util.spec_from_file_location` and calls `run_witness` and `one_account_world`.

### Port independence

The codec is used by the oracle, differ and world side only. The checked port, the first attempt and the mutants format their own record bytes and must not import `revenant`. Enforcement: one cheap unit test, `tests/unit/test_port_independence.py`, parses every `ports/**/*.py` with `ast` and fails on `import revenant` or `from revenant...`. It belongs to this spec's tasks and passes vacuously when the files do not use the engine. `ports/cbact04c/first_attempt/` is frozen: the test only reads it, and if it ever fails there, report it and do not edit the port.

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system. Properties serve as the bridge between human-readable specifications and machine-verifiable checks. Passing runs are reported as "no failure in N generated cases".*

Reflection: round-trip properties for alnum, uint and sdec are kept as one parametrised property per kind because the generators differ. 5.15 and 7.9 are merged into the layout invariant P12. 5.8-5.10, 6.12-6.14 and the 4.x tables are examples, not properties. 8.1-8.4 and 8.9-8.10 are merged into P15. 9.2-9.5 and 9.9 are merged into P19.

### Property 1: Schema contiguity

For any generated layout, and for each of the five real copybooks, field offsets start at 0, each offset equals the previous offset plus the previous length, the lengths sum to `schema.length`, and each group's offset is its first child's offset and its length is the sum of its children's lengths.

**Validates: Requirements 1.1, 1.3, 1.4, 1.5, 4.10**

Test file: tests/property/test_copybook.py. Strategy: layouts (a) rendered by (c).

### Property 2: Parser round trip

For any generated layout, parsing `render(layout)` gives the same names, levels, kinds, offsets, lengths, scales and group spans as `expected_schema(layout)`.

**Validates: Requirements 1.6, 1.7, 1.8, 1.9, 1.10, 3.13**

Test file: tests/property/test_copybook.py. Strategy: layouts (a), plain style.

### Property 3: Fixed_Format invariance

For any generated layout and any combination of formatting styles (CRLF, blank and comment lines, extra indentation within columns 8-72, trailing whitespace, sequence-area text, multi-line declarations, mixed-case keywords), the parsed schema equals the schema of the plain rendering.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.10**

Test file: tests/property/test_copybook.py. Strategy: layouts (a) with style flags (c).

### Property 4: Unsupported clause rejection

For any generated layout with one unsupported clause injected on a named item, parsing raises `UnsupportedClause` whose `item` and message contain that name, and no schema is returned.

**Validates: Requirements 3.2, 3.3, 3.4, 3.9, 3.12**

Test file: tests/property/test_copybook.py. Strategy: layouts (a) plus one injected clause from a list.

### Property 5: Alnum round trip

For any alnum field of length L and any printable-ASCII string of length 0..L without a trailing space, `decode_field(encode_field(s)) == s`.

**Validates: Requirements 7.1, 5.2, 6.3, 6.4**

Test file: tests/property/test_codec.py. Strategy: (b).

### Property 6: Uint round trip

For any uint field of n digits and any value from 0 to 10^n - 1 (including both ends), decoding the encoded field returns the value.

**Validates: Requirements 7.2, 5.4, 6.5**

Test file: tests/property/test_codec.py. Strategy: (b).

### Property 7: Sdec round trip

For any sdec field of L digits and any value from -(10^L - 1) to 10^L - 1 (including 0, 1, -1 and both extremes), decoding the encoded field returns the value.

**Validates: Requirements 7.3, 5.6, 6.7, 6.8, 6.9, 6.10**

Test file: tests/property/test_codec.py. Strategy: (b).

### Property 8: Record round trip

For any generated schema and any valid Logical_Record, `decode_record(encode_record(r)) == r`.

**Validates: Requirements 7.4, 6.1, 5.13**

Test file: tests/property/test_codec.py. Strategy: (a)+(b).

### Property 9: Canonical bytes round trip

For any generated schema and any bytes produced by the encoder, `encode_record(decode_record(b)) == b`.

**Validates: Requirements 7.5**

Test file: tests/property/test_codec.py. Strategy: (a)+(b), encode first.

### Property 10: Idempotence

For any valid Logical_Record, `encode(decode(encode(r))) == encode(r)`. For any decodable bytes, including `}` in a zero sdec, `decode(encode(decode(b))) == decode(b)`.

**Validates: Requirements 7.6, 7.7**

Test file: tests/property/test_codec.py. Strategy: (b), and (d) with valid-only mutations including `}`.

### Property 11: Sign class

For any sdec value v, the last byte of the encoded field is in `{A-I` when v >= 0 (and `{` when v is 0) and in `}J-R` when v < 0.

**Validates: Requirements 5.11, 7.8**

Test file: tests/property/test_codec.py. Strategy: (b).

### Property 12: Layout invariants

For any generated schema and valid record, the encoded length equals the schema length, each field span has its field length, and the first L-1 bytes of an encoded sdec are ASCII digits.

**Validates: Requirements 5.1, 5.15, 7.9**

Test file: tests/property/test_codec.py. Strategy: (a)+(b).

### Property 13: Determinism

For any generated schema and valid record, encoding the same inputs twice gives identical bytes.

**Validates: Requirements 5.14**

Test file: tests/property/test_codec.py. Strategy: (a)+(b).

### Property 14: Filler constant

For any generated schema and valid record, every filler span of the encoded record is spaces, the same for all records. Decode ignores any filler bytes.

**Validates: Requirements 5.12, 5.16, 6.15**

Test file: tests/property/test_codec.py. Strategy: (a)+(b).

### Property 15: Overflow and bad text rejection

For any field, a value just beyond its limit raises `CodecError` naming the field and returns no bytes. The values are: uint 10^n, sdec +/-10^L, negative uint, alnum of length N+1 or more, or an alnum character outside 0x20-0x7E.

**Validates: Requirements 5.3, 5.5, 5.7, 8.1, 8.2, 8.3, 8.4, 8.9, 8.10**

Test file: tests/property/test_codec.py. Strategy: (b) boundary values just beyond the limit.

### Property 16: Type rejection

For any field and any value of the wrong type (float, Decimal, bool, str, bytes or None in a numeric field; non-str in an alnum field), encoding raises `CodecError` naming the field and the type name.

**Validates: Requirements 8.5, 8.6**

Test file: tests/property/test_codec.py. Strategy: `st.one_of` of those types.

### Property 17: Record key check

For any generated schema and record, a missing field or an extra key (including `FILLER`) raises `CodecError` naming it.

**Validates: Requirements 8.7, 8.8**

Test file: tests/property/test_codec.py. Strategy: (b) with a dropped or added key.

### Property 18: Field-level and record-level agreement

For any generated schema and valid record, `encode_record` equals the concatenation of `encode_field` over fields in offset order (fillers as spaces), `decode_record[name]` equals `decode_field` on the field's slice, and `bytearray` and `bytes` input give equal results.

**Validates: Requirements 5.17, 6.16, 6.17**

Test file: tests/property/test_codec.py. Strategy: (a)+(b).

### Property 19: Malformed bytes rejection

For any canonical record with one byte in a uint or sdec span replaced by an invalid byte, or an alnum byte replaced by one outside 0x20-0x7E, decoding raises `CodecError` naming that field. With two bad fields, the first in schema order is named.

**Validates: Requirements 6.6, 6.11, 9.2, 9.3, 9.4, 9.5, 9.8, 9.9**

Test file: tests/property/test_codec.py. Strategy: (d) single-byte replacement.

### Property 20: Wrong length rejection

For any byte string whose length differs from the schema length, decoding raises `CodecError` naming the record, expected and actual length. For any non-bytes input, it raises naming the type before any length check. For any wrong-length field span, `decode_field` raises naming the field.

**Validates: Requirements 6.2, 9.1, 9.6, 9.7, 9.10**

Test file: tests/property/test_codec.py. Strategy: (d) wrong lengths.

### Property 21: Error atomicity

For any rejected copybook text (unsupported clause or broken structure), the parse call raises and returns no schema.

**Validates: Requirements 3.12**

Test file: tests/property/test_copybook.py. Strategy: same inputs as Property 4 plus broken structure.

### Property 22: Static source checks

For any of the two engine source files `codec.py` and `copybook.py`, an `ast` walk finds only standard-library imports, no `decimal` or `fractions` import, no `float` name or call, no float literal, no float-returning `math` function, and neither "proven" nor "equivalent" in the text. Integer-only division uses `//` and `divmod`. The check does not forbid the `/` operator, because path joins use it.

**Validates: Requirements 8.11, 11.6, 11.8**

Test file: tests/unit/test_static.py. Strategy: `ast` walk (example, not generated).

### Property 23: Port independence

For any Python file under `ports/`, parsing it with `ast` finds no `import revenant` and no `from revenant...`.

**Validates: Requirements 11.12**

Test file: tests/unit/test_port_independence.py. Strategy: `ast` walk (example).

Example and integration tests (not properties):

| Id | What | Requirements | File |
|---|---|---|---|
| E1 | Five CardDemo copybooks: names, lengths, the named offsets, the trailing-space case, group spans | 4.1-4.9 | tests/unit/test_copybook_carddemo.py |
| E2 | Parser error examples: no 01, two 01, 01 with PIC, orphan 05, empty group, duplicate name, tab on a line, no final period, comment/short line, PIC forms, levels 66/77/88, FILLER non-X | 1.13-1.19, 2.8-2.10, 3.5-3.8 | tests/unit/test_copybook_errors.py |
| E3 | Immutability: assigning to a schema attribute raises | 1.11 | tests/unit/test_copybook_errors.py |
| E4 | Byte examples: 125, -125, 0 encode; `0000000000}` decodes to 0; `p`-`y` rejected | 5.8-5.10, 6.12-6.14, 9.4 | tests/unit/test_codec_examples.py |
| E5 | Seed files: every line (CRLF stripped, padded) decodes; re-encoding matches every non-filler byte; filler spans compared by length; line counts asserted so no line is skipped | 10.1-10.4 | tests/unit/test_seed.py |
| E6 | Witness integration: for each of four inputs, builds the TCATBALF and DISCGRP records with `encode_record` on the parsed CVTRA01Y and CVTRA02Y schemas and substitutes them into the world passed to `run_witness` (ACCTFILE and XREFFILE records stay from the one-account builder in `scripts/m1_proof.py`). It checks that the old program reads what the codec writes, that the TRAN-AMT bytes equal the codec's encoding, and that the codec's decode equals the expected integer. Failures name the input and first differing offset | 10.5-10.10 | tests/integration/test_witness.py |
| E7 | `SHA256SUMS` guard: reads the file, recomputes digests, fails naming each mismatched or missing path; also run after parsing the five copybooks | 4.11, 11.9 | tests/unit/test_legacy_guard.py |
| E8 | Module docstring contains the overpunch note; `import revenant.copybook, revenant.codec` works with no `exhibits/` on the path | 10.11, 11.2 | tests/unit/test_static.py |

## Hypothesis strategies

(a) **Layouts.** A record name plus 1-6 top-level entries at level 05. Each entry is an elementary item or a group; a group holds 1-3 children at level 10, and at most one of them is a sub-group at level 10 with children at level 15. Kinds: `alnum` (`X(n)`), `uint` (`9(n)`), `sdec` (`S9(n)`, `S9(n)V9(m)` and `S9(n)V` plus nines), `filler`. Total digits 1..12, `m` 1..4. Names are unique across the layout (`st.lists(..., unique=True)`), uppercase COBOL style `[A-Z][A-Z0-9]{0,6}` with up to two `-XXX` parts, never ending in a hyphen and never in a reserved set (`FILLER`, `PIC`, `COMP*`, `VALUE`, `OCCURS`, other clause keywords, `IS`). `FILLER` items are added separately and may repeat.

(b) **Values.** From a schema: alnum draws printable ASCII (0x20-0x7E) of length 0..L, filtered to no trailing space; uint draws `st.integers(0, 10**L-1)` mixed with `st.sampled_from([0, 1, 10**L-1])`; sdec draws `st.integers(-(10**L-1), 10**L-1)` mixed with `[0, 1, -1, 10**L-1, -(10**L-1)]`. A record strategy composes one value per non-filler field. Out-of-range values for P15 are `10**L`, `-(10**L)` and strings of length L+1 or more.

(c) **Copybook text** (`tests/support/copybook_text.py`, `render(layout, style)`). The style has independent flags drawn by Hypothesis: indentation 0-20 extra spaces, provided every token stays within column 72; comment lines (`*` or `/` in column 7) and blank lines inserted between declarations; CRLF; trailing whitespace including after the period; sequence-area text in columns 73-80 and any text in 1-6; a declaration split across two or three lines at token boundaries; random case for keywords (`pic`, `Pic`, `s9`, `v`); `PIC` or `PICTURE`. `unsupported=(item_name, clause)` injects one clause on that item (`COMP-3`, `OCCURS 2 TIMES`, `REDEFINES X`, `VALUE 0`, a `ZZ9.99` picture, an unsigned `9(3)V99`, and so on).

(d) **Mutated bytes.** Start from canonical bytes for a generated record. Replace one byte at a chosen field span position with a byte drawn from the 256 minus the valid set for that kind and position (for the sdec last byte the valid set is the 20 overpunch characters). For P10 the mutation is instead to swap a zero sdec's final `{` for `}`. For P20 draw lengths other than the schema length (empty, one short, one long, random) and non-bytes types.

## Error Handling

| Condition | Raised | Names |
|---|---|---|
| Tab in columns 1-72, unsupported column-7 indicator | `CopybookError` | line number |
| Declaration with no period | `CopybookError` | start line |
| Zero or several 01 records | `CopybookError` | source, zero or more than one |
| 01 with PIC, bad nesting, empty group, no PIC, duplicate name | `CopybookError` | item |
| Level 66/77/88, clause keyword, unknown token, unsupported PIC, bad FILLER | `UnsupportedClause` | item, plus keyword, PIC string, level or `FILLER` and line |
| Non-ASCII byte in a copybook file | `CopybookError` | path |
| Unknown field name in `schema.field` | `KeyError` | name |
| Value of the wrong type (including `bool`, `float`, `Decimal`, `None`) | `CodecError` | field, type name |
| Value out of range, too long, non-printable char | `CodecError` | field |
| Missing or unknown record key | `CodecError` | key |
| Input is not bytes or bytearray | `CodecError` | record, type |
| Wrong record or field length | `CodecError` | record or field, expected and received |
| Bad digit, bad sign byte, non-printable alnum byte | `CodecError` | field and the byte |

## Testing Strategy

Dual approach: Hypothesis properties 1-21 for the generated space, `ast`-walk checks for Properties 22-23, plain pytest examples for fixed facts (E1-E8). Hypothesis is the property library; nothing is hand-rolled. Each property test is one test function, tagged in a comment `Feature: copybook-codec, Property N: <statement>`, run under the registered profile (100 cases by default, 200 under `ci`, derandomized in `ci`). Codec properties build their schemas by rendering a generated layout and parsing it, so the parser is on that path; P2 and E1 cover the parser alone. Result messages say "no failure in N generated cases".

### Files

```text
engine/revenant/__init__.py          empty
engine/revenant/copybook.py
engine/revenant/codec.py
tests/__init__.py  tests/unit/__init__.py  tests/property/__init__.py
tests/integration/__init__.py  tests/support/__init__.py          empty
tests/conftest.py                    Hypothesis profiles, --require-witness
tests/support/copybook_text.py       layout model, render, expected_schema, strategies
tests/unit/                          test_copybook_carddemo.py  test_copybook_errors.py
                                     test_codec_examples.py  test_seed.py  test_legacy_guard.py
                                     test_static.py  test_port_independence.py
tests/property/                      test_copybook.py  test_codec.py
tests/integration/test_witness.py
pytest.ini
docker/Dockerfile                    edit: pytest and hypothesis pinned with ==, ENV PYTHONPATH=/work/engine
```

### Not designed here

Packed, binary, `OCCURS`, `REDEFINES`, edited and unsigned-decimal pictures (rejected, not handled). Fields longer than 4,300 digits (Python's int/str conversion limit). The oracle runner, world model, differ and Hypothesis runner that use this codec. Port-side formatting. A root `pyproject.toml`. Any change to `scripts/m1_proof.py` or `./rv`.

## Requirement adjustments needed: none, applied

The seven adjustments listed in the earlier draft are now in `requirements.md`.
