""" Tests for the biclique problem.
"""
import unittest
import logging

from algobattle.problems.c4subgraphiso import parser, verifier

logging.disable(logging.CRITICAL)

class Parsertests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = parser.C4subgraphisoParser()

    def test_split_into_instance_and_solution(self):
        raw_input = [('e', '1', '2'), ('s', '5', '6', '7', '8'), ('s', '2'), ('foo', 'bar')]
        self.assertEqual(self.parser.split_into_instance_and_solution(raw_input), 
        ([('e', '1', '2')], [('s', '5', '6', '7', '8'), ('s', '2')]))

        #empty inputs should be handled
        self.assertEqual(self.parser.split_into_instance_and_solution([]), ([],[]))

    def test_parse_instance(self):
        #lines with too many entries should be removed
        raw_instance = [('e', '1', '2', '1'),('e', '3', '2')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [('e', '3', '2')])

        #lines with too few entries should be removed
        raw_instance = [('e', '1'), ('e')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=2), [])

        #Lines that use labels higher than instance_size should be removed
        raw_instance = [('e', '3', '2')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=2), [])

        #Duplicates should be removed
        raw_instance = [('e', '3', '2'), ('e', '3', '2')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [('e', '3', '2')])

        #Lines with letters should be removed
        raw_instance = [('e', '3', 'a'), ('e', 'b', '2')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [])

        #0 label lines should be removed
        raw_instance = [('e', '1', '0'), ('e', '0', '1')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [])

        #selfloop lines should be removed
        raw_instance = [('e', '1', '1')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [])

        #empty inputs should be handled
        self.assertEqual(self.parser.parse_instance([], instance_size=3), [])

    def test_parse_solution(self):
        #lines with too many entries should be removed
        raw_solution = [('s', '1', '2', '9', '10', '1'), ('s', '5', '6', '7', '8')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [('s', '5', '6', '7', '8')])

        #lines with too few entries should be removed
        raw_solution = [('s', '1', '2', '9')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [])

        #Lines that use labels higher than instance_size should be removed
        raw_solution = [('s', '1', '2', '9', '10')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=9), [])

        #Lines with letters should be removed
        raw_solution = [('s', '1', 'foo', '9', '10')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [])

        #0 label lines should be removed
        raw_solution = [('s', '1', '0', '9', '10')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [])

        #empty inputs should be handled
        self.assertEqual(self.parser.parse_solution([], instance_size=2), [])

    def test_encode(self):
        self.assertEqual(self.parser.encode([('s', '1', '2', '9', '10'), ('s', '5', '6', '7', '8'), ('e', '1', '2'), ('e', '2', '3'), ('e', '3', '4'), ('e', '3', '5'), ('e', '5', '6'), ('e', '6', '7'), ('e', '7', '8'), ('e', '8', '9'), ('e', '9', '10'), ('e', '10', '1'), ('e', '2', '9'), ('e', '5', '9'), ('e', '5', '8')]), 
"""s 1 2 9 10
s 5 6 7 8
e 1 2
e 2 3
e 3 4
e 3 5
e 5 6
e 6 7
e 7 8
e 8 9
e 9 10
e 10 1
e 2 9
e 5 9
e 5 8""".encode())

    def test_decode(self):
        self.assertEqual(self.parser.decode(
"""s 1 2 9 10
s 5 6 7 8
e 1 2
e 2 3
e 3 4
e 3 5
e 5 6
e 6 7
e 7 8
e 8 9
e 9 10
e 10 1
e 2 9
e 5 9
e 5 8
""".encode()), [('s', '1', '2', '9', '10'), ('s', '5', '6', '7', '8'), ('e', '1', '2'), ('e', '2', '3'), ('e', '3', '4'), ('e', '3', '5'), ('e', '5', '6'), ('e', '6', '7'), ('e', '7', '8'), ('e', '8', '9'), ('e', '9', '10'), ('e', '10', '1'), ('e', '2', '9'), ('e', '5', '9'), ('e', '5', '8')])


class Verifiertests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = verifier.C4subgraphisoVerifier()

    def test_verify_semantics_of_instance(self):
        self.assertTrue(self.verifier.verify_semantics_of_instance([('e', '1', '2')], instance_size=10))
        self.assertFalse(self.verifier.verify_semantics_of_instance([], instance_size=10))

    def test_verify_semantics_of_solution(self):
        self.assertFalse(self.verifier.verify_semantics_of_solution([('e', '1', '2')], [], 10, solution_type=False))
        self.assertFalse(self.verifier.verify_semantics_of_solution([], [('s', '5', '6', '7', '8'), ('s', '5', '2', '9', '10')], instance_size=10, solution_type=False))

    def test_verify_solution_against_instance(self):
        instance = [('e', '1', '2'), ('e', '2', '3'), ('e', '3', '4'), ('e', '3', '5'), ('e', '5', '6'), ('e', '6', '7'), ('e', '7', '8'), ('e', '8', '9'), ('e', '9', '10'), ('e', '10', '1'), ('e', '2', '9'), ('e', '5', '9'), ('e', '5', '8')]
        solution = [('s', '1', '2', '9', '10'), ('s', '5', '6', '7', '8')]
        self.assertTrue(self.verifier.verify_solution_against_instance(instance, solution, instance_size=10, solution_type=False))

        solution = [('s', '1', '2', '9', '10'), ('s', '5', '6', '7', '3')]
        self.assertFalse(self.verifier.verify_solution_against_instance(instance, solution, instance_size=10, solution_type=False))

    def test_calculate_approximation_ratio(self):
        instance = [('e', '1', '2'), ('e', '2', '3'), ('e', '3', '4'), ('e', '3', '5'), ('e', '5', '6'), ('e', '6', '7'), ('e', '7', '8'), ('e', '8', '9'), ('e', '9', '10'), ('e', '10', '1'), ('e', '2', '9'), ('e', '5', '9'), ('e', '5', '8')]
        solution_full = [('s', '1', '2', '9', '10'), ('s', '5', '6', '7', '8')]
        solution_small = [('s', '1', '2', '9', '10')]
        self.assertEqual(self.verifier.calculate_approximation_ratio(instance, 10, solution_full, solution_small), 2.0)
        self.assertEqual(self.verifier.calculate_approximation_ratio(instance, 10, solution_full, solution_full), 1.0)

if __name__ == '__main__':
    unittest.main()
