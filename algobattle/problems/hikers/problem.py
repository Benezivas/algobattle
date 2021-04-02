import logging

from algobattle.problem import Problem
from .parser import HikersParser
from .verifier import HikersVerifier

logger = logging.getLogger('algobattle.problems.hikers')


class Hikers(Problem):
    name = 'Hikers'
    n_start = 5
    parser = HikersParser()
    verifier = HikersVerifier()
    approximable = True
