"""Problem class built for tests."""
import logging

from algobattle.problem import Problem
from .parser import TestsParser
from .verifier import TestsVerifier

logger = logging.getLogger('algobattle.problems.testsproblem')


class Tests(Problem):
    """Artificial problem used for tests."""

    name: str = 'Tests'
    n_start: int = 1
    parser: TestsParser = TestsParser()
    verifier: TestsVerifier = TestsVerifier()
    approximable: bool = True
