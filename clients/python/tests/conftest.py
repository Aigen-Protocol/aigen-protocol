"""Pytest bootstrap.

Adds the project root to ``sys.path`` so the test-suite imports the local
``oabp`` package even when it has not been ``pip install``-ed yet (e.g. running
``pytest`` straight from a checkout).
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
