"""Root pytest conftest: add GoBreeder/breed to sys.path so tests can import modules."""
import sys
import os

_BREED_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "GoBreeder", "breed")
)
if _BREED_DIR not in sys.path:
    sys.path.insert(0, _BREED_DIR)
