# Requirements Document

## Introduction

The copybook parser and the record codec are the first Revenant engine component. The parser reads COBOL data declarations from copybook text and produces a field schema with a name, offset, length, kind and scale for each field. The codec encodes logical records into fixed-width bytes and decodes such bytes back into logical records, using that schema.

The component is exhibit-agnostic. It lives in `engine/revenant/copybook.py` and `engine/revenant/codec.py`. It is checked against the five CardDemo copybooks in `exhibits/cbact04c/legacy/cpy/`, which are never edited. It contains no model calls and no floating-point arithmetic.

Decisions recorded here, where the design's section 5 sample is out of date (steering and the build log take precedence):

- Signed display values use the mainframe overpunch produced by `cobc -fsign=EBCDIC`. The native `p` to `y` convention and the design's `encode_sdec` and `decode_sdec` samples are not used.
- The encoder writes `{` for a signed zero. The decoder also accepts `}` (negative zero) and returns 0.
- Alphanumeric values are limited to printable ASCII (0x20 to 0x7E). Other characters are rejected on encode and on decode.
- A decoded alphanumeric value has trailing spaces removed. Leading and interior spaces are kept.
- The encoder writes spaces into every filler. The decoder does not validate filler bytes, because CardDemo seed data holds zeros in some fillers.
- Observed facts about the seed files in `exhibits/cbact04c/seed/`: `cardxref.txt` lines are 36 characters, shorter than the 50-byte record. `tcatbal.txt` has CRLF line endings on 49 of 50 lines. The fillers in `tcatbal.txt` and `discgrp.txt` hold zeros.

Verification wording: results of this component's tests are described as "no failure in N generated cases". The documents and test names do not claim proof or equivalence.

## Glossary

- **Copybook_Parser**: The component in `engine/revenant/copybook.py` that converts copybook text into a Record_Schema.
- **Record_Codec**: The component in `engine/revenant/codec.py` that encodes logical records into bytes and decodes bytes into logical records.
- **Copybook**: Text of COBOL data declarations in fixed format, such as `CVACT01Y.cpy`.
- **Fixed_Format**: Source layout where column 7 is the indicator area, columns 8 to 72 hold code, and columns 73 to 80 are the sequence area.
- **Field_Schema**: An immutable description of one elementary item: `name`, `offset` (zero-based byte position in the record), `length` (bytes), `kind` and `scale`.
- **Group_Span**: The name, offset and length of a group item, which covers its children.
- **Record_Schema**: The name of an 01-level record, its total length in bytes, its Group_Spans, and its Field_Schemas in declaration order.
- **Kind**: One of `alnum`, `uint`, `sdec` or `filler`.
- **Alnum_Field**: A field of kind `alnum`, declared `PIC X(n)`.
- **Uint_Field**: A field of kind `uint`, declared `PIC 9(n)`.
- **Sdec_Field**: A field of kind `sdec`, declared `PIC S9(n)` or `PIC S9(n)V9(m)`. Its length is n+m bytes and its scale is m.
- **Filler_Field**: A field of kind `filler`, declared with the name `FILLER`.
- **Logical_Value**: A Python `str` for an Alnum_Field, or a Python `int` for a Uint_Field or an Sdec_Field. An Sdec_Field value is a count of the smallest unit, so 100.50 in a field with scale 2 is 10050.
- **Logical_Record**: A mapping from field name to Logical_Value, holding every non-filler field of a Record_Schema.
- **Overpunch**: The sign carried in the last digit of an Sdec_Field. Positive digits 0 to 9 map to `{` and `A` to `I`. Negative digits 0 to 9 map to `}` and `J` to `R`.
- **Canonical_Bytes**: Bytes that the Record_Codec encoder could have produced: fillers hold spaces, signed zero is `{`, and alnum padding is spaces.
- **Unsupported_Clause**: Any clause outside the grammar defined in Requirement 3, including `COMP`, `COMP-1` to `COMP-5`, `COMPUTATIONAL`, `BINARY`, `PACKED-DECIMAL`, `OCCURS`, `REDEFINES`, `VALUE`, `USAGE`, `SIGN`, `SYNCHRONIZED`, `JUSTIFIED`, `BLANK WHEN ZERO`, `RENAMES`, edited pictures, and level numbers 66, 77 and 88.
- **Codec_Error**: The base error type raised by the Record_Codec. Its message contains the name of the field concerned. It also carries that name as an attribute.
- **Copybook_Error**: The base error type raised by the Copybook_Parser. Its message contains the name of the item concerned, or the source name when no item applies. It also carries that name as an attribute.
- **Seed_Files**: The four files `acctdata.txt`, `cardxref.txt`, `discgrp.txt` and `tcatbal.txt` in `exhibits/cbact04c/seed/`.
- **Container**: The `revenant:dev` image, entered through `./rv`, in which all tests run.
- **Copybook_Text_Helper**: A test-only module under `tests/support/` that renders a layout (item names, level numbers, kinds and lengths) as Fixed_Format Copybook text, optionally with varied formatting and with unsupported clauses added. It is not part of the engine package.
- **Witness_Run**: One execution of the legacy program on a world, performed by `run_witness` in `scripts/m1_proof.py`, which returns the exit code, the transaction bytes, the account bytes and the console text. `scripts/m1_proof.py` also provides the one-account world builder.

