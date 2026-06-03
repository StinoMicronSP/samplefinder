import sys
from pathlib import Path

# Zorg dat `import sample_finder` werkt ongeacht vanwaar pytest gestart wordt.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
