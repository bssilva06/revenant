"""Shared pytest configuration: Hypothesis profiles and the --require-witness option."""
from hypothesis import settings

# "dev" is the default. "ci" is derandomized so two runs select the same cases.
settings.register_profile("dev", max_examples=100, deadline=None, database=None)
settings.register_profile(
    "ci",
    max_examples=200,
    derandomize=True,
    deadline=None,
    database=None,
)
settings.load_profile("dev")


def pytest_addoption(parser):
    parser.addoption(
        "--require-witness",
        action="store_true",
        default=False,
        help="Fail, instead of skipping, witness tests when build/cbact04c is absent.",
    )
