"""Top-level conftest that makes the repository root importable.

This ensures ``from app.xxx import ...`` works in tests regardless of how
pytest is invoked (``pytest`` vs ``python -m pytest``) and independent of
pytest's import-mode / rootdir heuristics.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
