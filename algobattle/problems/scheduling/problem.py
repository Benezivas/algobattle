import logging

from algobattle.problem import Problem
from .parser import SchedulingParser
from .verifier import SchedulingVerifier

logger = logging.getLogger('algobattle.problems.scheduling')


class Scheduling(Problem):
    name = 'Scheduling'
    n_start = 5
    parser = SchedulingParser()
    verifier = SchedulingVerifier()
    approximable = False
