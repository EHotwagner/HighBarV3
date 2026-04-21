# pytest conftest — add highbar_client/ to sys.path so the buf-generated
# stubs' absolute `from highbar import ...` imports resolve.
import sys
from pathlib import Path

_pkg_dir = Path(__file__).parent / "highbar_client"
sys.path.insert(0, str(_pkg_dir))
