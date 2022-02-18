"""Dummy problem class for delaytest."""
import logging

from algobattle.problem import Problem
from .parser import DelaytestParser
from .verifier import DelaytestVerifier

logger = logging.getLogger('algobattle.problems.delaytest')


class Delaytest(Problem):
    """Dummy Problem used for testing Docker delays."""

    name: str = 'Runtime Delay Test'
    n_start: int = 1
    parser: DelaytestParser = DelaytestParser()
    verifier: DelaytestVerifier = DelaytestVerifier()
    approximable: bool = False
