import sys
import unittest
from dataclasses import dataclass

from nexus_core.embedded import registered_module


class EmbeddedContractTests(unittest.TestCase):
    def test_synthetic_module_supports_dataclass(self):
        name = "nexus_test_embedded_module"
        source = """
from dataclasses import dataclass
@dataclass
class Candidate:
    value: int
"""

        with registered_module(name) as module:
            namespace = module.__dict__
            namespace["__name__"] = name
            exec(compile(source, f"<embedded:{name}>", "exec"), namespace)
            self.assertEqual(namespace["Candidate"](3).value, 3)
            self.assertIn(name, sys.modules)

        self.assertNotIn(name, sys.modules)


if __name__ == "__main__":
    unittest.main()
