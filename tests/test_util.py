""" Tests for the util.
"""
import unittest
import logging

logging.disable(logging.CRITICAL)


class Matchtests(unittest.TestCase):
    def tests_not_implemented(self):
        self.assertEqual(0, 1)  # Implement tests for util!