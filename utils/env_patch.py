"""
utils/env_patch.py — Centralized environment fixes for Streamlit Cloud
──────────────────────────────────────────────────────────────────────
Included fixes:
  1. SQLite: Swaps in pysqlite3 for system sqlite3 (needs >= 3.35.0)
  2. NumPy: Restores legacy attributes (int_, float_, etc.) for ChromaDB 0.4.x
"""

import sys

# 1. SQLite Patch
try:
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass

# 2. NumPy Patch
try:
    import numpy as np
    # NumPy 2.0 removed several attributes that older libraries (ChromaDB 0.4) expect.
    if not hasattr(np, "int_"):
        # Use intp (platform integer) as the replacement for int_
        np.int_ = np.intp if hasattr(np, "intp") else int
    if not hasattr(np, "float_"):
        np.float_ = float
    if not hasattr(np, "bool_"):
        np.bool_ = bool
    if not hasattr(np, "unicode_"):
        np.unicode_ = str
except ImportError:
    pass
