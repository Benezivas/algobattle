""" Tests for the biclique problem.
"""
import unittest
import logging

from algobattle.problems.clusterediting import parser, verifier

logging.disable(logging.CRITICAL)

class Parsertests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = parser.ClustereditingParser()

    def test_split_into_instance_and_solution(self):
        raw_input = [('e', '1', '2'), ('e', '3', '2'),('s', 'add', '3', '1'), ('s', 'del', '1', '2'), ('foo', 'bar')]
        self.assertEqual(self.parser.split_into_instance_and_solution(raw_input), 
        ([('e', '1', '2'), ('e', '3', '2')], [('s', 'add', '3', '1'), ('s', 'del', '1', '2')]))

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
        raw_solution = [('s', 'add', '3', '1', '5')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [])

        #lines with too few entries should be removed
        raw_solution = [('s', 'add', '5')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [])

        #Lines that use labels higher than instance_size should be removed
        raw_solution = [('s', 'add', '3', '10')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=9), [])

        #Lines with letters should be removed
        raw_solution = [('s', 'add', '3', 'foo')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [])

        #0 label lines should be removed
        raw_solution = [('s', 'add', '0', '1')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [])

        #empty inputs should be handled
        self.assertEqual(self.parser.parse_solution([], instance_size=2), [])

    def test_encode(self):
        self.assertEqual(self.parser.encode([('e', '1', '2'), ('e', '3', '2'),('s', 'add', '1', '3')]), 
"""e 1 2
e 3 2
s add 1 3""".encode())

    def test_decode(self):
        self.assertEqual(self.parser.decode(
"""e 1 2
e 3 2
s add 1 3
""".encode()), [('e', '1', '2'), ('e', '3', '2'),('s', 'add', '1', '3')])


class Verifiertests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = verifier.ClustereditingVerifier()

    def test_verify_semantics_of_instance(self):
        self.assertTrue(self.verifier.verify_semantics_of_instance([('e', '1', '2')], instance_size=10))
        self.assertFalse(self.verifier.verify_semantics_of_instance([], instance_size=10))

    def test_verify_semantics_of_solution(self):
        self.assertFalse(self.verifier.verify_semantics_of_solution([('e', '1', '2')], [], 10, solution_type=False))
        self.assertFalse(self.verifier.verify_semantics_of_solution([('e', '1', '2')], [('s', 'del', '1', '3')], 10, solution_type=False))
        self.assertTrue(self.verifier.verify_semantics_of_solution([('e', '1', '2')], [('s', 'add', '1', '3')], 10, solution_type=False))

    def test_verify_solution_against_instance(self):
        #Deleting a label to make a valid solution should be accepted
        instance = [('e', '1', '2'), ('e', '3', '2'), ('e', '1', '3'), ('e', '1', '4')]
        solution = [('s', 'del', '1', '4')]
        self.assertTrue(self.verifier.verify_solution_against_instance(instance, solution, instance_size=10, solution_type=False))

        #Deleting and adding a label to make a valid solution should be accepted
        instance = [('e', '1', '2'), ('e', '3', '2'), ('e', '1', '4')]
        solution = [('s', 'add', '1', '3'), ('s', 'del', '1', '4')]
        self.assertTrue(self.verifier.verify_solution_against_instance(instance, solution, instance_size=10, solution_type=False))

        instance = [('e', '1', '3'), ('e', '1', '5'), ('e', '1', '9'), ('e', '2', '6'), ('e', '2', '8'), ('e', '2', '9'), ('e', '3', '4'), ('e', '3', '6'), ('e', '3', '7'), ('e', '4', '7'), ('e', '5', '9')]
        solution = [('s', 'del', '2', '9'), ('s', 'del', '1', '3'), ('s', 'del', '3', '6'), ('s', 'add', '6', '8')]
        self.assertTrue(self.verifier.verify_solution_against_instance(instance, solution, instance_size=10, solution_type=False))

        #Deleting an edge to make an invalid solution should not be accepted
        instance = [('e', '1', '2'), ('e', '3', '2'), ('e', '1', '3')]
        solution = [('s', 'del', '1', '3')]
        self.assertFalse(self.verifier.verify_solution_against_instance(instance, solution, instance_size=10, solution_type=False))

        #Adding an edge to make an invalid solution should not be accepted
        instance = [('e', '1', '2'), ('e', '3', '2'), ('e', '1', '3'), ('e', '1', '4')]
        solution = [('s', 'add', '3', '4')]
        self.assertFalse(self.verifier.verify_solution_against_instance(instance, solution, instance_size=10, solution_type=False))

        #Adding and deleting an edge to make an invalid solution should not be accepted
        instance = [('e', '1', '2'), ('e', '3', '2'), ('e', '1', '3'), ('e', '1', '4')]
        solution = [('s', 'add', '3', '4'), ('s', 'del', '1', '3')]
        self.assertFalse(self.verifier.verify_solution_against_instance(instance, solution, instance_size=10, solution_type=False))

    def test_calculate_approximation_ratio(self):
        instance = [('e', '1', '2'), ('e', '1', '3'), ('e', '1', '4'), ('e', '2', '3'), ('e', '2', '4'), ('e', '3', '4'), ('e', '1', '5')]
        solution_sufficient = [('s', 'del', '1', '5')]
        solution_too_much = [('s', 'del', '1', '5'), ('s', 'del', '4', '1'), ('s', 'del', '4', '2'), ('s', 'del', '4', '3')]
        self.assertEqual(self.verifier.calculate_approximation_ratio(instance, 10, solution_sufficient, solution_too_much), 4.0)
        self.assertEqual(self.verifier.calculate_approximation_ratio(instance, 10, solution_sufficient, solution_sufficient), 1.0)

if __name__ == '__main__':
    unittest.main()