## Requirements

### Requirement 1: Parse copybook text into a Record_Schema

**User Story:** As an engine developer, I want COBOL data declarations turned into field schemas, so that the codec and the generators can work from the declarations instead of hand-written layouts.

#### Acceptance Criteria

1. WHEN valid Copybook text with exactly one 01-level record is provided, THE Copybook_Parser SHALL return a Record_Schema holding the record name, the record length in bytes, the Group_Spans and the Field_Schemas, with the Field_Schemas and Group_Spans each in declaration order.
2. THE Copybook_Parser SHALL expose one function that accepts Copybook text and one function that accepts a file path, and both SHALL produce Record_Schemas that compare equal for identical content.
3. THE Copybook_Parser SHALL assign each Field_Schema a zero-based byte offset equal to the sum of the lengths of all elementary items that precede it in the record, including `FILLER` items.
4. THE Copybook_Parser SHALL set the length of each Group_Span to the sum of the lengths of its children and the offset of each Group_Span to the offset of its first child.
5. THE Copybook_Parser SHALL set the Record_Schema length to the sum of the lengths of all elementary items, including `FILLER` items.
6. WHEN an elementary item is declared `PIC X(n)` with n from 1 to 99,999, THE Copybook_Parser SHALL produce a Field_Schema of kind `alnum`, length n and scale 0.
7. WHEN an elementary item is declared `PIC 9(n)` with n from 1 to 99,999, THE Copybook_Parser SHALL produce a Field_Schema of kind `uint`, length n and scale 0.
8. WHEN an elementary item is declared `PIC S9(n)V9(m)` or `PIC S9(n)V` followed by m nines, with n at least 1 and m at least 1, THE Copybook_Parser SHALL produce a Field_Schema of kind `sdec`, length n+m and scale m. The implied decimal point SHALL NOT add to the length.
9. WHEN an elementary item is declared `PIC S9(n)` without a `V` part, THE Copybook_Parser SHALL produce a Field_Schema of kind `sdec`, length n and scale 0.
10. WHEN an elementary item is named `FILLER`, THE Copybook_Parser SHALL produce a Field_Schema of kind `filler` for it, using the length from its `PIC X(n)` declaration.
11. THE Copybook_Parser SHALL produce Field_Schema and Record_Schema values that are immutable. Any attempt to assign to an attribute of such a value SHALL raise an error and leave the value unchanged.
12. THE Record_Schema SHALL provide a lookup of a Field_Schema by name for every non-filler field.
13. IF the lookup in criterion 12 is given a name that is not a non-filler field of the record, THEN THE Record_Schema SHALL raise an error naming the requested name.
14. IF two non-filler elementary items in one Copybook share a name, THEN THE Copybook_Parser SHALL raise a Copybook_Error naming the duplicated item and SHALL return no Record_Schema.
15. IF a Copybook contains no 01-level record or more than one 01-level record, THEN THE Copybook_Parser SHALL raise a Copybook_Error that names the source (the file path, or an indication that the text was supplied directly) and states whether zero or more than one 01-level record was found.
16. IF an 01-level item carries a `PIC` clause, THEN THE Copybook_Parser SHALL raise a Copybook_Error naming that item.
17. IF a level number does not have a valid parent in the nesting order (for example an 05 item before any 01 item), THEN THE Copybook_Parser SHALL raise a Copybook_Error naming the item.
18. IF a group item has no children, THEN THE Copybook_Parser SHALL raise a Copybook_Error naming the group.
19. IF an elementary item uses a `PIC` form not covered by criteria 6 to 10 (including a zero length), THEN THE Copybook_Parser SHALL raise a Copybook_Error naming the item and the offending clause, and SHALL NOT guess a layout. Requirement 3 defines the error for specific unsupported clauses.

### Requirement 2: Read Fixed_Format source layout

**User Story:** As an engine developer, I want the parser to read copybooks exactly as they appear in the repository, so that no copybook needs editing before use.

#### Acceptance Criteria

