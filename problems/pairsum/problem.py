import logging

from problems.pairsum.parser import PairsumParser
from problems.pairsum.verifier import PairsumVerifier
from problem import Problem

logger = logging.getLogger('algobattle.pairsum')

class Pairsum(Problem):
    n_start = 4
    parser = PairsumParser()
    verifier = PairsumVerifier()