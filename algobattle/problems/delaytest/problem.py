"""Dummy problem class for delaytest."""
import logging

from algobattle.problem import ApproxType, Problem

logger = logging.getLogger('algobattle.problems.delaytest')


class Delaytest(Problem[None, None]):
    """Dummy Problem used for testing Docker delays."""

    name = 'Runtime Delay Test'
    n_start: int = 1
    approx_type = ApproxType.maximize

    @staticmethod
    def split(input: str) -> tuple[list[str], list[str]]:
        return [], []
    
    @staticmethod
    def parse_instance(instance: list[str], size: int) -> None:
        return None
    
    @staticmethod
    def parse_solution(solution: list[str], size: int) -> None:
        return None
    
    @staticmethod
    def encode_instance(instance: None) -> str:
        return ""
    
    @staticmethod
    def verify_solution(instance: None, size: int, solution: None) -> bool:
        return True
    
    @staticmethod
    def solution_weight(instance: None, size: int, solutoion: None) -> float:
        return 1
