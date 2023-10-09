"""Tests for all util functions."""
import unittest

from algobattle.battle import Battle, Iterated, Averaged


class Utiltests(unittest.TestCase):
    """Tests for the util functions."""

    def test_default_battle_types(self):
        """Initializing an existing battle type works as expected."""
        self.assertEqual(Battle.all()["Iterated"], Iterated)
        self.assertEqual(Battle.all()["Averaged"], Averaged)


if __name__ == "__main__":
    unittest.main()
