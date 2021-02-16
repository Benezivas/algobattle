import logging

from problem import Problem
from problems.hikers.parser import HikersParser
from problems.hikers.verifier import HikersVerifier

logger = logging.getLogger('algobattle.hikers')

class Hikers(Problem):
    n_start  = 5
    parser   = HikersParser()
    verifier = HikersVerifier()