1. WHEN a line has `*` or `/` in column 7, THE Copybook_Parser SHALL treat the entire line as a comment and exclude columns 1 to 80 of that line from every declaration.
2. THE Copybook_Parser SHALL ignore columns 73 to 80 of every line, and SHALL ignore columns 1 to 6 of every line.
3. THE Copybook_Parser SHALL ignore trailing whitespace on every line, including a trailing space after a period, so that a declaration ending in `.` and a declaration ending in `. ` produce the same Record_Schema.
4. WHEN a declaration spans several lines, THE Copybook_Parser SHALL join the code from columns 8 to 72 of each line, in order, up to and including the first period that is followed by whitespace or the end of the line, into one declaration.
5. WHEN the text uses CRLF line endings, THE Copybook_Parser SHALL produce a Record_Schema identical to the one produced for the same text with LF line endings.
6. WHEN Copybook text has blank lines or comment lines (as defined in criterion 1), THE Copybook_Parser SHALL produce a Record_Schema identical to the one produced for the same text without them.
7. WHEN the same Copybook content is indented with different amounts of spaces inside columns 8 to 72, THE Copybook_Parser SHALL produce a Record_Schema identical to the one produced for the original indentation, provided every token stays within columns 8 to 72.
8. IF a line contains a tab character in columns 1 to 72, THEN THE Copybook_Parser SHALL raise a Copybook_Error that states the 1-based line number of the first such line and SHALL NOT return a Record_Schema.
9. IF a line is shorter than 7 columns, THEN THE Copybook_Parser SHALL treat the line as blank and SHALL NOT raise an error.
10. IF the text ends with a declaration that has no terminating period, THEN THE Copybook_Parser SHALL raise a Copybook_Error that states the 1-based line number on which that declaration starts and SHALL NOT return a Record_Schema.

### Requirement 3: Reject unsupported clauses by item name

**User Story:** As a verification engineer, I want unsupported data clauses to stop the run with a clear error, so that nothing is guessed about a layout the codec cannot honour.

#### Acceptance Criteria

1. THE Copybook_Parser SHALL accept only these clauses on an elementary item: a `PIC` or `PICTURE` clause with the forms `X(n)`, `9(n)`, `S9(n)`, `S9(n)V9(m)` and `S9(n)V` followed by one or more nines, where n and m are positive integers.
2. IF an item declares `COMP`, `COMP-1`, `COMP-2`, `COMP-3`, `COMP-4`, `COMP-5`, `COMPUTATIONAL` (with or without a numeric suffix), `BINARY` or `PACKED-DECIMAL`, THEN THE Copybook_Parser SHALL raise an Unsupported_Clause error whose message contains the item name and the clause keyword as written in the source.
3. IF an item declares `OCCURS`, `REDEFINES`, `RENAMES`, `VALUE`, `USAGE`, `SIGN`, `SYNCHRONIZED`, `SYNC`, `JUSTIFIED`, `JUST` or `BLANK WHEN ZERO`, THEN THE Copybook_Parser SHALL raise an Unsupported_Clause error whose message contains the item name and the clause keyword as written in the source.
4. IF an item declares a PIC string outside the forms in criterion 1 (for example an edited picture such as `ZZ9.99`, an unsigned `9(n)V9(m)`, a `P` scale position, or a `PIC` without a repeat count), THEN THE Copybook_Parser SHALL raise an Unsupported_Clause error whose message contains the item name and the PIC string as written in the source.
5. IF an elementary item has no `PIC` clause, THEN THE Copybook_Parser SHALL raise a Copybook_Error naming the item.
6. IF an item has level number 66, 77 or 88, THEN THE Copybook_Parser SHALL raise an Unsupported_Clause error whose message contains the item name and the level number.
7. IF an elementary item is named `FILLER` and its picture is not `X(n)`, THEN THE Copybook_Parser SHALL raise an Unsupported_Clause error whose message contains `FILLER` and the source line number of the declaration.
8. WHEN several items carry unsupported clauses, THE Copybook_Parser SHALL raise the error for the first such item in declaration order and SHALL NOT report later items.
9. FOR ALL Copybooks produced by the Copybook_Text_Helper from a valid layout with one unsupported clause added to one named item, THE Copybook_Parser SHALL raise an Unsupported_Clause error whose item-name attribute equals that item name and whose message contains that item name (error-condition property).
10. THE Copybook_Parser SHALL match clause keywords and PIC characters without regard to letter case.
11. THE Copybook_Parser SHALL read declarations only and SHALL NOT interpret procedure code.
12. IF the Copybook_Parser raises an Unsupported_Clause or Copybook_Error, THEN THE Copybook_Parser SHALL return no partial layout, so that no later stage receives a layout from the rejected copybook.
13. FOR ALL generated valid layouts, THE Copybook_Parser SHALL produce, when parsing the Copybook text rendered from the layout by the Copybook_Text_Helper, a Record_Schema whose item names, level numbers, kinds, offsets, lengths and scales match the layout (round-trip property, test only).
14. THE Copybook_Text_Helper SHALL be the single renderer used by the property in criterion 13 and by the error-condition property in criterion 9.
15. THE Copybook_Text_Helper SHALL be located under `tests/`, SHALL NOT belong to the shipped engine package, and SHALL NOT be exported by `engine/revenant/`.
16. WHERE a test requests varied formatting, THE Copybook_Text_Helper SHALL render comment lines, blank lines, indentation within columns 8 to 72, CRLF line endings and trailing whitespace, so that the Fixed_Format criteria of Requirement 2 can be property-tested with it.

