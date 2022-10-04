"""Problem class built for tests."""
import logging

from algobattle.problem import Problem
from .parser import TestsParser
from .verifier import TestsVerifier

logger = logging.getLogger('algobattle.problems.testsproblem')


class Tests(Problem):
    """Artificial problem used for tests."""

    name = 'Tests'
    n_start = 1
    parser = TestsParser()
    verifier = TestsVerifier()
    approximable = True
