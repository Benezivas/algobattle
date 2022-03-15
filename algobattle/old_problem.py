"""Module to provide backwards compatibility to old problem classes."""
from __future__ import annotations
from typing import Literal
from algobattle.problem import Problem as NewProblem
from algobattle.problem import WeightType

class Problem(NewProblem):
    """Wrapper class that provides the same interface as the new Problem class when inherited from an old Problem."""
    weight_type = WeightType.unweighted
    name = ""
    n_start = 0
    parser: Parser
    verifier: Verifier
    approximable: bool
    approx_type: Literal["minimize", "maximize"]

    def __init_subclass__(cls) -> None:
        cls.__bases__ = (*cls.__bases__, NewProblem)
        return super().__init_subclass__()

    def split(self, input):
        decoded = self.parser.decode(input)
        return self.parser.split_into_instance_and_solution(decoded)
    
    def parse_instance(self, input, size):
        parsed = self.parser.parse_instance(input, size)
        if not parsed:
            raise ValueError
        if not self.verifier.verify_semantics_of_instance(parsed, size):
            raise ValueError
        return parsed
    
    def parse_solution(self, solution, size):
        if len(solution) > 0 and isinstance(solution[0], str):
            solution = self.parser.decode("\n".join(solution))
        parsed = self.parser.parse_solution(solution, size)
        if not parsed:
            raise ValueError
        if not self.verifier.verify_semantics_of_solution(solution, size, True):
            raise ValueError
        return parsed
    
    def verify_solution(self, instance, size, solution):
        res = self.verifier.verify_solution_against_instance(instance, solution, size, True)
        self.parser.postprocess_instance(instance, size)
        return res

    def approximation_ratio(self, instance, size: int, generator, solver):
        if self.approximable:
            approx_ratio = self.verifier.calculate_approximation_ratio(instance, size, generator, solver)
            if approx_ratio == 0:
                return 0
            else:
                if self.approx_type == "minimize":
                    return 1 / approx_ratio
                else:
                    return approx_ratio
        else:
            return 1

    def encode_instance(self, instance):
        return self.parser.encode(instance)

class Parser:
    def split_into_instance_and_solution(self, raw_input): ...
    def parse_instance(self, raw_instance, instance_size: int): ...
    def parse_solution(self, raw_solution, instance_size: int): ...

    def postprocess_instance(self, instance, instance_size: int):
        return instance

    def encode(self, input) -> str:
        return "\n".join(str(" ".join(str(element) for element in line)) for line in input)

    def decode(self, raw_input: str):
        return [tuple(line.split()) for line in raw_input.splitlines() if line.split()]

class Verifier:
    def verify_solution_against_instance(self, instance, solution, instance_size: int, solution_type: bool) -> bool: ...
    def calculate_approximation_ratio(self, instance, instance_size: int,generator_solution, solver_solution) -> float: ...

    def verify_semantics_of_instance(self, instance, instance_size: int) -> bool:
        if not instance:
            return False
        return True

    def verify_semantics_of_solution(self, solution, instance_size: int, solution_type: bool) -> bool:
        if not solution:
            return False
        return True
