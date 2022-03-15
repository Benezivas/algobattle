"""Module to provide backwards compatibility to old problem classes."""
from __future__ import annotations
from typing import Type, Any
from abc import ABC, abstractmethod

from algobattle.problem import Problem as NewProblem
from algobattle.problem import WeightType


class Problem(ABC, NewProblem):
    """Problem Class, bundling together the verifier and parser of a problem.

    Enforces the necessary attribute n_start which is the smallest iteration
    size for a problem as well as a flag indicating whether a problem is
    usable in an approximation setting.
    """
    weight_type = WeightType.unweighted
    name = ""
    n_start = 0
    parser: Parser
    verifier: Verifier
    approximable: bool
    minimize: bool = False

    def generator_memory_scaler(self, memory, instance_size):
        return memory

    def solver_memory_scaler(self, memory, instance_size):
        return memory

    def __str__(self) -> str:
        return self.name

    @classmethod
    def split(cls, input):
        decoded = cls.parser.decode(input)
        return cls.parser.split_into_instance_and_solution(decoded)
    
    @classmethod
    def parse_instance(cls, input, size):
        cls.size = size
        parsed = cls.parser.parse_instance(input, size)
        if not parsed:
            raise ValueError
        if not cls.verifier.verify_semantics_of_instance(parsed, size):
            raise ValueError
        return parsed
    
    @classmethod
    def parse_solution(cls, solution, size):
        parsed = cls.parser.parse_solution(solution, size)
        if not parsed:
            raise ValueError
        if not cls.verifier.verify_semantics_of_solution(solution, size, True):
            raise ValueError
        return parsed
    
    @classmethod
    def verify_solution(cls, instance, size, solution):
        return cls.verifier.verify_solution_against_instance(instance, solution, size, True)
    
    @classmethod
    def approximation_ratio(cls, instance, size: int, generator, solver):
        if cls.approximable:
            if cls.minimize:
                approx_ratio = cls.verifier.calculate_approximation_ratio(instance, size, generator, solver)
                if approx_ratio == 0:
                    return 0
                else:
                    return 1 / approx_ratio
            else:
                approx_ratio = cls.verifier.calculate_approximation_ratio(instance, size, generator, solver)
                if approx_ratio == 0:
                    return 0
                else:
                    return approx_ratio
        else:
            return 1

    @classmethod
    def encode_instance(cls, instance):
        cls.parser.postprocess_instance(instance, cls.size)
        return cls.parser.encode(instance)

class Parser(ABC):

    @abstractmethod
    def split_into_instance_and_solution(self, raw_input: Any) -> tuple[Any, Any]:
        raise NotImplementedError

    @abstractmethod
    def parse_instance(self, raw_instance: Any, instance_size: int) -> Any:
        raise NotImplementedError

    @abstractmethod
    def parse_solution(self, raw_solution: Any, instance_size: int) -> Any:
        raise NotImplementedError

    def postprocess_instance(self, instance: Any, instance_size: int) -> Any:
        return instance

    @abstractmethod
    def encode(self, input: Any) -> str:
        return "\n".join(str(" ".join(str(element) for element in line)) for line in input)

    @abstractmethod
    def decode(self, raw_input: str) -> Any:
        return [tuple(line.split()) for line in raw_input.splitlines() if line.split()]

class Verifier(ABC):

    def verify_semantics_of_instance(self, instance: Any, instance_size: int) -> bool:
        if not instance:
            return False
        return True

    def verify_semantics_of_solution(self, solution: Any, instance_size: int, solution_type: bool) -> bool:
        if not solution:
            return False
        return True

    @abstractmethod
    def verify_solution_against_instance(self, instance: Any, solution: Any, instance_size: int, solution_type: bool) -> bool:
        raise NotImplementedError

    @abstractmethod
    def calculate_approximation_ratio(self, instance: Any, instance_size: int,
                                      generator_solution: Any, solver_solution: Any) -> float:
        raise NotImplementedError






def OldProblemIsMinimization(cls: Type[Problem]) -> Type[NewProblem]:
    """Decorator to turn an old Problem class into a new one."""
    cls.minimize = True

    return cls
