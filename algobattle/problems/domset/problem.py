import logging

from algobattle.problem import Problem
from .parser import DomsetParser
from .verifier import DomsetVerifier

logger = logging.getLogger('algobattle.domset')

class Domset(Problem):
    n_start  = 6
    parser   = DomsetParser()
    verifier = DomsetVerifier()