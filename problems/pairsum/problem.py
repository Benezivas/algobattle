import logging

from pairsum.parser import PairsumParser
from pairsum.verifier import PairsumVerifier
from problem import Problem

logger = logging.getLogger('algobattle.pairsum')

class Pairsum(Problem):
    n_start = 4
    parser = PairsumParser()
    verifier = PairsumVerifier()