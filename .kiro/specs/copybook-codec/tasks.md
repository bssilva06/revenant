# Implementation Plan: Copybook Parser and Record Codec

## Overview

Implementation language is Python 3.12 (the design is in Python). The work is ordered as the user required: image and pytest setup, then the parser, then the codec, then seed and witness integration tests. Estimated effort is about 6 hours of the roughly 18 hours for the whole engine. Every task ends with a command to run through `./rv`.

Rules for all tasks: never edit anything under `exhibits/cbact04c/legacy/` or `ports/`. Test messages and comments say "no failure in N generated cases". The words "proven" and "equivalent" do not appear in source or tests.

Optional marking: example tests that carry the acceptance values (the five copybooks, byte examples, seed lines, witness inputs) and the property tests for requirements 3.9, 3.13, 2.x and 7.1 to 7.8 are not optional. Property tests for invariants and error classes that other tests already cover in examples are marked optional.

## Tasks

- [ ] 1. Docker image and pytest setup
  - Edit the image, add the package skeleton and the test configuration, and guard the pinned legacy files.
  - _Requirements: 11.1, 11.3, 11.4, 11.5, 11.9, 11.10, 11.11_
  - Run: `./rv python3 -m pytest tests/unit/test_legacy_guard.py`

  - [ ] 1.1 Pin tools in `docker/Dockerfile`, rebuild the image and log it
    - Add `ARG PYTEST_VERSION=9.2.0`, `ARG HYPOTHESIS_VERSION=6.170.15`, a `pip install --break-system-packages` line using `==` pins, and `ENV PYTHONPATH=/work/engine`, after the existing `mcp` install.
    - Rebuild once with `docker build -t revenant:dev -f docker/Dockerfile docker`.
    - Append an entry to `docs/build-log.md` stating the tool used (Kiro), the two pinned versions, the `PYTHONPATH` line and the image rebuild.
    - _Requirements: 11.10, 11.11_
    - Run: `./rv python3 -m pytest --version`

  - [ ] 1.2 Create the package skeleton and test configuration
    - Create the empty `engine/revenant/__init__.py`.
    - Create `pytest.ini` (`testpaths = tests`, `addopts = -p no:cacheprovider`).
    - Create empty `__init__.py` in `tests/`, `tests/unit/`, `tests/property/`, `tests/integration/`, `tests/support/`.
    - Create `tests/conftest.py`: Hypothesis profiles `dev` (`max_examples=100`, `deadline=None`, `database=None`, default) and `ci` (`derandomize=True`, `max_examples=200`, `deadline=None`, `database=None`), and the `--require-witness` option via `pytest_addoption`.
    - _Requirements: 11.1, 11.3, 11.5, 11.11, 7.10_
    - Run: `./rv python3 -c "import revenant; print('ok')"`

  - [ ] 1.3 Write the `SHA256SUMS` legacy guard test (E7)
    - In `tests/unit/test_legacy_guard.py`, read `exhibits/cbact04c/SHA256SUMS`, recompute each digest with `hashlib`, and fail with a message naming every mismatched or missing path.
    - Expose a reusable function so the five-copybook test (task 2.3) can call it after parsing.
    - _Requirements: 4.11, 11.9_
    - Run: `./rv python3 -m pytest tests/unit/test_legacy_guard.py`

