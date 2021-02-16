import logging

from problem import Problem
from problems.scheduling.parser import SchedulingParser
from problems.scheduling.verifier import SchedulingVerifier

logger = logging.getLogger('algobattle.scheduling')

class Scheduling(Problem):
    n_start = 5
    parser = SchedulingParser()
    verifier = SchedulingVerifier()