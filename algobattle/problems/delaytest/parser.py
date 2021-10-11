import logging

from algobattle.parser import Parser

logger = logging.getLogger('algobattle.problems.delaytest.parser')


class DelaytestParser(Parser):
    """Dummy parser used for testing Docker delays."""

    def split_into_instance_and_solution(self, raw_input):
        return raw_input, raw_input

    def parse_instance(self, raw_instance, instance_size):
        return raw_instance

    def parse_solution(self, raw_solution, instance_size):
        return raw_solution

    def encode(self, input):
        return super().encode(input)

    def decode(self, raw_input):
        return raw_input.decode().splitlines()