- [ ] 2. Copybook parser and its tests
  - Build the test helper first, then `copybook.py`, then the example and property tests.
  - _Requirements: 1.1 to 1.19, 2.1 to 2.11, 3.1 to 3.16, 4.1 to 4.11_
  - Run: `./rv python3 -m pytest tests/unit/test_copybook_carddemo.py tests/unit/test_copybook_errors.py tests/property/test_copybook.py`

  - [ ] 2.1 Write the Copybook_Text_Helper and layout strategies
    - Create `tests/support/copybook_text.py` with `Item`, `Layout`, `render(layout, style)` (indentation, comment and blank lines, CRLF, trailing whitespace, sequence-area text, multi-line declarations, mixed case, `PIC`/`PICTURE`, injected unsupported clause), `expected_schema(layout)` computed by a plain tree walk, and Hypothesis strategies (a) layouts and (c) styles as in the design.
    - Names are unique, uppercase, not reserved; `FILLER` items are added separately.
    - _Requirements: 3.13, 3.14, 3.15, 3.16_
    - Run: `./rv python3 -c "import tests.support.copybook_text"`

  - [ ] 2.2 Implement `engine/revenant/copybook.py`
    - Frozen dataclasses `Field_Schema`, `Group_Span`, `Record_Schema` (with `field_named` and private `_index`, imported as `from dataclasses import dataclass, field as dc_field`), `CopybookError`, `UnsupportedClause`.
    - Line normaliser, declaration splitter, tokenizer with the five PIC regexes, and the level-stack builder, in the order the design gives. `parse_copybook` and `parse_copybook_file`. Standard library only, integer arithmetic only.
    - _Requirements: 1.1 to 1.19, 2.1 to 2.11, 3.1 to 3.8, 3.10 to 3.12, 11.2, 11.6_
    - Run: `./rv python3 -c "from revenant.copybook import parse_copybook_file as p; print(p('exhibits/cbact04c/legacy/cpy/CVTRA01Y.cpy').length)"`

  - [ ] 2.3 Write the five CardDemo copybook tests (E1)
    - In `tests/unit/test_copybook_carddemo.py`, assert record names and lengths 50, 50, 300, 50, 350; the `CVTRA01Y` five leaf fields with offsets, kinds and scales and group `TRAN-CAT-KEY` (0, 17); `DIS-INT-RATE` (16, 6, scale 2) and `DIS-GROUP-KEY` (0, 16); `TRAN-AMT` (132, 11, scale 2); `ACCT-CURR-BAL` (12, 12, scale 2) and `ACCT-EXPIRAION-DATE` (58, 10) with the trailing-space line; contiguity of offsets. Call the legacy guard from task 1.3 after parsing.
    - _Requirements: 4.1 to 4.11, 1.3, 1.4, 1.5_
    - Run: `./rv python3 -m pytest tests/unit/test_copybook_carddemo.py`

  - [ ] 2.4 Write parser error and immutability examples (E2, E3)
    - In `tests/unit/test_copybook_errors.py`: no 01, two 01, 01 with PIC, orphan 05, empty group, item without PIC, duplicate name, tab on a line (line number), missing final period (start line), column-7 indicator, short and comment lines, each PIC form, levels 66/77/88, each clause keyword family (`COMP*`, `OCCURS`, `REDEFINES`, `VALUE` and the rest of 3.3), non-`X(n)` FILLER, first-error-wins, case-insensitivity, assignment to a schema attribute raises, unknown `field_named` raises `KeyError`.
    - _Requirements: 1.11, 1.13 to 1.19, 2.8 to 2.11, 3.2 to 3.8, 3.10_
    - Run: `./rv python3 -m pytest tests/unit/test_copybook_errors.py`

  - [ ]* 2.5 Write property test for schema contiguity
    - **Property 1: Schema contiguity**
    - **Validates: Requirements 1.1, 1.3, 1.4, 1.5, 4.10**
    - In `tests/property/test_copybook.py`, over generated layouts and the five real copybooks.
    - Run: `./rv python3 -m pytest tests/property/test_copybook.py -k contiguity`

  - [ ] 2.6 Write property test for parser round trip
    - **Property 2: Parser round trip**
    - **Validates: Requirements 1.6, 1.7, 1.8, 1.9, 1.10, 3.13**
    - Run: `./rv python3 -m pytest tests/property/test_copybook.py -k round_trip`

  - [ ] 2.7 Write property test for Fixed_Format invariance
    - **Property 3: Fixed_Format invariance**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.10**
    - Run: `./rv python3 -m pytest tests/property/test_copybook.py -k fixed_format`

  - [ ] 2.8 Write property test for unsupported clause rejection
    - **Property 4: Unsupported clause rejection**
    - **Validates: Requirements 3.2, 3.3, 3.4, 3.9, 3.12**
    - Run: `./rv python3 -m pytest tests/property/test_copybook.py -k unsupported`

  - [ ]* 2.9 Write property test for error atomicity
    - **Property 21: Error atomicity**
    - **Validates: Requirements 3.12**
    - Run: `./rv python3 -m pytest tests/property/test_copybook.py -k atomicity`

