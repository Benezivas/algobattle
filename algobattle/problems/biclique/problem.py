import logging

from algobattle.problem import Problem
from algobattle.problems.biclique.parser import BicliqueParser
from algobattle.problems.biclique.verifier import BicliqueVerifier

logger = logging.getLogger('algobattle.biclique')

class Biclique(Problem):
    n_start = 5
    parser = BicliqueParser()
    verifier = BicliqueVerifier()