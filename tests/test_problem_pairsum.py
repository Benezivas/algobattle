""" Tests for the biclique problem.
"""
import unittest
import logging

from algobattle.problems.pairsum import parser, verifier

logging.disable(logging.CRITICAL)


class Parsertests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = parser.PairsumParser()

    def test_split_into_instance_and_solution(self):
        raw_input = ['1 2 3 4', '0 3 1 2']
        self.assertEqual(self.parser.split_into_instance_and_solution(raw_input),
                         ('1 2 3 4', ['0 3 1 2']))

        # empty inputs should be handled
        self.assertEqual(self.parser.split_into_instance_and_solution([]), ('', ['']))

        # Input of wrong length are discarded
        self.assertEqual(self.parser.split_into_instance_and_solution(['1', '2', '3']), ('', ['']))

    def test_parse_instance(self):
        # Entries should be ints
        raw_instance = '1 2 3 4 a'
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=10), [1, 2, 3, 4])

        raw_instance = '1 a 3 4 -10'
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=10), [1, 3, 4])

        # entries should not exceed 2**63
        raw_instance = '1 2 3 4 100000000000000000000000000000000000000000000'
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=10), [1, 2, 3, 4])

        # Instance should be cut down to instance_size number of entries
        raw_instance = '1 2 3 4 5 6'
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=5), [1, 2, 3, 4, 5])

        # empty inputs should be handled
        self.assertEqual(self.parser.parse_instance([], instance_size=3), [])

    def test_parse_solution(self):
        # Entries should be ints
        raw_solution = ['0 3 1 2 a']
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [0, 3, 1, 2])

        # Entries should not exceed instance_size
        raw_solution = ['0 3 1 2 4']
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=3), [0, 3, 1, 2])

    def test_encode(self):
        self.assertEqual(self.parser.encode(['1 2 3 4']),
                         """1 2 3 4""".encode())

    def test_decode(self):
        self.assertEqual(self.parser.decode(
                         """1 2 3 4\n0 3 1 2""".encode()), ['1 2 3 4', '0 3 1 2'])


class Verifiertests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = verifier.PairsumVerifier()

    def test_verify_semantics_of_instance(self):
        self.assertTrue(self.verifier.verify_semantics_of_instance([1, 2, 3, 4], instance_size=10))
        self.assertFalse(self.verifier.verify_semantics_of_instance([], instance_size=10))

    def test_verify_semantics_of_solution(self):
        self.assertFalse(self.verifier.verify_semantics_of_solution([], 10, solution_type=False))
        self.assertFalse(self.verifier.verify_semantics_of_solution([0, 3, 1], 10, solution_type=False))
        self.assertFalse(self.verifier.verify_semantics_of_solution([0, 3, 1, 1], 10, solution_type=False))
        self.assertTrue(self.verifier.verify_semantics_of_solution([0, 3, 1, 2], 10, solution_type=False))

    def test_verify_solution_against_instance(self):
        # Valid solutions should be accepted
        instance = [1, 2, 3, 4]
        solution = [0, 3, 1, 2]
        self.assertTrue(self.verifier.verify_solution_against_instance(instance,
                                                                       solution, instance_size=10, solution_type=False))

        # Invalid solutions should not be accepted
        instance = [1, 2, 3, 4]
        solution = [0, 1, 2, 3]
        self.assertFalse(self.verifier.verify_solution_against_instance(instance,
                                                                        solution, instance_size=10, solution_type=False))

    def test_calculate_approximation_ratio(self):
        instance = [1, 2, 3, 4]
        solution = [0, 1, 2, 3]
        self.assertEqual(self.verifier.calculate_approximation_ratio(instance, 10, solution, solution), 1.0)


if __name__ == '__main__':
    unittest.main()
