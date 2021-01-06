import logging

from verifier import Verifier

logger = logging.getLogger('algobattle.verifier')

class HikersVerifier(Verifier):
    def verify_solution_against_instance(self, instance, solution, instance_size):
        if not instance:
            logger.error('The instance is empty!')
            return True
        if not solution:
            logger.error('The solution is empty!')
            return False

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

    def verify_solution_quality(self, generator_solution, solver_solution):
        return super().verify_solution_quality(generator_solution, solver_solution)