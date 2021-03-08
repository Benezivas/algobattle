import logging

from algobattle.problem import Problem
from .parser import PairsumParser
from .verifier import PairsumVerifier


logger = logging.getLogger('algobattle.pairsum')

class Pairsum(Problem):
    n_start = 4
    parser = PairsumParser()
    verifier = PairsumVerifier()
    approximable = False