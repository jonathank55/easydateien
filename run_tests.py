#!/usr/bin/env python3
"""Test-Suite für EasyDateien — Kernfunktionen ohne interaktives Terminal.

Führt alle Tests aus allen test_*.py-Dateien im selben Verzeichnis aus
(unittest-Discovery) und beendet sich mit Exit-Code 0 (Erfolg) oder 1 (Misserfolg).
"""

import os
import sys
import unittest

REPO = os.path.dirname(os.path.abspath(__file__))


def main():
    sys.path.insert(0, REPO)
    os.chdir(REPO)
    loader = unittest.TestLoader()
    suite = loader.discover(REPO, pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
