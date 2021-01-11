import logging

from verifier import Verifier

logger = logging.getLogger('algobattle.verifier')

class PairsumVerifier(Verifier):
    def verify_solution_against_instance(self, instance, solution, instance_size, solution_type):
        if not instance:
            logger.error('The instance is empty!')
            return True

        if not solution:
            logger.error('The solution is empty!')
            return False
        
        if len(solution) != 4:
            logger.error('The solution is not of size 4!')
            return False

        if len(set(solution)) != 4:
            logger.error('The solution contains duplicate entries!')
            return False

        if not all(i < len(instance) and i >= 0 for i in solution):
            logger.error('The solution contains at least one number that is out of bounds!')
            return False

        if not instance[solution[0]] + instance[solution[1]] == instance[solution[2]] + instance[solution[3]]:
            logger.error('The given solution is not valid!')
            return False

        return True

    def verify_solution_quality(self, instance, instance_size, generator_solution, solver_solution):
        return len(solver_solution) == 4