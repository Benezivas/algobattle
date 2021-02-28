import logging

from algobattle.verifier import Verifier

logger = logging.getLogger('algobattle.verifier')

class HikersVerifier(Verifier):
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
        upper = {}
        lower = {}
        for line in instance:
            index = int(line[1])
            lower[index] = int(line[2])
            upper[index] = int(line[3])

        group = {}
        for line in solution:
            index  = int(line[1])
            group[index] = int(line[2])

        #store for each group the size
        sizes = {}
        for h in group.values():
            if h not in sizes:
                sizes[h] = 0
            sizes[h] += 1

        #make sure the size requirements are met for every hiker in the solution
        for index in group.keys():
            if (lower[index] > sizes[group[index]]) or (upper[index] < sizes[group[index]]):
                logger.error('Hiker {} is not happy with their assignment'.format(str(index)))
                return False

        return True

    def calculate_approximation_ratio(self, instance, instance_size, generator_solution, solver_solution):
        return  float(len(generator_solution)) / float(len(solver_solution))