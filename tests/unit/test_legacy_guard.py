"""Guard: the pinned upstream files under exhibits/cbact04c must match SHA256SUMS."""
import hashlib
from pathlib import Path

EXHIBIT = Path(__file__).resolve().parents[2] / "exhibits" / "cbact04c"


def legacy_mismatches(exhibit: Path = EXHIBIT) -> list[str]:
    """Return one message per path in SHA256SUMS that is missing or has a different digest."""
    problems = []
    for line in (exhibit / "SHA256SUMS").read_text().splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        path = exhibit / name.strip().lstrip("*")
        if not path.is_file():
            problems.append(f"missing: {path.relative_to(exhibit)}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            problems.append(f"digest mismatch: {path.relative_to(exhibit)}")
    return problems


def assert_legacy_unchanged(exhibit: Path = EXHIBIT) -> None:
    problems = legacy_mismatches(exhibit)
    assert not problems, "pinned files differ from SHA256SUMS: " + "; ".join(problems)


def test_legacy_files_match_sha256sums():
    assert_legacy_unchanged()


def test_guard_names_every_missing_or_changed_file(tmp_path):
    (tmp_path / "SHA256SUMS").write_text(
        hashlib.sha256(b"a").hexdigest() + "  legacy/a.txt\n"
        + hashlib.sha256(b"b").hexdigest() + "  legacy/b.txt\n"
        + hashlib.sha256(b"c").hexdigest() + "  legacy/c.txt\n"
    )
    (tmp_path / "legacy").mkdir()
    (tmp_path / "legacy" / "a.txt").write_bytes(b"a")
    (tmp_path / "legacy" / "b.txt").write_bytes(b"changed")
    assert legacy_mismatches(tmp_path) == [
        "digest mismatch: legacy/b.txt",
        "missing: legacy/c.txt",
    ]
