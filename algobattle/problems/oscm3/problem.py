import logging

from algobattle.problem import Problem
from .parser import OSCM3Parser
from .verifier import OSCM3Verifier

logger = logging.getLogger('algobattle.oscm3')

class OSCM3(Problem):
    n_start = 3
    parser = OSCM3Parser()
    verifier = OSCM3Verifier()
    approximable = True