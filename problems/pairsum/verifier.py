import logging

from verifier import Verifier

logger = logging.getLogger('algobattle.verifier')

class PairsumVerifier(Verifier):
    def verify_semantics_of_instance(self, instance, instance_size: int):
        # Instances for this problem are semantically valid if they are syntactically valid.
        # We only check if the instance is empty.
        if not instance:
            logger.error('The instance is empty!')
            return False
        return True

    def verify_semantics_of_solution(self, instance, solution, instance_size: int, solution_type: bool):
        # Solutions for this problem are semantically valid if they are syntactically valid.
        # We only check if the solution is empty.
        if not solution:
            logger.error('The solution is empty!')
            return False
        return True

    def verify_solution_against_instance(self, instance, solution, instance_size, solution_type):
        if not instance[solution[0]] + instance[solution[1]] == instance[solution[2]] + instance[solution[3]]:
            logger.error('The given solution is not valid!')
            return False

        return True

    def verify_solution_quality(self, instance, instance_size, generator_solution, solver_solution):
        return len(solver_solution) == 4