### Requirement 4: Parse the five CardDemo copybooks

**User Story:** As a verification engineer, I want the five exhibit copybooks to parse to the known record lengths, so that the layouts used in later milestones are anchored to observed values.

#### Acceptance Criteria

1. WHEN `CVTRA01Y.cpy` is parsed, THE Copybook_Parser SHALL return a Record_Schema named `TRAN-CAT-BAL-RECORD` with length 50 bytes.
2. WHEN `CVACT03Y.cpy` is parsed, THE Copybook_Parser SHALL return a Record_Schema named `CARD-XREF-RECORD` with length 50 bytes.
3. WHEN `CVACT01Y.cpy` is parsed, THE Copybook_Parser SHALL return a Record_Schema named `ACCOUNT-RECORD` with length 300 bytes.
4. WHEN `CVTRA02Y.cpy` is parsed, THE Copybook_Parser SHALL return a Record_Schema named `DIS-GROUP-RECORD` with length 50 bytes.
5. WHEN `CVTRA05Y.cpy` is parsed, THE Copybook_Parser SHALL return a Record_Schema named `TRAN-RECORD` with length 350 bytes.
6. WHEN `CVTRA01Y.cpy` is parsed, THE Copybook_Parser SHALL return exactly five leaf Field_Schemas, in this order: `TRANCAT-ACCT-ID` (uint, offset 0, length 11), `TRANCAT-TYPE-CD` (alnum, offset 11, length 2), `TRANCAT-CD` (uint, offset 13, length 4), `TRAN-CAT-BAL` (sdec, offset 17, length 11, scale 2) and a `FILLER` (kind filler, offset 28, length 22). THE Copybook_Parser SHALL also return a Group_Span `TRAN-CAT-KEY` with offset 0 and length 17, and the Group_Span SHALL NOT be counted among the leaf Field_Schemas.
7. WHEN `CVTRA02Y.cpy` is parsed, THE Copybook_Parser SHALL return `DIS-INT-RATE` as sdec with offset 16, length 6 and scale 2, and a Group_Span `DIS-GROUP-KEY` with offset 0 and length 16.
8. WHEN `CVTRA05Y.cpy` is parsed, THE Copybook_Parser SHALL return `TRAN-AMT` as sdec with offset 132, length 11 and scale 2.
9. WHEN `CVACT01Y.cpy` is parsed, THE Copybook_Parser SHALL return `ACCT-CURR-BAL` as sdec with offset 12, length 12 and scale 2, and SHALL return `ACCT-EXPIRAION-DATE` (spelled as in the source) as alnum with offset 58 and length 10, without raising an error for the single space that follows the terminating period on that line.
10. FOR ALL five Copybooks, THE Copybook_Parser SHALL return leaf Field_Schemas in source order whose first offset is 0, where each subsequent offset equals the previous offset plus the previous length, and whose lengths sum to the length of the Record_Schema (invariant property).
11. WHEN the Copybook_Parser has read the five Copybooks, THE Copybook_Parser SHALL leave every file under `exhibits/cbact04c/legacy/` byte-identical to its content before the read, as verified by the SHA-256 digests listed in `exhibits/cbact04c/SHA256SUMS`.

### Requirement 5: Encode Logical_Records into fixed-width bytes

**User Story:** As an engine developer, I want to encode logical records into the exact bytes a record file holds, so that both the old program and the port receive the same physical input.

#### Acceptance Criteria

