import logging

from algobattle.problem import Problem
from .parser import TestsParser
from .verifier import TestsVerifier

logger = logging.getLogger('algobattle.tests')


class Tests(Problem):
    name = 'Tests'
    n_start = 1
    parser = TestsParser()
    verifier = TestsVerifier()
    approximable = False
