import logging

from algobattle.problem import Problem
from .parser import HikersParser
from .verifier import HikersVerifier

logger = logging.getLogger('algobattle.hikers')

class Hikers(Problem):
    n_start  = 5
    parser   = HikersParser()
    verifier = HikersVerifier()
    approximable = True