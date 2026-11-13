import sys
from pathlib import Path


# The trial's code is a package beside this file, outside the transcriber's `src`: its tests import it from here.
sys.path.insert(0, str(Path(__file__).parent))
