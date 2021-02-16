import logging

from problem import Problem
from problems.clusterediting.parser import ClustereditingParser
from problems.clusterediting.verifier import ClustereditingVerifier

logger = logging.getLogger('algobattle.clusterediting')

class Clusterediting(Problem):
    n_start = 4
    parser = ClustereditingParser()
    verifier = ClustereditingVerifier()