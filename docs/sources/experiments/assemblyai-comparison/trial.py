"""
Run a step of the trial: `.venv\\Scripts\\python docs\\sources\\experiments\\assemblyai-comparison\\trial.py --help`.
"""

import sys
from pathlib import Path

# The trial reads the transcriber's code from the repository's root, without being part of it.
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from assemblyai_trial.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
