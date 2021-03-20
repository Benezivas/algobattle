import logging

from algobattle.verifier import Verifier

logger = logging.getLogger('algobattle.verifier')

class PathpackingVerifier(Verifier):
    def verify_semantics_of_instance(self, instance, instance_size: int):
        # Instances for this problem are semantically valid if they are syntactically valid.
        # We only check if the instance is empty.
        if not instance:
            logger.error('The instance is empty!')
            return False
        return True

    def verify_semantics_of_solution(self, solution, instance_size: int, solution_type: bool):
        if not solution:
            logger.error('The solution is empty!')
            return False

        solution = [line[1:] for line in solution]
        used_nodes = set([])
        for sol_path in solution:
            for sol_node in sol_path:
                if sol_node in used_nodes:
                    logger.error('Not all paths from the certificate are node-disjoint!')
                    return False
                used_nodes.add(sol_node)

        return True

    def verify_solution_against_instance(self, instance, solution, instance_size, solution_type):
        solution = [line[1:] for line in solution]
        for sol_path in solution:
            if (not (('e', sol_path[0], sol_path[1]) in instance or ('e', sol_path[1], sol_path[0]) in instance)
             or not (('e', sol_path[1], sol_path[2]) in instance or ('e', sol_path[2], sol_path[1]) in instance)
            ):
                logger.error('At least one element of the solution is not a path in the input graph!')
                return False
        return True

    def calculate_approximation_ratio(self, instance, instance_size, generator_solution, solver_solution):
        return  float(len(generator_solution)) / float(len(solver_solution))