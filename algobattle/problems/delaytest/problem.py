import logging

from algobattle.problem import Problem
from algobattle.problems.delaytest.parser import DelaytestParser
from algobattle.problems.delaytest.verifier import DelaytestVerifier

logger = logging.getLogger('algobattle.delaytest')

class Delaytest(Problem):
    n_start = 1
    parser = DelaytestParser()
    verifier = DelaytestVerifier()