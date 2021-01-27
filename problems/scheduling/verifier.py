import logging

from verifier import Verifier

logger = logging.getLogger('algobattle.verifier')

class SchedulingVerifier(Verifier):
    def verify_semantics_of_instance(self, instance, instance_size: int):
        if not instance:
            logger.error('The instance is empty!')
            return False

        if sum(int(job[2]) for job in instance) * 5 >= 2 ** 64:
            logger.warning('The cumulated job sizes exceed the given limit!')
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
        if len(solution) < len(instance):
            logger.error('The solution does not schedule all jobs!')
            return False
        
        return True

    def verify_solution_quality(self, instance, instance_size, generator_solution, solver_solution):
        jobs_to_be_scheduled = [job[1] for job in instance]
        # As the instance may have lost some jobs during parsing that were
        # assumed to be present, we may need to cut down the generator solution
        generator_solution = [assignment for assignment in generator_solution if assignment[1] in jobs_to_be_scheduled]

        generator_makespan = self.calculate_makespan(instance, generator_solution)
        solver_makespan = self.calculate_makespan(instance, solver_solution)

        return solver_makespan <= generator_makespan


    def calculate_makespan(self, jobs, assignments):
        makespans = [0 for i in range(5)]

        for assignment in assignments:
            job_number = assignment[1]
            machine = int(assignment[2])
            base_running_time = 0
            for job in jobs:
                if job[1] == job_number:
                    base_running_time = int(job[2])
            makespans[machine - 1] += base_running_time * machine

        return max(makespans)