1. WHEN a valid Logical_Record is provided, THE Record_Codec SHALL return `bytes` whose length equals the Record_Schema length.
2. WHEN an Alnum_Field value is encoded, THE Record_Codec SHALL write the value as ASCII, left-justified, padded on the right with spaces to the field length.
3. IF an Alnum_Field value is longer than the field length or contains a byte outside 0x20 to 0x7E, THEN THE Record_Codec SHALL raise an error naming the field and SHALL return no bytes.
4. WHEN a Uint_Field value is encoded, THE Record_Codec SHALL write the value as decimal digits, padded on the left with zeros to the field length.
5. IF a Uint_Field value is negative, is not an integer, or has more decimal digits than the field length, THEN THE Record_Codec SHALL raise an error naming the field and SHALL return no bytes.
6. WHEN an Sdec_Field value is encoded, THE Record_Codec SHALL write the absolute value of the integer in the field's smallest unit as decimal digits, padded on the left with zeros to the field length, with no stored decimal point, and with the last digit replaced by its Overpunch character for the value's sign.
7. IF an Sdec_Field value is not an integer (including a float) or its absolute value has more decimal digits than the field length, THEN THE Record_Codec SHALL raise an error naming the field and SHALL return no bytes.
8. WHEN an Sdec_Field value of 125 is encoded in a field of length 11, THE Record_Codec SHALL write `b"0000000012E"`.
9. WHEN an Sdec_Field value of -125 is encoded in a field of length 11, THE Record_Codec SHALL write `b"0000000012N"`.
10. WHEN an Sdec_Field value of 0 is encoded in a field of length 11, THE Record_Codec SHALL write `b"0000000000{"`.
11. THE Record_Codec SHALL write `{` for a value with last digit 0 and a non-negative sign, `A` to `I` for a non-negative value with last digit 1 to 9, `}` for a negative value with last digit 0, and `J` to `R` for a negative value with last digit 1 to 9, where `A` to `I` and `J` to `R` map to digits 1 to 9 in order.
12. THE Record_Codec SHALL write the byte 0x20 into every Filler_Field.
13. THE Record_Codec SHALL write each field at the byte offset given by its Field_Schema.
14. THE Record_Codec SHALL produce identical bytes for identical Record_Schema and Logical_Record inputs (determinism property).
15. FOR ALL valid Logical_Records, the encoded length SHALL equal the Record_Schema length, and the encoded length of each field span SHALL equal its Field_Schema length (invariant property).
16. FOR ALL valid Logical_Records, the filler spans of the encoded bytes SHALL be 0x20 bytes and SHALL be identical across all records (invariant property).
17. THE Record_Codec SHALL provide a field-level encode function that returns the bytes of one field, and the record-level encode function SHALL produce the concatenation of the field-level results in offset order.

### Requirement 6: Decode bytes into Logical_Records

**User Story:** As an engine developer, I want to decode record bytes into logical values, so that outputs from the old program can be compared with outputs from the port by value and by byte.

#### Acceptance Criteria

1. WHEN bytes of exactly the Record_Schema length are provided, THE Record_Codec SHALL return a Logical_Record holding every non-filler field, keyed by field name, and no Filler_Field.
2. IF the input length differs from the Record_Schema length, THEN THE Record_Codec SHALL raise an error that states the expected length and the actual length, and SHALL return no Logical_Record.
3. WHEN an Alnum_Field is decoded, THE Record_Codec SHALL return the ASCII text of the field with trailing spaces removed and leading spaces preserved.
4. WHEN an Alnum_Field holds only spaces, THE Record_Codec SHALL return the empty string.
5. WHEN a Uint_Field is decoded, THE Record_Codec SHALL return the integer value of its digits, with leading zeros not retained in the value.
6. IF a Uint_Field holds a byte other than ASCII `0` to `9`, THEN THE Record_Codec SHALL raise an error that names the field and the offending byte, and SHALL return no Logical_Record.
7. WHEN an Sdec_Field is decoded, THE Record_Codec SHALL return a signed integer of the smallest unit, using the first length-1 characters as digits and the last character as the Overpunch.
8. WHEN the Overpunch character is `{` or one of `A` to `I`, THE Record_Codec SHALL return a positive value whose last digit is 0 for `{` and 1 to 9 for `A` to `I` respectively.
9. WHEN the Overpunch character is `}`, THE Record_Codec SHALL return 0 for a field whose other digits are all zero, and SHALL return the negative value with last digit 0 otherwise.
10. WHEN the Overpunch character is one of `J` to `R`, THE Record_Codec SHALL return a negative value whose last digit is 1 to 9 respectively.
11. IF an Sdec_Field has a leading digit byte other than ASCII `0` to `9`, or a last byte that is not `{`, `}`, `A` to `I` or `J` to `R`, THEN THE Record_Codec SHALL raise an error that names the field and the offending byte, and SHALL return no Logical_Record.
12. WHEN an Sdec_Field holds `b"0000000012E"`, THE Record_Codec SHALL return 125.
13. WHEN an Sdec_Field holds `b"0000000012N"`, THE Record_Codec SHALL return -125.
14. WHEN an Sdec_Field holds `b"0000000000{"`, THE Record_Codec SHALL return 0, and WHEN it holds `b"0000000000}"`, THE Record_Codec SHALL also return 0.
15. THE Record_Codec SHALL skip validation of Filler_Field bytes, so that a filler holding any byte values from 0x00 to 0xFF does not raise an error.
16. THE Record_Codec SHALL provide a field-level decode function that accepts the bytes of one field and the field definition, and returns the same value as the record-level decode returns for that field.
17. THE Record_Codec SHALL accept `bytes` and `bytearray` as decode input and SHALL return identical results for identical content in either type.

