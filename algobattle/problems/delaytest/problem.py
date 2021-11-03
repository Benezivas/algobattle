"""Dummy problem class for delaytest."""
import logging

from algobattle.problem import Problem
from .parser import DelaytestParser
from .verifier import DelaytestVerifier

logger = logging.getLogger('algobattle.problems.delaytest')


class Delaytest(Problem):
    """Dummy Problem used for testing Docker delays."""

    name = 'Runtime Delay Test'
    n_start = 1
    parser = DelaytestParser()
    verifier = DelaytestVerifier()
    approximable = False
