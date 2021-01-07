import logging

from verifier import Verifier

logger = logging.getLogger('algobattle.verifier')

class PathpackingVerifier(Verifier):
    def verify_solution_against_instance(self, instance, solution, instance_size):
        if not instance:
            logger.error('The instance is empty!')
            return True
        if not solution:
            logger.error('The solution is empty!')
            return False

        solution = [line[2:] for line in solution]
        used_nodes = set([])
        for sol_path in solution:
            for sol_node in sol_path:
                if sol_node in used_nodes:
                    logger.error('Not all paths from the certificate are node-disjoint!')
                    return False
                used_nodes.add(sol_node)
            if (not (('e', sol_path[0], sol_path[1]) in instance or ('e', sol_path[1], sol_path[0]) in instance)
            or not (('e', sol_path[1], sol_path[2]) in instance or ('e', sol_path[2], sol_path[1]) in instance)
            ):
                logger.error('At least one element of the solution is not a path in the input graph!')
                return False
        return True

    def verify_solution_quality(self, generator_solution, solver_solution):
        return super().verify_solution_quality(generator_solution, solver_solution)