### Requirement 7: Round-trip and idempotence properties

**User Story:** As a verification engineer, I want the codec's encode and decode to be exact inverses on valid inputs, so that later differences between programs are not caused by the codec.

#### Acceptance Criteria

1. FOR ALL valid Alnum_Field values of length 0 to the field length, consisting only of printable ASCII characters 0x20 to 0x7E and having no trailing spaces, decoding the encoded field SHALL return the original value (round-trip property).
2. FOR ALL valid Uint_Field values from 0 to 10^n - 1, where n is the field length in digits, decoding the encoded field SHALL return the original value, including 0 and 10^n - 1 (round-trip property).
3. FOR ALL valid Sdec_Field values from -(10^L - 1) to 10^L - 1, where L is the field length in digits, decoding the encoded field SHALL return the original value, including 0, 1, -1, and both extremes of the field (round-trip property).
4. FOR ALL valid Logical_Records of a Record_Schema, decoding the encoded record SHALL return a Logical_Record equal to the original in every field (round-trip property).
5. FOR ALL Canonical_Bytes of a Record_Schema, where Canonical_Bytes are byte sequences the encoder could produce (fillers as spaces, signed zero as `{`), encoding the decoded record SHALL return bytes identical to the original in every position (round-trip property).
6. FOR ALL valid Logical_Records, encoding the result of decoding the first encoding SHALL return bytes identical to the first encoding (idempotence property).
7. FOR ALL byte sequences of the Record_Schema length that decode without error, including sequences with `}` as the last byte of a zero-valued Sdec_Field, encoding the decoded result and decoding that encoding SHALL return a Logical_Record equal to the first decoded Logical_Record in every field (idempotence property).
8. FOR ALL valid Sdec_Field values, the last byte of the encoded field SHALL be one of `{`, `A` to `I`, `}` and `J` to `R`. The byte SHALL be `{` or one of `A` to `I` when the value is greater than or equal to 0, and SHALL be `}` or one of `J` to `R` when the value is less than 0. The byte SHALL be `{` when the value is 0 (invariant property).
9. FOR ALL valid Sdec_Field values, the first L-1 bytes of the encoded field SHALL each be an ASCII digit from 0x30 to 0x39, where L is the field length in bytes (invariant property).
10. THE test suite SHALL run each property in criteria 1 to 9 with a Hypothesis-generated population of at least 100 examples per property, over every Record_Schema parsed from the five CardDemo copybooks and over generated schemas covering all four kinds of field (Alnum_Field, Uint_Field, Sdec_Field and filler).
11. IF a property test fails, THEN THE test suite SHALL report the property as failed and include the minimal failing example found by Hypothesis.

### Requirement 8: Reject invalid values on encode

**User Story:** As a verification engineer, I want encode to fail with the field name whenever a value cannot be written exactly, so that no value is silently changed.

#### Acceptance Criteria

