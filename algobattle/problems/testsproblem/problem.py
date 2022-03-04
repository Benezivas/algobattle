"""Problem class built for tests."""
import logging

from algobattle.problem import Problem, ApproxType

logger = logging.getLogger('algobattle.problems.testsproblem')


class Tests(Problem[list[list[str]], list[str]]):
    """Artificial problem used for tests."""

    name: str = "Tests"
    n_start: int = 1
    approx_type = ApproxType.minimize

    @staticmethod
    def split(input: str) -> tuple[list[str], list[str]]:
        raw_instance = []
        raw_solution = []

        for line in input.splitlines():
            if line[0] == 'i':
                raw_instance.append(line)
            elif line[0] == 's':
                raw_solution.append(line)

        return raw_instance, raw_solution
    
    @staticmethod
    def parse_instance(instance: list[str], size: int) -> list[list[str]]:
        parsed = [line.strip().split() for line in instance if line.strip() != ""]
        if not instance:
            raise ValueError
        if any(line[1] != '1' for line in parsed):
            raise ValueError
        return parsed
    
    @staticmethod
    def parse_solution(solution: list[str], size: int) -> list[list[str]]:
        parsed = [line.strip().split() for line in solution if line.strip() != ""]
        if not parsed:
            raise ValueError
        if any(line[1] != '1' for line in parsed):
            raise ValueError
        return parsed
    
    @staticmethod
    def encode_instance(instance: list[list[str]]) -> str:
        return "\n".join(" ".join(line) for line in instance)
    
    @staticmethod
    def verify_solution(instance: list[list[str]], size: int, solution: list[list[str]]) -> bool:
        if any(line[2] != '1' for line in solution):
            return False

        return True
    
    @staticmethod
    def solution_weight(instance: list[list[str]], size: int, solutoion: list[list[str]]) -> float:
        return len([line for line in solutoion if line[3] == '1'])

