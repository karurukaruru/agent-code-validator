import unittest
from patchcourt.reproductions import run_reproductions

class Regression(unittest.TestCase):
    def test_repairs(self):
        for case in run_reproductions():
            self.assertEqual(case["status"], "FAIL", case["id"])
            self.assertEqual(case["repair"]["status"], "VERIFIED", case["id"])

if __name__ == "__main__":
    unittest.main()
