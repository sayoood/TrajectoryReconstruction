"""Put the repository root on sys.path so tests import ``trajlib`` and ``pipeline``
exactly as the entry scripts do (they insert their own directory the same way)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
