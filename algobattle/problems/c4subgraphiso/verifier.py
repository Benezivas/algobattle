import logging

from algobattle.verifier import Verifier

logger = logging.getLogger('algobattle.verifier')

class C4subgraphisoVerifier(Verifier):
    def verify_semantics_of_solution(self, solution, instance_size: int, solution_type: bool):
        if not solution:
            logger.error('The solution is empty!')
            return False
        solution = [line[1:] for line in solution]
        used_nodes = set()
        for sol_square in solution:
            for sol_node in sol_square:
                if sol_node in used_nodes:
                    logger.error('Not all squares of the solution are node-disjoint!')
                    return False
                used_nodes.add(sol_node)
        return True

    def verify_solution_against_instance(self, instance, solution, instance_size, solution_type):
        solution = [line[1:] for line in solution]
        for sol_square in solution:
            if  (not (('e', sol_square[0], sol_square[1]) in instance or ('e', sol_square[1], sol_square[0]) in instance)
            or not (('e', sol_square[1], sol_square[2]) in instance or ('e', sol_square[2], sol_square[1]) in instance)
            or not (('e', sol_square[2], sol_square[3]) in instance or ('e', sol_square[3], sol_square[2]) in instance)
            or not (('e', sol_square[3], sol_square[0]) in instance or ('e', sol_square[0], sol_square[3]) in instance)
            or ('e', sol_square[0], sol_square[2]) in instance
            or ('e', sol_square[2], sol_square[0]) in instance
            or ('e', sol_square[1], sol_square[3]) in instance
            or ('e', sol_square[3], sol_square[1]) in instance):
                logger.error('At least one element of the solution is not an induced square in the input graph!')
                return False
        return True

    def calculate_approximation_ratio(self, instance, instance_size, generator_solution, solver_solution):
        return float(len(generator_solution)) / float(len(solver_solution))