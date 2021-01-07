import logging

from problem import Problem
from problems.pathpacking.parser import PathpackingParser
from problems.pathpacking.verifier import PathpackingVerifier

logger = logging.getLogger('algobattle.pathpacking')

class Pathpacking(Problem):
    n_start = 4
    parser = PathpackingParser()
    verifier = PathpackingVerifier()