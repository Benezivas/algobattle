import logging

from problem import Problem
from problems.biclique.parser import BicliqueParser
from problems.biclique.verifier import BicliqueVerifier

logger = logging.getLogger('algobattle.biclique')

class Biclique(Problem):
    n_start = 5
    parser = BicliqueParser()
    verifier = BicliqueVerifier()