"""Ensure the repository root is importable when running the test suite.

Putting a conftest.py at the repo root makes pytest add this directory to
sys.path, so `import core`, `import cli`, `import settings`, etc. resolve the
same way they do when the app is launched from the project root.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