1. IF a Uint_Field of n digits is given an `int` value greater than 10^n - 1, or an Sdec_Field of L total digits is given an `int` whose absolute value is greater than 10^L - 1, THEN THE Record_Codec SHALL raise a Codec_Error naming the field, SHALL NOT truncate the value, and SHALL NOT return any encoded bytes for the Logical_Record.
2. IF a Uint_Field is given a negative `int` value, THEN THE Record_Codec SHALL raise a Codec_Error naming the field and SHALL NOT return any encoded bytes for the Logical_Record.
3. IF an Alnum_Field is given a `str` longer than the field length in characters, THEN THE Record_Codec SHALL raise a Codec_Error naming the field, SHALL NOT truncate the value, and SHALL NOT return any encoded bytes for the Logical_Record.
4. IF an Alnum_Field is given a `str` containing a character outside the range 0x20 to 0x7E inclusive, THEN THE Record_Codec SHALL raise a Codec_Error naming the field and SHALL NOT return any encoded bytes for the Logical_Record.
5. IF a Uint_Field or Sdec_Field is given a `float`, a `decimal.Decimal` or a `bool`, THEN THE Record_Codec SHALL raise a Codec_Error naming the field and stating the received type name, and SHALL NOT return any encoded bytes for the Logical_Record.
6. IF an Alnum_Field is given a value that is not a `str`, or a Uint_Field or Sdec_Field is given a `str`, `bytes` or `None`, THEN THE Record_Codec SHALL raise a Codec_Error naming the field and stating the received type name, and SHALL NOT return any encoded bytes for the Logical_Record.
7. IF a Logical_Record lacks a non-filler field of the Record_Schema, THEN THE Record_Codec SHALL raise a Codec_Error naming the missing field and SHALL NOT return any encoded bytes for the Logical_Record.
8. IF a Logical_Record contains a key that names no non-filler field of the Record_Schema, including `FILLER`, THEN THE Record_Codec SHALL raise a Codec_Error naming the key and SHALL NOT return any encoded bytes for the Logical_Record.
9. FOR ALL numeric fields, THE Record_Codec SHALL raise a Codec_Error containing the field name when given the value one step beyond the limit: 10^n for a Uint_Field of n digits, and both 10^L and -(10^L) for an Sdec_Field of L total digits (error-condition property).
10. FOR ALL Alnum_Fields of length N, THE Record_Codec SHALL raise a Codec_Error containing the field name when given any `str` of length N+1 or greater (error-condition property).
11. THE public interface of the Record_Codec SHALL use `int` and `str` Logical_Values only, and SHALL contain no `float` or `decimal.Decimal` in any signature, return value or intermediate calculation.

### Requirement 9: Reject malformed bytes on decode

**User Story:** As a verification engineer, I want decode to fail with the field name whenever bytes cannot be read exactly, so that a bad oracle output is never read as a value.

#### Acceptance Criteria

1. IF the input length differs from the Record_Schema length, THEN THE Record_Codec SHALL raise a Codec_Error naming the record, the expected length and the received length, and SHALL return no partial values.
2. IF a Uint_Field span contains a byte that is not an ASCII digit (0x30 to 0x39), THEN THE Record_Codec SHALL raise a Codec_Error naming the field. This includes a space, a `+` character, a `-` character and a NUL byte.
3. IF the first length-1 bytes of an Sdec_Field span contain a byte that is not an ASCII digit (0x30 to 0x39), THEN THE Record_Codec SHALL raise a Codec_Error naming the field.
4. IF the last byte of an Sdec_Field span is not one of `{`, `A` to `I`, `}` or `J` to `R`, THEN THE Record_Codec SHALL raise a Codec_Error naming the field. This includes the native GnuCOBOL signs `p` to `y`, a plain digit, a space and a `-` character.
5. IF an Alnum_Field span contains a byte outside 0x20 to 0x7E, THEN THE Record_Codec SHALL raise a Codec_Error naming the field. This includes a tab (0x09), a newline (0x0A), a NUL byte and any byte from 0x80 to 0xFF.
6. IF the input is a `str` or any type other than `bytes` or `bytearray`, THEN THE Record_Codec SHALL raise a Codec_Error naming the record and the received type, and SHALL perform no length or content checks first.
7. IF a field-level decode of any field kind (Uint_Field, Sdec_Field or Alnum_Field) receives bytes whose length differs from the field length, THEN THE Record_Codec SHALL raise a Codec_Error naming the field, the expected length and the received length.
8. IF a record decode finds more than one malformed field, THEN THE Record_Codec SHALL raise a single Codec_Error naming the first malformed field in Record_Schema order.
9. FOR ALL Canonical_Bytes with exactly one byte in a Uint_Field or Sdec_Field span replaced by a byte outside the valid set for that position, THE Record_Codec SHALL raise a Codec_Error whose message contains the name of the field that holds the replaced byte (error-condition property).
10. FOR ALL byte sequences whose length differs from the Record_Schema length, THE Record_Codec SHALL raise a Codec_Error (error-condition property).

### Requirement 10: Check the codec against seed data and the real program's conventions

**User Story:** As a verification engineer, I want the codec exercised on real CardDemo bytes, so that the sign convention is anchored to data from the original platform and not only to the codec's own output.

#### Acceptance Criteria

