"""Main module of the Pairsum problem."""
import logging

from algobattle.problem import Problem
from .parser import PairsumParser
from .verifier import PairsumVerifier

logger = logging.getLogger('algobattle.problems.pairsum')


class Pairsum(Problem):
    """The pairsum problem class."""
    name = 'Pairsum'
    n_start = 4
    parser = PairsumParser()
    verifier = PairsumVerifier()
    approximable = False
