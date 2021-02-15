import logging

from problem import Problem
from problems.domset.parser import DomsetParser
from problems.domset.verifier import DomsetVerifier

logger = logging.getLogger('algobattle.domset')

class Domset(Problem):
    n_start  = 6
    parser   = DomsetParser()
    verifier = DomsetVerifier()