1. WHEN a Seed_File line is read with its line ending removed (LF or CRLF) and padded on the right with spaces to the record length of its copybook, THE Record_Codec SHALL decode it without error, using `CVACT01Y` for `acctdata.txt`, `CVACT03Y` for `cardxref.txt`, `CVTRA02Y` for `discgrp.txt` and `CVTRA01Y` for `tcatbal.txt`.
2. WHEN a decoded Seed_File line is encoded again, THE Record_Codec SHALL reproduce every byte outside the Filler_Field spans of the padded line, including each `{` sign byte.
3. WHEN the test for criterion 2 compares a re-encoded record with its padded Seed_File line, THE test SHALL compare each Filler_Field span for length only, because the seed fillers in `tcatbal.txt` and `discgrp.txt` hold zeros and the encoder writes spaces.
4. WHEN the test for criterion 1 runs over a Seed_File, THE test SHALL process every line of that file and SHALL fail if any line is not decoded, so that a line with CRLF ending (49 of the 50 lines in `tcatbal.txt`) or a line shorter than its record length (the 36-character lines in `cardxref.txt`, whose record is 50 bytes) is neither skipped nor counted as a pass.
5. WHERE the legacy program is built in the Container (the `build/cbact04c` binaries exist), THE test suite SHALL include an integration test in `tests/integration/` that performs a Witness_Run on one-account inputs and compares the TRAN-AMT bytes of the transaction record (offset 132, length 11) with the Record_Codec encoding of the expected integer.
6. THE integration test SHALL use these inputs, each given as balance and annual rate in the smallest unit, with the observed TRAN-AMT bytes and expected integer:
   - balance 10050 (100.50) at rate 1500 (15.00): `0000000012E`, 125.
   - balance -10050 (-100.50) at rate 1500 (15.00): `0000000012N`, -125.
   - balance -100 (-1.00) at rate 600 (6.00): `0000000000{`, 0. This input is negative and its truncated interest is zero, and the old program writes positive zero `{`, which is why the Record_Codec encoder writes `{` for zero.
   - balance -120 (-1.20) at rate 1000 (10.00): `0000000000J`, -1.
7. FOR EACH input in criterion 6, THE integration test SHALL decode the TRAN-AMT bytes written by the old program with the Record_Codec and compare the result with the expected integer, and SHALL encode the expected integer with the Record_Codec and compare the bytes with the TRAN-AMT bytes written by the old program.
8. WHILE the oracle runner does not exist, THE integration test SHALL obtain the old program's output by loading `scripts/m1_proof.py` by file path (the file is not a package) and calling its `run_witness` and one-account world builder.
9. IF the old program exits with a non-zero code, or writes other than exactly one 350-byte transaction record, for an input in criterion 6, THEN THE integration test SHALL fail and SHALL name the input.
10. IF a byte of the TRAN-AMT field differs between the old program and the Record_Codec encoding, THEN THE integration test SHALL fail and SHALL name the input and the first differing byte offset.
11. THE Record_Codec SHALL document, in the module docstring, that the Overpunch convention matches `cobc -std=ibm -fsign=EBCDIC` and is not the GnuCOBOL native convention.

### Requirement 11: Packaging, execution and test layout

**User Story:** As a maintainer, I want the component and its tests placed according to the repository conventions and runnable inside the container, so that results are reproducible.

#### Acceptance Criteria

1. THE Copybook_Parser SHALL be implemented in `engine/revenant/copybook.py` and THE Record_Codec in `engine/revenant/codec.py`.
2. THE engine package SHALL import without a dependency on any specific exhibit, so that the component runs against any Copybook that uses the supported grammar. Importing `revenant.copybook` and `revenant.codec` SHALL succeed when no `exhibits/` directory is on the import path.
3. THE test suite SHALL place unit tests in `tests/unit/`, property tests in `tests/property/`, integration tests in `tests/integration/` and the Copybook_Text_Helper in `tests/support/`, and SHALL create only those directories and `engine/revenant/` files that this component needs.
4. WHEN the command `./rv python3 -m pytest tests/unit tests/property` runs in the Container, THE test suite SHALL execute without requiring a native toolchain on the host, and SHALL exit with code 0 only if every collected test passes.
5. THE test suite SHALL use Hypothesis with a registered derandomized profile that CI selects, so that two runs with the same code and the same Hypothesis version select the same cases.
6. THE component SHALL import only Python standard library modules at run time, and only Hypothesis and pytest in tests.
7. THE component SHALL make no model calls.
8. THE source, tests and test output messages SHALL describe passing results as "no failure in N generated cases", where N is the number of cases run. THE source and tests SHALL NOT contain the words "proven" or "equivalent", or a confidence percentage.
9. IF `exhibits/cbact04c/SHA256SUMS` no longer matches the files under `exhibits/cbact04c/legacy/`, THEN THE test suite SHALL fail with a message naming each mismatched or missing file.
10. THE file `docker/Dockerfile` SHALL install pytest and Hypothesis at exact pinned versions written with `==`, not version ranges.
11. WHEN the command `./rv python3 -c "import revenant.copybook, revenant.codec"` runs from the repository root mounted at `/work`, THE Container SHALL exit with code 0 without a PYTHONPATH argument and without path changes on the command line, because the image or its environment provides the path to `engine/`.
