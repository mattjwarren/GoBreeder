"""pytest configuration: ensure GoBreeder/breed is importable."""

import os
import sys

# Add breed directory to sys.path so that tests can import the modules.
_BREED_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "GoBreeder", "breed"))
if _BREED_DIR not in sys.path:
    sys.path.insert(0, _BREED_DIR)
