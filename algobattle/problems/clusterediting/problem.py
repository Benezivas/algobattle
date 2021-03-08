import logging

from algobattle.problem import Problem
from .parser import ClustereditingParser
from .verifier import ClustereditingVerifier

logger = logging.getLogger('algobattle.clusterediting')

class Clusterediting(Problem):
    n_start = 4
    parser = ClustereditingParser()
    verifier = ClustereditingVerifier()
    approximable = True