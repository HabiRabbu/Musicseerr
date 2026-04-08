import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROOT_APP_DIR", tempfile.mkdtemp())

sys.path.insert(0, str(Path(__file__).parent.parent))
