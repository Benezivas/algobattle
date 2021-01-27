import logging

from verifier import Verifier

logger = logging.getLogger('algobattle.verifier')

class DsapproxVerifier(Verifier):
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
        all_nodes = set()
        domination = {}
        for edge in instance:
            domination[edge[1]] = domination.get(edge[1], set())
            domination[edge[2]] = domination.get(edge[2], set())
            domination[edge[1]].add(edge[1])
            domination[edge[1]].add(edge[2])
            domination[edge[2]].add(edge[1])
            domination[edge[2]].add(edge[2])
            all_nodes.add(edge[1])
            all_nodes.add(edge[2])

        dominated_nodes = set()
        for node in solution:
            dominated_nodes.update(domination[node[2]])

        if all_nodes != dominated_nodes:
            logger.error('The solution set does not dominate all nodes!')
            return False

        return True

    def verify_solution_quality(self, instance, instance_size, generator_solution, solver_solution):
        return len(solver_solution) <= 2 * len(generator_solution)