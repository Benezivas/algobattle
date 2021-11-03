"""Dummy verifier for the delaytest. Does not verify anything."""
import logging
from algobattle.verifier import Verifier

logger = logging.getLogger('algobattle.problems.delaytest.verifier')


class DelaytestVerifier(Verifier):
    """Dummy verifier used for testing Docker delays."""

    def verify_semantics_of_instance(self, instance, instance_size: int):
        return True

    def verify_semantics_of_solution(self, solution, instance_size: int, solution_type: bool):
        return True

    def verify_solution_against_instance(self, instance, solution, instance_size, solution_type):
        return True

    def calculate_approximation_ratio(self, instance, instance_size, generator_solution, solver_solution):
        return 1.0
