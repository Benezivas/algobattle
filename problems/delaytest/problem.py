import logging

from problem import Problem
from problems.delaytest.parser import DelaytestParser
from problems.delaytest.verifier import DelaytestVerifier

logger = logging.getLogger('algobattle.delaytest')

class Delaytest(Problem):
    n_start = 4
    parser = DelaytestParser()
    verifier = DelaytestVerifier()