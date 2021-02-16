import logging

from problem import Problem
from problems.c4subgraphiso.parser import C4subgraphisoParser
from problems.c4subgraphiso.verifier import C4subgraphisoVerifier

logger = logging.getLogger('algobattle.c4subgraphiso')

class C4subgraphiso(Problem):
    n_start = 4
    parser = C4subgraphisoParser()
    verifier = C4subgraphisoVerifier()