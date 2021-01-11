import logging

from verifier import Verifier

logger = logging.getLogger('algobattle.verifier')

class C4subgraphisoVerifier(Verifier):
    def verify_solution_against_instance(self, instance, solution, instance_size, solution_type):
        if not instance:
            logger.error('The instance is empty!')
            return True
        if not solution:
            logger.error('The solution is empty!')
            return False

        solution = [line[2:] for line in solution]
        used_nodes = set()
        for sol_square in solution:
            for sol_node in sol_square:
                if sol_node in used_nodes:
                    logger.error('Not all squares of the solution are node-disjoint!')
                    return False
                used_nodes.add(sol_node)
            if (not (('e', sol_square[0], sol_square[1]) in instance or ('e', sol_square[1], sol_square[0]) in instance)
            or not (('e', sol_square[1], sol_square[2]) in instance or ('e', sol_square[2], sol_square[1]) in instance)
            or not (('e', sol_square[2], sol_square[3]) in instance or ('e', sol_square[3], sol_square[2]) in instance)
            or not (('e', sol_square[3], sol_square[0]) in instance or ('e', sol_square[0], sol_square[3]) in instance)
            or ('e', sol_square[0], sol_square[2]) in instance
            or ('e', sol_square[2], sol_square[0]) in instance
            or ('e', sol_square[1], sol_square[3]) in instance
            or ('e', sol_square[3], sol_square[1]) in instance
            ):
                logger.error('At least one element of the solution is not an induced square in the input graph!')
                return False
        return True

    def verify_solution_quality(self, instance, instance_size, generator_solution, solver_solution):
        return super().verify_solution_quality(instance, instance_size, generator_solution, solver_solution)