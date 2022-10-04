"""Simple verifier hand-tailored for certain tests to succeed or fail."""
import logging

from algobattle.verifier import Verifier

logger = logging.getLogger('algobattle.problems.testsproblem.verifier')


class TestsVerifier(Verifier):
    """Dummy verifier."""

    def verify_semantics_of_instance(self, instance, instance_size: int):
        if not instance:
            return False
        if any(line[1] != '1' for line in instance):
            return False
        return True

    def verify_semantics_of_solution(self, solution, instance_size: int, solution_type: bool):
        if not solution:
            return False

        if any(line[1] != '1' for line in solution):
            return False
        return True

    def verify_solution_against_instance(self, instance, solution, instance_size, solution_type):
        if any(line[2] != '1' for line in solution):
            return False

        return True

    def calculate_approximation_ratio(self, instance, instance_size, generator_solution, solver_solution):
        return len([line for line in generator_solution if line[3] == '1']) \
            / len([line for line in solver_solution if line[3] == '1'])
