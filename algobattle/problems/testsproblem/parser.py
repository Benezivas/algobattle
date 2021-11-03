"""Dummy parser built for tests."""
import logging

from algobattle.parser import Parser

logger = logging.getLogger('algobattle.problems.testsproblem.parser')


class TestsParser(Parser):
    """Dummy parser."""

    def split_into_instance_and_solution(self, raw_input):
        raw_instance = []
        raw_solution = []

        for line in raw_input:
            if line[0] == 'i':
                raw_instance.append(line)
            elif line[0] == 's':
                raw_solution.append(line)

        return raw_instance, raw_solution

    def parse_instance(self, raw_instance, instance_size):
        return raw_instance

    def parse_solution(self, raw_solution, instance_size):
        return raw_solution

    def encode(self, input):
        return super().encode(input)

    def decode(self, raw_input):
        return super().decode(raw_input)
