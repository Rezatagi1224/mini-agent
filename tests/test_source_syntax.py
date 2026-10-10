import ast
import unittest
from pathlib import Path


class PythonSourceSyntaxTests(unittest.TestCase):
    def test_all_root_python_modules_parse(self):
        for path in sorted(Path(".").glob("*.py")):
            with self.subTest(path=str(path)):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


if __name__ == "__main__":
    unittest.main()
