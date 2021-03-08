import logging

from algobattle.problem import Problem
from .parser import DelaytestParser
from .verifier import DelaytestVerifier

logger = logging.getLogger('algobattle.delaytest')

class Delaytest(Problem):
    n_start = 1
    parser = DelaytestParser()
    verifier = DelaytestVerifier()
    approximable = False