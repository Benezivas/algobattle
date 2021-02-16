import logging

from problem import Problem
from problems.oscm3.parser import OSCM3Parser
from problems.oscm3.verifier import OSCM3Verifier

logger = logging.getLogger('algobattle.oscm3')

class OSCM3(Problem):
    n_start = 3
    parser = OSCM3Parser()
    verifier = OSCM3Verifier()