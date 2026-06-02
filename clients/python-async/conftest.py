"""Pytest bootstrap: make the in-tree ``oabp_async`` package importable.

This lets ``pytest`` run straight from a clean checkout without an editable
install.  When the package is installed (``pip install .``) this is harmless —
the installed copy is found first on ``sys.path`` anyway.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
