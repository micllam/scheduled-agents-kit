import glob
import os
import unittest

from tests import plan

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "examples")


class ExamplesTest(unittest.TestCase):
    def test_examples_are_valid_manifests(self):
        paths = glob.glob(os.path.join(EXAMPLES, "*.toml"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=os.path.basename(path)):
                plan.read_manifest(path)
