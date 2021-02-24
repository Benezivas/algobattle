import logging

from algobattle.problem import Problem
from .parser import SchedulingParser
from .verifier import SchedulingVerifier

logger = logging.getLogger('algobattle.scheduling')

class Scheduling(Problem):
    n_start = 5
    parser = SchedulingParser()
    verifier = SchedulingVerifier()