- [ ] 3. Record codec and its tests
  - Build `codec.py`, extend the helper with value and mutation strategies, then the example, property and static tests.
  - _Requirements: 5.1 to 5.17, 6.1 to 6.17, 7.1 to 7.11, 8.1 to 8.11, 9.1 to 9.10, 10.11, 11.6, 11.8, 11.12_
  - Run: `./rv python3 -m pytest tests/unit tests/property`

  - [ ] 3.1 Implement `engine/revenant/codec.py`
    - `CodecError` (with `field` attribute), `encode_field`, `decode_field`, `encode_record`, `decode_record`. Overpunch tables `POS = "{ABCDEFGHI"` and `NEG = "}JKLMNOPQR"`; `}` with all-zero digits decodes to 0. `type(value) is int` and `type(value) is str` checks. Check order as in the design: encode missing keys, unknown keys, values; decode input type, length, fields. Encode all fields before joining. Module docstring states the overpunch matches `cobc -std=ibm -fsign=EBCDIC`, not the GnuCOBOL native convention. No float, no Decimal.
    - _Requirements: 5.1 to 5.17, 6.1 to 6.17, 8.1 to 8.11, 9.1 to 9.8, 10.11, 11.6_
    - Run: `./rv python3 -c "from revenant.copybook import parse_copybook_file as p; from revenant.codec import encode_field; print(encode_field(p('exhibits/cbact04c/legacy/cpy/CVTRA05Y.cpy').field_named('TRAN-AMT'), 125))"`

  - [ ] 3.2 Add value and mutation strategies to the helper
    - In `tests/support/copybook_text.py`, add strategies (b) per-kind values and record values, including boundary values and out-of-range values, and (d) single-byte mutation, zero-sdec `}` swap and wrong-length inputs.
    - _Requirements: 7.10, 9.9, 9.10_
    - Run: `./rv python3 -c "import tests.support.copybook_text as t; print(sorted(n for n in dir(t) if not n.startswith('_'))[:5])"`

  - [ ] 3.3 Write byte examples (E4)
    - In `tests/unit/test_codec_examples.py`: 125 encodes to `0000000012E`, -125 to `0000000012N`, 0 to `0000000000{`; decode of each, `0000000000}` decodes to 0; `p` to `y`, a plain digit, a space and `-` as last byte are rejected; the alnum, uint and filler examples.
    - _Requirements: 5.8, 5.9, 5.10, 6.12, 6.13, 6.14, 9.4_
    - Run: `./rv python3 -m pytest tests/unit/test_codec_examples.py`

  - [ ] 3.4 Write property test for alnum round trip
    - **Property 5: Alnum round trip**
    - **Validates: Requirements 7.1, 5.2, 6.3, 6.4**
    - In `tests/property/test_codec.py`.
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k alnum_round_trip`

  - [ ] 3.5 Write property test for uint round trip
    - **Property 6: Uint round trip**
    - **Validates: Requirements 7.2, 5.4, 6.5**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k uint_round_trip`

  - [ ] 3.6 Write property test for sdec round trip
    - **Property 7: Sdec round trip**
    - **Validates: Requirements 7.3, 5.6, 6.7, 6.8, 6.9, 6.10**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k sdec_round_trip`

  - [ ] 3.7 Write property test for record round trip
    - **Property 8: Record round trip**
    - **Validates: Requirements 7.4, 6.1, 5.13**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k record_round_trip`

  - [ ] 3.8 Write property test for canonical bytes round trip
    - **Property 9: Canonical bytes round trip**
    - **Validates: Requirements 7.5**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k canonical_bytes`

  - [ ] 3.9 Write property test for idempotence
    - **Property 10: Idempotence**
    - **Validates: Requirements 7.6, 7.7**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k idempotence`

  - [ ] 3.10 Write property test for sign class
    - **Property 11: Sign class**
    - **Validates: Requirements 5.11, 7.8**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k sign_class`

  - [ ]* 3.11 Write property test for layout invariants
    - **Property 12: Layout invariants**
    - **Validates: Requirements 5.1, 5.15, 7.9**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k layout_invariants`

  - [ ]* 3.12 Write property test for determinism
    - **Property 13: Determinism**
    - **Validates: Requirements 5.14**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k determinism`

  - [ ]* 3.13 Write property test for filler constant
    - **Property 14: Filler constant**
    - **Validates: Requirements 5.12, 5.16, 6.15**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k filler`

  - [ ]* 3.14 Write property test for overflow and bad text rejection
    - **Property 15: Overflow and bad text rejection**
    - **Validates: Requirements 5.3, 5.5, 5.7, 8.1, 8.2, 8.3, 8.4, 8.9, 8.10**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k overflow`

  - [ ]* 3.15 Write property test for type rejection
    - **Property 16: Type rejection**
    - **Validates: Requirements 8.5, 8.6**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k type_rejection`

  - [ ]* 3.16 Write property test for record key check
    - **Property 17: Record key check**
    - **Validates: Requirements 8.7, 8.8**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k record_key`

  - [ ]* 3.17 Write property test for field-level and record-level agreement
    - **Property 18: Field-level and record-level agreement**
    - **Validates: Requirements 5.17, 6.16, 6.17**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k field_record_agreement`

  - [ ]* 3.18 Write property test for malformed bytes rejection
    - **Property 19: Malformed bytes rejection**
    - **Validates: Requirements 6.6, 6.11, 9.2, 9.3, 9.4, 9.5, 9.8, 9.9**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k malformed`

  - [ ]* 3.19 Write property test for wrong length rejection
    - **Property 20: Wrong length rejection**
    - **Validates: Requirements 6.2, 9.1, 9.6, 9.7, 9.10**
    - Run: `./rv python3 -m pytest tests/property/test_codec.py -k wrong_length`

  - [ ] 3.20 Write the static source check and import check (Property 22, E8)
    - **Property 22: Static source checks**
    - **Validates: Requirements 8.11, 11.6, 11.8**
    - In `tests/unit/test_static.py`, walk `codec.py` and `copybook.py` with `ast`: standard-library imports only, no `decimal` or `fractions`, no `float` name or call, no float literal, no float-returning `math` function, no "proven" or "equivalent" in the text. Check the codec docstring overpunch note, and that `import revenant.copybook, revenant.codec` works (11.2, 10.11).
    - Run: `./rv python3 -m pytest tests/unit/test_static.py`

  - [ ] 3.21 Write the port independence test (Property 23)
    - **Property 23: Port independence**
    - **Validates: Requirements 11.12**
    - In `tests/unit/test_port_independence.py`, parse every `ports/**/*.py` with `ast`, fail on `import revenant` or `from revenant...`. Read only; do not edit anything under `ports/`.
    - Run: `./rv python3 -m pytest tests/unit/test_port_independence.py`

- [ ] 4. Seed tests and witness integration tests
  - Precondition for the integration test: `./rv exhibits/cbact04c/build.sh` has produced `build/cbact04c/runint`.
  - _Requirements: 10.1 to 10.10, 11.4, 11.12 of requirements_
  - Run: `./rv python3 -m pytest tests/unit/test_seed.py tests/integration -rs`

  - [ ] 4.1 Write the seed file tests (E5)
    - In `tests/unit/test_seed.py`, for each of the four seed files: strip LF or CRLF, pad to the record length, decode with the matching copybook schema, re-encode and compare every byte outside filler spans, compare filler spans by length only. Assert expected line counts (including 49 CRLF lines in `tcatbal.txt` and the 36-character lines in `cardxref.txt`) so no line is skipped.
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
    - Run: `./rv python3 -m pytest tests/unit/test_seed.py`

  - [ ] 4.2 Write the witness integration test (E6)
    - In `tests/integration/test_witness.py`, load `scripts/m1_proof.py` by path with `importlib.util.spec_from_file_location`. For the four inputs (10050 at 1500 gives `0000000012E` and 125; -10050 at 1500 gives `0000000012N` and -125; -100 at 600 gives `0000000000{` and 0; -120 at 1000 gives `0000000000J` and -1), build the TCATBALF and DISCGRP records with `encode_record` on the parsed `CVTRA01Y` and `CVTRA02Y` schemas, substitute them into the one-account world, call `run_witness`, and check exit code 0, exactly one 350-byte record, TRAN-AMT bytes (offset 132, length 11) against the codec encoding, and the decode against the expected integer. Failures name the input and the first differing offset.
    - Skip with the reason "build/cbact04c not built: run ./rv exhibits/cbact04c/build.sh" when `build/cbact04c/runint` is absent; fail instead when `--require-witness` is given.
    - Do not edit `scripts/m1_proof.py`.
    - _Requirements: 10.5, 10.6, 10.7, 10.8, 10.9, 10.10, 10.12_
    - Run: `./rv exhibits/cbact04c/build.sh` then `./rv python3 -m pytest tests/integration -rs`

- [ ] 5. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
  - Report results as "no failure in N generated cases"; run the CI profile once with `--hypothesis-profile=ci`.
  - Run: `./rv python3 -m pytest tests/unit tests/property` and `./rv python3 -m pytest tests/integration --require-witness`

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster first pass.
- Every task ends with a `Run:` command that goes through `./rv`.
- Property tests share `tests/property/test_copybook.py` and `tests/property/test_codec.py`, so they sit in separate waves.
- The integration test needs `./rv exhibits/cbact04c/build.sh` first.
- Never edit `exhibits/cbact04c/legacy/`, `ports/` or `scripts/m1_proof.py`.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "2.1"] },
    { "id": 3, "tasks": ["2.2"] },
    { "id": 4, "tasks": ["2.3", "2.4", "2.5", "3.1"] },
    { "id": 5, "tasks": ["2.6", "3.2", "3.3", "4.1", "4.2"] },
    { "id": 6, "tasks": ["2.7", "3.4", "3.20", "3.21"] },
    { "id": 7, "tasks": ["2.8", "3.5"] },
    { "id": 8, "tasks": ["2.9", "3.6"] },
    { "id": 9, "tasks": ["3.7"] },
    { "id": 10, "tasks": ["3.8"] },
    { "id": 11, "tasks": ["3.9"] },
    { "id": 12, "tasks": ["3.10"] },
    { "id": 13, "tasks": ["3.11"] },
    { "id": 14, "tasks": ["3.12"] },
    { "id": 15, "tasks": ["3.13"] },
    { "id": 16, "tasks": ["3.14"] },
    { "id": 17, "tasks": ["3.15"] },
    { "id": 18, "tasks": ["3.16"] },
    { "id": 19, "tasks": ["3.17"] },
    { "id": 20, "tasks": ["3.18"] },
    { "id": 21, "tasks": ["3.19"] }
  ]
}
```
