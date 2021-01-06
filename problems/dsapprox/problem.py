import logging

from problem import Problem
from problems.dsapprox.parser import DsapproxParser
from problems.dsapprox.verifier import DsapproxVerifier

logger = logging.getLogger('algobattle.dsapprox')

class Dsapprox(Problem):
    n_start  = 6
    parser   = DsapproxParser()
    verifier = DsapproxVerifier()